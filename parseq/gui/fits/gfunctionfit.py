# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "30 May 2023"
# !!! SEE CODERULES.TXT !!!

import copy
from functools import partial
import ast
import numpy as np

from ...core import singletons as csi
from ...gui import gcommons as gco
from . import gbasefit as gbf

from silx.gui import qt


class FunctionFitModel(qt.QAbstractTableModel):
    """The Qt table model for a Function Fit in ParSeq. Each row in the model
    represents a fitting parameter in the formula.
    """
    HEADERS = ['var', 'value', 'step', 'tie', '[min, max]', 'error']

    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.setParams()

    def rowCount(self, parent=qt.QModelIndex()):
        return len(self.params)

    def columnCount(self, parent=qt.QModelIndex()):
        return len(self.HEADERS)

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        if index.column() == 0:  # p name
            res = qt.Qt.ItemIsEnabled
        elif index.column() in (1, 2, 4):  # value, step, lim
            res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        elif index.column() == 3:  # tie
            res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        elif index.column() == 5:  # error
            res = qt.Qt.NoItemFlags
        return res

    def data(self, index, role=qt.Qt.DisplayRole):
        if len(self.params) == 0:
            return
        if not index.isValid():
            return
        column, row = index.column(), index.row()
        p = list(self.params.keys())[row]
        pv = self.params[p]  # dict(value, step, tie, lim, error)
        fmt = gco.getFormatStr(pv['step'])
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            if column == 0:  # p name
                return p
            elif column == 1:  # value
                return fmt.format(pv['value'])
            elif column == 2:  # step
                return fmt.format(pv['step'])
            elif column == 3:  # tie
                if 'tie' in pv:
                    return pv['tie']
            elif column == 4:  # [min, max]
                if 'lim' in pv:
                    lim = list(pv['lim'])
                    lim[0] = '--' if lim[0] == -np.inf else fmt.format(lim[0])
                    lim[1] = '--' if lim[1] == -np.inf else fmt.format(lim[1])
                    return '[{0}, {1}]'.format(*lim)
            elif column == 5:  # error
                if 'error' in pv:
                    return fmt.format(pv['error'])
                else:
                    return '---'
        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignHCenter | qt.Qt.AlignVCenter
        elif role == qt.Qt.ToolTipRole:
            fmtLonger = gco.getFormatStr(pv['step']*0.001)
            if column == 1:
                return fmtLonger.format(pv['value'])
            elif column == 5 and 'error' in pv:
                return fmtLonger.format(pv['error'])
        elif role == qt.Qt.BackgroundRole:
            if column == 3:  # tie
                if 'tie' in pv:
                    if len(pv['tie']) < 2:
                        del pv['tie']
                    else:
                        if not self.worker.can_interpret_tie_str(
                                pv['tie'], self.params):
                            return qt.QColor(gbf.BAD_BKGND)
                        else:
                            return qt.QColor(gbf.GOOD_BKGND)
        elif role == gco.LIMITS_ROLE:  # return min, max, step
            if 'lim' in pv:
                return *pv['lim'], pv['step']
            else:
                return -np.inf, np.inf, pv['step']

    def setData(self, index, value, role=qt.Qt.EditRole):
        if len(self.params) == 0:
            return
        column, row = index.column(), index.row()
        p = list(self.params.keys())[row]
        pv = self.params[p]  # dict(value, step, tie, lim, error)
        if role == qt.Qt.EditRole:
            if column == 1:
                pv['value'] = float(value)
            elif column == 2:  # step
                pv['step'] = float(value)
            elif column == 3:  # tie
                if len(value) < 2 and 'tie' in pv:
                    del pv['tie']
                else:
                    pv['tie'] = str(value).strip()
            elif column == 4:  # [min, max]
                if len(value) == 0:
                    if 'lim' in pv:
                        del pv['lim']
                        self.dataChanged.emit(index, index)
                    return True
                try:
                    tmp = eval(value)
                except Exception:
                    return False
                if not isinstance(tmp, (list, tuple)):
                    return False
                pv['lim'] = [float(t) for t in tmp]
            self.dataChanged.emit(index, index)
            return True
        return False

    def headerData(self, section, orientation, role):
        if role == qt.Qt.DisplayRole:
            if orientation == qt.Qt.Horizontal:
                if section < len(self.HEADERS):
                    return self.HEADERS[section]
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
                    return 'parameter name'
                elif section == 1:
                    return 'parameter value'
                elif section == 2:
                    return 'step in the SpinBox value edit widget'
                elif section == 3:
                    return 'either "fixed" or str starting with = or > or < '\
                        '\nand followed by a Python expression of other vars'
                elif section == 4:
                    return 'parameter limits, applied to\nthe SpinBox value '\
                        'edit widget\nand the fitting method'
                elif section == 5:
                    return 'fitting error'

    def setParams(self, params=None, emit=True):
        self.beginResetModel()
        if params is None:
            self.params = {}
        else:
            self.params = params
        self.endResetModel()
        if emit:
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

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
        keys = list(self.params.keys())
        vals = list(self.params.values())
        self.beginResetModel()
        keys.insert(wro, keys.pop(row))
        vals.insert(wro, vals.pop(row))
        self.params = {k: v for k, v in zip(keys, vals)}
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        return wro

    def removeItem(self, index):
        if self.rowCount() == 0:
            return
        self.beginResetModel()
        row = index.row()
        wro = row if row < self.rowCount()-1 else self.rowCount()-2
        key = list(self.params.keys())[row]
        del self.params[key]
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        return wro

    def removeItems(self, indexes):
        keys = list(self.params.keys())
        vals = list(self.params.values())
        self.beginResetModel()
        for index in reversed(indexes):
            row = index.row()
            keys.pop(row)
            vals.pop(row)
        self.params = {k: v for k, v in zip(keys, vals)}
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())


class FunctionFitTableView(qt.QTableView):
    columnWidths = [60, 80, 50, 80, 150, 55]

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
        horHeaders.setMinimumSectionSize(20)
        verHeaders.setDefaultSectionSize(20)

        for i, cw in enumerate(self.columnWidths[:nC]):
            self.setColumnWidth(i, int(cw*csi.screenFactor))

        kw = dict(alignment=qt.Qt.AlignHCenter | qt.Qt.AlignVCenter)
        self.setItemDelegateForColumn(1, gco.DoubleSpinBoxDelegate(self, **kw))

        self.setMinimumHeight(horHeaders.height() * max(2, model.rowCount()+1))
        self.setMinimumWidth(
            int(sum(self.columnWidths[:nC])*csi.screenFactor) + 30)

        # self.setSelectionMode(qt.QAbstractItemView.NoSelection)
        self.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        # self.setSelectionBehavior(qt.QAbstractItemView.SelectItems)
        # self.setFocusPolicy(qt.Qt.NoFocus)

        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenu)
        self.makeActions()

    def makeActions(self):
        if csi.mainWindow is not None:
            self.actionCopyFitParams = self._addAction(
                "Copy fit params to picked data",
                partial(self.startPickData, 1), "Ctrl+P")
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
        menu.addAction(self.actionMoveUp)
        menu.addAction(self.actionMoveDown)
        menu.addSeparator()
        menu.addAction(self.actionRemove)
        menu.exec_(self.viewport().mapToGlobal(point))

    def startPickData(self, pickReason):
        self.pickReason = pickReason
        self.model().worker.node.widget.preparePickData(self)

    def applyPendingProps(self):
        if self.pickReason == 1:  # copy fit params
            srcParams = self.parent().spectrum.fitParams
            for item in csi.selectedItems:
                dfparams = item.fitParams
                dfparams['ffit_formula'] = str(srcParams['ffit_formula'])
                dfparams['ffit_params'] = copy.deepcopy(
                    srcParams['ffit_params'])
                dfparams['ffit_result'] = copy.deepcopy(
                    srcParams['ffit_params'])

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


class FunctionFitWidget(gbf.FitWidget):
    def __init__(self, parent, worker, plot):
        super().__init__(parent, worker, plot)
        self.spectrum = None

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layoutF = qt.QHBoxLayout()
        self.formulaLabel = qt.QLabel('f(x) =')
        layoutF.addWidget(self.formulaLabel)
        self.formulaEdit = qt.QLineEdit()
        toolTip = 'Use numpy functions as attributes of np, e.g. `np.exp(x)`'
        extraToolTip = worker.getToolTip()
        if extraToolTip:
            toolTip += '\nExtra functions defined in this context:'
            toolTip += extraToolTip
        self.formulaEdit.setToolTip(toolTip)

        self.formulaEdit.returnPressed.connect(self.parseFormula)
        layoutF.addWidget(self.formulaEdit)
        layout.addLayout(layoutF)

        self.fitModel = FunctionFitModel(worker)
        table = FunctionFitTableView(self, self.fitModel)
        layout.addWidget(table)
        self.fitModel.dataChanged.connect(self.makeFit)

        self.addRangeAndStartWidgets(layout)
        # layout.addStretch()
        self.setLayout(layout)

    def setSpectrum(self, spectrum):
        dfparams = spectrum.fitParams
        fitFormula = dfparams['ffit_formula']
        self.formulaEdit.setText(fitFormula)
        super().setSpectrum(spectrum)

    def parseFormula(self):
        cs = self.spectrum
        dfparams = cs.fitParams
        fitVars = dfparams['ffit_params']
        try:
            st = ast.parse(self.formulaEdit.text())
            self.formulaEdit.setStyleSheet('')
            fvars = []
            for node in ast.walk(st):
                if type(node) is ast.Name:
                    if node.id in (
                            ['np', 'x'] + list(self.worker.customFunctions)):
                        continue
                    if node.id not in fvars:
                        fvars.append(node.id)
            for fv in sorted(fvars):
                if fv not in fitVars:
                    defPar = list(self.worker.defaultEntryDict.values())[0]
                    fitVars[fv] = dict(defPar)
            dfparams['ffit_formula'] = self.formulaEdit.text()
            delKeys = [k for k in fitVars.keys() if k not in fvars]
            for k in delKeys:
                del fitVars[k]
            self.fitModel.setParams(fitVars)
        except Exception as err:
            print('Error: ', err)
            self.formulaEdit.setStyleSheet(
                "QLineEdit {background-color: "+gbf.BAD_BKGND+";}")

    def makeFit(self):
        """Here, all tie formulas and off-bounds are ignored."""
        if not self.fitModel.params:
            return
        cs = self.spectrum
        self.worker.make_model_curve(cs)

        dfparams = cs.fitParams
        lcfRes = dfparams['ffit_result']
        self.fitR.setText('R={0:.5g}'.format(lcfRes['R']))
        self.updateFitResults()
        self.fitReady.emit()
