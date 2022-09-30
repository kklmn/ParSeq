# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "28 Aug 2022"
# !!! SEE CODERULES.TXT !!!

import re
import sys
import os
import os.path as osp
import shutil
from silx.gui import qt

from xml.sax.saxutils import escape
from docutils.utils import SystemMessage
from sphinx.application import Sphinx
from sphinx.errors import SphinxError
import codecs

from ..core import singletons as csi

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

CONFDIR = osp.join(osp.dirname(osp.dirname(osp.abspath(__file__))), 'help')
GUIDIR = osp.dirname(osp.abspath(__file__))
PARSEQDIR = osp.dirname(osp.abspath(GUIDIR))
COREDIR = osp.join(PARSEQDIR, 'core')
GLOBDIR = osp.dirname(osp.abspath(PARSEQDIR))

DOCDIR = osp.expanduser(osp.join('~', '.parseq', 'doc'))
HELPDIR = osp.expanduser(osp.join('~', '.parseq', 'help'))
HELPFILE = osp.join(HELPDIR, '_build', 'index.html')


def make_context(task, name='', argspec='', note=''):
    if task == 'help':
        BASEDIR = HELPDIR
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


def sphinxify(task, context, wantMessages=False):
    if csi.DEBUG_LEVEL > 20:
        print('enter sphinxify')

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

    if task == 'help':
        srcdir = HELPDIR
        confdir = HELPDIR
        outdir = osp.join(HELPDIR, '_build')
        doctreedir = osp.join(HELPDIR, 'doctrees')
        confoverrides['extensions'] = [
            'sphinx.ext.autodoc', 'sphinx.ext.mathjax', 'animation']
    elif task == 'docs':
        srcdir = osp.join(DOCDIR, '_sources')
        confdir = DOCDIR
        outdir = DOCDIR
        doctreedir = osp.join(DOCDIR, 'doctrees')
        confoverrides['extensions'] = ['sphinx.ext.mathjax']
    else:
        raise ValueError('unspecified task')

    status, warning = [sys.stderr]*2 if wantMessages else [None]*2
    # os.chdir(srcdir)
    sphinx_app = Sphinx(srcdir, confdir, outdir, doctreedir, 'html',
                        confoverrides, status=status, warning=warning,
                        freshenv=True, warningiserror=False, tags=None)
    try:
        sphinx_app.build()
    except (SystemMessage, SphinxError) as e:
        print(e)
        raise(e)
#        output = ("It was not possible to generate rich text help for this "
#                  "object.</br>Please see it in plain text.")
    if csi.DEBUG_LEVEL > 20:
        print('exit sphinxify')


if 'pyqt4' in qt.BINDING.lower():
    import PyQt4.QtWebKit as myQtWeb
elif 'pyqt5' in qt.BINDING.lower():
    try:
        import PyQt5.QtWebEngineWidgets as myQtWeb
    except ImportError:
        import PyQt5.QtWebKitWidgets as myQtWeb
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

    def prepareHelp(self, argspec="", note=""):
        try:
            shutil.rmtree(HELPDIR)
        except FileNotFoundError:
            pass
        shutil.copytree(CONFDIR, HELPDIR)
        # insert abs path to parseq into conf.py:
        with open(osp.join(CONFDIR, 'conf.py'), 'r') as f:
            data = f.read()
        data = data.replace(
            "sys.path.insert(0, '../..')",
            "sys.path.insert(0, r'" + GLOBDIR + "')")
        with open(osp.join(HELPDIR, 'conf.py'), 'w') as f:
            f.write(data)

        outdir = osp.join(HELPDIR, '_build')
        if not osp.exists(outdir):
            os.makedirs(outdir)
        self.argspec = argspec
        self.note = note

    def prepareDocs(self, docs, docNames, argspec="", note=""):
        try:
            shutil.rmtree(DOCDIR)
        except FileNotFoundError:
            pass

        # copy images
        impath = osp.join(csi.appPath, 'doc', '_images')
        if osp.exists(impath):
            dst = osp.join(DOCDIR, '_images')
            shutil.copytree(impath, dst, dirs_exist_ok=True)

        shutil.copytree(osp.join(CONFDIR, '_images'),
                        osp.join(DOCDIR, '_images'), dirs_exist_ok=True)
        for ico in ['1', '2', '3', 'n']:
            fname = 'icon-item-{0}dim-32.png'.format(ico)
            shutil.copy2(osp.join(GUIDIR, '_images', fname),
                         osp.join(DOCDIR, '_images', fname))
        shutil.copytree(osp.join(CONFDIR, '_themes'),
                        osp.join(DOCDIR, '_themes'))
        shutil.copy2(osp.join(CONFDIR, 'conf_doc.py'),
                     osp.join(DOCDIR, 'conf.py'))

        srcdir = osp.join(DOCDIR, '_sources')
        if not osp.exists(srcdir):
            os.makedirs(srcdir)

        for doc, docName in zip(docs, docNames):
            docName = docName.replace(' ', '_')
            fname = osp.join(srcdir, docName) + '.rst'
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
