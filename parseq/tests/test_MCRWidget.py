# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "9 Jun 2026"

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.gui.mainWindow import MainWindowParSeq


def test():
    import parseq_XAS as myapp

    myapp.make_pipeline(withGUI=True)
    myapp.load_test_data_MCR(3)

    qtArgs = ["--disable-gpu"]  # has to be set for morph-browser users
    app = qt.QApplication(qtArgs)
    mainWindow = MainWindowParSeq(tabPos=qt.QTabWidget.North)
    node = csi.nodes['µd']
    node.widget.splitterData.setSizes([1, 1])
    node.widget.combiner.mcrTasker.maxIteration = 1500
    mainWindow.show()

    app.exec_()


if __name__ == '__main__':
    test()
