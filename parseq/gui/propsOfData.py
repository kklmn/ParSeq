# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

# from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco

DEBUG = 40


def getCommonPropInSelectedItems(prop):
    values = [cco.getDotAttr(it, prop) for it in csi.selectedItems]
    try:
        if values.count(values[0]) == len(values):  # equal in selectedItems
            return values[0]
    except (AttributeError, TypeError, IndexError) as e:
        if DEBUG > 30:
            print('getCommonPropInSelectedItems', prop, e,
                  [it.alias for it in csi.selectedItems])


def setRButtonGroupFromData(rButtons, prop):
    common = getCommonPropInSelectedItems(prop)
    if common is not None:
        rButtons[common].setChecked(True)  # prop is int index
    else:
        for rb in rButtons:
            rb.setAutoExclusive(False)
            rb.setChecked(False)
            rb.setAutoExclusive(True)


def setRButtonGroupWithEditsFromData(rButtons, edits, props):
    if not (len(rButtons) == len(edits) == len(props)):
        raise ValueError('these 3 sequences must have equal lengths')
    for rb, ed, prop in zip(rButtons, edits, props):
        common = getCommonPropInSelectedItems(prop)
        if common is not None:
            rb.setChecked(True)
            if isinstance(common, type('')):
                ed.setText(common)
            else:
                ed.setText(str(common))
        else:
            rb.setAutoExclusive(False)
            rb.setChecked(False)
            rb.setAutoExclusive(True)
            ed.setText('')


def setComboBoxFromData(comboBox, prop, compareWith=None, defaultIndex=0):
    common = getCommonPropInSelectedItems(prop)
    if common is not None:
        ind = compareWith.index(common) if compareWith is not None else common
        if isinstance(ind, int):
            comboBox.setCurrentIndex(ind)
        else:
            comboBox.setCurrentIndex(comboBox.findText(ind))
    else:
        if defaultIndex in ['last', -1]:
            defaultIndex = comboBox.count() - 1
        comboBox.setCurrentIndex(defaultIndex)


def setCButtonFromData(cButton, prop, compareWith=None):
    common = getCommonPropInSelectedItems(prop)
    if common is not None:
        if compareWith is not None:
            cond = common == compareWith
        else:
            cond = True if common else False  # prop can be not bool
        cButton.setChecked(cond)
    else:
        cButton.setChecked(False)


def setEditFromData(edit, prop, textFormat='', skipDefault=None, **kw):
    common = getCommonPropInSelectedItems(prop)
    if common is None or common == skipDefault:
        edit.setText('')
        return ''
    if isinstance(common, type('')):
        edit.setText(common)
        return common
    else:
        if textFormat == '':
            sf = '{0}'
        elif 'strip' in textFormat:
            sf = '{0:.0e}'
        else:
            sf = '{0:' + textFormat + '}'
        ss = sf.format(common)
        if 'strip' in textFormat:
            ss = ss.lower()
            for r in (("e-0", "e-"), ("e+0", "e+")):
                ss = ss.replace(*r)
        if ss.endswith("e+0") or ss.endswith("e-0"):
            ss = ss[:-3]
        edit.setText(ss)
        return ss


def setSpinBoxFromData(sb, prop):
    common = getCommonPropInSelectedItems(prop)
    if common is None:
        sb.setSpecialValueText(' ')  # can't be ''
        return
    if isinstance(common, type("")):
        sb.lineEdit().setText(common)
    else:
        sb.setValue(common)


def updateDataFromRButtonGroup(rButtons, prop):
    for irb, rb in enumerate(rButtons):
        if rb.isChecked():
            break
    else:
        return

    for it in csi.selectedItems:
        itContainer, itAttr, itValue = cco.getDotAttr(it, prop, True)
        if itValue != irb:
            # cco.setDotAttr(it, prop, irb)
            itContainer[itAttr] = irb
            it.hasChanged = True


def updateDataFromRButtonGroupWithEdits(
        rButtons, edits, props, convertTypes=None):
    if convertTypes is None:
        convertTypes = [None] * len(rButtons)
    if not (len(rButtons) == len(edits) == len(props) == len(convertTypes)):
        raise ValueError('these 4 sequences must have equal lengths')
    for irb, (rb, ed, prop, convertType) in enumerate(
            zip(rButtons, edits, props, convertTypes)):
        if rb.isChecked():
            txt = ed.text()
            if len(txt) == 0:
                return
            if convertType is not None:
                try:
                    txt = convertType(txt)
                except ValueError:
                    pass
            break
    else:
        return

    for it in csi.selectedItems:
        itContainer, itAttr, itValue = cco.getDotAttr(it, prop, True)
        if str(itValue) != str(txt):  # should update
            itContainer[itAttr] = txt
            for otherProp in props:
                if otherProp == prop:
                    continue
                itContainer.pop(otherProp, '')
            it.hasChanged = True


def updateDataFromEdit(edit, prop, convertType=None, textReplace=None, **kw):
    txt = edit.text()
    if len(txt) == 0:
        return
    if textReplace is not None:
        txt = txt.replace(*textReplace)
    if convertType is not None:
        try:
            txt = convertType(txt)
        except ValueError:
            pass

    for it in csi.selectedItems:
        itContainer, itAttr, itValue = cco.getDotAttr(it, prop, True)
        if itValue != txt:
            # cco.setDotAttr(it, prop, irb)
            itContainer[itAttr] = txt
            it.hasChanged = True


def copyProps(source, props):
    for prop in props:
        newVal = cco.getDotAttr(source, prop)
        for it in csi.selectedItems:
            itContainer, itAttr, oldVal = cco.getDotAttr(it, prop, True)
            if newVal != oldVal:
                if newVal is None:
                    del itContainer[itAttr]
                else:
                    itContainer[itAttr] = newVal
                it.hasChanged = True
