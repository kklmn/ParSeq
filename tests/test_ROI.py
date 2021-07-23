#!/usr/bin/env python

import sys
import numpy

from silx.gui import qt
from silx.gui.plot import Plot2D, StackView
from silx.gui.plot.tools.roi import RegionOfInterestManager
from silx.gui.plot.items.roi import RectangleROI
# from silx.gui.plot.actions import control as control_actions

def dummy_image():
    """Create a dummy image"""
    x = numpy.linspace(-1.5, 1.5, 1024)
    xv, yv = numpy.meshgrid(x, x)
    signal = numpy.exp(- (xv ** 2 / 0.15 ** 2 + yv ** 2 / 0.25 ** 2))
    # add noise
    signal += 0.3 * numpy.random.random(size=signal.shape)
    return signal

app = qt.QApplication([])  # Start QApplication

# Create the plot widget and add an image

plot = Plot2D()
roiManager = RegionOfInterestManager(plot)

# plot = StackView()
# roiManager = RegionOfInterestManager(plot._plot)

roiManager.setColor('pink')  # Set the color of ROI

# Add a rectangular region of interest
roi = RectangleROI()
roi.setGeometry(origin=(500, 500), size=(200, 200))
roi.setEditable(True)
roi.setVisible(True)
roi.setName('Initial ROI')
roiManager.addRoi(roi)

# Show the widget and start the application
plot.addImage(dummy_image())
plot.show()
result = app.exec_()
app.deleteLater()
sys.exit(result)
