# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Mar 2019"
# !!! SEE CODERULES.TXT !!!

import os
import os.path as osp
import re
from silx.gui import qt
from silx import version as versilx
import platform as pythonplatform
import webbrowser

from ..core import singletons as csi
from . import webWidget as gww
# path to ParSeq:
import sys; sys.path.append(osp.join('..', '..'))  # analysis:ignore
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
ICONPATHR = osp.join(osp.dirname(__file__), '_images', 'icon-info.png')


class AboutDialog(qt.QDialog):
    def __init__(self, parent):
        super(AboutDialog, self).__init__(parent)
        self.setWindowTitle("About")
        self.setWindowIcon(qt.QIcon(ICONPATHR))

        self.parseq_pypi_version = self.check_pypi_version()  # pypi_ver, cur_ver  # noqa

        self.tabBar = qt.QTabBar(parent=self)
        self.tabBar.setIconSize(qt.QSize(32, 32))
        self.tabBar.setStyleSheet("QTabBar {font: bold 10pt;}")
        # "QTabBar::tab { height: 100px; width: 400px; }")
        self.tabNames = ['ParSeq', csi.pipelineName]
        self.iconPaths = [ICONPATHP, csi.appIconPath]
        for tabName, iconPath in zip(self.tabNames, self.iconPaths):
            icon = qt.QIcon(iconPath) if iconPath else qt.QIcon()
            self.tabBar.addTab(icon, tabName)
        self.tabBar.currentChanged.connect(self.changePage)
        self.makeWebView()

        # self.webView.page().mainFrame().setScrollBarPolicy(
        #     qt.Qt.Vertical, qt.Qt.ScrollBarAlwaysOff)
        # self.webView.page().mainFrame().setScrollBarPolicy(
        #     qt.Qt.Horizontal, qt.Qt.ScrollBarAlwaysOff)

        layout = qt.QVBoxLayout()
        layout.addWidget(self.tabBar)
        layout.setSpacing(0)
        layout.addWidget(self.webView)
        self.setLayout(layout)
        self.resize(0, 0)

    def makeWebView(self):
        self.webView = gww.QWebView()
        self.webView.page().setLinkDelegationPolicy(2)
        self.webView.setMinimumWidth(500+50)
        self.webView.setMinimumHeight(510+40)
        self.webView.history().clear()
        self.webView.page().history().clear()
        self.lastBrowserLink = ''
        self.webView.page().linkClicked.connect(
            self.linkClicked, type=qt.Qt.UniqueConnection)

        self.sphinxThread = qt.QThread(self)
        self.sphinxWorker = gww.SphinxWorker()
        self.sphinxWorker.moveToThread(self.sphinxThread)
        self.sphinxThread.started.connect(self.sphinxWorker.render)
        self.canLoadHTML = False
        self.sphinxWorker.html_ready.connect(self._on_sphinx_html_ready)
        rawTexts = [self.makeTextMain(), self.makeTextPipeline()]
        self.sphinxWorker.prepare(rawTexts, self.tabNames)
        self.sphinxThread.start()

    def _on_sphinx_html_ready(self):
        self.canLoadHTML = True
        currentIndex = 1
        self.tabBar.setCurrentIndex(currentIndex)
        self.changePage(currentIndex)

    def makeTextMain(self):
        Qt_version = qt.QT_VERSION_STR
        PyQt_version = qt.PYQT_VERSION_STR
        locos = pythonplatform.platform(terse=True)
        if 'Linux' in locos:
            locos = " ".join(pythonplatform.linux_distribution())
        if isOpenCL:
            vercl = cl.VERSION
            if isinstance(vercl, (list, tuple)):
                vercl = '.'.join(map(str, vercl))
        else:
            vercl = isOpenStatus
        strOpenCL = r'pyopencl {0}'.format(vercl)
        strSilx = r'silx {0}'.format(versilx)
        strParSeq = 'ParSeq {0} in {1}'.format(
            parseqversion, PARSEQPATH).replace('\\', '/')
        if type(self.parseq_pypi_version) is tuple:
            pypiver, curver = self.parseq_pypi_version
            if curver < pypiver:
                strParSeq += \
                    ', **version {0} is available from** PyPI_'.format(pypiver)
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
    {9}""".format(
            parseq.__synopsis__, parseq.__doc__,
            locos, pythonplatform.python_version(), Qt_version, qt.BINDING,
            PyQt_version, strOpenCL, strSilx, strParSeq)
#        txt = txt.replace('imagezoom::', 'image::')
        return txt

    def makeTextPipeline(self):
        iconPath = csi.appIconPath
        path = csi.appPath
        if os.name == 'nt':
            iconPath = iconPath.replace('\\', '/')
            path = path.replace('\\', '/')
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
        if not self.canLoadHTML:
            return
        docName = self.tabNames[itab].replace(' ', '_')
        html = 'file:///' + osp.join(gww.CONFDIR, docName+'.html')
        html = re.sub('\\\\', '/', html)
        self.webView.load(qt.QUrl(html))

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
