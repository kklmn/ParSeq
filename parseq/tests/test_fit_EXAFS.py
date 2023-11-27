# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "29 Sep 2023"
# !!! SEE CODERULES.TXT !!!

import os.path as osp
import numpy as np

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.fits.exafsfit import EXAFSFit
from parseq.gui.fits.gexafsfit import EXAFSFitWidget
from parseq.gui.plot import Plot1D

from silx.gui import qt

nfft = 8192
rmax = 6.2


class MyEXAFSFit(EXAFSFit):
    name = 'EXAFSFit'
    dataAttrs = dict(EXAFSFit.dataAttrs)
    dataAttrs.update(x='k', y='bft', fit='fit')


class TestEXAFSFitWidget(qt.QWidget):
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

        self.plotk = Plot1D(self)
        self.plotk.getXAxis().setLabel(u'k (Å\u207B\u00B9)')
        self.plotk.getYAxis().setLabel(u'χ')

        self.plotr = Plot1D(self)
        self.plotr.getXAxis().setLabel(u'r (Å)')
        self.plotr.getYAxis().setLabel(u'FT[χ]')

        self.EXAFSFitWorker = MyEXAFSFit()

        self.EXAFSFitWidget = EXAFSFitWidget(
            self, worker=self.EXAFSFitWorker, plot=(self.plotk, self.plotr))
        self.EXAFSFitWidget.fitReady.connect(self.replot)
        layout.addWidget(self.EXAFSFitWidget)

        layoutP = qt.QHBoxLayout()
        layoutP.addWidget(self.plotk)
        layoutP.addWidget(self.plotr)
        layout.addLayout(layoutP)

        # layout.addStretch()
        self.setLayout(layout)

        self.spectra.setCurrentRow(0)

    def replot(self):
        cs = self.currentSpectrum
        if cs is None:
            return
        if not hasattr(cs, 'fit'):
            cs.fit = np.zeros_like(cs.k)
        self.plotk.addCurve(cs.k, cs.bft, legend='data')
        self.plotk.addCurve(cs.k, cs.fit, legend='fit', color='m')
        if cs.fit.any():  # any non-zero
            self.plotk.addCurve(cs.k, cs.bft-cs.fit, legend='res', color='g')
        else:
            self.plotk.remove('res', kind='curve')

        self.plotr.addCurve(cs.r, cs.ft, legend='data FT')
        ft = np.fft.rfft(cs.fit, n=nfft) * cs.dk/2
        cs.fitft = np.abs(ft)[:len(cs.r)]
        self.plotr.addCurve(cs.r, cs.fitft, legend='fit FT', color='m')

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
        if len(csi.selectedItems) == 0:
            return
        self.currentSpectrum = csi.selectedItems[0]
        self.EXAFSFitWidget.setSpectrum(self.currentSpectrum)
        self.replot()


class DataProxy(object):
    """An empty object to attach fields to it. With a simple instance of
    object() this is impossible but doable with an empty class."""
    pass


def read_data_Cu():
    fpath = "data/BFT-Cu-foil_EXAFS_23070.txt.gz"
    fname = osp.split(fpath)[1].split('.')[0]
    data = np.loadtxt(fpath, skiprows=1)
    spectrum = DataProxy()
    spectrum.alias = fname
    spectrum.k = data[:, 0]
    spectrum.bft = data[:, 1]

    spectrum.dk = spectrum.k[1] - spectrum.k[0]
    ft = np.fft.rfft(spectrum.bft, n=nfft) * spectrum.dk/2
    spectrum.r = np.fft.rfftfreq(nfft, spectrum.dk/np.pi)
    wherer = spectrum.r < rmax
    spectrum.ft = np.abs(ft)[wherer]
    spectrum.r = spectrum.r[wherer]

    spectrum.transfortmTimes = {}
    allData = [spectrum]
    csi.allLoadedItems = allData

    spectrum.transformParams = dict(kw=2)

    spectrum.fitParams = dict(
        exafsfit_params=[
            dict(r=dict(value=2.55, step=0.01, lim=[1.5, 3.5]),
                 n=dict(value=12.0, step=0.1, lim=[8., 16.]),
                 s=dict(value=0.006, step=0.001, lim=[0., 0.1]),
                 e=dict(value=0., step=0.1, lim=[-15., 15.])),
            dict(r=dict(value=3.61, step=0.01, lim=[1.5, 5.5]),
                 n=dict(value=6, step=0.1, lim=[4., 8.]),
                 s=dict(value=0.006, step=0.001, lim=[0., 0.1]),
                 e=dict(value=0., step=0.1, tie='=e1', lim=[-15., 15.])),
            dict(s0=dict(value=1.0, step=0.01, tie='fixed'))
            ],
        exafsfit_kRange=[1., 16.], exafsfit_k_use=True,
        exafsfit_rRange=[1., 2.5], exafsfit_r_use=False,
        exafsfit_aux=[
            # [path, N, stratoms, R, ver, nHeader, use]
            [r'data/feff/Cu/feff0001.dat',
             12, 'Cu-Cu', 2.5527, '8.20', 14, 1],
            [r'data/feff/Cu/feff0002.dat',
             6, 'Cu-Cu', 3.6100, '8.20', 14, 1]
            ]
        )
    return [spectrum]


def read_data_Cu_no_fit():
    fpath = "data/BFT-Cu-foil_EXAFS_23070.txt.gz"
    fname = osp.split(fpath)[1].split('.')[0]
    data = np.loadtxt(fpath, skiprows=1)
    spectrum = DataProxy()
    spectrum.alias = fname
    spectrum.k = data[:, 0]
    spectrum.bft = data[:, 1]

    spectrum.dk = spectrum.k[1] - spectrum.k[0]
    ft = np.fft.rfft(spectrum.bft, n=nfft) * spectrum.dk/2
    spectrum.r = np.fft.rfftfreq(nfft, spectrum.dk/np.pi)
    wherer = spectrum.r < rmax
    spectrum.ft = np.abs(ft)[wherer]
    spectrum.r = spectrum.r[wherer]

    spectrum.transfortmTimes = {}
    allData = [spectrum]
    csi.allLoadedItems = allData

    spectrum.transformParams = dict(kw=2)
    spectrum.fitParams = dict()

    return [spectrum]


def read_data_CeRu2():
    allData = []
    fpaths = "data/Ce-CeRu2.bft", "data/Ru-CeRu2.bft"
    for fpath in fpaths:
        fname = osp.split(fpath)[1].split('.')[0]
        data = np.loadtxt(fpath, skiprows=1)
        spectrum = DataProxy()
        allData.append(spectrum)
        spectrum.alias = fname
        spectrum.k = data[:, 0]
        spectrum.bft = data[:, 1]

        spectrum.dk = spectrum.k[1] - spectrum.k[0]
        ft = np.fft.rfft(spectrum.bft, n=nfft) * spectrum.dk/2
        spectrum.r = np.fft.rfftfreq(nfft, spectrum.dk/np.pi)
        wherer = spectrum.r < rmax
        spectrum.ft = np.abs(ft)[wherer]
        spectrum.r = spectrum.r[wherer]

        spectrum.transfortmTimes = {}
        spectrum.transformParams = dict(kw=2)

    allData[0].fitParams = dict(
        exafsfit_params=[
            dict(r=dict(value=3.1259, step=0.01, lim=[1.5, 3.5]),
                 n=dict(value=12.0, step=0.1, lim=[6., 24.], tie='fixed'),
                 s=dict(value=0.006, step=0.001, lim=[0., 0.1]),
                 e=dict(value=0., step=0.1, lim=[-15., 15.])),
            dict(r=dict(value=3.2649, step=0.01, lim=[1.5, 5.5]),
                 n=dict(value=4.0, step=0.1, lim=[2., 8.], tie='fixed'),
                 s=dict(value=0.006, step=0.001, lim=[0., 0.1]),
                 e=dict(value=0., step=0.1, lim=[-15., 15.])),
            dict(s0=dict(value=1.0, step=0.01, tie='fixed'))
            ],
        exafsfit_kRange=None, exafsfit_k_use=True,
        exafsfit_rRange=None, exafsfit_r_use=False,
        exafsfit_aux=[
            # [path, N, stratoms, R, ver, nHeader, use]
            [r'data/feff/CeRu2/feff0001.dat',
             12, 'Ce-Ru', 3.1259, '8.20', 13, 1],
            [r'data/feff/CeRu2/feff0002.dat',
             4, 'Ce-Ce', 3.2649, '8.20', 13, 1]
            ]
        )
    allData[1].fitParams = dict(
        exafsfit_params=[
            dict(r=dict(value=2.6658, step=0.01, lim=[1.5, 3.5]),
                 n=dict(value=6.0, step=0.1, lim=[3., 12.], tie='fixed'),
                 s=dict(value=0.006, step=0.001, lim=[0., 0.1]),
                 e=dict(value=0., step=0.1, lim=[-15., 15.])),
            dict(r=dict(value=3.1259, step=0.01, lim=[1.5, 5.5],
                        tie="=fit['Ce-CeRu2'].r1"),
                 n=dict(value=4.0, step=0.1, lim=[2., 8.], tie='fixed'),
                 s=dict(value=0.006, step=0.001, lim=[0., 0.1]),
                 e=dict(value=0., step=0.1, lim=[-15., 15.])),
            dict(s0=dict(value=1.0, step=0.01, tie='fixed'))
            ],
        exafsfit_kRange=None, exafsfit_k_use=True,
        exafsfit_rRange=None, exafsfit_r_use=False,
        exafsfit_aux=[
            # [path, N, stratoms, R, ver, nHeader, use]
            [r'data/feff/Ru_CeRu2/feff0001.dat',
             6, 'Ru-Ru', 2.6658, '8.20', 13, 1],
            [r'data/feff/Ru_CeRu2/feff0002.dat',
             6, 'Ru-Ce', 3.1259, '8.20', 13, 1]
            ]
        )

    csi.allLoadedItems = allData
    return allData


if __name__ == '__main__':
    # toFit = read_data_Cu()
    # toFit = read_data_Cu_no_fit()
    toFit = read_data_CeRu2()

    # csi.DEBUG_LEVEL = 100
    app = qt.QApplication(sys.argv)

    exafsFitTestWidget = TestEXAFSFitWidget(None, toFit)
    exafsFitTestWidget.setWindowTitle("Test LCF widget")
    exafsFitTestWidget.show()

    app.exec_()

    print("Done")
