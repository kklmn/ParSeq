# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "22 Apr 2021"
# !!! SEE CODERULES.TXT !!!

# import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"

from silx.gui import qt

import os, sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.fileDialogs import SaveProjectDlg
import parseq_XES_scan as myapp


def showRes(res):
    print(res)


def test():
    myapp.make_pipeline(withGUI=True)
    app = qt.QApplication(sys.argv)

    dlg = SaveProjectDlg()
    dlg.ready.connect(showRes)
    dlg.open()

    app.exec_()


if __name__ == '__main__':
    test()
