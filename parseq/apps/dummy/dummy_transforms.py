# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from scipy.interpolate import UnivariateSpline, interp1d
from ...core import singletons as csi
from ...core import transforms as ctr

EV_REVA = 0.2624682843  # 2m_e(eV) / (hbar(eVs)c(A/s))^2
N_FFT = 4096


# This is not a proper EXAFS analysis routine! This is a dummy for ParSeq.
class Tr0(ctr.Transform):
    name = 'calibrate E'
    params = dict(correctionNeeded=False, Eref=8979., correctionKind='')

    def run_main(self, data):
        data.e = data.eraw + 0.1
        data.i0 = data.i0raw
        data.i1 = data.i1raw
        data.isGood[self.toNode.name] = True


class Tr1(ctr.Transform):
    name = 'make k'
    params = dict(E0=8979., kmin=2., kmax='auto', dk=0.025, smoothing=7.,
                  kw=1)

    def run_main(self, data):
        dparams = data.transformParams[self.name]
        e0 = dparams['E0']
        kMin = dparams['kmin']
        kMax = dparams['kmax']
        dk = dparams['dk']
        if kMax == 'auto':
            kMax = ((data.e[-1]-e0) * EV_REVA)**0.5
        ik = np.arange(kMin/dk, kMax/dk, dtype=int)
        data.ikmin = ik[0]
        data.ikmax = ik[-1]
        data.k = ik * dk
        data.chi = np.zeros_like(data.k)

        try:
            data.mu = np.log(data.i0 / data.i1)
            data.mu -= data.mu.min()
            e = data.e[data.e >= e0]
            mu = data.mu[data.e >= e0]

            smspl = UnivariateSpline(e, mu, s=dparams['smoothing'])
            data.mu0 = smspl(e)
            chiE = (mu - data.mu0) / data.mu0

            kE = ((e-e0) * EV_REVA)**0.5
            chiF = interp1d(kE, chiE, 'cubic', copy=False, fill_value=0.,
                            assume_sorted=True)
            data.chi = np.zeros_like(data.k)
            krange = (data.k >= kMin) & (data.k <= kE[-1])
            data.chi[krange] = chiF(data.k[krange])
            if dparams['kw'] > 0:
                data.chi[krange] *= data.k[krange] ** dparams['kw']
            data.isGood[self.toNode.name] = True
        except (TypeError, IndexError, ValueError):
            data.isGood[self.toNode.name] = False

    def get_kmax(self):
        kMax = []
        for data in csi.selectedItems:
            dparams = data.transformParams[self.name]
            kMax.append(((data.e[-1]-dparams['E0']) * EV_REVA)**0.5)
        return min(kMax)


class Tr2(ctr.Transform):
    name = 'make r'
    params = dict(rmax=4.)

    def run_main(self, data):
        try:
            dparams = data.transformParams[self.name]
            dk = data.k[1] - data.k[0]
            data.r = np.fft.rfftfreq(N_FFT, dk)
            chi = np.zeros(N_FFT)
            chi[data.ikmin: data.ikmax+1] = data.chi
            data.ft = np.abs(np.fft.rfft(chi)) * dk
            rmax = dparams['rmax']
            data.ft = data.ft[data.r <= rmax]
            data.r = data.r[data.r <= rmax]
            data.isGood[self.toNode.name] = True
        except (TypeError, IndexError, ValueError):
            data.isGood[self.toNode.name] = False
