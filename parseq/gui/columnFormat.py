# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "2 Mar 2023"
# !!! SEE CODERULES.TXT !!!

from functools import partial

from silx.gui import qt

from ..core import singletons as csi
from ..core import commons as cco
from ..core import config
from ..core.logger import syslogger
from .propWidget import QLineEditSelectRB, PropWidget
from . import gcommons as gco
# from . import propsOfData as gpd


class ColumnFormatWidget(PropWidget):
    def __init__(self, parent=None, node=None):
        super().__init__(parent, node)
        self.shouldRemoveNonesFromProps = True
        self.fileType = ''  # or 'txt' or 'h5', used in format saving

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
            ind, "For HDF5/SPEC datasets: use context menu on data arrays.\n"
            "For column files: use expressions of variables `Col0`, `Col1`, …"
            "\n(zero-based!) or give a zero-based int column index.\n"
            "numpy can be used as `np`. Example: `np.log(Col6/Col7)`")

        self.conversionTab = self.makeConversionTab()
        ind = self.tabWidget.addTab(self.conversionTab, 'conversion')
        self.tabWidget.setTabToolTip(
            ind, "Give one of:\n"
            "1) a float factor,\n"
            "2) a new str unit (not for abscissa),\n"
            "3) lim(min, max) (typ. for abscissa), e.g. lim(None, 9900)\n"
            "4) transpose(*axes), e.g. transpose(2, 1, 0)\n"
            "5) leave empty (no conversion).")

        self.metadataTab = self.makeMetadataTab()
        ind = self.tabWidget.addTab(self.metadataTab, 'metadata')
        self.tabWidget.setTabToolTip(
            ind, "Give a set of hdf5 paths by using the right-click menu.\n"
            "These str fields will appear in the 'metadata' widget under the"
            " plot")
        self.metadata = {}  # {str: StrLabelWithCloseButton}

        self.saveTab = self.makeSaveTab()
        ind = self.tabWidget.addTab(self.saveTab, 'save')
        self.tabWidget.setTabToolTip(
            ind, "Specify a few substrings from 'metadata' panel to recognize "
            "this format.\nAll recognized formats for column files or hdf5 \n"
            "entries will appear in the popup menu in the file tree.")

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
        self.headerSEdit.setText('#')
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
            ndim = self.node.get_prop(arrayName, 'ndim')
            if unit:
                lbl += '({0})'.format(unit)
            dataLabel = qt.QLabel(lbl)
            dataLabel.setToolTip('{0}D'.format(ndim))
            dataEdit = qt.QLineEdit()
            dataEdit.setMinimumWidth(62)
            if role == 'optional':
                dataEdit.setPlaceholderText('non-mandatory')
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
        dataLayout.addStretch()
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
        dataLayout.addStretch()
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

    def makeSaveTab(self):
        if self.node is None:
            return

        saveLayout = qt.QVBoxLayout()
        saveLayout.setContentsMargins(2, 0, 0, 0)
        labelDescr = qt.QLabel("key words to recognize the format")
        saveLayout.addWidget(labelDescr)

        inLayout = qt.QHBoxLayout()
        inLayout.setContentsMargins(0, 0, 0, 0)
        inLabel = qt.QLabel("present key words")
        self.saveInEdit = qt.QLineEdit()
        self.saveInEdit.setMinimumWidth(62)
        self.saveInEdit.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
        self.saveInEdit.setToolTip("comma separated words, must be non-empty")
        inLayout.addWidget(inLabel)
        inLayout.addWidget(self.saveInEdit)
        saveLayout.addLayout(inLayout)

        outLayout = qt.QHBoxLayout()
        outLayout.setContentsMargins(0, 0, 0, 0)
        outLabel = qt.QLabel("absent key words")
        self.saveOutEdit = qt.QLineEdit()
        self.saveOutEdit.setMinimumWidth(62)
        self.saveOutEdit.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
        self.saveOutEdit.setToolTip("comma separated words, optional")
        outLayout.addWidget(outLabel)
        outLayout.addWidget(self.saveOutEdit)
        saveLayout.addLayout(outLayout)

        nameLayout = qt.QHBoxLayout()
        nameLayout.setContentsMargins(0, 0, 0, 0)
        nameLabel = qt.QLabel("format name")
        self.saveNameEdit = qt.QLineEdit()
        self.saveNameEdit.setMinimumWidth(62)
        self.saveNameEdit.setSizePolicy(
            qt.QSizePolicy.Expanding, qt.QSizePolicy.Fixed)
        self.saveButton = qt.QPushButton('Save')
        self.saveButton.setToolTip("to enable, highlight a loadable (green)"
                                   " entry in the file tree")
        self.saveButton.clicked.connect(self.doSaveFormat)

        nameLayout.addWidget(nameLabel)
        nameLayout.addWidget(self.saveNameEdit)
        nameLayout.addWidget(self.saveButton)
        saveLayout.addLayout(nameLayout)

        tab = qt.QWidget(self)
        saveLayout.addStretch()
        tab.setLayout(saveLayout)
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
                it.read_data(runDownstream=True)
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

            # cols = [edit.text() for edit in self.dataEdits]
            cols = []
            for edit in self.dataEdits:
                txt = edit.text()
                try:
                    txt = int(txt)
                except Exception:
                    pass
                cols.append(txt)
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

    def setHeader(self, fmt):
        fmtl = {k.lower(): v for k, v in fmt.items()}
        for rb, ed, kw in zip(
                self.radioButtons, self.edits, self.headerKW):
            if kw.lower() in fmtl:
                rb.setChecked(True)
                ed.setText(fmtl[kw.lower()])
            else:
                rb.setChecked(False)

    def setTexts(self, fmt, section, edits):
        fmtl = {k.lower(): v for k, v in fmt.items()}
        sectionl = section.lower()
        if sectionl not in fmtl:
            return
        try:
            params = fmtl[sectionl]
            if isinstance(params, str):
                params = eval(params)
        except Exception as e:
            syslogger.error('{0} {1}:\n{2}'.format(sectionl, params, e))
            return
        for edit, pStr in zip(edits, params):
            edit.setText(str(pStr))

    def setMetadata(self, fmt, section):
        fmtl = {k.lower(): v for k, v in fmt.items()}
        sectionl = section.lower()
        if sectionl not in fmtl:
            return
        toAdd = [s.strip() for s in fmtl[sectionl].split(',')]
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

    def setDataFormat(self, fmt):
        self.setHeader(fmt)
        self.setTexts(fmt, 'datasource', self.dataEdits)
        self.setTexts(fmt, 'slices', self.sliceEdits)
        self.setTexts(fmt, 'conversionfactors', self.conversionEdits)
        self.setMetadata(fmt, 'metadata')

    def doSaveFormat(self):
        if self.node is None:
            return
        txtName = self.saveNameEdit.text()
        if len(txtName) == 0:
            return
        inKeysTxt = self.saveInEdit.text()
        if len(inKeysTxt) == 0:
            return
        kind = self.fileType
        if kind not in ['txt', 'h5']:
            raise ValueError("unknown file type")
        secName = ':'.join((self.node.name, kind))
        if secName in config.configFormats:
            if txtName in config.configFormats[secName]:
                msg = qt.QMessageBox()
                msg.setIcon(qt.QMessageBox.Question)
                res = msg.question(
                    self, "The format name {0} already exists".format(txtName),
                    "Do you want to overwrite it in .parseq/formats.ini ?",
                    qt.QMessageBox.Yes | qt.QMessageBox.No, qt.QMessageBox.Yes)
                if res == qt.QMessageBox.No:
                    return

        outKeysTxt = self.saveOutEdit.text()
        inKeys = [s.strip() for s in inKeysTxt.split(',')]
        outKeys = [s.strip() for s in outKeysTxt.split(',')]

        fmt = self.getDataFormat(kind == 'txt')
        res = dict(dataFormat=fmt, inkeys=inKeys, outkeys=outKeys)
        config.put(config.configFormats, secName, txtName, str(res))
        config.write_configs('formats')
        self.saveButton.setText('Done')
        qt.QTimer.singleShot(3000, self.restoreSaveButton)

    def restoreSaveButton(self):
        self.saveButton.setText('Save')
