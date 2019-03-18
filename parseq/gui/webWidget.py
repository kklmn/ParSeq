# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import re
import sys
import os
import os.path as osp
from silx.gui import qt

from xml.sax.saxutils import escape
from docutils.utils import SystemMessage
from sphinx.application import Sphinx
import codecs

CONFDIR = osp.join(osp.dirname(osp.dirname(osp.abspath(__file__))), 'help')
CSS_PATH = osp.join(CONFDIR, '_static')
CSS_PATH = re.sub('\\\\', '/', CSS_PATH)
JS_PATH = CSS_PATH
parSeqPageName = 'parSeqPage'
parSeqPage = 'file:///' + osp.join(CONFDIR, parSeqPageName+'.html')
parSeqPage = re.sub('\\\\', '/', parSeqPage)

shouldScaleMath = qt.BINDING == "PyQt4" and sys.platform == 'win32'


def generate_context(name='', argspec='', note=''):
    context = {'name': name,
               'argspec': argspec,
               'note': note,
               'css_path': CSS_PATH,
               'js_path': JS_PATH,
               'shouldScaleMath': 'true' if shouldScaleMath else ''}
    return context


def sphinxify(docstring, context, buildername='html', img_path=''):
    """
    Largely modified Spyder's sphinxify.
    """
#    if not img_path:
#        img_path = os.path.join(CONFDIR, "_images")
    if img_path:
        if os.name == 'nt':
            img_path = img_path.replace('\\', '/')
        leading = '/' if os.name.startswith('posix') else ''
        docstring = docstring.replace('_images', leading+img_path)

    srcdir = osp.join(CONFDIR, '_sources')
    if not os.path.exists(srcdir):
        os.makedirs(srcdir)
#    srcdir = encoding.to_unicode_from_fs(srcdir)
    base_name = osp.join(srcdir, parSeqPageName)
    rst_name = base_name + '.rst'

    # This is needed so users can type \\ on latex eqnarray envs inside raw
    # docstrings
    docstring = docstring.replace('\\\\', '\\\\\\\\')

    # Add a class to several characters on the argspec. This way we can
    # highlight them using css, in a similar way to what IPython does.
    # NOTE: Before doing this, we escape common html chars so that they
    # don't interfere with the rest of html present in the page
    argspec = escape(context['argspec'])
    for char in ['=', ',', '(', ')', '*', '**']:
        argspec = argspec.replace(
            char, '<span class="argspec-highlight">' + char + '</span>')
    context['argspec'] = argspec

    doc_file = codecs.open(rst_name, 'w', encoding='utf-8')
    doc_file.write(docstring)
    doc_file.close()

    confoverrides = {'html_context': context,
                     'extensions': ['sphinx.ext.mathjax']}

    doctreedir = osp.join(CONFDIR, 'doctrees')
    sphinx_app = Sphinx(srcdir, CONFDIR, CONFDIR, doctreedir, buildername,
                        confoverrides, status=None, warning=None,
                        freshenv=True, warningiserror=False, tags=None)
    try:
        sphinx_app.build(None, [rst_name])
    except SystemMessage:
        pass
#        output = ("It was not possible to generate rich text help for this "
#                  "object.</br>Please see it in plain text.")


if 'pyqt4' in qt.BINDING.lower():
    import PyQt4.QtWebKit as myQtWeb
elif 'pyqt5' in qt.BINDING.lower():
    try:
        import PyQt5.QtWebEngineWidgets as myQtWeb
    except ImportError:
        import PyQt5.QtWebKitWidgets as myQtWeb
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
            web_page = WebPage(self)
            self.setPage(web_page)


class SphinxWorker(qt.QObject):
    html_ready = qt.pyqtSignal()

    def prepare(self, doc=None, docName=None, docArgspec=None,
                docNote=None, img_path=""):
        self.doc = doc
        self.docName = docName
        self.docArgspec = docArgspec
        self.docNote = docNote
        self.img_path = img_path

    def render(self):
        cntx = generate_context(
            name=self.docName,
            argspec=self.docArgspec,
            note=self.docNote)
        sphinxify(self.doc, cntx, img_path=self.img_path)
        self.thread().terminate()
        self.html_ready.emit()
