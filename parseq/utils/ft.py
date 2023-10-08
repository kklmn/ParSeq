# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "8 Jan 2023"
# !!! SEE CODERULES.TXT !!!

import numpy as np

ft_windows = ('none', 'box', 'linear-tapered', 'cosine-tapered',
              'Gaussian-tapered')


def make_ft_window(kind, x, xmin, xmax, width, vmin=0):
    """
    Create a tapered FT window function.

    *kind*: str
    one of `ft_windows`,

    *x*: array
    the independent variable of FT,

    *xmin*, xmax*: float
    the range of the transformed data,

    *width*: float
    the distance in x from xmin to the flat top and from the flat top to xmax,

    *vmin*: float
    the minimum value of the resulting window function at the ends.
    """
    res = np.ones_like(x)
    if not kind or kind == 'none':
        return res
    if kind == 'box':
        res[x < xmin] = 0
        res[x > xmax] = 0
        return res

    left_lobe = (x-xmin >= 0) & (x-xmin <= width)
    right_lobe = (xmax-x <= width) & (xmax-x >= 0)
    if kind == 'linear-tapered':
        if width > 1e-12:
            res[left_lobe] = (1-vmin) / width * (x[left_lobe]-xmin) + vmin
            res[right_lobe] = (1-vmin) / width * (xmax-x[right_lobe]) + vmin
    elif kind == 'cosine-tapered':
        v0 = vmin if 0 <= vmin <= 1 else 0
        if width > 1e-12:
            phi = np.pi * (x[left_lobe]-xmin) / width
            res[left_lobe] = 0.5 * (1-np.cos(phi)) * (1-v0) + v0
            phi = np.pi * (xmax-x[right_lobe]) / width
            res[right_lobe] = 0.5 * (1-np.cos(phi)) * (1-v0) + v0
    elif kind == 'Gaussian-tapered':
        v0 = vmin if 0 <= vmin <= 1 else 0
        if (width > 1e-12) and (v0 >= 1e-3):
            sigma2 = width**2 / (2*abs(np.log(v0)))
            res[left_lobe] = np.exp(-0.5*(x[left_lobe]-xmin-width)**2/sigma2)
            res[right_lobe] = np.exp(-0.5*(xmax-width-x[right_lobe])**2/sigma2)
    if len(res[left_lobe]) > 0:
        res[x < xmin] = vmin
    if len(res[right_lobe]) > 0:
        res[x > xmax] = vmin
    return res
