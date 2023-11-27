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
__date__ = "30 May 2023"
# !!! SEE CODERULES.TXT !!!

from functools import partial
from silx.gui import qt, icons
from ...core import singletons as csi
from ...gui.roi import RangeWidget

GOOD_BKGND = '#90ee90'
BAD_BKGND = '#ff8877'


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
                rw = RangeWidget(self, plot, cap, ttip, rName, clr, fStr)
                rangeName = 'range' if iw == 0 else 'range{0}'.format(iw+1)
                rw.rangeChanged.connect(
                    partial(self.updateFromRangeWidget, rangeName))
                rw.editCustom.returnPressed.connect(
                    partial(self.updateRange, rw))
                rw.rangeToggled.connect(partial(self.toggleRange, iw))
                self.rangeWidget.append(rw)
                layoutRange.addWidget(rw)
        else:
            rw = RangeWidget(self, self.plot, caption, tooltip, rangeName,
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
            print(e)
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
