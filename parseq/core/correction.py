# -*- coding: utf-8 -*-
u"""
Data corrections
----------------

General (not pipeline-specific) data corrections were designed in ParSeq for
the amendment of data distortions. One example of data correction is the
removal of diffraction peaks arriving at a fluorescence detector during x-ray
absorption measurements. In this case, diffraction peaks may appear as sharp
artefacts seen by different detector channels at different x-ray energies. The
correction can be a simple deletion of a few data points or a replacement by a
spline segment, where the comparison with undistorted spectra can guide the
decisions.

The ParSeq corrections operate in a transformation node and are applied to all
data arrays defined in that node. The corrections are calculated following the
incoming transformations that lead to the node.

.. note::
   When setting up a correction that depends on y-coordinates (e,g. spline
   correction) in the ParSeq GUI, make sure that the plot widget does not
   apply a normalization or any other modification affecting the y-axis.

In the present version, only 1D nodes can receive corrections. Each correction
defines a dictionary of parameters. The following corrections are defined.

+------------------+------------------+
|    correction    |    description   |
+==================+==================+
|  delete region   | |text_del|       |
+------------------+------------------+
|  scale region    | |text_scl|       |
+------------------+------------------+
| replace region   |                  |
| by spline        | |text_spl|       |
+------------------+------------------+
| delete spikes    | |text_spk|       |
+------------------+------------------+
| remove data step | |text_stp|       |
+------------------+------------------+

.. |text_del| replace::
   (*lim*: 2-sequence)
   All points within the (lim[0], lim[1]) interval are deleted from the node
   arrays.

.. |text_scl| replace::
   (*lim*: 2-sequence, *scale*: float)
   All points within the (lim[0], lim[1]) interval are vertically scaled toward
   the straight line connecting the end data points that fall within the
   interval. The scaling factor depends on the vertical distance from the
   `scale` parameter to the straight line.

.. |text_spl| replace::
   (*lim*: 2-sequence, *knots*: list of 2-lists ((x, y) points))
   A spline drawn through the given knots replaces the points within the
   (lim[0], lim[1]) interval.

.. |text_spk| replace::
   (*lim*: 2-sequence, *cutoff*: float)
   The first y-array defined in the node is used to calculate its second
   difference. The second difference is normalized to its maximum and compared
   with `cutoff`. The exciding points are deleted from the node arrays.
   The automatic cutoff is set as 0.7.

.. |text_stp| replace::
   (*left*: float (x-coordinate), *right*: 2-sequence ((x, y) point))
   All data points to the right of the `right` point are shifted vertically by
   the height difference at the `right` point. The points within the interval
   from left to right are linearly shifted from zero at the left to the found
   constant shift at the right.

"""
__author__ = "Konstantin Klementiev"
__date__ = "22 Nov 2024"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from scipy.interpolate import InterpolatedUnivariateSpline

AUTO_CUTOFF = 0.7  # for 'spikes', fraction of max(d²y)


def calc_correction(x, y, correction, datainds=None):
    if 'lim' not in correction and 'range' in correction:  # compatibility
        correction['lim'] = correction['range']
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
    elif correction['kind'] == 'spikes':
        lim, cutoff = correction['lim'], correction['cutoff']
        if cutoff is None:
            return x, y
        elif isinstance(cutoff, str):
            cutoff = AUTO_CUTOFF
        if not (0 < cutoff < 1):
            return x, y
        if datainds is None:
            where = np.argwhere((lim[0] < x) & (x < lim[1])).flatten()
            y2der = np.gradient(np.gradient(y))
            y2derw = y2der[where]
            if len(y2derw) == 0:
                return x, y
            y2derC = abs(y2derw).max() * cutoff
            args = np.argwhere((y2der < -y2derC) | (y2der > y2derC)).flatten()
            argsd = np.intersect1d(where, args)
        else:
            argsd = datainds
        return np.delete(x, argsd), np.delete(y, argsd), argsd
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
