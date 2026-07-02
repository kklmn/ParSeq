# -*- coding: utf-8 -*-
u"""
Data combination widget
-----------------------

.. imagezoom:: _images/w-combine0.png
   :align: left
   :alt: &ensp;Data combination widget

The widget "combine" can be found in the "Data" splitter under the list of all
data items.

Average, sum, rms deviation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Select one or more data items, select a combination type and press "Combine"
button. A new data item will be created and placed after the selected parental
data.

PCA
~~~

For a selected set of data, a plot window appears at the bottom of the widget,
displaying both a scree plot and the IND function. Use these plots to choose
the desired number of components, then click the "Combine" button. For each
parent data item, a new group will be created containing the PCA components of
the specified 1D array.

.. imagezoom:: _images/w-combine1.png
   :align: right
   :alt: &ensp;Data combination widget with MCR-ALS settings

Target transformation
~~~~~~~~~~~~~~~~~~~~~

Select a data item and choose the combination type "target-transformation".
Then click the "Combine" button. A data selection dialog will appear, allowing
to choose a set of basis spectra. After clicking "Apply", a new data item will
be created under the original one, containing the resulting target
transformation. Compare this new item with the original data.

MCR-ALS
~~~~~~~

For a selected set of examined data and a given value of :math:`N`, the widget
provides a table of MCR-ALS settings, including definitions of the initial
:math:`S` and optional constraints on :math:`S` and :math:`C`.

Note that the choice of the abscissa range is an additional parameter that can
influence the MCR-ALS solution. The combination widget includes a range
selector to help define an appropriate spectral interval.

The resulting :math:`C` is displayed at the bottom of the widget, while the
corresponding :math:`S` is shown in the main node plot. After clicking the
"Combine" button, a new data group is created containing the columns of
:math:`S` as new spectra.

"""
__author__ = "Konstantin Klementiev"
__date__ = "9 Jun 2026"
# !!! SEE CODERULES.TXT !!!

from functools import partial
import os
import numpy as np
from scipy.interpolate import interp1d
from silx.gui import qt
from silx.gui.plot import PlotWidget, tools, actions

# from ..core import spectra as csp
from ..core import singletons as csi
from ..core import transforms as ctr
from ..core import commons as cco
from .propWidget import PropWidget
from . import propsOfData as gpd
from ..utils import math as uma
from .roi import AutoRangeWidget
from . import gcommons as gco

COLOR_GRADIENT_PCA1 = 'green'
COLOR_GRADIENT_PCA2 = 'red'

headerMCR = 'initial S', 'S>0', 'C↓', 'tie C', 'tie C val'
headerMCRWidths = 90, 36, 36, 40, 70
initialMCR = 'auto', 'start', 'end', 'mean', 'reference'
constraintMCR = '', '<', '>'
defaultMCRDict = dict(initialS='auto', positiveS=True, zeroC=False,
                      constraintCKind='', constraintCValue=0.3)


class RangeWidgetX(AutoRangeWidget):
    'fractionMin, fractionMax of range [eMin, eMax]'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.editCustom.returnPressed.connect(self.updateFromEdit)

    def updateFromEdit(self):
        self.acceptEdit()


class MCRTasker(qt.QObject):
    ready = qt.pyqtSignal()

    def __init__(self):
        super().__init__()
        self.eps = 1e-16
        self.maxIteration = 1000

    def prepare(self, node, x, D, mcrData, retErrors=False):
        self.node = node
        self.x = x
        self.D = D
        self.mcrData = mcrData
        self.retErrors = retErrors

    def run(self):
        csi.mainWindow.beforeTransformSignal.emit(self.node.widget)
        self.node.widget.onTransform = True

        res = uma.mcr_als(
            self.x, self.D, self.mcrData, retErrors=self.retErrors,
            eps=self.eps, maxIteration=self.maxIteration)
        if self.retErrors:
            self.S, self.C, self.revCTC, self.Cfit = res
        else:
            self.S, self.C, self.revCTC = res
            self.Cfit = None

        self.node.widget.onTransform = False
        self.thread().terminate()
        self.ready.emit()
        csi.mainWindow.afterTransformSignal.emit(self.node.widget)


class MCRModel(qt.QAbstractTableModel):
    def __init__(self, parent, mcrData, node):
        super().__init__()
        self.parent = parent
        self.node = node
        self.pendingRow = 0
        self.selectedItemsMCR = []
        self.N = len(mcrData)
        self.setMCRData(mcrData)

    def rowCount(self, parent=qt.QModelIndex()):
        return self.N

    def columnCount(self, parent=qt.QModelIndex()):
        return len(headerMCR)

    def headerData(self, section, orientation, role):
        if orientation == qt.Qt.Horizontal:
            if role == qt.Qt.DisplayRole:
                return headerMCR[section]
            elif role == qt.Qt.TextAlignmentRole:
                return qt.Qt.AlignHCenter
            elif role == qt.Qt.ToolTipRole:
                if section == 0:  # initialS
                    return 'initial guess for spectral component'
                elif section == 1:  # S>0
                    return "toggle constraint S>0"
                elif section == 2:  # C↓
                    return "toggle constraint min(C)=0"
                elif section == 3:  # constraint kind
                    return "constraint C kind"
                elif section == 4:  # constraint value
                    return 'constraint C value'
        elif orientation == qt.Qt.Vertical:
            if role == qt.Qt.DisplayRole:
                return f'{section+1}'
            elif role == qt.Qt.TextAlignmentRole:
                return qt.Qt.AlignLeft
            elif role == qt.Qt.ForegroundRole:
                return qt.QColor(gco.colorCycle1[section % 10])
            elif role == qt.Qt.FontRole:
                font = qt.QFont()
                font.setBold(True)
                return font

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        column, row = index.column(), index.row()
        if column == 1:  # S>0
            return qt.Qt.ItemIsEnabled | qt.Qt.ItemIsUserCheckable
        elif column == 2:  # C↓
            return qt.Qt.ItemIsEnabled | qt.Qt.ItemIsUserCheckable
        elif column == 4:  # constraint value
            if self.mcrData[row]['constraintCKind'] == '':
                return qt.Qt.NoItemFlags
            else:
                return qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        else:
            return qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable

    def data(self, index, role=qt.Qt.DisplayRole):
        if not index.isValid():
            return
        column, row = index.column(), index.row()
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            if column == 0:  # initialS
                if self.mcrData[row]['initialS'] == initialMCR[-1]:
                    if 'refalias' in self.mcrData[row]:
                        return self.mcrData[row]['refalias']
                    else:
                        return ''
                return self.mcrData[row]['initialS']
            elif column == 3:  # constraint kind
                return self.mcrData[row]['constraintCKind']
            elif column == 4:  # constraint value
                if self.mcrData[row]['constraintCKind'] == '':
                    return ""
                else:
                    return f"{self.mcrData[row]['constraintCValue']:.2f}"
        elif role == qt.Qt.CheckStateRole:
            if column == 1:  # S>0
                return qt.Qt.Checked if self.mcrData[row]['positiveS'] else \
                    qt.Qt.Unchecked
            elif column == 2:  # C↓
                return qt.Qt.Checked if self.mcrData[row]['zeroC'] else \
                    qt.Qt.Unchecked
        elif role == qt.Qt.ToolTipRole:
            if column == 0:  # initialS
                return 'initial guess for spectral component'
            elif column == 1:  # S>0
                return "constraint S>0"
            elif column == 2:  # C↓
                return "constraint min(C)=0"
            elif column == 3:  # constraint kind
                return "constraint C('': none, '<': low-pass, '>': high-pass)"
            elif column == 4:  # constraint value
                return 'constraint C value (0 < value < 1)'
        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignCenter
        elif role == gco.LIMITS_ROLE:  # return min, max, step
            if column == 4:  # constraint value
                return 0.0, 1.0, 0.01
                return

    def setData(self, index, value, role=qt.Qt.EditRole):
        column, row = index.column(), index.row()
        if role == qt.Qt.EditRole:
            if column == 0:  # initialS
                self.mcrData[row]['initialS'] = value
                if value == initialMCR[-1]:
                    self.selectedItemsMCR = list(csi.selectedItems)
                    self.node.widget.preparePickData(
                        self.parent, 'Pick a reference')
                    self.pendingRow = row
                else:
                    self.parent.updateMCR()
                return True
            elif column == 3:  # constraint kind
                self.mcrData[row]['constraintCKind'] = value
                self.parent.updateMCR()
                return True
            elif column == 4:  # constraint value
                self.mcrData[row]['constraintCValue'] = value
                self.parent.updateMCR()
                return True
            else:
                return False
        elif role == qt.Qt.CheckStateRole:
            if column == 1:  # S>0
                self.mcrData[row]['positiveS'] = bool(value)
                self.parent.updateMCR()
                return True
            elif column == 2:  # C↓
                self.mcrData[row]['zeroC'] = bool(value)
                self.parent.updateMCR()
                return True
        return False

    def updateAll(self):
        topLeft = self.index(0, 0)
        bottomRight = self.index(self.rowCount()-1, self.columnCount()-1)
        if topLeft.isValid() and bottomRight.isValid():
            self.dataChanged.emit(topLeft, bottomRight)

    def setMCRData(self, mcrData=[]):
        self.beginResetModel()
        self.mcrData = mcrData
        self.endResetModel()
        self.updateAll()


class MCRTableView(qt.QTableView):
    def __init__(self, parent, model):
        super().__init__(parent)
        self.setModel(model)
        # horHeaders = self.horizontalHeader()  # QHeaderView instance
        horHeaders = gco.UnderlinedHeaderView(qt.Qt.Horizontal, self)
        self.setHorizontalHeader(horHeaders)

        verHeaders = self.verticalHeader()  # QHeaderView instance
        verHeaders.setDefaultSectionSize(20)

        if 'pyqt4' in qt.BINDING.lower():
            horHeaders.setMovable(False)
            for i in range(len(headerMCRWidths)):
                horHeaders.setResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setResizeMode(0, qt.QHeaderView.Stretch)  # initial
            horHeaders.setClickable(True)
        else:
            horHeaders.setSectionsMovable(False)
            for i in range(len(headerMCRWidths)):
                horHeaders.setSectionResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setSectionResizeMode(0, qt.QHeaderView.Stretch)
            horHeaders.setSectionsClickable(True)
        horHeaders.setStretchLastSection(False)
        horHeaders.setMinimumSectionSize(20)
        horHeaders.sectionClicked.connect(self.headerClicked)

        self.setItemDelegateForColumn(0, gco.ComboDelegate(self, initialMCR))
        self.setItemDelegateForColumn(1, gco.CheckBoxDelegate(self))
        self.setItemDelegateForColumn(2, gco.CheckBoxDelegate(self))
        kw = dict(alignment=qt.Qt.AlignHCenter | qt.Qt.AlignVCenter)
        self.setItemDelegateForColumn(
            3, gco.ComboDelegate(self, constraintMCR, **kw))
        self.setItemDelegateForColumn(
            4, gco.DoubleSpinBoxDelegate(self, **kw))

        for i, cw in enumerate(headerMCRWidths):
            self.setColumnWidth(i, int(cw*csi.screenFactor))

        self.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.setSizeAdjustPolicy(qt.QAbstractScrollArea.AdjustToContents)
        self.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Minimum)

    def headerClicked(self, column):
        if column == 1:
            for d in self.model().mcrData:
                d['positiveS'] = not d['positiveS']
        elif column == 2:
            for d in self.model().mcrData:
                d['zeroC'] = not d['zeroC']
        else:
            return
        self.model().updateAll()
        self.model().parent.updateMCR()


class CombineSpectraWidget(PropWidget):
    deflinestyle = dict(linewidth=1, linestyle='-', symbol='o', symbolsize=3)

    def __init__(self, parent=None, node=None):
        super().__init__(parent, node)
        self.selectedItemsTT = []
        self.D = None
        self.refD = []

        combineDataGroup = self.makeCombineDataGroup()
        layout = qt.QVBoxLayout()
        layout.setContentsMargins(4, 2, 2, 0)
        self.stopHereCB = qt.QCheckBox("stop data propagation here")
        self.stopHereCB.clicked.connect(self.doStopHere)
        self.stopHereCB.setEnabled(node is not None)
        layout.addWidget(self.stopHereCB)
        layout.addWidget(combineDataGroup)
        self.plotPCA = PlotWidget(parent=self)
        self.plotMCR = PlotWidget(parent=self)

        kw1 = dict(parent=self, plot=self.plotPCA)
        self.toolbarPCA = tools.InteractiveModeToolBar(**kw1)
        col1 = '#6F917C'
        tt1 = 'PCA scree and Malinowsky indicator IND'

        kw2 = dict(parent=self, plot=self.plotMCR)
        col2 = '#6F7C91'
        tt2 = 'MCR-ALS C matrix'
        self.toolbarMCR = tools.InteractiveModeToolBar(**kw2)

        for toolbar, kw, color, tt in zip(
                (self.toolbarPCA, self.toolbarMCR), (kw1, kw2), (col1, col2),
                (tt1, tt2)):
            action = actions.control.ResetZoomAction(**kw)
            toolbar.addAction(action)
            action = actions.control.CurveStyleAction(**kw)
            toolbar.addAction(action)
            action = actions.control.GridAction(**kw)
            toolbar.addAction(action)
            action = actions.control.XAxisLogarithmicAction(**kw)
            toolbar.addAction(action)
            action = actions.control.YAxisLogarithmicAction(**kw)
            toolbar.addAction(action)
            action = actions.io.CopyAction(**kw)
            toolbar.addAction(action)
            action = actions.io.SaveAction(**kw)
            toolbar.addAction(action)
            toolbar.setIconSize(qt.QSize(18, 18))
            butVisible = gco.EyeButton('', toolbar)
            butVisible.setToolTip(f'show/hide "{tt}" plot')
            butVisible.setStyleSheet("QPushButton{color: " + color + ";}")
            butVisible.setFixedSize(30, 22)
            butVisible.setCheckable(True)
            butVisible.setChecked(True)
            butVisible.clicked.connect(
                partial(self.setPlotVisible, kw['plot']))
            toolbar.addWidget(butVisible)

        self.plotPCA.setYAxisLogarithmic(True)
        self.plotPCA.setGraphXLabel(label="k")
        self.plotPCA.setGraphYLabel("eigenvalues", "left")
        self.plotPCA.setGraphYLabel("IND", "right")
        # self.plotPCA.setAxesMargins(0.1, 0.1, 0.1, 0.1)
        self.plotPCA.setMinimumSize(100, 100)
        self.plotPCA.hide()
        self.plotPCA.sigPlotSignal.connect(self.plotPCASlot)

        self.plotMCR.setGraphXLabel(label="k")
        self.plotMCR.setGraphYLabel("C", "left")
        # self.plotMCR.setAxesMargins(0.1, 0.1, 0.1, 0.1)
        self.plotMCR.setMinimumSize(100, 100)
        self.plotMCR.setGraphYLimits(0, 1, 'left')
        self.plotMCR.hide()
        # self.plotMCR.sigPlotSignal.connect(self.plotPCASlot)

        self.mcrPanel = None
        if node.plotDimension == 1:
            layoutMCR = qt.QVBoxLayout()
            layoutMCR.setContentsMargins(2, 2, 2, 2)
            self.mcrData = [dict(defaultMCRDict)]
            self.mcrModel = MCRModel(self, self.mcrData, node)
            self.mcrTable = MCRTableView(self, self.mcrModel)
            layoutMCR.addWidget(self.mcrTable)
            self.mcrPanel = qt.QGroupBox('MCR-ALS settings')
            self.mcrPanel.setLayout(layoutMCR)
            layout.addWidget(self.mcrPanel)

        layout.addWidget(self.toolbarMCR)
        layout.addWidget(self.plotMCR)
        layout.addWidget(self.toolbarPCA)
        layout.addWidget(self.plotPCA)

        self.combineDo = qt.QPushButton("Combine")
        self.combineDo.clicked.connect(self.createCombined)
        # self.combineDo.setEnabled(len(self.pcaNames) > 1)
        layout.addWidget(self.combineDo)

        layout.addStretch()
        self.setLayout(layout)
        self.combineTypeChanged(0)
        self.combineStopCBChanged(0)

        self.mcrThread = qt.QThread(self)
        self.mcrTasker = MCRTasker()
        self.mcrTasker.moveToThread(self.mcrThread)
        self.mcrThread.started.connect(self.mcrTasker.run)
        self.mcrTasker.ready.connect(self.doneMCR)

    def xRangeDefault(self):
        return self.node.widget.plot.getGraphXLimits()

    def makeCombineDataGroup(self):
        self.combineType = qt.QComboBox()
        self.combineType.addItems(cco.combineNames)
        for itt, tt in enumerate(cco.combineToolTips):
            self.combineType.setItemData(itt, tt, qt.Qt.ToolTipRole)
        if self.node.plotDimension > 1:
            for ind in range(4, self.combineType.count()):
                self.combineType.setItemData(ind, False, qt.Qt.UserRole-1)
        self.combineType.currentIndexChanged.connect(self.combineTypeChanged)
        self.combineArray = qt.QComboBox()
        if hasattr(self.node, 'pcaNames'):
            self.pcaNames = self.node.pcaNames
        else:
            self.pcaNames = self.node.get_1D_data_arrays()
        self.combineArray.addItems(self.pcaNames[1:])
        if len(self.pcaNames) > 1:
            self.combineArray.setCurrentIndex(len(self.pcaNames)-2)
        self.combineArray.setToolTip("arrays to form data matrix D")
        self.combineArray.currentIndexChanged.connect(self.updatePCA)
        self.combineInterpolateCB = qt.QCheckBox(u"interpolate")
        self.combineInterpolateCB.setToolTip(
            "interpolate all selected data\nto the grid of the first data")
        self.combineN = qt.QSpinBox()
        self.combineN.setToolTip('PCA N')
        self.combineN.setMinimum(1)
        self.combineN.valueChanged.connect(self.combineNChanged)
        self.combineStopCB = qt.QCheckBox(
            u"stop propagation of\ncontributing data at:")
        self.combineStopCB.stateChanged.connect(self.combineStopCBChanged)
        self.combineStop = qt.QComboBox()
        self.combineStop.addItems(csi.nodes.keys())
        self.combineMoveToGroupCB = qt.QCheckBox(
            u"move selected data to a new group")

        self.xRangeWidget = None
        if self.node.plotDimension == 1 and self.node.widget is not None:
            xname = self.node.plotXArray
            self.xRangeWidget = RangeWidgetX(
                self, self.node.widget.plot, f'{xname} range',
                f'[{xname}.min, {xname}.max]', 'MCR-ALS-range',
                "#60aad6", "{0[0]:.1f}, {0[1]:.1f}", self.xRangeDefault)
            self.xRangeWidget.setRange('auto')
            self.xRangeWidget.rangeChanged.connect(self.xRangeChanged)

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layoutN = qt.QHBoxLayout()
        layoutN.setContentsMargins(0, 0, 0, 0)
        layoutN.addWidget(self.combineType)
        layoutN.addStretch()
        layoutN.addWidget(self.combineArray)
        layoutN.addWidget(self.combineN)
        layout.addLayout(layoutN)

        layoutI = qt.QHBoxLayout()
        layoutI.setContentsMargins(0, 0, 0, 0)
        layoutI.addWidget(self.combineInterpolateCB)
        if self.xRangeWidget:
            layoutI.addWidget(self.xRangeWidget)
        layout.addLayout(layoutI)

        layoutS = qt.QHBoxLayout()
        layoutS.addWidget(self.combineStopCB)
        layoutS.addWidget(self.combineStop)
        layout.addLayout(layoutS)

        layout.addWidget(self.combineMoveToGroupCB)

        group = qt.QGroupBox('combine selected data')
        group.setLayout(layout)
        # group.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
        return group

    def doStopHere(self, checked):
        for it in csi.selectedItems:
            it.terminalNodeName = self.node.name if checked else None
            it.colorTag = 0
            it.set_auto_color_tag()
        model = self.node.widget.tree.model()
        model.invalidateData()

    def combineTypeChanged(self, ind):
        isMCR = ind == cco.COMBINE_MCR_ALS
        needA = ind in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE,
                        cco.COMBINE_TT, cco.COMBINE_MCR_ALS)
        self.combineArray.setVisible(needA)
        if self.xRangeWidget:
            self.xRangeWidget.setVisible(needA)
        needN = ind in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE,
                        cco.COMBINE_MCR_ALS)
        self.combineN.setVisible(needN)
        if ind == cco.COMBINE_TT:
            self.combineStopCB.setChecked(False)
            self.combineStop.setVisible(False)
            self.combineMoveToGroupCB.setChecked(False)
        self.combineStopCB.setEnabled(ind != cco.COMBINE_TT)
        self.combineMoveToGroupCB.setEnabled(ind != cco.COMBINE_TT)
        self.plotPCA.setVisible(needN)
        self.toolbarPCA.setVisible(needN)
        if needN:
            self.combineN.setMaximum(len(csi.selectedItems))
            self.combineDo.setEnabled(self.combineN.value() > 1)
            self.updatePCA()
        self.plotMCR.setVisible(isMCR)
        self.toolbarMCR.setVisible(isMCR)
        if self.mcrPanel is not None:
            self.mcrPanel.setVisible(isMCR)

        if not isMCR and self.node.widget is not None:
            plot = self.node.widget.plot
            for item in plot.getItems():
                legend = item.getName()
                if legend.startswith('temporal MCR-ALS'):
                    plot.removeItem(item)

    def combineStopCBChanged(self, state):
        self.combineStop.setVisible(state == qt.Qt.Checked)

    def combineNChanged(self, value):
        ind = self.combineType.currentIndex()
        isMCR = ind == cco.COMBINE_MCR_ALS
        if isMCR:
            self.combineDo.setEnabled(value > 1)
            while len(self.mcrData) < value:
                self.mcrData.append(dict(defaultMCRDict))
            self.mcrModel.N = value
            self.mcrModel.setMCRData(self.mcrData)
            self.updateMCR()
        else:
            self.combineDo.setEnabled(True)

    def setUIFromData(self):
        # gpd.setCButtonFromData(self.stopHereCB, 'terminalNodeName',
        #                        compareWith=self.node.name)
        # gpd.setComboBoxFromData(self.combineType, 'dataFormat.combine')
        # gpd.setCButtonFromData(
        #     self.combineInterpolateCB, 'dataFormat.combineInterpolate')
        # gpd.setCButtonFromData(self.combineStopCB, 'terminalNodeName')
        # gpd.setComboBoxFromData(self.combineStop, 'terminalNodeName',
        #                         compareWith=list(csi.nodes.keys()))

        if len(csi.selectedItems) == 0:
            return
        MCRC = None
        allAreMCRSpectra = False
        for it in csi.selectedItems:
            if not hasattr(it, 'MCRC'):
                allAreMCRSpectra = False
                break
            if MCRC is None:
                MCRC = it.MCRC
            else:
                if not np.allclose(MCRC, it.MCRC):
                    break
        else:
            allAreMCRSpectra = True

        if allAreMCRSpectra:
            it = csi.selectedItems[0]
            # if self.mcrPanel is not None:
            #     self.mcrPanel.setVisible(False)
            self.mcrData = [dict(comp) for comp in it.MCR]
            # add possible missing dict items:
            for d in self.mcrData:
                for key, value in defaultMCRDict.items():
                    if key not in d:
                        d[key] = value
            if self.mcrPanel is not None:
                self.mcrModel.updateAll()
                self.mcrPanel.setEnabled(False)
            self.combineN.setMaximum(len(it.MCR))
            self.combineN.setValue(len(it.MCR))
            self.combineN.setEnabled(False)
            self.toolbarPCA.setVisible(False)
            self.plotPCA.setVisible(False)
            self.toolbarMCR.setVisible(True)
            self.plotMCR.setVisible(True)
            self.replotMCRC(MCRC)
            self.replotMCRS(None)
        else:
            ind = self.combineType.currentIndex()
            needN = ind in (
                cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE,
                cco.COMBINE_MCR_ALS)
            if needN:
                self.combineN.setMaximum(len(csi.selectedItems))
                self.combineN.setEnabled(True)
                self.updatePCA()
            if self.mcrPanel is not None:
                self.mcrPanel.setEnabled(True)

    def updateDataFromUI(self):
        self.createCombined()

    def applyPendingProps(self):
        model = self.node.widget.tree.model()
        ind = self.combineType.currentIndex()
        if ind == cco.COMBINE_TT:
            kw = dict(dataFormat={'combine': ind},
                      color='#ee00ee',
                      originNodeName=self.node.name, runDownstream=False)
            dformat = kw['dataFormat']

            model.beginResetModel()
            items = csi.selectedItems + self.selectedItemsTT
            res = self.getPCA(items, interpolateTo=-1)
            if res is None:
                return
            wPCA, vPCA = res[:2]
            dformat['wPCA'] = wPCA[::-1]
            dformat['vPCA'] = vPCA[:, ::-1]
            ci = self.combineInterpolateCB.isChecked()  # after self.getPCA()!
            dformat['combineInterpolate'] = ci
            madeOf = list(csi.selectedItems)
            for idata, data in enumerate(self.selectedItemsTT):
                kw['refalias'] = '{0}-TT{1}'.format(data.alias, len(madeOf))
                it = data.parentItem.insert_item(
                    madeOf+[data], data.row()+1, **kw)
                ctr.run_transforms([it], it.parentItem)
            model.endResetModel()
            model.selectItems(self.selectedItemsTT)
        elif ind == cco.COMBINE_MCR_ALS or self.mcrPanel.isVisible():
            madeOf = list(csi.selectedItems)
            self.getRef(madeOf[0])
            self.node.widget.tree.blockSignals(True)
            model.selectItems(self.mcrModel.selectedItemsMCR)
            self.node.widget.tree.blockSignals(False)
            self.combineType.setCurrentIndex(cco.COMBINE_MCR_ALS)

    def cancelPendingProps(self):
        ind = self.combineType.currentIndex()
        if ind == cco.COMBINE_MCR_ALS:
            self.mcrData[self.mcrModel.pendingRow]['initialS'] = initialMCR[0]
            self.mcrData[self.mcrModel.pendingRow].pop('ref', None)
            self.mcrData[self.mcrModel.pendingRow].pop('refalias', None)
            self.mcrModel.updateAll()

    def setPlotVisible(self, plot, checked):
        plot.setVisible(checked)

    def getRef(self, data):
        self.mcrData[self.mcrModel.pendingRow]['refalias'] = data.alias
        arrName = self.combineArray.currentText()
        xi = getattr(data, self.pcaNames[0])
        arr = getattr(data, arrName)
        self.mcrData[self.mcrModel.pendingRow]['ref'] = xi, arr
        self.mcrModel.updateAll()
        self.updateMCR()

    def plotPCASlot(self, msg):
        pass
        # if msg['event'] == 'mouseClicked':
        #     N = round(msg['x'])
        #     self.combineN.setValue(N)

    def updatePCA(self):
        if len(csi.selectedItems) < 2:
            self.plotPCA.clearCurves()
            self.D = None
            return
        ind = self.combineType.currentIndex()
        if ind not in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE,
                       cco.COMBINE_MCR_ALS):
            self.plotPCA.clearCurves()
            self.D = None
            return

        if self.node is not None:
            nodes = list(csi.nodes.keys())
            nind = nodes.index(self.node.name)
            for idata, data in enumerate(csi.selectedItems):
                dind = nodes.index(data.originNodeName)
                if nind < dind:
                    self.plotPCA.clearCurves()
                    self.D = None
                    return

        res = self.getPCA()
        if res is None:
            return
        w, v, IE, IND = res
        self.replotPCA(w[::-1], IE, IND)

        ind = self.combineType.currentIndex()
        isMCR = ind == cco.COMBINE_MCR_ALS
        if isMCR:
            self.updateMCR()

    def getD(self, items=None, interpolateTo=0):
        if items is None:
            items = csi.selectedItems
        x = getattr(items[interpolateTo], self.pcaNames[0])
        arrName = self.combineArray.currentText()
        interpolate = self.combineInterpolateCB.isChecked()
        if interpolate:
            arrays = []
            for idata, data in enumerate(items):
                try:
                    arr = getattr(data, arrName)
                    xi = getattr(data, self.pcaNames[0])
                except AttributeError:
                    continue
                interp = interp1d(xi, arr, fill_value="extrapolate",
                                  assume_sorted=True)
                arrays.append(interp(x))
        else:
            arrays = []
            for idata, data in enumerate(items):
                try:
                    arr = getattr(data, arrName)
                except AttributeError:
                    continue
                if idata == 0:
                    len0 = len(arr)
                else:
                    if len0 != len(arr):
                        dName = '.'.join((data.alias, arrName))
                        msg = 'Array {0} differs in length from the others. '\
                            'Forced "interpolate".'.format(dName)
                        print(msg)
                        self.combineInterpolateCB.setChecked(True)
                        return self.getPCA(items, interpolateTo)
                arrays.append(arr)

        if interpolateTo == -1:
            arrays = arrays[:len(csi.selectedItems)]
        D = np.array([ar for ar in arrays if ar is not None]).T

        if self.xRangeWidget:
            ran = self.xRangeWidget.getRange()
        else:
            ran = None
        if ran is None or ran == 'auto':
            ran = [x[0], x[-1]]
        elif ran[0] is None:
            ran[0] = x[0]
        elif ran[1] is None:
            ran[1] = x[-1]
        where = (x >= ran[0]) & (x <= ran[1])
        self.xD = x[where]
        self.D = D[where, :]

    def getPCA(self, items=None, interpolateTo=0):
        try:
            self.getD(items, interpolateTo)
        except AttributeError:  # when only empty groups are present
            return
        k, nN = self.D.shape
        eigvals = 0, nN-1
        w, v, IE, IND = uma.make_PCA(self.D, eigvals, get_indicators=True)
        return w, v, IE, IND

    def replotPCA(self, w, IE, IND):
        legend = 'scree plot (left Y)'
        curve = self.plotPCA.getCurve(legend)
        x, y = np.arange(len(w))+1, w
        if curve is None:
            curve = self.plotPCA.addCurve(x, y, legend=legend)
            curve.setColor('C0')
            curve.setLineStyle(self.deflinestyle['linestyle'])
            curve.setLineWidth(self.deflinestyle['linewidth'])
            curve.setSymbol(self.deflinestyle['symbol'])
            curve.setSymbolSize(self.deflinestyle['symbolsize'])
        else:
            curve.setData(x, y)

        # legend = 'Malinowsky imbedded error IE'
        # curve = self.plotPCA.getCurve(legend)
        # x, y = np.arange(len(IE))+1, IE
        # if curve is None:
        #     curve = self.plotPCA.addCurve(
        #         x, y, legend=legend, symbol='o', color='C1')
        # else:
        #     curve.setData(x, y)

        legend = 'Malinowsky indicator IND (right Y)'
        curve = self.plotPCA.getCurve(legend)
        x, y = np.arange(len(IND))+1, IND
        if curve is None:
            curve = self.plotPCA.addCurve(x, y, yaxis='right', legend=legend)
            curve.setColor('C3')
            curve.setLineStyle(self.deflinestyle['linestyle'])
            curve.setLineWidth(self.deflinestyle['linewidth'])
            curve.setSymbol(self.deflinestyle['symbol'])
            curve.setSymbolSize(self.deflinestyle['symbolsize'])
        else:
            curve.setData(x, y)

        legend = 'min IND'
        marker = self.plotPCA.getCurve(legend)
        x = IND.argmin() + 1
        if marker is None:
            marker = self.plotPCA.addXMarker(
                x, legend, 'min IND', '#009000', yaxis='right')
        else:
            marker.setPosition(x, 0)
        marker.setText(f'min IND\nk={x}')

        minLim, _ = self.plotPCA.getGraphYLimits('left')
        self.plotPCA.setGraphYLimits(minLim, 1, 'left')

    def xRangeChanged(self):
        self.getD()
        self.updateMCR()

    def updateMCR(self):
        if self.D is None:
            self.getD()
        if self.D.shape[1] < 2:
            return

        N = self.combineN.value()
        mcrData = self.mcrData[:N]

        retErrors = False
        self.mcrTasker.prepare(self.node, self.xD, self.D, mcrData, retErrors)
        self.mcrThread.start()

    def doneMCR(self):
        C = self.mcrTasker.C
        S = self.mcrTasker.S
        self.replotMCRC(C)
        self.replotMCRS(S)
        # if len(self.mcrData) > 1 and self.mcrData[1]['constraintCKind'] == '<':
        #     bname = 'c:/ParSeq/parseq/tests/data/MCR-ALS/'
        #     fn = '{0:02.0f}.dat.gz'.format(
        #         self.mcrData[1]['constraintCValue']*100)
        #     np.savetxt(bname+'C'+fn, C)
        #     np.savetxt(bname+'S'+fn, S)
        #     np.savetxt(bname+'x.dat.gz', self.xD)
        #     np.savetxt(bname+'D.dat.gz', self.D)

    def replotMCRC(self, C):
        self.plotMCR.clearCurves()
        if C is None:
            return
        n, N = C.shape
        x = np.arange(n) + 1
        for iC in range(N):
            y = C[:, iC]
            if len(y) != len(x):
                continue
            legend = f'C{iC+1}'
            curve = self.plotMCR.getCurve(legend)
            if curve is None:
                curve = self.plotMCR.addCurve(x, y, legend=legend)
                curve.setColor(f'C{iC % 10}')
                curve.setLineStyle(self.deflinestyle['linestyle'])
                curve.setLineWidth(self.deflinestyle['linewidth'])
                curve.setSymbol(self.deflinestyle['symbol'])
                curve.setSymbolSize(self.deflinestyle['symbolsize'])
            else:
                curve.setData(x, y)

        # minLim, _ = self.plotMCR.getGraphYLimits('left')
        self.plotMCR.setGraphYLimits(0, 1, 'left')

    def replotMCRS(self, S):
        if self.node.plotDimension != 1:
            return
        plot = self.node.widget.plot
        if S is not None and len(S.shape) == 2:
            x = self.xD
            N = S.shape[1]
            for iS in range(N):
                y = S[:, iS]
                if len(y) != len(x):
                    continue
                legend = f'temporal MCR-ALS S{iS+1}'
                curve = plot.getCurve(legend)
                if curve is None:
                    curve = plot.addCurve(x, y, legend=legend)
                    curve.setColor(f'C{iS % 10}')
                    curve.setLineStyle(self.deflinestyle['linestyle'])
                    curve.setLineWidth(self.deflinestyle['linewidth'])
                    curve.setSymbol(self.deflinestyle['symbol'])
                    curve.setSymbolSize(self.deflinestyle['symbolsize'])
                else:
                    curve.setData(x, y)
        else:
            N = 0

        for item in plot.getItems():
            legend = item.getName()
            if legend.startswith('temporal MCR-ALS'):
                sN = legend.split()[-1]
                if sN.startswith('S'):
                    try:
                        vN = eval(sN[1:])
                        if vN > N:
                            plot.removeItem(item)
                    except Exception:
                        pass

    def createCombined(self):
        if self.node is None:
            return
        ind = self.combineType.currentIndex()
        if ind < 1:
            return

        madeOf = list(csi.selectedItems)
        isPCA = ind in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE)
        isMCR = ind in (cco.COMBINE_MCR_ALS,)
        if isPCA or isMCR:
            # msgBox = qt.QMessageBox()
            # msgBox.information(self, 'Not implemented',
            #                    'PCA is not implemented yet',
            #                    buttons=qt.QMessageBox.Close)
            # return
            NPCA = self.combineN.value()
        elif ind == cco.COMBINE_TT:
            self.selectedItemsTT = madeOf  # selection will change
            self.node.widget.preparePickData(self, 'Pick basis set')
            return

        # isStopHere = self.stopHereCB.isChecked()
        isStoppedAt = self.combineStopCB.isChecked()
        kw = dict(dataFormat={'combine': ind},
                  originNodeName=self.node.name,
                  runDownstream=False)
        dformat = kw['dataFormat']
        if isStoppedAt:
            for it in csi.selectedItems:
                it.terminalNodeName = self.combineStop.currentText()
                it.colorTag = 0
                it.set_auto_color_tag()
        isMoveToGroup = self.combineMoveToGroupCB.isChecked()

        model = self.node.widget.tree.model()
        model.beginResetModel()
        if isPCA:
            res = self.getPCA()
            if res is None:
                return
            wPCA, vPCA = res[:2]
            dformat['NPCA'] = NPCA
            dformat['wPCA'] = wPCA[::-1]
            dformat['vPCA'] = vPCA[:, ::-1]
            ci = self.combineInterpolateCB.isChecked()  # after self.getPCA()!
            dformat['combineInterpolate'] = ci
            # arrName = self.combineArray.currentText()
            # dformat['arrName'] = arrName
            for idata, data in enumerate(madeOf):
                dformat['iSpectrumPCA'] = idata
                grPCA = data.parentItem.insert_item(
                    '{0}-PCA{1}'.format(data.alias, NPCA), data.row()+1,
                    colorPolicy='gradient')
                grPCA.wPCA = wPCA[::-1]
                newItems = []
                for i in range(NPCA):
                    dformat['iPCA'] = i
                    kw['alias'] = '{0}-PCA{1}_{2}'.format(data.alias, NPCA, i+1)
                    newItem = grPCA.insert_item(madeOf, **kw)
                    newItems.append(newItem)
                grPCA.color1 = COLOR_GRADIENT_PCA1
                grPCA.color2 = COLOR_GRADIENT_PCA2
                grPCA.init_colors(grPCA.childItems)
                ctr.run_transforms(newItems, grPCA, runParallel=False)
        elif isMCR:
            NMCR = self.combineN.value()
            # arrName = self.combineArray.currentText()
            # dformat['arrName'] = arrName
            dformat['MCR-ALS-revCTC'] = np.array(self.mcrTasker.revCTC)
            dformat['MCR-ALS-C'] = np.array(self.mcrTasker.C)
            mcrDataOut = []
            for d in self.mcrData[:NMCR]:
                dout = {key: d[key] for key in defaultMCRDict.keys()}
                if d['initialS'] == initialMCR[-1]:
                    try:
                        dout['refalias'] = d['refalias']
                    except KeyError:
                        model.endResetModel()
                        model.updateAll()
                        return
                mcrDataOut.append(dout)
            dformat['MCR-ALS'] = mcrDataOut

            names = [it.alias for it in madeOf]
            cNames = cco.combine_names(names)
            if madeOf[0].parentItem is csi.dataRootItem:
                parentItem = csi.dataRootItem
                row = madeOf[0].row() + 1
            else:
                parentItem = madeOf[0].parentItem.parentItem
                row = madeOf[0].parentItem.row() + 1
            grMCR = parentItem.insert_item(
                'MCR-ALS-{0}-N{1}'.format(cNames, NMCR), row,
                colorPolicy='loop1')
            grMCR.MCRC = dformat['MCR-ALS-C']

            newItems = []
            for i in range(NPCA):
                dformat['iMCR'] = i
                kw['alias'] = '{0}-MCR-ALS-S{1}'.format(cNames, i+1)
                kw['color'] = gco.colorCycle1[i % 10]
                newItem = grMCR.insert_item(madeOf, **kw)
                newItems.append(newItem)
            ctr.run_transforms(newItems, grMCR, runParallel=False)
        else:
            last = csi.selectedItems[-1]
            pit = last.parentItem
            newItem = pit.insert_item(madeOf, last.row()+1, **kw)
            if newItem.state[self.node.name] == cco.DATA_STATE_GOOD:
                ctr.run_transforms([newItem], pit)

        model.endResetModel()
        model.updateAll()
        if isMoveToGroup:
            self.node.widget.tree.groupItems()
        if isMCR:
            model.selectItems(newItems)
        else:
            model.selectItems(madeOf)
