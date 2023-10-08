# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "6 May 2023"
# !!! SEE CODERULES.TXT !!!

import copy
from functools import partial

from ...core import singletons as csi
from ...fits.lcf import LCF
from ...gui import gcommons as gco
from . import gbasefit as gbf

from silx.gui import qt


class LCFModel(qt.QAbstractTableModel):
    """The Qt table model for a Linear Combination Fit in ParSeq. Each row in
    the model represents a spectrum participating in the fit. The weights (`w`)
    are the fitting parameters. Optionally, the spectra may get a shift in
    abscissa also found in the fitting.
    """
    HEADERS = ['ref spectra', 'w', 'w [min, max, δ]', 'w tie', 'w±',
               'Δ{0}', 'Δ{0} [min, max, δ]', 'Δ{0} tie', 'Δ{0}±']
    xName, xUnit = 'E', 'eV'

    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.xVary = worker.xVary
        self.setParams()

    def rowCount(self, parent=qt.QModelIndex()):
        return len(self.params)

    def columnCount(self, parent=qt.QModelIndex()):
        if self.xVary:
            return len(self.HEADERS)
        else:
            return len(self.HEADERS)-4

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        if index.column() == 0:
            res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsUserCheckable
        elif index.column() in (1, 2, 5, 6):  # w, wBounds, dx, dxBounds
            res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable | \
                qt.Qt.ItemIsSelectable
        elif index.column() in (3, 7):  # wtie, dEtie
            res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        elif index.column() in (4, 8):  # wError, dEError
            res = qt.Qt.NoItemFlags
        return res

    def data(self, index, role=qt.Qt.DisplayRole):
        if len(self.params) == 0:
            return
        if not index.isValid():
            return
        column, row = index.column(), index.row()
        ref = self.params[row]
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            if column == 0:  # name
                return ref['name']
            key = 'w' if column in [1, 2, 3, 4] else 'dx'
            keyb = key + 'Bounds'
            lim = ref[keyb]
            fmt = gco.getFormatStr(lim[2])
            if column in (1, 5):  # w, ΔE
                return fmt.format(ref[key])
            elif column in (2, 6):  # w-bounds, dE-bounds
                return '[{0}, {1}, {2}]'.format(*[fmt.format(s) for s in lim])
            elif column in (3, 7):  # wtie, dEtie
                keyt = key + 'tie'
                if keyt in ref:
                    return ref[keyt].replace('dx', 'd{0}'.format(self.xName))
            elif column in (4, 8):  # w-error, ΔE-error
                keye = key + 'Error'
                if keye in ref and ref['use']:
                    return fmt.format(ref[keye])
                else:
                    return '---'
        elif role == qt.Qt.CheckStateRole:
            if column == 0:
                return qt.Qt.Checked if ref['use'] else qt.Qt.Unchecked
        elif role == qt.Qt.TextAlignmentRole:
            if column == 0:
                return qt.Qt.AlignLeft | qt.Qt.AlignVCenter
            else:
                return qt.Qt.AlignHCenter | qt.Qt.AlignVCenter
        elif role == qt.Qt.ToolTipRole:
            if column in [1, 4, 5, 8]:
                key = 'w' if column in [1, 4] else 'dx'
                keyb = key + 'Bounds'
                lim = ref[keyb]
                fmtLonger = gco.getFormatStr(lim[2]*0.001)
                keye = key + 'Error'
                if column in (1, 5):  # w, ΔE
                    return fmtLonger.format(ref[key])
                elif column in (4, 8):  # w-error, ΔE-error
                    keye = key + 'Error'
                    if keye in ref:
                        return fmtLonger.format(ref[keye])
        elif role == qt.Qt.BackgroundRole:
            if column in (3, 7):  # wtie, dEtie
                key = 'w' if column == 3 else 'dx'
                keyt = key + 'tie'
                if keyt in ref:
                    if len(ref[keyt]) < 2:
                        del ref[keyt]
                    else:
                        if self.worker.can_interpret_LCF_tie_str(
                                ref[keyt], self.params):
                            return qt.QColor(gbf.GOOD_BKGND)
                        else:
                            return qt.QColor(gbf.BAD_BKGND)
        elif role == gco.LIMITS_ROLE:  # return min, max, step
            ref = self.params[row]
            if column == 1:  # w
                return ref['wBounds']
            elif column == 5:  # ΔE
                return ref['dxBounds']
            else:
                return

    def setData(self, index, value, role=qt.Qt.EditRole):
        if len(self.params) == 0:
            return
        if role == qt.Qt.EditRole:
            column, row = index.column(), index.row()
            ref = self.params[row]
            key = 'w' if column in [1, 2, 3, 4] else 'dx'
            if column in (1, 5):  # w, ΔE
                ref[key] = float(value)
            elif column in (2, 6):  # wBounds, dEBounds
                try:
                    tmp = eval(value)
                except Exception:
                    return False
                if not isinstance(tmp, (list, tuple)):
                    return False
                keyb = key + 'Bounds'
                ref[keyb] = [float(t) for t in tmp]
            elif column in (3, 7):  # wtie, dEtie
                keyt = key + 'tie'
                if len(value) < 2 and keyt in ref:
                    del ref[keyt]
                else:
                    ref[keyt] = str(value).strip().replace('dE', 'dx')

            self.dataChanged.emit(index, index)
            return True
        elif role == qt.Qt.CheckStateRole:
            column, row = index.column(), index.row()
            if column == 0:
                ref = self.params[row]
                ref['use'] = bool(value)
                self.dataChanged.emit(index, self.index(row, -1))
                return True
        return False

    def headerData(self, section, orientation, role):
        if role == qt.Qt.DisplayRole:
            if orientation == qt.Qt.Horizontal:
                if section < len(self.HEADERS):
                    return self.HEADERS[section].format(self.xName)
                else:
                    return section
            elif orientation == qt.Qt.Vertical:
                return str(section+1)
        elif role == qt.Qt.TextAlignmentRole:
            if orientation == qt.Qt.Horizontal:
                return qt.Qt.AlignCenter
        elif role == qt.Qt.ToolTipRole:
            if orientation == qt.Qt.Horizontal:
                if section == 0:
                    return 'data name (alias) of reference data'
                elif section == 1:
                    return 'weight'
                elif section == 2:
                    return 'weight bounds and step\n'\
                        'click the header to apply a selected cell to all rows'
                elif section == 3:
                    return 'either `fixed` or str starting with = or > or < '\
                        "\nand followed by a Python expression of other w's "\
                        "\nas `w[int]`, where int index is 1-based, same "\
                        "\nas the row number, e.g. `=0.5-w[1]`"
                elif section == 4:
                    return 'fitting error of weight'
                elif section == 5:
                    return 'Δ{0} ({1})'.format(self.xName, self.xUnit)
                elif section == 6:
                    return 'Δ{0} bounds and step ({1})\nclick the header to'\
                        ' apply a selected cell to all rows'.format(
                            self.xName, self.xUnit)
                elif section == 7:
                    return 'either `fixed` or str starting with = or > or < '\
                        "\nand followed by an expression of other Δ{0}'s "\
                        "\nas `d{0}[int]`, where int index is 1-based, same "\
                        "\nas the row number, e.g. `=d{0}[1]`".format(
                            self.xName)
                elif section == 8:
                    return 'fitting error of Δ{0} ({1})'.format(
                        self.xName, self.xUnit)

    def setParams(self, params=None, emit=True):
        self.beginResetModel()
        if params is None:
            self.params = []
        else:
            self.params = params
        self.endResetModel()
        if emit:
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def appendRef(self, name):
        for entry in self.params:
            if entry['name'] == name:
                return
        self.beginResetModel()
        entry = dict(LCF.defaultEntry)
        entry['name'] = name
        self.params.append(entry)
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        wro = self.rowCount()-1
        return wro

    def appendRefs(self, names):
        if not isinstance(names, (list, tuple)):
            names = [names]
        self.beginResetModel()
        for name in names:
            for entry in self.params:
                if entry['name'] == name:
                    continue
            entry = dict(LCF.defaultEntry)
            entry['name'] = name
            self.params.append(entry)
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        wro = self.rowCount()-1
        return wro

    def moveItem(self, index, to):  # to = +1(up) or -1(down)
        if self.rowCount() == 0:
            return
        row = index.row()
        if row == 0 and to == 1:
            wro = self.rowCount()-1
        elif row == self.rowCount()-1 and to == -1:
            wro = 0
        else:
            wro = row - to
        self.beginResetModel()
        self.params.insert(wro, self.params.pop(row))
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        return wro

    def removeItem(self, index):
        if self.rowCount() == 0:
            return
        self.beginResetModel()
        row = index.row()
        wro = row if row < self.rowCount()-1 else self.rowCount()-2
        self.params.pop(row)
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        return wro


class LCFTableView(qt.QTableView):
    columnWidths = [140, 55, 170, 80, 50, 55, 140, 80, 50]

    def __init__(self, parent, model):
        super().__init__(parent)
        self.setModel(model)

        horHeaders = self.horizontalHeader()  # QHeaderView instance
        verHeaders = self.verticalHeader()  # QHeaderView instance
        verHeaders.setVisible(True)

        nC = model.columnCount()
        if 'pyqt4' in qt.BINDING.lower():
            horHeaders.setMovable(False)
            horHeaders.setResizeMode(0, qt.QHeaderView.Stretch)
            for i in range(1, nC):
                horHeaders.setResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setClickable(True)
        else:
            horHeaders.setSectionsMovable(False)
            horHeaders.setSectionResizeMode(0, qt.QHeaderView.Stretch)
            for i in range(1, nC):
                horHeaders.setSectionResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setSectionsClickable(True)
        horHeaders.setStretchLastSection(False)
        # horHeaders.setMinimumSectionSize(20)
        verHeaders.setDefaultSectionSize(20)
        horHeaders.sectionClicked.connect(self.headerClicked)

        for i, cw in enumerate(self.columnWidths[:nC]):
            self.setColumnWidth(i, int(cw*csi.screenFactor))
        for i in [1, 5]:
            kw = dict(alignment=qt.Qt.AlignHCenter | qt.Qt.AlignVCenter)
            self.setItemDelegateForColumn(
                i, gco.DoubleSpinBoxDelegate(self, **kw))

        self.setMinimumHeight(horHeaders.height() * max(2, model.rowCount()+1))
        # self.setMinimumWidth(
        #     int(sum(self.columnWidths[:nC])*csi.screenFactor) + 30)

        # self.setSelectionMode(qt.QAbstractItemView.NoSelection)
        self.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        # self.setSelectionBehavior(qt.QAbstractItemView.SelectItems)
        # self.setFocusPolicy(qt.Qt.NoFocus)

        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenu)
        self.makeActions()

    def headerClicked(self, column):
        rows = self.model().rowCount()
        if column == 0:
            for row in range(rows):
                ref = self.model().params[row]
                ref['use'] = not ref['use']
            self.model().dataChanged.emit(self.model().index(0, column),
                                          self.model().index(rows-1, column))
            return

        if not self.selectionModel().hasSelection():
            return
        if column != self.currentIndex().column():
            return
        if column == 1:
            keyd = 'w'
        elif column == 2:
            keyd = 'wBounds'
        elif column == 5:
            keyd = 'dx'
        elif column == 6:
            keyd = 'dxBounds'
        ref0 = self.model().params[self.currentIndex().row()]
        for row in range(rows):
            ref = self.model().params[row]
            ref[keyd] = copy.copy(ref0[keyd])
        self.model().dataChanged.emit(self.model().index(0, column),
                                      self.model().index(rows-1, column))

    def makeActions(self):
        if csi.mainWindow is not None:
            self.actionCopyFitParams = self._addAction(
                "Copy fit params to picked data",
                partial(self.startPickData, 1), "Ctrl+P")
            self.actionAddRefSpectra = self._addAction(
                "Add ref spectra from data tree",
                partial(self.startPickData, 2), "Ctrl++")
        self.actionMoveUp = self._addAction(
            "Move up", partial(self.moveItem, +1), "Ctrl+Up")
        self.actionMoveDown = self._addAction(
            "Move down", partial(self.moveItem, -1), "Ctrl+Down")
        self.actionRemove = self._addAction("Remove", self.removeItem, "Del")

    def _addAction(self, text, slot, shortcut=None):
        action = qt.QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(qt.QKeySequence(shortcut))
        action.setShortcutContext(qt.Qt.WidgetWithChildrenShortcut)
        self.addAction(action)
        return action

    def onCustomContextMenu(self, point):
        menu = qt.QMenu()
        if csi.mainWindow is not None:
            menu.addAction(self.actionCopyFitParams)
            menu.addSeparator()
            menu.addAction(self.actionAddRefSpectra)
        # if csi.mainWindow is None:
        if True:
            refMenu = menu.addMenu("Add ref spectrum")
            refMenu.setEnabled(len(csi.allLoadedItems) > 0)
            refNamesLoaded = [item['name'] for item in self.model().params]
            for item in csi.allLoadedItems:
                i = item.alias
                refAction = self._addAction(i, partial(self.addRefSpectrum, i))
                refAction.setEnabled(i not in refNamesLoaded)
                refMenu.addAction(refAction)

        menu.addAction(self.actionMoveUp)
        self.actionMoveUp.setEnabled(len(csi.allLoadedItems) > 1)
        menu.addAction(self.actionMoveDown)
        self.actionMoveDown.setEnabled(len(csi.allLoadedItems) > 1)
        menu.addSeparator()
        menu.addAction(self.actionRemove)
        self.actionRemove.setEnabled(len(csi.allLoadedItems) > 0)
        menu.exec_(self.viewport().mapToGlobal(point))

    def startPickData(self, pickReason):
        self.pickReason = pickReason
        self.model().worker.node.widget.preparePickData(self)

    def addRefSpectrum(self, name):
        newRow = self.model().appendRef(name)
        if newRow is None:
            return
        newInd = self.model().index(newRow, 0)
        if newInd.isValid():
            self.setCurrentIndex(newInd)

    def applyPendingProps(self):
        if self.pickReason == 1:  # copy fit params
            srcParams = self.parent().spectrum.fitParams
            for item in csi.selectedItems:
                dfparams = item.fitParams
                for prop in ('lcf_xRange', 'lcf_params', 'lcf_result'):
                    dfparams[prop] = copy.deepcopy(srcParams[prop])
        elif self.pickReason == 2:  # add ref spectra
            names = [item.alias for item in csi.selectedItems]
            newRow = self.model().appendRefs(names)
            if newRow is None:
                return
            newInd = self.model().index(newRow, 0)
            if newInd.isValid():
                self.setCurrentIndex(newInd)

        csi.selectionModel.clear()
        csi.model.selectItems(self.parent().spectrum)

    def moveItem(self, to):
        newRow = self.model().moveItem(self.currentIndex(), to)
        if newRow is None:
            return
        newInd = self.model().index(newRow, 0)
        if newInd.isValid():
            self.setCurrentIndex(newInd)

    def removeItem(self):
        newRow = self.model().removeItem(self.currentIndex())
        if newRow is None:
            return
        newInd = self.model().index(newRow, 0)
        if newInd.isValid():
            self.setCurrentIndex(newInd)


class LCFWidget(gbf.FitWidget):
    def __init__(self, parent, worker, plot):
        super().__init__(parent, worker, plot)
        self.spectrum = None

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.fitModel = LCFModel(worker)
        table = LCFTableView(self, self.fitModel)
        layout.addWidget(table)
        self.fitModel.dataChanged.connect(self.makeFit)

        self.addRangeAndStartWidgets(layout)
        # layout.addStretch()
        self.setLayout(layout)

    def makeFit(self):
        """Here, all tie formulas and off-bounds are ignored."""
        if not self.fitModel.params:
            return
        cs = self.spectrum
        self.worker.make_model_curve(cs, allData=csi.allLoadedItems)

        dfparams = cs.fitParams
        lcfRes = dfparams['lcf_result']
        self.fitR.setText('R={0:.5g}'.format(lcfRes['R']))
        self.updateFitResults()
        self.fitReady.emit()
