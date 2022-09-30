#!/usr/bin/env python
# coding: utf-8

import numpy as np

from silx.gui import qt
# from silx.gui.plot.items.roi import ArcROI, RectangleROI

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.roi import RoiWidgetWithKeyFrames

ndim = 3
if ndim == 2:
    from silx.gui.plot import Plot2D
elif ndim == 3:
    from silx.gui.plot import StackView
else:
    raise ValueError('unknown dimension')


def dummy_image():
    x = np.linspace(-1.5, 1.5, 1920)
    y = np.linspace(-1.5, 1.5, 1200)
    xv, yv = np.meshgrid(x, y)
    signal = np.exp(-(xv**2 / 0.45**2 + yv**2 / 0.15**2))
    noise = 0.3 * np.random.random(size=signal.shape)
    return signal + noise


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


roiKeyFrames = {
    0: [dict(kind='ArcROI', name='arc1', center=(0, 500),
             innerRadius=500, outerRadius=510, startAngle=-1, endAngle=1),
        dict(kind='RectangleROI', name='rect', origin=(0, 0), size=(50, 900))],
    7: [dict(kind='ArcROI', name='arc1', center=(100, 500),
             innerRadius=500, outerRadius=550, startAngle=-1, endAngle=1),
        dict(kind='RectangleROI', name='rect', origin=(200, 100),
             size=(50, 900))],
    }
roiWidget = RoiWidgetWithKeyFrames(None, plot)
roiWidget.setKeyFrames(roiKeyFrames)
roiWidget.dataToCount = stack if ndim == 3 else image
dock = qt.QDockWidget('Image ROI')
dock.setWidget(roiWidget)
dock.visibilityChanged.connect(roiDockVisibilityChanged)
plot.addDockWidget(qt.Qt.RightDockWidgetArea, dock)

# Show the widget and start the application
plot.show()
result = app.exec()
app.deleteLater()
sys.exit(result)
