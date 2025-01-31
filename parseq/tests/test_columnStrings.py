# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "27 Jan 2018"
"""
Test expression evaluation where the expression operates arrays defined as
d["NNN"], where d is a local dictionary with the appropriate keys; the keys can
also be integers.
"""
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
    _locals = dict(d=d, np=np)
    for k in keys:
        d[k] = np.ones(3)
        if isColumn:
            if "col" not in k.lower():
                k_ = int(k)
                d[k_] = d[k]
        _locals[k] = k
    print(d, colStr)
    # keyword `locals` is an error in Py<3.13,
    # using just `_locals` (without globals()) does not work
    res = eval(colStr, {}, _locals)
    print(res, type(res))


if __name__ == '__main__':
    test('d["path1"] + d["path2"]', isColumn=False)
    test("d['path1'] + d['path2']", isColumn=False)
    test(' + '.join(['d["path{0}"]'.format(i) for i in range(1, 3)]),
         isColumn=False)

    test('path1', isColumn=False)

    test('d["col1"] + d["col2"]')
    test('d[col1] + d[col2]')
    test('d[1] + d[2]')
    test(' + '.join(['d["col{0}"]'.format(i) for i in range(1, 3)]))

    test('d[1]')
    test('1')
    test('col1')
    test('Col1')
