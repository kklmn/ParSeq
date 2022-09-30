# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Jul 2022"
# !!! SEE CODERULES.TXT !!!

import sys
import os.path as osp
import webbrowser
from collections import Counter
from functools import partial

from silx.gui import qt, colors, icons

from ..core import singletons as csi
from ..core import commons as cco
# from ..core import spectra as csp
from ..core.config import configLoad
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


class QSplitterButton(qt.QPushButton):
    def __init__(self, text, parent, isVertical=False,
                 margin=SPLITTER_BUTTON_MARGIN):
        super().__init__(text, parent)
        self.rawText = str(text)
        self.isVertical = isVertical
        fontSize = "10" if sys.platform == "darwin" else "7.7"
        grad = "x1: 0, y1: 0, x2: 0, y2: 1"
        self.setStyleSheet("""
            QPushButton {
                font-size: """ + fontSize + """pt; color: #151575;
                text-align: bottom; border-radius: 6px;
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
        grad = "x1: 0, y1: 0, x2: 0, y2: 1"
        self.splitter.setStyleSheet(
            "QSplitterHandle:hover {} "
            "QSplitter::handle:horizontal:hover{background-color: "
            "qlineargradient(" + grad + ", stop: 0 #6087cefa, "
            "stop: 1 #7097eeff);}")

        self.splitter.setStyleSheet(
            "QSplitterHandle:hover {} "
            "QSplitter::handle:horizontal:hover{background-color: #6087cefa;"
            "margin: 5px;}"
            "QSplitter::handle:vertical:hover{background-color: #6087cefa;"
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
        self.filesAutoAddCB = qt.QCheckBox("auto append fresh file TODO", self)

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
        layout.setContentsMargins(4, 0, 0, 0)
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
        node = self.node
        # self.backend = dict(backend='opengl')
        self.backend = dict(backend='matplotlib')

        if node.plotDimension == 3:
            self.plot = Plot3D(
                self.splitterPlot, position=Plot3D.posInfo, **self.backend
                )
            self.plot.setCustomPosInfo()
            self.plot.setTitleCallback(self.titleCallback3D)
        elif node.plotDimension == 2:
            self.plot = Plot2D(
                self.splitterPlot, **self.backend
                )
        elif node.plotDimension == 1:
            xLbl = node.get_arrays_prop('qLabel', role='x')[0]
            yLbl = node.get_arrays_prop('qLabel', role='y')[0]
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
        hasWidgetClass = self.node.widgetClass is not None
        if hasWidgetClass:
            self.transformWidget = self.node.widgetClass(
                parent=parent, node=self.node)
        else:
            self.transformWidget = qt.QWidget(parent)
        if tr is not None:
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
        self.makeSplitterButton('metadata', self.splitterPlot, 1, 1)
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
        # self.plot.clear()
        # yUnits = node.get_arrays_prop('plotUnit', yNames)
        # yLabels = node.get_arrays_prop('plotLabel', yNames)

        if node.plotDimension == 1:
            self.plot.clearCurves()
            self.plot.clearImages()
            # self.plot.clearMarkers()
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
                    curveLabel = item.alias + '.' + yN
                    plotProps = dict(item.plotProps[node.name][yN])
                    symbolsize = plotProps.pop('symbolsize', 2)
                    z = 1 if item in csi.selectedItems else 0
                    try:
                        self.plot.addCurve(
                            x, y, legend=curveLabel, color=item.color, z=z,
                            **plotProps)
                    except Exception as e:
                        print('plotting in {0} failed: {1}'.format(
                            self.node.name, e))
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
            # self.plot.clearMarkers()
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
                               scale=(xScale, yScale))
        if node.plotDimension == 3:
            self.plot._plot.clearCurves()
            self.plot._plot.clearImages()
            # self.plot._plot.clearMarkers()
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

    def shouldUpdateFileModel(self):
        for it in csi.selectedItems:
            if it.dataType in (cco.DATA_COLUMN_FILE, cco.DATA_DATASET) and\
                    csi.nodes[it.originNodeName] is self.node:
                return it.madeOf

    def loadFiles(self, fileNamesFull=None, parentItem=None, insertAt=None):
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
        csi.model.importData(
            fileNamesFull, parentItem, insertAt, dataFormat=df,
            originNodeName=self.node.name)

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

    def linkClicked(self, url):
        strURL = str(url.toString())
        if strURL.startswith('http') or strURL.startswith('ftp'):
            if self.lastBrowserLink == strURL:
                return
            webbrowser.open(strURL)
            self.lastBrowserLink = strURL
