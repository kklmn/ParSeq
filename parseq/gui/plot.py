# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 Feb 2019"
# !!! SEE CODERULES.TXT !!!

import os
from silx.gui import qt
from silx.gui import plot

from ..core import singletons as csi


class Plot1D(plot.Plot1D):
    def graphCallback(self, ddict=None):
        """This callback is going to receive all the events from the plot."""
        if ddict is None:
            ddict = {}
        if ddict['event'] in ["legendClicked", "curveClicked"]:
            if ddict['button'] == "left":
                self.activateCurve(ddict['label'])
                qt.QToolTip.showText(self.cursor().pos(), ddict['label'])

    def activateCurve(self, label):
        alias = os.path.splitext(label)[0]
        for item in csi.allLoadedItems:
            if item.alias == alias:
                break
        else:
            return
        index = csi.model.indexFromItem(item)
        csi.selectionModel.setCurrentIndex(
            index, qt.QItemSelectionModel.ClearAndSelect |
            qt.QItemSelectionModel.Rows)
