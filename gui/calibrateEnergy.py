# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from functools import partial

from silx.gui import qt

from ..core import singletons as csi
# from ..core import commons as cco
from ..core import spectra as csp
from ..third_party import xrt

HEADERS = ['reference data', 'slice', 'energy', 'DCM', 'FWHM']
columnWidths = (114, 44, 64, 64, 54)


class CalibrationModel(qt.QAbstractTableModel):
    def __init__(self, dataCollection=None, header=None, formatStr='{0}'):
        super().__init__()
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
        if index.column() < 4:
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
                elif column == 1:  # slice
                    return self.dataCollection['slice'][row]
                elif column == 2:  # E
                    return self.dataCollection['energy'][row]
                elif column == 3:  # DCM
                    res = self.dataCollection['DCM'][row]
                    return res if res in xrt.crystals.keys() else 'none'
                elif column == 4:  # fwhm
                    if 'FWHM' not in self.dataCollection:
                        return
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
            elif column == 1:  # slice
                self.dataCollection['slice'][row] = value
            elif column == 2:  # E
                self.dataCollection['energy'][row] = value
            elif column == 3:  # DCM
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
        elif role == qt.Qt.ToolTipRole:
            if section == 0:
                return('data name (alias) of elastic scans')
            elif section == 1:
                return('data slice if needed, otherwise :')
            elif section == 2:
                return('formal energy value')
            elif section == 3:
                return('crystals for calculating\nFWHM of DCM bandwidth')

    def setDataCollection(self, dataCollection=None):
        self.beginResetModel()
        if dataCollection is None:
            self.dataCollection = {}
        else:
            self.dataCollection = dict(dataCollection)
        if ('slice' not in self.dataCollection  # added later
                and 'base' in self.dataCollection):
            self.dataCollection['slice'] = \
                [':'] * len(self.dataCollection['base'])
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())


class ComboDelegate(qt.QItemDelegate):
    def createEditor(self, parent, option, index):
        combo = qt.QComboBox(parent)
        combo.addItems(list(xrt.crystals.keys()) + ['none'])
        combo.currentIndexChanged.connect(
            partial(self.currentIndexChanged, combo))
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

    def currentIndexChanged(self, combo):
        self.commitData.emit(combo)


class CalibrateTableView(qt.QTableView):
    def __init__(self, parent, model):
        super().__init__(parent)
        self.setModel(model)

        horHeaders = self.horizontalHeader()  # QHeaderView instance
        verHeaders = self.verticalHeader()  # QHeaderView instance

        if 'pyqt4' in qt.BINDING.lower():
            horHeaders.setMovable(False)
            horHeaders.setResizeMode(0, qt.QHeaderView.Stretch)
            for i in range(1, len(columnWidths)):
                horHeaders.setResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setClickable(True)
        else:
            horHeaders.setSectionsMovable(False)
            horHeaders.setSectionResizeMode(0, qt.QHeaderView.Stretch)
            for i in range(1, len(columnWidths)):
                horHeaders.setSectionResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setSectionsClickable(True)
        horHeaders.setStretchLastSection(False)
        horHeaders.setMinimumSectionSize(20)

        self.setItemDelegateForColumn(3, ComboDelegate(self))
        for i, cw in enumerate(columnWidths):
            self.setColumnWidth(i, int(cw*csi.screenFactor))
        self.setMinimumHeight(
            horHeaders.height() + 2*verHeaders.sectionSize(0) + 2)
        self.setMinimumWidth(int(sum(columnWidths)*csi.screenFactor) + 10)


class CalibrateEnergyWidget(qt.QWidget):
    def __init__(self, parent=None, dataCollection=None, formatStr='{0}'):
        super().__init__(parent)

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layoutB = qt.QHBoxLayout()
        self.autoSetButton = qt.QPushButton('auto set references')
        # self.autoSetButton.setMinimumWidth(120)
        layoutB.addWidget(self.autoSetButton)
        self.addButton = qt.QPushButton('add')
        self.addButton.setMinimumWidth(int(12*csi.screenFactor))
        self.addButton.clicked.connect(self.add)
        layoutB.addWidget(self.addButton)
        self.clearButton = qt.QPushButton('clear')
        self.clearButton.setMinimumWidth(int(36*csi.screenFactor))
        self.clearButton.clicked.connect(self.clear)
        layoutB.addWidget(self.clearButton)
        self.acceptButton = qt.QPushButton('accept')
        self.acceptButton.setMinimumWidth(int(46*csi.screenFactor))
        layoutB.addWidget(self.acceptButton)
        layoutB.addStretch()

        layout.addLayout(layoutB)

        self.calibrationModel = CalibrationModel(
            dataCollection, HEADERS, formatStr)
        self.table = CalibrateTableView(self, self.calibrationModel)

        layout.addWidget(self.table)

        self.setLayout(layout)

    def add(self):
        col = self.calibrationModel.dataCollection
        if len(col) == 0:
            col['base'] = ['none', 'none']
            col['slice'] = [':', ':']
            col['energy'] = [9000, 10000]
            col['DCM'] = ['Si111', 'Si111']
            col['FWHM'] = [0, 0]
        else:
            col['base'].append('none')
            col['slice'].append(':')
            col['energy'].append(col['energy'][-1] + 20)
            col['DCM'].append(col['DCM'][-1])
            col['FWHM'].append(0)
        self.calibrationModel.setDataCollection(col)

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
