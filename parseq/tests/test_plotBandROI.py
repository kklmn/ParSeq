#!/usr/bin/env python
# coding: utf-8

from functools import partial
import numpy as np

from silx.gui import qt
from silx.gui.plot import ImageView, PlotWindow

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.roi import RoiWidget


class DataProxy(object):
    """An empty object to attach fields to it. With a simple instance of
    object() this is impossible but doable with an empty class."""

    def __repr__(self):
        return "DataProxy object for '{0}'".format(self.alias)


def makeDummyData():
    nx, ny = 1920, 1200
    yRange = -1, 2

    data = DataProxy()
    data.alias = 'dummy data'
    data.x = np.arange(nx)
    data.y = np.linspace(*yRange, ny)
    xv, yv = np.meshgrid(data.x, data.y)
    # print('x', xv.shape, 'y', yv.shape)
    signal = np.exp(-((xv-nx/3)**2/(nx*0.2)**2 + yv**2/0.15**2))
    signal += 0.5*np.exp(-((xv-2*nx/3)**2/(nx*0.2)**2 + (yv-1)**2/0.15**2))
    noise = 0.7 * np.random.random(size=signal.shape)
    data.xes2D = (signal + noise) * 100
    # print('2D', data.xes2D.shape)
    data.xes1D_left = np.zeros(ny)
    # data.xes1D_bottom = np.zeros(nx)
    return data


def line(xs, ys):
    try:
        k = (ys[1] - ys[0]) / (xs[1] - xs[0])
    except ZeroDivisionError:
        return np.inf, 0.
    b = ys[1] - k*xs[1]
    return k, b


def dockVisibilityChanged(roiWidget, visible):
    """Handle change of visibility of the roi dock widget

    If dock becomes hidden, ROI interaction is stopped.
    """
    if not visible:
        roiWidget.roiManager.stop()


def replot1D(data, roiWidget, plot1D, useFractionalPixels=True):
    roi = roiWidget.getCurrentRoi()
    try:
        x1, y1 = roi['begin']
        x2, y2 = roi['end']
        w = roi['width']
    except KeyError:
        return
    k, b = line((x1, x2), (y1, y2))

    dataCut = np.array(data.xes2D, dtype=np.float32)
    u, v = np.meshgrid(np.arange(data.xes2D.shape[1]), data.y)
    if len(data.y) > 1:
        dt = abs(data.y[-1]-data.y[0]) / (len(data.y)-1)
    else:
        dt = 1
    vm = v - k*u - b - w/2
    vp = v - k*u - b + w/2
    if useFractionalPixels and (dt > 0):
        dataCut[vm > dt] = 0
        dataCut[vp < -dt] = 0
        vmWherePartial = (vm > 0) & (vm < dt)
        dataCut[vmWherePartial] *= vm[vmWherePartial] / dt
        vpWherePartial = (vp > -dt) & (vp < 0)
        dataCut[vpWherePartial] *= -vp[vpWherePartial] / dt
    else:
        dataCut[vm > 0] = 0
        dataCut[vp < 0] = 0
    data.xes1D_left[:] = dataCut.sum(axis=1)

    data.xes1D_bottom = dataCut.sum(axis=0)
    data.x_bottom = k*np.arange(data.xes2D.shape[1]) + b

    # cutting of the incomplete ends:
    mline = k*np.arange(data.xes2D.shape[1]) + b
    gd = (mline - w/2 > data.y[0]) & (mline + w/2 < data.y[-1])
    data.xes1D_bottom = data.xes1D_bottom[gd]
    data.x_bottom = data.x_bottom[gd]

    # curve = plot1D.getCurve('xes1D')
    # curve.setData(data.y, data.xes)
    plot1D.clearCurves()
    plot1D.addCurve(data.y, data.xes1D_left, legend='xes1D-left')
    plot1D.addCurve(data.x_bottom, data.xes1D_bottom, legend='xes1D-bottom')


def test():
    app = qt.QApplication([])  # Start QApplication

    data = makeDummyData()
    plot2D = ImageView()
    plot2D.getXAxis().setLabel('meridional pixel')
    plot2D.getYAxis().setLabel('x3pit')
    plot2D.getDefaultColormap().setName('viridis')
    x0, xScale = data.x.min(), (data.x.max()-data.x.min()) / len(data.x)
    y0, yScale = data.y.min(), (data.y.max()-data.y.min()) / len(data.y)
    plot2D.addImage(data.xes2D, origin=(x0, y0), scale=(xScale, yScale))
    plot2D.setKeepDataAspectRatio(False)

    roiDict = dict(kind='BandROI', name='θ-2θ band', use=True,
                   begin=(500, -0.5), end=(1250, 1.5), width=0.6)
    roiWidget = RoiWidget(None, plot2D, ['BandROI'])

    roiWidget.setRois(roiDict)
    roiWidget.dataToCount = data.xes2D
    roiWidget.acceptButton.hide()

    dock = qt.QDockWidget('Image ROI')
    dock.setWidget(roiWidget)
    dock.visibilityChanged.connect(partial(dockVisibilityChanged, roiWidget))
    plot2D.addDockWidget(qt.Qt.RightDockWidgetArea, dock)

    plot1D = PlotWindow()
    plot1D.getXAxis().setLabel('x3pit')
    plot1D.getYAxis().setLabel('counts')

    roiWidget.roiManager.sigRoiChanged.connect(partial(
        replot1D, data, roiWidget, plot1D))

    # Show the widget and start the application
    plot2D.show()
    plot1D.show()
    roiWidget.updateCounts()
    replot1D(data, roiWidget, plot1D)

    result = app.exec()
    app.deleteLater()
    sys.exit(result)


if __name__ == '__main__':
    test()
