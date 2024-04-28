# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 Apr 2024"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline


def calc_correction(x, y, correction):
    if correction['kind'] == 'delete':
        lim = correction['lim']
        args = np.argwhere((lim[0] < x) & (x < lim[1]))
        return np.delete(x, args), np.delete(y, args)
    elif correction['kind'] == 'scale':
        lim = correction['lim']
        where = (lim[0] < x) & (x < lim[1])
        wx = x[where]
        if len(wx) == 0:
            return
        wy = y[where]
        if len(wy) == 0:
            return
        dy = wy.max() - wy.min()
        if dy == 0:
            return
        scale = correction['scale']
        factor = (scale - wy.min()) / dy
        yn = np.array(y)
        line = (wy[-1] - wy[0])/(wx[-1] - wx[0])*(wx - wx[0]) + wy[0]
        yn[where] = (wy - line)*factor + line
        return x, yn
    elif correction['kind'] == 'spline':
        lim = correction['lim']
        where = (lim[0] < x) & (x < lim[1])
        wx = x[where]
        if len(wx) == 0:
            return
        yn = np.array(y)
        kns = correction['knots']
        if len(kns) == 1:
            yn[where] = kns[0][1]
        else:  # len(knots) >= 2:
            k = min(len(kns)-1, 3)
            try:
                spl = InterpolatedUnivariateSpline(kns[:, 0], kns[:, 1], k=k)
                yn[where] = spl(wx)
            except ValueError:
                return
        return x, yn
    elif correction['kind'] == 'step':
        left = correction['left']
        right = correction['right']
        inStep = (left < x) & (x < right[0])
        afterStep = x >= right[0]
        eAfterStep = x[afterStep]
        if len(eAfterStep) == 0:
            return
        dyAfter = y[afterStep][0] - right[1]
        yn = np.array(y)
        yn[afterStep] -= dyAfter
        xInStep = x[inStep]
        if len(xInStep) > 0:
            yn[inStep] -= dyAfter / (right[0] - left) * (xInStep - left)
        return x, yn
