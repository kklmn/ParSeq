# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import os, sys; sys.path.append('..')  # analysis:ignore
from collections import OrderedDict
import parseq.core.nodes as cno


def _test():
    class Node1(cno.Node):
        name = 'currents'
        arrays = OrderedDict()
        arrays['e'] = dict(
            qLabel='E', qUnit='eV', raw='eraw', plotRole='x', plotLabel=r'$E$')
        arrays['i0'] = dict(
            qLabel='I0', qUnit='counts', raw='i0raw', plotRole='yleft',
            plotLabel=r'$I_0$', plotParams=dict(linewidth=3))
        arrays['i1'] = dict(
            qLabel='I1', qUnit='counts', raw='i1raw', plotRole='yright',
            plotLabel=r'$I_1$',
            plotParams=dict(
                linewidth=1, linestyle='--', symbol='d', symbolsize=5))

    node = Node1()
    print(node.plotXArray, node.plotYArrays)
    print(node.getProp('e', 'plotRole'))
    print(node.getPropList('qLabel'))
    print(node.getPropList('qLabel', plotRole='x')[0])
    print(node.getPropList('qLabel', plotRole='y'))


if __name__ == '__main__':
    _test()
