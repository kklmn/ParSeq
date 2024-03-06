# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "01 Jan 2019"
# !!! SEE CODERULES.TXT !!!

# import os
# os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"  # to work with external links
# import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"

from silx.gui import qt, icons

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.fileTreeModelView import FileTreeView
# from silx.gui.hdf5.Hdf5TreeView import Hdf5TreeView


def test1():
    import h5py
    fname = r"c:\_MaxIV\Balder data\20240213-Mo-XES\scan-29270_albaem_2d_01.h5"
    entry = "entry/instrument/albaem"
    with h5py.File(fname, "r") as f:
        print(f.get(entry))
        print(f.get(entry, getclass=True))
        print(f.get(entry, getclass=True, getlink=True))

    fname = r"c:\_MaxIV\Balder data\20240213-Mo-XES\20240213.h5 "
    entry = "entry29270/instrument"
    with h5py.File(fname, "r") as f:
        print(f.get(entry))
        print(f.get(entry, getclass=True))
        print(f.get(entry, getclass=True, getlink=True))

    fname = r"c:\_MaxIV\Balder data\20240213-Mo-XES\20240213.h5 "
    entry = "entry29270/instrument/albaem_2d_01"
    with h5py.File(fname, "r") as f:
        print(f.get(entry))
        print(f.get(entry, getclass=True))
        print(f.get(entry, getclass=True, getlink=True))


def test2():
    def gotoLastData():
        view.gotoWhenReady(path)

    app = qt.QApplication(sys.argv)

    # path = 'C:/ParSeq/parseq_XES_scan/data'
    # path = 'C:/ParSeq/parseq_XES_scan/data/20201112.h5'
    # path = 'silx:C:/ParSeq/parseq_XES_scan/data/20201112.h5::/entry10170'
    # path = 'silx:C:/ParSeq/parseq_XES_scan/data/20201112.h5::/entry10170/measurement'
    # path = 'c:/_MaxIV/Balder data/20240213-Mo-XES/20240213.h5'
    path = 'silx:data/hdf5/20240213s.h5::/entry29270/instrument'

    view = FileTreeView()
    # view = Hdf5TreeView()
    view.setMinimumSize(qt.QSize(700, 600))
    view.header().resizeSection(0, 320)
    view.setWindowTitle("Merged Tree Model: QFileSystemModel + h5Model")
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
    layout = qt.QHBoxLayout()
    # layout.addWidget(gotoButton)
    layout.addWidget(view)
    widget.setLayout(layout)

    widget.show()
    app.exec_()
    app.deleteLater()


if __name__ == '__main__':
    # test1()
    test2()
