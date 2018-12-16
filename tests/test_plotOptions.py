# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import os, sys; sys.path.append('..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.gui.plotOptions import LineProps
import parseq.apps.dummy as myapp
import time


def test():
    myapp.make_pipeline(withGUI=True)
    myapp.load_test_data()

    app = qt.QApplication(sys.argv)
    dia = LineProps(None, csi.nodes['currents'])
    dia.setWindowTitle("Line properties")
    dia.setLineProperties(0, color='red', symbol='', style='-', width=2)
    dia.setLineProperties(
        1, color='blue', symbol='o', symbolsize=5, style='-', width=1)
    dia.show()
    app.exec_()

    if dia.result() == qt.QDialog.Accepted:
        lineProps = dia.getLineProperties()
        print(lineProps)
        time.sleep(3)


if __name__ == '__main__':
    test()
