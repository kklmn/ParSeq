# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "31 Oct 2026"
# !!! SEE CODERULES.TXT !!!

import os
import sys

if sys.platform == "linux":
    os.environ["PYOPENGL_PLATFORM"] = "glx"
if sys.platform == "darwin":
    os.environ["QT_STYLE_OVERRIDE"] = "Fusion"

import numpy as np

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
            aspectRatio=False, yInverted=False, copy=False, save=True,
            print_=False, control=False, position=position, roi=False,
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

        self.savedBackgroundColor = None
        self.savedDataBackgroundColor = None

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
        menu.addSeparator()
        color1 = self.getBackgroundColor().name()
        color2 = self.getDataBackgroundColor().name()
        if color1 == color2 == "#ffffff":
            bkndAction = qt.QAction(self.makeColorIcon("saved"),
                                    "Set standard background", parent=self)
        else:
            bkndAction = qt.QAction(self.makeColorIcon("white"),
                                    "Set white background", parent=self)
        bkndAction.triggered.connect(self.changeBackground)
        menu.addAction(bkndAction)

        self._sigDefaultContextMenu.emit(menu)

        plotArea = self.getWidgetHandle()
        globalPosition = plotArea.mapToGlobal(pos)
        menu.exec(globalPosition)

    def changeBackground(self):
        color1 = self.getBackgroundColor().name()
        color2 = self.getDataBackgroundColor().name()
        if color1 == color2 == "#ffffff":
            self.setBackgroundColor(self.savedBackgroundColor)
            self.setDataBackgroundColor(self.savedDataBackgroundColor)
            inst = qt.QCoreApplication.instance()
            tcolor = inst.palette().color(qt.QPalette.Text)
            self.setForegroundColor(tcolor)
        else:
            self.setBackgroundColor("#ffffff")
            self.setDataBackgroundColor("#ffffff")
            self.setForegroundColor('#000000')

    def setBackgroundColor(self, color):
        super().setBackgroundColor(color)
        if self.savedBackgroundColor is None:
            self.savedBackgroundColor = color

    def setDataBackgroundColor(self, color):
        super().setDataBackgroundColor(color)
        if self.savedDataBackgroundColor is None:
            self.savedDataBackgroundColor = color

    def makeColorIcon(self, color='saved', size=16):
        pm = qt.QPixmap(size, size)
        if color == 'saved':
            color1 = qt.QColor(self.savedBackgroundColor)
            color2 = qt.QColor(self.savedDataBackgroundColor)
            inst = qt.QCoreApplication.instance()
            color3 = inst.palette().color(qt.QPalette.Text)
        else:
            color1 = color2 = qt.Qt.white
            color3 = qt.Qt.black
        pm.fill(color1)
        painter = qt.QPainter(pm)
        painter.fillRect(3, 2, size-6, size-6, color2)
        painter.setPen(color3)  # border
        painter.drawRect(3, 2, size-6, size-6)
        painter.drawLine(6, size-3, 6, size-2)
        painter.drawLine(12, size-3, 12, size-2)
        painter.drawLine(1, 6, 2, 6)
        painter.drawLine(1, 12, 2, 12)
        painter.end()
        return qt.QIcon(pm)


# class Plot2D(splot.Plot2D):

class Plot2D(splot.ImageView):
    def __init__(self, parent=None, backend=None):
        super().__init__(parent=parent, backend=backend)
        self._outputToolBar.getCopyAction().setVisible(False)  # remove copy
        self.valueChanged.connect(self._showCustomPosInfo)

    def _showCustomPosInfo(self, row, column, value):
        """Update status bar with coordinates/value from plots."""
        if np.isnan(row):
            msg = f"Column: {int(column)}, Sum: {value:.4g}"
        elif np.isnan(column):
            msg = f"Row: {int(row)}, Sum: {value:.4g}"
        else:
            msg = f"Position: ({int(row)}, {int(column)}), Value: {value:.4g}"
        self.setGraphTitle(msg)

    def setBackgroundColor(self, color):
        super().setBackgroundColor(color)
        self._histoHPlot.setBackgroundColor(color)
        self._histoVPlot.setBackgroundColor(color)

    def setDataBackgroundColor(self, color):
        super().setDataBackgroundColor(color)
        self._histoHPlot.setDataBackgroundColor(color)
        self._histoVPlot.setDataBackgroundColor(color)


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
