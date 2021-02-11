# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "06 Feb 2021"
# !!! SEE CODERULES.TXT !!!

"""
Test data for the dummy app.
"""
import os.path as osp
from os.path import dirname as up
import parseq.core.singletons as csi


def load_test_data():
    dirname = up(up(up(up(osp.abspath(__file__)))))

    scanName = ("silx:" + osp.join(dirname, 'data', '20201112.h5') +
                "::/entry10170")
    dataName = ("silx:" +
                osp.join(dirname, 'data', 'NbO2_Kb13_76_data_000001.h5') +
                "::/entry/data/data")
    h5Format = [
        'measurement/xtal2_pit',
        'd["measurement/albaem01_ch1"] + d["measurement/albaem01_ch2"]',
        dataName]

    rootItem = csi.dataRootItem
    dataFormat = dict(dataSource=h5Format)
    rootItem.insert_data(scanName, dataFormat=dataFormat)
