# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys
from silx.gui import qt
from collections import OrderedDict

symbols = OrderedDict([
    ('circle', 'o'), ('point', '.'), ('pixel', ','), ('cross', '+'),
    ('x-cross', 'x'), ('diamond', 'd'), ('square', 's'), ('none', '')])
styles = OrderedDict([
    ('no line', ' '), ('solid', '-'), ('dashed', '--'), ('dash-dot', '-.'),
    ('dotted', ':')])


class LinePropertiesDialog(qt.QDialog):
    def __init__(self, parent=None, title="Line Properties Dialog"):
        qt.QDialog.__init__(self, parent)
        self.setWindowTitle(title)

        layout1 = qt.QHBoxLayout()
        layout1.addWidget(qt.QLabel('Color:'))
        self.colorButton = qt.QPushButton()
        self.colorButton.clicked.connect(self.openColorDialog)
        layout1.addWidget(self.colorButton, 1)

        layout2 = qt.QHBoxLayout()
        layout2.addWidget(qt.QLabel('Symbol:'))
        self.symbolComboBox = qt.QComboBox()
        for symbol in tuple(symbols.keys()):
            self.symbolComboBox.addItem(symbol)
        layout2.addWidget(self.symbolComboBox, 1)

        layout3 = qt.QHBoxLayout()
        layout3.addWidget(qt.QLabel('Width:'))
        self.widthSpinBox = qt.QDoubleSpinBox()
        self.widthSpinBox.setDecimals(1)
        self.widthSpinBox.setMaximum(10)
        self.widthSpinBox.setMinimum(0.1)
        self.widthSpinBox.setSingleStep(0.5)
        layout3.addWidget(self.widthSpinBox, 1)

        layout4 = qt.QHBoxLayout()
        layout4.addWidget(qt.QLabel('Style:'))
        self.styleComboBox = qt.QComboBox()
        for style in tuple(styles.keys()):
            self.styleComboBox.addItem(style)
        layout4.addWidget(self.styleComboBox, 1)

        buttonBox = qt.QDialogButtonBox(
            qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)  # OK button

        layout = qt.QVBoxLayout(self)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(layout4)
        layout.addStretch()
        layout.addWidget(buttonBox)
        self.setLayout(layout)
#        self.setFixedSize(vLayout.minimumSize())

        self.setLineProperties(color='red', symbol='', width=1, style='-')

    def setColor(self, color):
        self.color = color
        self.colorButton.setStyleSheet("background-color: %s" % color)

    def openColorDialog(self):
        color = qt.QColorDialog().getColor()
        if color.isValid():
            self.setColor(str(color.name()))

    def setLineProperties(self, color=None, symbol=None, width=None,
                          style=None):
        if color is not None:
            self.setColor(color)

        if symbol is not None:
            assert symbol in symbols.values()
            index = list(symbols.values()).index(symbol)
            self.symbolComboBox.setCurrentIndex(index)

        if width is not None:
            if width < self.widthSpinBox.minimum():
                width = self.widthSpinBox.minimum()
            if width > self.widthSpinBox.maximum():
                width = self.widthSpinBox.maximum()
            self.widthSpinBox.setValue(width)

        if style is not None:
            assert style in styles.values()
            index = list(styles.values()).index(style)
            self.styleComboBox.setCurrentIndex(index)

    def getLineProperties(self):
        properties = {
            'color': self.color,
            'symbol': symbols[self.symbolComboBox.currentText()],
            'linewidth': self.widthSpinBox.value(),
            'linestyle': styles[self.styleComboBox.currentText()]
            }
        return properties


def test():
    import time
    app = qt.QApplication(sys.argv)
    form = LinePropertiesDialog()
    form.show()
    app.exec_()
    lineProps = form.getLineProperties()
    print(lineProps)
    time.sleep(3)


if __name__ == '__main__':
    test()
