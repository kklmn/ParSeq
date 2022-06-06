# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Jan 2018"
# !!! SEE CODERULES.TXT !!!

import numpy as np
import re
#import os, sys; sys.path.append('..')  # analysis:ignore
#from parseq.gui.combineSpectra import CombineSpectraWidget
#import parseq.apps.dummy as myapp


def test(colStr, isColumn=True):
    keys = re.findall(r'\[(.*?)\]', colStr)
    if len(keys) == 0:
        keys = colStr,
        colStr = 'd["{0}"]'.format(colStr)
    else:
        # remove outer quotes:
        keys = [k[1:-1] if k.startswith(('"', "'")) else k for k in keys]
    d = {}
    for k in keys:
        d[k] = np.ones(3)
        if isColumn:
            if "col" not in k.lower():
                k_ = int(k)
                d[k_] = d[k]
        locals()[k] = k
    print(d, colStr)
    res = eval(colStr)
    print(res, type(res))


if __name__ == '__main__':
    test('d["path1"] + d["path2"]', isColumn=False)
    test("d['path1'] + d['path2']", isColumn=False)
    test(' + '.join(['d["path{0}"]'.format(i) for i in range(1, 3)]), isColumn=False)

    test('path1', isColumn=False)

    test('d["col1"] + d["col2"]')
    test('d[col1] + d[col2]')
    test('d[1] + d[2]')
    test(' + '.join(['d["col{0}"]'.format(i) for i in range(1, 3)]))

    test('d[1]')
    test('1')
    test('col1')
    test('Col1')
