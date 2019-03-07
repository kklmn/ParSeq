# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

MAX_HEADER_LINES = 256
MIME_TYPE_DATA = 'parseq-data-model-items'
MIME_TYPE_TEXT = 'text/uri-list'
MIME_TYPE_HDF5 = 'parseq-hdf5-model-items'


def common_substring(sa, sb):
    """finds the longest common substring from the beginning of sa and sb"""
    def _iter():
        for a, b in zip(sa, sb):
            if a == b:
                yield a
            else:
                return
    return ''.join(_iter())


def slice_repr(slice_obj):
    """
    Get the best guess of a minimal representation of
    a slice, as it would be created by indexing.
    """
    slice_items = [slice_obj.start, slice_obj.stop, slice_obj.step]
    if slice_items[-1] is None:
        slice_items.pop()
    if slice_items[-1] is None:
        if slice_items[0] is None:
            return "all"
        else:
            return repr(slice_items[0]) + ":"
    else:
        return ":".join("" if x is None else repr(x) for x in slice_items)


def get_header(fname, readkwargs):
    skipUntil = readkwargs.pop('lastSkipRowContains', '')
    headerLen = -1
    if 'skiprows' not in readkwargs:
        if skipUntil:
            with open(fname, 'r') as f:
                for il, line in enumerate(f):
                    if skipUntil in line:
                        headerLen = il
                    if il == MAX_HEADER_LINES:
                        break
            if headerLen >= 0:
                readkwargs['skiprows'] = headerLen + 1
    else:
        headerLen = readkwargs['skiprows']
    header = []
    with open(fname, 'r') as f:
        for il, line in enumerate(f):
            if il == MAX_HEADER_LINES:
                break
            if ((headerLen >= 0) and (il <= headerLen)) or \
                    line.startswith('#'):
                header.append(line)
    return header