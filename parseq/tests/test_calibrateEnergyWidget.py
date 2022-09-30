# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Aug 2022"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.calibrateEnergy import CalibrateEnergyWidget
from parseq.tests import testapp


def test():
    testapp.make_pipeline(withGUI=True)
    testapp.load_test_data()

    app = qt.QApplication(sys.argv)
    dataCollection = dict(base=['aa', 'bb'], energy=[8000.5, 9000.1],
                          DCM=['Si111', 'Si111'], FWHM=[0.1, 0.2])
    # dataCollection = OrderedDict()
    mainWindow = CalibrateEnergyWidget(dataCollection=dataCollection)
    mainWindow.resize(0, 0)

    mainWindow.setWindowTitle("Calibrate energy")
    mainWindow.show()
    app.exec_()


if __name__ == '__main__':
    test()
