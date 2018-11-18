# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from matplotlib.colors import LinearSegmentedColormap
from silx.gui.plot import Colormap
from matplotlib import cm


class Colormaps:
    def __init__(self, parent=None):
        self._colormaps = {}

        cdict = {'red': ((0.0, 0.0, 0.0),
                         (1.0, 1.0, 1.0)),
                 'green': ((0.0, 0.0, 0.0),
                           (1.0, 0.0, 0.0)),
                 'blue': ((0.0, 0.0, 0.0),
                          (1.0, 0.0, 0.0))}
        self._colormaps['red'] = LinearSegmentedColormap(
            'red', cdict, 256)

        cdict = {'red': ((0.0, 0.0, 0.0),
                         (1.0, 0.0, 0.0)),
                 'green': ((0.0, 0.0, 0.0),
                           (1.0, 1.0, 1.0)),
                 'blue': ((0.0, 0.0, 0.0),
                          (1.0, 0.0, 0.0))}
        self._colormaps['green'] = LinearSegmentedColormap(
            'green', cdict, 256)

        cdict = {'red': ((0.0, 0.0, 0.0),
                         (1.0, 0.0, 0.0)),
                 'green': ((0.0, 0.0, 0.0),
                           (1.0, 0.0, 0.0)),
                 'blue': ((0.0, 0.0, 0.0),
                          (1.0, 1.0, 1.0))}
        self._colormaps['blue'] = LinearSegmentedColormap(
            'blue', cdict, 256)

        # Temperature as defined in spslut
        cdict = {'red': ((0.0, 0.0, 0.0),
                         (0.5, 0.0, 0.0),
                         (0.75, 1.0, 1.0),
                         (1.0, 1.0, 1.0)),
                 'green': ((0.0, 0.0, 0.0),
                           (0.25, 1.0, 1.0),
                           (0.75, 1.0, 1.0),
                           (1.0, 0.0, 0.0)),
                 'blue': ((0.0, 1.0, 1.0),
                          (0.25, 1.0, 1.0),
                          (0.5, 0.0, 0.0),
                          (1.0, 0.0, 0.0))}
        # but limited to 256 colors for a faster display (of the colorbar)
        self._colormaps['temperature'] = LinearSegmentedColormap(
            'temperature', cdict, 256)

        # reversed gray
        cdict = {'red':     ((0.0, 1.0, 1.0),
                             (1.0, 0.0, 0.0)),
                 'green':   ((0.0, 1.0, 1.0),
                             (1.0, 0.0, 0.0)),
                 'blue':    ((0.0, 1.0, 1.0),
                             (1.0, 0.0, 0.0))}

        self._colormaps['reversed gray'] = LinearSegmentedColormap(
            'yerg', cdict, 256)

    def getCmap(self, name):
        if name in self._colormaps:
            return self._colormaps[name]
        elif hasattr(Colormap, name):  # viridis and sister colormaps
            return getattr(Colormap, name)
        else:
            # matplotlib built-in
            return cm.get_cmap(name)
