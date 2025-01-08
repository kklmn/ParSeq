# -*- coding: utf-8 -*-
u"""
Fit widgets
-----------

Custom fit widgets are supposed to inherit from :class:`FitWidget` that gives
some common functionality to all fit widgets.

A custom widget typically instantiates a table view class for displaying
fitting parameters and an associated table model class for it.
"""
__author__ = "Konstantin Klementiev"
__date__ = "29 Nov 2023"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from functools import partial
from silx.gui import qt, icons
from ...core import singletons as csi
from ...core.logger import syslogger
from ...gui.roi import AutoRangeWidget

GOOD_BKGND = '#90ee90'
BAD_BKGND = '#ff8877'


class CorrModel(qt.QAbstractTableModel):
    def __init__(self, defnames=[]):
        super().__init__()
        self.setTable(names=defnames)

    def rowCount(self, parent=qt.QModelIndex()):
        return self.corr.shape[0]

    def columnCount(self, parent=qt.QModelIndex()):
        return self.corr.shape[1]

    def flags(self, index):
        return qt.Qt.NoItemFlags

    def setTable(self, names=None, corr=None, emit=True):
        self.beginResetModel()
        self.names = names if names else ['p1', 'p2']
        self.corr = corr if corr is not None else np.identity(len(self.names))
        self.endResetModel()
        if emit:
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def data(self, index, role):
        column, row = index.column(), index.row()
        if role == qt.Qt.ToolTipRole:
            corr = self.corr[row, column]
            txt = '{0} ∩ {1}\n{2:#.4g}'.format(
                self.names[row], self.names[column], corr)
            if not (-1-1e-8 < corr < 1+1e-8):
                txt += '\nA value not within [0, 1] means no'
                txt += '\nχ² minimum in particular variables.'
                txt += '\nTry to change the fit range.'
            return txt
        elif role == qt.Qt.BackgroundRole:
            corr = self.corr[row, column]
            if corr > 0:
                return qt.QColor(int(corr * 255), 0, 0)
            else:
                return qt.QColor(0, 0, int(-corr * 255))

    def headerData(self, section, orientation, role):
        if role == qt.Qt.DisplayRole:
            if orientation == qt.Qt.Horizontal:
                return str(section+1)
            elif orientation == qt.Qt.Vertical:
                try:
                    return '{0} {1}'.format(section+1, self.names[section])
                except Exception:
                    return str(section+1)
        # elif role == qt.Qt.TextAlignmentRole:
        #     if orientation == qt.Qt.Horizontal:
        #         return qt.Qt.AlignCenter
        elif role == qt.Qt.ToolTipRole:
            if orientation == qt.Qt.Horizontal:
                try:
                    return self.names[section]
                except Exception:
                    return str(section+1)


class CorrTableView(qt.QTableView):
    cellSize = 24

    def __init__(self, parent, model):
        super().__init__(parent)
        self.setCornerButtonEnabled(False)
        self.setModel(model)

        horHeaders = UnderlinedHeaderView(qt.Qt.Horizontal, self)
        horHeaders.setFixedHeight(self.cellSize)
        self.setHorizontalHeader(horHeaders)
        verHeaders = self.verticalHeader()  # QHeaderView instance

        nC = model.columnCount()
        for headers in (horHeaders, verHeaders):
            headers.setMinimumSectionSize(self.cellSize)
            if 'pyqt4' in qt.BINDING.lower():
                headers.setMovable(False)
                for i in range(nC):
                    headers.setResizeMode(i, qt.QHeaderView.Fixed)
                headers.setClickable(False)
            else:
                headers.setSectionsMovable(False)
                for i in range(nC):
                    headers.setSectionResizeMode(i, qt.QHeaderView.Fixed)
                headers.setSectionsClickable(False)
            headers.setStretchLastSection(False)
            headers.setDefaultSectionSize(self.cellSize)
            # for i in range(nC):
            #     self.setColumnWidth(i, self.cellSize)
            #     self.setRowHeight(i, self.cellSize)
        horHeaders.hide()

        height = 4*self.cellSize + 2
        self.setMinimumHeight(height)


class UnderlinedHeaderView(qt.QHeaderView):
    "The separation line between header and table is missing on Windows 10/11."
    BOTTOM_COLOR = qt.QColor('#cccccc')

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        painter.setPen(qt.QPen(qt.QColor(self.BOTTOM_COLOR), 0.5))
        bottom = rect.bottom()
        painter.drawLine(rect.left(), bottom, rect.right(), bottom)


class FitWidget(qt.QWidget):
    """
    Base widget for custom fit widgets. It sends fit parameters to the fit
    table model (provided by custom widgets), provides a range widget and
    reactions on it, a display widget for fit results and a start button. It
    also send `fitReady` signal to the node widget.
    """
    fitReady = qt.pyqtSignal()

    def __init__(self, parent, worker, plot):
        super().__init__(parent)
        self.worker = worker
        self.plot = plot

    def addRangeAndStartWidgets(
        self, layout, layoutRange=None, caption='fit range',
        tooltip='eMin, eMax', rangeName='fit-range', color="#da70d6",
            formatStr="{0[0]:.1f}, {0[1]:.1f}"):
        layoutLoc = qt.QHBoxLayout()
        if layoutRange is None:
            layoutRange = layoutLoc
        if isinstance(self.plot, (list, tuple)):
            if isinstance(caption, str):
                caption = caption, caption
            if isinstance(tooltip, str):
                tooltip = tooltip, tooltip
            if isinstance(rangeName, str):
                rangeName = rangeName, rangeName
            if isinstance(color, str):
                color = color, color
            if isinstance(formatStr, str):
                formatStr = formatStr, formatStr
            self.rangeWidget = []
            for iw, (plot, cap, ttip, rName, clr, fStr) in enumerate(zip(
                    self.plot, caption, tooltip, rangeName, color, formatStr)):
                rw = AutoRangeWidget(self, plot, cap, ttip, rName, clr, fStr)
                rangeName = 'range' if iw == 0 else 'range{0}'.format(iw+1)
                rw.rangeChanged.connect(
                    partial(self.updateFromRangeWidget, rangeName))
                rw.editCustom.returnPressed.connect(
                    partial(self.updateRange, rw))
                rw.rangeToggled.connect(partial(self.toggleRange, iw))
                self.rangeWidget.append(rw)
                layoutRange.addWidget(rw)
        else:
            rw = AutoRangeWidget(self, self.plot, caption, tooltip, rangeName,
                                 color, formatStr)
            self.rangeWidget = rw
            rw.rangeChanged.connect(
                partial(self.updateFromRangeWidget, 'range'))
            rw.editCustom.returnPressed.connect(partial(self.updateRange, rw))
            rw.rangeToggled.connect(partial(self.toggleRange, 0))
            layoutLoc.addWidget(rw)

        self.fitR = qt.QLabel('')
        layoutLoc.addWidget(self.fitR)
        self.fitN = qt.QLabel('')
        layoutLoc.addWidget(self.fitN)

        self.startButton = qt.QPushButton('Start fitting')
        self.startButton.setIcon(icons.getQIcon('next'))
        self.startButton.clicked.connect(self.start)
        layoutLoc.addStretch()
        layoutLoc.addWidget(self.startButton)
        layout.addLayout(layoutLoc)

    def setSpectrum(self, spectrum):
        self.spectrum = spectrum
        try:
            dfparams = spectrum.fitParams
            fitVars = dfparams[self.worker.ioAttrs['params']]
        except (KeyError, AttributeError):
            return
        self.fitModel.setParams(fitVars)
        try:
            if isinstance(self.rangeWidget, (list, tuple)):
                for iw, w in enumerate(self.rangeWidget):
                    attr = 'x' if iw == 0 else 'x{0}'.format(iw+1)
                    x = getattr(spectrum, self.worker.dataAttrs[attr])
                    w.defaultRange = [x.min(), x.max()]
            else:
                x = getattr(spectrum, self.worker.dataAttrs['x'])
                self.rangeWidget.defaultRange = [x.min(), x.max()]
        except Exception as e:
            syslogger.error(str(e))
            return

        if isinstance(self.rangeWidget, (list, tuple)):
            for iw, w in enumerate(self.rangeWidget):
                if w.panel.isCheckable():
                    attr = 'use_range' if iw == 0 else \
                        'use_range{0}'.format(iw+1)
                    if attr in self.worker.ioAttrs:
                        use = dfparams[self.worker.ioAttrs[attr]]
                        w.panel.setChecked(use)
                else:
                    use = True
                attr = 'range' if iw == 0 else 'range{0}'.format(iw+1)
                if attr in self.worker.ioAttrs:
                    xrange = dfparams[self.worker.ioAttrs[attr]]
                    if xrange is not None:
                        w.setRange(xrange, use)
                    else:
                        w.setAutoRange()
        else:
            if self.rangeWidget.panel.isCheckable():
                if 'use_range' in self.worker.ioAttrs:
                    use = dfparams[self.worker.ioAttrs['use_range']]
                    self.rangeWidget.panel.setChecked(use)
            else:
                use = True

            if 'range' in self.worker.ioAttrs:
                xrange = dfparams[self.worker.ioAttrs['range']]
                if xrange is not None:
                    self.rangeWidget.setRange(xrange, use)
                else:
                    self.rangeWidget.setAutoRange()

    def updateFromRangeWidget(self, rangeName, ran):
        if self.spectrum is None:
            return
        dfparams = self.spectrum.fitParams
        if rangeName in self.worker.ioAttrs:
            dfparams[self.worker.ioAttrs[rangeName]] = list(ran)

    def updateRange(self, w=None):
        if w is None:
            w = self.rangeWidget
        ran = w.acceptEdit()
        w.setRange(ran)

    def toggleRange(self, iw=0, on=True):
        if self.spectrum is None:
            return
        attr = 'use_range' if iw == 0 else 'use_range{0}'.format(iw+1)
        if attr in self.worker.ioAttrs:
            dfparams = self.spectrum.fitParams
            dfparams[self.worker.ioAttrs[attr]] = on

    def start(self):
        if len(csi.selectedItems) == 0:
            return
        self.startButton.setEnabled(False)
        self.worker.run(dataItems=csi.selectedItems)

        self.startButton.setEnabled(True)
        cs = csi.selectedItems[0]
        dfparams = cs.fitParams
        fitVars = dfparams[self.worker.ioAttrs['params']]
        self.fitModel.setParams(fitVars, False)
        self.updateCorrMatrix()
        self.updateFitResults()
        self.fitReady.emit()

    def updateFitResults(self):
        if self.spectrum is None:
            return
        if hasattr(self.spectrum, 'error') and self.spectrum.error:
            self.fitR.setToolTip(self.spectrum.error)
            clr = BAD_BKGND
            self.fitR.setStyleSheet("QLabel {background-color: "+clr+";}")
            return

        dfparams = self.spectrum.fitParams

        fitRes = dfparams[self.worker.ioAttrs['result']]
        if fitRes['ier']:
            clr = GOOD_BKGND if 1 <= fitRes['ier'] <= 4 else BAD_BKGND
            self.fitR.setStyleSheet("QLabel {background-color: "+clr+";}")
        else:
            self.fitR.setStyleSheet('')

        if fitRes['R']:
            self.fitR.setText('R={0:.5g}'.format(fitRes['R']))
            self.fitR.setToolTip(fitRes['mesg'])
        else:
            self.fitR.setText('')
            self.fitR.setToolTip('')

        info = fitRes['info']
        if 'nfev' in info:
            txt = '{0} function call{1}'.format(
                info['nfev'], '' if info['nfev'] == 1 else 's')
            if 'Nind' in fitRes:
                txt += ', Nind={0:.2f}'.format(fitRes['Nind'])
            txt += ', P={0}'.format(fitRes['nparam'])
            if 'Nind' in fitRes:
                txt += ', ν={0:.2f}'.format(fitRes['Nind']-fitRes['nparam'])
            self.fitN.setText(txt)
        else:
            self.fitN.setText('')

    def updateCorrMatrix(self):
        if not hasattr(self, 'corrModel'):
            return
        if self.spectrum is None:
            return
        dfparams = self.spectrum.fitParams
        if not self.fitModel.params:
            return
        fitRes = dfparams[self.worker.ioAttrs['result']]
        P = fitRes['nparam']
        info = fitRes['info']
        pnames = info['fitKeys'] if 'fitKeys' in info else \
            ['{0}'.format(i) for i in range(P)]
        corr = fitRes['corr'] if 'corr' in fitRes else np.identity(P)
        self.corrModel.setTable(pnames, corr)
