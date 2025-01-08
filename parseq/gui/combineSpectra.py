# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Dec 2024"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

# from ..core import spectra as csp
from ..core import singletons as csi
from ..core import transforms as ctr
from ..core import commons as cco
from .propWidget import PropWidget
from . import propsOfData as gpd

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
        self.combineInterpolateCB = qt.QCheckBox(u"interpolate")
        self.combineInterpolateCB.setToolTip(
            "interpolate all selected data\nto the grid of the first data")
        self.combineNLabel = qt.QLabel("N=")
        self.combineN = qt.QSpinBox()
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

#        layout = qt.QVBoxLayout()
#        layout.addWidget(self.combineType)
#        layout.addWidget(self.combineStopCB)
#        layout.addWidget(self.combineStop)
#        layout.addWidget(self.combineDo)
#        layout.addStretch()
        layout = qt.QGridLayout()
        layout.setContentsMargins(2, 0, 2, 2)
        layout.addWidget(self.combineType, 0, 0)
        layoutN = qt.QHBoxLayout()
        layoutN.addStretch()
        layoutN.addWidget(self.combineNLabel)
        layoutN.addWidget(self.combineN)
        layout.addLayout(layoutN, 0, 1)
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
        model = self.node.widget.tree.model()
        model.invalidateData()

    def combineTypeChanged(self, ind):
        self.combineNLabel.setVisible(ind == cco.COMBINE_PCA)
        self.combineN.setVisible(ind == cco.COMBINE_PCA)
        if ind == cco.COMBINE_PCA:
            self.combineN.setMaximum(len(csi.selectedItems))
        elif ind == cco.COMBINE_TT:
            self.combineStopCB.setChecked(False)
            self.combineStop.setVisible(False)
            self.combineMoveToGroupCB.setChecked(False)
        self.combineStopCB.setEnabled(ind != cco.COMBINE_TT)
        self.combineMoveToGroupCB.setEnabled(ind != cco.COMBINE_TT)

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
        if ind == cco.COMBINE_PCA:
            self.combineN.setMaximum(len(csi.selectedItems))

    def updateDataFromUI(self):
        self.createCombined()

    def createCombined(self):
        if self.node is None:
            return
        ind = self.combineType.currentIndex()
        if ind < 1:
            return

        madeOf = list(csi.selectedItems)
        if ind == cco.COMBINE_PCA:
            # msgBox = qt.QMessageBox()
            # msgBox.information(self, 'Not implemented',
            #                    'PCA is not implemented yet',
            #                    buttons=qt.QMessageBox.Close)
            # return
            nPCA = self.combineN.value()
        elif ind == cco.COMBINE_TT:
            self.selectedItemsTT = madeOf
            self.node.widget.preparePickData(self, 'Pick basis set')
            return

        # isStopHere = self.stopHereCB.checkState() == qt.Qt.Checked
        isStoppedAt = self.combineStopCB.checkState() == qt.Qt.Checked
        ci = self.combineInterpolateCB.checkState() == qt.Qt.Checked
        kw = dict(dataFormat={'combine': ind, 'combineInterpolate': ci},
                  colorTag=ind, originNodeName=self.node.name,
                  runDownstream=False)
        if isStoppedAt:
            for it in csi.selectedItems:
                it.terminalNodeName = self.combineStop.currentText()
                it.colorTag = 0
                it.set_auto_color_tag()
        isMoveToGroup = self.combineMoveToGroupCB.checkState() == qt.Qt.Checked

        model = self.node.widget.tree.model()
        model.beginResetModel()
        if ind == cco.COMBINE_PCA:
            kw['dataFormat']['nPCA'] = nPCA
            for idata, data in enumerate(madeOf):
                grPCA = data.parentItem.insert_item(
                    '{0}-PCA{1}'.format(data.alias, nPCA),
                    data.row()+1, colorPolicy='gradient')
                newItems = []
                for i in range(nPCA):
                    kw['dataFormat']['iSpectrumPCA'] = idata
                    kw['dataFormat']['iPCA'] = i
                    kw['alias'] = '{0}-PCA{1}_{2}'.format(data.alias, nPCA, i)
                    newItem = grPCA.insert_item(madeOf, **kw)
                    newItems.append(newItem)
                grPCA.color1 = COLOR_GRADIENT_PCA1
                grPCA.color2 = COLOR_GRADIENT_PCA2
                grPCA.init_colors(grPCA.childItems)
                if idata == 0:
                    ctr.run_transforms(newItems[0:1], grPCA, runParallel=False)
                    for idata, data in enumerate(madeOf):
                        data.skip_eigh = True
                    ctr.run_transforms(newItems[1:], grPCA, runParallel=False)
                else:
                    ctr.run_transforms(newItems, grPCA, runParallel=False)
            for idata, data in enumerate(madeOf):
                del data.skip_eigh
        else:
            last = csi.selectedItems[-1]
            pit = last.parentItem
            newItem = pit.insert_item(madeOf, last.row()+1, **kw)
            if newItem.state[self.node.name] == cco.DATA_STATE_GOOD:
                ctr.run_transforms([newItem], pit)
        model.endResetModel()
        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

        if isMoveToGroup:
            self.node.widget.tree.groupItems()
        model.selectItems(madeOf)

    def applyPendingProps(self):
        ci = self.combineInterpolateCB.checkState() == qt.Qt.Checked
        ind = cco.COMBINE_TT
        kw = dict(dataFormat={'combine': ind, 'combineInterpolate': ci},
                  colorTag=ind, color='#ee00ee',
                  originNodeName=self.node.name, runDownstream=False)

        model = self.node.widget.tree.model()
        model.beginResetModel()

        madeOf = list(csi.selectedItems)
        for idata, data in enumerate(self.selectedItemsTT):
            kw['alias'] = '{0}-TT{1}'.format(data.alias, len(madeOf))
            newItem = data.parentItem.insert_item(
                madeOf+[data], data.row()+1, **kw)
            ctr.run_transforms([newItem], newItem.parentItem)

        model = self.node.widget.tree.model()
        model.selectItems(self.selectedItemsTT)
