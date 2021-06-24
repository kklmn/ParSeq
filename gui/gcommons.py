# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import numpy as np
from silx.gui import qt

colorCycle1 = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
               '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']  # mpl
colorCycle2 = ['#0000ff', '#00ee00', '#ff0000', '#00ffff', '#ff00ff',
               '#ffff00', '#aaaaaa', '#000000']

COLOR_POLICY_INDIVIDUAL, COLOR_POLICY_LOOP1, COLOR_POLICY_LOOP2,\
    COLOR_POLICY_GRADIENT = range(4)
COLOR_POLICY_NAMES = 'individual', 'loop1', 'loop2', 'gradient'

COLOR_HDF5_HEAD = '#2299F0'
COLOR_FS_COLUMN_FILE = '#32AA12'
COLOR_LOAD_CAN = '#44C044'
COLOR_LOAD_CANNOT = '#C04444'


def makeGradientCollection(color1, color2, ncolor=8):
    c1 = np.array(qt.QColor(color1).getHsvF())
    c2 = np.array(qt.QColor(color2).getHsvF())
    c1[c1 < 0] = 0  # for gray, getHsvF returns hue=-1 that is not accepted by fromHsv  # noqa
    c2[c2 < 0] = 0
    t = np.linspace(0, 1, ncolor)[:, np.newaxis]
    colors = c1*(1-t) + c2*t
    res = []
    for i in range(ncolor):
        res.append(qt.QColor.fromHsvF(*colors[i]))
    return res


def getColorName(color):
    return qt.QColor(color).name()
