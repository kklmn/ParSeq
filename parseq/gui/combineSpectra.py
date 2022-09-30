# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

# from ..core import spectra as csp
from ..core import singletons as csi
from ..core import transforms as ctr
from ..core import commons as cco
from .propWidget import PropWidget
from . import propsOfData as gpd


class CombineSpectraWidget(PropWidget):
    def __init__(self, parent=None, node=None):
        super().__init__(parent, node)
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
        self.combineType.currentIndexChanged.connect(self.combineTypeChanged)
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
        layout.addWidget(self.combineStopCB, 1, 0)
        layout.addWidget(self.combineStop, 1, 1)
        layout.addWidget(self.combineMoveToGroupCB, 2, 0, 1, 2)
        layout.addWidget(self.combineDo, 3, 0, 1, 2)

        group = qt.QGroupBox('combine selected data')
        group.setLayout(layout)
        # group.setSizePolicy(qt.QSizePolicy.Fixed, qt.QSizePolicy.Fixed)
        return group

    def doStopHere(self, checked):
        # print(csi.selectedItems)
        for it in csi.selectedItems:
            it.terminalNodeName = self.node.name if checked else None
            it.colorTag = 0
            it.set_auto_color_tag()
        model = self.node.widget.tree.model()
        model.invalidateData()

    def combineTypeChanged(self, ind):
        self.combineNLabel.setVisible(ind == 3)  # PCA
        self.combineN.setVisible(ind == 3)  # PCA

    def combineStopCBChanged(self, state):
        self.combineStop.setVisible(state == qt.Qt.Checked)

    def setUIFromData(self):
        gpd.setCButtonFromData(self.stopHereCB, 'terminalNodeName',
                               compareWith=self.node.name)
        gpd.setComboBoxFromData(self.combineType, 'dataFormat.combine')
        gpd.setCButtonFromData(self.combineStopCB, 'terminalNodeName')
        gpd.setComboBoxFromData(self.combineStop, 'terminalNodeName',
                                compareWith=list(csi.nodes.keys()))

    def updateDataFromUI(self):
        self.createCombined()

    def createCombined(self):
        if self.node is None:
            return
        ind = self.combineType.currentIndex()
        if ind == 0:
            return
        if ind == cco.COMBINE_PCA:
            msgBox = qt.QMessageBox()
            msgBox.information(self, 'Not implemented',
                               'PCA is not implemented yet',
                               buttons=qt.QMessageBox.Close)
            return
            nPCA = self.combineN.value()  # !!! TODO !!!
#        isStopHere = self.stopHereCB.checkState() == qt.Qt.Checked
        isStoppedAt = self.combineStopCB.checkState() == qt.Qt.Checked
        kw = dict(dataFormat={'combine': ind}, colorTag=ind,
                  originNodeName=self.node.name, runDownstream=False)
        if isStoppedAt:
            for it in csi.selectedItems:
                it.terminalNodeName = self.combineStop.currentText()
        isMoveToGroup = self.combineMoveToGroupCB.checkState() == qt.Qt.Checked
        model = self.node.widget.tree.model()

        model.beginResetModel()
        first = csi.selectedItems[0]
        pit = first.parentItem
        newItem = pit.insert_item(list(csi.selectedItems), first.row(), **kw)
        ctr.run_transforms([newItem], pit)
        model.endResetModel()
        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

        if isMoveToGroup:
            self.node.widget.tree.groupItems()

        mode = qt.QItemSelectionModel.Select | qt.QItemSelectionModel.Rows
        row = newItem.row()
        index = model.createIndex(row, 0, newItem)
        csi.selectionModel.select(index, mode)
