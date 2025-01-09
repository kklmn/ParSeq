# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 May 2023"
# !!! SEE CODERULES.TXT !!!

# import os.path as osp
from functools import partial
import numpy as np
from scipy.optimize import curve_fit
from scipy import interpolate

from .basefit import Fit


class LCF(Fit):
    name = 'LCF'
    xVary = True
    defaultEntry = dict(
        name='', use=True, w=0.1, wBounds=[0., 1., 0.01],
        # if xVary is True, these two are needed:
        dx=0., dxBounds=[-1., 1., 0.01]
        # may have wtie, dxtie, later added: wError, dxError
        )
    defaultResult = dict(R=1., mesg='', ier=None, info={}, nparam=0)
    defaultParams = dict(lcf_params=[], lcf_xRange=None,
                         lcf_result=defaultResult)
    dataAttrs = dict(x='x', y='y', fit='fit')
    allDataAttrs = dict(x='x', y='y')
    ioAttrs = {'range': 'lcf_xRange', 'params': 'lcf_params',
               'result': 'lcf_result'}

    @classmethod
    def make_model_curve(cls, data, allData):
        dfparams = data.fitParams
        lcf = dfparams['lcf_params']
        if len(lcf) == 1 and len(lcf[0]['name']) == 0:  # default no-fit state
            return
        try:
            x = getattr(data, cls.dataAttrs['x'])
            y = getattr(data, cls.dataAttrs['y'])
        except AttributeError:
            return

        refs, args = {}, []
        lcfProps = dict(cls.defaultResult)
        try:
            for v in lcf:
                if not v['use']:
                    continue
                k = v['name']
                for sp in allData:
                    if sp.alias == k:
                        break
                else:
                    raise ValueError(
                        'No reference spectrum {0} found'.format(k))
                xref = getattr(sp, cls.allDataAttrs['x'])
                yref = getattr(sp, cls.allDataAttrs['y'])
                refs[k] = dict(x=xref, y=yref, w=len(args))
                args.append(v['w'])
            if cls.xVary:
                for v in lcf:
                    if not v['use']:
                        continue
                    k = v['name']
                    refs[k]['dx'] = len(args)
                    args.append(v['dx'])

            if len(refs) == 0:
                fit = np.zeros_like(x)
            else:
                fit = cls.linear_combination(x, *args, refs=refs)
            lcfProps['R'] = ((y - fit)**2).sum() / (y**2).sum()
        except (RuntimeError, ValueError, KeyError) as err:
            print('Error: ', err)
            fit = np.zeros_like(x)

        setattr(data, cls.dataAttrs['fit'], fit)
        dfparams['lcf_result'] = lcfProps

    @classmethod
    def run_main(cls, data, allData):
        dfparams = data.fitParams
        lcf = dfparams['lcf_params']
        xRange = dfparams['lcf_xRange']
        x = getattr(data, cls.dataAttrs['x'])
        y = getattr(data, cls.dataAttrs['y'])

        refs = {}
        args, mins, maxs = [], [], []
        argNames = []  # for diagnostics
        try:
            for v in lcf:
                if not v['use']:
                    continue
                k = v['name']
                for sp in allData:
                    if sp.alias == k:
                        break
                else:
                    raise ValueError(
                        'No reference spectrum {0} found'.format(k))
                xref = getattr(sp, cls.allDataAttrs['x'])
                yref = getattr(sp, cls.allDataAttrs['y'])
                refs[k] = dict(x=xref, y=yref)

                wantVary = True
                if 'wtie' in v:
                    tieStr = v['wtie']
                    if not cls.can_interpret_LCF_tie_str(tieStr, lcf):
                        raise ValueError('wrong tie expr for w[{0}]'.format(k))
                    refs[k]['w'] = v['w'] if tieStr.startswith('fix') else \
                        tieStr
                    refs[k]['wtie'] = tieStr
                    # if tieStr[0] in '<>' then w is both tied and varied
                    if tieStr[0] not in '<>':
                        wantVary = False
                if wantVary:
                    wMin, wMax = v['wBounds'][:2]
                    if wMin < wMax:
                        refs[k]['w'] = len(args)
                        args.append(v['w'])
                        argNames.append(k)
                        mins.append(wMin)
                        maxs.append(wMax)
                    else:
                        refs[k]['w'] = float(wMin)
                        v['w'] = wMin
            if cls.xVary:
                kd = 'dx'
                kdt = kd + 'tie'
                for v in lcf:
                    if not v['use']:
                        continue
                    k = v['name']
                    wantVary = True
                    if kdt in v:
                        tieStr = v[kdt]
                        if not cls.can_interpret_LCF_tie_str(tieStr, lcf):
                            raise ValueError(
                                'wrong tie expr for {0}[{1}]'.format(kd, k))
                        refs[k][kd] = v[kd] if tieStr.startswith('fix') else \
                            tieStr
                        refs[k][kdt] = tieStr
                        # if tieStr[0] in '<>' then dE is both tied and varied
                        if tieStr[0] not in '<>':
                            wantVary = False
                    if wantVary:
                        dEMin, dEMax = v[kd+'Bounds'][:2]
                        if dEMin < dEMax:
                            refs[k][kd] = len(args)
                            args.append(v[kd])
                            argNames.append('dE_'+k)
                            mins.append(dEMin)
                            maxs.append(dEMax)
                        else:
                            refs[k][kd] = float(dEMin)
                            v[kd] = dEMin

            where = (xRange[0] <= x) & (x <= xRange[1]) \
                if isinstance(xRange, (list, tuple)) else None
            locx = x[where]
            locy = y[where]
            fcounter = {'nfev': 0}
            wopt, pcov, info, mesg, ier = curve_fit(partial(
                cls.linear_combination, refs=refs, fcounter=fcounter),
                locx, locy, p0=args, bounds=(mins, maxs), full_output=True)
            # info2 = {'nfev': info['nfev']}
            info2 = fcounter
            lcfProps = dict(mesg=mesg, ier=ier, info=info2, nparam=len(wopt))
            fit = cls.linear_combination(x, *wopt, refs=refs)
            lcfProps['R'] = ((locy - fit[where])**2).sum() / (locy**2).sum()

            werr = np.sqrt(np.diag(pcov))
            for v in lcf:
                if not v['use']:
                    continue
                ref = refs[v['name']]
                indw = ref['w']
                if isinstance(indw, int):
                    v['w'] = wopt[indw]
                    v['wError'] = werr[indw]
                elif isinstance(indw, float):  # fixed
                    if 'wError' in v:
                        del v['wError']
                if 'wres' in ref:
                    v['w'] = ref['wres']
                    if 'wError' in v:
                        del v['wError']
            if cls.xVary:
                for v in lcf:
                    if not v['use']:
                        continue
                    ref = refs[v['name']]
                    inddE = ref[kd]
                    if isinstance(inddE, int):
                        v[kd] = wopt[inddE]
                        v[kd+'Error'] = werr[inddE]
                    elif isinstance(inddE, float):  # fixed
                        if kd+'Error' in v:
                            del v[kd+'Error']
                    if 'shres' in ref:
                        v[kd] = ref['shres']
                        if kd+'Error' in v:
                            del v[kd+'Error']
        except (RuntimeError, ValueError, TypeError) as e:
            # print('Error: ', e)
            fit = np.zeros_like(x)
            lcfProps = dict(cls.defaultResult)
            lcfProps['mesg'] = str(e)

        setattr(data, cls.dataAttrs['fit'], fit)
        dfparams['lcf_result'] = lcfProps

    @classmethod
    def can_interpret_LCF_tie_str(cls, tieStr, lcf):
        if tieStr.startswith('fix'):  # fixed
            return True
        if tieStr[0] not in '=<>':
            return False
        w = [0]  # w list indexing is 1-based
        if cls.xVary:
            dx = [0]  # dE list indexing is 1-based
        for ref in lcf:
            w.append(ref['w'])
            if cls.xVary:
                dx.append(ref['dx'])
        try:
            eval(tieStr[1:])
            return True
        except Exception:
            return False

    @classmethod
    def linear_combination(cls, x, *params, refs, fcounter={}):
        """
        *x* : array of energy of the fitted spectrum,

        *params*: sequence of fitting parameters, weights and energy shifts,

        *refs*: dict of [ref name]: dict with keys 'x', 'y', 'w', 'dx'
        The values of 'w' and 'dx' are indices of *params* list.
        """

        if fcounter:
            fcounter['nfev'] += 1
        w = [0]  # w list indexing is 1-based for tie formulae
        for ref in refs.values():
            wr = ref['w']
            w.append(params[wr] if isinstance(wr, int) else
                     wr if isinstance(wr, float) else 0.)
        kd = 'dx'
        if cls.xVary:
            _s = [0]  # is 1-based
            for ref in refs.values():
                dEr = ref[kd]
                _s.append(params[dEr] if isinstance(dEr, int) else
                          dEr if isinstance(dEr, float) else 0.)
        else:
            _s = [0] * (len(refs)+1)  # is 1-based
        dx = _s  # analysis:ignore

        assert len(refs) == len(w[1:]) == len(_s[1:])
        kdt = kd + 'tie'
        res = 0.
        for (k, ref), wi, sh in zip(refs.items(), w[1:], _s[1:]):
            xref, yref = ref['x'], ref['y']
            if 'wtie' in ref:
                wtie = ref['wtie']
                if wtie[0] in '=<>':
                    val = eval(wtie[1:])
                    if (wtie[0] == '=' or (wtie[0] == '<' and wi > val) or
                            (wtie[0] == '>' and wi < val)):
                        wi = val
                        ref['wres'] = val
            if cls.xVary:
                if kdt in ref:
                    dtie = ref[kdt]
                    if dtie[0] in '=<>':
                        val = eval(dtie[1:])
                        if (dtie[0] == '=' or (dtie[0] == '<' and sh > val) or
                                (dtie[0] == '>' and sh < val)):
                            sh = val
                            ref['shres'] = val
            f = interpolate.interp1d(
                xref+sh, yref, kind='linear', copy=False,
                fill_value='extrapolate', assume_sorted=True)
            res += wi * f(x)
        return res
