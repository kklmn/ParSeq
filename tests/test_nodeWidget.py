# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Sep 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import os, sys; sys.path.append('..')  # analysis:ignore
import parseq.core.singletons as csi
from parseq.gui.nodeWidget import NodeWidget
import parseq.apps.dummy as myapp


def test():
    myapp.make_pipeline(withGUI=True)

    app = qt.QApplication(sys.argv)
    node = list(csi.nodes.values())[0]
    nodeWidget = NodeWidget(node)

    # load test data
    myapp.load_test_data()
    nodeWidget.tree.dataChanged()
    # select the 1st item (it is a group)
    nodeWidget.tree.setCurrentIndex(csi.model.index(0))

    nodeWidget.show()
    app.exec_()


if __name__ == '__main__':
    test()
