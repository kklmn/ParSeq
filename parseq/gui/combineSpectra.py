# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "23 Apr 2026"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from silx.gui import qt

# from ..core import spectra as csp
from ..core import singletons as csi
from ..core import transforms as ctr
from ..core import commons as cco
from .propWidget import PropWidget
from . import propsOfData as gpd
from .plot import Plot1D
from ..utils import math as uma
from scipy.interpolate import interp1d

COLOR_GRADIENT_PCA1 = 'green'
COLOR_GRADIENT_PCA2 = 'red'


class CombineSpectraWidget(PropWidget):
    def __init__(self, parent=None, node=None):
        super().__init__(parent, node)
        self.selectedItemsTT = []

        combineDataGroup = self.makeCombineDataGroup()
        layout = qt.QVBoxLayout()
        layout.setContentsMargins(4, 2, 2, 0)
        self.stopHereCB = qt.QCheckBox("stop data propagation here")
        self.stopHereCB.clicked.connect(self.doStopHere)
        self.stopHereCB.setEnabled(node is not None)
        layout.addWidget(self.stopHereCB)
        layout.addWidget(combineDataGroup)
        self.plot = Plot1D(self)
        for toolbar in self.plot.findChildren(qt.QToolBar):
            toolbar.hide()
        self.plot.setYAxisLogarithmic(True)
        self.plot.setGraphXLabel(label="k")
        self.plot.setGraphYLabel(label="")
        # self.plot.setAxesMargins(0.1, 0.1, 0.1, 0.1)
        self.plot.setMinimumSize(100, 100)
        self.plot.hide()
        self.plot.sigPlotSignal.connect(self.plotSlot)
        layout.addWidget(self.plot)
        layout.addStretch()
        self.setLayout(layout)
        self.combineTypeChanged(0)
        self.combineStopCBChanged(0)

    def makeCombineDataGroup(self):
        self.combineType = qt.QComboBox()
        self.combineType.addItems(cco.combineNames)
        for itt, tt in enumerate(cco.combineToolTips):
            self.combineType.setItemData(itt, tt, qt.Qt.ToolTipRole)
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
        self.combineStopCB = qt.QCheckBox(
            u"stop propagation of\ncontributing data at:")
        self.combineStopCB.stateChanged.connect(self.combineStopCBChanged)
        self.combineStop = qt.QComboBox()
        self.combineStop.addItems(csi.nodes.keys())
        self.combineMoveToGroupCB = qt.QCheckBox(
            u"move selected data to a new group")
        self.combineDo = qt.QPushButton("Combine")
        self.combineDo.clicked.connect(self.createCombined)
        self.combineDo.setEnabled(len(self.pcaNames) > 1)

        layout = qt.QGridLayout()
        layout.setContentsMargins(2, 0, 2, 2)
        layoutN = qt.QHBoxLayout()
        layoutN.addWidget(self.combineType)
        layoutN.addStretch()
        layoutN.addWidget(self.combineArray)
        layoutN.addWidget(self.combineN)
        layout.addLayout(layoutN, 0, 0, 1, 2)
        layout.addWidget(self.combineInterpolateCB, 1, 0)
        layout.addWidget(self.combineStopCB, 2, 0)
        layout.addWidget(self.combineStop, 2, 1)
        layout.addWidget(self.combineMoveToGroupCB, 3, 0, 1, 2)
        layout.addWidget(self.combineDo, 4, 0, 1, 2)

        group = qt.QGroupBox('combine selected data')
        group.setLayout(layout)
        # group.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
        return group

    def doStopHere(self, checked):
        for it in csi.selectedItems:
            it.terminalNodeName = self.node.name if checked else None
            it.colorTag = 0
            it.set_auto_color_tag()
        if self.node.widget is not None:
            model = self.node.widget.tree.model()
            model.invalidateData()

    def combineTypeChanged(self, ind):
        needA = ind in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE,
                        cco.COMBINE_TT)
        self.combineArray.setVisible(needA)
        needN = ind in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE)
        self.combineN.setVisible(needN)
        if ind == cco.COMBINE_TT:
            self.combineStopCB.setChecked(False)
            self.combineStop.setVisible(False)
            self.combineMoveToGroupCB.setChecked(False)
        self.combineStopCB.setEnabled(ind != cco.COMBINE_TT)
        self.combineMoveToGroupCB.setEnabled(ind != cco.COMBINE_TT)
        self.plot.setVisible(needN)
        if needN:
            self.combineN.setMaximum(len(csi.selectedItems))
            self.updatePCA()

    def combineStopCBChanged(self, state):
        self.combineStop.setVisible(state == qt.Qt.Checked)

    def setUIFromData(self):
        gpd.setCButtonFromData(self.stopHereCB, 'terminalNodeName',
                               compareWith=self.node.name)
        gpd.setComboBoxFromData(self.combineType, 'dataFormat.combine')
        gpd.setCButtonFromData(
            self.combineInterpolateCB, 'dataFormat.combineInterpolate')
        gpd.setCButtonFromData(self.combineStopCB, 'terminalNodeName')
        gpd.setComboBoxFromData(self.combineStop, 'terminalNodeName',
                                compareWith=list(csi.nodes.keys()))
        ind = self.combineType.currentIndex()
        needN = ind in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE)
        if needN:
            self.combineN.setMaximum(len(csi.selectedItems))
            self.updatePCA()

    def updateDataFromUI(self):
        self.createCombined()

    def createCombined(self):
        if self.node is None:
            return
        ind = self.combineType.currentIndex()
        if ind < 1:
            return

        madeOf = list(csi.selectedItems)
        isPCA = ind in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE)
        if isPCA:
            # msgBox = qt.QMessageBox()
            # msgBox.information(self, 'Not implemented',
            #                    'PCA is not implemented yet',
            #                    buttons=qt.QMessageBox.Close)
            # return
            NPCA = self.combineN.value()
        elif ind == cco.COMBINE_TT:
            self.selectedItemsTT = madeOf  # selection will change
            if self.node.widget is not None:
                self.node.widget.preparePickData(self, 'Pick basis set')
            return

        # isStopHere = self.stopHereCB.isChecked()
        isStoppedAt = self.combineStopCB.isChecked()
        kw = dict(dataFormat={'combine': ind},
                  colorTag=ind, originNodeName=self.node.name,
                  runDownstream=False)
        if isStoppedAt:
            for it in csi.selectedItems:
                it.terminalNodeName = self.combineStop.currentText()
                it.colorTag = 0
                it.set_auto_color_tag()
        isMoveToGroup = self.combineMoveToGroupCB.isChecked()

        if self.node.widget is not None:
            model = self.node.widget.tree.model()
            model.beginResetModel()
        if isPCA:
            wPCA, vPCA = self.getPCA()[:2]
            kw['dataFormat']['NPCA'] = NPCA
            kw['dataFormat']['wPCA'] = wPCA[::-1]
            kw['dataFormat']['vPCA'] = vPCA[:, ::-1]
            ci = self.combineInterpolateCB.isChecked()  # after self.getPCA()!
            kw['dataFormat']['combineInterpolate'] = ci
            # arrName = self.combineArray.currentText()
            # kw['dataFormat']['arrName'] = arrName
            for idata, data in enumerate(madeOf):
                kw['dataFormat']['iSpectrumPCA'] = idata
                grPCA = data.parentItem.insert_item(
                    '{0}-PCA{1}'.format(data.alias, NPCA),
                    data.row()+1, colorPolicy='gradient')
                grPCA.wPCA = wPCA[::-1]
                newItems = []
                for i in range(NPCA):
                    kw['dataFormat']['iPCA'] = i
                    kw['alias'] = '{0}-PCA{1}_{2}'.format(data.alias, NPCA, i+1)
                    newItem = grPCA.insert_item(madeOf, **kw)
                    newItems.append(newItem)
                grPCA.color1 = COLOR_GRADIENT_PCA1
                grPCA.color2 = COLOR_GRADIENT_PCA2
                grPCA.init_colors(grPCA.childItems)
                ctr.run_transforms(newItems, grPCA, runParallel=False)
        else:
            last = csi.selectedItems[-1]
            pit = last.parentItem
            newItem = pit.insert_item(madeOf, last.row()+1, **kw)
            if newItem.state[self.node.name] == cco.DATA_STATE_GOOD:
                ctr.run_transforms([newItem], pit)
        if self.node.widget is not None:
            model.endResetModel()
            model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            if isMoveToGroup:
                self.node.widget.tree.groupItems()
            model.selectItems(madeOf)

    def applyPendingProps(self):
        ind = cco.COMBINE_TT
        kw = dict(dataFormat={'combine': ind},
                  colorTag=ind, color='#ee00ee',
                  originNodeName=self.node.name, runDownstream=False)

        if self.node.widget is not None:
            model = self.node.widget.tree.model()
            model.beginResetModel()

        items = csi.selectedItems + self.selectedItemsTT
        wPCA, vPCA = self.getPCA(items, interpolateTo=-1)[:2]
        kw['dataFormat']['wPCA'] = wPCA[::-1]
        kw['dataFormat']['vPCA'] = vPCA[:, ::-1]
        ci = self.combineInterpolateCB.isChecked()  # after self.getPCA()!
        kw['dataFormat']['combineInterpolate'] = ci
        madeOf = list(csi.selectedItems)
        for idata, data in enumerate(self.selectedItemsTT):
            kw['alias'] = '{0}-TT{1}'.format(data.alias, len(madeOf))
            it = data.parentItem.insert_item(madeOf+[data], data.row()+1, **kw)
            ctr.run_transforms([it], it.parentItem)

        if self.node.widget is not None:
            model = self.node.widget.tree.model()
            model.selectItems(self.selectedItemsTT)

    def plotSlot(self, msg):
        if msg['event'] == 'mouseClicked':
            N = round(msg['x'])
            self.combineN.setValue(N)

    def updatePCA(self):
        if len(csi.selectedItems) < 2:
            self.plot.clearCurves()
            return
        ind = self.combineType.currentIndex()
        if ind not in (cco.COMBINE_PCA_CLASSIC, cco.COMBINE_PCA_CUMULATIVE):
            self.plot.clearCurves()
            return

        if self.node is not None:
            nodes = list(csi.nodes.keys())
            nind = nodes.index(self.node.name)
            for idata, data in enumerate(csi.selectedItems):
                dind = nodes.index(data.originNodeName)
                if nind < dind:
                    self.plot.clearCurves()
                    return

        w, v, IE, IND = self.getPCA()
        self.plotPCA(w[::-1], IE, IND)

    def getPCA(self, items=None, interpolateTo=0):
        if items is None:
            items = csi.selectedItems
        arrName = self.combineArray.currentText()
        interpolate = self.combineInterpolateCB.isChecked()
        if interpolate:
            x0 = getattr(items[interpolateTo], self.pcaNames[0])
            for idata, data in enumerate(items):
                x = getattr(data, self.pcaNames[0])
                arr = getattr(data, arrName)
                if idata == 0:
                    x0 = x
                    arrays = [arr]
                else:
                    interp = interp1d(x, arr, fill_value="extrapolate",
                                      assume_sorted=True)
                    arrays.append(interp(x0))
        else:
            arrays = []
            for idata, data in enumerate(items):
                arr = getattr(data, arrName)
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
        k, nN = D.shape
        eigvals = 0, nN-1
        w, v, IE, IND = uma.make_PCA(D, eigvals, get_indicators=True)
        return w, v, IE, IND

    def plotPCA(self, w, IE, IND):
        legend = 'scree plot'
        curve = self.plot.getCurve(legend)
        x, y = np.arange(len(w))+1, w
        if curve is None:
            curve = self.plot.addCurve(
                x, y, legend=legend, symbol='o', symbolsize=4, color='C0')
        else:
            curve.setData(x, y)

        # legend = 'Malinowsky imbedded error IE'
        # curve = self.plot.getCurve(legend)
        # x, y = np.arange(len(IE))+1, IE
        # if curve is None:
        #     curve = self.plot.addCurve(
        #         x, y, legend=legend, symbol='o', symbolsize=4, color='C1')
        # else:
        #     curve.setData(x, y)

        legend = 'Malinowsky indicator IND'
        curve = self.plot.getCurve(legend)
        x, y = np.arange(len(IND))+1, IND
        if curve is None:
            curve = self.plot.addCurve(
                x, y, yaxis='right', legend=legend, symbol='o', symbolsize=4,
                color='C3')
        else:
            curve.setData(x, y)

        legend = 'min IND'
        marker = self.plot.getCurve(legend)
        x = IND.argmin() + 1
        if marker is None:
            marker = self.plot.addXMarker(
                x, legend, 'min IND', '#009000', yaxis='right')
        else:
            marker.setPosition(x, 0)
        marker.setText(f'min IND\nk={x}')

        minLim, _ = self.plot.getGraphYLimits('left')
        self.plot.setGraphYLimits(minLim, 1, 'left')
