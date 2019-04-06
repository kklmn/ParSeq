# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt


class QLineEditSelectRB(qt.QLineEdit):
    def __init__(self, parent=None, rb=None):
        super(QLineEditSelectRB, self).__init__(parent)
        self.buddyRB = rb

    def focusInEvent(self, e):
        self.buddyRB.setChecked(True)
        super(QLineEditSelectRB, self).focusInEvent(e)


class PropWidget(qt.QWidget):

    def keyPressEvent(self, event):
        if event.key() in (qt.Qt.Key_Enter, qt.Qt.Key_Return):
            self.updateDataFromUI()
        event.accept()

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
