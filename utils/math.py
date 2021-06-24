# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "6 Apr 2021"
# !!! SEE CODERULES.TXT !!!

from scipy.interpolate import UnivariateSpline


def fwhm(x, y):
    try:
        if x[0] > x[-1]:
            x, y = x[::-1], y[::-1]
        spline = UnivariateSpline(x, y - y.max()*0.5, s=0)
        roots = spline.roots()
        return max(roots) - min(roots)
    except ValueError:
        return
