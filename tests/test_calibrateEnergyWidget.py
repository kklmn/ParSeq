# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "24 Mar 2021"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.calibrateEnergyWidget import CalibrateEnergyWidget
import parseq_XES_scan as myapp


def test():
    myapp.make_pipeline(withGUI=True)
    myapp.load_test_data()

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
