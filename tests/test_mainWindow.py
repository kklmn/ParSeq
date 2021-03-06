# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
import parseq_XES_scan as myapp


def test(withGUI=True, withTestData=True):
    myapp.make_pipeline(withGUI)

    if withTestData:
        myapp.load_test_data()

    if withGUI:
        node0 = list(csi.nodes.values())[0]
        node0.fileNameFilters = ['*.fio', '*.h5', '*.dat']

        from silx.gui import qt
        from parseq.gui.mainWindow import MainWindowParSeq
        app = qt.QApplication(sys.argv)
        mainWindow = MainWindowParSeq()
        mainWindow.dataChanged()
        mainWindow.show()

        node0.widget.tree.setFocus()  # important
        node0.widget.tree.setCurrentIndex(csi.model.index(0))

        from modeltest import ModelTest
        node0.widget.files.ModelTest = ModelTest

        app.exec_()
    else:
        import matplotlib.pyplot as plt
        for data in csi.dataRootItem.get_items():
            plt.plot(data.r, data.ft)
        plt.show()


if __name__ == '__main__':
    test(withGUI=True, withTestData=True)
    # test(withGUI=True, withTestData=False)
    # test(withGUI=False, withTestData=True)
