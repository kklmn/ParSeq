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
import multiprocessing
import webbrowser

from ..core import singletons as csi
from . import gcommons as gco
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

nC = multiprocessing.cpu_count()

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


def makeThreadProcessStr(nThreads, nProcesses):
    if isinstance(nThreads, str):
        nThreads = max(nC//2, 1) if nThreads.startswith('h') else nC
    if isinstance(nProcesses, str):
        nProcesses = max(nC//2, 1) if nProcesses.startswith('h') else nC

    res = ''
    if nProcesses > 1:
        res = ' ({0} processes)'.format(nProcesses)
    elif nThreads > 1:
        res = ' ({0} threads)'.format(nThreads)
    return res


def makeGraphPipeline():
    ranks = {}
    for i in range(len(csi.nodes)):
        nodes = []
        transforms = []
        icons = []
        fits = {}
        fitIcon = 'icon-fit-32'
        for name, node in csi.nodes.items():
            if len(node.upstreamNodes) == i:
                nodes.append(name)
                if node.plotDimension is None:
                    iName = None
                elif node.plotDimension < 4:
                    iName = 'icon-item-{0}dim-32'.format(
                        node.plotDimension)
                else:
                    iName = 'icon-item-ndim-32'
                icons.append(iName)
                for tr in node.transformsOut:
                    trEntry = [tr.name, tr.fromNode.name, tr.toNode.name,
                               tr.nThreads, tr.nProcesses]
                    transforms.append(trEntry)
                for fit in csi.fits.values():
                    if fit.node is node:
                        fitEntry = [fit.name, fit.nThreads, fit.nProcesses]
                        if name in fits:
                            fits[name].append(fitEntry)
                        else:
                            fits[name] = [fitEntry]

        ranks[i] = dict(nodes=nodes, icons=icons, transforms=transforms,
                        fits=fits)

    # ranks = {  # a fake test pipeline
    #     0: {'nodes': ['aaaaa', 'bbbbbbbbb'],
    #         'transforms': [['tr ac jhvcqwvedvsd', 'aaaaa', 'cccc'],
    #                        ['tr bc jhvpyvv', 'bbbbbbbbb', 'cccc'],
    #                        ['tr bb j', 'bbbbbbbbb', 'bbbbbbbbb']],
    #         'icons': ['icon-item-ndim', 'icon-item-ndim']},
    #     1: {'nodes': ['cccc'],
    #         'transforms': [['tr cd lkjblbh', 'cccc', 'dd']],
    #         'icons': ['icon-item-3dim']},
    #     2: {'nodes': ['dd'],
    #         'transforms': [['tr de sfsfJKBLV', 'dd', 'eeeee'],
    #                        ['tr df kkklklnlo', 'dd', 'fffffffff']],
    #         'icons': ['icon-item-2dim']},
    #     3: {'nodes': ['eeeee', 'fffffffff'],
    #         'transforms': [['tr eg hjblvh', 'eeeee', 'ggggg'],
    #                        ['tr fg íj[aaa', 'fffffffff', 'ggggg']],
    #         'icons': ['icon-item-1dim', 'icon-item-1dim']},
    #     4: {'nodes': ['ggggg'], 'transforms': [],
    #         'icons': ['icon-item-1dim']}}

    flowChart = """\n
    <div class="pipeline">
    <svg><defs>"""
    for i in range(len(gco.colorCycle1)):
        flowChart += """\n
    <filter id="flt{0}" filterUnits="userSpaceOnUse" id="shadow" x="-2" y="1">
      <feGaussianBlur in="SourceAlpha" stdDeviation="1.5" result="blur">
      </feGaussianBlur>
      <feOffset in="blur" dx="1.5" dy="0" result="shadow"></feOffset>
      <feFlood flood-color="{1}99" result="color" />
      <feComposite in="color" in2="shadow" operator="in" />
      <feComposite in="SourceGraphic"/>
    </filter>
    <marker id="arrow{0}" markerWidth="12" markerHeight="8"
    refX="7" refY="4" orient="auto" markerUnits="userSpaceOnUse">
    <polyline points="1 1, 9 4, 1 7" class="shadow" stroke={1} />
    </marker>""".format(i, gco.colorCycle1[i])
    flowChart += """\n
    </defs></svg>"""

    iline = 0
    for irank, (rank, rankDict) in enumerate(ranks.items()):
        names = rankDict['nodes']
        icons = rankDict['icons']
        fits = rankDict['fits']
        if not names:
            continue
        flowChart += """\n      <div class="pipeline-rank">"""
        for name, iName in zip(names, icons):
            name_ = "_".join(name.split())
            iconTxt = '' if iName is None else \
                '<img src="_images/{0}.png" height="20" />'.format(iName)
            flowChart += u"""\n
                <div id="pn_{0}" class="pipeline-node">{1} {2}""".format(
                name_, iconTxt, name)
            if name in fits:
                ficonTxt = '<img src="_images/{0}.png" height="20" />'\
                    .format(fitIcon)
                for fit in fits[name]:
                    fitName = fit[0]
                    thr_pr = makeThreadProcessStr(fit[1], fit[2])
                    flowChart += u"""&nbsp <span id="fn_{0}"
                        class="pipeline-fit">{1} {2} {3}&nbsp</span>"""\
                            .format(name_, ficonTxt, fitName, thr_pr)
            flowChart += "</div>"
        flowChart += """\n      </div>"""  # class="pipeline-rank"

        transforms = rankDict['transforms']
        if not transforms:
            continue
        flowChart += """\n      <div class="pipeline-transforms">"""
        if len(transforms) % 2 == 1:
            flowChart += u"""\n        <div class="pipeline-tr" ></div>"""
        for transform in transforms:
            iline_ = iline % len(gco.colorCycle1)
            color = gco.colorCycle1[iline_]
            colorStr = \
                'style="color: {0}; text-shadow: 1px 1.5px 3px {0}99;"'\
                .format(color)
            thr_pr = makeThreadProcessStr(transform[3], transform[4])
            flowChart += u"""\n        <div class="pipeline-tr" {1}>
            {0}{2}</div>""".format(transform[0], colorStr, thr_pr)
            name1_ = "_".join(transform[1].split())
            name2_ = "_".join(transform[2].split())
            colorStr = """style="stroke: {0}; """\
                """marker-end: url(#arrow{1}); filter: url(#flt{1})" """\
                .format(color, iline % len(gco.colorCycle1))
            if name1_ == name2_:
                flowChart += u"""\n
        <svg><path id="arc_{0}" node=pn_{1} class="shadow" {2} />
        </svg>""".format(iline, name1_, colorStr)
            else:
                flowChart += u"""\n
        <svg><line id="line_{0}" node1=pn_{1} node2=pn_{2} class="shadow"
        transform="translate(0, 0)"
        {3} /></svg>""".format(iline, name1_, name2_, colorStr)
            iline += 1
        flowChart += """\n      </div>"""  # class="pipeline-rank"
    flowChart += u"""\n
    </div>"""  # </div class="pipeline">
    return flowChart


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

    flowChart = makeGraphPipeline()
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
        self.webView.setMinimumWidth(560)
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
        html = 'file:///' + osp.join(gww.DOCDIR, docName+'.html')
        html = re.sub('\\\\', '/', html)
        self.webView.load(qt.QUrl(html))

    def linkClicked(self, url):
        strURL = str(url.toString())
        if strURL.startswith('http') or strURL.startswith('ftp'):
            if self.lastBrowserLink == strURL:
                return
            webbrowser.open(strURL)
            self.lastBrowserLink = strURL
