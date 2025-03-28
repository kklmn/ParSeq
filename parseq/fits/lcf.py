# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "12 Jan 2025"
# !!! SEE CODERULES.TXT !!!

# import os.path as osp
from functools import partial
import numpy as np
from scipy.optimize import curve_fit
from scipy import interpolate

from .basefit import Fit


class LCF(Fit):
    name = 'LCF'
    xVary = False
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
        if data is None:
            return
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
            for iv, v in enumerate(lcf):
                if not v['use']:
                    continue
                k = v['name']
                if 'isMeta' in v:
                    refs[k] = dict(w=[len(args), iv], isMeta=True)
                else:
                    for sp in allData:
                        if sp.alias == k:
                            break
                    else:
                        raise ValueError(
                            'No reference spectrum {0} found'.format(k))
                    xref = getattr(sp, cls.allDataAttrs['x'])
                    yref = getattr(sp, cls.allDataAttrs['y'])
                    refs[k] = dict(x=xref, y=yref, w=[len(args), iv])
                args.append(v['w'])
            if cls.xVary:
                for iv, v in enumerate(lcf):
                    if not v['use']:
                        continue
                    k = v['name']
                    if 'isMeta' in v:
                        refs[k]['dx'] = None
                        continue
                    refs[k]['dx'] = [len(args), iv]
                    args.append(v['dx'])

            if len(refs) == 0:
                fit = np.zeros_like(x)
            else:
                fit = cls.linear_combination(x, *args, refs=refs,
                                             lenlcf=len(lcf))
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
            for iv, v in enumerate(lcf):
                if not v['use']:
                    continue
                k = v['name']
                if 'isMeta' in v:
                    refs[k] = dict(isMeta=True)
                else:
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
                    refs[k]['w'] = [v['w'], iv] if tieStr.startswith('fix') \
                        else tieStr
                    refs[k]['wtie'] = tieStr
                    # if tieStr[0] in '<>' then w is both tied and varied
                    if tieStr[0] not in '<>':
                        wantVary = False
                if wantVary:
                    wMin, wMax = v['wBounds'][:2]
                    if wMin < wMax:
                        refs[k]['w'] = [len(args), iv]
                        args.append(v['w'])
                        argNames.append(k)
                        mins.append(wMin)
                        maxs.append(wMax)
                    else:
                        refs[k]['w'] = [float(wMin), iv]
                        v['w'] = wMin
            if cls.xVary:
                kd = 'dx'
                kdt = kd + 'tie'
                for iv, v in enumerate(lcf):
                    if not v['use']:
                        continue
                    k = v['name']
                    if 'isMeta' in v:
                        refs[k][kd] = None
                        continue
                    wantVary = True
                    if kdt in v:
                        tieStr = v[kdt]
                        if not cls.can_interpret_LCF_tie_str(tieStr, lcf):
                            raise ValueError(
                                'wrong tie expr for {0}[{1}]'.format(kd, k))
                        refs[k][kd] = [v[kd], iv] if tieStr.startswith('fix') \
                            else tieStr
                        refs[k][kdt] = tieStr
                        # if tieStr[0] in '<>' then dE is both tied and varied
                        if tieStr[0] not in '<>':
                            wantVary = False
                    if wantVary:
                        dEMin, dEMax = v[kd+'Bounds'][:2]
                        if dEMin < dEMax:
                            refs[k][kd] = [len(args), iv]
                            args.append(v[kd])
                            argNames.append('dE_'+k)
                            mins.append(dEMin)
                            maxs.append(dEMax)
                        else:
                            refs[k][kd] = [float(dEMin), iv]
                            v[kd] = dEMin

            where = (xRange[0] <= x) & (x <= xRange[1]) \
                if isinstance(xRange, (list, tuple)) else None
            locx = x[where]
            locy = y[where]
            fcounter = {'nfev': 0}
            wopt, pcov, info, mesg, ier = curve_fit(partial(
                cls.linear_combination, refs=refs, lenlcf=len(lcf),
                fcounter=fcounter),
                locx, locy, p0=args, bounds=(mins, maxs), full_output=True)
            # info2 = {'nfev': info['nfev']}
            info2 = fcounter
            lcfProps = dict(mesg=mesg, ier=ier, info=info2, nparam=len(wopt))
            fit = cls.linear_combination(x, *wopt, refs=refs, lenlcf=len(lcf))
            lcfProps['R'] = ((locy - fit[where])**2).sum() / (locy**2).sum()

            werr = np.sqrt(np.diag(pcov))
            for v in lcf:
                if not v['use']:
                    continue
                ref = refs[v['name']]
                indw = ref['w']
                if isinstance(indw, list):
                    if isinstance(indw[0], int):
                        v['w'] = wopt[indw[0]]
                        v['wError'] = werr[indw[0]]
                    elif isinstance(indw[0], float):  # fixed
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
                    if isinstance(inddE, list):
                        if isinstance(inddE[0], int):
                            v[kd] = wopt[inddE[0]]
                            v[kd+'Error'] = werr[inddE[0]]
                        elif isinstance(inddE[0], float):  # fixed
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
        _locals = dict(w=w)
        if cls.xVary:
            dx = [0]  # dE list indexing is 1-based
            _locals['dx'] = dx
        for ref in lcf:
            w.append(ref['w'])
            if cls.xVary:
                dx.append(ref['dx'])
            if 'isMeta' in ref:
                _locals[ref['name']] = ref['w']
        try:
            eval(tieStr[1:], {}, _locals)
            return True
        except Exception:
            return False

    @classmethod
    def linear_combination(cls, x, *params, refs, lenlcf, fcounter={}):
        """
        *x* : array of energy of the fitted spectrum,

        *params*: sequence of fitting parameters, weights and energy shifts,

        *refs*: dict of [ref name]: dict with keys 'x', 'y', 'w', 'dx'
        The values of 'w' and 'dx' are indices of *params* list.
        """

        if fcounter:
            fcounter['nfev'] += 1

        w = [0] * (lenlcf+1)  # w list indexing is 1-based for tie formulae
        _locals = dict(w=w)
        _w = []
        for iref, (k, ref) in enumerate(refs.items()):
            wr = ref['w']
            val = 0.
            if isinstance(wr, list):
                if isinstance(wr[0], int):
                    val = params[wr[0]]
                elif isinstance(wr[0], float):
                    val = wr[0]
                w[wr[1]+1] = val
            _w.append(val)
            if 'isMeta' in ref:
                _locals[k] = val
        kd = 'dx'
        dx = [0] * (lenlcf+1)  # is 1-based
        _dx = []
        if cls.xVary:
            for ref in refs.values():
                dEr = ref[kd]
                val = 0.
                if isinstance(dEr, list):
                    if isinstance(dEr[0], int):
                        val = params[dEr[0]]
                    elif isinstance(dEr[0], float):
                        val = dEr[0]
                    dx[dEr[1]+1] = val
                _dx.append(val)
        _locals['dx'] = dx

        assert len(refs) == len(_w)
        if cls.xVary:
            assert len(refs) == len(_dx)

        kdt = kd + 'tie'
        res = 0.
        for (k, ref), wi, sh in zip(refs.items(), _w, _dx):
            if 'wtie' in ref:
                wtie = ref['wtie']
                if wtie[0] in '=<>':
                    val = eval(wtie[1:], {}, _locals)
                    if (wtie[0] == '=' or (wtie[0] == '<' and wi > val) or
                            (wtie[0] == '>' and wi < val)):
                        wi = val
                        ref['wres'] = val
            if cls.xVary:
                if kdt in ref:
                    dtie = ref[kdt]
                    if dtie[0] in '=<>':
                        val = eval(dtie[1:], {}, _locals)
                        if (dtie[0] == '=' or (dtie[0] == '<' and sh > val) or
                                (dtie[0] == '>' and sh < val)):
                            sh = val
                            ref['shres'] = val
            if 'isMeta' not in ref:
                xref, yref = ref['x'], ref['y']
                f = interpolate.interp1d(
                    xref+sh, yref, kind='linear', copy=False,
                    fill_value='extrapolate', assume_sorted=True)
                res += wi * f(x)
        return res
