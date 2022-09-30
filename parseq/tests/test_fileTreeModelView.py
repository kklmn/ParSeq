# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "01 Jan 2019"
# !!! SEE CODERULES.TXT !!!

# import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"

from silx.gui import qt, icons
import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.fileTreeModelView import FileTreeView


def test():
    def gotoLastData():
        view.gotoWhenReady(path)

    app = qt.QApplication(sys.argv)

    # view = FileTreeView(rootPath=r'../..')
    view = FileTreeView(rootPath='')

    view.setMinimumSize(qt.QSize(700, 600))
    view.header().resizeSection(0, 320)
    view.setWindowTitle("Merged Tree Model: QFileSystemModel + h5Model")

    # path = 'C:/ParSeq/parseq_XES_scan/data'
    # path = 'C:/ParSeq/parseq_XES_scan/data/20201112.h5'
    # path = 'silx:C:/ParSeq/parseq_XES_scan/data/20201112.h5::/entry10170'
    path = 'silx:C:/ParSeq/parseq_XES_scan/data/20201112.h5::/entry10170/measurement'
    view.gotoWhenReady(path)

    # if "qt5" in qt.BINDING.lower():
    #     from modeltest import ModelTest
    #     ModelTest(view.model(), view)

    gotoButton = qt.QToolButton()
    gotoButton.setFixedSize(24, 24)
    gotoButton.setIcon(icons.getQIcon('last'))
    gotoButton.setToolTip("Go to the latest loaded data")
    gotoButton.clicked.connect(gotoLastData)

    # Main widget
    widget = qt.QWidget()
    layout = qt.QVBoxLayout()
    layout.addWidget(gotoButton)
    layout.addWidget(view)
    widget.setLayout(layout)

    widget.show()
    app.exec_()


if __name__ == '__main__':
    test()
