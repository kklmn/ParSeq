# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "12 Jan 2025"
# !!! SEE CODERULES.TXT !!!

import os.path as osp
import copy
from functools import partial
import numpy as np

from ...core import singletons as csi
from ...core import config
from ...core.logger import syslogger
from ...gui import gcommons as gco
from . import gbasefit as gbf

from silx.gui import qt, icons


class EXAFSFitModel(qt.QAbstractTableModel):
    """The Qt table model for an EXAFS Fit in ParSeq."""

    HEADERS = ['variable', 'value', 'step', 'tie', '[min, max]',
               'errorᵃ', 'errorᵇ',
               # 'errorᶜ'
               ]
    ERRORS = 'errorA', 'errorB'  # , 'errorC'
    colERRORS = 5, 6  # , 7
    INFERROR = 1e2
    MAXMETAVARS = 3

    def __init__(self, worker):
        super().__init__()
        self.worker = worker
        self.setParams()

    def rowCount(self, parent=qt.QModelIndex()):
        return len(self.keys)

    def columnCount(self, parent=qt.QModelIndex()):
        return len(self.HEADERS)

    def isMeta(self, index):
        row = index.row()
        try:
            ish, key = self.keys[row]
        except IndexError:
            return
        if ish == len(self.params)-1:  # s0 and metavariables
            if key != 's0':
                return True

    def flags(self, index):
        res = qt.Qt.NoItemFlags
        if not index.isValid():
            return res
        if index.column() == 0:  # p name
            res = qt.Qt.ItemIsEnabled
            if self.isMeta(index):
                res |= qt.Qt.ItemIsEditable
        elif index.column() in (1, 2, 4):  # value, step, lim
            res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        elif index.column() == 3:  # tie
            res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        elif index.column() in self.colERRORS:  # errors
            res = qt.Qt.NoItemFlags
        return res

    def data(self, index, role=qt.Qt.DisplayRole):
        if len(self.keys) == 0:
            return
        if not index.isValid():
            return
        column, row = index.column(), index.row()
        ish, key = self.keys[row]
        pv = self.params[ish][key]  # dict(value, step, tie, lim, error)
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            if column == 0:  # parameter name
                if key == 's0':
                    return 'S\u2080², ' + key
                elif key.startswith('r'):
                    return 'distance (Å), {0}{1}'.format(key, ish+1)
                elif key.startswith('n'):
                    return 'coordination number, {0}{1}'.format(key, ish+1)
                elif key.startswith('s'):
                    return 'distance variance (Å²), {0}{1}'.format(key, ish+1)
                elif key.startswith('e'):
                    return 'E\u2080 shift (eV), {0}{1}'.format(key, ish+1)
                if self.isMeta(index):
                    if role == qt.Qt.DisplayRole:
                        return 'metavariable, {0}'.format(key)
                    elif role == qt.Qt.EditRole:
                        return key
            elif column == 1:  # value
                fmt = gco.getFormatStr(pv['step']*0.1)
                return fmt.format(pv['value'])
            elif column == 2:  # step
                fmt = gco.getFormatStr(pv['step'])
                return fmt.format(pv['step'])
            elif column == 3:  # tie
                if 'tie' in pv:
                    return pv['tie']
            elif column == 4:  # [min, max]
                if 'lim' in pv:
                    lim = list(pv['lim'])
                    fmt = gco.getFormatStr(pv['step'])
                    lim[0] = '--' if lim[0] == -np.inf else fmt.format(lim[0])
                    lim[1] = '--' if lim[1] == -np.inf else fmt.format(lim[1])
                    return '[{0}, {1}]'.format(*lim)
            elif column in self.colERRORS:  # errors
                errorStr = self.ERRORS[column-self.colERRORS[0]]
                if errorStr in pv:
                    error = pv[errorStr]
                    if error > self.INFERROR:
                        return '∞'
                    fmt = gco.getFormatStr(pv['step']*0.1)
                    return fmt.format(error)
                else:
                    return '---'
        elif role == qt.Qt.TextAlignmentRole:
            if column == 0:
                return qt.Qt.AlignLeft | qt.Qt.AlignVCenter
            return qt.Qt.AlignHCenter | qt.Qt.AlignVCenter
        elif role == qt.Qt.ToolTipRole:
            fmtLonger = gco.getFormatStr(pv['step']*0.001)
            if column == 0:
                res = 'Displayed as "variable description, variable name"'
                if self.isMeta(index):
                    res += '.\nMust not start with "r", "n", "s" or "e".'
                    res += '.\nRemember to tie it to an EXAFS variable.'
                return res
            elif column == 1:
                return fmtLonger.format(pv['value'])
            elif column in self.colERRORS:
                errorStr = self.ERRORS[column-self.colERRORS[0]]
                if errorStr in pv:
                    error = pv[errorStr]
                    if error > self.INFERROR:
                        # return '∞'
                        return ''
                    return fmtLonger.format(error)
        elif role == qt.Qt.BackgroundRole:
            if column == 3:  # tie
                if 'tie' in pv:
                    if len(pv['tie']) < 2:
                        del pv['tie']
                    else:
                        # Don't! This would spoil global tying:
                        # if '{0}{1}'.format(key, ish+1) in pv['tie']:
                        #     return qt.QColor(gbf.BAD_BKGND)
                        if not self.worker.can_interpret_tie_str(
                            pv['tie'], self.params,
                                allData=csi.allLoadedItems):
                            return qt.QColor(gbf.BAD_BKGND)
                        else:
                            return qt.QColor(gbf.GOOD_BKGND)
            elif column in self.colERRORS:
                errorStr = self.ERRORS[column-self.colERRORS[0]]
                if errorStr in pv:
                    error = pv[errorStr]
                    if error > self.INFERROR:
                        return qt.QColor(gbf.BAD_BKGND)
        elif role == gco.LIMITS_ROLE:  # return min, max, step
            if 'lim' in pv:
                return *pv['lim'], pv['step']
            else:
                return -np.inf, np.inf, pv['step']

    def setData(self, index, value, role=qt.Qt.EditRole):
        if len(self.keys) == 0:
            return
        column, row = index.column(), index.row()
        ish, key = self.keys[row]
        pv = self.params[ish][key]  # dict(value, step, tie, lim, error)
        if role == qt.Qt.EditRole:
            if column == 0:
                if self.isMeta(index):
                    if not value.isidentifier():
                        return False
                    if value.startswith(("r", "n", "s", "e", "s0")):
                        return False
                    newKey = value
                    self.params[ish][newKey] = self.params[ish].pop(key)
                    self.keys[row] = ish, newKey
                else:
                    return False
            elif column == 1:
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
                    return 'variable description, variable name'
                elif section == 1:
                    return 'variable value'
                elif section == 2:
                    return 'step in SpinBox value edit widget'
                elif section == 3:
                    return 'Either "fixed" or str starting with = or > or < '\
                        '\nand followed by a Python expression of other vars,'\
                        '\ne.g. "=n1/2" (without quotes).'\
                        '\nThe expression can refer to another fit like this:'\
                        "\n=fit['alias-of-data-with-that-fit'].r1"
                elif section == 4:
                    return 'Limits of the variable, applied to SpinBox\n'\
                        'value edit widget and the fitting method.'\
                        '\nIf min≥max, the variable is fixed at min value.'
                elif section == 5:
                    return 'Fitting errors excluding pair correlations.'\
                        '\nClick to show/hide the correlation matrix.'
                elif section == 6:
                    return 'Fitting errors including all pair correlations.'\
                        '\nClick to show/hide the correlation matrix.'

    def setParams(self, params=None, emit=True):
        self.beginResetModel()
        if params is None:
            self.params = []
            self.keys = []
        else:
            self.params = params  # list of shell dicts
            self.keys = [[ishell, key] for (ishell, shell) in
                         enumerate(self.params) for key in shell]
        self.endResetModel()
        if emit:
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def addMetaVar(self):
        if len(self.keys) == 0:
            return
        if len(self.params[-1]) > self.MAXMETAVARS:  # +1 for 's0'
            return
        self.beginResetModel()
        tryName = 'meta'
        while tryName in self.params[-1]:
            tryName += '_a'
        self.params[-1][tryName] = dict(self.worker.defaultMetaParams)
        last = len(self.params) - 1
        self.keys.append([last, tryName])
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def deleteMetaVar(self, row, ish, key):
        self.beginResetModel()
        self.params[ish].pop(key)
        del self.keys[row]
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())


class EXAFSFitTableView(qt.QTableView):
    columnWidths = [60, 80, 60, 80, 130, 75, 75]

    def __init__(self, parent, model, rows=4):
        super().__init__(parent)
        self.setModel(model)

        # horHeaders = self.horizontalHeader()  # QHeaderView instance
        # horHeaders.setStyleSheet(  # doesn't work
        #     "QHeaderView::section {border-bottom: 1px solid gray; }")
        horHeaders = gbf.UnderlinedHeaderView(qt.Qt.Horizontal, self)
        self.setHorizontalHeader(horHeaders)
        verHeaders = self.verticalHeader()  # QHeaderView instance

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
        horHeaders.sectionClicked.connect(self.headerClicked)
        horHeaders.setStretchLastSection(False)
        verHeaders.setDefaultSectionSize(int(20/csi.screenFactor))
        verHeaders.hide()

        for i, cw in enumerate(self.columnWidths[:nC]):
            self.setColumnWidth(i, int(cw*csi.screenFactor))

        kw = dict(alignment=qt.Qt.AlignHCenter | qt.Qt.AlignVCenter)
        self.setItemDelegateForColumn(1, gco.DoubleSpinBoxDelegate(self, **kw))

        height = int(horHeaders.height()*csi.screenFactor) + \
            rows*verHeaders.sectionSize(0) + 1
        self.setMinimumHeight(height)
        # self.setMinimumWidth(
        #     int(sum(self.columnWidths[:nC])*csi.screenFactor) + 30)

        self.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        # self.setSelectionBehavior(qt.QAbstractItemView.SelectItems)
        # self.setFocusPolicy(qt.Qt.NoFocus)

        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenu)
        self.makeActions()

    def headerClicked(self, column):
        nC = self.model().columnCount()
        if nC-2 <= column <= nC-1:
            isVisible = self.parent().parentFitWidget.corrTable.isVisible()
            self.parent().parentFitWidget.corrTable.setVisible(not isVisible)

    def makeActions(self):
        if csi.mainWindow is None:
            return
        self.actionCopyFitParams = self._addAction(
            "Copy fit params to picked data",
            partial(self.startPickData, 1), "Ctrl+P")

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
        if csi.mainWindow is not None and \
                self.parent().parentFitWidget.spectrum is not None:
            index = self.indexAt(point)
            if self.model().isMeta(index):
                row = index.row()
                ish, key = self.model().keys[row]
                action = qt.QAction(
                    'Delete this metavariable "{0}"'.format(key), self)
                action.triggered.connect(
                    partial(self.model().deleteMetaVar, row, ish, key))
                menu.addAction(action)
                menu.addSeparator()
            menu.addAction(self.actionCopyFitParams)
        menu.exec_(self.viewport().mapToGlobal(point))

    def startPickData(self, pickReason):
        self.pickReason = pickReason
        self.model().worker.node.widget.preparePickData(self)

    def applyPendingProps(self):
        if self.parent().parentFitWidget.spectrum is None:
            return
        if self.pickReason == 1:  # copy fit params
            srcParams = self.parent().parentFitWidget.spectrum.fitParams
            for item in csi.selectedItems:
                dfparams = item.fitParams
                for prop in self.model().worker.defaultParams:
                    if prop in srcParams:
                        dfparams[prop] = copy.deepcopy(srcParams[prop])

        csi.selectionModel.clear()
        csi.model.selectItems(self.parent().parentFitWidget.spectrum)


class BasePage(qt.QWidget):
    def setVisibleShellParams(self, ishell):
        model = self.table.model()
        self.ishell = ishell
        for row in range(model.rowCount()):
            ish, _ = model.keys[row]
            if ish == ishell:
                self.table.showRow(row)
            else:
                self.table.hideRow(row)


class EXAFSSettingsPage(BasePage):
    def __init__(self, parent, model):
        self.parentFitWidget = parent  # will be re-parented, so we save it
        super().__init__(parent)
        self.model = model
        self.ishell = -1
        layout = qt.QVBoxLayout()
        # layout.setContentsMargins(0, 0, 0, 0)

        try:
            lenParam = len(model.params[-1])
        except Exception:
            lenParam = 1
        self.table = EXAFSFitTableView(self, model, lenParam)
        layout.addWidget(self.table)
        layout.addStretch()
        self.setLayout(layout)

        addMetaButton = qt.QToolButton(self)
        addMetaButton.setIcon(icons.getQIcon('add'))
        tooltip = "add metavariable to use in tie expressions,"\
            "\nmax {0} metavariables".format(model.MAXMETAVARS)
        addMetaButton.setToolTip(tooltip)
        addMetaButton.setStyleSheet("QToolButton{border: 0;}")  # make it small
        addMetaButton.move(-24, 8)
        addMetaButton.clicked.connect(model.addMetaVar)


class EXAFSShellPage(BasePage):
    addShells = qt.pyqtSignal(dict)  # path: [deg, pathStr, reff, ver, nHeader]

    def __init__(self, parent, model):
        self.parentFitWidget = parent  # will be re-parented, so we save it
        super().__init__(parent)
        self.model = model
        self.ishell = 0
        layout = qt.QVBoxLayout()
        # layout.setContentsMargins(0, 0, 0, 0)

        layoutAP = qt.QHBoxLayout()
        apButton = qt.QToolButton()
        apButton.setIcon(icons.getQIcon('math-phase-color'))
        apButton.setToolTip("Load file with amplitudes and phases.\n"
                            "Accepted: feffNNNN.dat.\n"
                            "Not yet accepted: 3-column file (k, F, φ).")
        apButton.clicked.connect(self.readAP)
        layoutAP.addWidget(apButton)
        self.apLabel = qt.QLabel('')
        layoutAP.addWidget(self.apLabel)
        layoutAP.addStretch()
        self.hideOthersCB = qt.QCheckBox('hide other shells')
        self.hideOthersCB.toggled.connect(self.hideOthers)
        layoutAP.addWidget(self.hideOthersCB)
        layout.addLayout(layoutAP)

        self.table = EXAFSFitTableView(self, model, 4)
        layout.addWidget(self.table)

        # layout.addStretch()
        self.setLayout(layout)

    def hideOthers(self, value):
        cs = self.parentFitWidget.spectrum
        dfparams = cs.fitParams
        auxs = dfparams['exafsfit_aux']
        for ish, aux in enumerate(auxs):
            if ish == self.ishell:
                aux[6] = 1
            else:
                aux[6] = 0 if value else 1
        self.parentFitWidget.makeFit()

    def readAP(self):
        dlg = LoadFEFFfileDlg(self)
        fitname = self.model.worker.name

        cs = self.parentFitWidget.spectrum
        dfparams = cs.fitParams
        shells = dfparams['exafsfit_params']
        if not shells:
            self.parentFitWidget.addShellTab()
            return

        auxs = dfparams['exafsfit_aux']
        try:
            if auxs:
                d = osp.dirname(auxs[self.ishell][0])
                dlg.setDirectory(d)
            else:
                if config.configFits.has_section(fitname) and \
                        config.configFits.has_option(fitname, 'exafsfit_aux'):
                    co = config.get(config.configLoad, fitname, 'exafsfit_aux')
                    lastKey = list(co.keys())[-1]
                    lastPath = co[lastKey][0]
                    d = osp.dirname(lastPath)
                    dlg.setDirectory(d)
        except Exception:
            pass
        dlg.ready.connect(self.doLoadFEFFfile)
        dlg.open()

    def doLoadFEFFfile(self, feffDict):
        cs = self.parentFitWidget.spectrum
        dfparams = cs.fitParams
        auxs = dfparams['exafsfit_aux']
        for i in range(len(auxs), self.ishell+1):
            auxs.append([])  # extend the list if short
        for key, val in feffDict.items():
            if not val:
                continue
            feffStruct = [key]
            feffStruct.extend(list(val))
            auxs[self.ishell] = feffStruct
            break
        else:
            return
        self.parentFitWidget.updateTabs()

        shells = dfparams['exafsfit_params']
        if self.ishell > len(shells)-1:
            return
        r = feffStruct[3]
        n = feffStruct[1]
        # return [deg, pathStr, reff, feffVersion, nHeader, 1]
        shells[self.ishell]['r']['value'] = r
        shells[self.ishell]['r']['lim'] = [r*0.5, r*2]
        shells[self.ishell]['n']['value'] = n
        shells[self.ishell]['n']['lim'] = [n*0.5, n*2]
        for ish, (shell, aux) in enumerate(zip(shells, auxs)):
            if shell is shells[self.ishell]:
                continue
            if aux[2] == feffStruct[2]:
                shells[self.ishell]['e']['value'] = shell['e']['value']
                shells[self.ishell]['e']['tie'] = '=e{0}'.format(ish+1)
                break
        if len(feffDict) > 1:
            del feffDict[key]
            self.addShells.emit(feffDict)
        else:
            self.parentFitWidget.makeFit()


class MyProxyModel(qt.QIdentityProxyModel):
    byteHint = 1000
    prevLine = " -------------------------"
    ssColor = "#ccffcc"

    def data(self, index, role=qt.Qt.DisplayRole):
        if role == qt.Qt.BackgroundRole:
            fpath = self.sourceModel().filePath(index)
            head, tail = osp.split(fpath)
            if tail.startswith('feff') and tail.endswith('dat'):
                nleg = self.get_feff_nleg(fpath)
                if nleg == 2:
                    return qt.QColor(self.ssColor)
        else:
            return super().data(index, role)

    def get_feff_nleg(self, fpath):
        with open(fpath, 'r', encoding="utf-8") as f:
            lines = f.readlines(self.byteHint)
        for iline, line in enumerate(lines):
            if line.startswith(self.prevLine):
                break
        else:
            return
        try:
            return int(lines[iline+1].split()[0])
        except Exception:
            return


class LoadFEFFfileDlg(qt.QFileDialog):
    ready = qt.pyqtSignal(dict)  # path: [N, stratoms, R, ver, nHeader, use]
    uniqueWord = 'real[2*phc]'
    reffWord = 'nleg,'
    endHeaderWord = 'real[p]@#'
    byteHint = 5000

    def __init__(self, parent=None, dirname=''):
        super().__init__(
            parent=parent, caption='Load FEFF file', directory=dirname)
        self.setOption(self.DontUseNativeDialog, True)
        self.setAcceptMode(self.AcceptOpen)
        self.setFileMode(self.ExistingFiles)
        self.setViewMode(self.Detail)
        self.setProxyModel(MyProxyModel())
        self.setNameFilter("feffNNNN File (*.dat)")

        self.currentChanged.connect(self.updatePreview)
        self.accepted.connect(self.onAccept)

        self.splitter = self.layout().itemAtPosition(1, 0).widget()
        previewPanel = qt.QWidget(self)
        layoutP = qt.QVBoxLayout()
        layoutP.setContentsMargins(0, 0, 0, 0)
        self.previewLabel = qt.QLabel('Preview:', self)
        layoutP.addWidget(self.previewLabel)
        self.previewContent = qt.QLabel(self)
        layoutP.addWidget(self.previewContent, 1)
        previewPanel.setLayout(layoutP)
        previewPanel.setMinimumWidth(400)
        self.splitter.addWidget(previewPanel)

        self.setMinimumSize(1000, 500)

    def parseFEFF(self, lines):
        isFEFFfile = False
        reffFound = False
        atoms = []
        pathStr = ''
        nHeader = 0
        deg, reff = 1.0, 2.0
        feffVersion = 0
        for iline, line in enumerate(lines):
            if iline == 0:
                feffVersion = line.split()[-1].strip()
                syslogger.info('feffVersion = {0}'.format(feffVersion))
            if not isFEFFfile and (self.uniqueWord in line):
                isFEFFfile = True
            if self.endHeaderWord in line:
                nHeader = iline + 1
                break
            if not reffFound and (self.reffWord in line):
                deg, reff = [float(s.strip()) for s in line.split()[1:3]]
                reffFound = True
                continue
            if reffFound and ('x' in line) and ('y' in line):
                continue
            if reffFound:
                atoms.append(line.split()[5].strip())
        if isFEFFfile and reffFound:
            pathStr = '-'.join(atoms)
            return [deg, pathStr, reff, feffVersion, nHeader, 1]

    def updatePreview(self, path):
        if not osp.isfile(path):
            return
        with open(path, 'r', encoding="utf-8") as f:
            lines = f.readlines(self.byteHint)
        self.previewContent.setText(''.join(lines))
        feffStruct = self.parseFEFF(lines)
        if feffStruct:
            deg, pathStr, reff = feffStruct[:3]
            txt = '<b><font color=green>{0:.0f}×{1} @ {2:.4f} Å </color></b>'\
                .format(deg, pathStr, reff)
        else:
            txt = '<b><font color=red>not a feffNNNN.dat file</color></b>'
        self.previewLabel.setText(txt)

    def onAccept(self):
        feffDict = {}
        for path in self.selectedFiles():
            with open(path, 'r', encoding="utf-8") as f:
                lines = f.readlines(self.byteHint)
            res = self.parseFEFF(lines)
            if res:
                feffDict[path] = res
        self.ready.emit(feffDict)


class MyTabBar(qt.QTabBar):
    reshuffled = qt.pyqtSignal()

    def mousePressEvent(self, event):
        self.setMovable(self.tabAt(event.pos()) < self.count()-1)
        self.movingTabInd = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.movingTabInd != self.tabAt(event.pos()):
            self.reshuffled.emit()


class EXAFSFitWidget(gbf.FitWidget):
    """
    Inside `EXAFSFitWidget`.
    """

    def __init__(self, parent, worker, plot):
        super().__init__(parent, worker, plot)
        self.spectrum = None

        self.fitModel = EXAFSFitModel(worker)
        self.fitModel.dataChanged.connect(self.makeFit)

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabWidget = qt.QTabWidget()
        # tabBar = self.tabWidget.tabBar()
        tabBar = MyTabBar()
        tabBar.setTabsClosable(True)
        tabBar.setMovable(True)
        tabBar.reshuffled.connect(self.reTab)
        self.tabWidget.setTabBar(tabBar)

        # self.tabWidget.setTabsClosable(True)
        self.tabWidget.tabCloseRequested.connect(self.closeShellTab)

        self.optionsPage = EXAFSSettingsPage(self, self.fitModel)
        self.tabWidget.addTab(self.optionsPage, icons.getQIcon('rudder'), '')
        try:
            tabBar.tabButton(0, qt.QTabBar.RightSide).deleteLater()
            tabBar.setTabButton(0, qt.QTabBar.RightSide, None)
        except Exception:
            pass

        addShellButton = qt.QToolButton()
        addShellButton.setIcon(icons.getQIcon('add'))
        addShellButton.setToolTip("New atomic shell")
        addShellButton.clicked.connect(self.addShellTab)
        addShellButton.setStyleSheet("QToolButton{border: 0;}")
        self.tabWidget.setCornerWidget(addShellButton, qt.Qt.TopLeftCorner)
        layout.addWidget(self.tabWidget)

        self.corrModel = gbf.CorrModel(['r1', 'n1', 's1', 'e1'])
        self.corrTable = gbf.CorrTableView(self, self.corrModel)
        self.corrTable.hide()
        layoutC = qt.QHBoxLayout()
        layoutC.setContentsMargins(0, 0, 0, 0)
        layoutC.addWidget(self.corrTable, 1)
        # layoutC.addStretch()
        layout.addLayout(layoutC)

        layoutRange = qt.QHBoxLayout()
        self.optionsPage.layout().addLayout(layoutRange)
        self.addRangeAndStartWidgets(layout, layoutRange,
                                     caption=('fit k-range', 'fit r-range'),
                                     tooltip=('kMin, kMax', 'rMin, rMax'))
        for w in self.rangeWidget:
            w.panel.setCheckable(True)
            w.panel.setChecked(False)
        # layout.addStretch()
        self.setLayout(layout)
        # self.currentShell = 0
        self.tabWidget.currentChanged.connect(self.currentShellChanged)

    def currentShellChanged(self, index):
        if hasattr(self.tabWidget.widget(index), 'hideOthersCB'):
            wasChecked = False
            for i in range(self.tabWidget.count()):
                if i == index:
                    continue
                hasCB = hasattr(self.tabWidget.widget(i), 'hideOthersCB')
                if hasCB:
                    cb = self.tabWidget.widget(i).hideOthersCB
                    if cb.isChecked():
                        wasChecked = True
                        cb.setChecked(False)
            if wasChecked:
                cb = self.tabWidget.widget(index).hideOthersCB
                cb.setChecked(True)

    def reTab(self):
        """Place the options tab at the right of tabBar."""
        if self.spectrum is None:
            return
        fr = self.tabWidget.indexOf(self.optionsPage)
        tabBar = self.tabWidget.tabBar()
        tabBar.moveTab(fr, tabBar.count()-1)

        inds = [self.tabWidget.widget(i).ishell for i in
                range(self.tabWidget.count())]
        fps = self.spectrum.fitParams
        fps['exafsfit_params'] = [fps['exafsfit_params'][i] for i in inds]
        try:
            fps['exafsfit_aux'] = [fps['exafsfit_aux'][i] for i in inds[:-1]]
        except IndexError:
            pass
        self.fitModel.setParams(fps['exafsfit_params'])

    def updateTabs(self):
        """Tabs are atomic shells plus one tab for general parameters (Sₒ²)"""
        if self.spectrum is None:
            return
        dfparams = self.spectrum.fitParams
        shells = dfparams['exafsfit_params']

        last = len(shells) - 1
        wasIn = False
        for i in range(last, self.tabWidget.count()-1):
            self.tabWidget.removeTab(last)
            wasIn = True
        if wasIn:
            self.tabWidget.setCurrentIndex(max(self.tabWidget.count()-2, 0))

        wasIn = False
        for i in range(self.tabWidget.count(), len(shells)):
            page = EXAFSShellPage(self, self.fitModel)
            page.addShells.connect(self.addShells)
            self.tabWidget.insertTab(i-1, page, '{0}) undefined'.format(i+1))
            wasIn = True
        if wasIn:
            self.tabWidget.setCurrentIndex(max(self.tabWidget.count()-2, 0))

        for i, shell in enumerate(shells):
            self.tabWidget.widget(i).setVisibleShellParams(i)

        auxs = dfparams['exafsfit_aux']
        for i, (shell, aux) in enumerate(zip(shells, auxs)):
            if aux:
                s = '<b>{0[1]:.0f}×{0[2]} @ {0[3]:.4f} Å</b> in {0[0]}'.format(
                    aux)
                title = '{0}) {1[2]}'.format(i+1, aux)
            else:
                title = '{0}) undefined'.format(i+1)
                s = ''
            self.tabWidget.setTabText(i, title)
            self.tabWidget.widget(i).apLabel.setText(s)

    def addShells(self, shellDict):
        if self.spectrum is None:
            return
        dfparams = self.spectrum.fitParams
        fitVars = dfparams['exafsfit_params']  # list of shell dicts, min len=2
        auxs = dfparams['exafsfit_aux']

        iTab = self.tabWidget.currentIndex()
        iShellToCopy = min(iTab, len(fitVars)-2)
        i = -1
        for path, feffStruct in shellDict.items():
            if not feffStruct:
                continue
            i += 1
            shell = copy.deepcopy(fitVars[iShellToCopy])
            r = feffStruct[2]
            shell['r']['value'] = r
            shell['r']['lim'] = [r*0.5, r*2]
            n = feffStruct[0]
            shell['n']['value'] = n
            shell['n']['lim'] = [n*0.5, n*2]
            for ish, (shtmp, aux) in enumerate(zip(fitVars, auxs)):
                if shell is shtmp:
                    continue
                if aux[2] == feffStruct[1]:
                    shell['e']['value'] = shtmp['e']['value']
                    shell['e']['tie'] = '=e{0}'.format(ish+1)
                    break
            fitVars.insert(iShellToCopy+i+1, shell)
            aux = [path]
            aux.extend(feffStruct)
            auxs.insert(iShellToCopy+i+1, copy.deepcopy(aux))

        self.fitModel.setParams(fitVars)
        self.tabWidget.setCurrentIndex(iTab+i+1)

    def addShellTab(self):
        if self.spectrum is None:
            return
        dfparams = self.spectrum.fitParams
        if 'exafsfit_params' not in dfparams:  # only in test_fit_EXAFS.py
            dfparams['exafsfit_params'] = []

        if not dfparams['exafsfit_params']:
            dfparams.update(copy.deepcopy(self.fitModel.worker.defaultParams))
            fitVars = copy.deepcopy(self.fitModel.worker.defaultShellParams)
            dfparams['exafsfit_params'] = fitVars
            dfparams['exafsfit_aux'] = []
            self.fitModel.setParams(fitVars)
            self.tabWidget.setCurrentIndex(0)
            return

        fitVars = dfparams['exafsfit_params']  # list of shell dicts, min len=2
        auxs = dfparams['exafsfit_aux']

        iTab = self.tabWidget.currentIndex()
        iShellToCopy = min(iTab, len(fitVars)-2)
        fitVars.insert(iShellToCopy+1, copy.deepcopy(fitVars[iShellToCopy]))

        # auxs.insert(iShellToCopy+1, copy.deepcopy(auxs[iShellToCopy]))
        auxs.insert(iShellToCopy+1, [])  # if want empty amp-ph in the copy

        # fitVars.sort(key=lambda x: x['r']['value'])
        self.fitModel.setParams(fitVars)

        self.tabWidget.setCurrentIndex(iTab+1)

    def closeShellTab(self, iTab):
        if self.spectrum is None:
            return
        dfparams = self.spectrum.fitParams
        if (iTab > self.tabWidget.count()-2) or (self.tabWidget.count() < 3):
            return
        self.tabWidget.removeTab(iTab)
        fitVars = dfparams['exafsfit_params']
        auxs = dfparams['exafsfit_aux']
        try:
            del fitVars[iTab]
            del auxs[iTab]
        except IndexError:
            pass
        self.fitModel.setParams(fitVars)
        activeTabInd = max(iTab-1, 0)
        self.tabWidget.setCurrentIndex(activeTabInd)

    def makeFit(self):
        """Here, all tie formulas and off-bounds are ignored."""
        if self.spectrum is None:
            return
        dfparams = self.spectrum.fitParams
        if not self.fitModel.params:
            return
        resMakeFit = self.fitModel.worker.make_model_curve(self.spectrum)
        fitRes = dfparams['exafsfit_result']
        self.fitR.setText('R={0:.5g}'.format(fitRes['R']))
        self.updateTabs()
        if isinstance(resMakeFit, str):
            self.fitR.setToolTip(resMakeFit)
            co = gbf.BAD_BKGND
            self.fitR.setStyleSheet("QLabel {background-color: "+co+";}")
        else:
            self.updateFitResults()
        self.fitReady.emit()
