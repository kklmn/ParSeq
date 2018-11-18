# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from . import singletons
from . import spectra
from . import transforms
from . import commons


def upply_undo():
    """*undo* list has records of
    1) [transform, activeIndex, params, prev], where prev list has
       [data, prevParams] records for each data within activeIndex
    2) [spectrum, insertAt, lenData]
    """
    lastUndo = singletons.undo.pop()
    singletons.redo.append(lastUndo)
    if isinstance(lastUndo[0], transforms.Transform):
        tran = lastUndo[0]
        singletons.activeIndex = lastUndo[1]
        prev = lastUndo[-1]
        for data, params in prev:
            for par in params:
                data.transformParams[tran.name][par] = params[par]
        for par in params:
            tran.params[par] = params[par]
        tran.run(updateUndo=False, runDownstream=True)
    elif isinstance(lastUndo[0], spectra.Spectrum):
        del(singletons.dataEntries[lastUndo[1]])


def upply_redo():
    lastRedo = singletons.redo.pop()
    singletons.undo.append(lastRedo)
    if isinstance(lastRedo[0], transforms.Transform):
        tran = lastRedo[0]
        singletons.activeIndex = lastRedo[1]
        params = lastRedo[2]
        for par in params:
            tran.params[par] = params[par]
        tran.run(params=params, updateUndo=False, runDownstream=True)
    elif isinstance(lastRedo[0], spectra.Spectrum):
        data = lastRedo[0]
        insertAt = lastRedo[1]
        singletons.dataEntries.insert(insertAt, data)


def get_undo_str():
    return get_str_repr('undo')


def get_redo_str():
    return get_str_repr('redo')


def get_str_repr(what):
    if what == 'redo':
        dolist = singletons.redo
    else:
        dolist = singletons.undo
    strList = []
    for entry in dolist:
        if isinstance(entry[0], transforms.Transform):
            srep = commons.slice_repr(entry[1]) if isinstance(entry[1], slice)\
                else entry[1]
            do = "apply '{0}' to {1} with {2}".format(
                entry[0].name, srep, entry[2])
        elif isinstance(entry[0], spectra.Spectrum):
            if entry[1] == entry[2]:
                do = 'append {0}'.format(entry[0].alias)
            else:
                do = 'insert {0} at {1}'.format(entry[0].alias, entry[1])
        strList.append(do)
    return strList
