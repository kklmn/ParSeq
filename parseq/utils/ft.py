# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "8 Jan 2023"
# !!! SEE CODERULES.TXT !!!

import numpy as np

ft_windows = 'none', 'box', 'linear-tapered',


def make_ft_window(kind, x, xmin, xmax, width, vmin):
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
    res[x < xmin] = 0
    res[x > xmax] = 0
    if kind == 'box':
        return res
    elif kind == 'linear-tapered':
        left_lobe = (x-xmin >= 0) & (x-xmin <= width)
        right_lobe = (xmax-x <= width) & (xmax-x >= 0)
        res[left_lobe] = (1-vmin) / width * (x[left_lobe]-xmin) + vmin
        res[right_lobe] = (1-vmin) / width * (xmax-x[right_lobe]) + vmin
    return res
