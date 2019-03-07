# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt
from ..core import singletons as csi


class QLineEditSelectRB(qt.QLineEdit):
    def __init__(self, parent=None, rb=None):
        super(QLineEditSelectRB, self).__init__(parent)
        self.buddyRB = rb

    def focusInEvent(self, e):
        self.buddyRB.setChecked(True)
        super(QLineEditSelectRB, self).focusInEvent(e)


class PropWidget(qt.QWidget):

    def getPropsInSelectedItems(self, dataPropName, kwProp=None, ind=None):
        try:
            if kwProp is None:  # then dataPropName is a value
                props = [getattr(it, dataPropName) for it in csi.selectedItems]
            else:  # then dataPropName is a dict or a sequence
                if ind is None:
                    props = [getattr(it, dataPropName)[kwProp]
                             for it in csi.selectedItems]
                else:
                    props = [getattr(it, dataPropName)[kwProp][ind]
                             for it in csi.selectedItems]
            return props
        except (IndexError, KeyError) as e:
#            print(dataPropName, e)
            return

    def getCommonPropInSelectedItems(self, dataPropName, kw=None, ind=None):
        props = self.getPropsInSelectedItems(dataPropName, kw, ind)
        try:
            if props.count(props[0]) == len(props):  # equal in all items
                return props[0]
        except (AttributeError, TypeError):
            return

    def setRButtonGroupFromData(self, rButtons, dataPropName, kwProp=None):
        prop = self.getCommonPropInSelectedItems(dataPropName, kwProp)
        if prop is not None:
            rButtons[prop].setChecked(True)  # prop is int index
        else:
            for rb in rButtons:
                rb.setAutoExclusive(False)
                rb.setChecked(False)
                rb.setAutoExclusive(True)

    def setRButtonGroupWithEditsFromData(self, rButtons, edits, dataPropName,
                                         kwProps):
        for rb, ed, kw in zip(rButtons, edits, kwProps):
            prop = self.getCommonPropInSelectedItems(dataPropName, kw)
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

    def setComboBoxFromData(self, comboBox, dataPropName, kwProp=None,
                            ind=None, compareWith=None):
        prop = self.getCommonPropInSelectedItems(dataPropName, kwProp, ind)
        if prop is not None:
            ind = compareWith.index(prop) if compareWith is not None else prop
            comboBox.setCurrentIndex(ind)
        else:
            comboBox.setCurrentIndex(0)

    def setCButtonFromData(self, cButton, dataPropName, kwProp=None, ind=None,
                           compareWith=None):
        prop = self.getCommonPropInSelectedItems(dataPropName, kwProp, ind)
        if prop is not None:
            if compareWith is not None:
                cond = prop == compareWith
            else:
                cond = True if prop else False
            cButton.setChecked(cond)  # prop can be not bool
        else:
            cButton.setChecked(False)

    def setEditFromData(self, edit, dataPropName, kwProp=None, ind=None,
                        textFormat='', skipDefault=None):
        prop = self.getCommonPropInSelectedItems(dataPropName, kwProp, ind)
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

    def setSpinBoxFromData(self, sb, dataPropName, kwProp=None, ind=None):
        prop = self.getCommonPropInSelectedItems(dataPropName, kwProp, ind)
        if prop is None:
            sb.lineEdit().setText("")
            return
        if isinstance(prop, type("")):
            sb.lineEdit().setText(prop)
        else:
            sb.setValue(prop)

    def keyPressEvent(self, event):
        if event.key() in (qt.Qt.Key_Enter, qt.Qt.Key_Return):
            self.updateDataFromUI()
        event.accept()

    def updateDataFromRButtonGroup(self, rButtons, dataPropName, kwProp=None):
        for irb, rb in enumerate(rButtons):
            if rb.isChecked():
                break
        else:
            return
        props = self.getPropsInSelectedItems(dataPropName, kwProp)
        if props is None:
            props = [None] * len(csi.selectedItems)
        for prop, it in zip(props, csi.selectedItems):
            if prop != irb:  # should update
                setattr(it, dataPropName, irb)  # prop is int index
                it.hasChanged = True

    def updateDataFromRButtonGroupWithEdits(self, rButtons, edits,
                                            dataPropName, kwProps):
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

        props = self.getPropsInSelectedItems(dataPropName, kwProp)
        if props is None:
            props = [None] * len(csi.selectedItems)
        for prop, it in zip(props, csi.selectedItems):
            if str(prop) != str(txt):  # should update
                propDict = getattr(it, dataPropName)
                propDict[kwProp] = txt
                for whatT in kwProps:
                    if whatT == kwProp:
                        continue
                    propDict.pop(whatT, '')
                it.hasChanged = True

    def updateDataFromEdit(self, edit, dataPropName, kwProp=None, ind=None,
                           fieldType=None, textReplace=None):
        txt = edit.text()
        if len(txt) == 0:
            return
        if textReplace is not None:
            txt = txt.replace(*textReplace)
        if fieldType is not None:
            txt = fieldType(txt)

        props = self.getPropsInSelectedItems(dataPropName, kwProp, ind)
        if props is None:
            props = [None] * len(csi.selectedItems)
        for prop, it in zip(props, csi.selectedItems):
            if str(prop) != str(txt):  # should update
                if kwProp is None:
                    setattr(it, dataPropName, txt)
                else:
                    propData = getattr(it, dataPropName)
                    if ind is None:
                        propData[kwProp] = txt
                    else:
                        propData[kwProp][ind] = txt
                it.hasChanged = True

    def updateProp(self, key, value):
        if self.params[key] == value:
            return
        self.transform.run({key: value})
        self.transform.toNode.widget.replot()
        for subnode in self.transform.toNode.downstreamNodes:
            subnode.widget.replot()

    def updatePropFromSpinBox(self, key, value):
        self.updateProp(key, value)

    def updatePropFromCheckBox(self, key, value):
        self.updateProp(key, value)

    def updatePropFromComboBox(self, key, index, indexToValue=None):
        value = indexToValue[index] if indexToValue is not None else index
        self.updateProp(key, value)

    def setUIFromData(self):
        raise NotImplementedError("'setUIFromData' must be implemented")

    def updateDataFromUI(self):
        pass
