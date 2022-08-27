# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Aug 2022"
# !!! SEE CODERULES.TXT !!!

# import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"

from silx.gui import qt

import os, sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.fileDialogs import SaveProjectDlg
from parseq.tests import testapp


def showRes(res):
    print(res)


def test():
    testapp.make_pipeline(withGUI=True)
    app = qt.QApplication(sys.argv)

    dlg = SaveProjectDlg()
    dlg.ready.connect(showRes)
    dlg.open()

    app.exec_()


if __name__ == '__main__':
    test()
