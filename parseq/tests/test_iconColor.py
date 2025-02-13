# -*- coding: utf-8 -*-
"""
Created on Wed Feb 12 20:26:47 2025

@author: konkle
"""

import sys
from silx.gui import qt


class MainWindow(qt.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = qt.QVBoxLayout()
        button = qt.QPushButton("Click Me", self)
        pixOn = qt.QPixmap("../gui/_images/icon-item-1dim-32.png")
        pixOff = qt.QPixmap(pixOn)

        painter = qt.QPainter(pixOff)
        painter.setCompositionMode(qt.QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixOff.rect(), qt.Qt.red)
        painter.end()

        icon = qt.QIcon()
        icon.addPixmap(pixOff, qt.QIcon.Normal, qt.QIcon.Off)
        icon.addPixmap(pixOn, qt.QIcon.Normal, qt.QIcon.On)

        button.setIcon(icon)
        button.setCheckable(True)
        button.setChecked(True)

        layout.addWidget(button)
        layout.addStretch()

        self.resize(200, 100)


if __name__ == '__main__':
    app = qt.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec_()
    # app.deleteLater()
