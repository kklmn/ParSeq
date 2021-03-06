# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.gui.plotOptions import LineProps
import parseq_XES_scan as myapp
import time


def test():
    myapp.make_pipeline(withGUI=True)
    myapp.load_test_data()

    csi.selectedItems[:] = []
    csi.selectedTopItems[:] = []
    group = csi.dataRootItem.get_groups()[0]
    items = group.get_items()
    csi.selectedItems.extend(items)
    csi.selectedTopItems.extend([group])

    app = qt.QApplication(sys.argv)
    dia = LineProps(None, list(csi.nodes.values())[-1])
    dia.show()
    app.exec_()

    if dia.result() == qt.QDialog.Accepted:
        lineProps = dia.setLineOptions()
        print(lineProps)
        time.sleep(3)


if __name__ == '__main__':
    test()
