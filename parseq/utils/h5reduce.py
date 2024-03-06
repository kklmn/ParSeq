# -*- coding: utf-8 -*-
"""
How to remove unwanted entries from an hdf5 file
------------------------------------------------

1. Copy the file to another one.
2. Run `del_all_except()`. This will remove all unwanted enties but will keep
   the file size. You may check that the legal entries by `print_entries()`.
3. Repack the file into another hdf5 file by `repack()`.
"""

__author__ = "Konstantin Klementiev"
__date__ = "13 Jun 2021"
# !!! SEE CODERULES.TXT !!!

import os
os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"  # to work with external links
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
    # delete unwanted entries
    del_all_except(r'c:\ParSeq\parseq_XAS\data\HERFD\20230318s.h5',
                   ['entry24212', 'entry24213'])

    # and print the keys
    print_entries(r'c:\ParSeq\parseq_XAS\data\HERFD\20230318s.h5')

    # copy to another h5 file
    repack(r'c:\ParSeq\parseq_XAS\data\HERFD\20230318s.h5 ',
           r'c:\ParSeq\parseq_XAS\data\HERFD\20230318ss.h5')

    # and print the keys of the repacked file
    print_entries(r'c:\ParSeq\parseq_XAS\data\HERFD\20230318ss.h5')

    print("Done")
