# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from .propWidget import QLineEditSelectRB, PropWidget
# from . import propsOfData as gpd


class ColumnFormatWidget(PropWidget):
    def __init__(self, parent=None, node=None):
        super(ColumnFormatWidget, self).__init__(parent, node)
        self.shouldRemoveNonesFromProps = True

        self.tabWidget = qt.QTabWidget(self)
        self.tabWidget.setStyleSheet(
            # "QTabBar::tab:selected {background: palette(window);}"
            "QTabWidget>QWidget>QWidget{background: palette(window);}")
        self.headerTab = self.makeHeaderTab()
        self.tabWidget.addTab(self.headerTab, 'file header')
        self.dataLocationTab = self.makeDataLocationTab()
        ind = self.tabWidget.addTab(self.dataLocationTab, 'data location')
        self.tabWidget.setTabToolTip(
            ind, "Use context menu on one or more HDF5/SPEC datasets.\n"
            "For column files use functions of variables `Col1`, `Col2` etc")
        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabWidget)
        layout.addStretch()
        self.setLayout(layout)

        self.tabWidget.setCurrentIndex(1)
        self.registerPropGroup(
            self, [self.headerTab, self.dataLocationTab], 'data format')

    def makeHeaderTab(self):
        self.headerNRB = qt.QRadioButton("has")
        self.headerNEdit = QLineEditSelectRB(rb=self.headerNRB)
        self.headerNEdit.setFixedWidth(28)
        self.headerNEdit.setValidator(
            qt.QIntValidator(0, cco.MAX_HEADER_LINES, self))
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
        self.fullHeaderKW = ['dataFormat.' + kw for kw in self.headerKW]
        self.radioButtons = self.headerNRB, self.headerSRB, self.headerERB
        self.edits = self.headerNEdit, self.headerSEdit, self.headerEEdit

        self.registerExclusivePropGroup(
            headerTab, [self.radioButtons, self.edits], 'file header',
            props=self.fullHeaderKW, convertTypes=[int, None, None])

        return headerTab

    def makeDataLocationTab(self):
        if self.node is None:
            return

        self.dataEdits = []
        dataLayout = qt.QVBoxLayout()
        for ia, arrayName in enumerate(self.node.arrays):
            role = self.node.getProp(arrayName, 'role')
            if role.startswith('0'):
                continue
            arrayLayout = qt.QHBoxLayout()
            arrayLayout.setContentsMargins(0, 0, 0, 0)
            lbl = self.node.getProp(arrayName, 'qLabel')
            unit = self.node.getProp(arrayName, 'qUnit')
            strUnit = u"({0})".format(unit) if unit else ""
            dataLabel = qt.QLabel(u"{0}{1}".format(lbl, strUnit))
            dataEdit = qt.QLineEdit()
            dataEdit.setMinimumWidth(62)
            dataEdit.setSizePolicy(
                qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
            self.dataEdits.append(dataEdit)
            arrayLayout.addWidget(dataLabel)
            arrayLayout.addWidget(dataEdit, 1)
            if role.startswith('x'):
                dataXLabelTimes = qt.QLabel(u"×")
                self.dataXEditTimes = qt.QLineEdit()
                self.dataXEditTimes.setFixedWidth(36)
                arrayLayout.addWidget(dataXLabelTimes)
                arrayLayout.addWidget(self.dataXEditTimes)
                self.registerPropWidget(
                    (dataXLabelTimes, self.dataXEditTimes),
                    dataXLabelTimes.text(),
                    'dataFormat.xFactor', convertType=float, skipDefault=1,
                    textFormat='strip0')
            else:
                self.dataXEditTimes = None
            dataLayout.addLayout(arrayLayout)
            self.registerPropWidget(
                (dataLabel, dataEdit), dataLabel.text(),
                'dataFormat.dataSource.int({0})'.format(ia), convertType=int)
                # ('dataFormat.dataSource', ia), convertType=int)

        dataLocationTab = qt.QWidget(self)
        dataLocationTab.setLayout(dataLayout)
        dataLocationTab.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)

        edits = self.dataEdits
        if self.dataXEditTimes is not None:
            edits += [self.dataXEditTimes]
        self.registerPropGroup(dataLocationTab, edits, 'data location')

        return dataLocationTab

    def setHeaderEnabled(self, enabled=True):
        self.tabWidget.setTabEnabled(0, enabled)
        self.headerTab.setEnabled(enabled)  # to disable context menu entry
        if self.tabWidget.currentIndex() == 0:
            self.tabWidget.setCurrentIndex(1)

    def updateProp(self):
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
        # print([cco.getDotAttr(it, 'dataFormat') for it in csi.selectedItems])

    def getDataFormat(self, needHeader):
        dres = {}
        try:
            if needHeader:
                for rb, ed, kw in zip(
                        self.radioButtons, self.edits, self.headerKW):
                    if rb.isChecked():
                        txt = ed.text()
                        if kw == 'skiprows':
                            txt = int(txt)
                        dres[kw] = txt

            cols = [edit.text() for edit in self.dataEdits]
            dres['dataSource'] = cols

            if self.dataXEditTimes is not None:
                txt = self.dataXEditTimes.text()
                if txt:
                    dres['xFactor'] = float(txt)
        except:  # noqa
            return
        return dres
