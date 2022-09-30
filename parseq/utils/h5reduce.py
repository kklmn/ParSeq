# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "13 Jun 2021"
# !!! SEE CODERULES.TXT !!!

import h5py


def print_entries(fname):
    with h5py.File(fname, "a") as f:
        print(list(f.keys()))


def del_entry(fname, entry):
    with h5py.File(fname,  "a") as f:
        del f[entry]


def del_all_except(fname, keep):
    with h5py.File(fname, "a") as f:
        for entry in list(f.keys()):
            if entry in keep:
                continue
            del f[entry]


def repack(fname, newfname):
    with h5py.File(newfname, "w") as fd:
        with h5py.File(fname, "r") as fs:
            for entry in list(fs.keys()):
                fs.copy(entry, fd)


if __name__ == '__main__':
    # del_all_except(r'c:\ParSeq\parseq_XES_scan\data\20201112.h5',
    #                ['entry10170', 'entry10190', 'entry10191'])

    # print_entries(r'c:\ParSeq\parseq_XES_scan\data\20201112.h5')

    repack(r'c:\ParSeq\parseq_XES_scan\data\20201112.h5',
           r'c:\ParSeq\parseq_XES_scan\data\20201112_small_n.h5')
