# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys
import os
from silx.gui import qt

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

    class QWebView(myQtWeb.QWebEngineView):
        """Web view"""
        def __init__(self, parent=None):
            myQtWeb.QWebEngineView.__init__(self, parent)
            web_page = WebPage(self)
            self.setPage(web_page)
