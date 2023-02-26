# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "10 Nov 2022"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

import sys; sys.path.append('../..')  # analysis:ignore
from parseq.gui.gcommons import StateButtons


def test():
    app = qt.QApplication(sys.argv)
    sb = StateButtons(None, 'caption', (-4, -3, 0, 1), (-3, 0), 0)
    sb.statesActive.connect(printStates)
    printStates(sb.getActive())
    sb.show()
    app.exec_()


def printStates(states):
    print(states)


if __name__ == '__main__':
    test()
