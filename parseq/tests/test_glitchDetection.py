# coding: utf-8
from functools import partial
import numpy as np

from silx.gui import qt
from silx.gui.plot import Plot1D

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.utils.glitch as ug
ug.MAXNGLITCHES = 20
from parseq.gui.glitches import GlitchPanel, clearGlitches, replotGlitches

fpath = "data/cur-Cu-foil_EXAFS_23070.txt.gz"
data = np.loadtxt(fpath, skiprows=1)


class GlitchSelectionWidget(qt.QWidget):
    def __init__(self, parent=None, plot=None):
        super().__init__(parent)
        self.plot = plot
        layout = qt.QVBoxLayout()
        self.glitchPanel = GlitchPanel(self)
        self.glitchPanel.propChanged.connect(self.updateGlitches)
        self.glitchPanel.propCleared.connect(partial(clearGlitches, self.plot))
        layout.addWidget(self.glitchPanel)
        layout.addStretch()
        self.setLayout(layout)

    def updateGlitches(self, peakSettings):
        e, i0 = data[:, 0], data[:, 1]
        peaks, peakProps = ug.calc_glitches(peakSettings, e, i0)
        replotGlitches(self.plot, e, peakProps)


def main():
    app = qt.QApplication([])

    plot = Plot1D()
    plot.setGraphTitle(fpath)
    plot.setGraphXLabel(label='energy (eV)')
    plot.setGraphYLabel(label='I0 (µA)')
    e, i0 = data[:, 0], data[:, 1]
    plot.addCurve(e, i0, legend='i0')

    dock = qt.QDockWidget('Glitches')
    rightDockWidget = GlitchSelectionWidget(dock, plot)
    dock.setWidget(rightDockWidget)
    plot.addDockWidget(qt.Qt.RightDockWidgetArea, dock)

    plot.show()
    result = app.exec()
    app.deleteLater()
    sys.exit(result)


if __name__ == '__main__':
    main()
