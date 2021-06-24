# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

from ..core import singletons as csi
# from ..core import commons as cco
from ..core import spectra as csp
from ..third_party import xrt

columnWidths = (120, 80, 65, 60)


class CalibrationModel(qt.QAbstractTableModel):
    def __init__(self, dataCollection=None, header=None, formatStr='{0}'):
        super(CalibrationModel, self).__init__()
        self.headerList = header if header is not None else []
        self.formatStr = formatStr
        self.setDataCollection(dataCollection)

    def rowCount(self, parent=qt.QModelIndex()):
        if len(self.dataCollection) == 0:
            return 0
        return len(self.dataCollection['base'])

    def columnCount(self, parent):
        return max(len(self.dataCollection), len(self.headerList))

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        if index.column() < 3:
            return qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        else:
            return qt.Qt.ItemIsEnabled

    def data(self, index, role=qt.Qt.DisplayRole):
        if len(self.dataCollection) == 0:
            return
        if not index.isValid():
            return
        column, row = index.column(), index.row()
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            try:
                if column == 0:  # base
                    res = self.dataCollection['base'][row]
                    if isinstance(res, csp.Spectrum):
                        return self.dataCollection['base'][row].alias
                    else:
                        return res
                elif column == 1:  # E
                    return self.dataCollection['energy'][row]
                elif column == 2:  # DCM
                    res = self.dataCollection['DCM'][row]
                    return res if res in xrt.crystals.keys() else 'none'
                elif column == 3:  # fwhm
                    res = self.dataCollection['FWHM'][row]
                    return self.formatStr.format(res)
            except (IndexError, TypeError):
                return '---'
        elif role == qt.Qt.ToolTipRole:
            if column == 3:  # fwhm
                return '(eV)'

    def setData(self, index, value, role=qt.Qt.EditRole):
        if len(self.dataCollection) == 0:
            return
        if role == qt.Qt.EditRole:
            column, row = index.column(), index.row()
            if column == 0:
                for item in csi.allLoadedItems:
                    if value == item.alias:
                        break
                else:
                    return False
            if column == 0:  # base
                self.dataCollection['base'][row] = value
            elif column == 1:  # E
                self.dataCollection['energy'][row] = value
            elif column == 2:  # DCM
                self.dataCollection['DCM'][row] = value
            self.dataChanged.emit(index, index)
            return True
        return False

    def headerData(self, section, orientation, role):
        if orientation != qt.Qt.Horizontal:
            return
        if role == qt.Qt.DisplayRole:
            if section < len(self.headerList):
                return self.headerList[section]
            else:
                return section
        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignHCenter

    def setDataCollection(self, dataCollection=None):
        self.beginResetModel()
        if dataCollection is None:
            self.dataCollection = {}
        else:
            self.dataCollection = dataCollection
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())


class ComboDelegate(qt.QItemDelegate):
    def createEditor(self, parent, option, index):
        combo = qt.QComboBox(parent)
        combo.addItems(list(xrt.crystals.keys()) + ['none'])
        combo.currentIndexChanged.connect(self.currentIndexChanged)
        return combo

    def setEditorData(self, editor, index):
        editor.blockSignals(True)
        ind = editor.findText(index.model().data(index))
        if ind < 0:
            editor.setCurrentIndex(editor.count() - 1)
        else:
            editor.setCurrentIndex(ind)
        editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText())

    def currentIndexChanged(self):
        self.commitData.emit(self.sender())


class CalibrateTableView(qt.QTableView):
    def __init__(self, parent, model):
        super(CalibrateTableView, self).__init__(parent)
        self.setModel(model)

        horHeaders = self.horizontalHeader()  # QHeaderView instance
        verHeaders = self.verticalHeader()  # QHeaderView instance

        if 'pyqt4' in qt.BINDING.lower():
            horHeaders.setMovable(False)
            for i in range(4):
                horHeaders.setResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setClickable(True)
        else:
            horHeaders.setSectionsMovable(False)
            for i in range(4):
                horHeaders.setSectionResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setSectionsClickable(True)
        horHeaders.setStretchLastSection(False)
        horHeaders.setMinimumSectionSize(20)

        self.setItemDelegateForColumn(2, ComboDelegate(self))
        for i in range(4):
            self.setColumnWidth(i, columnWidths[i])
        self.setMinimumHeight(
            horHeaders.height() + 2*verHeaders.sectionSize(0) + 2)
        self.setMinimumWidth(sum(columnWidths) + 10)


class CalibrateEnergyWidget(qt.QWidget):
    def __init__(self, parent=None, dataCollection=None, formatStr='{0}'):
        super(CalibrateEnergyWidget, self).__init__(parent)

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layoutB = qt.QHBoxLayout()
        self.autoSetButton = qt.QPushButton('auto set references')
        # self.autoSetButton.setMinimumWidth(120)
        layoutB.addWidget(self.autoSetButton)
        self.clearButton = qt.QPushButton('clear')
        self.clearButton.setMinimumWidth(36)
        self.clearButton.clicked.connect(self.clear)
        layoutB.addWidget(self.clearButton)
        self.acceptButton = qt.QPushButton('accept')
        self.acceptButton.setMinimumWidth(46)
        layoutB.addWidget(self.acceptButton)
        layoutB.addStretch()

        layout.addLayout(layoutB)

        header = ['reference data', 'energy', 'DCM', 'FWHM']
        self.calibrationModel = CalibrationModel(
            dataCollection, header, formatStr)
        self.table = CalibrateTableView(self, self.calibrationModel)

        layout.addWidget(self.table)

        self.setLayout(layout)

    def clear(self):
        self.calibrationModel.setDataCollection()

    def getCalibrationData(self):
        return self.calibrationModel.dataCollection

    def setCalibrationData(self, data):
        dtparams = data.transformParams
        self.calibrationModel.setDataCollection(dtparams['calibrationData'])

    def setData(self, prop):
        if len(csi.selectedItems) == 0:
            return
        it = csi.selectedItems[0]
        self.setCalibrationData(it)
