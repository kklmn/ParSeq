# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "24 Oct 2022"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.dataRebin import DataRebinWidget
from parseq.core import singletons as csi


class TestWidget(qt.QWidget):
    def __init__(self, parent=None, regions=()):
        super().__init__(parent)
        layout = qt.QVBoxLayout()
        self.rebinWidget = DataRebinWidget(self, regions)
        self.rebinWidget.regionsChanged.connect(self.acceptRebinRegions)
        layout.addWidget(self.rebinWidget)
        layout.addStretch()
        self.setLayout(layout)

    def acceptRebinRegions(self):
        regions = self.rebinWidget.getRegions()
        print('new regions', regions)


def test():
    app = qt.QApplication(sys.argv)
    captions = 'pre-edge', 'edge', 'post-edge', 'EXAFS'
    deltas = (['dE', 1.0, 0.1, 10, 0.1],  # label, value, min, max, step
              ['dE', 0.2, 0.02, 2, 0.02],
              ['dE', 0.4, 0.04, 4, 0.02],
              ['dk', 0.025, 0.005, 0.1, 0.001])
    splitters = (['E0+', -20, -200, 0, 1],  # label, value, min, max, step
                 ['E0+', 50., 0, 200, 2],
                 ['kmin', 2.1, 0, 5, 0.1],
                 ['kmax', 'inf', 0, 'inf', 0.1])
    # deltas = (['dE', 1.0, 0.1, 10, 0.1],  # label, value, min, max, step
    #           ['dE', 0.2, 0.02, 2, 0.02],
    #           ['dE', 0.4, 0.04, 4, 0.02],
    #           ['dE', 0.5, 0.05, 5, 0.02])
    # splitters = (['E0+', -20, -200, 0, 1],  # label, value, min, max, step
    #              ['E0+', 50., 0, 200, 2],
    #              ['E0+', 100, 20, 500, 2])
    mainWindow = TestWidget(regions=(captions, deltas, splitters))
    mainWindow.setWindowTitle("Absorption edge regions")
    csi.screenFactor = app.desktop().logicalDpiX() / 120.

    regions = dict(deltas=(1., 0.2, 0.5, 0.025),
                   splitters=(-15, 15, 2.5, 'inf'))
    mainWindow.rebinWidget.setRegions(regions)
    mainWindow.rebinWidget.setBinNumbers(0, [100, 200, 300, 400])
    mainWindow.rebinWidget.setBinNumbers(1, [10, 20, 30, 40])

    mainWindow.show()

    print(mainWindow.rebinWidget.getRegions())

    app.exec_()


if __name__ == '__main__':
    test()
