# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys; sys.path.append('../..')  # analysis:ignore
from collections import OrderedDict
import parseq.core.nodes as cno


def _test():
    class Node1(cno.Node):
        name = 'currents'
        arrays = OrderedDict()
        arrays['e'] = dict(
            qLabel='E', qUnit='eV', raw='eraw', role='x', plotLabel=r'$E$')
        arrays['i0'] = dict(
            qLabel='I0', qUnit='counts', raw='i0raw', role='yleft',
            plotLabel=r'$I_0$', plotParams=dict(linewidth=3))
        arrays['i1'] = dict(
            qLabel='I1', qUnit='counts', raw='i1raw', role='yright',
            plotLabel=r'$I_1$',
            plotParams=dict(
                linewidth=1, linestyle='--', symbol='d', symbolsize=5))

    node = Node1()
    print(node.plotXArray, node.plotYArrays)
    print(node.get_prop('e', 'role'))
    print(node.get_arrays_prop('qLabel'))
    print(node.get_arrays_prop('qLabel', role='x')[0])
    print(node.get_arrays_prop('qLabel', role='y'))


if __name__ == '__main__':
    _test()
