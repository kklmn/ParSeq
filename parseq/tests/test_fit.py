# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 May 2023"
# !!! SEE CODERULES.TXT !!!

import numpy as np

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
import parseq.fits as fits
from parseq.gui.fits.glcf import LCFWidget
from parseq.gui.fits.gfunctionfit import FunctionFitWidget
from parseq.gui.plot import Plot1D

from silx.gui import qt


class LCF(fits.lcf.LCF):
    name = 'LCF'
    xVary = True
    dataAttrs = dict(x='e', y='mu', fit='fit')
    allDataAttrs = dict(x='e', y='mu')
    nThreads = 4


class FunctionFit(fits.functionfit.FunctionFit):
    name = 'FunctionFit'
    dataAttrs = dict(x='e', y='mu', fit='fit')
    nThreads = 2


class LCFTestWidget(qt.QWidget):
    def __init__(self, parent=None, fitData=None):
        super().__init__(parent)
        self.move(200, 100)

        self.fitData = fitData
        self.currentSpectrum = None

        layout = qt.QVBoxLayout()

        self.spectra = qt.QListWidget(self)
        self.spectra.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        if fitData is not None:
            self.spectra.addItems([d.alias for d in fitData])
        self.spectra.setFixedHeight(48)
        self.spectra.selectionModel().selectionChanged.connect(self.selChanged)
        layout.addWidget(self.spectra)

        self.plot = Plot1D(self)
        self.plot.getXAxis().setLabel('energy (eV)')
        self.plot.getYAxis().setLabel('µd')

        self.lcfWorker = LCF()
        self.lcfWidget = LCFWidget(self, worker=self.lcfWorker, plot=self.plot)
        self.lcfWidget.fitReady.connect(self.replot)
        layout.addWidget(self.lcfWidget)

        layout.addWidget(self.plot)

        # layout.addStretch()
        self.setLayout(layout)

        self.spectra.setCurrentRow(0)

    def replot(self):
        cs = self.currentSpectrum
        if cs is None:
            return
        if not hasattr(cs, 'fit'):
            cs.fit = np.zeros_like(cs.e)
        self.plot.addCurve(cs.e, cs.mu, legend='data')
        self.plot.addCurve(cs.e, cs.fit, legend='fit')
        if cs.fit.any():  # any non-zero
            self.plot.addCurve(cs.e, cs.mu-cs.fit, legend='res')

        selectedIndexes = self.spectra.selectionModel().selectedRows()
        for ind in selectedIndexes:
            tt = self.fitData[ind.row()]
            item = self.spectra.item(ind.row())
            if hasattr(tt, 'error') and (tt.error is not None):
                item.setToolTip(tt.error)
                item.setBackground(qt.QBrush(qt.QColor('red')))
            else:
                item.setToolTip('')
                item.setBackground(qt.QBrush())

    def selChanged(self, selected, deselected):
        selectedIndexes = self.spectra.selectionModel().selectedRows()
        inds = [ind.row() for ind in selectedIndexes]
        csi.selectedItems = [self.fitData[ind] for ind in inds]
        self.currentSpectrum = csi.selectedItems[0]
        self.lcfWidget.setSpectrum(self.currentSpectrum)
        self.replot()


class FunctionFitTestWidget(qt.QWidget):
    def __init__(self, parent=None, fitData=None):
        super().__init__(parent)
        self.move(200, 100)

        self.fitData = fitData

        self.currentSpectrum = None

        layout = qt.QVBoxLayout()

        self.spectra = qt.QListWidget(self)
        self.spectra.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        if fitData is not None:
            self.spectra.addItems([d.alias for d in fitData])
        self.spectra.setFixedHeight(48)
        self.spectra.selectionModel().selectionChanged.connect(self.selChanged)
        layout.addWidget(self.spectra)

        self.plot = Plot1D(self)
        self.plot.getXAxis().setLabel('energy (eV)')
        self.plot.getYAxis().setLabel('µd')

        self.funcFitWorker = FunctionFit()
        self.funcFitWidget = FunctionFitWidget(
            self, worker=self.funcFitWorker, plot=self.plot)
        self.funcFitWidget.fitReady.connect(self.replot)
        layout.addWidget(self.funcFitWidget)

        layout.addWidget(self.plot)

        # layout.addStretch()
        self.setLayout(layout)

        self.spectra.setCurrentRow(0)

    def replot(self):
        cs = self.currentSpectrum
        if cs is None:
            return
        if not hasattr(cs, 'fit'):
            cs.fit = np.zeros_like(cs.e)
        self.plot.addCurve(cs.e, cs.mu, legend='data')
        self.plot.addCurve(cs.e, cs.fit, legend='fit')
        if cs.fit.any():  # any non-zero
            self.plot.addCurve(cs.e, cs.mu-cs.fit, legend='res')

        selectedIndexes = self.spectra.selectionModel().selectedRows()
        for ind in selectedIndexes:
            tt = self.fitData[ind.row()]
            item = self.spectra.item(ind.row())
            if hasattr(tt, 'error') and (tt.error is not None):
                item.setToolTip(tt.error)
                item.setBackground(qt.QBrush(qt.QColor('red')))
            else:
                item.setToolTip('')
                item.setBackground(qt.QBrush())

    def selChanged(self, selected, deselected):
        selectedIndexes = self.spectra.selectionModel().selectedRows()
        inds = [ind.row() for ind in selectedIndexes]
        csi.selectedItems = [self.fitData[ind] for ind in inds]
        self.currentSpectrum = csi.selectedItems[0]
        self.funcFitWidget.setSpectrum(self.currentSpectrum)
        self.replot()


class DataProxy(object):
    """An empty object to attach fields to it. With a simple instance of
    object() this is impossible but doable with an empty class."""
    pass


def read_data(fpath, usecols):
    # fname = osp.split(fpath)[1]
    with open(fpath, 'r') as f:
        header = f.readline()
    rawRefNames = header.split()
    refNames = [rawRefNames[i] for i in usecols]

    data = np.loadtxt(fpath, skiprows=1)
    e = data[:, 0]

    allData = []
    for i, refName in zip(usecols, refNames):
        spectrum = DataProxy()
        spectrum.alias = refName
        spectrum.e = e
        spectrum.mu = data[:, i]
        spectrum.transfortmTimes = {}
        allData.append(spectrum)
    csi.allLoadedItems = allData

    mix1 = DataProxy()
    mix1.alias = 'mix1'
    mix1.e = e
    mix1.mu = data[:, -2]
    mix1.transfortmTimes = {}
    mix1BasisNames = ['cufe2o4_ave4', 'cus_ave2', 'cucl_w_ave2']
    w1 = 1./len(mix1BasisNames)
    lcfParams = []
    for refName in mix1BasisNames:
        lcfParams.append(
            dict(name=refName, use=True, w=w1, wBounds=[0., 1., 0.01],
                 dx=0., dxBounds=[-1., 1., 0.01],
                 # may have wtie, dxtie, later added: wError, dxError
                 ))
    # lcf_result = dict(R=None, mesg='', ier=None, info={}, nparam=0)
    # ffit_result = dict(R=None, mesg='', ier=None, info={}, nparam=0)
    mix1.fitParams = dict(
        lcf_params=lcfParams, lcf_xRange=[8850, 9100],
        ffit_formula='a*(np.arctan((x-b)/c)+np.pi/2) + '
        'd*np.exp(-(x-e)**2/f**2)',
        ffit_params=dict(
            a=dict(value=0.3, step=0.01, tie='fixed', lim=[0., 2.]),
            b=dict(value=8980., step=0.1, lim=[8950., 9050.]),
            c=dict(value=5., step=0.1, lim=[0., 30.]),
            d=dict(value=0.2, step=0.01, lim=[0., 2.]),
            e=dict(value=8996., step=0.1, tie='=b+15', lim=[8950., 9050.]),
            f=dict(value=5., step=0.1, lim=[0., 30.])),
        ffit_xRange=[8850, 9100]
        )

    mix2 = DataProxy()
    mix2.alias = 'mix2'
    mix2.e = e
    mix2.mu = data[:, -1]
    mix2.transfortmTimes = {}
    mix2BasisNames = ['cuoh2_ave4', 'cucl2_ave2', 'cuco36h2o_ave3', 'cuo_ave2']
    w2 = 1./len(mix2BasisNames)
    lcfParams = []
    for refName in mix2BasisNames:
        lcfParams.append(
            dict(name=refName, use=True, w=w2, wBounds=[0., 1., 0.01],
                 dx=0., dxBounds=[-1., 1., 0.01],
                 # may have wtie, dxtie, later added: wError, dxError
                 ))
    lcfParams[3]['dEtie'] = "=dE[1]"
    # lcf_result = dict(R=None, mesg='', ier=None, info={}, nparam=0)
    # ffit_result = dict(R=None, mesg='', ier=None, info={}, nparam=0)
    mix2.fitParams = dict(
        lcf_params=lcfParams, lcf_xRange=[8900, 9100],
        ffit_formula='a*(np.arctan((x-b)/c)+np.pi/2) + d*gau(x, e, f)',
        ffit_params=dict(
            a=dict(value=0.3, step=0.01, tie='fixed', lim=[0., 2.]),
            b=dict(value=8980., step=0.1, lim=[8950., 9050.]),
            c=dict(value=5., step=0.1),
            d=dict(value=5, step=0.01, lim=[0, 20]),
            e=dict(value=8996., step=0.1, lim=[8950., 9050.]),
            f=dict(value=5., step=0.1, lim=[0., 30.])),
        ffit_xRange=[8900, 9100]
        )

    return mix1, mix2


if __name__ == '__main__':
    # data = make_fit(
    #     "data/cu-ref-mix.res", list(range(1, 13))+list(range(14, 18)))
    # data = make_fit(
    #     "data/zn-ref-mix.res", list(range(1, 10))+list(range(12, 14)))
    # data = make_fit(
    #     "data/pb-ref-mix.res", list(range(1, 9))+list(range(10, 13)))

    toFit = read_data(
        "data/cu-ref-mix.res", list(range(1, 13))+list(range(14, 18)))

    # csi.DEBUG_LEVEL = 100
    app = qt.QApplication(sys.argv)

    lcfTestWidget = LCFTestWidget(None, toFit)
    lcfTestWidget.setWindowTitle("Test LCF widget")
    lcfTestWidget.show()

    funcFitTestWidget = FunctionFitTestWidget(None, toFit)
    funcFitTestWidget.setWindowTitle("Test formula fit widget")
    funcFitTestWidget.show()

    app.exec_()

    print("Done")
