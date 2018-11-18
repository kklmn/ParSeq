# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

"""
Test data for the dummy app.
"""
import os.path as osp
from os.path import dirname as up
import parseq.core.singletons as csi


def load_test_data():
    dirname = up(up(up(up(osp.abspath(__file__)))))
    fNames = [[osp.join(dirname, 'data', 'Cu_lnt1.fio'), [3, 5, 6]],  # fname, data columns
              [osp.join(dirname, 'data', 'Cu_lnt2.fio'), [3, 5, 6]],
              [osp.join(dirname, 'data', 'Cu_rt1.fio'), [3, 5, 6]],
              [osp.join(dirname, 'data', 'Cu_rt2.fio'), [3, 5, 6]],
              [osp.join(dirname, 'data', 'Cu2O_lnt1.fio'), [0, 5, 6]],
              [osp.join(dirname, 'data', 'Cu2O_lnt2.fio'), [0, 5, 6]],
              [osp.join(dirname, 'data', 'CuO_lnt.fio'), [0, 5, 6]]]

    rootItem = csi.dataRootItem

    group0 = rootItem.insert_item('metal')
    dataFormat = dict(usecols=fNames[0][1], lastSkipRowContains='Col ')
#    dataFormat['xFactor'] = 1e-3
    data = [fn[0] for fn in fNames[:4]]
    group0.insert_data(data, dataFormat=dataFormat)

    group1, = rootItem.insert_data('oxides')  # another way to insert, res=list
    dataFormat = dict(usecols=fNames[4][1], lastSkipRowContains='Col ')
    data = [fn[0] for fn in fNames[4:7]]
    group1.insert_data(data, dataFormat=dataFormat)
