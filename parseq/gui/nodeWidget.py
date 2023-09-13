# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "2 Mar 2023"
# !!! SEE CODERULES.TXT !!!

import sys
import os.path as osp
import webbrowser
from collections import Counter
from functools import partial
import traceback
# import time
import glob

from silx.gui import qt, colors, icons

from ..core import singletons as csi
from ..core import commons as cco
# from ..core import spectra as csp
from ..core.config import configLoad
from ..core.logger import logger
from ..gui import fileTreeModelView as gft
from ..gui.fileTreeModelView import FileTreeView
from ..gui.dataTreeModelView import DataTreeView
from ..gui.plot import Plot1D, Plot2D, Plot3D
from ..gui.webWidget import QWebView
from ..gui.columnFormat import ColumnFormatWidget
from ..gui.combineSpectra import CombineSpectraWidget
from . import gcommons as gco

SPLITTER_WIDTH, SPLITTER_BUTTON_MARGIN = 14, 6
COLORMAP = 'viridis'

autoLoadDelay = 3000  # msec


class QSplitterButton(qt.QPushButton):
    def __init__(self, text, parent, isVertical=False,
                 margin=SPLITTER_BUTTON_MARGIN):
        super().__init__(text, parent)
        self.rawText = str(text)
        self.isVertical = isVertical
        fontSize = "10" if sys.platform == "darwin" else "8.5" \
            if sys.platform == "linux" else "8"
        grad = "x1: 0, y1: 1, x2: 0, y2: 0"
        bottomMargin = '-1' if isVertical else '-3'
        self.setStyleSheet("""
            QPushButton {
                font-size: """ + fontSize + """pt; color: #151575;
                text-align: bottom; border-radius: 6px;
                margin: 0px 0px """ + bottomMargin + """px 0px;
                background-color: qlineargradient(
                """ + grad + """, stop: 0 #e6e7ea, stop: 1 #cacbce);}
            QPushButton:pressed {
                background-color: qlineargradient(
                """ + grad + """, stop: 0 #cacbce, stop: 1 #e6e7ea);}
            QPushButton:hover {
                background-color: qlineargradient(
                """ + grad + """, stop: 0 #6087cefa, stop: 1 #7097eeff);} """)
        myFont = qt.QFont()
        myFont.setPointSize(int(float(fontSize)))
        fm = qt.QFontMetrics(myFont)
        width = fm.width(text) + 3*margin
        if isVertical:
            self.setFixedSize(int(SPLITTER_WIDTH*csi.screenFactor), width)
        else:
            self.setFixedSize(width, int(SPLITTER_WIDTH*csi.screenFactor))

    def paintEvent(self, event):
        painter = qt.QStylePainter(self)
        if self.isVertical:
            painter.rotate(270)
            painter.translate(-self.height(), 0)
        else:
            painter.translate(0, -2)
        painter.drawControl(qt.QStyle.CE_PushButton, self.getStyleOptions())

    def getStyleOptions(self):
        options = qt.QStyleOptionButton()
        options.initFrom(self)
        size = options.rect.size()
        if self.isVertical:
            size.transpose()
        options.rect.setSize(size)
        try:
            options.features = qt.QStyleOptionButton.None_
        except AttributeError:
            options.features = getattr(qt.QStyleOptionButton, 'None')
        if self.isFlat():
            options.features |= qt.QStyleOptionButton.Flat
        if self.menu():
            options.features |= qt.QStyleOptionButton.HasMenu
        if self.autoDefault() or self.isDefault():
            options.features |= qt.QStyleOptionButton.AutoDefaultButton
        if self.isDefault():
            options.features |= qt.QStyleOptionButton.DefaultButton
        if self.isDown() or (self.menu() and self.menu().isVisible()):
            options.state |= qt.QStyle.State_Sunken
        if self.isChecked():
            options.state |= qt.QStyle.State_On
        if not self.isFlat() and not self.isDown():
            options.state |= qt.QStyle.State_Raised

        options.text = self.text()
        options.icon = self.icon()
        options.iconSize = self.iconSize()
        return options


class NodeWidget(qt.QWidget):
    enableAutoLoad = qt.pyqtSignal(bool)

    def __init__(self, node, parent=None):
        super().__init__(parent)
        self.mainWindow = parent
#        self.setContentsMargins(0, 0, 0, 0)
        self.node = node
        self.helpFile = ''
        node.widget = self
        self.transformWidget = None
        self.tree = None
        self.help = None
        self.pendingPropDialog = None
        self.wasNeverPlotted = True
        self.onTransform = False
        self.fitLines = []

        self.makeSplitters()

        self.fillSplitterFiles()
        self.fillSplitterData()
        self.fillSplitterPlot()
        self.makeTransformWidget(self.splitterTransform)
        self.fillSplitterTransform()
        self.makeSplitterButtons()
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setStretchFactor(3, 0)

        # if not osp.exists(self.helpFile):
        if True:
            self.splitterTransform.setSizes([1, 0])
        self.splitterButtons['files && containers'].clicked.emit()
        self.splitterButtons['transform'].clicked.emit()

        self.splitter.setSizes([1, 1, 1, 1])  # set in MainWindowParSeq
        if len(csi.selectedItems) > 0:
            self.updateNodeForSelectedItems()
            self.replot()
        else:
            self.gotoLastData()
        # # doesn't work in Linux:
        # self.fileSystemWatcher = qt.QFileSystemWatcher(self)

    def gotoLastData(self):
        self.files.gotoLastData()
        if configLoad.has_section('Format_'+self.node.name):
            formats = dict(configLoad.items('Format_'+self.node.name))
            self.columnFormat.setDataFormat(formats)

    def makeSplitters(self):
        layout = qt.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = qt.QSplitter(self)
        self.splitter.setOrientation(qt.Qt.Horizontal)
        layout.addWidget(self.splitter)
        self.setLayout(layout)
        # grad = "x1: 0, y1: 0, x2: 0, y2: 1"
        # self.splitter.setStyleSheet(
        #     "QSplitterHandle:hover {} "
        #     "QSplitter::handle:horizontal:hover{background-color: "
        #     "qlineargradient(" + grad + ", stop: 0 #6087cefa, "
        #     "stop: 1 #7097eeff);}")
        # self.splitter.setStyleSheet(
        #     "QSplitterHandle:hover {} "
        #     "QSplitter::handle:horizontal:hover{background-color: #6087cefa;"
        #     "margin: 5px;}"
        #     "QSplitter::handle:vertical:hover{background-color: #6087cefa;"
        #     "margin: 5px;}")
        self.splitter.setStyleSheet(
            "QSplitterHandle:hover {} "
            "QSplitter::handle:hover{background-color: #6087cefa;"
            "margin: 5px;}")

        self.splitterFiles = qt.QSplitter(self.splitter)
        self.splitterFiles.setOrientation(qt.Qt.Vertical)
        self.splitterData = qt.QSplitter(self.splitter)
        self.splitterData.setOrientation(qt.Qt.Vertical)
        self.splitterPlot = qt.QSplitter(self.splitter)
        self.splitterPlot.setOrientation(qt.Qt.Vertical)
        self.splitterTransform = qt.QSplitter(self.splitter)
        self.splitterTransform.setOrientation(qt.Qt.Vertical)

    def fillSplitterFiles(self):
        splitterInner = qt.QWidget(self.splitterFiles)

        labelIncludeFilter = qt.QLabel('include')
        self.editIncludeFilter = qt.QLineEdit()
        self.editIncludeFilter.setToolTip(
            "A list of comma separated wildcards.\n"
            "For quick jump into a location:\npaste its path in front of the\n"
            "wildcard filter(s) and press Enter.")
        self.editIncludeFilter.returnPressed.connect(self.setIncludeFilter)
        if hasattr(self.node, 'includeFilters'):
            self.editIncludeFilter.setText(', '.join(self.node.includeFilters))

        labelExcludeFilter = qt.QLabel('exclude')
        self.editExcludeFilter = qt.QLineEdit()
        self.editExcludeFilter.returnPressed.connect(self.setExcludeFilter)
        if hasattr(self.node, 'excludeFilters'):
            self.editExcludeFilter.setText(', '.join(self.node.excludeFilters))
        self.editExcludeFilter.setToolTip("comma separated wildcards")

        self.files = FileTreeView(self.node, splitterInner)
#        self.files.doubleClicked.connect(self.loadFiles)

        self.autoPanel = qt.QGroupBox(self)
        self.autoPanel.setTitle('auto load new data from current location')
        self.autoPanel.setCheckable(True)
        self.autoPanel.setChecked(False)
        # self.autoPanel.setEnabled(False)
        self.autoPanel.toggled.connect(self.autoLoadToggled)
        self.enableAutoLoad.connect(self.autoLoadChangeEnabled)
        self.autoFileList = []
        layoutA = qt.QHBoxLayout()
        layoutA.setContentsMargins(6, 0, 0, 0)
        labelA1 = qt.QLabel('auto load every')
        layoutA.addWidget(labelA1)
        self.filesAutoLoadEvery = qt.QSpinBox()
        self.filesAutoLoadEvery.setMinimum(1)
        self.filesAutoLoadEvery.setMaximum(1000)
        self.filesAutoLoadEvery.setValue(1)
        self.filesAutoLoadEvery.setSuffix('st')
        self.filesAutoLoadEvery.valueChanged.connect(self.autoLoadEveryChanged)
        self.autoLoadTimer = None

        layoutA.addWidget(self.filesAutoLoadEvery)
        labelA2 = qt.QLabel('file/dataset')
        layoutA.addWidget(labelA2)
        layoutA.addStretch()
        self.autoPanel.setLayout(layoutA)

        gotoLastButton = qt.QToolButton()
        gotoLastButton.setFixedSize(24, 24)
        gotoLastButton.setIcon(icons.getQIcon('last'))
        tt = "Go to the latest loaded data"
        if configLoad.has_option('Data', self.node.name):
            tt += "\n" + configLoad.get('Data', self.node.name)
        gotoLastButton.setToolTip(tt)
        gotoLastButton.clicked.connect(self.gotoLastData)
        color = qt.QColor(gco.COLOR_LOAD_CAN)
        color.setAlphaF(0.32)
        gotoLastButton.setStyleSheet(
            "QToolButton{border-radius: 8px;}"
            "QToolButton:hover{background-color: " +
            color.name(qt.QColor.HexArgb) + ";}")

        fileFilterLayout = qt.QGridLayout()
        fileFilterLayout.addWidget(labelIncludeFilter, 0, 0)
        fileFilterLayout.addWidget(self.editIncludeFilter, 0, 1)
        fileFilterLayout.addWidget(labelExcludeFilter, 1, 0)
        fileFilterLayout.addWidget(self.editExcludeFilter, 1, 1)
        fileFilterLayout.addWidget(gotoLastButton, 0, 2, 2, 1,
                                   qt.Qt.AlignHCenter | qt.Qt.AlignVCenter)
        layout = qt.QVBoxLayout()
        layout.setContentsMargins(4, 0, 0, 4)
        layout.addLayout(fileFilterLayout)
        layout.addWidget(self.files)
        layout.addWidget(self.autoPanel)
        splitterInner.setLayout(layout)

        self.columnFormat = ColumnFormatWidget(self.splitterFiles, self.node)

        self.splitterFiles.setStretchFactor(0, 1)  # don't remove
        self.splitterFiles.setStretchFactor(1, 0)

    def fillSplitterData(self):
        splitterInner = qt.QWidget(self.splitterData)
        self.pickWidget = qt.QWidget(splitterInner)
        labelPick = qt.QLabel('Pick data')
        cancelPick = qt.QPushButton('Cancel')
        cancelPick.setStyleSheet("QPushButton {background-color: tomato;}")
        cancelPick.setMinimumWidth(40)
        cancelPick.clicked.connect(self.cancelPropsToPickedData)
        applyPick = qt.QPushButton('Apply')
        applyPick.setStyleSheet("QPushButton {background-color: lightgreen;}")
        applyPick.setMinimumWidth(40)
        applyPick.clicked.connect(self.applyPropsToPickedData)

        pickLayout = qt.QHBoxLayout()
        pickLayout.setContentsMargins(0, 0, 0, 0)
        pickLayout.addWidget(labelPick)
        pickLayout.addWidget(cancelPick, 1)
        pickLayout.addWidget(applyPick, 1)
        self.pickWidget.setLayout(pickLayout)
        self.pickWidget.setVisible(False)

        self.tree = DataTreeView(self.node, splitterInner)
        self.tree.model().needReplot.connect(self.replot)
        self.tree.selectionModel().selectionChanged.connect(self.selChanged)

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pickWidget)
        layout.addWidget(self.tree)
        splitterInner.setLayout(layout)

        self.combiner = CombineSpectraWidget(self.splitterData, self.node)

        self.splitterData.setStretchFactor(0, 1)  # don't remove
        self.splitterData.setStretchFactor(1, 0)
        self.splitterData.setSizes([1, 0])

    def fillSplitterPlot(self):
        self.makePlotWidget()
        self.makeFitWidgets()
        self.makeMetadataWidget()

        self.splitterPlot.setCollapsible(0, False)
        self.splitterPlot.setStretchFactor(0, 1)  # don't remove
        for i in range(1, self.splitterPlot.count()):
            self.splitterPlot.setStretchFactor(i, 0)
        sizes = [0] * self.splitterPlot.count()
        sizes[0] = 1
        self.splitterPlot.setSizes(sizes)

    def fillSplitterTransform(self):
        self.help = QWebView(self.splitterTransform)
        # self.help.setHtml('no documentation available')
        self.help.setMinimumSize(qt.QSize(100, 5))
        self.help.page().setLinkDelegationPolicy(2)
        self.help.history().clear()
        self.help.page().history().clear()
        self.lastBrowserLink = ''
        self.help.page().linkClicked.connect(
            self.linkClicked, type=qt.Qt.UniqueConnection)

        self.splitterTransform.setCollapsible(0, False)
        self.splitterTransform.setStretchFactor(0, 0)  # don't remove
        self.splitterTransform.setStretchFactor(1, 1)

    def makeTransformWidget(self, parent):
        # insert QScrollArea for a possibly big transformWidget
        scrollArea = qt.QScrollArea(parent)
        scrollArea.setFrameShape(qt.QFrame.NoFrame)
        scrollArea.setWidgetResizable(True)
        scrollArea.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        scrollArea.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAsNeeded)

        if self.node.widgetClass is not None:
            self.transformWidget = self.node.widgetClass(
                parent=scrollArea, node=self.node)
            scrollArea.setMinimumWidth(self.transformWidget.sizeHint().width())
        else:
            self.transformWidget = qt.QWidget(parent=scrollArea)
        scrollArea.setWidget(self.transformWidget)
        for tr in self.node.transformsIn:
            tr.sendSignals = csi.mainWindow is not None
            tr.widget = self.transformWidget

    def makeSplitterButtons(self):
        "Orientation should be given for the closed state."
        self.splitterButtons = {}
        self.makeSplitterButton('files && containers', self.splitter, 1, 0)
        self.makeSplitterButton('data', self.splitter, 2, 1)
        self.makeSplitterButton('transform', self.splitter, 3, 3)
        self.makeSplitterButton('data format', self.splitterFiles, 1, 1)
        self.makeSplitterButton('combine', self.splitterData, 1, 1)

        ind = 1
        for fit in csi.fits.values():
            if fit.node is self.node and fit.widgetClass is not None:
                but = self.makeSplitterButton(
                    fit.name, self.splitterPlot, ind, ind)
                but.setToolTip(fit.tooltip)
                ind += 1
        self.makeSplitterButton('metadata', self.splitterPlot, ind, ind)

        self.makeSplitterButton('help', self.splitterTransform, 1, 1)
        self.makeSplitterHelpButton(self.splitterTransform, 1)

    def makeSplitterButton(self, name, splitter, indHandle, indSizes):
        handle = splitter.handle(indHandle)
        if handle is None:
            return
        isVerical = splitter.orientation() == qt.Qt.Horizontal
        trNames = ''
        if name == 'transform':
            if self.node.widgetClass is not None:
                if hasattr(self.node.widgetClass, 'name'):
                    trNames = self.node.widgetClass.name
            if not trNames:
                trNames = ', '.join([tr.name for tr in self.node.transformsIn])
        if trNames:
            nameBut = name + ': ' + trNames
        else:
            nameBut = name
        button = QSplitterButton(nameBut, handle, isVerical)
        button.setText(button.rawText)
        if isVerical:
            splitter.setHandleWidth(int(SPLITTER_WIDTH*csi.screenFactor))
        else:
            splitter.setHandleWidth(int(SPLITTER_WIDTH*csi.screenFactor))
        po = qt.QSizePolicy(qt.QSizePolicy.Preferred, qt.QSizePolicy.Preferred)
        button.setSizePolicy(po)
        button.clicked.connect(
            partial(self.handleSplitterButton, button, indSizes))
        if isVerical:
            sLayout = qt.QVBoxLayout()
        else:
            sLayout = qt.QHBoxLayout()
        sLayout.setContentsMargins(0, 0, 0, 0)
        sLayout.addStretch(1)
        sLayout.addWidget(button, 0)
        sLayout.addStretch(1)
        handle.setLayout(sLayout)
        self.splitterButtons[name] = button
        return button

    def makeSplitterHelpButton(self, splitter, indHandle):
        handle = splitter.handle(indHandle)
        if handle is None:
            return
        button = QSplitterButton("open in browser", handle, margin=10)
        button.clicked.connect(self.handleSplitterHelpButton)
        sLayout = handle.layout()
        sLayout.addWidget(button)
        handle.setLayout(sLayout)

    def handleSplitterButton(self, button, indSizes):
        splitter = button.parent().splitter()
        sizes = splitter.sizes()
        if sizes[indSizes]:
            sizes[indSizes] = 0
        else:
            sizes[indSizes] = 1
        splitter.setSizes(sizes)
        if splitter is self.splitterPlot:
            self.updateFits(shouldClear=True)

    def handleSplitterHelpButton(self):
        webbrowser.open_new_tab(self.helpFile)
        # webbrowser.open_new_tab("https://github.com/")

    def setIncludeFilter(self):
        txt = self.editIncludeFilter.text()
        lst = [s.strip() for s in txt.split(',')]
        if hasattr(self.node, 'includeFilters'):
            if lst == self.node.includeFilters:
                return
        if lst:
            dirname = osp.dirname(lst[0])
            if dirname:
                lst[0] = lst[0][len(dirname)+1:]
                self.node.includeFilters = lst
                self.editIncludeFilter.setText(', '.join(lst))
                self.files.initModel()
                self.files.gotoWhenReady(dirname)
                return
        self.node.includeFilters = lst
        self.files.initModel()

    def setExcludeFilter(self):
        txt = self.editExcludeFilter.text()
        lst = [s.strip() for s in txt.split(',')]
        if hasattr(self.node, 'excludeFilters'):
            if lst == self.node.excludeFilters:
                return
        self.node.excludeFilters = lst
        self.files.initModel()

    def _makeAxisLabels(self, labels, for3Dtitle=False):
        res = []
        node = self.node
        for label in labels:
            if label in node.arrays:
                u = node.get_prop(label, 'plotUnit')
                if for3Dtitle:
                    space = '' if ('°' in u) or ('^o' in u) else ' '
                    ll = node.get_prop(label, 'plotLabel') + \
                        '[{0}] = {1:#.4g}' + space + u
                else:
                    sU = u" ({0})".format(u) if u else ""
                    ll = "{0}{1}".format(node.get_prop(label, 'plotLabel'), sU)
                res.append(ll)
            else:
                if for3Dtitle:
                    res.append(label + '[{0}]')
                else:
                    res.append(label)
        return res

    def titleCallback3D(self, ind):
        if len(csi.selectedItems) > 0:
            item = csi.selectedItems[0]
        else:
            return ""
        if not self.shouldPlotItem(item):
            return ""
        node = self.node
        labels = node.get_prop(node.plot3DArray, 'plotLabel')
        axisLabels = self._makeAxisLabels(labels, True)
        title = axisLabels[self.plot._perspective]
        if '{1' in title:
            arr = None
            if self.plot._perspective == 0:
                if hasattr(self.node, 'plotXArray'):
                    arr = getattr(item, self.node.plotXArray)
            elif self.plot._perspective == 1:
                if hasattr(self.node, 'plotYArrays'):
                    arr = getattr(item, self.node.plotYArrays[-1])
            elif self.plot._perspective == 2:
                if hasattr(self.node, 'plotZArray'):
                    arr = getattr(item, self.node.plotZArray)
            if arr is None:
                return ""
            try:
                return title.format(ind, arr[ind])
            except Exception:
                return ""
        try:
            return title.format(ind)
        except Exception:
            return ""

    def makePlotWidget(self):
        node = self.node
        # self.backend = dict(backend='opengl')
        self.backend = dict(backend='matplotlib')

        if node.plotDimension == 3:
            self.plot = Plot3D(self.splitterPlot, position=Plot3D.posInfo,
                               **self.backend)
            self.plot.setCustomPosInfo()
            self.plot.setTitleCallback(self.titleCallback3D)
        elif node.plotDimension == 2:
            self.plot = Plot2D(self.splitterPlot, **self.backend)
        elif node.plotDimension == 1:
            xLbl = node.get_arrays_prop('qLabel', role='x')[0]
            yLbl = node.get_arrays_prop('qLabel', role='y')[0]
            hasCustomCursorLabels = False
            if self.node.widgetClass is not None:
                if (hasattr(self.node.widgetClass, 'cursorPositionCallback')
                        and hasattr(self.node.widgetClass, 'cursorLabels')):
                    hasCustomCursorLabels = True
            if hasCustomCursorLabels:
                position = [
                    (label, partial(
                        self.node.widgetClass.cursorPositionCallback, label))
                    for label in self.node.widgetClass.cursorLabels]
            else:
                position = [(xLbl, lambda x, y: x), (yLbl, lambda x, y: y)]
            self.plot = Plot1D(self.splitterPlot, position=position,
                               **self.backend)
            self.plot.getXAxis().setLabel(xLbl)
            self.plot.getYAxis().setLabel(yLbl)
        else:
            raise ValueError("wrong plot dimension")
        self.plotSetup()
        self.plot.setMinimumWidth(20)
        self.savedPlotProps = {'cm.vmin': None, 'cm.vmax': None}

    def plotSetup(self):
        node = self.node
        if node.plotDimension == 1:
            try:
                unit = node.get_arrays_prop('plotUnit', role='x')[0]
                strUnit = u" ({0})".format(unit) if unit else ""
            except AttributeError:
                strUnit = ''
            self.plotXLabel = u"{0}{1}".format(
                node.get_prop(node.plotXArray, 'plotLabel'), strUnit)
            self.plot.setGraphXLabel(label=self.plotXLabel)
        elif node.plotDimension == 2:
            labels = node.get_prop(node.plot2DArray, 'plotLabel')
            axisLabels = self._makeAxisLabels(labels)
            self.plot.getXAxis().setLabel(axisLabels[0])
            self.plot.getYAxis().setLabel(axisLabels[1])
        elif node.plotDimension == 3:
            self.plot.setColormap(COLORMAP)
            labels = node.get_prop(node.plot3DArray, 'plotLabel')
            axisLabels = self._makeAxisLabels(labels)
            self.plot.setLabels(axisLabels)

    def makeFitWidgets(self):
        self.fitWidgets = []
        for ifit, fit in enumerate(csi.fits.values()):
            if fit.node is self.node and fit.widgetClass is not None:
                fitWidget = fit.widgetClass(self.splitterPlot, fit, self.plot)
                fitWidget.fitReady.connect(
                    partial(self.replotFit, fit, ifit))
                self.fitWidgets.append(fitWidget)
                curveLabel = fit.dataAttrs['fit']
                if curveLabel not in self.fitLines:
                    self.fitLines.append(curveLabel)
                    self.fitLines.append(curveLabel+'.residue')

    def makeMetadataWidget(self):
        self.metadata = qt.QTextEdit(self.splitterPlot)
        self.metadata.setStyleSheet("QTextEdit {border: none;}")
        self.metadata.setReadOnly(True)
        # self.metadata.setContentsMargins(0, 0, 0, 0)
        self.metadata.setMinimumHeight(84)
        self.metadata.setAlignment(qt.Qt.AlignLeft | qt.Qt.AlignTop)
        self.metadata.setText("text metadata here")
        self.metadata.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.metadata.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOn)
        self.metadata.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)

    def getAxisLabels(self):
        plot = self.plot
        if self.node.plotDimension == 1:
            res = [plot.getGraphXLabel(), plot.getGraphYLabel(axis='left'),
                   plot.getGraphYLabel(axis='right')]
            return res
        elif self.node.plotDimension == 2:
            return [plot.getXAxis().getLabel(), plot.getYAxis().getLabel()]
        elif self.node.plotDimension == 3:
            return plot.getLabels()

    def shouldPlotItem(self, item):
        if not self.node.is_between_nodes(
                item.originNodeName, item.terminalNodeName):
            return False
        if item.state[self.node.name] != cco.DATA_STATE_GOOD:
            return False
        if not item.isVisible:
            return False
        return True

    def _storePlotState(self):
        if self.wasNeverPlotted:
            return
        if self.node.plotDimension == 3:
            plot = self.plot._plot
            self.savedPlotProps['browser.value'] = self.plot._browser.value()
        elif self.node.plotDimension == 2:
            plot = self.plot
        elif self.node.plotDimension == 1:
            plot = self.plot
            ylimR = plot.getYAxis(axis='right').getLimits()
            self.savedPlotProps['yaxisR.range'] = ylimR
        else:
            return
        self.savedPlotProps['xaxis.range'] = plot.getXAxis().getLimits()
        self.savedPlotProps['yaxis.range'] = plot.getYAxis().getLimits()

        if self.node.plotDimension in [3, 2]:
            activeImage = self.plot.getActiveImage()
            if activeImage is not None:
                cm = activeImage.getColormap()
                self.savedPlotProps['cm.vmin'] = cm.getVMin()
                self.savedPlotProps['cm.vmax'] = cm.getVMax()

    def _restorePlotState(self):
        if self.wasNeverPlotted:
            return
        if self.node.plotDimension == 3:
            plot = self.plot._plot
            self.plot._browser.setValue(self.savedPlotProps['browser.value'])
        elif self.node.plotDimension == 2:
            plot = self.plot
        elif self.node.plotDimension == 1:
            plot = self.plot
            plot.getYAxis(axis='right').setLimits(
                *self.savedPlotProps['yaxisR.range'])
        else:
            return
        plot.getXAxis().setLimits(*self.savedPlotProps['xaxis.range'])
        plot.getYAxis().setLimits(*self.savedPlotProps['yaxis.range'])

        if self.node.plotDimension in [3, 2]:
            activeImage = self.plot.getActiveImage()
            if activeImage is not None:
                cm = activeImage.getColormap()
                if self.savedPlotProps['cm.vmin'] is not None:
                    cm.setVMin(self.savedPlotProps['cm.vmin'])
                if self.savedPlotProps['cm.vmax'] is not None:
                    cm.setVMax(self.savedPlotProps['cm.vmax'])

    def getCalibration(self, item, axisStr):
        arr = None
        if axisStr == 'x':
            if hasattr(self.node, 'plotXArray'):
                arr = getattr(item, self.node.plotXArray)
        elif axisStr == 'y':
            if hasattr(self.node, 'plotYArrays'):
                arr = getattr(item, self.node.plotYArrays[-1])
        elif axisStr == 'z':
            if hasattr(self.node, 'plotZArray'):
                arr = getattr(item, self.node.plotZArray)
        if arr is not None:
            return arr.min(), (arr.max()-arr.min()) / len(arr)
        else:
            return 0, 1

    @logger(minLevel=50, attrs=[(0, 'node')])
    def replot(self, needClear=False, keepExtent=True, senderName=''):
        if self.onTransform:
            return
        # if len(csi.allLoadedItems) == 0:
        #     return

        node = self.node
        if keepExtent:
            self._storePlotState()
        # self.plot.clear()
        # yUnits = node.get_arrays_prop('plotUnit', yNames)
        # yLabels = node.get_arrays_prop('plotLabel', yNames)

        if node.plotDimension == 1:
            if needClear:
                self.plot.clearCurves()
            self.plot.clearImages()
            # self.plot.clearMarkers()
            nPlottedItems = 0
            leftAxisColumns, rightAxisColumns = [], []
            leftAxisUnits, rightAxisUnits = [], []
            for item in csi.allLoadedItems:
                if not self.shouldPlotItem(item):
                    for yN in node.plotYArrays + self.fitLines:
                        legend = '{0}.{1}'.format(item.alias, yN)
                        self.plot.remove(legend, kind='curve')
                    continue
                try:
                    x = getattr(item, node.plotXArray)
                except AttributeError:
                    continue
                if (csi.nodes[item.originNodeName] is node and
                        'conversionFactors' in item.dataFormat):
                    convs = [cN for (yN, cN) in zip(
                        node.arrays, item.dataFormat['conversionFactors'])
                        if yN in node.plotYArrays]
                else:
                    convs = [None for yN in node.plotYArrays]
                for yN, cN in zip(node.plotYArrays, convs):
                    try:
                        y = getattr(item, yN)
                    except AttributeError:
                        continue
                    if y is None:
                        continue
                    curveLabel = item.alias + '.' + yN
                    curve = self.plot.getCurve(curveLabel)
                    plotProps = dict(item.plotProps[node.name][yN])
                    symbolsize = plotProps.pop('symbolsize', 2)
                    z = 1 if item in csi.selectedItems else 0
                    try:
                        if hasattr(self.transformWidget, 'extraPlotTransform'):
                            x, y = self.transformWidget.extraPlotTransform(
                                item, node.plotXArray, x, yN, y)
                        if curve is None:
                            self.plot.addCurve(
                                x, y, legend=curveLabel, color=item.color, z=z,
                                **plotProps)
                        else:
                            curve.setData(x, y)
                            curve.setZValue(z)
                    except Exception as e:
                        print('plotting in {0} failed for ({1}, len={2}) vs '
                              '({3}, len={4}): {5}'
                              .format(self.node.name, yN, len(y),
                                      node.plotXArray, len(x), e))
                        tb = traceback.format_exc()
                        print(tb)
                        continue
                    nPlottedItems += 1
                    symbol = plotProps.get('symbol', None)
                    if symbol is not None:
                        curve = self.plot.getCurve(curveLabel)
                        if curve is not None:
                            if self.backend['backend'] == 'opengl':
                                # don't know why it is small with opengl
                                symbolsize *= 2
                            curve.setSymbolSize(symbolsize)
                    curve = self.plot.getCurve(curveLabel)
                    if curve is None:
                        continue
                    yaxis = curve.getYAxis()
                    if yaxis == 'left':
                        if yN not in leftAxisColumns:
                            leftAxisColumns.append(yN)
                        if isinstance(cN, type("")):
                            if cN not in leftAxisUnits:
                                leftAxisUnits.append(cN)
                        else:
                            unit = node.get_prop(yN, 'plotUnit')
                            if unit:
                                if unit not in leftAxisUnits:
                                    leftAxisUnits.append(unit)
                    if yaxis == 'right':
                        if yN not in rightAxisColumns:
                            rightAxisColumns.append(yN)
                        if isinstance(cN, type("")):
                            if cN not in rightAxisUnits:
                                rightAxisUnits.append(cN)
                        else:
                            unit = node.get_prop(yN, 'plotUnit')
                            if unit:
                                if unit not in rightAxisUnits:
                                    rightAxisUnits.append(unit)
            self.plot.isRightAxisVisible = len(rightAxisColumns) > 0
            zoomModeAction = self.plot.getInteractiveModeToolBar().\
                getZoomModeAction()
            if hasattr(zoomModeAction, 'setAxesMenuEnabled'):
                zoomModeAction.setAxesMenuEnabled(self.plot.isRightAxisVisible)
            if nPlottedItems == 0:
                self.plot.clearCurves()
                return
            self.plotLeftYLabel = self._makeYLabel(
                leftAxisColumns, leftAxisUnits)
            self.plot.setGraphYLabel(label=self.plotLeftYLabel, axis='left')
            self.plotRightYLabel = self._makeYLabel(
                rightAxisColumns, rightAxisUnits)
            self.plot.setGraphYLabel(label=self.plotRightYLabel, axis='right')
        if node.plotDimension == 2:
            self.plot.clearCurves()
            # if needClear:
            if True:
                self.plot.clearImages()
                # self.plot.clearMarkers()  # clears roi lines, don't add
            if len(csi.selectedItems) > 0:
                item = csi.selectedItems[0]  # it could be the last one but
                # then when going with arrows up and down in the data tree and
                # passing a group that becomes selected, the displayed item
                # jumps between the first and the last
            elif len(csi.allLoadedItems) > 0:
                item = csi.allLoadedItems[-1]
            else:
                return
            if not self.shouldPlotItem(item):
                return
            try:
                image = getattr(item, self.node.plot2DArray)
            except AttributeError as e:
                if not self.wasNeverPlotted:
                    print(e)
                    print(
                        'If you use multiprocessing, check that this array is '
                        'included into *outArrays* list in your transform.')
                return

            xOrigin, xScale = self.getCalibration(item, 'x')
            yOrigin, yScale = self.getCalibration(item, 'y')
            self.plot.addImage(image, colormap=colors.Colormap(COLORMAP),
                               origin=(xOrigin, yOrigin),
                               scale=(xScale, yScale), z=-100)
        if node.plotDimension == 3:
            self.plot._plot.clearCurves()
            # if needClear:
            if True:
                self.plot._plot.clearImages()
                # self.plot._plot.clearMarkers()  # clears roi lines, don't add
            item = None
            if len(csi.selectedItems) > 0:
                item = csi.selectedItems[0]
            elif len(csi.allLoadedItems) > 0:
                item = csi.allLoadedItems[-1]
            else:
                return
            if not self.shouldPlotItem(item):
                return
            try:
                stack = getattr(item, self.node.plot3DArray) if item else None
            except AttributeError as e:
                if not self.wasNeverPlotted:
                    print(e)
                    print(
                        'If you use multiprocessing, check that this array is '
                        'included into *outArrays* list in your transform.')
                return
            if item:
                calibrations = [self.getCalibration(item, ax) for ax in 'xyz']
                self.plot.setStack(stack, calibrations=calibrations)

        if keepExtent:
            self._restorePlotState()

        try:
            if hasattr(self.transformWidget, 'extraPlot'):
                self.transformWidget.extraPlot()
        except Exception as e:
            print('extraPlot in {0} failed: {1}'.format(self.node.name, e))

        # if self.wasNeverPlotted and node.plotDimension == 1:
        #     self.plot.resetZoom()
        self.wasNeverPlotted = False

    @logger(minLevel=50, attrs=[(0, 'node')])
    def replotFit(self, fitWorker, ifit):
        def plotOne(item, x, y, curveLabel, plotProps):
            symbolsize = plotProps.pop('symbolsize', 2)
            curve = self.plot.getCurve(curveLabel)
            z = 1 if item in csi.selectedItems else 0
            try:
                if curve is None:
                    self.plot.addCurve(
                        x, y, legend=curveLabel, color=item.color, z=z,
                        **plotProps)
                else:
                    curve.setData(x, y)
                    curve.setZValue(z)
            except Exception as e:
                print('plotting in {0} failed for ({1}, len={2}) vs '
                      '({3}, len={4}): {5}'
                      .format(node.name, fitAttrName, len(y), xAttrName,
                              len(x), e))
                tb = traceback.format_exc()
                print(tb)
                return
            symbol = plotProps.get('symbol', None)
            if symbol is not None:
                curve = self.plot.getCurve(curveLabel)
                if curve is not None:
                    if self.backend['backend'] == 'opengl':
                        # don't know why it is small with opengl
                        symbolsize *= 2
                    curve.setSymbolSize(symbolsize)

        node = self.node
        xAttrName, yAttrName, fitAttrName = [
            fitWorker.dataAttrs[a] for a in ('x', 'y', 'fit')]
        fitSizes = self.splitterPlot.sizes()[1:-1]
        assert len(fitSizes) == len(self.fitWidgets)

        if node.plotDimension == 1:
            plotProps = fitWorker.plotParams['fit']
            residueProps = fitWorker.plotParams['residue']
            for item in csi.allLoadedItems:
                curveLabel = item.alias + '.' + fitAttrName
                residueLabel = curveLabel + '.residue'
                if not self.shouldPlotItem(item) or fitSizes[ifit] == 0:
                    self.plot.remove(curveLabel, kind='curve')
                    self.plot.remove(residueLabel, kind='curve')
                    continue
                try:
                    x = getattr(item, xAttrName)
                    y = getattr(item, yAttrName)
                    fity = getattr(item, fitAttrName)
                except AttributeError:
                    continue
                plotOne(item, x, fity, curveLabel, dict(plotProps))
                if fity.any():  # any non-zero
                    plotOne(item, x, y-fity, residueLabel, dict(residueProps))
        else:
            raise NotImplementedError('fit plot not implemented for dim={0}'
                                      .format(node.plotDimension))

    def saveGraph(self, fname, i, name):
        if fname.endswith('.pspj'):
            fname = fname.replace('.pspj', '')
        fname += '-{0}-{1}.png'.format(i+1, name)
        if self.node.plotDimension in [1, 2]:
            if len(self.plot.getItems()) == 0:
                return
            self.plot.saveGraph(fname)
        elif self.node.plotDimension in [3]:
            if len(self.plot.getPlotWidget().getItems()) == 0:
                return
            self.plot._plot.saveGraph(fname)

    def _makeYLabel(self, yNames, yUnits):
        if not yNames:
            return ""
        yLabels = self.node.get_arrays_prop('plotLabel', yNames)
        axisLabel = ", ".join(yLabels)
        axisUnit = ", ".join(yUnits)
        if len(axisUnit) > 0:
            axisLabel += u" ({0})".format(axisUnit)
        return axisLabel

    def updatePlot(self):  # bring the selected curves to the top
        node = self.node
        if node.plotDimension == 1:
            for item in csi.selectedItems:
                if not node.is_between_nodes(
                        item.originNodeName, item.terminalNodeName):
                    continue
                for col, yN in enumerate(node.plotYArrays):
                    curveLabel = item.alias + '.' + yN
                    curve = self.plot.getCurve(curveLabel)
                    if curve is not None:
                        curve._updated()

    def preparePickData(self, pendingPropDialog):
        self.pendingPropDialog = pendingPropDialog
        self.pickWidget.setVisible(True)
        self.tree.setCustomSelectionMode(0)  # ignore gui updates on picking

    def cancelPropsToPickedData(self):
        self.pendingPropDialog = None
        self.pickWidget.setVisible(False)
        self.tree.setCustomSelectionMode()

    def applyPropsToPickedData(self):
        if self.pendingPropDialog is not None:
            self.pendingPropDialog.applyPendingProps()
            self.pendingPropDialog = None
        self.pickWidget.setVisible(False)
        self.selChanged()
        self.tree.setCustomSelectionMode()

    def selChanged(self):
        if not self.pickWidget.isVisible() and \
                csi.selectionModel.customSelectionMode:
            self.updateNodeForSelectedItems()
        if csi.DEBUG_LEVEL > 0 and self.mainWindow is None:  # for test purpose
            selNames = ', '.join([it.alias for it in csi.selectedItems])
            dataCount = len(csi.allLoadedItems)
            self.setWindowTitle('{0} total; {1}'.format(dataCount, selNames))

    def updateNodeForSelectedItems(self):
        self.updateSplittersForSelectedItems()
        fname = self.shouldUpdateFileModel()
        if fname:
            self.files.gotoWhenReady(fname)
            self.columnFormat.setUIFromData()

        self.updateMeta()
        self.combiner.setUIFromData()
        self.updateTransforms()
        self.updateFits()

    def shouldUpdateFileModel(self):
        for it in csi.selectedItems:
            if it.dataType in (cco.DATA_COLUMN_FILE, cco.DATA_DATASET) and\
                    csi.nodes[it.originNodeName] is self.node:
                return it.madeOf

    def loadFiles(self, fileNamesFull=None, parentItem=None, insertAt=None,
                  concatenate=False):
        def times(n):
            return " ({0} times)".format(n) if n > 1 else ""

        selectedIndexes = self.files.selectionModel().selectedRows()
        if len(selectedIndexes) == 0:
            return
        selectedIndex = selectedIndexes[0]
        dataStruct = selectedIndex.data(gft.LOAD_DATASET_ROLE)
        if dataStruct is None:
            return
        colRecs, df = dataStruct

        # spectraInOneFile = 1
        # for col in colRecs:  # col is a list of (expr, d[xx]-expr, data-keys)
        #     spectraInOneFile = max(spectraInOneFile, len(col))
        # if spectraInOneFile > 1:
        #     colMany = []
        #     for icol, col in enumerate(colRecs):
        #         if len(col) not in [1, spectraInOneFile]:
        #             msg = qt.QMessageBox()
        #             msg.setIcon(qt.QMessageBox.Question)
        #             res = msg.critical(
        #                 self, "Cannot load data",
        #                 "Lists of different lengths found")
        #             return
        #         if len(col) == spectraInOneFile:
        #             colMany.append(icol)
        #     if not colMany:
        #         return

        fileNamesFull = self.files.getFullFileNames(fileNamesFull)
        if fileNamesFull is None:  # when isDir
            return
        fileNames = [osp.normcase(nf) for nf in fileNamesFull]
        allLoadedItemNames = []
        for d in csi.allLoadedItems:
            if isinstance(d.madeOf, str):
                ln = d.madeOf[5:] if d.madeOf.startswith('silx:') else d.madeOf
                nln = osp.normcase(osp.abspath(ln))
                if d.madeOf.startswith('silx:'):
                    nln = 'silx:' + nln
                allLoadedItemNames.append(nln)
            else:
                allLoadedItemNames.append(str(d))
        allLoadedItemsCount = Counter(allLoadedItemNames)
        duplicates, duplicatesN = [], []
        fileNamesFullN = []
        for fname, fnameFull in zip(fileNames, fileNamesFull):
            n = allLoadedItemsCount[osp.normcase(fnameFull)]
            if n > 0:
                duplicates.append(fnameFull)
                duplicatesN.append(n)
            fileNamesFullN.append(n)
        if duplicates:
            duplicatesNStr =\
                [dup + times(n) for dup, n in zip(duplicates, duplicatesN)]
            st1, st2, st3, st4 =\
                ('This', '', 'is', 'it') if len(duplicates) == 1 else\
                ('These', 's', 'are', 'them')
            msg = qt.QMessageBox()
            msg.setIcon(qt.QMessageBox.Question)
            res = msg.question(self, "Already in the data list",
                               "{0} file{1} {2} already loaded:\n{3}".format(
                                   st1, st2, st3, '\n'.join(duplicatesNStr)) +
                               "\nDo you want to load {0} gain?".format(st4),
                               qt.QMessageBox.Yes | qt.QMessageBox.No,
                               qt.QMessageBox.Yes)
            if res == qt.QMessageBox.No:
                return

        if parentItem is None:
            if csi.selectedItems:
                parentItem = csi.selectedItems[0].parentItem
            else:
                parentItem = csi.dataRootItem

        # df['dataSource'] = [col[0][0] for col in colRecs]
        csi.model.importData(
            fileNamesFull, parentItem, insertAt, dataFormat=df,
            originNodeName=self.node.name, concatenate=concatenate)

    def shouldShowColumnDialog(self):
        for it in csi.selectedItems:
            if it.dataType in (cco.DATA_COLUMN_FILE, cco.DATA_DATASET) and\
                    csi.nodes[it.originNodeName] is self.node:
                return True
        return False

    def updateSplittersForSelectedItems(self):
        showColumnDialog = self.shouldShowColumnDialog()
        self.splitterFiles.setSizes([1, int(showColumnDialog)])

    def updateMeta(self):
        try:
            cs = csi.selectedItems[0].meta['text']
        except (IndexError, KeyError):
            return
        for item in csi.selectedItems[1:]:
            cs = cco.common_substring((cs, item.meta['text']))
        self.metadata.setText(cs)

    def updateTransforms(self):
        if len(csi.selectedItems) < 1:
            return
        dataType = csi.selectedItems[0].dataType
        for data in csi.selectedItems:
            if dataType != data.dataType:
                dataType = None
                break
        if (dataType == cco.DATA_COMBINATION and
            not self.node.is_between_nodes(
                data.originNodeName, data.terminalNodeName,
                node1in=False)):
            self.transformWidget.setEnabled(False)
        else:
            self.transformWidget.setEnabled(True)
            # in tests, transformWidget is a QWidget instance:
            if hasattr(self.transformWidget, 'setUIFromData'):
                self.transformWidget.setUIFromData()

    def updateFits(self, shouldClear=False):
        if len(csi.selectedItems) < 1:
            return
        fitSizes = self.splitterPlot.sizes()[1:-1]
        assert len(fitSizes) == len(self.fitWidgets)
        for fitWidget, fitSize in zip(self.fitWidgets, fitSizes):
            if fitSize > 0 or shouldClear:
                fitWidget.setSpectrum(csi.selectedItems[0])
            if shouldClear:
                roi = fitWidget.rangeWidget.roi
                if roi is not None:
                    roi.blockSignals(True)
                    roi.setVisible(fitSize > 0)
                    roi.blockSignals(False)

    def linkClicked(self, url):
        strURL = str(url.toString())
        if strURL.startswith('http') or strURL.startswith('ftp'):
            if self.lastBrowserLink == strURL:
                return
            webbrowser.open(strURL)
            self.lastBrowserLink = strURL

    def autoLoadChangeEnabled(self, enabled):
        if not enabled:
            self.autoLoadToggled(False)
            self.autoPanel.setChecked(False)
        self.autoPanel.setEnabled(enabled)

    def autoLoadToggled(self, on):
        if on:
            self.autoFileExt = None
            if reversed(csi.recentlyLoadedItems):
                for item in csi.recentlyLoadedItems:
                    if isinstance(item.madeOf, type("")):
                        self.autoFileExt = osp.splitext(item.madeOf)[1]
                        break
            if self.autoFileExt is None:
                if hasattr(self.node, 'includeFilters'):
                    self.autoFileExt = self.node.includeFilters[0]
            if self.autoFileExt is None:
                self.autoFileExt = ''
            self.activateAutoLoad()
        else:
            if self.autoLoadTimer is not None:
                self.autoLoadTimer.stop()
            self.autoFileList = []
            self.autoDirName = ''
            self.autoChunk = 1
            self.autoIndex = 0

    def autoLoadEveryChanged(self, val):
        if 11 <= (val % 100) <= 13:
            suffix = 'th'
        else:
            suffix = ['th', 'st', 'nd', 'rd', 'th'][min(val % 10, 4)]
        self.filesAutoLoadEvery.setSuffix(suffix)
        if val < 20:
            step = 1
        if 20 <= val < 100:
            step = 10
        if 100 <= val:
            step = 100
        self.filesAutoLoadEvery.setSingleStep(step)
        self.activateAutoLoad()

    def activateAutoLoad(self):
        self.autoChunk = self.filesAutoLoadEvery.value()
        self.autoIndex = 0
        self.autoDirName, self.autoFileList = self.files.getActiveDir()
        # self.fileSystemWatcher.removePath(self.autoDirName)
        # self.fileSystemWatcher.addPath(self.autoDirName)
        # self.fileSystemWatcher.directoryChanged.connect(self.dirChanged)
        self.autoLoadTimer = qt.QTimer(self)
        self.autoLoadTimer.timeout.connect(self.doAutoLoad)
        self.autoLoadTimer.start(autoLoadDelay)
        # print('activateAutoLoad', self.autoDirName, self.autoFileList)

    def doAutoLoad(self):
        if self.autoDirName.startswith('silx:'):
            model = self.files.getSourceModel()
            if self.autoDirName.endswith('::/'):
                ind = model.indexFileName(self.autoDirName[5:-3])
            else:
                ind = model.indexFromH5Path(self.autoDirName)
            model.reloadHdf5(ind)
            # self.files.synchronizeHDF5Index(ind)

        # this first solution doesn't work in NFS in Linux:
        # newFileList = self.files.getActiveDir(self.autoDirName)

        dirname = str(self.autoDirName)
        if not dirname.endswith('/'):
            dirname += '/'
        newFileList = [p.replace('\\', '/') for p in
                       glob.glob(dirname + '*' + self.autoFileExt)]

        diffs = [x for x in newFileList if x not in list(self.autoFileList)]
        print('auto', self.autoDirName, diffs, self.autoIndex, self.autoChunk)
        if len(diffs) > 0:
            toLoad = [diff for i, diff in enumerate(diffs) if
                      (i+self.autoIndex) % self.autoChunk == self.autoChunk-1]
            self.autoIndex += len(diffs)
            self.autoFileList = newFileList
            if toLoad:
                self.loadFiles(toLoad)
