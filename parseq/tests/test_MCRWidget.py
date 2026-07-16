# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 Jul 2026"

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.gui.mainWindow import MainWindowParSeq


def test():
    import parseq_XAS as myapp

    csi.plotBackend = 'mpl'
    csi.DEBUG_LEVEL = 100

    myapp.make_pipeline(withGUI=True)
    # 1: dataFName = 'Cu30_1_0.txt.gz', dLabel = 'wide-Cu2O+CuO'
    # 2: dataFName = 'Cu30_0.7_0.3.txt.gz', dLabel = 'narrow-Cu2O+CuO'
    # 3: dataFName = 'NiCo.txt.gz', dLabel = 'NiCo'
    # 4: dataFName = 'CoNi.txt.gz', dLabel = 'CoNi'
    # 5: dataFName = 'MES-Ni.txt.gz', dLabel = 'Ni-mono'
    # 6: dataFName = 'MES-Co.txt.gz', dLabel = 'Co-mono'
    # 7: dataFName = 'ceria.dat.gz', dLabel = 'ceria'
    myapp.load_test_data_MCR(5)  # see the case description above

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
