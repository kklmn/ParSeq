# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "21 Nov 2023"
# !!! SEE CODERULES.TXT !!!

import os
import os.path as osp
import numpy as np
import re
import sphinx
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


tabNames = ["about-ParSeq", "about-{0}".format(csi.pipelineName)]

path = csi.appPath
projFiles = []
for root, dirs, files in os.walk(path):
    for file in files:
        if file.endswith(".pspj"):
            pr = os.path.join(root, file)
            with open(pr, 'r') as fp:
                prd = fp.read()
                if "pipelineName = {}".format(csi.pipelineName) in prd:
                    projFiles.append(osp.relpath(pr, path).replace('\\', '/'))


def check_pypi_version():
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


def makeTextMain():
    # https://stackoverflow.com/a/69325836/2696065
    def isWin11():
        return True if sys.getwindowsversion().build > 22000 else False

    if qt.BINDING.lower().startswith('pyside2'):
        import PySide2.QtCore
        Qt_version = PySide2.QtCore.qVersion()
        PyQt_version = PySide2.__version__
    elif qt.BINDING.lower().startswith('pyside6'):
        import PySide6.QtCore
        Qt_version = PySide6.QtCore.qVersion()
        PyQt_version = PySide6.__version__
    else:
        Qt_version = qt.QT_VERSION_STR
        PyQt_version = qt.PYQT_VERSION_STR
    locos = pythonplatform.platform(terse=True)
    if 'Linux' in locos:
        try:
            locos = " ".join(pythonplatform.linux_distribution())
        except AttributeError:  # no platform.linux_distribution in py3.8
            try:
                import distro
                locos = " ".join(distro.linux_distribution())
            except ImportError:
                print("do 'pip install distro' for a better view of Linux"
                      " distro string")
    elif 'Windows' in locos:
        if isWin11():
            locos = 'Windows 11'

    if isOpenCL:
        vercl = cl.VERSION
        if isinstance(vercl, (list, tuple)):
            vercl = '.'.join(map(str, vercl))
    else:
        vercl = isOpenStatus
    strNumpy = r'numpy {0}'.format(np.__version__)
    strOpenCL = r'pyopencl {0}'.format(vercl)
    strSphinx = 'Sphinx {0}'.format(sphinx.__version__)
    strSilx = r'silx {0}'.format(versilx)
    strParSeq = '{0}'.format(PARSEQPATH).replace('\\', '/')
    parseq_pypi_version = check_pypi_version()  # pypi_ver, cur_ver  # noqa
    if isinstance(parseq_pypi_version, tuple):
        pypiver, curver = parseq_pypi_version
        pstr = "`PyPI <https://pypi.python.org/pypi/parseq>`_"
        if curver < pypiver:
            strParSeq += \
                ', **version {0} is available from** {1}'.format(
                    pypiver, pstr)
        else:
            strParSeq += ', this is the latest version in {0}'.format(pstr)

    txt = u"""

.. list-table::
   :widths: 25 75

   * - |ico|
     - |synopsis|

.. |ico| image:: _images/parseq.ico
   :scale: 100%

.. |synopsis| replace::
   :bigger:`{0}`

{1}

:Created by:
    Konstantin Klementiev (`MAX IV Laboratory <https://www.maxiv.lu.se/>`_)
:License:
    MIT License, Nov 2018
:Located at:
    {2}
:Version:
    {3}
:Your system:
    {4}, Python {5}\n
    Qt {6}, {7} {8}\n
    {9}\n
    {10}\n
    {11}\n
    {12}""".format(
            parseq.__synopsis__, parseq.__doc__, strParSeq, parseqversion,
            locos, pythonplatform.python_version(),
            Qt_version, qt.BINDING, PyQt_version,
            strNumpy, strOpenCL, strSphinx, strSilx)
    # txt = txt.replace('imagezoom::', 'image::')
    return txt


def makeTextPipeline():
    iconPath = csi.appIconPath
    path = csi.appPath
    if os.name == 'nt':
        iconPath = iconPath.replace('\\', '/')
    elif os.name.startswith('posix'):
        iconPath = '/' + iconPath

    if projFiles:
        testStr = """
Test it as::

"""
        for projFile in projFiles:
            testStr += """
    python {0} -p {1}""".format(sys.argv[0], projFile)
    else:
        testStr = ""

    flowChart = gww.makeGraphPipeline()
    txt = u"""
.. list-table::
   :widths: 25 75

   * - |ico|
     - |synopsis|

.. |ico| image:: {0}
   :scale: {1:.0%}

.. |synopsis| replace::
   :bigger:`{2}`

.. raw:: html

   {3}

{4}

{5}

:Created by:
    {6}
:License:
    {7}
:Located at:
    {8}
:Version:
    {9}
    """.format(iconPath, csi.appIconScale, csi.appSynopsis, flowChart,
               csi.appDescription, testStr, csi.appAuthor, csi.appLicense,
               path.replace('\\', '/'), csi.appVersion)
    return txt


class AboutDialog(qt.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setWindowIcon(qt.QIcon(ICONPATHR))

        self.tabBar = qt.QTabBar(parent=self)
        self.tabBar.setIconSize(qt.QSize(32, 32))
        self.tabBar.setStyleSheet(
            "QTabBar {font: bold 10pt;}"
            "QTabBar::tab:selected {background: white;}")
        # "QTabBar::tab { height: 100px; width: 400px; }")
        self.iconPaths = [ICONPATHP, csi.appIconPath]
        for tabName, iconPath in zip(tabNames, self.iconPaths):
            icon = qt.QIcon(iconPath) if iconPath else qt.QIcon()
            self.tabBar.addTab(icon, tabName[tabName.find("-")+1:])
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

        currentIndex = 1
        self.tabBar.setCurrentIndex(currentIndex)
        self.changePage(currentIndex)

    def makeWebView(self):
        self.webView = gww.QWebView(self)
        self.webView.page().setLinkDelegationPolicy(2)
        self.webView.setMinimumWidth(620)
        # self.webView.setMinimumHeight(620)
        self.webView.setMinimumHeight(
            480 + 30*len(csi.nodes) + 15*len(projFiles) +
            len(csi.appDescription)//4)
        self.webView.history().clear()
        self.webView.page().history().clear()
        self.lastBrowserLink = ''
        self.webView.page().linkClicked.connect(
            self.linkClicked, type=qt.Qt.UniqueConnection)

    def changePage(self, itab):
        docName = tabNames[itab].replace(' ', '_')
        html = 'file:///' + osp.join(gww.DOCOUTDIR, docName+'.html')
        html = re.sub('\\\\', '/', html)
        self.webView.load(qt.QUrl(html))

    def linkClicked(self, url):
        strURL = str(url.toString())
        if strURL.startswith('http') or strURL.startswith('ftp'):
            if self.lastBrowserLink == strURL:
                return
            webbrowser.open(strURL)
            self.lastBrowserLink = strURL
