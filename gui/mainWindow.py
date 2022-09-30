# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "12 Sep 2022"
# !!! SEE CODERULES.TXT !!!

import sys
import os.path as osp
import time
from functools import partial
import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"
import textwrap
import re
import shutil
import psutil
import glob
import inspect
import webbrowser

from silx.gui import qt

# # path to ParSeq:
# import sys; sys.path.append('..')  # analysis:ignore
from ..core import config
from ..core import singletons as csi
from ..core import commons as cco
# from ..core import spectra as csp
from ..core import save_restore as csr
from ..gui import undoredo as gur
from .nodeWidget import NodeWidget
from .transformer import Transformer
from .fileDialogs import SaveProjectDlg, LoadProjectDlg
from .aboutDialog import AboutDialog
from . import gcommons as gco
from . import webWidget as gww

fontSize = 12 if sys.platform == "darwin" else 8.5
mainWindowWidth, mainWindowHeight = 1600, 768
ICON_SIZE = 32


class QDockWidgetNoClose(qt.QDockWidget):  # ignores Alt+F4 on undocked widget
    def closeEvent(self, evt):
        evt.setAccepted(not evt.spontaneous())

    def changeWindowFlags(self, evt):
        if self.isFloating():
            # The dockWidget will automatically regain it's Qt::widget flag
            # when it becomes docked again
            self.setWindowFlags(qt.Qt.Window |
                                qt.Qt.CustomizeWindowHint |
                                qt.Qt.WindowMaximizeButtonHint)
            # setWindowFlags calls setParent() when changing the flags for a
            # window, causing the widget to be hidden, so:
            self.show()

            # Custom title bar:
            self.titleBar = qt.QWidget(self)
            self.titleBar.setAutoFillBackground(True)
            # self.titleBar.setStyleSheet(
            #     "QWidget {font: bold; font-size: " + str(fontSize) + "pt;}")
            pal = self.titleBar.palette()
            pal.setColor(qt.QPalette.Window, qt.QColor("lightgray"))
            self.titleBar.setPalette(pal)
            height = qt.QApplication.style().pixelMetric(
                qt.QStyle.PM_TitleBarHeight)
            self.titleBar.setMaximumHeight(height)
            layout = qt.QHBoxLayout()
            self.titleBar.setLayout(layout)

            bSize = height - int(16*csi.screenFactor)
            self.buttonSize = qt.QSize(bSize, bSize)
            self.titleIcon = qt.QLabel()
            if hasattr(self, 'dimIcon'):
                self.titleIcon.setPixmap(self.dimIcon.pixmap(self.buttonSize))
            self.titleIcon.setVisible(True)
            layout.addWidget(self.titleIcon, 0)
            self.title = qt.QLabel(self.windowTitle())
            layout.addWidget(self.title, 0)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.addStretch()

            self.dockButton = qt.QToolButton(self)
            self.dockButton.setIcon(qt.QApplication.style().standardIcon(
                qt.QStyle.SP_ToolBarVerticalExtensionButton))
            self.dockButton.setMaximumSize(self.buttonSize)
            self.dockButton.setAutoRaise(True)
            self.dockButton.clicked.connect(self.toggleFloating)
            self.dockButton.setToolTip('dock into the main window')
            layout.addWidget(self.dockButton, 0)

            self.maxButton = qt.QToolButton(self)
            self.maxButton.setIcon(qt.QApplication.style().standardIcon(
                qt.QStyle.SP_TitleBarMaxButton))
            self.maxButton.setMaximumSize(self.buttonSize)
            self.maxButton.setAutoRaise(True)
            self.maxButton.clicked.connect(self.toggleMax)
            layout.addWidget(self.maxButton, 0)

            self.setTitleBarWidget(self.titleBar)
        else:
            self.setTitleBarWidget(None)
            self.parent().setTabIcons()

    def toggleFloating(self):
        self.setFloating(not self.isFloating())
        self.raise_()

    def toggleMax(self):
        if self.isMaximized():
            self.showNormal()
            self.maxButton.setIcon(qt.QApplication.style().standardIcon(
                qt.QStyle.SP_TitleBarMaxButton))
        else:
            self.showMaximized()
            self.maxButton.setIcon(qt.QApplication.style().standardIcon(
                qt.QStyle.SP_TitleBarNormalButton))

    def setFloatingTabColor(self, state):
        if hasattr(self, 'dimIcon'):
            icon = self.dimIconBusy if state == 1 else self.dimIcon
            self.titleIcon.setPixmap(icon.pixmap(self.buttonSize))
        # self.titleIcon.setVisible(state == 1)

        pal = self.title.palette()
        color = gco.BUSY_COLOR_FGND if state == 1 else 'black'
        pal.setColor(qt.QPalette.WindowText, qt.QColor(color))
        self.title.setPalette(pal)
        self.update()


class MainWindowParSeq(qt.QMainWindow):
    intervalCPU = 1000
    beforeTransformSignal = qt.pyqtSignal(qt.QWidget)
    afterTransformSignal = qt.pyqtSignal(qt.QWidget)
    beforeDataTransformSignal = qt.pyqtSignal(list)
    afterDataTransformSignal = qt.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        csi.screenFactor = qt.qApp.desktop().logicalDpiX() / 120.

        selfDir = osp.dirname(__file__)
        self.iconDir = osp.join(selfDir, '_images')
        self.runIcon = qt.QIcon(osp.join(self.iconDir, 'parseq.ico'))
        # self.emptyIcon = qt.QIcon(qt.QPixmap.fromImage(qt.QImage.fromData(
        #     b'<svg version="1.1" viewBox="0 0  32"'
        #     b' xmlns="http://www.w3.org/2000/svg"></svg>')))
        # self.emptyIcon = qt.QIcon()

        transformThread = qt.QThread(self)
        csi.transformer = Transformer()
        csi.transformer.moveToThread(transformThread)
        transformThread.started.connect(
            partial(self.displayStatusMessage, u'calculating…'))
        transformThread.started.connect(csi.transformer.run)
        csi.transformer.ready.connect(
            partial(self.displayStatusMessage, u'ready'))
        csi.mainWindow = self
        self.setWindowTitle(u"ParSeq  \u2014  " + csi.pipelineName)
        self.helpFile = gww.HELPFILE

        self.initTabs()

        # self.settings = qt.QSettings('parseq.ini', qt.QSettings.IniFormat)
        self.setWindowIcon(qt.QIcon(osp.join(self.iconDir, 'parseq.ico')))
        self.setWindowFlags(qt.Qt.Window)

        self.statusBar = self.statusBar()
#        self.statusBar.setStyleSheet("QStatusBar {min-height: 20;}")

        self.statusBarLeft = qt.QLabel("ready")
        self.statusBarCenter = qt.QLabel("")
        self.statusBarCenter.setToolTip("total number of data by categories")
        self.statusBarSpacer = qt.QLabel(" ")
        self.statusBarRight = qt.QLabel("")
        self.statusBarRight.setToolTip("memory and CPU usage")
        self.statusBar.addWidget(self.statusBarLeft)
        self.statusBar.addPermanentWidget(self.statusBarCenter)
        self.statusBar.addPermanentWidget(self.statusBarSpacer)
        self.statusBar.addPermanentWidget(self.statusBarRight)
        self.timerCPU = qt.QTimer(self)
        self.timerCPU.timeout.connect(self.updateCPU)
        self.timerCPU.start(self.intervalCPU)
        self.updateCPU()

        self.restore_perspective()

        self.initToolbar()

        self.beforeTransformSignal.connect(partial(self.updateTabStatus, 1))
        self.afterTransformSignal.connect(partial(self.updateTabStatus, 0))
        self.beforeDataTransformSignal.connect(partial(self.updateItemView, 1))
        self.afterDataTransformSignal.connect(partial(self.updateItemView, 0))

        self.dataChanged()

    def initToolbar(self):
        self.loadAction = qt.QAction(
            qt.QIcon(osp.join(self.iconDir, "icon-load-proj.png")),
            "Load project (Ctrl+O)", self)
        self.loadAction.setShortcut('Ctrl+O')
        self.loadAction.triggered.connect(self.slotLoadProject)

        self.saveAction = qt.QAction(
            qt.QIcon(osp.join(self.iconDir, "icon-save-proj.png")),
            "Save project, data and plots (Ctrl+S)", self)
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.triggered.connect(self.slotSaveProject)
        self.saveAction.setEnabled(False)

        self.undoAction = qt.QAction(
            qt.QIcon(osp.join(self.iconDir, "icon-undo.png")),
            "Undo last action (Ctrl+Z)", self)
        self.undoAction.setShortcut('Ctrl+Z')
        self.undoAction.triggered.connect(partial(self.slotUndo, -1))
        undoMenu = qt.QMenu()
        subAction = qt.QAction(
            'group sequential changes of same parameter', self)
        subAction.setCheckable(True)
        subAction.setChecked(csi.undoGrouping)
        subAction.triggered.connect(self.undoGroup)
        undoMenu.addAction(subAction)
        undoMenu.addSeparator()
        undoMenu.nHeaderActions = len(undoMenu.actions())
        self.undoAction.setMenu(undoMenu)
        menu = self.undoAction.menu()
        menu.aboutToShow.connect(partial(self.populateUndoMenu, menu))

        self.redoAction = qt.QAction(
            qt.QIcon(osp.join(self.iconDir, "icon-redo.png")),
            "Redo last undone action (Ctrl+Shift+Z)", self)
        self.redoAction.setShortcut('Ctrl+Shift+Z')
        self.redoAction.triggered.connect(partial(self.slotRedo, -1))
        redoMenu = qt.QMenu()
        self.redoAction.setMenu(redoMenu)
        menu = self.redoAction.menu()
        menu.aboutToShow.connect(partial(self.populateRedoMenu, menu))
        self.setEnableUndoRedo()

        infoAction = qt.QAction(
            qt.QIcon(osp.join(self.iconDir, "icon-info.png")),
            "About ParSeq… Ctrl+I", self)
        infoAction.setShortcut('Ctrl+I')
        infoAction.triggered.connect(self.slotAbout)

        helpAction = qt.QAction(
            qt.QIcon(osp.join(self.iconDir, "icon-help.png")),
            "Help… Ctrl+?", self)
        helpAction.setShortcut('Ctrl+?')
        helpAction.triggered.connect(self.slotHelp)

        self.toolbar = self.addToolBar("Toolbar")
        # iconSize = int(32 * csi.screenFactor)
        iconSize = 32
        self.toolbar.setIconSize(qt.QSize(iconSize, iconSize))
        self.toolbar.addAction(self.loadAction)
        self.toolbar.addAction(self.saveAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undoAction)
        self.toolbar.addAction(self.redoAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(infoAction)
        self.toolbar.addAction(helpAction)

    def initTabs(self):
        self.setTabPosition(qt.Qt.AllDockWidgetAreas, qt.QTabWidget.West)

        dockFeatures = (qt.QDockWidget.DockWidgetMovable |
                        qt.QDockWidget.DockWidgetFloatable)  # |
#                        qt.QDockWidget.DockWidgetVerticalTitleBar)
        self.docks = {}  # nodeWidget: (dock, node, tabName)
        for i, (name, node) in enumerate(csi.nodes.items()):
            tabName = u'{0} \u2013 {1}'.format(i+1, name)
            dock = QDockWidgetNoClose(tabName, self)
            dock.setAllowedAreas(qt.Qt.AllDockWidgetAreas)
            dock.setFeatures(dockFeatures)
            dock.defStyleSheet = "QDockWidget {font: bold; padding-left: 5px;}"
            dock.setStyleSheet(dock.defStyleSheet)
            self.addDockWidget(qt.Qt.TopDockWidgetArea, dock)
            nodeWidget = NodeWidget(node, dock)
            # nodeWidget = None  # for testing fo app closure
            dock.setWidget(nodeWidget)

            if node.plotDimension is None:
                dock.dimIcon = qt.QIcon()
                dock.dimIconBusy = qt.QIcon()
            elif node.plotDimension < 4:
                dim = node.plotDimension if node.plotDimension < 4 else 'n'
                name = 'icon-item-{0}dim-{1}.png'.format(dim, ICON_SIZE)
                dock.dimIcon = qt.QIcon(osp.join(self.iconDir, name))
                name = 'icon-item-{0}dim-busy-{1}.png'.format(dim, ICON_SIZE)
                dock.dimIconBusy = qt.QIcon(osp.join(self.iconDir, name))

            if i == 0:
                dock0, node0, tabName0 = dock, nodeWidget, tabName
            else:
                self.tabifyDockWidget(dock0, dock)
            # the pipeline head(s) with initially opened file tree:
            first = 1 if len(node.upstreamNodes) == 0 else 0

            try:
                last = 0 if node.widget.transformWidget.hideInitialView \
                    else 1
            except AttributeError:
                last = 1
            if nodeWidget:
                nodeWidget.splitter.setSizes([first, 1, 1, last])
            self.docks[nodeWidget] = dock, node, tabName
            dock.visibilityChanged.connect(partial(self.nodeChanged, node))
            dock.topLevelChanged.connect(dock.changeWindowFlags)

        for node in csi.nodes.values():
            if hasattr(node.widget.transformWidget, 'extraGUISetup'):
                node.widget.transformWidget.extraGUISetup()

        dock0.raise_()
        if node0:
            node0.tree.setFocus()
            csi.currentNode = node0.node

        self.tabWiget = None
        for tab in self.findChildren(qt.QTabBar):
            if tab.tabText(0) == tabName0:
                self.tabWiget = tab
                break
        # self.tabWiget.setStyleSheet("QTabBar::tab { font:bold };")
        # self.tabWiget.setStyleSheet(
        #     "QTabBar::tab {width:32; padding-bottom: 8; padding-top: 8};")

        self.setTabIcons()

        self.makeHelpPages()
        self.makeDocPages()

    def makeHelpPages(self):
        if not osp.exists(self.helpFile):
            shouldBuild = True
        else:
            latest = []
            for files in [glob.glob(osp.join(gww.CONFDIR, '*')),
                          glob.glob(osp.join(gww.GUIDIR, '*.py')),
                          glob.glob(osp.join(gww.COREDIR, '*.py'))]:
                latest.append(max(files, key=osp.getmtime))
            tSource = max(map(osp.getmtime, latest))
            tDoc = osp.getmtime(self.helpFile)
            shouldBuild = tSource > tDoc  # source newer than doc
        if not shouldBuild:
            return

        self.sphinxThread = qt.QThread(self)
        self.sphinxWorker = gww.SphinxWorker()
        self.sphinxWorker.moveToThread(self.sphinxThread)
        self.sphinxThread.started.connect(partial(
            self.sphinxWorker.render, 'help'))
        self.sphinxWorker.html_ready.connect(self._on_help_ready)
        if csi.DEBUG_LEVEL > -1:
            print('building help...')
        self.sphinxWorker.prepareHelp()
        self.sphinxThread.start()

    def _on_help_ready(self):
        if csi.DEBUG_LEVEL > -1:
            print('help ready')

    def makeDocPages(self):
        rawTexts, rawTextNames = [], []
        for i, (name, node) in enumerate(csi.nodes.items()):
            if node.widget is None:
                continue
            if node.widgetClass is None:
                continue
            if not node.widgetClass.__doc__:
                continue

            shouldBuild = True
            try:
                tSource = osp.getmtime(inspect.getfile(node.widgetClass))
                docName = name.replace(' ', '_')
                fname = osp.join(gww.DOCDIR, docName) + '.html'
                if osp.exists(fname):
                    tDoc = osp.getmtime(fname)
                    shouldBuild = tSource > tDoc  # source newer than doc
            except Exception:
                pass
            if not shouldBuild:
                continue

            rawTexts.append(textwrap.dedent(node.widgetClass.__doc__))
            rawTextNames.append(name)

        # make doc pages
        if rawTexts:
            # copy images
            impath = osp.join(csi.appPath, 'doc', '_images')
            if osp.exists(impath):
                dst = osp.join(gww.DOCDIR, '_images')
                shutil.copytree(impath, dst, dirs_exist_ok=True)

            self.sphinxThread = qt.QThread(self)
            self.sphinxWorker = gww.SphinxWorker()
            self.sphinxWorker.moveToThread(self.sphinxThread)
            self.sphinxThread.started.connect(partial(
                self.sphinxWorker.render, 'docs'))
            self.sphinxWorker.html_ready.connect(self._on_docs_ready)
            if csi.DEBUG_LEVEL > -1:
                print('building docs...')
            self.sphinxWorker.prepareDocs(rawTexts, rawTextNames)
            self.sphinxThread.start()
        else:
            self._on_docs_ready(shouldReport=False)

    def _on_docs_ready(self, shouldReport=True):
        if shouldReport and csi.DEBUG_LEVEL > -1:
            print('docs ready')
        for name, node in csi.nodes.items():
            if node.widget is None:
                continue
            if node.widget.help is None:
                continue
            docName = name.replace(' ', '_')
            fname = osp.join(gww.DOCDIR, docName) + '.html'
            if not osp.exists(fname):
                continue
            html = 'file:///' + fname
            html = re.sub('\\\\', '/', html)
            node.widget.helpFile = fname
            node.widget.help.load(qt.QUrl(html))

    def setTabIcons(self):
        for itab, (dock, _, _) in enumerate(self.docks.values()):
            self.setTabIcon(itab, dock)

    def setTabIcon(self, itab, dock, state=0):
        icon = dock.dimIconBusy if state == 1 else dock.dimIcon
        self.tabWiget.setTabIcon(itab, icon)

    def dataChanged(self):
        for node in csi.nodes.values():
            if node.widget is None:
                continue
            if node.widget.tree is None:
                continue
            node.widget.tree.model().dataChanged.emit(
                qt.QModelIndex(), qt.QModelIndex())

    def selChanged(self):
        if len(csi.selectedItems) == 0:
            return
        selNames = [it.alias for it in csi.selectedItems]
        combinedNames = cco.combine_names(selNames)

        cLoaded = len([it for it in csi.allLoadedItems if it.dataType in
                       [cco.DATA_DATASET, cco.DATA_COLUMN_FILE]])
        cBranched = len([it for it in csi.allLoadedItems if it.dataType ==
                         cco.DATA_BRANCH])
        cCreated = len([it for it in csi.allLoadedItems if it.dataType ==
                        cco.DATA_FUNCTION])
        cCombined = len([it for it in csi.allLoadedItems if it.dataType ==
                         cco.DATA_COMBINATION])
        cData = cLoaded + cBranched + cCreated + cCombined

        self.saveAction.setEnabled(cData > 0)
        cSelected = len(csi.selectedItems)
        if cSelected:
            self.statusBarLeft.setText('{0} selected: {1}'.format(
                cSelected, combinedNames))
        else:
            self.statusBarLeft.setText('')
        sLoaded = '{0} loaded'.format(cLoaded) if cLoaded else ''
        sBranched = '{0} branched'.format(cBranched) if cBranched else ''
        sCreated = '{0} created'.format(cCreated) if cCreated else ''
        sCombined = '{0} combined'.format(cCombined) if cCombined else ''
        ss = [s for s in (sLoaded, sBranched, sCreated, sCombined) if s]
        self.statusBarCenter.setText(', '.join(ss))

    def nodeChanged(self, node, visible):
        if visible:
            csi.currentNode = node

    def undoGroup(self):
        csi.undoGrouping = not csi.undoGrouping

    def populateUndoMenu(self, menu):
        # menu = self.sender()
        for action in menu.actions()[menu.nHeaderActions:]:
            menu.removeAction(action)
        icon = qt.QIcon(osp.join(self.iconDir, "icon-undo.png"))
        for ientry, entry in reversed(list(enumerate(csi.undo))):
            subAction = qt.QWidgetAction(self)
            text = gur.getStrRepr(entry)

            menuWidget = qt.QWidget(self)
            menuWidget.setStyleSheet(
                "QWidget:hover{background-color: #edd400;}")
            labelIcon = qt.QLabel(menuWidget)
            labelIcon.setPixmap(icon.pixmap(ICON_SIZE//2, ICON_SIZE//2))
            labelText = qt.QLabel(text, menuWidget)
            labelText.setAttribute(qt.Qt.WA_TranslucentBackground)
            labelText.setAttribute(qt.Qt.WA_TransparentForMouseEvents)
            closeButton = gco.CloseButton(menuWidget)
            closeButton.clicked.connect(
                partial(self._removeFromUndo, ientry, subAction))

            wlayout = qt.QHBoxLayout()
            wlayout.setContentsMargins(2, 2, 2, 2)
            wlayout.addWidget(labelIcon)
            wlayout.addWidget(labelText, 1)
            wlayout.addWidget(closeButton)
            menuWidget.setLayout(wlayout)
            subAction.setDefaultWidget(menuWidget)

            subAction.triggered.connect(partial(self.slotUndo, ientry))
            menu.addAction(subAction)

    def populateRedoMenu(self, menu):
        # menu = self.sender()
        for action in menu.actions():
            menu.removeAction(action)
        icon = qt.QIcon(osp.join(self.iconDir, "icon-redo.png"))
        for ientry, entry in reversed(list(enumerate(csi.redo))):
            subAction = qt.QWidgetAction(self)
            text = gur.getStrRepr(entry)

            menuWidget = qt.QWidget(self)
            menuWidget.setStyleSheet(
                "QWidget:hover{background-color: #99b00b;}")
            labelIcon = qt.QLabel(menuWidget)
            labelIcon.setPixmap(icon.pixmap(ICON_SIZE//2, ICON_SIZE//2))
            labelText = qt.QLabel(text, menuWidget)
            labelText.setAttribute(qt.Qt.WA_TranslucentBackground)
            labelText.setAttribute(qt.Qt.WA_TransparentForMouseEvents)
            closeButton = gco.CloseButton(menuWidget)
            closeButton.clicked.connect(
                partial(self._removeFromRedo, ientry, subAction))

            wlayout = qt.QHBoxLayout()
            wlayout.setContentsMargins(2, 2, 2, 2)
            wlayout.addWidget(labelIcon)
            wlayout.addWidget(labelText, 1)
            wlayout.addWidget(closeButton)
            menuWidget.setLayout(wlayout)
            subAction.setDefaultWidget(menuWidget)

            subAction.triggered.connect(partial(self.slotRedo, ientry))
            menu.addAction(subAction)

    def _removeFromUndo(self, ind, subAction):
        del csi.undo[ind]
        menu = self.undoAction.menu()
        menu.removeAction(subAction)
        self.setEnableUndoRedo()

    def _removeFromRedo(self, ind, subAction):
        del csi.redo[ind]
        menu = self.redoAction.menu()
        menu.removeAction(subAction)
        self.setEnableUndoRedo()

    def slotUndo(self, ind):
        gur.upplyUndo(ind)

    def slotRedo(self, ind):
        gur.upplyRedo(ind)

    def setEnableUndoRedo(self):
        self.undoAction.setEnabled(len(csi.undo) > 0)
        self.redoAction.setEnabled(len(csi.redo) > 0)

    def slotAbout(self):
        lineDialog = AboutDialog(self)
        lineDialog.exec_()

    def slotHelp(self):
        if not osp.exists(self.helpFile):
            return
        webbrowser.open_new_tab(self.helpFile)

    def slotSaveProject(self):
        dlg = SaveProjectDlg(self)
        if config.configLoad.has_option('Project', csi.pipelineName):
            d = osp.dirname(config.configLoad.get('Project', csi.pipelineName))
            dlg.setDirectory(d)
        dlg.ready.connect(self.doSaveProject)
        dlg.open()

    def doSaveProject(self, res):
        fname = res[0][0]
        if not fname.endswith('.pspj'):
            fname += '.pspj'
        try:
            with open(fname, 'w') as f:
                f.write('try')
        except OSError:
            msg = qt.QMessageBox()
            msg.setIcon(qt.QMessageBox.Critical)
            msg.critical(self, "Cannot write file",
                         "Invalid file name {0}".format(fname))
            return
        self.save_project(fname)
        for i, (name, node) in enumerate(csi.nodes.items()):
            node.widget.saveGraph(fname, i, name)
        if len(res) < 5:
            return
        saveNodes, saveTypes, saveScriptMpl, saveScriptSilx = res[1:5]
        plots, h5plots = self.save_data(fname, saveNodes, saveTypes)
        if saveScriptMpl:
            self.save_script(fname, plots, h5plots, 'mpl')
        if saveScriptSilx:
            self.save_script(fname, plots, h5plots, 'silx')
        config.put(config.configLoad, 'Project', csi.pipelineName, fname)

    def slotLoadProject(self):
        dlg = LoadProjectDlg(self)
        if config.configLoad.has_option('Project', csi.pipelineName):
            d = osp.dirname(config.configLoad.get('Project', csi.pipelineName))
            dlg.setDirectory(d)
        dlg.ready.connect(self.doLoadProject)
        dlg.open()

    def doLoadProject(self, res):
        self.cursor().setPos(self.mapToGlobal(qt.QPoint(0, 0)))
        fname = res[0][0]
        self.load_project(fname)
        config.put(config.configLoad, 'Project', csi.pipelineName, fname)

    def closeEvent(self, event):
        self.timerCPU.stop()
        self.save_perspective()
        if len(csi.selectedItems) > 0:
            csi.selectedItems[0].save_transform_params()
        config.write_configs()
        time.sleep(0.1)
        for dock, _, _ in self.docks.values():
            dock.deleteLater()
        csi.transformer.thread().quit()
        csi.transformer.deleteLater()
        super().closeEvent(event)

    def updateItemView(self, state, items):
        if state == 1:
            try:
                for item in items:
                    ind = csi.model.indexFromItem(item)
                    # nodes = [csi.currentNode]
                    nodes = csi.nodes.values()
                    for node in nodes:
                        node.widget.tree.model().dataChanged.emit(ind, ind)
                    node.widget.tree.update()
            except TypeError:  # when an item is removed during transformation
                pass

    def updateTabStatus(self, state, nodeWidget):
        if self.tabWiget is None:
            return
        dock, _, tabName = self.docks[nodeWidget]
        if dock.isFloating():
            dock.setFloatingTabColor(state)
        else:
            color = gco.BUSY_COLOR_FGND if state == 1 else 'black'
            for itab in range(self.tabWiget.count()):
                if self.tabWiget.tabText(itab) == tabName:
                    break
            else:
                return
            self.setTabIcon(itab, dock, state)
            cc = qt.QColor(color)
            self.tabWiget.setTabTextColor(itab, cc)
            ss = dock.defStyleSheet.replace(
                "}", " color: "+cc.name(qt.QColor.HexArgb)+";}")
            dock.setStyleSheet(ss)

    def displayStatusMessage(self, txt, starter=None, what='', duration=0,
                             errorList=None):
        if 'ready' in txt:
            factor, unit, ff = (1e3, 'ms', '{0:.0f}') if duration < 1 else (
                1, 's', '{0:.1f}')
            ss = what + ' finished in ' + ff + ' {1}'
            if errorList:
                errNames = [it.alias for it in errorList]
                combinedNames = cco.combine_names(errNames)
                ss += ', <span style="background-color:red; color:white;">'
                ss += '<b> with errors in ' + combinedNames
                ss += ', see traceback in data tooltip</b>'
                ss += '</span>'
            self.statusBarLeft.setText(ss.format(duration*factor, unit))
        elif 'hdf5' in txt:
            factor, unit, ff = (1e3, 'ms', '{0:.0f}') if duration < 1 else (
                1, 's', '{0:.1f}')
            ss = txt + ' in ' + ff + ' {1}'
            self.statusBarLeft.setText(ss.format(duration*factor, unit))
        else:
            self.statusBarLeft.setText(txt)

    def updateCPU(self):
        res = psutil.virtual_memory().percent, psutil.cpu_percent()
        self.statusBarRight.setText('mem {0:.0f}%   CPU {1:.0f}%'.format(*res))

    def save_perspective(self, configObject=config.configGUI):
        floating = [dock.isFloating() for dock, _, _ in self.docks.values()]
        config.put(configObject, 'Docks', 'floating', str(floating))

        if csi.currentNode is not None:
            config.put(configObject, 'Docks', 'active', csi.currentNode.name)

        geometryStr = 'maximized' if self.isMaximized() else \
            str(self.geometry().getRect())
        config.put(configObject, 'Geometry', 'mainWindow', geometryStr)
        for nodeWidget, (dock, node, tabName) in self.docks.items():
            if nodeWidget is None:
                continue
            if dock.isFloating():
                geometryStr = 'maximized' if dock.isMaximized() else \
                    str(dock.geometry().getRect())
            else:
                geometryStr = '()'
            config.put(
                configObject, 'Geometry', nodeWidget.node.name, geometryStr)

        config.put(configObject, 'Undo', 'grouping', str(csi.undoGrouping))

    def restore_perspective(self, configObject=config.configGUI):
        csi.undoGrouping = config.get(configObject, 'Undo', 'grouping', True)

        floatingStates = config.get(
            configObject, 'Docks', 'floating', [False for node in csi.nodes])
        active = config.get(configObject, 'Docks', 'active', '')

        for nodeStr, floatingState in zip(csi.nodes, floatingStates):
            for nodeWidget, (dock, node, tabName) in self.docks.items():
                if nodeWidget is None:
                    continue
                if nodeStr == nodeWidget.node.name:
                    dock.setFloating(floatingState)
                    break
            else:
                continue
            geometry = config.get(configObject, 'Geometry', nodeStr, ())
            if geometry == 'maximized':
                dock.showMaximized()
            elif len(geometry) == 4:
                dock.setGeometry(*geometry)
            if nodeStr == active:
                dock.raise_()
                nodeWidget.tree.setFocus()
                csi.currentNode = nodeWidget.node

        geometry = config.get(configObject, 'Geometry', 'mainWindow', ())
        if geometry == 'maximized':
            self.showMaximized()
        elif len(geometry) == 4:
            self.setGeometry(*geometry)

    def load_project(self, fname):
        msg = qt.QMessageBox()
        msg.setIcon(qt.QMessageBox.Critical)
        csr.load_project(fname, msg, self.restore_perspective)

    def save_project(self, fname):
        csr.save_project(fname, self.save_perspective)

    def save_data(self, fname, saveNodes, saveTypes):
        msg = qt.QMessageBox()
        msg.setIcon(qt.QMessageBox.Critical)
        return csr.save_data(fname, saveNodes, saveTypes, msg)

    def save_script(self, fname, plots, h5plots, lib='mpl'):
        csr.save_script(fname, plots, h5plots, lib=lib)
