# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 Feb 2019"
# !!! SEE CODERULES.TXT !!!

import os
from silx.gui import qt
from silx.gui import plot as splot
from silx.gui.plot.actions.control import ZoomBackAction, CrosshairAction
try:
    from silx.gui.plot.tools.menus import ZoomEnabledAxesMenu
except ModuleNotFoundError:
    ZoomEnabledAxesMenu = None

from ..core import singletons as csi


class Plot1D(splot.PlotWindow):
    def __init__(self, parent=None, backend=None, position=True):
        super().__init__(
            parent=parent, backend=backend, resetzoom=True, autoScale=True,
            logScale=True, grid=True, curveStyle=True, colormap=False,
            aspectRatio=False, yInverted=False, copy=True, save=True,
            print_=True, control=True, position=position, roi=False,
            mask=False, fit=False)
        if parent is None:
            self.setWindowTitle('Plot1D')

        self._zoomBackAction = ZoomBackAction(plot=self, parent=self)
        self._crosshairAction = CrosshairAction(plot=self, parent=self)
        if ZoomEnabledAxesMenu is not None:
            self._zoomEnabledAxesMenu = ZoomEnabledAxesMenu(
                plot=self, parent=self)
        self.isRightAxisVisible = False
        # Retrieve PlotWidget's plot area widget
        plotArea = self.getWidgetHandle()
        # Set plot area custom context menu
        plotArea.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        plotArea.customContextMenuRequested.connect(self._contextMenu)

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
        # elif ddict['event'] == "limitsChanged":
        #     print(ddict['ydata'])

    def addCurve(self, *args, **kwargs):
        lockwargs = dict(kwargs)
        symbolsize = lockwargs.pop('symbolsize', None)
        curve = super().addCurve(*args, **lockwargs)
        if symbolsize is not None:
            curve.setSymbolSize(symbolsize)
        return curve

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

    def _contextMenu(self, pos):
        """Handle plot area customContextMenuRequested signal.

        :param QPoint pos: Mouse position relative to plot area
        """
        # Create the context menu
        menu = qt.QMenu(self)
        menu.addAction(self._zoomBackAction)
        if self.isRightAxisVisible and ZoomEnabledAxesMenu is not None:
            menu.addMenu(self._zoomEnabledAxesMenu)
        menu.addSeparator()
        menu.addAction(self._crosshairAction)

        plotArea = self.getWidgetHandle()
        globalPosition = plotArea.mapToGlobal(pos)
        menu.exec(globalPosition)


# class Plot2D(splot.Plot2D):
class Plot2D(splot.ImageView):
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
