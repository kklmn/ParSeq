# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Mar 2019"
# !!! SEE CODERULES.TXT !!!

import os.path as osp
from silx.gui import qt
import platform as pythonplatform
import webbrowser
from . import gl

from ..core import singletons as csi
from . import webWidget as gww
# path to ParSeq:
import os, sys; sys.path.append(os.path.join('..', '..'))  # analysis:ignore
import parseq
from ..version import __version__ as parseqversion

redStr = ':red:`{0}`'
try:
    import pyopencl as cl
    cl_platforms = cl.get_platforms()
    isOpenCL = True
    isOpenStatus = 'present'
except ImportError:
    isOpenCL = False
    isOpenStatus = redStr.format('not found')
except cl.LogicError:
    isOpenCL = False
    isOpenStatus = 'is installed '+redStr.format('but no OpenCL driver found')

PARSEQPATH = osp.dirname(osp.dirname(osp.abspath(__file__)))
ICONPATHP = osp.join(osp.dirname(__file__), '_images', 'parseq.ico')
ICONPATHR = osp.join(osp.dirname(__file__), '_images', 'readme.png')


class AboutDialog(qt.QDialog):
    def __init__(self, parent):
        super(AboutDialog, self).__init__(parent)
        self.setWindowTitle("About")
        self.setWindowIcon(qt.QIcon(ICONPATHR))

        self.parseq_pypi_version = self.check_pypi_version()  # pypi_ver, cur_ver  # noqa

        self.tabBar = qt.QTabBar(parent=self)
        self.tabNames = ['ParSeq', csi.pipelineName]
        self.iconPaths = [ICONPATHP, csi.appIconPath]
        for tabName, iconPath in zip(self.tabNames, self.iconPaths):
            icon = qt.QIcon(iconPath) if iconPath else qt.QIcon()
            self.tabBar.addTab(icon, tabName)
        self.tabBar.currentChanged.connect(self.changePage)
        self.webView = self.makeWebView()

        layout = qt.QVBoxLayout()
        layout.addWidget(self.tabBar)
        layout.setSpacing(0)
        layout.addWidget(self.webView)
        self.setLayout(layout)
        self.resize(0, 0)

        self.rawTexts = [self.makeTextMain(), self.makeTextPipeline()]
        currentIndex = 1
        self.tabBar.setCurrentIndex(currentIndex)
        self.changePage(currentIndex)

    def makeWebView(self):
        view = gww.QWebView()
        view.page().setLinkDelegationPolicy(2)
        view.setMinimumWidth(500+50)
        view.setMinimumHeight(510+40)
        view.history().clear()
        view.page().history().clear()
        self.lastBrowserLink = ''
        view.page().linkClicked.connect(
            self.linkClicked, type=qt.Qt.UniqueConnection)

        self.sphinxThread = qt.QThread(self)
        self.sphinxWorker = gww.SphinxWorker()
        self.sphinxWorker.moveToThread(self.sphinxThread)
        self.sphinxThread.started.connect(self.sphinxWorker.render)
        self.sphinxWorker.html_ready.connect(self._on_sphinx_thread_html_ready)

        return view

    def _on_sphinx_thread_html_ready(self):
        self.webView.load(qt.QUrl(gww.parSeqPage))

    def renderLiveDoc(self, doc, docName, docArgs="", docNote="", img_path=""):
        self.sphinxWorker.prepare(doc, docName, docArgs, docNote, img_path)
        self.sphinxThread.start()

    def makeTextMain(self):
        Qt_version = qt.QT_VERSION_STR
        PyQt_version = qt.PYQT_VERSION_STR
        locos = pythonplatform.platform(terse=True)
        if 'Linux' in locos:
            locos = " ".join(pythonplatform.linux_distribution())
        if gl.isOpenGL:
            strOpenGL = '{0} {1}'.format(gl.__name__, gl.__version__)
            if not bool(gl.glutBitmapCharacter):
                strOpenGL += ' ' + redStr.format('but GLUT is not found')
        else:
            strOpenGL = 'OpenGL '+redStr.format('not found')
        if isOpenCL:
            vercl = cl.VERSION
            if isinstance(vercl, (list, tuple)):
                vercl = '.'.join(map(str, vercl))
        else:
            vercl = isOpenStatus
        strOpenCL = r'pyopencl {}'.format(vercl)
        strParSeq = 'ParSeq {0} in {1}'.format(
            parseqversion, PARSEQPATH).replace('\\', '\\\\')
        if type(self.parseq_pypi_version) is tuple:
            pypi_ver, cur_ver = self.parseq_pypi_version
            if cur_ver < pypi_ver:
                strParSeq += \
                    ', **version {0} is available from** PyPI_'.format(pypi_ver)
            else:
                strParSeq += ', this is the latest version at PyPI_'

        txt = u"""
+-------+--------------------+
| |ico| |   |br| |synopsis|  |
+-------+--------------------+

.. |br| raw:: html

   <br/>

.. |ico| image:: ../gui/_images/parseq.ico
   :scale: 100 %

.. |synopsis| replace::
   :bigger:`{0}`

{1}

:Created by:
    Konstantin Klementiev (`MAX IV Laboratory <https://www.maxiv.lu.se/>`_)
:License:
    MIT License, Nov 2018
:Your system:
    {2}, Python {3}\n
    Qt {4}, {5} {6}\n
    {7}\n
    {8}\n
    {9} """.format(
            parseq.__synopsis__, parseq.__doc__,
            locos, pythonplatform.python_version(), Qt_version, qt.BINDING,
            PyQt_version, strOpenGL, strOpenCL, strParSeq)
#        txt = txt.replace('imagezoom::', 'image::')
        return txt

    def makeTextPipeline(self):
        iconPath = csi.appIconPath
        path = csi.appPath
        if os.name == 'nt':
            iconPath = iconPath.replace('\\', '\\\\')
            path = path.replace('\\', '\\\\')
        elif os.name.startswith('posix'):
            iconPath = '/' + iconPath
        txt = u"""
+-------+--------------------+
| |ico| |   |br| |synopsis|  |
+-------+--------------------+

.. |br| raw:: html

   <br/>

.. |ico| image:: {0}
   :scale: {1:.0%}

.. |synopsis| replace::
   :bigger:`{2}`

{3}

:Created by:
    {4}
:License:
    {5}
:Located at:
    {6}
    """.format(iconPath, csi.appIconScale, csi.appSynopsis,
               csi.appDescription, csi.appAuthor, csi.appLicense, path)
        return txt

    def changePage(self, itab):
        self.renderLiveDoc(self.rawTexts[itab], self.tabNames[itab])

    def check_pypi_version(self):
        try:
            import requests
            import distutils.version as dv
            import json
            PyPI = 'https://pypi.python.org/pypi/parseq/json'
            req = requests.get(PyPI)
            if req.status_code != requests.codes.ok:
                return
            rels = json.loads(req.text)['releases']
            v = max([dv.LooseVersion(r) for r in rels if 'b' not in r])
            return v, dv.LooseVersion(parseqversion)
        except:  # noqa
            pass

    def linkClicked(self, url):
        strURL = str(url.toString())
#        if strURL.endswith('tutorial.html') or strURL.endswith('tutorial'):
#            self.showTutorial(tutorial.__doc__[60:],
#                              "Using xrtQook for script generation")
        if strURL.startswith('http') or strURL.startswith('ftp'):
            if self.lastBrowserLink == strURL:
                return
            webbrowser.open(strURL)
            self.lastBrowserLink = strURL
