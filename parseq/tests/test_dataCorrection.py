# coding: utf-8

from functools import partial
import numpy as np

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.gcorrection import Correction1DWidget
from parseq.core.correction import calc_correction
from silx.gui.plot import Plot1D

curveLabel = 'test_curve'
corrections1 = [
    dict(kind='delete', name='del1', lim=(8950, 9050)),
    ]
corrections2 = [
    dict(kind='scale', name='scl1', lim=(8950, 9050), scale=0.8),
    dict(kind='spikes', name='spk1', lim=(8960, 9070), cutoff='auto'),
    ]
corrections3 = [
    dict(kind='spline', name='spl1', lim=(8950, 9050),
         knots=[[8960, 0.8], [9000, 0.9], [9030, 1.0]]),
    dict(kind='step', name='stp1', left=8950, right=[8960, 0.8]),
    ]
allCorrections = [corrections1, corrections2, corrections3]


def test_curve(col=1):
    fpath = "data/cu-ref-mix.res"

    with open(fpath, 'r') as f:
        header = f.readline()
    refNames = header.split()
    data = np.loadtxt(fpath, skiprows=1)
    return data[:, 0], data[:, col], refNames[col]


def correctionDockVisibilityChanged(visible, correctionWidget):
    if not visible:
        correctionWidget.roiManager.stop()


def syncCorrection(correctionWidget):
    plot = correctionWidget.plot
    curve = plot.getCurve(curveLabel)
    if curve is None:
        return
    e0, mu0 = plot._test_curve

    corrections = correctionWidget.getCorrections()
    print(corrections)

    correction = correctionWidget.getCurrentCorrection()
    if correction is None:
        curve.setData(e0, mu0)
        return

    res = calc_correction(e0, mu0, correction)
    if res is not None:
        en, mun = res[0:2]
        curve.setData(en, mun)


def cycleCorrections(correctionWidget):
    correctionWidget.iCorr += 1
    if correctionWidget.iCorr >= len(allCorrections):
        correctionWidget.iCorr = 0
    correctionWidget.setCorrections(allCorrections[correctionWidget.iCorr])


def main():
    app = qt.QApplication([])  # Start QApplication

    # Create the plot widget and add a curve
    e0, mu0, header = test_curve(4)
    print("test data lngth = {}".format(len(mu0)))
    plot = Plot1D()
    plot.setGraphTitle(header)
    plot.setGraphXLabel(label='energy (eV)')
    plot.setGraphYLabel(label='normalized absorptance')
    plot.addCurve(e0, mu0, legend=curveLabel)
    plot._test_curve = e0, mu0

    rightDockWidget = qt.QWidget()
    layout = qt.QVBoxLayout()
    correctionWidget = Correction1DWidget(
        None, None, plot,  # parent, node, plot
        ['CorrectionDelete', 'CorrectionScale',
         'CorrectionSpline', 'CorrectionStep', 'CorrectionSpikes'])
    correctionWidget.iCorr = 0
    correctionWidget.setCorrections(allCorrections[correctionWidget.iCorr])
    correctionWidget.table.sigCorrectionChanged.connect(partial(
        syncCorrection, correctionWidget))
    layout.addWidget(correctionWidget)
    gotoNextCorrectionDict = qt.QPushButton('go to next Corrections')
    gotoNextCorrectionDict.pressed.connect(partial(
        cycleCorrections, correctionWidget))
    layout.addWidget(gotoNextCorrectionDict)
    rightDockWidget.setLayout(layout)

    dock = qt.QDockWidget('1D corrections')
    dock.setWidget(rightDockWidget)
    dock.visibilityChanged.connect(partial(
        correctionDockVisibilityChanged, correctionWidget))
    plot.addDockWidget(qt.Qt.RightDockWidgetArea, dock)

    # Show the widget and start the application
    plot.show()
    result = app.exec()
    app.deleteLater()
    sys.exit(result)


if __name__ == '__main__':
    main()
