# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import os, sys; sys.path.append('..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.gui.mainWindow import MainWindowParSeq
import parseq.apps.dummy as myapp


def run():
    myapp.make_pipeline(withGUI=True)

    app = qt.QApplication(sys.argv)
    mainWindow = MainWindowParSeq()
    mainWindow.dataChanged()
    mainWindow.show()
    # select the 1st item (it is a group)
    node0 = list(csi.nodes.values())[0]
    node0.nodeWidget.tree.setCurrentIndex(csi.model.index(0))
    app.exec_()


if __name__ == '__main__':
    run()
