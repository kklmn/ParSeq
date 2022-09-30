# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 Feb 2019"
# !!! SEE CODERULES.TXT !!!

import os
from silx.gui import qt
from silx.gui import plot as splot

from ..core import singletons as csi


class Plot1D(splot.PlotWindow):
    def __init__(self, parent=None, backend=None, position=True):
        super().__init__(parent=parent, backend=backend,
                         resetzoom=True, autoScale=True,
                         logScale=True, grid=True,
                         curveStyle=True, colormap=False,
                         aspectRatio=False, yInverted=False,
                         copy=True, save=True, print_=True,
                         control=True, position=position,
                         roi=False, mask=False, fit=False)
        if parent is None:
            self.setWindowTitle('Plot1D')
        action = self.getFitAction()
        action.setXRangeUpdatedOnZoom(True)
        action.setFittedItemUpdatedFromActiveCurve(True)

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
        csi.selectedItems[:] = []
        csi.selectedItems.extend([item])
        csi.selectedTopItems[:] = []
        csi.selectedTopItems.extend(csi.model.getTopItems([index]))

        csi.selectionModel.setCurrentIndex(
            index, qt.QItemSelectionModel.ClearAndSelect |
            qt.QItemSelectionModel.Rows)
        nodeWidget = self.parent().parent().parent()
        nodeWidget.tree.setCurrentIndex(index)
        nodeWidget.tree.selChanged()
        nodeWidget.updateNodeForSelectedItems()


class Plot2D(splot.Plot2D):
    pass


class Plot3D(splot.StackView):
    posInfo = [
        ('Position', None),  # None is callback fn set after instantiation
        ('Value', None)]  # None is callback fn set after instantiation

    def setCustomPosInfo(self):
        p = self._plot._positionWidget._fields[0]
        self._plot._positionWidget._fields[0] = (p[0], p[1], self._imagePos)
        p = self._plot._positionWidget._fields[1]
        self._plot._positionWidget._fields[1] = (p[0], p[1], self._imageVal)

    def _imageVal(self, x, y):
        "used for displaying pixel value under cursor"
        activeImage = self.getActiveImage()
        if activeImage is not None:
            data = activeImage.getData()
            height, width = data.shape
            # print(width, height, x, y)
            x = int(x)
            y = int(y)
            return data[y][x] if 0 <= x < width and 0 <= y < height else ''
        return '-'

    def _imagePos(self, x, y):
        "used for displaying pixel coordinates under cursor"
        img_i = str(self._browser.value())
        x, y = "{:#.4g}".format(x), "{:#.4g}".format(y)
        if self._perspective == 0:
            dim0, dim1, dim2 = img_i, y, x
        elif self._perspective == 1:
            dim0, dim1, dim2 = y, img_i, x
        elif self._perspective == 2:
            dim0, dim1, dim2 = y, x, img_i
        return '{0}, {1}, {2}'.format(dim0, dim1, dim2)
