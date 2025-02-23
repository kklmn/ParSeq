# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "1 Feb 2022"
# !!! SEE CODERULES.TXT !!!

# from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from ..core.logger import syslogger


def getCommonPropInSelectedItems(prop, outLevel=10):
    values = [cco.getDotAttr(it, prop) for it in csi.selectedItems]
    if outLevel > 1 and isinstance(prop, str):
        if prop.startswith('transformParams'):
            for it in csi.selectedItems:
                test = cco.getDotAttr(it, prop, True)
                if test[1] not in test[0]:  # attr in container
                    syslogger.error(
                        "unknown parameter in data's transformParams: {0}"
                        .format(test[1]))
    try:
        if values.count(values[0]) == len(values):  # equal in selectedItems
            return values[0]
    except (AttributeError, TypeError, IndexError, ValueError) as e:
        syslogger.error('getCommonPropInSelectedItems {0} {1} {2}'.format(
            prop, e, [it.alias for it in csi.selectedItems]))


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
            if isinstance(common, str):
                ed.setText(common)
            else:
                ed.setText(str(common))
        else:
            rb.setAutoExclusive(False)
            rb.setChecked(False)
            rb.setAutoExclusive(True)
            ed.setText('')


def setComboBoxFromData(comboBox, prop, compareWith=None, defaultIndex=-1,
                        **kw):
    common = getCommonPropInSelectedItems(prop)
    if common is not None:
        if isinstance(common, float):
            comboBox.lineEdit().setText(str(common))
            return
        ind = common if compareWith is None else compareWith.index(common)
        newInd = ind if isinstance(ind, int) else comboBox.findText(ind)
    else:
        if defaultIndex in ['last',]:
            defaultIndex = comboBox.count() - 1
        newInd = defaultIndex

    curInd = comboBox.currentIndex()
    comboBox.setCurrentIndex(newInd)
    if curInd == newInd:  # force the signal for updating gui
        comboBox.currentIndexChanged.emit(newInd)


def setRangeWidgetFromData(rWidget, prop):
    common = getCommonPropInSelectedItems(prop)
    rWidget.setRange(common)


def setStateButtonsFromData(sb, prop):
    common = getCommonPropInSelectedItems(prop)
    sb.setActive(common)


def setCorrectionsFromData(corrTable, prop):
    common = getCommonPropInSelectedItems(prop, outLevel=0)
    corrTable.setCorrections(common)


def setCButtonFromData(cButton, prop, compareWith=None):
    common = getCommonPropInSelectedItems(prop)
    if common is not None:
        if compareWith is None:
            cond = True if common else False  # prop can be not bool
        else:
            cond = common == compareWith
        cButton.setChecked(cond)
    else:
        cButton.setChecked(False)


def setEditFromData(edit, prop, textFormat='', skipDefault=None, **kw):
    kwc = dict(outLevel=0) if 'ignoreErrors' in kw else {}
    common = getCommonPropInSelectedItems(prop, **kwc)
    hideEmpty = kw.get('hideEmpty', False)
    if hideEmpty:
        edit.setVisible(common not in ['', None])
    if common is None or common == skipDefault:
        edit.setText('')
        return ''
    if isinstance(common, str):
        if 'styleDict' in kw:
            styleDict = kw['styleDict']
            for word, styleStr in styleDict.items():
                if word in common:
                    edit.setText(styleStr.format(common))
                    return common
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
        if ('strip' in textFormat) or ('g' in textFormat):
            ss = ss.lower()
            for r in (("e-0", "e-"), ("e+0", "e+")):
                ss = ss.replace(*r)
        if ss.endswith("e+0") or ss.endswith("e-0"):
            ss = ss[:-3]
        edit.setText(ss)
        return ss


setLabelFromData = setEditFromData


def setSpinBoxFromData(sb, prop):
    common = getCommonPropInSelectedItems(prop)
    if common is None:
        sb.lineEdit().setText('')
        return
    if isinstance(common, str):
        sb.lineEdit().setText(common)
    else:
        sb.setValue(common)
        sb.update()


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
        if 'emptyMeans' in kw:
            txt = kw['emptyMeans']
        else:
            return
    else:
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


def updateDataFromSpinBox(spinBox, prop):
    if not spinBox.isEnabled():
        return
    value = spinBox.value()
    for it in csi.selectedItems:
        itContainer, itAttr, itValue = cco.getDotAttr(it, prop, True)
        if itValue != value:
            # cco.setDotAttr(it, prop, irb)
            itContainer[itAttr] = value
            it.hasChanged = True


def updateDataFromComboBox(combobox, prop, convertType=None, textReplace=None,
                           compareWith=None, **kw):
    if not combobox.isEnabled():
        return
    ind = combobox.currentIndex()
    txt = combobox.currentText() if compareWith is None else compareWith[ind]

    if textReplace is not None:
        txt = txt.replace(*textReplace)
    if convertType is not None:
        try:
            txt = convertType(txt)
        except ValueError:
            pass
    for it in csi.selectedItems:
        itContainer, itAttr, itValue = cco.getDotAttr(it, prop, True)
        val = ind if isinstance(itValue, int) else txt
        if itValue != val:
            itContainer[itAttr] = txt
            it.hasChanged = True


def updateDataFromRangeWidget(rangeWidget, prop):
    value = rangeWidget.acceptEdit()
    for it in csi.selectedItems:
        itContainer, itAttr, itValue = cco.getDotAttr(it, prop, True)
        if itValue != value:
            # cco.setDotAttr(it, prop, irb)
            itContainer[itAttr] = value
            it.hasChanged = True


def copyProps(dataItems, props, newVals, removeNones=True):
    assert len(props) == len(newVals)
    countChanges = 0
    for prop, newVal in zip(props, newVals):
        for it in dataItems:
            itContainer, itAttr, oldVal = cco.getDotAttr(it, prop, True)
            try:
                isOld = newVal == oldVal
                if not isinstance(isOld, bool):  # i.e. is an array
                    isOld = isOld.all()
                if not isOld:
                    if (newVal is None) and removeNones:
                        del itContainer[itAttr]
                    else:
                        itContainer[itAttr] = newVal
                    it.hasChanged = True
                    countChanges += 1
            except ValueError:
                type_ = type(newVal).__name__
                raise ValueError(
                    'do not mix arrays with non-arrays in the {0} {1}'.format(
                        type_, prop))
    return countChanges
