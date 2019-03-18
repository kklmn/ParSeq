# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import os
import sys
from silx.gui import qt

# path to ParSeq:
import os, sys; sys.path.append(os.path.join('..', '..'))  # analysis:ignore
from .nodeWidget import NodeWidget
from ..core import singletons as csi
from ..core import undoredo as cun

mainWindowWidth, mainWindowHeight = 1600, 768


class QDockWidgetNoClose(qt.QDockWidget):  # ignores Alt+F4 on undocked widget
    def closeEvent(self, evt):
        evt.setAccepted(not evt.spontaneous())


class MainWindowParSeq(qt.QMainWindow):
    def __init__(self, parent=None):
        super(MainWindowParSeq, self).__init__(parent)
        selfDir = os.path.dirname(__file__)
        self.iconDir = os.path.join(selfDir, '_images')

        csi.mainWindow = self
        self.setWindowTitle(u"ParSeq  \u2014  " + csi.pipelineName)

        self.initToolbar()
        self.initTabs()

        self.settings = qt.QSettings('parseq.ini', qt.QSettings.IniFormat)
        self.setWindowIcon(qt.QIcon(os.path.join(self.iconDir, 'parseq.ico')))
        self.setWindowFlags(qt.Qt.Window)

        self.statusBar = self.statusBar()
#        self.statusBar.setStyleSheet("QStatusBar {min-height: 20;}")

        self.statusBarLeft = qt.QLabel("Ready")
        self.statusBarRight = qt.QLabel("")
        self.statusBar.addWidget(self.statusBarLeft)
        self.statusBar.addPermanentWidget(self.statusBarRight)

        self.setMinimumSize(qt.QSize(mainWindowWidth, mainWindowHeight))
        self.move(qt.QApplication.desktop().screen().rect().center() -
                  self.rect().center())

    def initToolbar(self):
        saveAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "filesave.png")),
            "Save project (Ctrl+S)", self)
        saveAction.setShortcut('Ctrl+S')

        saveAsAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "filesaveas.png")),
            "Save project as… (Ctrl+Shift+S)", self)
        saveAsAction.setShortcut('Ctrl+Shift+S')

        undoAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "undo.png")),
            "Undo last action (Ctrl+Z)", self)
        undoAction.setShortcut('Ctrl+Z')
        undoAction.triggered.connect(self.slotUndo)

        redoAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "redo.png")),
            "Redo last action (Ctrl+Shift+Z)", self)
        redoAction.setShortcut('Ctrl+Shift+Z')
        redoAction.triggered.connect(self.slotRedo)

        infoAction = qt.QAction(
            qt.QIcon(os.path.join(self.iconDir, "readme.png")),
            "About ParSeq…", self)
        infoAction.setShortcut('Ctrl+?')
        infoAction.triggered.connect(self.slotAbout)

        self.toolbar = self.addToolBar("Toolbar")
        self.toolbar.addAction(saveAction)
        self.toolbar.addAction(saveAsAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(undoAction)
        self.toolbar.addAction(redoAction)
        self.toolbar.addSeparator()
        self.toolbar.addAction(infoAction)

    def initTabs(self):
        self.setTabPosition(qt.Qt.AllDockWidgetAreas, qt.QTabWidget.West)

        dockFeatures = (qt.QDockWidget.DockWidgetMovable |
                        qt.QDockWidget.DockWidgetFloatable)  # |
#                        qt.QDockWidget.DockWidgetVerticalTitleBar)
        self.docks = []
        for i, (name, node) in enumerate(csi.nodes.items()):
            dock = QDockWidgetNoClose(u'{0} \u2013 {1}'.format(i+1, name), self)
            dock.setAllowedAreas(qt.Qt.AllDockWidgetAreas)
            dock.setFeatures(dockFeatures)
            fs = "12" if sys.platform == "darwin" else "9"
            dock.setStyleSheet("""QDockWidget
               {font: bold; font-size: """+fs+"""pt; padding-left: 5px}""")
            self.addDockWidget(qt.Qt.TopDockWidgetArea, dock)
            nodeWidget = NodeWidget(node, self)
            dock.setWidget(nodeWidget)
            if i == 0:
                dock0 = dock
                node0 = node
            else:
                self.tabifyDockWidget(dock0, dock)
            self.docks.append(dock)
#            dock.visibilityChanged.connect(
#                partial(self.nodeChanged, dock, node))
        dock0.raise_()
        # restore after configure all widgets
#        self.restorePerspective()

    def dataChanged(self):
        for node in csi.nodes.values():
            node.widget.tree.dataChanged()

    def selChanged(self):
        selNames = ', '.join([it.alias for it in csi.selectedItems])
        dataCount = len(csi.allLoadedItems)
#        self.statusbar.showMessage('{0}; {1}'.format(dataCount, selNames))
        sellen = len(csi.selectedItems)
        if sellen:
            self.statusBarLeft.setText('{0} selected spectr{1}: {2}'.format(
                sellen, 'um' if sellen == 1 else 'a', selNames))
        else:
            self.statusBarLeft.setText('')
        self.statusBarRight.setText('{0} spectr{1}'.format(
            dataCount, 'um' if dataCount == 1 else 'a'))

    def slotUndo(self):
        if len(cun.get_undo_str()):
            cun.upply_undo()
            self.updateGraphs()
        else:
            print("undo deque is empty.")

    def slotRedo(self):
        if len(cun.get_redo_str()):
            cun.upply_redo()
            self.updateGraphs()
        else:
            print("redo deque is empty.")

    def slotAbout(self):
        from .aboutDialog import AboutDialog
        lineDialog = AboutDialog(self)
        lineDialog.exec_()

    def restorePerspective(self):
        try:
            self.restoreGeometry(self.settings.value("geometry").toByteArray())
        except AttributeError:  # when the 1st time
            return
        self.restoreState(self.settings.value("windowState").toByteArray())
        for inode, node in enumerate(csi.nodes.values()):
            tab = self.tabs[inode]
            sname = 'tab0%d_splitter' % (inode+1)
            for subName in [sname, sname+'_left', sname+'_center',
                            sname+'_right']:
                s = tab.findChild(qt.QSplitter, subName)
                sizes = self.settings.value(subName).toPyObject()
                if sizes is None:
                    sizes = [1, 1, 1]
                s.setSizes([int(size) for size in sizes])

        # restore last active dock tab
#        lastCurrentDock = self.settings.value('currentDock').toString()
#        if lastCurrentDock:
#            currentDock = self.findChild(qt.QDockWidget, lastCurrentDock)
#        else:
#            currentDock = self.findChild(qt.QDockWidget, 'dock01')
#        currentDock.raise_()

#    def nodeChanged(self, dock, node, visible):
#        if visible:
#            self.currentDock = dock
#            self.currentNode = node

    def closeEvent(self, event):
#        self.settings.setValue("currentDock", self.currentDock.objectName())
        self.settings.setValue("geometry", self.saveGeometry())
#        self.settings.setValue("windowState", self.saveState())

        for dock in self.docks:
            dock.deleteLater()
#        for inode, node in enumerate(csi.nodes.values()):
#            tab = self.findChild(
#                qt.QWidget, '{0:01d}-{1}'.format(inode+1, node.name))
#            sname = 'tab0%d_splitter' % (i+1)
#            for subName in [sname, sname+'_left', sname+'_center',
#                            sname+'_right']:
#                s = tab.findChild(qt.QSplitter, subName)
#                self.settings.setValue(subName, s.sizes())
