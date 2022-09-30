# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "19 Jul 2022"
# !!! SEE CODERULES.TXT !!!

from functools import partial

from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from .propWidget import QLineEditSelectRB, PropWidget
from . import gcommons as gco
# from . import propsOfData as gpd


class ColumnFormatWidget(PropWidget):
    def __init__(self, parent=None, node=None):
        super().__init__(parent, node)
        self.shouldRemoveNonesFromProps = True

        self.tabWidget = qt.QTabWidget(self)
        self.tabWidget.setStyleSheet(
            "QTabWidget>QWidget>QWidget {background: palette(window);}"
            "QTabBar::tab {padding:4px;padding-left:6px;padding-right:6px;}"
            "QTabBar::tab:selected {background: white;}"
            "QTabBar::tab:hover {background: #6087cefa;}"
            )

        self.headerTab = self.makeHeaderTab()
        self.tabWidget.addTab(self.headerTab, 'header')

        self.dataLocationTab = self.makeDataLocationTab()
        ind = self.tabWidget.addTab(self.dataLocationTab, 'arrays')
        self.tabWidget.setTabToolTip(
            ind, "for HDF5/SPEC datasets: use context menu on data arrays\n"
            "for column files: use expressions of variables `Col1`, `Col2`, …"
            "\nor give a zero-based int column index")

        self.conversionTab = self.makeConversionTab()
        ind = self.tabWidget.addTab(self.conversionTab, 'conversion')
        self.tabWidget.setTabToolTip(
            ind, "give either a float factor,\n"
            "a new str unit (not for abscissa) or\n"
            "leave empty (no conversion)")

        self.metadataTab = self.makeMetadataTab()
        ind = self.tabWidget.addTab(self.metadataTab, 'metadata')
        self.tabWidget.setTabToolTip(
            ind, "give a set of hdf5 paths by using the right-click menu;\n"
            "these str fields will appear in the 'metadata' widget under the"
            " plot")
        self.metadata = {}  # {str: StrLabelWithCloseButton}

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
        headerLayout.setContentsMargins(2, 0, 0, 0)
        headerLayout.addLayout(headerLayoutN)
        headerLayout.addLayout(headerLayoutS)
        headerLayout.addLayout(headerLayoutE)
        headerLayout.addStretch()

        tab = qt.QWidget(self)
        tab.setLayout(headerLayout)
        tab.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)

        self.headerKW = 'skiprows', 'comments', 'lastSkipRowContains'
        self.fullHeaderKW = ['dataFormat.' + kw for kw in self.headerKW]
        self.radioButtons = self.headerNRB, self.headerSRB, self.headerERB
        self.edits = self.headerNEdit, self.headerSEdit, self.headerEEdit

        self.registerExclusivePropGroupWithEdits(
            tab, [self.radioButtons, self.edits], 'header',
            props=self.fullHeaderKW, convertTypes=[int, None, None])

        return tab

    def makeDataLocationTab(self):
        if self.node is None:
            return

        self.dataEdits = []
        self.sliceEdits = []
        dataLayout = qt.QVBoxLayout()
        dataLayout.setContentsMargins(2, 0, 0, 0)
        for ia, arrayName in enumerate(self.node.arrays):
            role = self.node.get_prop(arrayName, 'role')
            if role.startswith('0'):
                continue
            arrayLayout = qt.QHBoxLayout()
            arrayLayout.setContentsMargins(0, 0, 0, 0)
            lbl = self.node.get_prop(arrayName, 'qLabel')
            unit = self.node.get_prop(arrayName, 'qUnit')
            if unit:
                lbl += '({0})'.format(unit)
            dataLabel = qt.QLabel(lbl)
            dataEdit = qt.QLineEdit()
            dataEdit.setMinimumWidth(62)
            dataEdit.setSizePolicy(
                qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
            self.dataEdits.append(dataEdit)
            sliceEdit = qt.QLineEdit()
            sliceEdit.setSizePolicy(
                qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
            self.sliceEdits.append(sliceEdit)
            sliceEdit.textChanged.connect(
                partial(self._resizeToContent, sliceEdit))
            sliceEdit.hide()
            arrayLayout.addWidget(dataLabel)
            arrayLayout.addWidget(dataEdit, 1)
            arrayLayout.addWidget(sliceEdit, 0)
            dataLayout.addLayout(arrayLayout)
            self.registerPropWidget(
                (dataLabel, dataEdit), dataLabel.text(),
                # ('dataFormat.dataSource', ia), convertType=int)
                'dataFormat.dataSource.int({0})'.format(ia), convertType=int)
            self.registerPropWidget(
                sliceEdit, 'slice', 'dataFormat.slices.int({0})'.format(ia),
                hideEmpty=True)

        tab = qt.QWidget(self)
        tab.setLayout(dataLayout)
        tab.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)

        self.registerPropGroup(tab, self.dataEdits, 'data location')

        return tab

    def makeConversionTab(self):
        if self.node is None:
            return

        self.conversionEdits = []
        dataLayout = qt.QVBoxLayout()
        dataLayout.setContentsMargins(2, 0, 0, 0)
        for ia, arrayName in enumerate(self.node.arrays):
            role = self.node.get_prop(arrayName, 'role')
            if role.startswith('0'):
                continue
            arrayLayout = qt.QHBoxLayout()
            arrayLayout.setContentsMargins(0, 0, 0, 0)
            lbl = self.node.get_prop(arrayName, 'qLabel')
            unit = self.node.get_prop(arrayName, 'qUnit')
            if unit:
                lbl += '({0})'.format(unit)
            dataLabel = qt.QLabel(lbl)
            conversionEdit = qt.QLineEdit()
            conversionEdit.setMinimumWidth(62)
            conversionEdit.setSizePolicy(
                qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
            self.conversionEdits.append(conversionEdit)
            arrayLayout.addWidget(dataLabel)
            arrayLayout.addWidget(conversionEdit, 1)
            dataLayout.addLayout(arrayLayout)
            self.registerPropWidget(
                (dataLabel, conversionEdit), dataLabel.text(),
                'dataFormat.conversionFactors.int({0})'.format(ia),
                emptyMeans=None, convertType=float)

        tab = qt.QWidget(self)
        tab.setLayout(dataLayout)
        tab.setSizePolicy(qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)

        self.registerPropGroup(tab, self.conversionEdits, 'data units')

        return tab

    def makeMetadataTab(self):
        if self.node is None:
            return

        tab = qt.QWidget(self)
        self.metadataLayout = gco.FlowLayout()
        tab.setLayout(self.metadataLayout)

        return tab

    def _resizeToContent(self, edit, text):
        # edit = self.sender()
        fm = qt.QFontMetrics(edit.font())
        edit.setFixedWidth(fm.width('['+text+']'))
        self.adjustSize()

    def setHeaderEnabled(self, enabled=True):
        self.tabWidget.setTabEnabled(0, enabled)
        self.headerTab.setEnabled(enabled)  # to disable context menu entry
        if self.tabWidget.currentIndex() == 0:
            self.tabWidget.setCurrentIndex(1)

    def setMetadataEnabled(self, enabled=True):
        self.tabWidget.setTabEnabled(3, enabled)
        self.metadataTab.setEnabled(enabled)  # to disable context menu entry
        if self.tabWidget.currentIndex() == 3:
            self.tabWidget.setCurrentIndex(1)

    def updateProp(self):
        needReplot = False
        for it in csi.selectedItems:
            if it.hasChanged:
                needReplot = True
                it.read_data()
                it.hasChanged = False
        if needReplot:
            self.node.widget.replot(keepExtent=False)
            for subnode in self.node.downstreamNodes:
                subnode.widget.replot(keepExtent=False)
        # print([cco.getDotAttr(it, 'dataFormat') for it in csi.selectedItems])

    def getDataFormat(self, needHeader):
        def try_float(txt):
            try:
                return float(txt)
            except Exception:
                return txt

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
            slices = [edit.text() for edit in self.sliceEdits]
            if slices.count('') != len(slices):
                dres['slices'] = slices
            convs = [try_float(edit.text()) for edit in self.conversionEdits]
            dres['conversionFactors'] = convs
            dres['metadata'] = ', '.join(self.metadata.keys())
        except:  # noqa
            return
        return dres

    def setTexts(self, formats, section, edits):
        if section not in formats:
            return
        try:
            params = eval(formats[section])
        except (SyntaxError, NameError):
            return
        for edit, pStr in zip(edits, params):
            edit.setText(pStr)

    def setMetadata(self, formats, section):
        if section not in formats:
            return
        toAdd = [s.strip() for s in formats[section].split(',')]
        for path in self.metadata:
            if path not in toAdd:
                self._deleteMetadataLabel(path)
        self.addMetadata(toAdd)

    def addMetadata(self, metas):
        for path in metas:
            if path in self.metadata:
                continue
            metadataLabel = gco.StrLabelWithCloseButton(self, path)
            metadataLabel.delete.connect(self._deleteMetadataLabel)
            self.metadataLayout.addWidget(metadataLabel)
            self.metadata[path] = metadataLabel

    def _deleteMetadataLabel(self, path):
        metadataLabel = self.metadata[path]
        try:
            metadataLabel.delete.disconnect(self._deleteMetadataLabel)
        except TypeError:  # 'method' object is not connected
            pass
        self.metadataLayout.removeWidget(metadataLabel)
        metadataLabel.close()
        del self.metadata[path]

    def setDataFormat(self, formats):
        self.setTexts(formats, 'datasource', self.dataEdits)
        self.setTexts(formats, 'slices', self.sliceEdits)
        self.setTexts(formats, 'conversionfactors', self.conversionEdits)
        self.setMetadata(formats, 'metadata')
