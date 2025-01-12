# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "12 Jan 2025"
# !!! SEE CODERULES.TXT !!!

import numpy as np
if not hasattr(np, 'trapezoid'):
    np.trapezoid = np.trapz
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d
from scipy.linalg import eigh
from functools import partial
import re

from ..core.logger import syslogger
from ..utils import ft as uft
from ..utils.constants import eV2revA
from .basefit import Fit, DataProxy


class EXAFSFit(Fit):
    name = 'EXAFS fit'
    # nProcesses = 2

    defaultShellParams = [
        dict(r=dict(value=2.2, step=0.01),
             n=dict(value=6, step=0.1),
             s=dict(value=0.006, step=0.001, lim=[0., 0.1]),
             e=dict(value=0, step=0.1, lim=[-15., 15.])),
        dict(s0=dict(value=1.0, step=0.01, tie='fixed', lim=[0.5, 1.]),)]
    defaultMetaParams = dict(value=2.0, step=0.01, lim=[0.1, 10.])
    auxItems = {}  # here amps and phases will be stored as {path: (k, a, ph)}

    defaultResult = dict(R=1., mesg='', ier=None, info={}, nparam=0, Nind=0)
    defaultParams = dict(exafsfit_params=[], exafsfit_result=defaultResult,
                         exafsfit_aux=[],
                         exafsfit_kRange=None, exafsfit_k_use=False,
                         exafsfit_rRange=None, exafsfit_r_use=False)
    dataAttrs = dict(x='bftk', y='bft', fit='bftfit',
                     x2='r', y2='ft', fit2='ftfit')
    ioAttrs = {'range': 'exafsfit_kRange', 'range2': 'exafsfit_rRange',
               'use_range': 'exafsfit_k_use', 'use_range2': 'exafsfit_r_use',
               'params': 'exafsfit_params', 'result': 'exafsfit_result',
               'aux': 'exafsfit_aux'}

    nfft = 8192
    allowMetaParams = True

    @classmethod
    def make_aux(cls, data):
        dfparams = data.fitParams
        auxs = dfparams['exafsfit_aux']
        for aux in auxs:
            if not aux:
                continue
            if aux[0] not in cls.auxItems:
                try:
                    reff = aux[3]
                    # feffVersion = aux[4]
                    # if feffVersion == '8.20':
                    if True:
                        arrs = np.loadtxt(aux[0], skiprows=aux[5]).T
                        k = arrs[0]
                        amp = arrs[2] * arrs[4] * np.exp(-2*reff/arrs[5])
                        ph = arrs[1] + arrs[3]
                    ampFunc = interp1d(k, amp, 'cubic', copy=False,
                                       fill_value='extrapolate',
                                       assume_sorted=True)
                    phFunc = interp1d(k, ph, 'cubic', copy=False,
                                      fill_value='extrapolate',
                                      assume_sorted=True)
                    cls.auxItems[aux[0]] = [ampFunc, phFunc]
                except Exception:
                    res = 'cannot parse feff file: {0}'.format(aux[0])
                    syslogger.error(res)
                    # cls.auxItems[aux[0]] = None
                    return res

    @classmethod
    def merge_shells(cls, fitVars):
        keys, vals = [], []
        fitDict = {}
        for ishell, shell in enumerate(fitVars[:-1]):
            for p in 'rnse':
                key = '{0}{1}'.format(p, ishell+1)
                keys.append(key)
                vals.append(shell[p]['value'])
                fitDict[key] = shell[p]

        if cls.allowMetaParams:
            for p, val in fitVars[-1].items():
                keys.append(p)
                vals.append(val['value'])
                fitDict[p] = val
        else:
            keys.append('s0')
            vals.append(fitVars[-1]['s0']['value'])
            fitDict['s0'] = fitVars[-1]['s0']

        return keys, vals, fitDict

    @classmethod
    def make_model_curve(cls, data):
        try:
            x = getattr(data, cls.dataAttrs['x'])
            y = getattr(data, cls.dataAttrs['y'])
        except AttributeError:
            return
        dfparams = data.fitParams

        resAux = cls.make_aux(data)
        if isinstance(resAux, str):
            fit = np.zeros_like(x)
            setattr(data, cls.dataAttrs['fit'], fit)
            fitProps = dict(cls.defaultResult)
            fitProps['R'] = 1.
            dfparams['exafsfit_result'] = fitProps
            if hasattr(data, cls.dataAttrs['fit2']):
                setattr(data, cls.dataAttrs['fit2'], np.zeros_like(
                    getattr(data, cls.dataAttrs['fit2'])))
            return resAux

        fitVars = dfparams['exafsfit_params']
        auxs = dfparams['exafsfit_aux']

        dtparams = data.transformParams
        kw = dtparams['kw']
        keys, vals, _ = cls.merge_shells(fitVars)
        indexVaried = {k: ind for (ind, k) in enumerate(keys)}
        fitStruct0 = dict(data=data, varied=keys, auxs=auxs, tie={},
                          indexVaried=indexVaried, tieRes={}, kw=kw)
        res = cls.exafs(x, *vals, fitStruct=[fitStruct0])
        if isinstance(res, str):
            fit = np.zeros_like(x)
        else:
            fit = np.array(res)

        fitProps = dict(cls.defaultResult)
        fitProps['R'] = ((y - fit)**2).sum() / (y**2).sum()
        setattr(data, cls.dataAttrs['fit'], fit)
        dfparams['exafsfit_result'] = fitProps
        cls.make_model_FT(data, fit)

    @classmethod
    def make_model_FT(cls, data, fit):
        dtparams = data.transformParams

        x = getattr(data, cls.dataAttrs['x'])
        dk = x[1] - x[0]
        if 'ftWindowKind' in dtparams:  # not in test mock transforms
            kind = dtparams['ftWindowKind']
            w, vmin = dtparams['ftWindowProp']
            kmin, kmax = dtparams['krange']
            # kmaxE = dtparams['datakmax']
            # kmax = min(kmax, kmaxE) if kmax else kmaxE
            data.ftfitwindow = uft.make_ft_window(kind, x, kmin, kmax, w, vmin)
        else:
            data.ftfitwindow = 1.

        fitw = fit * data.ftfitwindow
        if 'forceFT0' in dtparams:
            if dtparams['forceFT0']:
                fitw -= np.trapezoid(fitw, x=x) / np.trapezoid(
                    np.ones_like(fitw), x=x)
        fitft = np.fft.rfft(fitw, n=cls.nfft) * dk/2
        r = np.fft.rfftfreq(cls.nfft, dk/np.pi)
        wherer = r <= dtparams['rmax'] if 'rmax' in dtparams else None
        setattr(data, cls.dataAttrs['fit2'], np.abs(fitft)[wherer])

    @classmethod
    def prepare_fit(cls, data, allData):
        dfparams = data.fitParams
        fitVars = dfparams['exafsfit_params']
        auxs = dfparams['exafsfit_aux']

        kRange = dfparams['exafsfit_kRange']
        kRangeUse = dfparams['exafsfit_k_use']
        rRange = dfparams['exafsfit_rRange']
        rRangeUse = dfparams['exafsfit_r_use']

        x = getattr(data, cls.dataAttrs['x'])
        y = getattr(data, cls.dataAttrs['y'])
        dtparams = data.transformParams
        kw = dtparams['kw']

        resAux = cls.make_aux(data)
        if isinstance(resAux, str):
            return resAux

        varied, args, mins, maxs = [], [], [], []
        tie = {}
        otherFits = []
        keys, vals, fitDict = cls.merge_shells(fitVars)
        try:
            for k, v in zip(keys, fitDict.values()):
                if 'tie' in v:
                    tieStr = v['tie']
                    others = []
                    if not cls.can_interpret_tie_str(tieStr, fitVars, allData,
                                                     others=others):
                        raise ValueError(
                            f'wrong tie expression for {k}:\n'
                            f'  tieStr = {tieStr}\n  fitVars = {fitVars}')
                    if others:
                        otherFits.extend(others)
                    tie[k] = v['value'] if tieStr.startswith('fix') else tieStr
                    # if tieStr[0] in '<>' then k is in both tie and varied
                    if tieStr[0] not in '<>':
                        continue
                vMin, vMax = v['lim'] if 'lim' in v else (-np.inf, np.inf)
                if vMin < vMax:
                    varied.append(k)
                    args.append(v['value'])
                    mins.append(vMin)
                    maxs.append(vMax)
                else:
                    tie[k] = vMin
                    v['value'] = vMin

            if kRangeUse:
                try:
                    wherek = (kRange[0] <= x) & (x <= kRange[1])
                except Exception:
                    if 'kmin' in dtparams and 'kmax' in dtparams:
                        kRange = [dtparams['kmin'], dtparams['kmax']]
                    else:
                        kRange = [0, x.max()]
                    wherek = (kRange[0] <= x) & (x <= kRange[1])
                xw, yw = x[wherek], y[wherek]
                Deltak = kRange[1] - kRange[0] \
                    if isinstance(kRange, (list, tuple)) else x.max() - x.min()
            else:
                wherek = None
                xw, yw = x, y
                Deltak = x.max() - x.min()
            sigmax = xw**kw

            if rRangeUse:
                dk = x[1] - x[0]
                ft = np.fft.rfft(y, n=cls.nfft) * dk/2
                r = np.fft.rfftfreq(cls.nfft, dk/np.pi)
                try:
                    wherer = (rRange[0] <= r) & (r <= rRange[1])
                except Exception:
                    if 'rmax' in dtparams:
                        rRange = [0, dtparams['rmax']]
                    else:
                        rRange = [0, r.max()]
                    wherer = (rRange[0] <= r) & (r <= rRange[1])
                Deltar = rRange[1] - rRange[0]
                rw, ftwr, ftwi = r[wherer], ft.real[wherer], ft.imag[wherer]
                # ftwm = np.abs(ft)[wherer]

                ftDict = dict(k=x, dk=dk, kRange=kRange, rRange=rRange)
                xkw = xw.max()**(2*kw+1) - xw.min()**(2*kw+1)
                sigmar = (dk*xkw / (np.pi * (2*kw+1)))**0.5 * np.ones_like(rw)
                if kRangeUse:
                    xw = np.concatenate((xw, rw, rw))
                    yw = np.concatenate((yw, ftwr, ftwi))
                    sigmax = np.concatenate((sigmax, sigmar, sigmar))
                else:
                    xw = np.concatenate((rw, rw))
                    yw = np.concatenate((ftwr, ftwi))
                    sigmax = np.concatenate((sigmar, sigmar))
            else:
                wherer = None
                ftDict = None
                if 'ftWindowKind' in dtparams:  # not in test mock transforms
                    if dtparams['bftWindowKind'] == 'none':
                        Deltar = dtparams['rmax']
                    else:
                        rmin, rmax = dtparams['bftWindowRange']
                        Deltar = rmax - rmin
                else:
                    Deltar = 8.
            Nind = 2*Deltak*Deltar/np.pi + 2
        except (RuntimeError, ValueError) as e:
            return str(e)
        return dict(
            x=x, y=y, xw=xw, yw=yw, keys=keys, vals=vals, varied=varied,
            args=args, auxs=auxs, kw=kw, mins=mins, maxs=maxs, tie=tie,
            fitDict=fitDict, ftDict=ftDict, otherFits=otherFits,
            kRange=kRange, kRangeUse=kRangeUse, wherek=wherek,
            rRange=rRange, rRangeUse=rRangeUse, wherer=wherer,
            data=data, tieRes={}, sigma=sigmax, Nind=Nind)

    @classmethod
    def run_main(cls, data, allData):
        fitStruct = []
        fitStruct0 = cls.prepare_fit(data, allData)
        if isinstance(fitStruct0, str):
            raise ValueError(fitStruct0)
        prepared_fits = [data.alias]
        toLoad = list(fitStruct0['otherFits'])
        fitStruct = [fitStruct0]
        while len(toLoad) > 0:
            lenBefore = len(toLoad)
            for sp in allData:
                if sp.alias in toLoad:
                    if sp.alias not in prepared_fits:
                        fitStruct1 = cls.prepare_fit(sp, allData)
                        if isinstance(fitStruct1, str):
                            raise ValueError(fitStruct1)
                        fitStruct.append(fitStruct1)
                        prepared_fits.append(sp.alias)
                    toLoad.remove(sp.alias)
                    break
            lenAfter = len(toLoad)
            if lenAfter == lenBefore:
                raise ValueError('invalid data reference')

        xw = np.concatenate([fs['xw'] for fs in fitStruct])
        yw = np.concatenate([fs['yw'] for fs in fitStruct])
        args = [arg for fs in fitStruct for arg in fs['args']]
        bounds = ([m for fs in fitStruct for m in fs['mins']],
                  [m for fs in fitStruct for m in fs['maxs']])
        sigma = None
        # sigma = np.concatenate([fs['sigma'] for fs in fitStruct])
        Nind = sum([fs['Nind'] for fs in fitStruct])
        ind = 0
        premesg = '{0}calculated for '.format(
            'jointly ' if len(fitStruct) > 1 else '')
        for ifs, fs in enumerate(fitStruct):
            fs['indexVaried'] = {}
            sp = fs['data']
            premesg += '{0}{1}'.format(', ' if ifs > 0 else '', sp.alias)
            for key in fs['varied']:
                fs['indexVaried'][key] = ind
                ind += 1

        fcounter = {'nfev': 0}
        popt, pcov, info, mesg, ier = curve_fit(
            partial(cls.exafs, fitStruct=fitStruct, fcounter=fcounter),
            xw, yw, p0=args, sigma=sigma, bounds=bounds, full_output=True)
        # info2 = {'nfev': info['nfev']}
        info2 = fcounter
        P = len(popt)
        fitProps = dict(mesg=premesg+'\n'+mesg, ier=ier, info=info2,
                        nparam=P, Nind=Nind)
        err = np.sqrt(np.diag(pcov))

        # exafs with optimal parameters and within k and r fit ranges
        fits = cls.exafs(xw, *popt, fitStruct=fitStruct)
        chi2opt = cls.get_chi2(xw, popt, fitStruct, getR=True)
        nu = Nind - P
        if nu > 0:
            H = cls.get_Hessian_chi2(xw, chi2opt, fitStruct, err, popt, bounds)
            H *= nu / chi2opt
            diagH = np.array(np.diag(H))
            diagH[diagH < 0] = 1e-28
            Hii = diagH**0.5
            fitProps['corr'] = H / np.dot(Hii.reshape(P, 1), Hii.reshape(1, P))

            errA = np.sqrt(2) / Hii

            wH, vH = eigh(H/2)
            errB2 = (vH[:, wH > 0]**2 / wH[wH > 0]).sum(axis=1)
            errB = np.where(errB2 >= 0, np.abs(errB2)**0.5, np.full(P, 1e20))
        else:
            fitProps['corr'] = np.identity(P)
            errA, errB = np.full(P, 1e20), np.full(P, 1e20)

        # exafs with optimal parameters in full k range
        for fs in fitStruct:
            fs['kRangeUse'] = False
            fs['rRangeUse'] = False
            fs['tieRes'] = {}
        fits = cls.exafs(xw, *popt, fitStruct=fitStruct)

        istart = 0
        for fs in fitStruct:
            iend = istart + len(fs['x'])
            fit = fits[istart: iend]
            istart = iend

            ind = fs['indexVaried']
            fitDict = fs['fitDict']
            for k in fs['varied']:
                v = fitDict[k]
                v['value'] = popt[ind[k]]
                v['errorA'] = errA[ind[k]]
                v['errorB'] = errB[ind[k]]
                # v['errorC'] = errC[ind[k]]
            for k in fs['tieRes']:
                v = fitDict[k]
                v['value'] = fs['tieRes'][k]
                for errorStr in ['error'+ch for ch in ('A', 'B')]:
                    if errorStr in v:
                        del v[errorStr]

            sp = fs['data']
            setattr(sp, cls.dataAttrs['fit'], fit)
            dfparams = sp.fitParams
            fitProps['R'] = fs['R']
            dfparams['exafsfit_result'] = fitProps
            cls.make_model_FT(sp, fit)

    @classmethod
    def get_other_fits(cls, tieStr, allData):
        fit = dict()
        otherFits = [k.replace('"', '').replace("'", '') for k in
                     re.findall(r'\[(.*?)\]', tieStr)]
        for otherFit in otherFits:
            if otherFit in fit:
                continue
            for sp in allData:
                if sp.alias == otherFit:
                    break
            else:
                return
            dfparams = sp.fitParams
            fitVarsOther = dfparams['exafsfit_params']
            keys, vals, _ = cls.merge_shells(fitVarsOther)
            dp = DataProxy()
            for key, val in zip(keys, vals):
                setattr(dp, key, val)
            fit[otherFit] = dp

        try:
            eval(tieStr[1:])
            return fit
        except Exception as e:
            syslogger.error('tie expression cannot be parsed:\n'+str(e))

    @classmethod
    def get_chi2(cls, xw, p, fitStruct, getR=False):
        fits = cls.exafs(xw, *p, fitStruct=fitStruct)
        istart = 0
        chi2 = 0
        for fs in fitStruct:
            y, sigma = fs['yw'], fs['sigma']
            iend = istart + len(y)
            fit = fits[istart: iend]
            istart = iend
            if getR:
                fs['R'] = ((y - fit)**2).sum() / (y**2).sum()
            chi2 += (((y - fit)/sigma)**2).sum()
        return chi2

    @classmethod
    def get_Hessian_chi2(cls, xw, chi2opt, fitStruct, err, popt, bounds):
        n = len(popt)
        chi2minus, chi2plus = np.zeros(n), np.zeros(n)
        for i, (h, hmin, hmax) in enumerate(zip(err, *bounds)):
            dopt = list(popt)
            dopt[i] = popt[i] - h
            if not (hmin < dopt[i] < hmax):
                chi2minus[i] = np.inf
                continue
            chi2minus[i] = cls.get_chi2(xw, dopt, fitStruct)
            dopt[i] = popt[i] + h
            if not (hmin < dopt[i] < hmax):
                chi2plus[i] = np.inf
                continue
            chi2plus[i] = cls.get_chi2(xw, dopt, fitStruct)
        hessian = np.zeros((n, n))
        for i, h in enumerate(err):
            if (chi2minus[i] == np.inf) or (chi2plus[i] == np.inf) or (h <= 0):
                hessian[i, i] = 1e-24
                for j in range(n):
                    hessian[i, j] = 1e-24
                    hessian[j, i] = 1e-24
                continue
            else:
                hessian[i, i] = (chi2plus[i] - 2*chi2opt + chi2minus[i]) / h**2
            for j, k in enumerate(err[:i]):
                if (chi2minus[j] == np.inf) or (chi2plus[j] == np.inf) or \
                        (h*k <= 0):
                    hessian[i, j] = 1e-24
                    hessian[j, i] = 1e-24
                    continue
                dopt = list(popt)
                dopt[i] = popt[i] - h
                dopt[j] = popt[j] - k
                chi2minusminus = cls.get_chi2(xw, dopt, fitStruct)
                dopt[i] = popt[i] + h
                dopt[j] = popt[j] + k
                chi2plusplus = cls.get_chi2(xw, dopt, fitStruct)
                hessian[i, j] = (
                    chi2plusplus - chi2plus[i] - chi2plus[j] + 2*chi2opt
                    - chi2minus[i] - chi2minus[j] + chi2minusminus) / (2*h*k)
                hessian[j, i] = hessian[i, j]
        return hessian

    @classmethod
    def can_interpret_tie_str(cls, tieStr, fitVars, allData, others=[]):
        if tieStr.startswith('fix'):  # fixed
            return True
        if tieStr[0] not in '=<>':
            return False
        keys, vals, _ = cls.merge_shells(fitVars)
        _locals = dict(zip(keys, vals))

        if 'fit[' in tieStr:
            fit = cls.get_other_fits(tieStr, allData)
            if fit is None:
                return False
            _locals['fit'] = fit
            others.extend(list(fit.keys()))

        try:
            # keyword `locals` is an error in Py<3.13,
            # using just `_locals` (without globals()) does not work
            eval(tieStr[1:], {}, _locals)
            return True
        except Exception:
            return False

    @classmethod
    def exafs(cls, x, *vals, fitStruct=[], fcounter={}):
        if fcounter:
            fcounter['nfev'] += 1
        fit = {}
        fitKeys = []
        _locals = dict(fit=fit)
        for ifs, fs in enumerate(fitStruct):
            dp = DataProxy()
            # this loop is needed for tying to fixed params:
            if ('keys' in fs) and ('vals' in fs):
                for key, val in zip(fs['keys'], fs['vals']):
                    setattr(dp, key, val)
                    if ifs == 0:
                        _locals[key] = val  # needed to evaluate tie str
            ind = fs['indexVaried']
            for key in fs['varied']:
                val = vals[ind[key]]
                setattr(dp, key, val)
                if ifs == 0:
                    _locals[key] = val  # needed to evaluate tie str
                    fitKeys.append(key)
                else:
                    fitKeys.append('.'.join((fs['data'].alias, key)))
            fit[fs['data'].alias] = dp
        if fcounter:
            fcounter['fitKeys'] = fitKeys

        for ifs, fs in enumerate(fitStruct):
            dp = fit[fs['data'].alias]
            for key, param in fs['tie'].items():
                if isinstance(param, str):
                    # keyword `locals` is an error in Py<3.13,
                    # using just `_locals` (without globals()) does not work
                    tval = eval(param[1:], {}, _locals)
                    if (param[0] == '=' or
                        (param[0] == '<' and _locals[key] > tval) or
                            (param[0] == '>' and _locals[key] < tval)):
                        setattr(dp, key, tval)
                        # if ifs == 0:
                        #     _locals[key] = tval
                        fs['tieRes'][key] = tval
                else:
                    setattr(dp, key, param)
                    # if ifs == 0:
                    #     _locals[key] = param
                    fs['tieRes'][key] = param

        resultArrays = []
        for fs in fitStruct:
            if 'rRangeUse' in fs and fs['rRangeUse']:
                k = fs['ftDict']['k']
            elif 'kRangeUse' in fs and fs['kRangeUse'] and 'xw' in fs:
                k = fs['xw']
            elif 'x' in fs:
                k = fs['x']
            else:
                k = x
            # _locals['k'] = k

            kw = fs['kw']
            dp = fit[fs['data'].alias]
            try:
                res = np.zeros_like(k)
                for ishell, aux in enumerate(fs['auxs']):
                    if not aux or (aux[6] == 0):
                        continue
                    ish = str(ishell+1)
                    # r, n = _locals['r'+ish], _locals['n'+ish]
                    # s, e = _locals['s'+ish], _locals['e'+ish]
                    r, n, s, e = [getattr(dp, a+ish) for a in 'rnse']
                    k2 = k**2 + e*eV2revA
                    shiftk = np.sign(k2)*np.abs(k2)**0.5 - k
                    kshifted = k - shiftk
                    ampFunc, phFunc = cls.auxItems[aux[0]]
                    sinarg = 2*r*kshifted + phFunc(kshifted)
                    dw = np.exp(-2*s*k2)
                    res += np.sin(sinarg)*n*(r**-2)*ampFunc(kshifted)*dw
                # s02 = _locals['s0']
                s02 = getattr(dp, 's0')
                res *= s02 * k**(kw - 1)

                if 'rRangeUse' in fs and fs['rRangeUse']:
                    ftDict = fs['ftDict']
                    dk = ftDict['dk']
                    ftfit = np.fft.rfft(res, n=cls.nfft) * dk/2
                    r = np.fft.rfftfreq(cls.nfft, dk/np.pi)
                    rRange = ftDict['rRange']
                    wherer = (rRange[0] <= r) & (r <= rRange[1])
                    ftwr, ftwi = ftfit.real[wherer], ftfit.imag[wherer]
                    # ftwm = np.abs(ftfit)[wherer]
                    if 'kRangeUse' in fs and fs['kRangeUse']:
                        kRange = ftDict['kRange']
                        wherek = (kRange[0] <= k) & (k <= kRange[1]) \
                            if isinstance(kRange, (list, tuple)) else None
                        yw = res[wherek]
                        resft = np.concatenate((yw, ftwr, ftwi))
                    else:
                        resft = np.concatenate((ftwr, ftwi))
                    resultArrays.append(resft)
                else:
                    resultArrays.append(res)
            except (NameError, TypeError) as e:
                return str(e)
        return np.concatenate(resultArrays)
