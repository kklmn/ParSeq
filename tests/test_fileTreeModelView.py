# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "01 Jan 2019"
# !!! SEE CODERULES.TXT !!!

import sys
from silx.gui import qt
import os, sys; sys.path.append('..')  # analysis:ignore
from parseq.gui.fileTreeModelView import FileTreeView


def test():
    app = qt.QApplication(sys.argv)
    dirname = r'..'
    view = FileTreeView(roothPath=dirname)
    view.setMinimumSize(qt.QSize(700, 600))
    view.header().resizeSection(0, 320)
    ind = view.model().indexFileName('../data/CuO_lnt.fio')
    view.setCurrentIndex(ind)

#    if "qt5" in qt.BINDING.lower():
#        from modeltest import ModelTest
#        ModelTest(view.model(), view)

    view.setWindowTitle("Merged Tree Model: QFileSystemModel + h5Model")
    view.setSortingEnabled(True)
    view.show()

    app.exec_()


if __name__ == '__main__':
    test()
