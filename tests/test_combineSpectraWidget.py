# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Aug 2022"
# !!! SEE CODERULES.TXT !!!

import sys; sys.path.append('../..')  # analysis:ignore
from silx.gui import qt

from parseq.gui.combineSpectra import CombineSpectraWidget
from parseq.tests import testapp


def test():
    testapp.make_pipeline(withGUI=True)
    testapp.load_test_data()

    app = qt.QApplication(sys.argv)
    mainWindow = CombineSpectraWidget()
    mainWindow.setWindowTitle("Combine")
    mainWindow.show()
    app.exec_()


if __name__ == '__main__':
    test()
