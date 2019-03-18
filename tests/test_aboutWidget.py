# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import os, sys; sys.path.append('..')  # analysis:ignore
from parseq.gui.aboutDialog import AboutDialog
import parseq.apps.dummy as myapp
#import parseq.apps.XASviewer as myapp


def test():
    myapp.make_pipeline(True)

    app = qt.QApplication(sys.argv)
    mainWindow = AboutDialog(None)
    mainWindow.show()
    app.exec_()


if __name__ == '__main__':
    test()
