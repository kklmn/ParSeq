# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "3 Mar 2022"
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

CONFDIR = osp.join(osp.dirname(osp.dirname(osp.abspath(__file__))), 'help')
GUIDIR = osp.dirname(osp.abspath(__file__))
DOCDIR = osp.expanduser(osp.join('~', '.parseq', 'doc'))

try:
    shutil.rmtree(DOCDIR)
except FileNotFoundError:
    pass
shutil.copytree(osp.join(CONFDIR, '_images'), osp.join(DOCDIR, '_images'))
for ico in ['1', '2', '3', 'n']:
    fname = 'icon-item-{0}dim-32.png'.format(ico)
    shutil.copy2(osp.join(GUIDIR, '_images', fname),
                 osp.join(DOCDIR, '_images', fname))
shutil.copytree(osp.join(CONFDIR, '_themes'), osp.join(DOCDIR, '_themes'))
shutil.copy2(osp.join(CONFDIR, 'conf.py'), osp.join(DOCDIR, 'conf.py'))

CSS_PATH = osp.join(DOCDIR, '_static')
CSS_PATH = re.sub('\\\\', '/', CSS_PATH)
JS_PATH = CSS_PATH
shouldScaleMath = qt.BINDING == "PyQt4" and sys.platform == 'win32'


def generate_context(name='', argspec='', note=''):
    context = {'name': name,
               'argspec': argspec,
               'note': note,
               'css_path': CSS_PATH,
               'js_path': JS_PATH,
               'shouldScaleMath': 'true' if shouldScaleMath else ''}
    return context


def sphinxify(context):
    """
    Largely modified Spyder's sphinxify.
    """
    if csi.DEBUG_LEVEL > 20:
        print('enter sphinxify')
    srcdir = osp.join(DOCDIR, '_sources')

    # Add a class to several characters on the argspec. This way we can
    # highlight them using css, in a similar way to what IPython does.
    # NOTE: Before doing this, we escape common html chars so that they
    # don't interfere with the rest of html present in the page
    argspec = escape(context['argspec'])
    for char in ['=', ',', '(', ')', '*', '**']:
        argspec = argspec.replace(
            char, '<span class="argspec-highlight">' + char + '</span>')
    context['argspec'] = argspec

    confoverrides = {'html_context': context,
                     'extensions': ['sphinx.ext.mathjax', ]}

    doctreedir = osp.join(DOCDIR, 'doctrees')
    sphinx_app = Sphinx(srcdir, DOCDIR, DOCDIR, doctreedir, 'html',
                        confoverrides, status=None, warning=None,
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
                settings.setAttribute(
                    myQtWeb.QWebEngineSettings.ShowScrollBars, False)

            web_page = WebPage(self)
            self.setPage(web_page)


class SphinxWorker(qt.QObject):
    html_ready = qt.pyqtSignal()

    def prepare(self, docs, docNames, docArgspec="", docNote="", img_path=""):
        srcdir = osp.join(DOCDIR, '_sources')
        if not os.path.exists(srcdir):
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

        self.docArgspec = docArgspec
        self.docNote = docNote
        # self.img_path = img_path

    def render(self):
        cntx = generate_context(
            name='',
            argspec=self.docArgspec,
            note=self.docNote)
        sphinxify(cntx)
        self.thread().terminate()
        self.html_ready.emit()
