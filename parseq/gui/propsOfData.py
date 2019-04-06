# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco

DEBUG = 20


def getPropsInSelectedItems(prop, items=None):
    """
    *prop* can have a dot notation for sub-atributes.
    """
    try:
        objs = [cco.getDotAttr(it, prop) for it in csi.selectedItems]
        if items is not None:
            if not isinstance(items, (tuple, list)):
                items = [items]
            for item in items:
                objs = [obj[item] for obj in objs]
        return objs
    except (AttributeError, IndexError, KeyError) as e:
        if DEBUG > 30:
            print('getPropsInSelectedItems', prop, e,
                  [it.alias for it in csi.selectedItems])
        return


def getCommonPropInSelectedItems(dataPropName, items=None):
    props = getPropsInSelectedItems(dataPropName, items)
    try:
        if props.count(props[0]) == len(props):  # equal in all items
            return props[0]
    except (AttributeError, TypeError):
        return


def setRButtonGroupFromData(rButtons, dataPropName, items=None):
    prop = getCommonPropInSelectedItems(dataPropName, items)
    if prop is not None:
        rButtons[prop].setChecked(True)  # prop is int index
    else:
        for rb in rButtons:
            rb.setAutoExclusive(False)
            rb.setChecked(False)
            rb.setAutoExclusive(True)


def setRButtonGroupWithEditsFromData(rButtons, edits, dataPropName, items):
    for rb, ed, item in zip(rButtons, edits, items):
        prop = getCommonPropInSelectedItems(dataPropName, item)
        if prop is not None:
            rb.setChecked(True)
            if isinstance(prop, type('')):
                ed.setText(prop)
            else:
                ed.setText(str(prop))
        else:
            rb.setAutoExclusive(False)
            rb.setChecked(False)
            rb.setAutoExclusive(True)
            ed.setText('')


def setComboBoxFromData(comboBox, dataPropName, items=None,
                        compareWith=None, defaultIndex=0):
    prop = getCommonPropInSelectedItems(dataPropName, items)
    if prop is not None:
        ind = compareWith.index(prop) if compareWith is not None else prop
        if isinstance(ind, int):
            comboBox.setCurrentIndex(ind)
        else:
            comboBox.setCurrentIndex(comboBox.findText(ind))
    else:
        if defaultIndex == 'last':
            defaultIndex = comboBox.count() - 1
        comboBox.setCurrentIndex(defaultIndex)


def setCButtonFromData(cButton, dataPropName, items=None, compareWith=None):
    prop = getCommonPropInSelectedItems(dataPropName, items)
    if prop is not None:
        if compareWith is not None:
            cond = prop == compareWith
        else:
            cond = True if prop else False
        cButton.setChecked(cond)  # prop can be not bool
    else:
        cButton.setChecked(False)


def setEditFromData(edit, dataPropName, items=None, textFormat='',
                    skipDefault=None):
    prop = getCommonPropInSelectedItems(dataPropName, items)
    if prop is None or prop == skipDefault:
        edit.setText('')
        return
    if isinstance(prop, type('')):
        edit.setText(prop)
    else:
        if textFormat == '':
            sf = '{0}'
        elif 'strip' in textFormat:
            sf = '{0:.0e}'
        else:
            sf = '{0:' + textFormat + '}'
        ss = sf.format(prop)
        if 'strip' in textFormat:
            ss = ss.lower()
            for r in (("e-0", "e-"), ("e+0", "e+")):
                ss = ss.replace(*r)
        if ss.endswith("e+0") or ss.endswith("e-0"):
            ss = ss[:-3]
        edit.setText(ss)


def setSpinBoxFromData(sb, dataPropName, items=None):
    prop = getCommonPropInSelectedItems(dataPropName, items)
    if prop is None:
        sb.setSpecialValueText(' ')  # can't be ''
        return
    if isinstance(prop, type("")):
        sb.lineEdit().setText(prop)
    else:
        sb.setValue(prop)


def updateDataFromRButtonGroup(rButtons, dataPropName, items=None):
    for irb, rb in enumerate(rButtons):
        if rb.isChecked():
            break
    else:
        return
    props = getPropsInSelectedItems(dataPropName, items)
    if props is None:
        props = [None] * len(csi.selectedItems)
    for prop, it in zip(props, csi.selectedItems):
        if prop != irb:  # should update
            if items is None:
                cco.setDotAttr(it, dataPropName, irb)  # prop is int index
            else:
                if not isinstance(items, (tuple, list)):
                    items = [items]
                propData = cco.getDotAttr(it, dataPropName)
                for item in items[:-1]:
                    propData = propData[item]
                propData[items[-1]] = irb
            it.hasChanged = True


def updateDataFromRButtonGroupWithEdits(rButtons, edits, dataPropName,
                                        kwProps):
    for irb, (rb, ed, kwProp) in enumerate(zip(rButtons, edits, kwProps)):
        if rb.isChecked():
            txt = ed.text()
            if len(txt) == 0:
                return
            if kwProp == 'skiprows':
                txt = int(txt)
            break
    else:
        return
    props = getPropsInSelectedItems(dataPropName, kwProp)
    if props is None:
        props = [None] * len(csi.selectedItems)
    for prop, it in zip(props, csi.selectedItems):
        if str(prop) != str(txt):  # should update
            propDict = cco.getDotAttr(it, dataPropName)
            propDict[kwProp] = txt
            for whatT in kwProps:
                if whatT == kwProp:
                    continue
                propDict.pop(whatT, '')
            it.hasChanged = True


def updateDataFromEdit(edit, dataPropName, items=None, fieldType=None,
                       textReplace=None):
    txt = edit.text()
    if len(txt) == 0:
        return
    if textReplace is not None:
        txt = txt.replace(*textReplace)
    if fieldType is not None:
        txt = fieldType(txt)

    props = getPropsInSelectedItems(dataPropName, items)
    if props is None:
        props = [None] * len(csi.selectedItems)
    for prop, it in zip(props, csi.selectedItems):
        if str(prop) != str(txt):  # should update
            if items is None:
                cco.setDotAttr(it, dataPropName, txt)
            else:
                if not isinstance(items, (tuple, list)):
                    items = [items]
                propData = cco.getDotAttr(it, dataPropName)
                for item in items[:-1]:
                    propData = propData[item]
                propData[items[-1]] = txt
            it.hasChanged = True
