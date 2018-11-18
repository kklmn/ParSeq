# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

from .propWidget import PropWidget


class ContainerFileWidget(PropWidget):
    def __init__(self, parent=None, node=None):
        super(ContainerFileWidget, self).__init__(parent)
        self.node = node

        label = qt.QLabel("select data entry in container file:")
        self.selector = qt.QComboBox()
        self.selector.addItems(["not yet implemented"])
        self.autoAddCB = qt.QCheckBox("auto append fresh data TODO")

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(label)
        layout.addWidget(self.selector)
        layout.addWidget(self.autoAddCB)
        layout.addStretch()
        self.setLayout(layout)
