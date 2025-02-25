# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "22 Jan 2025"
# !!! SEE CODERULES.TXT !!!

import re
import sys
import os
import os.path as osp
import shutil
import glob
import multiprocessing

from silx.gui import qt

from xml.sax.saxutils import escape
from docutils.utils import SystemMessage
from sphinx.application import Sphinx
from sphinx.errors import SphinxError
try:
    import sphinxcontrib.jquery  # to check if it exists, analysis:ignore
except ImportError as e:
    print('do "pip install sphinxcontrib-jquery"')
    raise e
import codecs

from ..core import singletons as csi
from ..core.logger import logger
from . import gcommons as gco

nC = multiprocessing.cpu_count()

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

CONFDIR = osp.join(osp.dirname(osp.dirname(osp.abspath(__file__))), 'help')
GUIDIR = osp.dirname(osp.abspath(__file__))
PARSEQDIR = osp.dirname(osp.abspath(GUIDIR))
COREDIR = osp.join(PARSEQDIR, 'core')
GLOBDIR = osp.dirname(osp.abspath(PARSEQDIR))

# Ubuntu's web browsers may fail to open htmls in hidden dirs. If so, remove
# the leading dot here (or completely rename).
DOCHEAD = '.parseq'
DOCDIR = osp.expanduser(osp.join('~', DOCHEAD, 'doc'))
MAINHELPDIR = osp.expanduser(osp.join('~', DOCHEAD, 'help-ParSeq'))
MAINHELPFILE = osp.join(MAINHELPDIR, '_build', 'index.html')
PIPEHELPDIR = osp.expanduser(
    osp.join('~', DOCHEAD, 'help-{0}'.format(csi.pipelineName)))
PIPEOUTDIR = osp.join(PIPEHELPDIR, '_build')
PIPEHELPFILE = osp.join(PIPEOUTDIR, 'index.html')


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


def makeGraphPipeline(addLinks=False):
    ranks = {}
    for i in range(len(csi.nodes)):
        nodes, icons, refs = [], [], []
        transforms = []
        fits = {}
        fitIcon = 'icon-fit-32.png'
        for name, node in csi.nodes.items():
            if len(node.upstreamNodes) == i:
                nodes.append(name)
                hasUserIcon = False
                if hasattr(node, 'icon'):
                    iconPath = osp.join(csi.appPath, node.icon)
                    hasUserIcon = osp.exists(iconPath)
                if hasUserIcon:
                    iName = osp.split(node.icon)[1]
                else:
                    if node.plotDimension is None:
                        iName = None
                    elif node.plotDimension < 4:
                        iName = 'icon-item-{0}dim-32.png'.format(
                            node.plotDimension)
                    else:
                        iName = 'icon-item-ndim-32.png'
                icons.append(iName)
                ref = node.ref if hasattr(node, 'ref') else None
                refs.append(ref)

                for tr in node.transformsOut:
                    trRef = tr.ref if hasattr(tr, "ref") else None
                    trEntry = [tr.name, tr.fromNode.name, tr.toNode.name,
                               tr.nThreads, tr.nProcesses, trRef]
                    transforms.append(trEntry)
                for fit in csi.fits.values():
                    if fit.node is node:
                        fitRef = fit.ref if hasattr(fit, "ref") else None
                        fitEntry = [fit.name, fit.nThreads, fit.nProcesses,
                                    fitRef]
                        if name in fits:
                            fits[name].append(fitEntry)
                        else:
                            fits[name] = [fitEntry]

        ranks[i] = dict(nodes=nodes, icons=icons, refs=refs,
                        transforms=transforms, fits=fits)

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
        refs = rankDict['refs']
        if not names:
            continue
        flowChart += """\n      <div class="pipeline-rank">"""
        for name, iconName, ref in zip(names, icons, refs):
            name_ = "_".join(name.split())
            iconTxt = '' if iconName is None else \
                '<img src="_images/{0}" height="24" />'.format(iconName)
            if addLinks and ref:
                fref = osp.join(PIPEOUTDIR, ref)
                txt = '<a href={0}>{1}</a>'.format(fref, name)
            else:
                txt = name
            flowChart += u"""\n
                <div id="pn_{0}" class="pipeline-node">{1}&nbsp{2}""".format(
                name_, iconTxt, txt)
            if name in fits:
                ficonTxt = '<img src="_images/{0}" height="20" />'\
                    .format(fitIcon)
                for fit in fits[name]:
                    if addLinks and fit[3]:
                        fref = osp.join(PIPEOUTDIR, fit[3])
                        fitName = '<a href={0}>{1}</a>'.format(fref, fit[0])
                    else:
                        fitName = fit[0]
                    thr_pr = makeThreadProcessStr(fit[1], fit[2])
                    flowChart += u"""&nbsp <span id="fn_{0}"
                        class="pipeline-fit">{1}&nbsp{2} {3}&nbsp</span>"""\
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
            if addLinks and transform[5]:
                fref = osp.join(PIPEOUTDIR, transform[5])
                txt = '<a href={0}>{1}</a>'.format(fref, transform[0])
            else:
                txt = transform[0]
            thr_pr = makeThreadProcessStr(transform[3], transform[4])
            flowChart += u"""\n        <div class="pipeline-tr" {1}>
            {0}{2}</div>""".format(txt, colorStr, thr_pr)
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


def make_context(task, name='', argspec='', note=''):
    if task == 'main':
        BASEDIR = MAINHELPDIR
    elif task == 'pipe':
        BASEDIR = PIPEHELPDIR
    elif task == 'docs':
        BASEDIR = DOCDIR
    else:
        raise ValueError('unspecified task')

    CSS_PATH = osp.join(BASEDIR, '_static')
    CSS_PATH = re.sub('\\\\', '/', CSS_PATH)
    JS_PATH = CSS_PATH
    shouldScaleMath = qt.BINDING == "PyQt4" and sys.platform == 'win32'

    context = {'name': name,
               'argspec': argspec,
               'note': note,
               'css_path': CSS_PATH,
               'js_path': JS_PATH,
               'shouldScaleMath': 'true' if shouldScaleMath else ''}
    return context


class SphinxProcess(multiprocessing.Process):
    def __init__(self, srcdir, confdir, outdir, doctreedir, confoverrides,
                 status, warning):
        self.srcdir, self.confdir, self.outdir, self.doctreedir, \
            self.confoverrides, self.status, self.warning = \
            (srcdir, confdir, outdir, doctreedir, confoverrides, status,
             warning)
        multiprocessing.Process.__init__(self)

    def run(self):
        sys.path.append(csi.parseqPath)  # to find parseq in multiprocessing
        try:
            self.sphinx_app = Sphinx(
                self.srcdir, self.confdir, self.outdir, self.doctreedir,
                'html', self.confoverrides, status=self.status,
                warning=self.warning,
                freshenv=True, warningiserror=False, tags=None)
            self.sphinx_app.build()
        except (SystemMessage, SphinxError) as e:
            print(e)
            raise e


# @logger(minLevel=20)
def sphinxify(task, context, wantMessages=False):
    # Add a class to several characters on the argspec. This way we can
    # highlight them using css, in a similar way to what IPython does.
    # NOTE: Before doing this, we escape common html chars so that they
    # don't interfere with the rest of html present in the page
    argspec = escape(context['argspec'])
    for char in ['=', ',', '(', ')', '*', '**']:
        argspec = argspec.replace(
            char, '<span class="argspec-highlight">' + char + '</span>')
    context['argspec'] = argspec
    confoverrides = {'html_context': context}

    if task == 'main':
        srcdir = MAINHELPDIR
        confdir = MAINHELPDIR
        outdir = osp.join(MAINHELPDIR, '_build')
        doctreedir = osp.join(MAINHELPDIR, 'doctrees')
        confoverrides['extensions'] = [
            'sphinx.ext.autodoc', 'sphinx.ext.mathjax', 'sphinxcontrib.jquery',
            'animation']
    elif task == 'pipe':
        srcdir = PIPEHELPDIR
        confdir = PIPEHELPDIR
        outdir = PIPEOUTDIR
        doctreedir = osp.join(PIPEHELPDIR, 'doctrees')
        confoverrides['extensions'] = [
            'sphinx.ext.autodoc', 'sphinx.ext.mathjax', 'sphinxcontrib.jquery',
            'animation']
    elif task == 'docs':
        srcdir = osp.join(DOCDIR, '_sources')
        confdir = DOCDIR
        outdir = DOCDIR
        doctreedir = osp.join(DOCDIR, 'doctrees')
        confoverrides['extensions'] = [
            'sphinx.ext.mathjax', 'sphinxcontrib.jquery']
        os.chdir(DOCDIR)
    else:
        raise ValueError('unspecified task')

    status, warning = [sys.stderr]*2 if wantMessages else [None]*2
    # sphinx_app = Sphinx(srcdir, confdir, outdir, doctreedir, 'html',
    #                     confoverrides, status=status, warning=warning,
    #                     freshenv=True, warningiserror=False, tags=None)
    # try:
    #     sphinx_app.build()
    # except (SystemMessage, SphinxError) as e:
    #     print(e)
    #     raise e
    worker = SphinxProcess(srcdir, confdir, outdir, doctreedir, confoverrides,
                           status, warning)
    worker.start()
    worker.join(60.)


if 'pyqt4' in qt.BINDING.lower():
    import PyQt4.QtWebKit as myQtWeb
elif 'pyqt5' in qt.BINDING.lower():
    try:
        import PyQt5.QtWebEngineWidgets as myQtWeb
    except ImportError:
        try:
            import PyQt5.QtWebKitWidgets as myQtWeb
        except ImportError as e:
            print('do "conda install -c conda-forge pyqtwebengine"'
                  ' or "pip install pyqtwebengine"')
            raise e
elif 'pyside2' in qt.BINDING.lower():
    import PySide2.QtWebEngineWidgets as myQtWeb
elif 'pyside6' in qt.BINDING.lower():
    import PySide6.QtWebEngineWidgets as myQtWeb
else:
    raise ImportError("Cannot import any Python Qt package!")

try:
    class WebPage(myQtWeb.QWebPage):
        """
        Web page subclass to manage hyperlinks like in WebEngine
        """
        showHelp = qt.Signal()

    class QWebView(myQtWeb.QWebView):
        """Web view"""

        def __init__(self, parent=None):
            myQtWeb.QWebView.__init__(self, parent)
            web_page = WebPage(self)
            self.setPage(web_page)

except AttributeError:
    # QWebKit deprecated in Qt 5.7
    # The idea and partly the code of the compatibility fix is borrowed from
    # spyderlib.widgets.browser
    class WebPage(myQtWeb.QWebEnginePage):
        """
        Web page subclass to manage hyperlinks for WebEngine

        Note: This can't be used for WebKit because the
        acceptNavigationRequest method has a different
        functionality for it.
        """
        linkClicked = qt.Signal(qt.QUrl)
        showHelp = qt.Signal()
        linkDelegationPolicy = 0

        def setLinkDelegationPolicy(self, policy):
            self.linkDelegationPolicy = policy

        def acceptNavigationRequest(self, url, navigation_type, isMainFrame):
            """
            Overloaded method to handle links ourselves
            """
            strURL = str(url.toString())
            if strURL.endswith('png') or strURL.endswith('ico'):
                return False
            elif strURL.startswith('file'):
                if strURL.endswith('tutorial.html') or\
                        strURL.endswith('tutorial'):
                    self.linkClicked.emit(url)
                    return False
                else:
                    return True
            else:
                self.linkClicked.emit(url)
                return False

    class QWebView(myQtWeb.QWebEngineView):
        """Web view"""

        def __init__(self, parent=None):
            myQtWeb.QWebEngineView.__init__(self, parent)
            if qt.BINDING.lower().startswith(('pyqt5', 'pyside2')):
                settings = myQtWeb.QWebEngineSettings.globalSettings()
                try:
                    settings.setAttribute(
                        myQtWeb.QWebEngineSettings.ShowScrollBars, False)
                except AttributeError:  # added in Qt 5.10
                    pass

            web_page = WebPage(self)
            self.setPage(web_page)


class SphinxWorker(qt.QObject):
    html_ready = qt.pyqtSignal()

    def copyNodeIcons(self, dest):
        for ico in ['1', '2', '3', 'n']:
            fname = 'icon-item-{0}dim-32.png'.format(ico)
            shutil.copy2(osp.join(GUIDIR, '_images', fname),
                         osp.join(dest, '_images'))
        fname = 'icon-fit-32.png'
        shutil.copy2(osp.join(GUIDIR, '_images', fname),
                     osp.join(dest, '_images'))

        for node in csi.nodes.values():
            if hasattr(node, 'icon'):
                iconPath = osp.join(csi.appPath, node.icon)
                hasUserIcon = osp.exists(iconPath)
                if hasUserIcon:
                    shutil.copy2(iconPath, osp.join(dest, '_images'))

    def prepareMain(self, argspec="", note=""):
        try:
            shutil.rmtree(MAINHELPDIR)
        except FileNotFoundError:
            pass
        shutil.copytree(CONFDIR, MAINHELPDIR, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('conf_doc*.py',))
        shutil.copy2(osp.join(PARSEQDIR, 'version.py'), osp.dirname(DOCDIR))
        # insert abs path to parseq into conf.py:
        with open(osp.join(CONFDIR, 'conf.py'), 'r') as f:
            txt = f.read()
        txt = txt.replace(
            "sys.path.insert(0, '../..')",
            "sys.path.insert(0, r'" + GLOBDIR + "')")
        with open(osp.join(MAINHELPDIR, 'conf.py'), 'w') as f:
            f.write(txt)

        outdir = osp.join(MAINHELPDIR, '_build')
        if not osp.exists(outdir):
            os.makedirs(outdir)
        self.argspec = argspec
        self.note = note

    def preparePipe(self, argspec="", note=""):
        try:
            shutil.rmtree(PIPEHELPDIR)
        except FileNotFoundError:
            pass

        dirsToCopy = '_images', '_static', '_templates', '_themes', 'exts'
        for dc in dirsToCopy:
            dst = osp.join(PIPEHELPDIR, dc)
            dpath = osp.join(csi.appPath, 'doc', dc)
            if not osp.exists(dpath):
                dpath = osp.join(CONFDIR, dc)
            shutil.copytree(dpath, dst, dirs_exist_ok=True)

        dpath = osp.join(csi.appPath, 'doc', 'conf.py')
        if osp.exists(dpath):
            shutil.copy2(dpath, osp.join(PIPEHELPDIR, 'conf.py'))
        else:  # from main ParSeq
            dpath = osp.join(CONFDIR, 'conf.py')
            confPy = osp.join(PIPEHELPDIR, 'conf.py')
            shutil.copy2(dpath, confPy)

            # edit it:
            with open(confPy, 'r') as f:
                lines = [line.rstrip('\n') for line in f.readlines()]
            for iline, line in enumerate(lines):
                if line.startswith("sys.path.insert(0, '../..')"):
                    lines[iline] = "sys.path.insert(0, r'{0}')".format(GLOBDIR)
                elif line.startswith("html_favicon"):
                    iconPath = osp.split(csi.appIconPath)
                    lines[iline] = 'html_favicon = "_images/{0}"'.format(
                        iconPath[-1])
                elif line.startswith("html_logo"):
                    if hasattr(csi, 'appBigIconPath'):
                        iconPath = osp.split(csi.appBigIconPath)
                        lines[iline] = 'html_logo = "_images/{0}"'.format(
                            iconPath[-1])
                elif line.startswith("version"):
                    lines[iline] = 'version = "{0}"'.format(csi.appVersion)
                elif line.startswith("release"):
                    lines[iline] = 'release = "{0}"'.format(csi.appVersion)
                elif "html_title" in line[:25]:
                    lines[iline] = 'html_title = "ParSeq-{0} documentation"'\
                        .format(csi.pipelineName)
            with open(confPy, 'w') as f:
                f.write('\n'.join(lines))

        for fname in glob.glob(osp.join(csi.appPath, 'doc', '*.rst')):
            shutil.copy2(fname, PIPEHELPDIR)
        if not osp.exists(osp.join(PIPEHELPDIR, 'index.rst')):
            shutil.copy2(osp.join(CONFDIR, 'indexrst.mock'),
                         osp.join(PIPEHELPDIR, 'index.rst'))
        flowChart = makeGraphPipeline(True)
        txtFlowChart = u""".. raw:: html\n\n   {0}""".format(flowChart)
        rstFlowChart = osp.join(PIPEHELPDIR, 'graph.rst')
        with open(rstFlowChart, 'w', encoding='utf-8') as f:
            f.write(txtFlowChart)

        outdir = PIPEOUTDIR
        if not osp.exists(outdir):
            os.makedirs(outdir)
        # images for the pipeline graph:
        imdir = osp.join(outdir, '_images')
        if not osp.exists(imdir):
            os.makedirs(imdir)
        self.copyNodeIcons(outdir)
        self.argspec = argspec
        self.note = note

    def prepareDocs(self, docs, docNames, argspec="", note=""):
        # try:
        #     shutil.rmtree(DOCDIR)
        # except FileNotFoundError:
        #     pass

        # copy images
        impath = osp.join(csi.appPath, 'doc', '_images')
        if osp.exists(impath):
            dst = osp.join(DOCDIR, '_images')
            shutil.copytree(impath, dst, dirs_exist_ok=True)

        shutil.copytree(osp.join(CONFDIR, '_images'),
                        osp.join(DOCDIR, '_images'), dirs_exist_ok=True)
        self.copyNodeIcons(DOCDIR)
        shutil.copytree(osp.join(CONFDIR, '_themes'),
                        osp.join(DOCDIR, '_themes'), dirs_exist_ok=True)
        shutil.copy2(osp.join(CONFDIR, 'conf_doc.py'),
                     osp.join(DOCDIR, 'conf.py'))

        srcdir = osp.join(DOCDIR, '_sources')
        if not osp.exists(srcdir):
            os.makedirs(srcdir)

        for doc, docName in zip(docs, docNames):
            docName = docName.replace(' ', '_')
            fname = osp.join(srcdir, '{0}.rst'.format(docName))
            with codecs.open(fname, 'w', encoding='utf-8') as f:
                f.write(".. title:: {0}\n".format(docName))
                f.write(doc)

        fname = osp.join(srcdir, 'content.rst')
        with codecs.open(fname, 'w', encoding='utf-8') as f:
            f.write(".. toctree::\n   :maxdepth: 3\n\n")
            for docName in docNames:
                docName = docName.replace(' ', '_')
                f.write("   {0}.rst\n".format(docName))

        self.argspec = argspec
        self.note = note

    def render(self, task='docs'):
        cnx = make_context(task, name='', argspec=self.argspec, note=self.note)
        sphinxify(task, cnx)
        self.thread().terminate()
        self.html_ready.emit()
