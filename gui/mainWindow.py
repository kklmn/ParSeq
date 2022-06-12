# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "23 Jul 2021"
# !!! SEE CODERULES.TXT !!!

import os
import pickle
import time
import json
import numpy as np
from functools import partial
import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"
import h5py
import autopep8
import textwrap
import re
import shutil

from silx.gui import qt

# path to ParSeq:
import sys; sys.path.append('..')  # analysis:ignore
from ..core import config
from ..core import singletons as csi
from ..core import commons as cco
from ..core import spectra as csp
from ..gui import undoredo as gur
from .nodeWidget import NodeWidget
from .transformer import Transformer
from .fileDialogs import SaveProjectDlg, LoadProjectDlg
from .aboutDialog import AboutDialog
from . import gcommons as gco
from . import webWidget as gww

fontSize = "12" if sys.platform == "darwin" else "9"
mainWindowWidth, mainWindowHeight = 1600, 768

__fdir__ = os.path.abspath(os.path.dirname(__file__))


class QDockWidgetNoClose(qt.QDockWidget):  # ignores Alt+F4 on undocked widget
    def closeEvent(self, evt):
        evt.setAccepted(not evt.spontaneous())

    def changeWindowFlags(self, node, evt):
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
            self.titleBar.setStyleSheet(
                "QWidget {font: bold; font-size: " + fontSize + "pt;}")
            pal = self.titleBar.palette()
            pal.setColor(qt.QPalette.Window, qt.QColor("lightgray"))
            self.titleBar.setPalette(pal)
            height = qt.QApplication.style().pixelMetric(
                qt.QStyle.PM_TitleBarHeight)
            self.titleBar.setMaximumHeight(height)
            layout = qt.QHBoxLayout()
            self.titleBar.setLayout(layout)

            buttonSize = qt.QSize(height-16, height-16)
            self.titleIcon = qt.QLabel()
            # self.titleIcon.setPixmap(self.parent().runIcon.pixmap(buttonSize))
            self.titleIcon.setPixmap(node.widget.dimIcon.pixmap(buttonSize))
            self.titleIcon.setVisible(True)
            layout.addWidget(self.titleIcon, 0)
            self.title = qt.QLabel(self.windowTitle())
            layout.addWidget(self.title, 0)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.addStretch()

            self.dockButton = qt.QToolButton(self)
            self.dockButton.setIcon(qt.QApplication.style().standardIcon(
                qt.QStyle.SP_ToolBarVerticalExtensionButton))
            self.dockButton.setMaximumSize(buttonSize)
            self.dockButton.setAutoRaise(True)
            self.dockButton.clicked.connect(self.toggleFloating)
            self.dockButton.setToolTip('dock into the main window')
            layout.addWidget(self.dockButton, 0)

            self.maxButton = qt.QToolButton(self)
            self.maxButton.setIcon(qt.QApplication.style().standardIcon(
                qt.QStyle.SP_TitleBarMaxButton))
            self.maxButton.setMaximumSize(buttonSize)
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
        pal = self.title.palette()
        if state == 1:
            pal.setColor(qt.QPalette.WindowText, qt.QColor("deepskyblue"))
            self.titleIcon.setVisible(True)
        else:
            pal.setColor(qt.QPalette.WindowText, qt.QColor("black"))
            self.titleIcon.setVisible(False)
        self.title.setPalette(pal)
        self.update()


class MainWindowParSeq(qt.QMainWindow):
    beforeTransformSignal = qt.pyqtSignal(qt.QWidget)
    afterTransformSignal = qt.pyqtSignal(qt.QWidget)
    beforeDataTransformSignal = qt.pyqtSignal(list)
    afterDataTransformSignal = qt.pyqtSignal(list)

    chars2removeMap = {ord(c): '-' for c in '/*? '}

    def __init__(self, parent=None):
        super().__init__(parent)
        selfDir = os.path.dirname(__file__)
        self.iconDir = os.path.join(selfDir, '_images')
        self.runIcon = qt.QIcon(os.path.join(self.iconDir, 'parseq.ico'))
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

        self.initTabs()

        # self.settings = qt.QSettings('parseq.ini', qt.QSettings.IniFormat)
        self.setWindowIcon(qt.QIcon(os.path.join(self.iconDir, 'parseq.ico')))
        self.setWindowFlags(qt.Qt.Window)

        self.statusBar = self.statusBar()
#        self.statusBar.setStyleSheet("QStatusBar {min-height: 20;}")

        self.statusBarLeft = qt.QLabel("ready")
        self.statusBarRight = qt.QLabel("")
        self.statusBar.addWidget(self.statusBarLeft)
        self.statusBar.addPermanentWidget(self.statusBarRight)

        self.restore_perspective()

        self.initToolbar()

        self.beforeTransformSignal.connect(partial(self.updateTabStatus, 1))
        self.afterTransformSignal.connect(partial(self.updateTabStatus, 0))
        self.beforeDataTransformSignal.connect(self.updateItemView)
        self.afterDataTransformSignal.connect(self.updateItemView)

        self.dataChanged()

    def initToolbar(self):
        self.loadAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "icon-load-proj.png")),
            "Load project (Ctrl+O)", self)
        self.loadAction.setShortcut('Ctrl+O')
        self.loadAction.triggered.connect(self.slotLoadProject)

        self.saveAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "icon-save-proj.png")),
            "Save project, data and plots (Ctrl+S)", self)
        self.saveAction.setShortcut('Ctrl+S')
        self.saveAction.triggered.connect(self.slotSaveProject)
        self.saveAction.setEnabled(False)

        self.undoAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "icon-undo.png")),
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
            qt.QIcon(os.path.join(self.iconDir, "icon-redo.png")),
            "Redo last undone action (Ctrl+Shift+Z)", self)
        self.redoAction.setShortcut('Ctrl+Shift+Z')
        self.redoAction.triggered.connect(partial(self.slotRedo, -1))
        redoMenu = qt.QMenu()
        self.redoAction.setMenu(redoMenu)
        menu = self.redoAction.menu()
        menu.aboutToShow.connect(partial(self.populateRedoMenu, menu))
        self.setEnableUredoRedo()

        infoAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "icon-info.png")),
            "About ParSeq…", self)
        infoAction.setShortcut('Ctrl+I')
        infoAction.triggered.connect(self.slotAbout)

        helpAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "icon-help.png")),
            "Help…", self)
        helpAction.setShortcut('Ctrl+?')
        helpAction.triggered.connect(self.slotAbout)

        self.toolbar = self.addToolBar("Toolbar")
        self.toolbar.setIconSize(qt.QSize(32, 32))
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
        self.docks = []
        for i, (name, node) in enumerate(csi.nodes.items()):
            tabName = u'{0} \u2013 {1}'.format(i+1, name)
            dock = QDockWidgetNoClose(tabName, self)
            dock.setAllowedAreas(qt.Qt.AllDockWidgetAreas)
            dock.setFeatures(dockFeatures)
            dock.setStyleSheet(
                "QDockWidget {font: bold; font-size: " + fontSize + "pt;"
                "padding-left: 5px}")
            self.addDockWidget(qt.Qt.TopDockWidgetArea, dock)
            nodeWidget = NodeWidget(node, None)
            dock.setWidget(nodeWidget)
            if i == 0:
                dock0, node0 = dock, nodeWidget
            else:
                self.tabifyDockWidget(dock0, dock)
            # the pipeline head(s) with initially opened file tree:
            first = 1 if len(node.upstreamNodes) == 0 else 0

            try:
                last = 0 if node.widget.transformWidget.hideInitialView \
                    else 1
            except AttributeError:
                last = 1
            nodeWidget.splitter.setSizes([first, 1, 1, last])
            self.docks.append((dock, nodeWidget, tabName))
            dock.visibilityChanged.connect(
                partial(self.nodeChanged, dock, node))
            dock.topLevelChanged.connect(partial(dock.changeWindowFlags, node))
        dock0.raise_()
        node0.tree.setFocus()
        csi.currentNode = node0.node

        self.makeHelpPages()

        self.tabWiget = None
        for tab in self.findChildren(qt.QTabBar):
            if tab.tabText(0) == self.docks[0][2]:
                self.tabWiget = tab
                break
        # self.tabWiget.setStyleSheet("QTabBar::tab { font:bold };")
        self.tabWiget.setStyleSheet(
            "QTabBar::tab {width:32; padding-bottom: 8; padding-top: 8};")

        self.setTabIcons()
        # for dock in self.docks:
        #     self.updateTabStatus(0, dock[1])

    def makeHelpPages(self):
        # copy images
        impath = os.path.join(csi.appPath, 'doc', '_images')
        if os.path.exists(impath):
            dst = os.path.join(gww.DOCDIR, '_images')
            # print(dest_impath, os.path.exists(dst))
            shutil.copytree(impath, dst, dirs_exist_ok=True)

        rawTexts, rawTextNames = [], []
        for i, (name, node) in enumerate(csi.nodes.items()):
            if hasattr(node.widget.transformWidget, 'extraGUISetup'):
                node.widget.transformWidget.extraGUISetup()
            tr = node.transformIn
            if tr is None:
                continue
            if node.widgetClass is None:
                continue
            if not node.widgetClass.__doc__:
                continue
            rawTexts.append(textwrap.dedent(node.widgetClass.__doc__))
            rawTextNames.append(name)

        # make help pages
        if rawTexts:
            self.sphinxThread = qt.QThread(self)
            self.sphinxWorker = gww.SphinxWorker()
            self.sphinxWorker.moveToThread(self.sphinxThread)
            self.sphinxThread.started.connect(self.sphinxWorker.render)
            self.sphinxWorker.html_ready.connect(self._on_sphinx_html_ready)
            self.sphinxWorker.prepare(rawTexts, rawTextNames)
            self.sphinxThread.start()

    def _on_sphinx_html_ready(self):
        for name, node in csi.nodes.items():
            docName = name.replace(' ', '_')
            fname = os.path.join(gww.DOCDIR, docName) + '.html'
            if not os.path.exists(fname):
                continue
            html = 'file:///' + fname
            html = re.sub('\\\\', '/', html)
            node.widget.helpFile = fname
            node.widget.help.load(qt.QUrl(html))

    def setTabIcons(self):
        for itab, node in enumerate(csi.nodes.values()):
            self.tabWiget.setTabIcon(itab, node.widget.dimIcon)

    def dataChanged(self):
        for node in csi.nodes.values():
            node.widget.tree.dataChanged()

    def selChanged(self):
        if len(csi.selectedItems) == 0:
            return
        selNames = [it.alias for it in csi.selectedItems]
        combinedNames = cco.combine_names(selNames)

        cLoaded = len([it for it in csi.allLoadedItems if it.dataType in
                       [csp.DATA_DATASET, csp.DATA_COLUMN_FILE]])
        cBranched = len([it for it in csi.allLoadedItems if it.dataType ==
                         csp.DATA_BRANCH])
        cCreated = len([it for it in csi.allLoadedItems if it.dataType ==
                        csp.DATA_FUNCTION])
        cCombined = len([it for it in csi.allLoadedItems if it.dataType ==
                         csp.DATA_COMBINATION])
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
        self.statusBarRight.setText(', '.join(ss))

    def nodeChanged(self, dock, node, visible):
        if visible:
            csi.currentNode = node

    def undoGroup(self):
        csi.undoGrouping = not csi.undoGrouping

    def populateUndoMenu(self, menu):
        # menu = self.sender()
        for action in menu.actions()[menu.nHeaderActions:]:
            menu.removeAction(action)
        for ientry, entry in reversed(list(enumerate(csi.undo))):
            text = gur.getStrRepr(entry)
            subAction = qt.QAction(qt.QIcon(os.path.join(
                self.iconDir, "icon-undo.png")), text, self)
            subAction.triggered.connect(partial(self.slotUndo, ientry))
            menu.addAction(subAction)

    def populateRedoMenu(self, menu):
        # menu = self.sender()
        for action in menu.actions():
            menu.removeAction(action)
        for ientry, entry in reversed(list(enumerate(csi.redo))):
            text = gur.getStrRepr(entry)
            subAction = qt.QAction(qt.QIcon(os.path.join(
                self.iconDir, "icon-redo.png")), text, self)
            subAction.triggered.connect(partial(self.slotRedo, ientry))
            menu.addAction(subAction)

    def slotUndo(self, ind):
        gur.upplyUndo(ind)

    def slotRedo(self, ind):
        gur.upplyRedo(ind)

    def setEnableUredoRedo(self):
        self.undoAction.setEnabled(len(csi.undo) > 0)
        self.redoAction.setEnabled(len(csi.redo) > 0)

    def slotAbout(self):
        lineDialog = AboutDialog(self)
        lineDialog.exec_()

    def slotSaveProject(self):
        dlg = SaveProjectDlg(self)
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

    def slotLoadProject(self):
        dlg = LoadProjectDlg(self)
        dlg.ready.connect(self.doLoadProject)
        dlg.open()

    def doLoadProject(self, res):
        self.cursor().setPos(self.mapToGlobal(qt.QPoint(0, 0)))
        fname = res[0][0]
        self.load_project(fname)

    def closeEvent(self, event):
        self.save_perspective()
        if len(csi.selectedItems) > 0:
            csi.selectedItems[0].save_transform_params()
        config.write_configs()
        time.sleep(0.1)
        # for dock in self.docks:
        #     dock[0].deleteLater()
        # super().closeEvent(event)

    def updateItemView(self, items):
        for item in items:
            ind = csi.model.indexFromItem(item)
            # nodes = [csi.currentNode]
            nodes = csi.nodes.values()
            for node in nodes:
                node.widget.tree.dataChanged(ind, ind)
            node.widget.tree.update()

    def updateTabStatus(self, state, nodeWidget):
        if self.tabWiget is None:
            return
        docks, nodeWidgets, tabNames = list(zip(*self.docks))
        i = nodeWidgets.index(nodeWidget)

        if docks[i].isFloating():
            docks[i].setFloatingTabColor(state)
        else:
            color = 'deepskyblue' if state == 1 else 'black'
            # icon = self.runIcon if state == 1 else self.emptyIcon
            for itab in range(self.tabWiget.count()):
                if self.tabWiget.tabText(itab) == tabNames[i]:
                    break
            else:
                return
            self.tabWiget.setTabTextColor(itab, qt.QColor(color))
            # self.tabWiget.setTabIcon(itab, icon)

    def displayStatusMessage(self, txt, starter=None, what='', duration=0):
        if 'ready' in txt:
            factor, unit, ff = (1e3, 'ms', '{0:.0f}') if duration < 1 else (
                1, 's', '{0:.1f}')
            ss = what + ' finished in ' + ff + ' {1}'
            self.statusBarLeft.setText(ss.format(duration*factor, unit))
            return
        self.statusBarLeft.setText(txt)

    def save_perspective(self, configObject=config.configGUI):
        floating = [dock.isFloating() for dock, _, _ in self.docks]
        config.put(configObject, 'Docks', 'floating', str(floating))

        if csi.currentNode is not None:
            config.put(configObject, 'Docks', 'active', csi.currentNode.name)

        geometryStr = 'maximized' if self.isMaximized() else \
            str(self.geometry().getRect())
        config.put(configObject, 'Geometry', 'mainWindow', geometryStr)
        for dock, nodeWidget, tabName in self.docks:
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
            for dock, nodeWidget, tabName in self.docks:
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
        configProject = config.ConfigParser()
        configProject.optionxform = str  # makes it case sensitive
        try:
            configProject.read(fname)
        except Exception:
            msg = qt.QMessageBox()
            msg.setIcon(qt.QMessageBox.Critical)
            msg.critical(self, "Cannot load project",
                         "Invalid project file {0}".format(fname))
            return
        self.restore_perspective(configProject)
        dataTree = config.get(configProject, 'Root', 'tree', [])
        root = csi.dataRootItem
        colorPolicyName = config.get(configProject, 'Root', 'colorPolicy',
                                     gco.COLOR_POLICY_NAMES[1])
        root.colorPolicy = gco.COLOR_POLICY_NAMES.index(colorPolicyName)
        if root.colorPolicy == gco.COLOR_POLICY_GRADIENT:
            root.color1 = config.get(configProject, 'Root', 'color1', 'r')
            root.color2 = config.get(configProject, 'Root', 'color2', 'b')
        elif root.colorPolicy == gco.COLOR_POLICY_INDIVIDUAL:
            root.color = config.get(configProject, 'Root', 'color', 'm')
        root.colorAutoUpdate = config.get(
            configProject, 'Root', 'colorAutoUpdate',
            csp.DEFAULT_COLOR_AUTO_UPDATE)

        os.chdir(os.path.dirname(fname))
        csi.model.importData(dataTree, configData=configProject)

    def save_project(self, fname):
        configProject = config.ConfigParser(allow_no_value=True)
        configProject.optionxform = str  # makes it case sensitive

        root = csi.dataRootItem
        config.put(configProject, 'Root', 'tree', repr(root))
        config.put(configProject, 'Root', 'colorPolicy',
                   gco.COLOR_POLICY_NAMES[root.colorPolicy])
        if root.colorPolicy == gco.COLOR_POLICY_GRADIENT:
            config.put(configProject, 'Root', 'color1', str(root.color1))
            config.put(configProject, 'Root', 'color2', str(root.color2))
        elif root.colorPolicy == gco.COLOR_POLICY_INDIVIDUAL:
            config.put(configProject, 'Root', 'color', str(root.color))
        config.put(configProject, 'Root', 'colorAutoUpdate',
                   str(root.colorAutoUpdate))

        dirname = os.path.dirname(fname)
        for item in csi.dataRootItem.get_items(alsoGroupHeads=True):
            item.save_to_project(configProject, dirname)
        self.save_perspective(configProject)
        with open(fname, 'w+') as cf:
            configProject.write(cf)

    def save_data(self, fname, saveNodes, saveTypes):
        if fname.endswith('.pspj'):
            fname = fname.replace('.pspj', '')

        plots = []
        if 'txt' in saveTypes:
            for iNode, ((nodeName, node), saveNode) in enumerate(
                    zip(csi.nodes.items(), saveNodes)):
                if not saveNode:
                    continue
                if node.plotDimension == 1:
                    header = [node.plotXArray] + [y for y in node.plotYArrays]
                else:
                    continue

                curves = {}
                for it in csi.selectedItems:
                    dataToSave = [getattr(it, arr) for arr in header]
                    nname = nodeName.translate(self.chars2removeMap)
                    dname = it.alias.translate(self.chars2removeMap)
                    sname = u'{0}-{1}-{2}'.format(iNode+1, nname, dname)
                    np.savetxt(sname+'.txt.gz', np.column_stack(dataToSave),
                               fmt='%.12g', header=' '.join(header))
                    curves[sname] = [it.alias, it.color, header,
                                     it.plotProps[node.name]]

                    for iG, aG in enumerate(node.auxArrays):
                        dataAux, headerAux = [], []
                        for yN in aG:
                            try:
                                dataAux.append(getattr(it, yN))
                            except AttributeError:
                                break
                            headerAux.append(yN)
                        if len(dataAux) == 0:
                            continue
                        sname = u'{0}-{1}-{2}-aux{3}'.format(
                                iNode+1, nname, dname, iG)
                        np.savetxt(sname+'.txt.gz', np.column_stack(dataAux),
                                   fmt='%.12g', header=' '.join(headerAux))
                        curves[sname] = [it.alias, it.color, headerAux]
                plots.append(['txt', node.name, node.plotDimension,
                              node.widget.getAxisLabels(), curves])

        if 'json' in saveTypes or 'pickle' in saveTypes:
            dataToSave = {}
            snames = []
            for it in csi.selectedItems:
                dname = it.alias.translate(self.chars2removeMap)
                snames.append(dname)
                dataToSave[it] = {}
            for node, saveNode in zip(csi.nodes.values(), saveNodes):
                if not saveNode:
                    continue
                if node.plotDimension == 1:
                    header = [node.plotXArray] + [y for y in node.plotYArrays]
                elif node.plotDimension == 2:
                    header = node.plot2DArray
                elif node.plotDimension == 3:
                    header = node.plot3DArray

                curves = {}
                for it, sname in zip(csi.selectedItems, snames):
                    for aN in node.arrays:
                        dataToSave[it][aN] = getattr(it, aN).tolist()
                    for aN in [j for i in node.auxArrays for j in i]:
                        try:
                            dataToSave[it][aN] = getattr(it, aN).tolist()
                        except AttributeError:
                            continue
                    curves[sname] = [it.alias, it.color, header,
                                     it.plotProps[node.name]]
                    if node.auxArrays:
                        headerAux = []
                        for aG in node.auxArrays:
                            for yN in aG:
                                if not hasattr(it, yN):
                                    break
                            else:
                                headerAux.append(aG)
                        if headerAux:
                            curves[sname].append(headerAux)
                if 'json' in saveTypes and node.plotDimension == 1:
                    plots.append(
                        ['json', node.name, node.plotDimension,
                         node.widget.getAxisLabels(), curves])
                if 'pickle' in saveTypes:
                    plots.append(
                        ['pickle', node.name, node.plotDimension,
                         node.widget.getAxisLabels(), curves])

            for it, sname in zip(csi.selectedItems, snames):
                if 'json' in saveTypes and node.plotDimension == 1:
                    with open(sname+'.json', 'w') as f:
                        json.dump(dataToSave[it], f)
                if 'pickle' in saveTypes:
                    with open(sname+'.pickle', 'wb') as f:
                        pickle.dump(dataToSave[it], f)

        h5plots = []
        if 'h5' in saveTypes:
            dataToSave = {}
            snames = []
            for it in csi.selectedItems:
                dname = it.alias.translate(self.chars2removeMap)
                snames.append('data/' + dname)
                dataToSave[it] = {}
            for node, saveNode in zip(csi.nodes.values(), saveNodes):
                if not saveNode:
                    continue
                if node.plotDimension == 1:
                    header = [node.plotXArray] + [y for y in node.plotYArrays]
                elif node.plotDimension == 2:
                    header = node.plot2DArray
                elif node.plotDimension == 3:
                    header = node.plot3DArray

                curves = {}
                for it, sname in zip(csi.selectedItems, snames):
                    for aN in node.arrays:
                        dataToSave[it][aN] = getattr(it, aN)
                    for aN in [j for i in node.auxArrays for j in i]:
                        try:
                            dataToSave[it][aN] = getattr(it, aN)
                        except AttributeError:
                            continue
                    curves[sname] = [it.alias, it.color, header,
                                     it.plotProps[node.name]]
                    if node.auxArrays:
                        headerAux = []
                        for aG in node.auxArrays:
                            for yN in aG:
                                if not hasattr(it, yN):
                                    break
                            else:
                                headerAux.append(aG)
                        if headerAux:
                            curves[sname].append(headerAux)
                h5plots.append([node.name, node.plotDimension,
                                node.widget.getAxisLabels(), curves])

            with h5py.File(fname+'.h5', 'w') as f:
                dataGrp = f.create_group('data')
                plotsGrp = f.create_group('plots')
                for it in csi.selectedItems:
                    dname = it.alias.translate(self.chars2removeMap)
                    if dname in f:
                        continue
                    grp = dataGrp.create_group(dname)
                    for aN in dataToSave[it]:
                        if aN in grp:
                            continue
                        com = None if np.isscalar(dataToSave[it][aN]) else\
                            'gzip'
                        grp.create_dataset(aN, data=dataToSave[it][aN],
                                           compression=com)
                    grp.create_dataset('transformParams',
                                       data=str(it.transformParams))
                for plot in h5plots:
                    grp = plotsGrp.create_group(plot[0])
                    grp.create_dataset('ndim', data=plot[1])
                    grp.create_dataset('axes', data=str(plot[2]))
                    grp.create_dataset('plots', data=str(plot[3]))

        return plots, h5plots

    def _script(self, lines, sname):
        for i, line in enumerate(lines):
            if 'def ' + sname in line:
                istart = i
            if 'end ' + sname in line:
                iend = i
                break
        else:
            return []
        return lines[istart-2: iend+1]

    def save_script(self, fname, plots, h5plots, lib='mpl'):
        if len(plots) == len(h5plots) == 0:
            print("no plots selected")
            return
        if fname.endswith('.pspj'):
            fname = fname.replace('.pspj', '')
        basefname = os.path.basename(fname)

        pyExportMod = os.path.join(__fdir__, 'plotExport.py')
        with open(pyExportMod, 'r') as f:
            lines = [line.rstrip('\n') for line in f]

        output = lines[:2]
        if lib == 'mpl':
            output.extend(lines[2:4])

        output.extend(self._script(lines, "readFile"))
        dims = set([plot[2] for plot in plots] + [plot[1] for plot in h5plots])
        for dim in [1, 2, 3]:
            if dim in dims:
                output.extend(self._script(lines, "read{0}D".format(dim)))
                output.extend(
                    self._script(lines, "plot{0}D{1}".format(dim, lib)))

        if len(h5plots) > 0:
            output.extend(self._script(lines, "getPlotsFromHDF5"))
        output.extend(self._script(lines, "plotSavedData"))
        output.extend(["", "", "if __name__ == '__main__':"])

        if len(plots) == 0:
            output.extend(["    h5name = '{0}.h5'".format(basefname),
                           "    plots = getPlotsFromHDF5(h5name)"])
        elif len(h5plots) == 0:
            output.append("    plots = {0}".format(
                autopep8.fix_code(repr(plots), options={'aggressive': 2})))
        else:
            output.extend([
                "    # you can get plot definitions from the h5 file:",
                "    # h5name = '{0}.h5'".format(basefname),
                "    # plots = getPlotsFromHDF5(h5name)", "",
                "    # ...or from the `plots` list:",
                "    plots = {0}".format(
                    autopep8.fix_code(repr(plots), options={'aggressive': 2}))
                ])
        if lib == 'silx':
            output.extend(["    from silx.gui import qt",
                           "    app = qt.QApplication([])"])
        output.extend(["    plotSavedData(plots, '{0}')".format(lib), ""])
        if lib == 'silx':
            output.extend(["    app.exec_()"])

        fnameOut = '{0}_{1}.py'.format(fname, lib)
        with open(fnameOut, 'w') as f:
            f.write('\n'.join(output))
