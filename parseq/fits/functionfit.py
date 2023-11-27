# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "30 May 2023"
# !!! SEE CODERULES.TXT !!!

from functools import partial
import numpy as np
from scipy.optimize import curve_fit

from .basefit import Fit


def gau(x, m, s):
    "gau(x, m, s): normalized Gaussian function, m=center, s=sigma"
    return 1 / (s*(2*np.pi)**0.5) * np.exp(-(x - m)**2 / (2 * s**2))


def lor(x, m, s):
    "lor(x, m, s): normalized Lorentzian function, m=center, s=HWHM"
    return s / np.pi / ((x - m)**2 + s**2)


class FunctionFit(Fit):
    name = 'function fit'

    defaultEntryDict = dict(a=dict(value=5., step=0.1))
    defaultResult = dict(R=1., mesg='', ier=None, info={}, nparam=0)
    defaultParams = dict(ffit_formula='', ffit_params=dict(),
                         ffit_xRange=None, ffit_result=defaultResult)
    dataAttrs = dict(x='x', y='y', fit='fit')
    ioAttrs = {'range': 'ffit_xRange', 'params': 'ffit_params',
               'result': 'ffit_result'}
    customFunctions = ('gau', 'lor')

    def getToolTip(self):
        res = ''
        for funcName in self.customFunctions:
            res += '\n' + globals()[funcName].__doc__
        return res

    @classmethod
    def make_model_curve(cls, data):
        dfparams = data.fitParams
        fitVars = dfparams['ffit_params']
        try:
            x = getattr(data, cls.dataAttrs['x'])
            y = getattr(data, cls.dataAttrs['y'])
        except AttributeError:
            return

        formula = dfparams['ffit_formula']
        if len(formula) == 0:
            return

        vals = [v['value'] for v in fitVars.values()]
        keys = list(fitVars.keys())
        res = cls.evaluate_formula(x, *vals, formula=formula, keys=keys)
        if isinstance(res, str):
            fit = np.zeros_like(x)
        else:
            fit = np.array(res)

        fitProps = dict(cls.defaultResult)
        fitProps['R'] = ((y - fit)**2).sum() / (y**2).sum()
        setattr(data, cls.dataAttrs['fit'], fit)
        dfparams['ffit_result'] = fitProps

    @classmethod
    def run_main(cls, data):
        dfparams = data.fitParams
        fitVars = dfparams['ffit_params']
        xRange = dfparams['ffit_xRange']
        formula = dfparams['ffit_formula']
        x = getattr(data, cls.dataAttrs['x'])
        y = getattr(data, cls.dataAttrs['y'])

        varied, args, mins, maxs = [], [], [], []
        tie = {}
        try:
            for k, v in fitVars.items():
                if 'tie' in v:
                    tieStr = v['tie']
                    if not cls.can_interpret_tie_str(tieStr, fitVars):
                        raise ValueError(f'wrong tie expression for {k}')
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

            where = (xRange[0] <= x) & (x <= xRange[1]) \
                if isinstance(xRange, (list, tuple)) else None
            locx = x[where]
            locy = y[where]
            fcounter = {'nfev': 0}
            popt, pcov, info, mesg, ier = curve_fit(
                partial(cls.evaluate_formula, formula=formula,
                        keys=varied, tie=tie, fcounter=fcounter),
                locx, locy, p0=args, bounds=(mins, maxs), full_output=True)
            # info2 = {'nfev': info['nfev']}
            info2 = fcounter
            fitProps = dict(mesg=mesg, ier=ier, info=info2, nparam=len(popt))
            tieRes = {}
            fit = cls.evaluate_formula(x, *popt, formula=formula,
                                       keys=varied, tie=tie, tieRes=tieRes)
            fitProps['R'] = ((locy - fit[where])**2).sum() / (locy**2).sum()

            perr = np.sqrt(np.diag(pcov))
            for k, opt, err in zip(varied, popt, perr):
                v = fitVars[k]
                v['value'] = opt
                v['error'] = err
            for k in tieRes:
                v = fitVars[k]
                v['value'] = tieRes[k]
                if 'error' in v:
                    del v['error']
        except (RuntimeError, ValueError) as e:
            # print('Error: ', e)
            fit = np.zeros_like(x)
            fitProps = dict(cls.defaultResult)
            fitProps['mesg'] = str(e)

        setattr(data, cls.dataAttrs['fit'], fit)
        dfparams['ffit_result'] = fitProps

    @classmethod
    def can_interpret_tie_str(cls, tieStr, fitVars):
        if tieStr.startswith('fix'):  # fixed
            return True
        if tieStr[0] not in '=<>':
            return False
        for k, v in fitVars.items():
            locals()[k] = v['value']
        try:
            eval(tieStr[1:])
            return True
        except Exception:
            return False

    @classmethod
    def evaluate_formula(cls, x, *params, formula, keys, tie={}, tieRes={},
                         fcounter={}):
        if fcounter:
            fcounter['nfev'] += 1
        res = 0.
        for key, param in zip(keys, params):
            locals()[key] = param
        for key, param in tie.items():
            if isinstance(param, str):
                val = eval(param[1:])
                if (param[0] == '=' or
                    (param[0] == '<' and locals()[key] > val) or
                        (param[0] == '>' and locals()[key] < val)):
                    locals()[key] = val
                    tieRes[key] = val
            else:
                locals()[key] = param
                tieRes[key] = param
        try:
            return eval(formula)
        except (NameError, TypeError) as err:
            return str(err)
