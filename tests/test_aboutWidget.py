# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Aug 2022"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.aboutDialog import AboutDialog

from parseq.tests import testapp


def test():
    testapp.make_pipeline(withGUI=True)
    app = qt.QApplication(sys.argv)
    mainWindow = AboutDialog(None)
    mainWindow.show()
    app.exec_()


if __name__ == '__main__':
    test()
