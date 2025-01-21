# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "19 Jan 2025"
# !!! SEE CODERULES.TXT !!!

from functools import partial
import numpy as np
from scipy import ndimage

from silx.gui import qt

GLITCHCOLOR = '#0000ff33'
BIG = 1e37
MAXNGLITCHES = 50


class GlitchPanel(qt.QGroupBox):
    propChanged = qt.pyqtSignal(dict)
    propCleared = qt.pyqtSignal()

    peakSettings = dict(sign=-1, prominence=0.3, width=0, rel_height=0.75)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('mark glitches')
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self.glitchPanelToggled)

        layoutG = qt.QGridLayout()
        layoutG.setContentsMargins(2, 2, 0, 0)

        prominenceLabel = qt.QLabel('prominence')
        tt = 'a lower value detects weaker glitches'
        prominenceLabel.setToolTip(tt)
        layoutG.addWidget(prominenceLabel, 0, 0)
        self.prominenceValue = qt.QDoubleSpinBox()
        self.prominenceValue.setMinimum(0)
        self.prominenceValue.setMaximum(1)
        self.prominenceValue.setSingleStep(0.01)
        self.prominenceValue.setDecimals(2)
        self.prominenceValue.setAccelerated(True)
        self.prominenceValue.setValue(self.peakSettings['prominence'])
        self.prominenceValue.valueChanged.connect(partial(
            self.setProp, 'prominence'))
        self.prominenceValue.setToolTip(tt)
        layoutG.addWidget(self.prominenceValue, 0, 1)

        # widthLabel = qt.QLabel('minimum width')
        # tt = 'narrower glitches are not detected'
        # widthLabel.setToolTip(tt)
        # layoutG.addWidget(widthLabel, 1, 0)
        # self.widthValue = qt.QSpinBox()
        # self.widthValue.setMinimum(0)
        # self.widthValue.setMaximum(100)
        # self.widthValue.setAccelerated(True)
        # self.widthValue.setValue(self.peakSettings['width'])
        # self.widthValue.valueChanged.connect(partial(self.setProp, 'width'))
        # self.withValue.setToolTip(tt)
        # layoutG.addWidget(self.widthValue, 1, 1)

        heightLabel = qt.QLabel('marking height')
        tt = 'relative height from peak to base\nwhere the glitch is marked'
        heightLabel.setToolTip(tt)
        layoutG.addWidget(heightLabel, 2, 0)
        self.heightValue = qt.QDoubleSpinBox()
        self.heightValue.setMinimum(0)
        self.heightValue.setMaximum(1)
        self.heightValue.setSingleStep(0.01)
        self.heightValue.setDecimals(2)
        self.heightValue.setAccelerated(True)
        self.heightValue.setValue(self.peakSettings['rel_height'])
        self.heightValue.valueChanged.connect(partial(
            self.setProp, 'rel_height'))
        self.heightValue.setToolTip(tt)
        layoutG.addWidget(self.heightValue, 2, 1)

        self.setLayout(layoutG)

    def readProps(self):
        self.peakSettings['prominence'] = self.prominenceValue.value()
        # self.peakSettings['width'] = self.widthValue.value()
        self.peakSettings['rel_height'] = self.heightValue.value()

    def setProp(self, prop, value):
        self.peakSettings[prop] = value
        self.propChanged.emit(self.peakSettings)

    def glitchPanelToggled(self, active):
        if active:
            self.readProps()
            self.propChanged.emit(self.peakSettings)
        else:
            self.propCleared.emit()


def clearGlitches(plot):
    for item in plot.getItems():
        if item.getName().startswith('glitch'):
            plot.removeItem(item)


def replotGlitches(plot, x, props):
    clearGlitches(plot)
    xsp = ndimage.spline_filter(x)
    for ip, (wl, wr) in enumerate(zip(props["left_ips"], props["right_ips"])):
        if ip >= MAXNGLITCHES:
            break
        ibar = np.array([wl, wr])
        ebar = ndimage.map_coordinates(xsp, [ibar], order=1, prefilter=True)
        lebar = list(ebar)
        plot.addShape(lebar+lebar[::-1], [BIG, BIG, -BIG, -BIG],
                      legend=f'glitch{ip}', shape='rectangle',
                      color=GLITCHCOLOR, fill=True)


def replotGlitchesConverted(plot, props):
    clearGlitches(plot)
    for ip, (wl, wr) in enumerate(zip(props["left_x"], props["right_x"])):
        if ip >= MAXNGLITCHES:
            break
        xbar = [wl, wr]
        plot.addShape(xbar+xbar[::-1], [BIG, BIG, -BIG, -BIG],
                      legend=f'glitch{ip}', shape='rectangle',
                      color=GLITCHCOLOR, fill=True)
