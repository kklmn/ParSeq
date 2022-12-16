# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "6 Apr 2021"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from scipy.interpolate import UnivariateSpline


def line(xs, ys):
    try:
        k = (ys[1] - ys[0]) / (xs[1] - xs[0])
    except ZeroDivisionError:
        return np.inf, 0.
    b = ys[1] - k*xs[1]
    return k, b


def fwhm(x, y):
    try:
        if x[0] > x[-1]:
            x, y = x[::-1], y[::-1]
        spline = UnivariateSpline(x, y - y.max()*0.5, s=0)
        roots = spline.roots()
        return max(roots) - min(roots)
    except ValueError:
        return


def get_roi_mask(geom, xs, ys):
    if geom['kind'] == 'RectangleROI':
        x, y = geom['origin']
        w, h = geom['size']
        return (xs >= x) & (xs <= x+w) & (ys >= y) & (ys <= y+h)
    elif geom['kind'] == 'ArcROI':
        x, y = geom['center']
        r1, r2 = geom['innerRadius'], geom['outerRadius']
        dist2 = (xs-x)**2 + (ys-y)**2
        return (dist2 >= r1**2) & (dist2 <= r2**2)
    elif geom['kind'] == 'BandROI':
        x1, y1 = geom['begin']
        x2, y2 = geom['end']
        k, b = line((x1, x2), (y1, y2))
        w = geom['width']
        return (ys >= k*(xs-w/2) + b) & (ys <= k*(xs+w/2) + b)
    elif geom['kind'] == 'HorizontalRangeROI':
        vmin, vmax = geom['vmin'], geom['vmax']
        return (xs >= vmin) & (xs <= vmax) & (ys > 0)
    else:
        raise ValueError('unsupported ROI type')


def interpolate_frames(keyFrameGeometries, ind, wantExtrapolate=True):
    """
    Piecewise linear interpolation between ROI geometries saved as key frames
    for a stacked image.
    *keyFrameGeometries*: dict {key_frame: [list of roi geometries]}, where roi
    geometries are dicts of roi parameters.
    *ind*: int index in the stacking direction
    *wantExtrapolate*: bool, controls the possible hanging ends, when the key
    frames are not at the ends of the stack.
    """
    assert len(keyFrameGeometries) > 1
    keys = list(sorted(keyFrameGeometries.keys()))
    if ind <= keys[0]:
        if wantExtrapolate:
            ikey = 0
        else:
            return keyFrameGeometries[keys[0]]
    elif ind >= keys[-1]:
        if wantExtrapolate:
            ikey = len(keys) - 2
        else:
            return keyFrameGeometries[keys[-1]]
    else:
        for ikey in range(len(keys)-1):
            if keys[ikey] <= ind < keys[ikey+1]:
                break
        else:
            raise ValueError('wrong key frames')

    # linear interpolation between ikey and ikey+1:
    savedRois0 = keyFrameGeometries[keys[ikey]]
    savedRois1 = keyFrameGeometries[keys[ikey+1]]
    rr = (ind-keys[ikey]) / (keys[ikey+1]-keys[ikey])
    res = []
    for savedRoi0, savedRoi1 in zip(savedRois0, savedRois1):
        savedRoi = {k0: v0 if isinstance(v0, (str, bool)) else
                    (np.array(v1)-np.array(v0))*rr + np.array(v0)
                    for (k0, v0), (k1, v1) in zip(
                        sorted(savedRoi0.items()), sorted(savedRoi1.items()))}
        res.append(savedRoi)
    return res
