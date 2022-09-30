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

PARSEQPATH = osp.dirname(osp.dirname(osp.abspath(__file__)))
ICONPATHP = osp.join(osp.dirname(__file__), '_images', 'parseq.ico')
ICONPATHR = osp.join(osp.dirname(__file__), '_images', 'icon-info.png')


class AboutDialog(qt.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
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
        self.webView = gww.QWebView(self)
        self.webView.page().setLinkDelegationPolicy(2)
        self.webView.setMinimumWidth(500+50)
        self.webView.setMinimumHeight(510+40+30*len(csi.nodes))
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
        self.sphinxWorker.prepareDocs(rawTexts, self.tabNames)
        self.sphinxThread.start()

    def _on_sphinx_html_ready(self):
        self.canLoadHTML = True
        currentIndex = 1
        self.tabBar.setCurrentIndex(currentIndex)
        self.changePage(currentIndex)

    def makeTextMain(self):
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
        if isOpenCL:
            vercl = cl.VERSION
            if isinstance(vercl, (list, tuple)):
                vercl = '.'.join(map(str, vercl))
        else:
            vercl = isOpenStatus
        strOpenCL = r'pyopencl {0}'.format(vercl)
        strSilx = r'silx {0}'.format(versilx)
        strParSeq = '{0}'.format(PARSEQPATH).replace('\\', '/')
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

.. |ico| image:: _images/parseq.ico
   :scale: 100 %

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
    {10}""".format(
            parseq.__synopsis__, parseq.__doc__,
            strParSeq, parseqversion,
            locos, pythonplatform.python_version(), Qt_version, qt.BINDING,
            PyQt_version, strOpenCL, strSilx, strParSeq)
#        txt = txt.replace('imagezoom::', 'image::')
        return txt

    def makeGraphPipeline(self):
        ranks = {}
        for i in range(len(csi.nodes)):
            nodes = []
            transforms = []
            icons = []
            for name, node in csi.nodes.items():
                if len(node.upstreamNodes) == i:
                    nodes.append(name)
                    if node.plotDimension is None:
                        iName = None
                    elif node.plotDimension < 4:
                        iName = 'icon-item-{0}dim-32'.format(node.plotDimension)
                    else:
                        iName = 'icon-item-ndim-32'
                    icons.append(iName)
                    for tr in node.transformsOut:
                        transforms.append(
                            [tr.name, tr.fromNode.name, tr.toNode.name])
            ranks[i] = dict(nodes=nodes, icons=icons, transforms=transforms)

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
      <feGaussianBlur in="SourceAlpha" stdDeviation="1.5" result="blur"></feGaussianBlur>
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
            if not names:
                continue
            flowChart += """\n      <div class="pipeline-rank">"""
            for name, iName in zip(names, icons):
                name_ = "_".join(name.split())
                iconTxt = '' if iName is None else \
                    '<img src="_images/{0}.png" height="20" />'.format(iName)
                flowChart += u"""\n
        <div id="pn_{0}" class="pipeline-node">{1} {2}</div>""".format(
                    name_, iconTxt, name)
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
                colorStr = 'style="color: {0}; text-shadow: 1px 1.5px 3px {0}99;"'\
                    .format(color)
                flowChart += u"""\n        <div class="pipeline-tr" {1}>
                {0}</div>""".format(transform[0], colorStr)
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
            {3} /></svg>""".format(iline, name1_, name2_, colorStr)
                iline += 1
            flowChart += """\n      </div>"""  # class="pipeline-rank"
        flowChart += u"""\n
    </div>"""  # </div class="pipeline">
        return flowChart

    def makeTextPipeline(self):
        iconPath = csi.appIconPath
        path = csi.appPath
        if os.name == 'nt':
            iconPath = iconPath.replace('\\', '/')
            path = path.replace('\\', '/')
        elif os.name.startswith('posix'):
            iconPath = '/' + iconPath

        flowChart = self.makeGraphPipeline()
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

.. inheritance-diagram:: sphinx.ext.inheritance_diagram.InheritanceDiagram

.. raw:: html

   {3}

{4}

:Created by:
    {5}
:License:
    {6}
:Located at:
    {7}
:Version:
    {8}
    """.format(iconPath, csi.appIconScale, csi.appSynopsis, flowChart,
               csi.appDescription, csi.appAuthor, csi.appLicense, path,
               csi.appVersion)
        return txt

    def changePage(self, itab):
        if not self.canLoadHTML:
            return
        docName = self.tabNames[itab].replace(' ', '_')
        html = 'file:///' + osp.join(gww.DOCDIR, docName+'.html')
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
        if strURL.startswith('http') or strURL.startswith('ftp'):
            if self.lastBrowserLink == strURL:
                return
            webbrowser.open(strURL)
            self.lastBrowserLink = strURL
