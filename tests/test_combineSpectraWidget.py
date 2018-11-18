# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import os, sys; sys.path.append('..')  # analysis:ignore
from parseq.gui.combineSpectraWidget import CombineSpectraWidget
import parseq.apps.dummy as myapp


def test():
    myapp.make_pipeline(withGUI=True)
    myapp.load_test_data()

    app = qt.QApplication(sys.argv)
    mainWindow = CombineSpectraWidget()
    mainWindow.setWindowTitle("Combine")
    mainWindow.show()
    app.exec_()


if __name__ == '__main__':
    test()
