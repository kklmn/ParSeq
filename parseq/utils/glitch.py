# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "19 Jan 2025"

import numpy as np
from scipy.signal import find_peaks


def calc_glitches(peakSettings, x, y):
    fit = np.polyfit(x, y, 3)
    baseline = np.poly1d(fit)  # create the linear baseline function
    yc = y - baseline(x)
    dy = yc.max() - yc.min()
    peaks, props = find_peaks(
        yc*peakSettings['sign'], prominence=dy*peakSettings['prominence'],
        width=peakSettings['width'], rel_height=peakSettings['rel_height'])
    return peaks, props
