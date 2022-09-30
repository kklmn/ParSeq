#!/usr/bin/env python
# coding: utf-8

from functools import partial
import numpy as np

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.roi import RoiWidget

ndim = 2
nx, ny = 1920, 1200
if ndim == 2:
    from silx.gui.plot import Plot2D
elif ndim == 3:
    from silx.gui.plot import StackView
else:
    raise ValueError('unknown dimension')


def dummy_image():
    x = np.linspace(-1.5, 1.5, nx)
    y = np.linspace(-1.5, 1.5, ny)
    xv, yv = np.meshgrid(x, y)
    signal = np.exp(-(xv**2 / 0.45**2 + yv**2 / 0.15**2))
    noise = 0.3 * np.random.random(size=signal.shape)
    return (signal + noise) * 100


app = qt.QApplication([])  # Start QApplication

# Create the plot widget and add an image
image = dummy_image()
if ndim == 2:
    plot = Plot2D()
    plot.getDefaultColormap().setName('viridis')
    plot.addImage(image)
elif ndim == 3:
    plot = StackView()
    plot.setColormap('viridis')
    stack = np.stack([image for i in range(10)])
    # print(stack.shape)
    plot.setStack(stack)

plot.setKeepDataAspectRatio(False)


def roiDockVisibilityChanged(visible):
    """Handle change of visibility of the roi dock widget

    If dock becomes hidden, ROI interaction is stopped.
    """
    if not visible:
        roiWidget.roiManager.stop()


def acceptROI(roiWidget):
    roi = roiWidget.roiManager.getCurrentRoi()
    if roi.__class__.__name__ in ('ArcROI', 'RectangleROI'):
        geom = roi._geometry
        cx, cy = list(geom.center)
        radius = (roi.getInnerRadius() + roi.getOuterRadius()) * 0.5
        outY = np.arange(ny)
        outX = cx + (radius**2 - (outY - cy)**2)**0.5
        print((outX[0], outY[0]), (outX[-1], outY[-1]))
        return outX, outY
    elif roi.__class__.__name__ in ('PointROI', 'CrossROI'):
        res = list(roi.getPosition())
        print(res)
        return res


# # test arc type:
# roiDict = dict(kind='ArcROI', name='arc1', center=(-1000, 1000),
#                innerRadius=1950, outerRadius=2050,
#                startAngle=-0.5, endAngle=0.1)
# roiWidget = RoiWidget(None, plot, ['ArcROI'], 3)

# test point types:
roiDict = [dict(kind='CrossROI', name='p1', pos=(100, 100)),
           dict(kind='PointROI', name='p2', pos=(900, 900))]
roiWidget = RoiWidget(None, plot, ['CrossROI', 'PointROI'], 2)


roiWidget.setRois(roiDict)
roiWidget.dataToCount = stack if ndim == 3 else image
roiWidget.acceptButton.clicked.connect(partial(acceptROI, roiWidget))

dock = qt.QDockWidget('Image ROI')
dock.setWidget(roiWidget)
dock.visibilityChanged.connect(roiDockVisibilityChanged)
plot.addDockWidget(qt.Qt.RightDockWidgetArea, dock)

# Show the widget and start the application
plot.show()
result = app.exec()
app.deleteLater()
sys.exit(result)
