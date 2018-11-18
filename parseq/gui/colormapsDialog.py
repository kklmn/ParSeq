# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys
from silx.gui import qt

colormaps = (
    'temperature', 'viridis', 'plasma', 'cool', 'copper', 'autumn', 'spring',
    'summer', 'winter', 'brg', 'gnuplot', 'jet')


class ColormapDialog(qt.QDialog):
    def __init__(self, parent=None, title="Colormap Dialog"):
        super(qt.QDialog, self).__init__(parent)
        self.setWindowTitle(title)

        layout1 = qt.QHBoxLayout()
        layout1.addWidget(qt.QLabel('Colormap:'))
        layout1.addSpacing(0)
        self.colormapCB = qt.QComboBox()
        for cmap in colormaps:
            self.colormapCB.addItem(cmap.capitalize())
        layout1.addWidget(self.colormapCB, 1)

        layout2 = qt.QHBoxLayout()
        layout2.addWidget(qt.QLabel('Normalization:'))
        self.normButtonLinear = qt.QRadioButton('Linear')
        self.normButtonLinear.setChecked(True)
        self.normButtonLog = qt.QRadioButton('Log')
        normButtonGroup = qt.QButtonGroup(self)
        normButtonGroup.setExclusive(True)
        normButtonGroup.addButton(self.normButtonLinear)
        normButtonGroup.addButton(self.normButtonLog)
        layout2.addWidget(self.normButtonLinear)
        layout2.addWidget(self.normButtonLog)

        buttonBox = qt.QDialogButtonBox(
            qt.QDialogButtonBox.Ok | qt.QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)  # OK button

        layout = qt.QVBoxLayout(self)
        layout.addLayout(layout1)
        layout.addLayout(layout2)
        layout.addStretch()
        layout.addWidget(buttonBox)
        self.setLayout(layout)

        self.setColormap(name='temperature', normalization='linear')

    def setColormap(self, name=None, normalization=None):
        if name is not None:
            assert name in colormaps
            index = colormaps.index(name)
            self.colormapCB.setCurrentIndex(index)

        if normalization is not None:
            assert normalization in ('linear', 'log')
            self.normButtonLinear.setChecked(normalization == 'linear')
            self.normButtonLog.setChecked(normalization == 'log')

    def getColormap(self):
        isNormLinear = self.normButtonLinear.isChecked()
        colormap = {
            'name': str(self.colormapCB.currentText()).lower(),
            'normalization': 'linear' if isNormLinear else 'log'}
        return colormap

#    def accept(self):
#        colormap = self.getColormap()
#        print(colormap)


def test():
    import time
    app = qt.QApplication(sys.argv)
    form = ColormapDialog()
    form.show()
    app.exec_()
    print(form.getColormap())
    time.sleep(3)


if __name__ == '__main__':
    test()
