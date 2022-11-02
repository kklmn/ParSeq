# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "28 Oct 2022"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

ROWHEIGHT = 24
HEADERHEIGHT = 28
DOTSIZE = 2, 4
DOTDELTA = 1


def getFormatStr(step):
    if 0.1 <= step < 1:
        return '{0:.1f}'
    elif 0.01 <= step < 0.1:
        return '{0:.2f}'
    elif 0.001 <= step < 0.01:
        return '{0:.3f}'
    elif 0.0001 <= step < 0.001:
        return '{0:.4f}'
    elif 0.00001 <= step < 0.0001:
        return '{0:.5f}'
    else:
        return '{0:.0f}'


def getDecimals(step):
    if 0.1 <= step < 1:
        return 1
    elif 0.01 <= step < 0.1:
        return 2
    elif 0.001 <= step < 0.01:
        return 3
    elif 0.0001 <= step < 0.001:
        return 4
    elif 0.00001 <= step < 0.0001:
        return 5
    else:
        return 0


def formatted(region):  # region: label, value, min, max, step
    if len(region) < 5:
        return ''
    val = region[1]
    if isinstance(val, (float, int)):
        step = region[4]
        fmt = getFormatStr(step)
        return fmt.format(float(val))
    else:
        return 'inf'


class SplittersModel(qt.QAbstractTableModel):
    def __init__(self, captions, splitters):
        super().__init__()
        self.captions, self.splitters = list(captions), list(splitters)
        if len(self.splitters) < len(self.captions):
            self.splitters.append([])

    def rowCount(self, parent=qt.QModelIndex()):
        return 1

    def columnCount(self, parent=qt.QModelIndex()):
        return len(self.splitters)

    def flags(self, index):
        return qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable

    def data(self, index, role=qt.Qt.DisplayRole):
        if not index.isValid():
            return
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            return formatted(self.splitters[index.column()])
        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignRight
        elif role == qt.Qt.ToolTipRole:
            res = self.splitters[index.column()][0]
            res += 'pos (eV)' if res.startswith('E') else ' (Å⁻¹)' \
                if res.startswith('k') else ''
            return res

    def setData(self, index, value, role=qt.Qt.EditRole):
        if role == qt.Qt.EditRole:
            try:
                step = self.splitters[index.column()][4]
                newValue = round(float(value), getDecimals(step))
                if self.splitters[index.column()][1] == newValue:
                    return False
                if newValue == float('inf'):
                    newValue = 'inf'
                self.splitters[index.column()][1] = newValue
                self.dataChanged.emit(index, index)
            except ValueError:
                return False
            return True
        return False


class DeltasModel(qt.QAbstractTableModel):
    def __init__(self, captions, deltas):
        super().__init__()
        self.captions, self.deltas = list(captions), list(deltas)
        self.binNumbersOld = None
        self.binNumbersNew = None
        self.calcDots()

    def rowCount(self, parent=qt.QModelIndex()):
        return 3

    def columnCount(self, parent=qt.QModelIndex()):
        return len(self.deltas)

    def flags(self, index):
        if index.row() == 1:
            return qt.Qt.ItemIsEnabled | qt.Qt.ItemIsEditable
        else:
            return qt.Qt.NoItemFlags

    def data(self, index, role=qt.Qt.DisplayRole):
        if not index.isValid():
            return
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            if index.row() == 0:
                if self.binNumbersOld is None:
                    return
                return str(self.binNumbersOld[index.column()])
            elif index.row() == 1:
                return formatted(self.deltas[index.column()])
            elif index.row() == 2:
                if self.binNumbersNew is None:
                    return
                return str(self.binNumbersNew[index.column()])

        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignCenter
        elif role == qt.Qt.ToolTipRole:
            if index.row() == 1:
                res = self.deltas[index.column()][0]
                res += ' (eV)' if res.startswith('dE') else ' (Å⁻¹)' \
                    if res.startswith('dk') else ''
            elif index.row() in (0, 2):
                res = 'bins in ' + self.captions[index.column()]
            return res

    def setData(self, index, value, role=qt.Qt.EditRole):
        if role == qt.Qt.EditRole:
            try:
                step = self.deltas[index.column()][4]
                newValue = round(float(value), getDecimals(step))
                if self.deltas[index.column()][1] == newValue:
                    return False
                self.deltas[index.column()][1] = newValue
                self.calcDots()
                self.dataChanged.emit(index, index)
                self.headerDataChanged.emit(
                    qt.Qt.Horizontal, 0, self.columnCount()-1)
            except ValueError:
                return False
            return True
        return False

    def calcDots(self):
        self.curDeltas = [d[1] if 'k' not in d[0] else -1 for d in self.deltas]
        self.minDelta = min([v for v in self.curDeltas if v > 0])


class DeltasHeaderModel(qt.QAbstractItemModel):
    def __init__(self, deltasModel):
        super().__init__()
        self.deltasModel = deltasModel

    def columnCount(self, parent):
        return self.deltasModel.columnCount()

    def rowCount(self, parent):
        return 1

    def headerData(self, section, orientation=qt.Qt.Horizontal,
                   role=qt.Qt.DisplayRole):
        if role == qt.Qt.DisplayRole:
            return self.deltasModel.captions[section]
        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignCenter
        elif role == qt.Qt.FontRole:
            font = qt.QFont()
            font.setBold(True)
            return font


class DeltasHeaderView(qt.QHeaderView):
    DOT_COLOR = qt.QColor('#1f77b4')

    def __init__(self, parent=None, deltasModel=None, hideLastBrace=False):
        super().__init__(qt.Qt.Horizontal, parent=parent)
        self.deltasModel = deltasModel
        self.setModel(DeltasHeaderModel(deltasModel))
        self.hideLastBrace = hideLastBrace
        self.setFixedHeight(HEADERHEIGHT)

    def paintSection(self, painter, rect, logicalIndex):
        painter.setRenderHint(qt.QPainter.Antialiasing, True)
        # painter.save()
        # super().paintSection(painter, rect, logicalIndex)
        # painter.restore()

        opt = qt.QStyleOption()
        opt.initFrom(self)

        font = self.model().headerData(logicalIndex, role=qt.Qt.FontRole)
        if font is not None:
            painter.setFont(font)
        txt = self.model().headerData(logicalIndex)
        alignment = self.model().headerData(
            logicalIndex, role=qt.Qt.TextAlignmentRole)
        rectT = rect.translated(0, -2)  # a copy of rect
        painter.drawText(rectT, alignment, txt)

        if not hasattr(self.deltasModel, 'curDeltas'):
            return
        delta = self.deltasModel.curDeltas[logicalIndex]
        factor = delta / self.deltasModel.minDelta if delta > 0 else -1

        if (opt.state & qt.QStyle.State_Enabled):
            painter.setPen(qt.QPen(qt.QColor('darkblue'), 2.0))
        else:
            painter.setPen(qt.QPen(qt.QColor('darkgray'), 2.0))
        if logicalIndex > 0:  # left half-brace
            ll = rect.left()
            painter.drawArc(ll, 5, 10, 10, 90*16, 90*16)
            painter.drawLine(ll+5, 5, ll+13, 5)
            painter.drawArc(ll+8, -5, 10, 10, 270*16, 90*16)
        if logicalIndex < self.deltasModel.columnCount()-1 \
                or not self.hideLastBrace:  # right half-brace
            r = rect.right()
            painter.drawArc(r-18, -5, 10, 10, 180*16, 90*16)
            painter.drawLine(r-11, 5, r-7, 5)
            painter.drawArc(r-10, 5, 10, 10, 0*16, 90*16)

        if (opt.state & qt.QStyle.State_Enabled):
            # if (opt.state & qt.QStyle.State_MouseOver):
            color = self.DOT_COLOR
        else:
            color = qt.QColor('darkgray')

        painter.setBrush(color)
        painter.setPen(color)
        dx, dy = DOTSIZE
        sx = DOTDELTA
        rectd = qt.QRect(rect.x(), rect.bottom()-dy, dx, dy)
        painter.drawRect(rectd)
        di = 0
        while rectd.x() < rect.right():
            if factor > 0:
                rectd.translate(int((dx+sx)*factor), 0)
            else:
                di += 1
                rectd.translate(dx+sx+di, 0)
            painter.drawRect(rectd)


class VHeaderModel(qt.QAbstractItemModel):
    def __init__(self, captions):
        super().__init__()
        self.captions = captions

    def columnCount(self, parent):
        return 1

    def rowCount(self, parent):
        return len(self.captions)

    def headerData(self, section, orientation=qt.Qt.Horizontal,
                   role=qt.Qt.DisplayRole):
        if role == qt.Qt.DisplayRole:
            return self.captions[section]
        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignCenter
        # elif role == qt.Qt.FontRole:
        #     font = qt.QFont()
        #     font.setBold(True)
        #     return font


class VHeaderView(qt.QHeaderView):
    def __init__(self, parent, captions=None):
        super().__init__(qt.Qt.Vertical, parent=parent)
        self.setModel(VHeaderModel(captions))

    def paintSection(self, painter, rect, logicalIndex):
        painter.setRenderHint(qt.QPainter.Antialiasing, True)
        font = self.model().headerData(logicalIndex, role=qt.Qt.FontRole)
        if font is not None:
            painter.setFont(font)
        alignment = self.model().headerData(
            logicalIndex, role=qt.Qt.TextAlignmentRole)
        txt = self.model().headerData(logicalIndex)
        if txt == 'bins':
            what = 'orig' if logicalIndex == 0 else 'new'
            for it, t in enumerate([what, txt]):
                rr = rect.translated(0, -8)  # a copy of rect
                # rr.setHeight(4)
                painter.drawText(rr.translated(0, it*12), alignment, t)
        else:
            painter.drawText(rect, alignment, txt)


class DoubleSpinBoxDelegate(qt.QStyledItemDelegate):
    def __init__(self, parent, limits, alignment):
        super().__init__(parent)
        self.limits = limits
        self.alignment = alignment

    def createEditor(self, parent, option, index):
        dsb = qt.QDoubleSpinBox(parent)
        if len(self.limits) == 0:  # last section and hideLastBrace is True
            return
        dsb.setMinimum(float(self.limits[0]))
        dsb.setMaximum(float(self.limits[1]))
        step = self.limits[2]
        dsb.setSingleStep(step)
        decimals = getDecimals(step)
        dsb.setDecimals(decimals)
        dsb.setAlignment(self.alignment)
        return dsb

    def setEditorData(self, editor, index):
        # editor.blockSignals(True)
        editor.setValue(float(index.data()))
        # editor.blockSignals(False)

    def setModelData(self, editor, model, index):
        if (len(editor.text()) == 0) and (self.limits[1] == 'inf'):
            model.setData(index, float('inf'))
            return
        model.setData(index, editor.value())

    def eventFilter(self, editor, event):
        if (event.type() == qt.QEvent.KeyPress and
                event.key() == qt.Qt.Key_Return):
            self.commitData.emit(editor)
            if True:  # emit closeEditor
                self.closeEditor.emit(editor)
            else:  # select contents instead
                editor.selectAll()
            return True
        return False

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect.x(), option.rect.y(),
                           option.rect.width(), option.rect.height()-1)


class SplittersTableView(qt.QTableView):
    def __init__(self, parent, model):
        super().__init__(parent)
        self.setFocusPolicy(qt.Qt.NoFocus)
        self.setModel(model)
        horHeader = DeltasHeaderView(self, model)  # needed for getting sizes
        self.setHorizontalHeader(horHeader)
        verHeader = VHeaderView(self, ['limits'])
        self.setVerticalHeader(verHeader)
        if 'pyqt4' in qt.BINDING.lower():
            horHeader.setMovable(False)
            # for c in range(model.columnCount()):
            horHeader.setResizeMode(qt.QHeaderView.ResizeToContents)
            horHeader.setClickable(False)
            verHeader.setClickable(False)
            verHeader.setResizeMode(qt.QHeaderView.Fixed)
            verHeader.setDefaultSectionSize(ROWHEIGHT)
        else:
            horHeader.setSectionsMovable(False)
            # for c in range(model.columnCount()):
            horHeader.setSectionResizeMode(qt.QHeaderView.ResizeToContents)
            horHeader.setSectionsClickable(False)
            verHeader.setSectionsClickable(False)
            verHeader.setSectionResizeMode(qt.QHeaderView.Fixed)
            verHeader.setDefaultSectionSize(ROWHEIGHT)
        horHeader.setStretchLastSection(True)
        horHeader.hide()
        self.setStyleSheet("""QTableView {
            border-top: 1px solid black; border-bottom: 0px solid black;
            border-left: 1px solid black; border-right: 1px solid black;}""")

        for c in range(model.columnCount()):
            kw = dict(limits=model.splitters[c][2:5],  # min, max, step
                      alignment=qt.Qt.AlignRight | qt.Qt.AlignVCenter)
            self.setItemDelegateForColumn(c, DoubleSpinBoxDelegate(self, **kw))
        self.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.setShowGrid(False)
        self.setFixedHeight(ROWHEIGHT+1)


class DeltasTableView(qt.QTableView):
    def __init__(self, parent, model, hideLastBrace):
        super().__init__(parent)
        self.setFocusPolicy(qt.Qt.NoFocus)
        self.setModel(model)
        horHeader = DeltasHeaderView(self, model, hideLastBrace)
        self.setHorizontalHeader(horHeader)
        verHeader = VHeaderView(self, ['bins', 'δ', 'bins'])
        self.setVerticalHeader(verHeader)
        model.headerDataChanged.connect(self.redrawHeader)

        if 'pyqt4' in qt.BINDING.lower():
            horHeader.setMovable(False)
            # for c in range(model.columnCount()):
            horHeader.setResizeMode(qt.QHeaderView.ResizeToContents)
            horHeader.setClickable(False)
            verHeader.setClickable(False)
            verHeader.setResizeMode(qt.QHeaderView.Fixed)
            verHeader.setDefaultSectionSize(ROWHEIGHT)
        else:
            horHeader.setSectionsMovable(False)
            # for c in range(model.columnCount()):
            horHeader.setSectionResizeMode(qt.QHeaderView.ResizeToContents)
            horHeader.setSectionsClickable(False)
            verHeader.setSectionsClickable(False)
            verHeader.setSectionResizeMode(qt.QHeaderView.Fixed)
            verHeader.setDefaultSectionSize(ROWHEIGHT)
        horHeader.setStretchLastSection(True)
        self.setStyleSheet("""QTableView {
            border-top: 0px solid black; border-bottom: 1px solid black;
            border-left: 1px solid black; border-right: 1px solid black;}
            QTableView QTableCornerButton::section {
                background: #eeeeee; border: 0px;}""")

        for c in range(model.columnCount()):
            # self.setColumnWidth(c, 80)
            kw = dict(limits=model.deltas[c][2:5],  # min, max, step
                      alignment=qt.Qt.AlignCenter)
            self.setItemDelegateForColumn(c, DoubleSpinBoxDelegate(self, **kw))
        self.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        # self.setShowGrid(False)
        self.setFixedHeight(HEADERHEIGHT + (ROWHEIGHT+1)*3)

    def redrawHeader(self, orientation, logicalFirst, logicalLast):
        self.horizontalHeader().headerDataChanged(
            orientation, logicalFirst, logicalLast)


class DataRebinWidget(qt.QWidget):
    regionsChanged = qt.pyqtSignal()

    def __init__(self, parent=None, regions=()):
        super().__init__(parent)
        captions, deltas, splitters = regions
        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.splittersModel = SplittersModel(captions, splitters)
        self.splittersView = SplittersTableView(self, self.splittersModel)
        self.deltasModel = DeltasModel(captions, deltas)
        self.deltasView = DeltasTableView(self, self.deltasModel,
                                          len(splitters) < len(captions))
        layout.addWidget(self.splittersView)
        layout.addWidget(self.deltasView)
        self.setLayout(layout)
        self.splittersView.clearSelection()
        self.deltasView.clearSelection()
        self.splittersView.setMinimumWidth(380)
        self.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)

        self.splittersModel.dataChanged.connect(self.updateClient)
        self.deltasModel.dataChanged.connect(self.updateClient)

    def getRegions(self):
        return dict(
            deltas=[v[1] for v in self.deltasModel.deltas if len(v) > 1],
            splitters=[v[1] for v in self.splittersModel.splitters
                       if len(v) > 1])

    def setRegions(self, regions):
        for o, n in zip(self.deltasModel.deltas, regions['deltas']):
            o[1] = n
        for o, n in zip(self.splittersModel.splitters, regions['splitters']):
            o[1] = n

    def updateClient(self, topLeft, bottomRight, roles):
        model = topLeft.model()
        row = topLeft.row()
        if ((model is self.splittersModel and row == 0) or
                (model is self.deltasModel and row == 1)):
            self.regionsChanged.emit()

    def setBinNumbers(self, kind, values):
        if kind == 0:
            self.deltasModel.binNumbersOld = values
            row = 0
        elif kind == 1:
            self.deltasModel.binNumbersNew = values
            row = 2
        else:
            return
        ind1 = self.deltasModel.index(row, 0)
        ind2 = self.deltasModel.index(row, 3)
        self.deltasModel.dataChanged.emit(ind1, ind2)
