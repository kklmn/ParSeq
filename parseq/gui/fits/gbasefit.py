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

from silx.gui import qt
from ...core import singletons as csi
from ...gui.roi import RangeWidget

GOOD_BKGND = '#90ee90'
BAD_BKGND = '#ff8877'


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

    def addRangeAndStartWidgets(self, layout):
        layoutR = qt.QHBoxLayout()
        self.rangeWidget = RangeWidget(
            self, self.plot, 'fit range', 'eMin, eMax', 'fit-range',
            "#da70d6", "{0[0]:.1f}, {0[1]:.1f}")
        self.rangeWidget.rangeChanged.connect(self.updateFromRangeWidget)
        self.rangeWidget.editCustom.returnPressed.connect(self.updateRange)
        layoutR.addWidget(self.rangeWidget)

        self.fitR = qt.QLabel('')
        layoutR.addWidget(self.fitR)
        self.fitN = qt.QLabel('')
        layoutR.addWidget(self.fitN)

        self.startButton = qt.QPushButton('start fitting')
        self.startButton.clicked.connect(self.start)
        layoutR.addStretch()
        layoutR.addWidget(self.startButton)
        layout.addLayout(layoutR)

    def setSpectrum(self, spectrum):
        self.spectrum = spectrum
        dfparams = spectrum.fitParams
        fitVars = dfparams[self.worker.ioAttrs['params']]
        self.fitModel.setParams(fitVars)
        try:
            x = getattr(spectrum, self.worker.dataAttrs['x'])
        except Exception as e:
            print(e)
            return
        self.rangeWidget.defaultRange = [x.min(), x.max()]
        xrange = dfparams[self.worker.ioAttrs['range']]
        if xrange is not None:
            self.rangeWidget.setRange(xrange)
        else:
            self.rangeWidget.setAutoRange()

    def updateFromRangeWidget(self, ran):
        dfparams = self.spectrum.fitParams
        dfparams[self.worker.ioAttrs['range']] = list(ran)

    def updateRange(self):
        ran = self.rangeWidget.acceptEdit()
        self.rangeWidget.setRange(ran)

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
            self.fitN.setText(
                '{0} function call{1}, {2} fitting parameter{3}'.format(
                    info['nfev'], '' if info['nfev'] == 1 else 's',
                    fitRes['nparam'], '' if fitRes['nparam'] == 1 else 's'))
        else:
            self.fitN.setText('')
