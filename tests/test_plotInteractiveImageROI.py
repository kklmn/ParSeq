#!/usr/bin/env python
# coding: utf-8

import numpy as np

from silx.gui import qt
from silx.gui.plot.items.roi import ArcROI, RectangleROI

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.roi import RoiWidget

ndim = 3
if ndim == 2:
    from silx.gui.plot import Plot2D
elif ndim == 3:
    from silx.gui.plot import StackView
else:
    raise ValueError('unknown dimension')


def dummy_image():
    x = np.linspace(-1.5, 1.5, 1024)
    xv, yv = np.meshgrid(x, x)
    signal = np.exp(-(xv**2 / 0.15**2 + yv**2 / 0.25**2))
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
    plot.setStack(stack)

plot.setKeepDataAspectRatio(False)


# Add a rectangular region of interest
roi1 = ArcROI()
roi1.setGeometry(center=(0, 500), innerRadius=500, outerRadius=510,
                 startAngle=-1, endAngle=1)
# print(str(roi1))
roi2 = RectangleROI()
roi2.setGeometry(center=(100, 500), size=(50, 900))
# print(str(roi2))


def roiDockVisibilityChanged(visible):
    """Handle change of visibility of the roi dock widget

    If dock becomes hidden, ROI interaction is stopped.
    """
    if not visible:
        roiWidget.roiManager.stop()


roiWidget = RoiWidget(None, plot)
roiWidget.roiManager.addRoi(roi1)
roiWidget.roiManager.addRoi(roi2)
dock = qt.QDockWidget('Image ROI')
dock.setWidget(roiWidget)
dock.visibilityChanged.connect(roiDockVisibilityChanged)
plot.addDockWidget(qt.Qt.RightDockWidgetArea, dock)

# Show the widget and start the application
plot.show()
result = app.exec()
app.deleteLater()
sys.exit(result)
