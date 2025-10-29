# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "29 Oct 2025"
# !!! SEE CODERULES.TXT !!!

import os
from silx.gui import qt
from ..core import singletons as csi
from ..core import commons as cco
from ..core import config

ftypes = 'HDF5', 'pickle', 'json (for 1D)', 'txt (for 1D)', 'txt.gz (for 1D)'
fexts = 'h5', 'pickle', 'json', 'txt', 'txt.gz'


class SaveProjectDlg(qt.QFileDialog):
    ready = qt.pyqtSignal(list)

    def __init__(self, parent=None, dirname=''):
        super().__init__(
            parent=parent, caption='Save project', directory=dirname)
        self.setOption(qt.QFileDialog.DontUseNativeDialog, True)
        self.setAcceptMode(qt.QFileDialog.AcceptSave)
        self.setFileMode(qt.QFileDialog.AnyFile)
        self.setViewMode(qt.QFileDialog.Detail)
        self.setNameFilter("ParSeq Project File (*.pspj)")
        try:  # hide all other files, otherwise they are greyed out
            child = self.findChild(qt.QTreeView)
            model = child.model()
            model.setNameFilterDisables(False)
        except Exception:
            pass

        selNames = [it.alias for it in csi.selectedItems]
        combinedNames = cco.combine_names(selNames)
        sellen = len(csi.selectedItems)
        if sellen < 4:
            exportStr = 'export data of {0} selected item{1}: {2}'.format(
                sellen, 's' if sellen > 1 else '', combinedNames)
        else:
            exportStr = 'export data of {0} selected items'.format(sellen)
            exportStr += ' ordered as shown in the main window status line'
        self.saveData = qt.QGroupBox(exportStr, self)
        self.saveData.setCheckable(True)
        self.saveData.setChecked(True)

        layoutC = qt.QHBoxLayout()
        layoutC.setContentsMargins(0, 2, 0, 0)

        saveDataFrom = qt.QGroupBox('from nodes', self)
        layoutF = qt.QVBoxLayout()
        layoutF.setContentsMargins(4, 4, 4, 4)
        self.saveNodeCBs = []
        for i, (name, node) in enumerate(csi.nodes.items()):
            tabName = u'{0} \u2013 {1}'.format(i+1, name)
            nodeCB = qt.QCheckBox(tabName, self)
            self.saveNodeCBs.append(nodeCB)
            layoutF.addWidget(nodeCB)
        layoutF.addStretch()
        nsaved = config.get(config.configLoad, 'Save', 'nodes')
        if nsaved is None:
            nodeCB.setChecked(True)
        else:
            for name, nodeCB in zip(csi.nodes.keys(), self.saveNodeCBs):
                nodeCB.setChecked(name in nsaved)
        saveDataFrom.setLayout(layoutF)
        layoutC.addWidget(saveDataFrom)

        saveDataAs = qt.QGroupBox('as', self)
        layoutA = qt.QVBoxLayout()
        layoutA.setContentsMargins(4, 4, 4, 4)
        self.saveAsCBs = []
        for i, dtype in enumerate(ftypes):
            asCB = qt.QCheckBox(dtype, self)
            self.saveAsCBs.append(asCB)
            layoutA.addWidget(asCB)
        layoutA.addStretch()
        fsaved = config.get(config.configLoad, 'Save', 'filetypes')
        if fsaved is None:
            self.saveAsCBs[0].setChecked(True)
        else:
            for ftype, saveAsCB in zip(ftypes, self.saveAsCBs):
                saveAsCB.setChecked(ftype in fsaved)
        saveDataAs.setLayout(layoutA)
        layoutC.addWidget(saveDataAs)

        layoutP = qt.QVBoxLayout()
        self.scriptCBmpl = qt.QCheckBox(
            'save a matplotlib plotting script\nfor the exported data', self)
        msaved = config.get(config.configLoad, 'Save', 'scriptMpl')
        self.scriptCBmpl.setChecked(msaved)
        layoutP.addWidget(self.scriptCBmpl, alignment=qt.Qt.AlignTop)
        self.scriptCBsilx = qt.QCheckBox(
            'save a silx plotting script\nfor the exported data', self)
        ssaved = config.get(config.configLoad, 'Save', 'scriptSilx')
        self.scriptCBsilx.setChecked(ssaved)
        layoutP.addWidget(self.scriptCBsilx, alignment=qt.Qt.AlignTop)
        layoutP.addStretch()
        layoutC.addLayout(layoutP)

        self.saveData.setLayout(layoutC)
        self.layout().addWidget(
            self.saveData, self.layout().rowCount(), 0, 1, 2)
        self.layout().setRowStretch(self.layout().rowCount(), 0)

        self.finished.connect(self.onFinish)

        self.setMinimumSize(1000, 700)

    def onFinish(self, result):
        if not result:
            return
        resFile = self.selectedFiles()
        saveData = self.saveData.isChecked()
        if not saveData:
            self.ready.emit([resFile])
            return
        saveNodes = [nodeCB.isChecked() for nodeCB in self.saveNodeCBs]
        asTypes = [ext for saveAsCB, ext in zip(self.saveAsCBs, fexts)
                   if saveAsCB.isChecked()]
        saveScriptMpl = self.scriptCBmpl.isChecked()
        saveScriptSilx = self.scriptCBsilx.isChecked()
        self.ready.emit(
            [resFile, saveNodes, asTypes, saveScriptMpl, saveScriptSilx])

        nchecked = []
        for name, nodeCB in zip(csi.nodes.keys(), self.saveNodeCBs):
            if nodeCB.isChecked():
                nchecked.append(name)
        config.put(config.configLoad, 'Save', 'nodes', '; '.join(nchecked))

        fchecked = []
        for ftype, saveAsCB in zip(ftypes, self.saveAsCBs):
            if saveAsCB.isChecked():
                fchecked.append(ftype)
        config.put(config.configLoad, 'Save', 'filetypes', '; '.join(fchecked))

        config.put(config.configLoad, 'Save', 'scriptMpl', str(saveScriptMpl))
        config.put(
            config.configLoad, 'Save', 'scriptSilx', str(saveScriptSilx))

# class QTooltipProxyModel(qt.QIdentityProxyModel):
#     def data(self, index, role=qt.Qt.DisplayRole):
#         if role == qt.Qt.ToolTipRole:
#             # return '<html><img src="ttt-4-1D energy XES.png"/></html>'
#             return '<img src="ttt-4-1D energy XES.png" ' + \
#                 'style="width: 200px; image-rendering: smooth;" >'
#         else:
#             return super().data(index, role)


class QPreviewPanel(qt.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layoutC = qt.QHBoxLayout()
        layoutC.setContentsMargins(0, 0, 0, 0)
        contentLabel = qt.QLabel('In this project file:', self)
        layoutC.addWidget(contentLabel)
        self.content = qt.QLabel('', self)
        layoutC.addWidget(self.content)
        layoutC.addStretch()
        layout.addLayout(layoutC)

        self.previewLabel = qt.QLabel('Preview', self)
        self.previewLabel.setScaledContents(True)
        layout.addWidget(self.previewLabel)

        self.previewSlider = qt.QSlider(qt.Qt.Horizontal)
        self.previewSlider.setTickPosition(qt.QSlider.TicksAbove)
        self.previewSlider.setVisible(False)
        self.previewSlider.valueChanged.connect(self.sliderValueChanged)
        layout.addWidget(self.previewSlider)

        self.groups = None
        self.items = None
        self.pipelineName = ''
        self.pipelineToolTip = ''
        self.pms = []
        self.pmIndex = 1e6
        self.previewContent = qt.QLabel(self)
        layout.addWidget(self.previewContent, 1)
        layout.addStretch()

        self.setLayout(layout)
        self.setMinimumWidth(300)

    def resizeEvent(self, ev):
        self.updatePreview()

    def updatePreview(self):
        if self.pipelineName:
            txt = '{0}, '.format(self.pipelineName)
        else:
            txt = ''
        txt += '{0} group{1}, '.format(
            self.groups, 's' if self.groups > 1 else '') if self.groups else ''
        txt += '{0} item{1}'.format(
            self.items, 's' if self.items > 1 else '') if self.items else ''
        self.content.setText(txt)
        self.content.setToolTip(self.pipelineToolTip)

        self.previewSlider.setVisible(len(self.pms) > 1)
        if not self.pms:
            self.previewContent.setPixmap(qt.QPixmap())
            self.previewLabel.setText('Preview')
            return
        if self.pmIndex > len(self.pms)-1:
            self.pmIndex = len(self.pms)-1
        elif self.pmIndex < 0:
            self.pmIndex = 0
        if self.pms[self.pmIndex].isNull():
            return
        self.previewSlider.setRange(0, len(self.pms)-1)
        self.previewSlider.setValue(self.pmIndex)
        size = self.size()
        self.previewContent.setMinimumSize(1, 1)
        self.previewContent.setPixmap(
            self.pms[self.pmIndex].scaled(
                size.width(), size.height(),
                aspectRatioMode=qt.Qt.KeepAspectRatio,
                transformMode=qt.Qt.SmoothTransformation))
        self.previewLabel.setText('Preview: ' + self.pmNames[self.pmIndex])

    def sliderValueChanged(self, val):
        self.pmIndex = val
        self.updatePreview()


class LoadProjectDlg(qt.QFileDialog):
    ready = qt.pyqtSignal(list)

    def __init__(self, parent=None, dirname=''):
        super().__init__(
            parent=parent, caption='Load project', directory=dirname)
        self.setOption(qt.QFileDialog.DontUseNativeDialog, True)
        self.setAcceptMode(qt.QFileDialog.AcceptOpen)
        self.setFileMode(qt.QFileDialog.ExistingFile)
        self.setViewMode(qt.QFileDialog.Detail)
        self.setNameFilter("ParSeq Project File (*.pspj)")
        try:  # hide all other files, otherwise they are greyed out
            child = self.findChild(qt.QTreeView)
            model = child.model()
            model.setNameFilterDisables(False)
        except Exception:
            pass
        # self.setProxyModel(QTooltipProxyModel(self))

        self.currentChanged.connect(self.updatePreview)
        self.finished.connect(self.onFinish)

        self.splitter = self.layout().itemAtPosition(1, 0).widget()
        self.previewPanel = QPreviewPanel(self)
        self.splitter.addWidget(self.previewPanel)

        self.setMinimumSize(1000, 500)

    def updatePreview(self, path):
        if path.endswith('.pspj'):
            fname = path.replace('.pspj', '')
        else:
            return

        configProject = config.ConfigParser()
        active = ''
        try:
            configProject.read(path, encoding=config.encoding)
            self.previewPanel.groups = int(configProject.get('Root', 'groups'))
            self.previewPanel.items = int(configProject.get('Root', 'items'))
            if configProject.has_section('ParSeq Application'):
                pName = configProject.get('ParSeq Application', 'pipelineName')
                isOwn = pName == csi.pipelineName
                colorStr = "#008800" if isOwn else "#ff0000"
                self.previewPanel.pipelineName = \
                    "<font color={0}>{1}</font>".format(colorStr, pName)
                self.previewPanel.pipelineToolTip = '' if isOwn else \
                    "this project file was made by another pipeline!"
            else:
                self.previewPanel.pipelineName = ''
            active = config.get(configProject, 'Docks', 'active', '')
        except Exception:
            pass

        self.previewPanel.pmIndex = 0
        self.previewPanel.pms = []
        self.previewPanel.pmNames = []
        curInd = 0
        for i, (name, node) in enumerate(csi.nodes.items()):
            pngName = fname + '-{0}-{1}.png'.format(i+1, name)
            pmName = u'{0} \u2013 {1}'.format(i+1, name)
            if os.path.exists(pngName):
                self.previewPanel.pms.append(qt.QPixmap(pngName))
                self.previewPanel.pmNames.append(pmName)
                if name == active:
                    self.previewPanel.pmIndex = curInd
                curInd += 1
        self.previewPanel.updatePreview()

    def onFinish(self, result):
        if not result:
            return
        resFile = self.selectedFiles()
        self.ready.emit([resFile])
