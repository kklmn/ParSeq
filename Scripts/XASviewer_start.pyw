# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "04 Mar 2019"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import os, sys; sys.path.append('..')  # analysis:ignore
# import parseq.core.singletons as csi
from parseq.gui.mainWindow import MainWindowParSeq
import parseq.apps.XASviewer as myapp


def run():
    myapp.make_pipeline(withGUI=True)

    app = qt.QApplication(sys.argv)
    mainWindow = MainWindowParSeq()
    mainWindow.dataChanged()
    mainWindow.show()
#    mainWindow.docks[1].raise_()
    app.exec_()


if __name__ == '__main__':
    run()
