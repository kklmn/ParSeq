# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "23 Jul 2021"
# !!! SEE CODERULES.TXT !!!

import sys
import os.path as osp
import webbrowser
from collections import Counter
from functools import partial

from silx.gui import qt, colors

from ..core import singletons as csi
from ..core import commons as cco
from ..core import spectra as csp
from ..gui import fileTreeModelView as gft
from ..gui.fileTreeModelView import FileTreeView
from ..gui.dataTreeModelView import DataTreeView
from ..gui.plot import Plot1D, Plot2D, Plot3D
from ..gui.webWidget import QWebView
from ..gui.columnFormatWidget import ColumnFormatWidget
from ..gui.combineSpectraWidget import CombineSpectraWidget

SPLITTER_WIDTH, SPLITTER_BUTTON_MARGIN = 13, 6
COLORMAP = 'viridis'


class QSplitterButton(qt.QPushButton):
    def __init__(self, text, parent, isVertical=False,
                 margin=SPLITTER_BUTTON_MARGIN):
        super(QSplitterButton, self).__init__(text, parent)
        self.rawText = str(text)
        self.isVertical = isVertical
        fontSize = "10" if sys.platform == "darwin" else "7"
        grad = "x1: 0, y1: 0, x2: 0, y2: 1"
        self.setStyleSheet("""
            QPushButton {
                font-size: """ + fontSize + """pt; color: #151575;
                padding-bottom: 0px; padding-top: -1px;
                text-align: bottom; border-radius: 4px;
                background-color: qlineargradient(
                """ + grad + """, stop: 0 #e6e7ea, stop: 1 #cacbce);}
            QPushButton:pressed {
                background-color: qlineargradient(
                """ + grad + """, stop: 0 #cacbce, stop: 1 #e6e7ea);} """)
        myFont = qt.QFont()
        myFont.setPointSize(int(float(fontSize)))
        fm = qt.QFontMetrics(myFont)
        width = fm.width(text) + 2*margin
        if isVertical:
            self.setFixedSize(SPLITTER_WIDTH+1, width)
        else:
            self.setFixedSize(width, SPLITTER_WIDTH+1)

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
    def __init__(self, node, parent=None):
        super(NodeWidget, self).__init__(parent)
        self.mainWindow = parent
#        self.setContentsMargins(0, 0, 0, 0)
        self.node = node
        self.helpFile = ''
        node.widget = self
        self.pendingPropDialog = None
        self.pendingFile = None
        self.wasNeverPlotted = True
        self.onTransform = False

        self.makeSplitters()

        self.fillSplitterFiles()
        self.fillSplitterData()
        self.fillSplitterPlot()
        self.makeTransformWidget(self.splitterTransform)
        self.fillSplitterTransform()
        self.makeSplitterButtons()
        self.splitter.setStretchFactor(0, 0.1)
        self.splitter.setStretchFactor(1, 0.1)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setStretchFactor(3, 0.1)

        # if not osp.exists(self.helpFile):
        if True:
            self.splitterTransform.setSizes([1, 0])
        self.splitterButtons['files && containers'].clicked.emit()
        self.splitterButtons['transform'].clicked.emit()

        # self.splitter.setSizes([1, 1, 1, 1])  # set in MainWindowParSeq
        if len(csi.selectedItems) > 0:
            self.updateNodeForSelectedItems()
            self.replot()

        if node.plotDimension is None:
            self.dimIcon = qt.QIcon()
        elif node.plotDimension < 4:
            name = 'icon-item-{0}dim'.format(node.plotDimension)
        else:
            name = 'icon-item-ndim'
        self.iconDir = osp.join(osp.dirname(__file__), '_images')
        self.dimIcon = qt.QIcon(osp.join(self.iconDir, name+'.png'))

    def makeSplitters(self):
        layout = qt.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = qt.QSplitter(self)
        self.splitter.setOrientation(qt.Qt.Horizontal)
        layout.addWidget(self.splitter)
        self.setLayout(layout)

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
        labelFilter = qt.QLabel('file filter')
        self.editFileFilter = qt.QLineEdit()
        self.editFileFilter.returnPressed.connect(self.setFileFilter)
        if hasattr(self.node, 'fileNameFilters'):
            self.editFileFilter.setText(', '.join(self.node.fileNameFilters))
        self.files = FileTreeView(self.node)
#        self.files.doubleClicked.connect(self.loadFiles)
        self.files.model().directoryLoaded.connect(self._directoryIsLoaded)
        self.filesAutoAddCB = qt.QCheckBox("auto append fresh file TODO", self)

        fileFilterLayout = qt.QHBoxLayout()
        fileFilterLayout.addWidget(labelFilter)
        fileFilterLayout.addWidget(self.editFileFilter, 1)

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(2, 0, 0, 0)
        layout.addLayout(fileFilterLayout)
        layout.addWidget(self.files)
        layout.addWidget(self.filesAutoAddCB)
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
        cancelPick.clicked.connect(self.cancelPropsToPickedData)
        applyPick = qt.QPushButton('Apply')
        applyPick.setStyleSheet("QPushButton {background-color: lightgreen;}")
        applyPick.clicked.connect(self.applyPropsToPickedData)

        pickLayout = qt.QHBoxLayout()
        pickLayout.setContentsMargins(0, 0, 0, 0)
        pickLayout.addWidget(labelPick)
        pickLayout.addWidget(cancelPick, 0.5)
        pickLayout.addWidget(applyPick, 0.5)
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
        node = self.node
        # self.backend = dict(backend='opengl')
        self.backend = dict(backend='matplotlib')

        if node.plotDimension == 3:
            self.plot = Plot3D(
                self.splitterPlot, position=Plot3D.posInfo, **self.backend
                )
            self.plot.setCustomPosInfo()
        elif node.plotDimension == 2:
            self.plot = Plot2D(
                self.splitterPlot, **self.backend
                )
        elif node.plotDimension == 1:
            xLbl = node.getPropList('qLabel', role='x')[0]
            yLbl = node.getPropList('qLabel', role='y')[0]
            self.plot = Plot1D(
                self.splitterPlot,
                position=[(xLbl, lambda x, y: x), (yLbl, lambda x, y: y)],
                **self.backend
                )
            self.plot.getXAxis().setLabel(xLbl)
            self.plot.getYAxis().setLabel(yLbl)
        else:
            raise ValueError("wrong plot dimension")
        self.plotSetup()
        self.savedPlotProps = {}

        self.metadata = qt.QTextEdit(self.splitterPlot)
        self.metadata.setStyleSheet("QTextEdit {border: none;}")
        self.metadata.setReadOnly(True)
#        self.metadata.setContentsMargins(0, 0, 0, 0)
        self.metadata.setMinimumHeight(80)
        self.metadata.setAlignment(qt.Qt.AlignLeft | qt.Qt.AlignTop)
        self.metadata.setText("text metadata here")
        self.metadata.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.metadata.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOn)
        self.metadata.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Expanding)

        self.splitterPlot.setCollapsible(0, False)
        self.splitterPlot.setStretchFactor(0, 1)  # don't remove
        self.splitterPlot.setStretchFactor(1, 0)
        self.splitterPlot.setSizes([1, 1])

    def fillSplitterTransform(self):
        self.help = QWebView(self.splitterTransform)
        # self.help.setHtml('no documentation available')
        self.help.setMinimumSize(qt.QSize(200, 200))
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
        tr = self.node.transformIn
        tr.sendSignals = csi.mainWindow is not None
        hasWidgetClass = tr is not None
        if hasWidgetClass:
            hasWidgetClass = tr.widgetClass is not None
        if hasWidgetClass:
            self.transformWidget = tr.widgetClass(
                parent=parent, node=self.node, transform=tr)
        else:
            self.transformWidget = qt.QWidget(parent)
        if tr is not None:
            tr.widget = self.transformWidget

    def makeSplitterButtons(self):
        "Orientation should be given for the closed state."
        self.splitterButtons = {}
        self.makeSplitterButton('files && containers', self.splitter, 1, 0)
        self.makeSplitterButton('data', self.splitter, 2, 1)
        self.makeSplitterButton('transform', self.splitter, 3, 3)
        self.makeSplitterButton('data format', self.splitterFiles, 1, 1)
        self.makeSplitterButton('combine', self.splitterData, 1, 1)
        self.makeSplitterButton('meta', self.splitterPlot, 1, 1)
        self.makeSplitterButton('help', self.splitterTransform, 1, 1)
        self.makeSplitterHelpButton(self.splitterTransform, 1)

    def makeSplitterButton(self, name, splitter, indHandle, indSizes):
        handle = splitter.handle(indHandle)
        if handle is None:
            return
        isVerical = splitter.orientation() == qt.Qt.Horizontal
        if name == 'transform' and self.node.transformIn is not None:
            nameBut = name + ': ' + self.node.transformIn.name
        else:
            nameBut = name
        button = QSplitterButton(nameBut, handle, isVerical)
        button.setText(button.rawText)
        splitter.setHandleWidth(SPLITTER_WIDTH)
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

    def handleSplitterHelpButton(self):
        webbrowser.open_new_tab(self.helpFile)
        # webbrowser.open_new_tab("https://github.com/")

    def setFileFilter(self):
        txt = self.editFileFilter.text()
        if not txt:
            return
        lst = txt.split(',')
        if hasattr(self.node, 'fileNameFilters'):
            if lst == self.node.fileNameFilters:
                return
        self.files.setCurrentIndex(qt.QModelIndex())
        self.node.fileNameFilters = lst
        self.files.model().fsModel.setNameFilters(lst)

    def _makeAxisLabels(self, labels):
        node = self.node
        res = []
        for label in labels:
            if label in node.arrays:
                unit = node.getProp(label, 'plotUnit')
                sUnit = u" ({0})".format(unit) if unit else ""
                ll = "{0}{1}".format(node.getProp(label, 'plotLabel'), sUnit)
                res.append(ll)
            else:
                res.append(label)
        return res

    def plotSetup(self):
        node = self.node
        if node.plotDimension == 1:
            try:
                unit = node.getPropList('plotUnit', role='x')[0]
                strUnit = u" ({0})".format(unit) if unit else ""
            except AttributeError:
                strUnit = ''
            self.plotXLabel = u"{0}{1}".format(
                node.getProp(node.plotXArray, 'plotLabel'), strUnit)
            self.plot.setGraphXLabel(label=self.plotXLabel)
        elif node.plotDimension == 2:
            labels = node.getProp(node.plot2DArray, 'plotLabel')
            axisLabels = self._makeAxisLabels(labels)
            self.plot.getXAxis().setLabel(axisLabels[0])
            self.plot.getYAxis().setLabel(axisLabels[1])
        elif node.plotDimension == 3:
            self.plot.setColormap(COLORMAP)
            labels = node.getProp(node.plot3DArray, 'plotLabel')
            axisLabels = self._makeAxisLabels(labels)
            self.plot.setLabels(axisLabels)

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
        if not self.node.is_between_nodes(item.originNode, item.terminalNode,
                                          node1in=True, node2in=True):
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
            self.savedPlotProps['browser.value'] = self.plot._browser.value()
            xlim = self.plot._plot.getXAxis().getLimits()
            ylim = self.plot._plot.getYAxis().getLimits()
        elif self.node.plotDimension in [1, 2]:
            xlim = self.plot.getXAxis().getLimits()
            ylim = self.plot.getYAxis().getLimits()
            if self.node.plotDimension == 1:
                ylimR = self.plot.getYAxis(axis='right').getLimits()
                self.savedPlotProps['yaxisR.range'] = ylimR
        else:
            return
        self.savedPlotProps['xaxis.range'] = xlim
        self.savedPlotProps['yaxis.range'] = ylim

    def _restorePlotState(self):
        if self.wasNeverPlotted:
            return
        if self.node.plotDimension == 3:
            self.plot._browser.setValue(self.savedPlotProps['browser.value'])
            self.plot._plot.getXAxis().setLimits(
                *self.savedPlotProps['xaxis.range'])
            self.plot._plot.getYAxis().setLimits(
                *self.savedPlotProps['yaxis.range'])
        elif self.node.plotDimension in [1, 2]:
            self.plot.getXAxis().setLimits(*self.savedPlotProps['xaxis.range'])
            self.plot.getYAxis().setLimits(*self.savedPlotProps['yaxis.range'])
            if self.node.plotDimension == 1:
                self.plot.getYAxis(axis='right').setLimits(
                    *self.savedPlotProps['yaxisR.range'])

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

    def replot(self, keepExtent=True):
        if csi.DEBUG_LEVEL > 50:
            print('enter replot() of {0}'.format(self.node.name))

        if self.onTransform:
            return
        if len(csi.allLoadedItems) == 0:
            return

        node = self.node
        if keepExtent:
            self._storePlotState()
        # # self.plot.clear()
        # yUnits = node.getPropList('plotUnit', keys=yNames)
        # yLabels = node.getPropList('plotLabel', keys=yNames)

        if node.plotDimension == 1:
            self.plot.clearCurves()
            self.plot.clearImages()
            nPlottedItems = 0
            leftAxisColumns, rightAxisColumns = [], []
            leftAxisUnits, rightAxisUnits = [], []
            for item in csi.allLoadedItems:
                if not self.shouldPlotItem(item):
                    continue
                try:
                    x = getattr(item, node.plotXArray)
                except AttributeError:
                    continue
                if item.originNode is node:
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
                    curveLabel = item.alias + '.' + yN
                    plotProps = dict(item.plotProps[node.name][yN])
                    symbolsize = plotProps.pop('symbolsize', 2)
                    z = 1 if item in csi.selectedItems else 0
                    self.plot.addCurve(
                        x, y, legend=curveLabel, color=item.color, z=z,
                        **plotProps)
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
                            unit = node.getProp(yN, 'plotUnit')
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
                            unit = node.getProp(yN, 'plotUnit')
                            if unit:
                                if unit not in rightAxisUnits:
                                    rightAxisUnits.append(unit)
            if nPlottedItems == 0:
                return
            self.plotLeftYLabel = self._makeYLabel(
                leftAxisColumns, leftAxisUnits)
            self.plot.setGraphYLabel(label=self.plotLeftYLabel, axis='left')
            self.plotRightYLabel = self._makeYLabel(
                rightAxisColumns, rightAxisUnits)
            self.plot.setGraphYLabel(label=self.plotRightYLabel, axis='right')
        if node.plotDimension == 2:
            self.plot.clearCurves()
            self.plot.clearImages()
            if len(csi.selectedItems) > 0:
                item = csi.selectedItems[0]  # it could be the last one but
                # then when goint with arrows up and down in the data tree and
                # passing a group that becomes selected, the displayed item
                # jumps between the first and the last
            elif len(csi.allLoadedItems) > 0:
                item = csi.allLoadedItems[-1]
            else:
                return
            try:
                image = getattr(item, self.node.plot2DArray)
            except AttributeError:
                return

            xOrigin, xScale = self.getCalibration(item, 'x')
            yOrigin, yScale = self.getCalibration(item, 'y')
            self.plot.addImage(image, colormap=colors.Colormap(COLORMAP),
                               origin=(xOrigin, yOrigin),
                               scale=(xScale, yScale))
        if node.plotDimension == 3:
            self.plot._plot.clearImages()
            item = None
            if len(csi.selectedItems) > 0:
                item = csi.selectedItems[0]
            elif len(csi.allLoadedItems) > 0:
                item = csi.allLoadedItems[-1]
            else:
                return
            try:
                stack = getattr(item, self.node.plot3DArray) if item else None
            except AttributeError:
                return
            if item:
                calibrations = [self.getCalibration(item, ax) for ax in 'xyz']
                self.plot.setStack(stack, calibrations=calibrations)

        if keepExtent:
            self._restorePlotState()

        if hasattr(self.transformWidget, 'extraPlot'):
            self.transformWidget.extraPlot()
        # if self.wasNeverPlotted and node.plotDimension == 1:
        #     self.plot.resetZoom()
        self.wasNeverPlotted = False
        if csi.DEBUG_LEVEL > 50:
            print('exit replot() of {0}'.format(self.node.name))

    def saveGraph(self, fname, i, name):
        if fname.endswith('.pspj'):
            fname = fname.replace('.pspj', '')
        fname += '-{0}-{1}.png'.format(i+1, name)
        if self.node.plotDimension in [1, 2]:
            self.plot.saveGraph(fname)
        elif self.node.plotDimension in [3]:
            self.plot._plot.saveGraph(fname)

    def _makeYLabel(self, yNames, yUnits):
        if not yNames:
            return ""
        yLabels = self.node.getPropList('plotLabel', keys=yNames)
        axisLabel = u""
        spacer = u""
        for yLabel in yLabels:
            if yLabel not in axisLabel:
                axisLabel += spacer + yLabel
                spacer = u", "
        spacer = u""
        axisUnit = u""
        for yUnit in yUnits:
            if yUnit not in axisUnit:
                axisUnit += spacer + yUnit
                spacer = u", "
        if len(axisUnit) > 0:
            axisLabel += u" ({0})".format(axisUnit)
        return axisLabel

    def updatePlot(self):  # bring the selected curves to the top
        node = self.node
        if node.plotDimension == 1:
            for item in csi.selectedItems:
                if not node.is_between_nodes(
                    item.originNode, item.terminalNode,
                        node1in=True, node2in=True):
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

    def _directoryIsLoaded(self, path):
        if self.pendingFile:
            fname = osp.normcase(self.pendingFile[0])
            if fname.startswith('silx:'):
                fname = fname[5:]
            indSuff = fname.rfind('::')
            if indSuff > 0:
                fname = fname[:indSuff]
            if fname == osp.normcase(path):
                if self.pendingFile[1] == csp.DATA_COLUMN_FILE:
                    ind = self.files.model().indexFileName(self.pendingFile[0])
                else:  # csp.DATA_DATASET:
                    ind = self.files.model().indexFromH5Path(
                        self.pendingFile[0], True)
                # self.files.scrollTo(ind, qt.QAbstractItemView.EnsureVisible)
                self.files.scrollTo(ind, qt.QAbstractItemView.PositionAtCenter)
                self.files.setCurrentIndex(ind)
                self.files.selectionModel().select(
                    ind, qt.QItemSelectionModel.ClearAndSelect)
                self.pendingFile = None

    def updateNodeForSelectedItems(self):
        self.updateSplittersForSelectedItems()
        fobj = self.shouldUpdateFileModel()
        if fobj:
            self.pendingFile = fobj
            if fobj[1] == csp.DATA_COLUMN_FILE:
                ind = self.files.model().indexFileName(fobj[0])
            else:  # fobj[1] == csp.DATA_DATASET:
                ind = self.files.model().indexFromH5Path(fobj[0], True)
            self.files.setCurrentIndex(ind)
            # self.files.scrollTo(ind, qt.QAbstractItemView.PositionAtCenter)
            self.files.scrollTo(ind, qt.QAbstractItemView.PositionAtTop)
            self.files.dataChanged(ind, ind)
        self.updateMeta()
        if fobj:
            self.columnFormat.setUIFromData()
        self.combiner.setUIFromData()
        self.updateTransforms()

    def shouldUpdateFileModel(self):
        for it in csi.selectedItems:
            if it.dataType in (csp.DATA_COLUMN_FILE, csp.DATA_DATASET) and\
                    it.originNode is self.node:
                return it.madeOf, it.dataType

    def loadFiles(self, fileNamesFull=None, parentItem=None, insertAt=None):
        def times(n):
            return " ({0} times)".format(n) if n > 1 else ""

        selectedIndexes = self.files.selectionModel().selectedRows()
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

        if isinstance(fileNamesFull, qt.QModelIndex):
            if qt.QFileInfo(
                    self.files.model().filePath(fileNamesFull)).isDir():
                return
            fileNamesFull = None
        if not fileNamesFull:
            sIndexes = self.files.selectionModel().selectedRows()
            nodeType = self.files.model().nodeType(sIndexes[0])
            if nodeType == gft.NODE_FS:
                fileNamesFull = \
                    [self.files.model().filePath(i) for i in sIndexes]
            else:  # FileTreeView.NODE_HDF5, FileTreeView.NODE_HDF5_HEAD
                fileNamesFull = \
                    [self.files.model().getHDF5FullPath(i) for i in sIndexes]

        fileNames = [osp.normcase(nf) for nf in fileNamesFull]
        allLoadedItemNames = []
        for d in csi.allLoadedItems:
            lfn = d.madeOf[5:] if d.madeOf.startswith('silx:') else d.madeOf
            lfns = osp.normcase(osp.abspath(lfn))
            if d.madeOf.startswith('silx:'):
                lfns = 'silx:' + lfns
            allLoadedItemNames.append(lfns)
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

        # !!! TODO !!!
        # here the column format is taken from the present state of
        # ColumnFormatWidget. Should be automatically detected from
        # file format

        # df['dataSource'] = [col[0][0] for col in colRecs]
        items = csi.model.importData(
            fileNamesFull, parentItem, insertAt, dataFormat=df,
            originNode=self.node)

        # if spectraInOneFile == 1:
        #     df['dataSource'] = [col[0][0] for col in colRecs]
        #     items = csi.model.importData(
        #         fileNamesFull, parentItem, insertAt, dataFormat=df,
        #         originNode=self.node)
        # else:
        #     keys = [col[2][0] for col in colRecs[colMany[0]]]
        #     cs = keys[0]
        #     for key in keys[1:]:
        #         cs = cco.common_substring(cs, key)
        #     colNames = [key[len(cs):] for key in keys]
        #     for fname in fileNamesFull:
        #         basename = osp.basename(fname)
        #         groupName = osp.splitext(basename)[0]
        #         if '::' in fname:
        #             h5name = osp.splitext(osp.basename(
        #                 fname[:fname.find('::')]))[0]
        #             groupName = '/'.join([h5name, groupName])
        #         group, = csi.model.importData(groupName, parentItem, insertAt)
        #         for i, colName in enumerate(colNames):
        #             df['dataSource'] = \
        #                 [col[i][0] if len(col) > 1 else col[0][0]
        #                  for col in colRecs]
        #             csi.model.importData(
        #                 fname, group, dataFormat=df,
        #                 alias='{0}_{1}'.format(groupName, colName),
        #                 originNode=self.node)
        #     items = group,

        mode = qt.QItemSelectionModel.Select | qt.QItemSelectionModel.Rows
        for item in items:
            row = item.row()
            index = csi.model.createIndex(row, 0, item)
            csi.selectionModel.select(index, mode)

    def shouldShowColumnDialog(self):
        for it in csi.selectedItems:
            if it.dataType in (csp.DATA_COLUMN_FILE, csp.DATA_DATASET) and\
                    it.originNode is self.node:
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
            cs = cco.common_substring(cs, item.meta['text'])
        self.metadata.setText(cs)

    def updateTransforms(self):
        # try:
        if hasattr(self.transformWidget, 'setUIFromData'):
            self.transformWidget.setUIFromData()
        # except AttributeError:  # when transformWidget is QWidget
        #     pass

    def linkClicked(self, url):
        strURL = str(url.toString())
        if strURL.startswith('http') or strURL.startswith('ftp'):
            if self.lastBrowserLink == strURL:
                return
            webbrowser.open(strURL)
            self.lastBrowserLink = strURL
