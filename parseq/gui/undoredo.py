# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import reprlib

from ..core import singletons as csi
from ..core import spectra as csp
from ..core import commons as cco


class FloatRepr(reprlib.Repr):
    def repr_float(self, value, level):
        return format(value, '.3f')

    def repr_float64(self, value, level):
        return self.repr_float(value, level)


def upplyUndo(ind):
    """*undo* list has records of
    1) [propWidget, dataItems, params, prevValues, newValues, strChange],
    2) [spectra, rows, strChange]
    """
    if len(csi.undo) == 0:
        return
    if 0 <= ind < len(csi.undo):
        csi.undo.rotate(-ind)
        lastEntry = csi.undo.popleft()
        csi.undo.rotate(ind)
    else:
        lastEntry = csi.undo.pop()
    if isinstance(lastEntry[0], list) and lastEntry[-1].startswith('remove'):
        pass
    else:
        csi.redo.append(lastEntry)
    csi.mainWindow.setEnableUndoRedo()
    if hasattr(lastEntry[0], 'undoProps'):  # lastEntry[0] is PropWidget
        lastEntry[0].undoProps(lastEntry)
    elif isinstance(lastEntry[0], list):
        if isinstance(lastEntry[0][0], csp.Spectrum):
            if lastEntry[-1].startswith('remove'):
                csi.model.undoRemove(lastEntry)


def upplyRedo(ind):
    if len(csi.redo) == 0:
        return
    if 0 <= ind < len(csi.redo):
        csi.redo.rotate(-ind)
        lastEntry = csi.redo.popleft()
        csi.redo.rotate(ind)
    else:
        lastEntry = csi.redo.pop()
    csi.undo.append(lastEntry)
    csi.mainWindow.setEnableUndoRedo()
    if hasattr(lastEntry[0], 'redoProps'):  # lastEntry[0] is PropWidget
        lastEntry[0].redoProps(lastEntry)
    elif isinstance(lastEntry[0], csp.Spectrum):
        pass


def getStrRepr(entry):
    if hasattr(entry[0], 'undoProps'):  # lastUndo[0] is PropWidget
        propWidget, items, params, prevValues, values, strChange = entry
        selNames = [it.alias for it in items]
        combinedNames = cco.combine_names(selNames)
        if strChange.startswith('reset'):
            return '{0} for {1}'.format(strChange, combinedNames)
        elif len(params) == 1:
            return 'change {0} to {1} for {2}'.format(
                cco.shrinkTransformParam(params[0]),
                FloatRepr().repr(values[0]), combinedNames)
        elif len(params) > 1:
            return '{0} to {1}'.format(strChange, combinedNames)
    elif isinstance(entry[0], list):
        warn = ', <span style="color:red;"> still in memory, ' + \
            'use the cross ➜ to free up memory </span>'
        if isinstance(entry[0][0], csp.Spectrum):
            spectra, struct, strChange = entry
            selNames = [it.alias for it in spectra]
            combinedNames = cco.combine_names(selNames)
            return '{0} {1} {2}'.format(strChange, combinedNames, warn)


def pushTransformToUndo(propWidget, dataItems, params, values, strChange=''):
    """*undo* list has records of
    [propWidget, dataItems, params, prevValues, newValues, strChange],
    prevValues is a list (length of dataItems) of lists of old values.
    """
    # Check for repeated change of parameters. Considered as repeated if
    # same dataItems and same set of params
    if len(csi.undo) > 0 and csi.undoGrouping:  # compare with last record
        lastUndo = csi.undo[-1]
        isRepeated = ((lastUndo[1] == dataItems) and
                      (set(lastUndo[2]) == set(params)))  # set of keys
        if isRepeated:
            # update only the new params in the last entry without
            # appending a new entry to undo list
            lastUndo[4] = values
            return

    prevValues = []
    items = []
    for data in dataItems:
        pvs = [cco.getDotAttr(data, p) for p in params]
        for pv, v in zip(pvs, values):
            try:
                if v != pv:
                    hasChanged = True
                    break
            except ValueError:  # ambiguous for numpy arrays
                if not (v == pv).all():
                    hasChanged = True
                    break
        else:
            hasChanged = False
        if hasChanged:
            items.append(data)
            prevValues.append(pvs)

    if len(items) > 0 and hasattr(csi.mainWindow, 'undoAction'):  # has changed
        csi.undo.append(
            [propWidget, items, params, prevValues, values, strChange])
        csi.mainWindow.setEnableUndoRedo()


def pushDataToUndo(data, struct, strChange=''):
    """
    struct = [(d.parentItem, d.childItems.copy(), d.row()) for d in data]
    """
    if len(data) > 0 and hasattr(csi.mainWindow, 'undoAction'):
        csi.undo.append([data, struct, strChange])
        csi.mainWindow.setEnableUndoRedo()
