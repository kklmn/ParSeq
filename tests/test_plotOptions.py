# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Aug 2022"
# !!! SEE CODERULES.TXT !!!

import time
from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.gui.plotOptions import LineProps

from parseq.tests import testapp


def test():
    testapp.make_pipeline(withGUI=True)
    testapp.load_test_data()

    # csi.selectedItems[:] = []
    # csi.selectedTopItems[:] = []
    # groups = csi.dataRootItem.get_groups()
    # if len(groups) > 0:
    #     group = csi.dataRootItem.get_groups()[0]
    #     items = group.get_items()
    #     csi.selectedItems.extend(items)
    #     csi.selectedTopItems.extend([group])

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
