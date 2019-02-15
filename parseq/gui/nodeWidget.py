# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys
import os
import webbrowser

from silx.gui import qt
#from silx.gui.plot.PlotWindow import PlotWindow
from silx.gui.plot import Plot1D

from ..core import singletons as csi
from ..core import commons as cco
from ..core import spectra as csp
from ..gui.fileTreeModelView import FileTreeView, NODE_FS
from ..gui.dataTreeModelView import DataTreeView
from ..gui.webWidget import QWebView
from ..gui.columnFormatWidget import ColumnFormatWidget
from ..gui.combineSpectraWidget import CombineSpectraWidget

SPLITTER_WIDTH, SPLITTER_BUTTON_MARGIN = 10, 25
DEBUG = 10


class QSplitterButton(qt.QPushButton):
    def __init__(self, text, parent, isVertical=False,
                 margin=SPLITTER_BUTTON_MARGIN):
        super(QSplitterButton, self).__init__(text, parent)
        self.rawText = str(text)
        self.isVertical = isVertical
        fontSize = "10" if sys.platform == "darwin" else "6.5"
        grad = "x1: 0, y1: 0, x2: 0, y2: 1"
        self.setStyleSheet("""
            QPushButton {
                font-size: """ + fontSize + """pt; color: #151575;
                padding-bottom: 0px; text-align: bottom;
                border: 2px; border-radius: 4px;
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
        if not self.isVertical:
            super(QSplitterButton, self).paintEvent(event)
            return
        painter = qt.QStylePainter(self)
        painter.rotate(270)
        painter.translate(-1 * self.height(), 0)
        painter.drawControl(qt.QStyle.CE_PushButton, self.getStyleOptions())

    def getStyleOptions(self):
        options = qt.QStyleOptionButton()
        options.initFrom(self)
        size = options.rect.size()
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
        fname = self.node.name + '.html'
        self.helpFile = os.path.join(csi.appPath, 'doc', fname)
        node.widget = self

        self.makeSplitters()
        self.fillSplitterFiles()
        self.fillSplitterData()
        self.fillSplitterPlot()
        self.fillSplitterTransform()
        self.makeSplitterButtons()
        self.fillHelpWidget()
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setStretchFactor(3, 0)
        self.splitter.setSizes([1, 1, 1, 1])
        self.splitterButtons[u'files && containers'].clicked.emit(False)

        # sharing tree selections among nodes:
        if csi.selectionModel is None:
            csi.selectionModel = self.tree.selectionModel()
        else:
            self.tree.setSelectionModel(csi.selectionModel)
        self.replot()

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
        qWidget = qt.QWidget(self.splitterFiles)
        layout = qt.QVBoxLayout(self.splitterFiles)
        layout.setContentsMargins(2, 0, 0, 0)
        self.files = FileTreeView(self.node, self.splitterFiles)
#        self.files.doubleClicked.connect(self.loadFiles)

        self.filesAutoAddCB = qt.QCheckBox("auto append fresh file TODO", self)
        layout.addWidget(self.files)
        layout.addWidget(self.filesAutoAddCB)
        qWidget.setLayout(layout)

        self.columnFormat = ColumnFormatWidget(self.splitterFiles, self.node)

        self.splitterFiles.setStretchFactor(0, 1)  # don't remove
        self.splitterFiles.setStretchFactor(1, 0)

    def fillSplitterData(self):
        self.tree = DataTreeView(self.node, self.splitterData)
        self.tree.needReplot.connect(self.replot)
        self.tree.selectionModel().selectionChanged.connect(self.selChanged)
        self.combiner = CombineSpectraWidget(self.splitterData, self.node)

        self.splitterData.setStretchFactor(0, 1)  # don't remove
        self.splitterData.setStretchFactor(1, 0)

    def fillSplitterPlot(self):
#        self.backend = dict(backend='opengl')
        self.backend = dict(backend='matplotlib')
        try:
            xLbl = self.node.xQLabel
        except AttributeError:
            xLbl = self.node.xName
        try:
            yLbl = self.node.yQLabels[0]
        except AttributeError:
            yLbl = self.node.yNames[0]

#        self.plot = PlotWindow(
        self.plot = Plot1D(
            self.splitterPlot, **self.backend
#            position=[(xLbl, lambda x, y: x), (yLbl, lambda x, y: y)]
            )
        self.plot.getXAxis().setLabel(xLbl)
        self.plot.getYAxis().setLabel(yLbl)
        self.setupPlot()

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
        self.makeTransformWidget(self.splitterTransform)
        self.help = QWebView(self.splitterTransform)
        self.help.setHtml('no documentation available')
        self.help.setMinimumSize(qt.QSize(200, 200))

        self.splitterTransform.setCollapsible(0, False)
        self.splitterTransform.setStretchFactor(0, 0)  # don't remove
        self.splitterTransform.setStretchFactor(1, 1)

    def makeTransformWidget(self, parent):
        tr = self.node.transformIn
        if tr is not None:
            self.transformWidget = tr.widgetClass(parent=parent, transform=tr)
        else:
            self.transformWidget = None

    def fillHelpWidget(self):
        if not os.path.exists(self.helpFile):
            # self.splitterButtons['help'].click()  # doesn't work
            self.handleHideHelp()
        self.makeSplitterHelpButton(self.splitterTransform, 1)

        ipath = os.path.join(os.path.dirname(self.helpFile), r'_images')
        ipath = ipath.replace("\\", r"/")  # or else doesn't work on Windows!\
        f = qt.QFile(self.helpFile)
        if f.open(qt.QFile.ReadOnly | qt.QFile.Text):
            stream = qt.QTextStream(f)
            self.help.setHtml(stream.readAll(), qt.QUrl('file:///'+ipath))
            f.close()

    def makeSplitterButtons(self):
        self.splitterButtons = {}
        self.makeSplitterButton(
            u'files && containers', self.splitter, 1, 0, qt.Qt.LeftArrow)
        self.makeSplitterButton(
            'data', self.splitter, 2, 1, qt.Qt.LeftArrow)
        self.makeSplitterButton(
            'transform', self.splitter, 3, 3, qt.Qt.RightArrow)
        self.makeSplitterButton(
            'data format', self.splitterFiles, 1, 1, qt.Qt.DownArrow)
        self.makeSplitterButton(
            'combine', self.splitterData, 1, 1, qt.Qt.DownArrow)
        self.makeSplitterButton(
            'meta', self.splitterPlot, 1, 1, qt.Qt.DownArrow)
        self.makeSplitterButton(
            'help', self.splitterTransform, 1, 1, qt.Qt.DownArrow)

    def setArrowType(self, button, orientation):
        if orientation in (qt.Qt.LeftArrow, qt.Qt.UpArrow):
            sym = u' ▲ '
        elif orientation in (qt.Qt.RightArrow, qt.Qt.DownArrow):
            sym = u' ▼ '
        else:
            sym = ''
        button.setText(sym + button.rawText + sym)

    def makeSplitterButton(
            self, name, splitter, indHandle, indSizes, orientation):
        handle = splitter.handle(indHandle)
        if handle is None:
            return
        isVerical = orientation in (qt.Qt.LeftArrow, qt.Qt.RightArrow)
        button = QSplitterButton(name, handle, isVerical)
        self.setArrowType(button, orientation)
        splitter.setHandleWidth(SPLITTER_WIDTH)
        po = qt.QSizePolicy(qt.QSizePolicy.Preferred, qt.QSizePolicy.Preferred)
        button.setSizePolicy(po)
        button.clicked.connect(
            lambda: self.handleSplitterButton(orientation, indSizes))
        if orientation in (qt.Qt.UpArrow, qt.Qt.DownArrow):
            sLayout = qt.QHBoxLayout()
        else:
            sLayout = qt.QVBoxLayout()
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
        button.clicked.connect(lambda: self.handleSplitterHelpButton())
        sLayout = handle.layout()
        sLayout.addWidget(button)
        handle.setLayout(sLayout)

    def handleSplitterButton(self, orientation, indSizes):
        button = self.sender()
        splitter = button.parent().splitter()
        sizes = splitter.sizes()
        if sizes[indSizes]:
            sizes[indSizes] = 0
            if orientation == qt.Qt.LeftArrow:
                arrow = qt.Qt.RightArrow
            elif orientation == qt.Qt.RightArrow:
                arrow = qt.Qt.LeftArrow
            elif orientation == qt.Qt.UpArrow:
                arrow = qt.Qt.DownArrow
            elif orientation == qt.Qt.DownArrow:
                arrow = qt.Qt.UpArrow
            else:
                arrow = qt.Qt.NoArrow
        else:
            sizes[indSizes] = 1
            arrow = orientation
        splitter.setSizes(sizes)
        self.setArrowType(button, arrow)

    def handleSplitterHelpButton(self):
        webbrowser.open(self.helpFile)

    def handleHideHelp(self):
        self.splitterTransform.setSizes([1, 0])
        self.setArrowType(self.splitterButtons['help'], qt.Qt.UpArrow)

    def setupPlot(self):
        try:
            xUnit = u" ({0})".format(self.node.xPlotUnit) \
                if self.node.xPlotUnit else ""
        except AttributeError:
            xUnit = ''
        self.plot.setGraphXLabel(
            label=u"{0}{1}".format(self.node.xPlotLabel, xUnit))

    def replot(self):
        node = self.node
        self.plot.clear()
        for item in csi.allLoadedItems:
            if not node.is_between_nodes(item.originNode, item.terminalNode,
                                         node1in=True, node2in=True):
                continue
            if not item.isGood[node.name]:
                continue
            if not item.isVisible:
                continue
            try:
                x = getattr(item, node.xName)
            except AttributeError:
                continue
            for col, yN in enumerate(node.yNames):
                try:
                    y = getattr(item, yN)
                except AttributeError:
                    continue
                curveLabel = item.alias + '.' + yN
                plotProps = dict(item.plotProps[node.name][yN])
                symbolsize = plotProps.pop('symbolsize', 2)
                self.plot.addCurve(
                    x, y, legend=curveLabel, color=item.color, **plotProps)
                symbol = plotProps.get('symbol', None)
                if symbol is not None:
                    curve = self.plot.getCurve(curveLabel)
                    if curve is not None:
                        if self.backend['backend'] == 'opengl':
                            # don't know why it is small with opengl
                            symbolsize *= 2
                        curve.setSymbolSize(symbolsize)
        self.setPlotYLabels()

    def setPlotYLabels(self):
        node = self.node
        leftAxisCols = []
        rightAxisCols = []
        for data in csi.allLoadedItems:
            if not node.is_between_nodes(data.originNode, data.terminalNode,
                                         node1in=True, node2in=True):
                continue
            for col, yN in enumerate(node.yNames):
                curveLabel = data.alias + '.' + yN
                curve = self.plot.getCurve(curveLabel)
                if curve is None:
                    continue
                yaxis = curve.getYAxis()
                if yaxis == 'left':
                    if col not in leftAxisCols:
                        leftAxisCols.append(col)
                if yaxis == 'right':
                    if col not in rightAxisCols:
                        rightAxisCols.append(col)
        self.plot.setGraphYLabel(
            label=self._makeYLabel(leftAxisCols), axis='left')
        self.plot.setGraphYLabel(
            label=self._makeYLabel(rightAxisCols), axis='right')

    def _makeYLabel(self, cols):
        if cols == []:
            return ""
        node = self.node
        equalYUnits = True
        try:
            yUnit0 = node.yPlotUnits[cols[0]]
            for yUnit in [node.yPlotUnits[i] for i in cols[1:]]:
                if yUnit != yUnit0:
                    equalYUnits = False
                    break
        except AttributeError:
            yUnit0 = ""

        axisLabel = u""
        for icol, col in enumerate(cols):
            spacer = u"" if icol == 0 else u", "
            unit = u"" if equalYUnits else u" ({0})".format(
                node.yPlotUnits[col] if node.yPlotUnits[col] else "unitless")
            axisLabel += spacer + node.yPlotLabels[col] + unit
        if equalYUnits and yUnit0:
            axisLabel += u" ({0})".format(yUnit0)
        return axisLabel

    def selChanged(self):
        self.updateNodeForSelectedItems()
        if DEBUG > 0 and self.mainWindow is None:  # only for test purpose
            selNames = ', '.join([it.alias for it in csi.selectedItems])
            dataCount = len(csi.allLoadedItems)
            self.setWindowTitle('{0} total; {1}'.format(dataCount, selNames))

    def updateNodeForSelectedItems(self):
        self.updateSplittersForSelectedItems()
        fobj = self.shouldUpdateFileModel()
        if fobj:
            if fobj[1] == csp.DATA_COLUMN_FILE:
                ind = self.files.model().indexFileName(fobj[0])
            else:  # fobj[1] == csp.DATA_DATASET:
                ind = self.files.model().indexFromH5Path(fobj[0])
            self.files.setCurrentIndex(ind)
            self.files.scrollTo(ind)
        self.updateMeta()
        self.updatePlot()
        self.columnFormat.setUIFromData()
        self.combiner.setUIFromData()
        self.updateTransforms()

    def shouldUpdateFileModel(self):
        for it in csi.selectedItems:
            if it.dataType in (csp.DATA_COLUMN_FILE, csp.DATA_DATASET) and\
                    it.originNode is self.node:
                return it.madeOf, it.dataType
        return

    def loadFiles(self, fileNamesFull=None, parentItem=None, insertAt=None):
        if isinstance(fileNamesFull, qt.QModelIndex):
            if qt.QFileInfo(
                    self.files.model().filePath(fileNamesFull)).isDir():
                return
            fileNamesFull = None
        if fileNamesFull is None:
            sIndexes = self.files.selectionModel().selectedRows()
            nodeType = self.files.model().nodeType(sIndexes[0])
            if nodeType == NODE_FS:
                fileNamesFull = \
                    [self.files.model().filePath(i) for i in sIndexes]
            else:  # FileTreeView.NODE_HDF5, FileTreeView.NODE_HDF5_HEAD
                fileNamesFull = \
                    [self.files.model().getHDF5FullPath(i) for i in sIndexes]

        fileNames = [os.path.normcase(i) for i in fileNamesFull]
        duplicates, duplicatesNorm = [], []
        for data in csi.allLoadedItems:
            normpath = os.path.normcase(data.madeOf)
            if normpath in fileNames:
                if normpath not in duplicatesNorm:
                    duplicatesNorm.append(normpath)
                    duplicates.append(data.madeOf)
        if duplicates:
            st1, st2, st3, st4 =\
                ('This', '', 'is', 'it') if len(duplicates) == 1 else\
                ('These', 's', 'are', 'them')
            msg = qt.QMessageBox()
            msg.setIcon(qt.QMessageBox.Question)
            res = msg.question(self, "Already in the data list",
                               "{0} file{1} {2} already loaded:\n{3}".format(
                                   st1, st2, st3, '\n'.join(duplicates)) +
                               "\nDo you want to load {0} gain?".format(st4),
                               qt.QMessageBox.Yes | qt.QMessageBox.No,
                               qt.QMessageBox.Yes)
            if res == qt.QMessageBox.No:
                return
        if parentItem is None:
            if csi.selectedItems:
                parentItem = csi.selectedItems[-1].parentItem
            else:
                parentItem = csi.dataRootItem
        # !!! TODO !!!
        # here the column format is taken from the present state of
        # ColumnFormatWidget. Should be automatically detected from
        # file format
        df = self.columnFormat.getDataFormat()
        if not df:
            return
        return csi.model.importData(
            fileNamesFull, parentItem, insertAt, dataFormat=df,
            originNode=self.node)

    def shouldShowColumnDialog(self):
        for it in csi.selectedItems:
            if it.dataType in (csp.DATA_COLUMN_FILE, csp.DATA_DATASET) and\
                    it.originNode is self.node:
                return True
        return False

    def updateSplittersForSelectedItems(self):
        showColumnDialog = self.shouldShowColumnDialog()
        self.splitterFiles.setSizes([1, int(showColumnDialog)])
        self.setArrowType(
            self.splitterButtons['data format'],
            qt.Qt.DownArrow if showColumnDialog else qt.Qt.UpArrow)

    def updateMeta(self):
        try:
            cs = csi.selectedItems[0].meta['text']
        except (IndexError, KeyError):
            return
        for item in csi.selectedItems[1:]:
            cs = cco.common_substring(cs, item.meta['text'])
        self.metadata.setText(cs)

    def updatePlot(self):  # bring the selected curves to the top
        node = self.node
        for item in csi.selectedItems:
            if not node.is_between_nodes(item.originNode, item.terminalNode,
                                         node1in=True, node2in=True):
                continue
            for col, yN in enumerate(node.yNames):
                curveLabel = item.alias + '.' + yN
                curve = self.plot.getCurve(curveLabel)
                if curve is not None:
                    curve._updated()

    def updateTransforms(self):
        if self.transformWidget:
            self.transformWidget.setUIFromData()
