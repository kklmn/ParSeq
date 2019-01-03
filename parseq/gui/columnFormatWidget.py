# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

from ..core import singletons as csi
from ..core import spectra as csp
from .propWidget import QLineEditSelectRB, PropWidget


class ColumnFormatWidget(PropWidget):
    def __init__(self, parent=None, node=None):
        super(ColumnFormatWidget, self).__init__(parent)
        self.node = node

        self.tabWidget = qt.QTabWidget(self)
        headerTab = self.makeHeaderTab()
        self.tabWidget.addTab(headerTab, 'file header')
        dataLocationTab = self.makeDataLocationTab()
        self.tabWidget.addTab(dataLocationTab, 'data location')

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabWidget)
        layout.addStretch()
        self.setLayout(layout)

    def makeHeaderTab(self):
        self.headerNRB = qt.QRadioButton("has")
        self.headerNEdit = QLineEditSelectRB(rb=self.headerNRB)
        self.headerNEdit.setFixedWidth(28)
        self.headerNEdit.setValidator(
            qt.QIntValidator(0, csp.MAX_HEADER_LINES, self))
        self.headerNLabel2 = qt.QLabel("lines")

        self.headerSRB = qt.QRadioButton("has lines beginning with")
        self.headerSEdit = QLineEditSelectRB(rb=self.headerSRB)
        self.headerSEdit.setFixedWidth(16)

        self.headerERB = qt.QRadioButton("ends with line containing")
        self.headerEEdit = QLineEditSelectRB(rb=self.headerERB)
        self.headerEEdit.setMinimumWidth(30)

        self.headerSRB.setChecked(True)

        headerLayoutN = qt.QHBoxLayout()
        headerLayoutN.addWidget(self.headerNRB)
        headerLayoutN.addWidget(self.headerNEdit)
        headerLayoutN.addWidget(self.headerNLabel2)
        headerLayoutN.addStretch()

        headerLayoutS = qt.QHBoxLayout()
        headerLayoutS.addWidget(self.headerSRB)
        headerLayoutS.addWidget(self.headerSEdit)
        headerLayoutS.addStretch()

        headerLayoutE = qt.QHBoxLayout()
        headerLayoutE.addWidget(self.headerERB)
        headerLayoutE.addWidget(self.headerEEdit, 1)
        headerLayoutE.addStretch()

        headerLayout = qt.QVBoxLayout()
        headerLayout.setContentsMargins(2, 2, 2, 2)
        headerLayout.addLayout(headerLayoutN)
        headerLayout.addLayout(headerLayoutS)
        headerLayout.addLayout(headerLayoutE)

        headerTab = qt.QWidget(self)
        headerTab.setLayout(headerLayout)
        headerTab.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)

        self.headerKW = 'skiprows', 'comments', 'lastSkipRowContains'
        self.radioButtons = self.headerNRB, self.headerSRB, self.headerERB
        self.edits = self.headerNEdit, self.headerSEdit, self.headerEEdit

        return headerTab

    def makeDataLocationTab(self):
        if self.node is None:
            return

        try:
            xLbl = self.node.xQLabel
        except AttributeError:
            xLbl = self.node.xName
        try:
            xUnt = self.node.xQUnit
        except AttributeError:
            xUnt = ''
        xUnt = u"({0})".format(xUnt) if xUnt else ""
        self.dataXLabel = qt.QLabel(u"{0}{1} =".format(xLbl, xUnt))
        self.dataXEdit = qt.QLineEdit()
        self.dataXEdit.setMinimumWidth(62)
        self.dataXLabelTimes = qt.QLabel(u"×")
        self.dataXEditTimes = qt.QLineEdit()
        self.dataXEditTimes.setFixedWidth(36)

        self.dataYLabels = []
        self.dataYEdits = []
        try:
            yLbls = self.node.yQLabels
        except AttributeError:
            yLbls = self.node.yNames
        try:
            yUnts = self.node.yQUnits
        except AttributeError:
            yUnts = ['' for y in yLbls]
        for yLbl, yUnt in zip(yLbls, yUnts):
            yUnt = u"({0})".format(yUnt) if yUnt else ""
            dataYLabel = qt.QLabel(u"{0}{1} =".format(yLbl, yUnt))
            dataYEdit = qt.QLineEdit()
            dataYEdit.setSizePolicy(
                qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
            self.dataYLabels.append(dataYLabel)
            self.dataYEdits.append(dataYEdit)

        dataLayoutX = qt.QHBoxLayout()
        dataLayoutX.addWidget(self.dataXLabel)
        dataLayoutX.addWidget(self.dataXEdit, 1)
        dataLayoutX.addWidget(self.dataXLabelTimes)
        dataLayoutX.addWidget(self.dataXEditTimes)
        dataLayoutX.addStretch()

        dataLayoutY = qt.QGridLayout()
        for row, (dataYLabel, dataYEdit) in\
                enumerate(zip(self.dataYLabels, self.dataYEdits)):
            dataLayoutY.addWidget(dataYLabel, row, 0)
            dataLayoutY.addWidget(dataYEdit, row, 1)

        dataLayout = qt.QVBoxLayout()
        dataLayout.setContentsMargins(2, 2, 2, 2)
        dataLayout.addLayout(dataLayoutX)
        dataLayout.addLayout(dataLayoutY)
#        dataLayout.addStretch()

        dataLocationTab = qt.QWidget(self)
        dataLocationTab.setLayout(dataLayout)
        dataLocationTab.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
        return dataLocationTab

    def setUIFromData(self):
        self.setRButtonGroupWithEditsFromData(
            self.radioButtons, self.edits, 'dataFormat', self.headerKW)
        self.setEditFromData(self.dataXEdit, 'dataFormat', 'usecols', 0)
        for iC, edit in enumerate(self.dataYEdits):
            self.setEditFromData(edit, 'dataFormat', 'usecols', iC+1)
        self.setEditFromData(self.dataXEditTimes, 'dataFormat', 'xFactor',
                             textFormat='strip0', skipDefault=1)

    def updateDataFromUI(self):
        self.updateDataFromRButtonGroupWithEdits(
            self.radioButtons, self.edits, 'dataFormat', self.headerKW)

        self.updateDataFromEdit(self.dataXEdit, 'dataFormat', 'usecols', 0,
                                fieldType=int, textReplace=("Col", ""))
        for iC, edit in enumerate(self.dataYEdits):
            self.updateDataFromEdit(edit, 'dataFormat', 'usecols', iC+1,
                                    fieldType=int, textReplace=("Col", ""))
        self.updateDataFromEdit(self.dataXEditTimes, 'dataFormat', 'xFactor',
                                fieldType=float)
        needReplot = False
        for it in csi.selectedItems:
            if it.hasChanged:
                needReplot = True
                it.read_data()
                it.hasChanged = False
        if needReplot:
            self.node.widget.replot()
            for subnode in self.node.downstreamNodes:
                subnode.widget.replot()

    def getFormatDict(self):
        res = {}
        try:
            for rb, ed, kw in zip(
                    self.radioButtons, self.edits, self.headerKW):
                if rb.isChecked():
                    txt = ed.text()
                    if kw == 'skiprows':
                        txt = int(txt)
                    res[kw] = txt

            cols = [int(self.dataXEdit.text().replace("Col", ""))]
            for edit in self.dataYEdits:
                cols.append(int(edit.text().replace("Col", "")))
            res['usecols'] = cols

            txt = self.dataXEditTimes.text()
            if txt:
                res['xFactor'] = float(txt)
        except:
            return
        return res
