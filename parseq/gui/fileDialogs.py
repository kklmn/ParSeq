# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "22 Apr 2021"
# !!! SEE CODERULES.TXT !!!

import os
from silx.gui import qt
from ..core import singletons as csi
from ..core import commons as cco

ftypes = 'HDF5', 'pickle', 'json (for 1D)', 'column text (for 1D)'
fexts = 'h5', 'pickle', 'json', 'txt'


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

        selNames = [it.alias for it in csi.selectedItems]
        combinedNames = cco.combine_names(selNames)
        sellen = len(csi.selectedItems)
        exportStr = 'export data of {0} selected item{1}: {2}'.format(
            sellen, 's' if sellen > 1 else '', combinedNames) if sellen < 4 \
            else 'export data of {0} selected items'.format(sellen)
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
        nodeCB.setChecked(True)
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
        self.saveAsCBs[0].setChecked(True)
        saveDataAs.setLayout(layoutA)
        layoutC.addWidget(saveDataAs)

        layoutP = qt.QVBoxLayout()
        self.scriptCBmpl = qt.QCheckBox(
            'save a matplotlib plotting script\nfor the exported data', self)
        layoutP.addWidget(self.scriptCBmpl, alignment=qt.Qt.AlignTop)
        self.scriptCBsilx = qt.QCheckBox(
            'save a silx plotting script\nfor the exported data', self)
        layoutP.addWidget(self.scriptCBsilx, alignment=qt.Qt.AlignTop)
        layoutP.addStretch()
        layoutC.addLayout(layoutP)

        self.saveData.setLayout(layoutC)
        self.layout().addWidget(
            self.saveData, self.layout().rowCount(), 0, 1, 2)
        self.layout().setRowStretch(self.layout().rowCount(), 0)

        self.finished.connect(self.onFinish)

    def onFinish(self, result):
        if not result:
            return
        resFile = self.selectedFiles()
        saveData = self.saveData.isChecked()
        if not saveData:
            self.ready.emit([resFile])
            return
        saveNodes = [node.isChecked() for node in self.saveNodeCBs]
        asTypes = [ext for ftype, ext in zip(self.saveAsCBs, fexts)
                   if ftype.isChecked()]
        saveScriptMpl = self.scriptCBmpl.isChecked()
        saveScriptSilx = self.scriptCBsilx.isChecked()
        self.ready.emit(
            [resFile, saveNodes, asTypes, saveScriptMpl, saveScriptSilx])


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

        self.previewLabel = qt.QLabel('Preview', self)
        self.previewLabel.setScaledContents(True)
        layout.addWidget(self.previewLabel)

        self.previewSlider = qt.QSlider(qt.Qt.Horizontal)
        self.previewSlider.setTickPosition(qt.QSlider.TicksAbove)
        self.previewSlider.setVisible(False)
        self.previewSlider.valueChanged.connect(self.sliderValueChanged)
        layout.addWidget(self.previewSlider)

        self.pms = []
        self.pmIndex = 1e6
        self.previewContent = qt.QLabel(self)
        layout.addWidget(self.previewContent, 1)
        layout.addStretch()

        self.setLayout(layout)
        self.setMinimumWidth(400)

    def resizeEvent(self, ev):
        self.updatePreview()

    def updatePreview(self):
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
        # self.setProxyModel(QTooltipProxyModel(self))

        self.currentChanged.connect(self.updatePreview)
        self.finished.connect(self.onFinish)

        self.splitter = self.layout().itemAtPosition(1, 0).widget()
        self.previewPanel = QPreviewPanel(self)
        self.splitter.addWidget(self.previewPanel)

        self.setMinimumWidth(1200)

    def updatePreview(self, path):
        if path.endswith('.pspj'):
            fname = path.replace('.pspj', '')
        else:
            return
        self.previewPanel.pms = []
        self.previewPanel.pmNames = []
        for i, (name, node) in enumerate(csi.nodes.items()):
            pngName = fname + '-{0}-{1}.png'.format(i+1, name)
            pmName = u'{0} \u2013 {1}'.format(i+1, name)
            if os.path.exists(pngName):
                self.previewPanel.pms.append(qt.QPixmap(pngName))
                self.previewPanel.pmNames.append(pmName)
        self.previewPanel.updatePreview()

    def onFinish(self, result):
        if not result:
            return
        resFile = self.selectedFiles()
        self.ready.emit([resFile])
