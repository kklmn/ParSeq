# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "10 Apr 2022"
# !!! SEE CODERULES.TXT !!!

# from collections import OrderedDict
# from functools import partial

from silx.gui import qt
from silx.gui.plot.tools.roi import (
    RegionOfInterestManager, RoiModeSelectorAction)
from silx.gui.plot.items.roi import ArcROI, RectangleROI

from . import gcommons as gco

ROI_COLOR = '#f7941e'
HEADERS = 'label', 'use', 'geometry'
columnWidths = 45, 32, 140


class RoiManager(RegionOfInterestManager):
    def __init__(self, parent):
        super().__init__(parent)
        self.setColor(ROI_COLOR)
        self.sigRoiAdded.connect(self.updateAddedRegionOfInterest)

    def updateAddedRegionOfInterest(self, roi):
        if roi.getName() == '':
            roi.setName('roi{0}'.format(len(self.getRois())))
        roi.setLineWidth(0.5)
        roi.setLineStyle('-')
        # roi.setSymbolSize(5)
        roi.setSelectable(True)
        roi.setEditable(True)


class RoiModel(qt.QAbstractTableModel):
    def __init__(self, roiManager=None, dim=2):
        super().__init__()
        self.setRoiManager(roiManager)
        roiManager.sigRoiAdded.connect(self.reset)

    def setRoiManager(self, roiManager=None):
        self.beginResetModel()
        if roiManager is not None:
            self.roiManager = roiManager
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def reset(self):
        self.beginResetModel()
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def rowCount(self, parent=qt.QModelIndex()):
        return len(self.roiManager.getRois())

    def columnCount(self, parent):
        return len(HEADERS)

    def headerData(self, section, orientation, role):
        if orientation != qt.Qt.Horizontal:
            return
        if role == qt.Qt.DisplayRole:
            if section < len(HEADERS):
                return HEADERS[section]
            else:
                return section
        elif role == qt.Qt.TextAlignmentRole:
            return qt.Qt.AlignHCenter

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        res = qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable
        column = index.column()
        if column == 1:
            res |= qt.Qt.ItemIsUserCheckable
        else:
            res |= qt.Qt.ItemIsEditable
        return res

    def data(self, index, role=qt.Qt.DisplayRole):
        rois = self.roiManager.getRois()
        if len(rois) == 0:
            return
        if not index.isValid():
            return
        column, row = index.column(), index.row()
        roi = rois[row]
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            if column == 0:  # label
                return roi.getName()
            elif column == 2:  # geometry
                return self.getReadableRoiDescription(roi)
        elif role == qt.Qt.CheckStateRole:
            if column == 1:  # use
                return int(
                    qt.Qt.Checked if roi.isVisible() else qt.Qt.Unchecked)
        elif role == qt.Qt.ToolTipRole:
            return roi.__class__.__name__
        elif role == qt.Qt.TextAlignmentRole:
            if column == 1:
                return qt.Qt.AlignCenter

    def setData(self, index, value, role=qt.Qt.EditRole):
        rois = self.roiManager.getRois()
        if len(rois) == 0:
            return
        if role == qt.Qt.EditRole:
            column, row = index.column(), index.row()
            roi = rois[row]
            if column == 0:  # label
                roi.setName(value)
                return True
            elif column == 2:  # geometry
                return self.setRoiFromTxt(roi, value)
            else:
                return False
        elif role == qt.Qt.CheckStateRole:
            row = index.row()
            roi = rois[row]
            roi.setVisible(bool(value))
            return True
        return False

    def getRoiGeometry(self, roi):
        """Returns a dict that can be used directly in `roi.setGeometry()`."""
        if isinstance(roi, RectangleROI):
            return dict(origin=roi.getOrigin(), size=roi.getSize())
        elif isinstance(roi, ArcROI):
            geom = roi._geometry
            return dict(center=geom.center, innerRadius=roi.getInnerRadius(),
                        outerRadius=roi.getOuterRadius(),
                        startAngle=geom.startAngle, endAngle=geom.endAngle)
        else:
            return dict()

    def getReadableRoiDescription(self, roi):
        if isinstance(roi, RectangleROI):
            x, y = roi.getOrigin()
            w, h = roi.getSize()
            text = 'origin: {0:.1f}, {1:.1f}\nwidth: {2:.1f}\nheight: {3:.1f}'\
                .format(x, y, w, h)
        elif isinstance(roi, ArcROI):
            geom = roi._geometry
            x, y = geom.center
            innerR, outerR = roi.getInnerRadius(), roi.getOuterRadius()
            startAngle, endAngle = geom.startAngle, geom.endAngle
            text = 'center: {0:.1f}, {1:.1f}\nradii: {2:.1f}, {3:.1f}\n'\
                'angles: {4:.3f}, {5:.3f}'.format(
                    x, y, innerR, outerR, startAngle, endAngle)
        else:
            text = ''
        return text

    def setRoiFromTxt(self, roi, txt):
        try:
            txt = txt.replace(':', '=(')
            res = {}
            for row in txt.split('\n'):
                res.update(eval('dict({0}))'.format(row)))
            # print(res)
            if isinstance(roi, RectangleROI):
                kw = dict(origin=res['origin'],
                          size=(res['width'], res['height']))
            elif isinstance(roi, ArcROI):
                kw = dict(
                    center=res['center'],
                    innerRadius=res['radii'][0], outerRadius=res['radii'][1],
                    startAngle=res['angles'][0], endAngle=res['angles'][1])
            else:
                return False
            self.setRoi(roi, kw)
            return True
        except Exception as e:
            print(e)
            return False

    def setRoi(self, roi, kw):
        roi.setGeometry(**kw)


class RoiToolBar(qt.QToolBar):
    """A toolbar which hide itself if no actions are visible"""

    def __init__(self, parent, roiManager):
        super().__init__(parent)
        self.setIconSize(qt.QSize(24, 24))

        # to add more, add classes from:
        # silx.gui.plot.items.roi.RegionOfInterestManager.ROI_CLASSES
        action = roiManager.getInteractionModeAction(ArcROI)
        self.addAction(action)
        action = roiManager.getInteractionModeAction(RectangleROI)
        self.addAction(action)

        self.modeSelectorAction = RoiModeSelectorAction()
        self.modeSelectorAction.setRoiManager(roiManager)
        self.addAction(self.modeSelectorAction)

    def actionEvent(self, event):
        if event.type() == qt.QEvent.ActionChanged:
            self._updateVisibility()
        try:
            return super().actionEvent(event)
        except RuntimeError:
            return

    def _updateVisibility(self):
        self.modeSelectorAction.setVisible(self.modeSelectorAction.isVisible())


class RoiTableView(qt.QTableView):
    def __init__(self, parent, roiManager, dim):
        super().__init__(parent)
        self.roiModel = RoiModel(roiManager, dim)
        self.setModel(self.roiModel)

        self.setSelectionMode(qt.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(qt.QAbstractItemView.SelectRows)
        self.selectionModel().selectionChanged.connect(self.selChanged)

        horHeaders = self.horizontalHeader()  # QHeaderView instance
        horHeaders.setHighlightSections(False)
        verHeaders = self.verticalHeader()  # QHeaderView instance
        verHeaders.setVisible(False)

        if 'pyqt4' in qt.BINDING.lower():
            horHeaders.setMovable(False)
            for i in range(len(HEADERS)):
                horHeaders.setResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setClickable(True)
            verHeaders.setResizeMode(qt.QHeaderView. ResizeToContents)
        else:
            horHeaders.setSectionsMovable(False)
            for i in range(len(HEADERS)):
                horHeaders.setSectionResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setSectionsClickable(True)
            verHeaders.setSectionResizeMode(qt.QHeaderView. ResizeToContents)
        horHeaders.setStretchLastSection(True)
        horHeaders.setMinimumSectionSize(20)
        # verHeaders.setMinimumSectionSize(70)

        self.setItemDelegateForColumn(2, gco.MultiLineEditDelegate(self))

        for i in range(len(HEADERS)):
            self.setColumnWidth(i, columnWidths[i])
        self.setMinimumWidth(sum(columnWidths) + 2)
        self.setMinimumHeight(horHeaders.height()*4)

        roiManager.sigCurrentRoiChanged.connect(self.currentRoiChanged)

    def selChanged(self):
        if not self.hasFocus():
            return
        selectedIndex = self.selectionModel().selectedRows()[0]
        manager = self.roiModel.roiManager
        manager.setCurrentRoi(manager.getRois()[selectedIndex.row()])

    def currentRoiChanged(self, roi):
        rois = self.roiModel.roiManager.getRois()
        try:
            self.selectRow(rois.index(roi))
        except Exception:
            pass


class RoiWidget(qt.QWidget):
    maxVisibleTableRows = 4

    def __init__(self, parent, plot):
        super().__init__(parent)
        self.plot = plot
        self.isStack = hasattr(self.plot, '_plot')
        if self.isStack:
            self.roiManager = RoiManager(plot._plot)
        else:
            self.roiManager = RoiManager(plot)
        self.bypassRoiUpdate = False

        layout = qt.QVBoxLayout()
        # layout.setContentsMargins(0, 0, 0, 0)
        roiToolbar = RoiToolBar(self, self.roiManager)
        layout.addWidget(roiToolbar)
        self.table = RoiTableView(self, self.roiManager, plot)
        layout.addWidget(self.table)
        if self.isStack:
            layoutF = qt.QHBoxLayout()
            keyFrameLabel = qt.QLabel('Key frames')
            layoutF.addWidget(keyFrameLabel)
            self.keyFramesFrame = qt.QFrame(self)
            layoutF.addWidget(self.keyFramesFrame, 1)
            self.keyFramesLayout = gco.FlowLayout()
            self.keyFramesLayout.setSpacing(4)
            self.keyFramesFrame.setLayout(self.keyFramesLayout)
            # self.keyFrameEdit = qt.QLineEdit()
            # layoutF.addWidget(self.keyFrameEdit, 1)
            layout.addLayout(layoutF)
            self.keyFrames = {}
            plot.sigFrameChanged.connect(self.updateFrameNumber)
            self.roiManager.sigRoiAboutToBeRemoved.connect(
                self._removeRoiFromKeys)
        layout.addStretch()
        self.setLayout(layout)

        self.roiManager.sigRoiChanged.connect(self.syncRoi)

    def updateFrameNumber(self, ind):
        if len(self.keyFrames) < 2:
            return
        rois = self.roiManager.getRois()
        model = self.table.roiModel
        keys = list(sorted(self.keyFrames))
        if ind <= keys[0]:
            savedRois = self.keyFrames[keys[0]]['geometries']
            for roi, savedRoi in zip(rois, savedRois):
                self.bypassRoiUpdate = True
                model.setRoi(roi, savedRoi)
            return
        elif ind >= keys[-1]:
            savedRois = self.keyFrames[keys[-1]]['geometries']
            for roi, savedRoi in zip(rois, savedRois):
                self.bypassRoiUpdate = True
                model.setRoi(roi, savedRoi)
            return
        for ikey in range(len(keys)-1):
            if keys[ikey] <= ind < keys[ikey+1]:
                break
        else:
            raise ValueError('wrong key frames')

        # linear interpolation between ikey and ikey+1:
        savedRois0 = self.keyFrames[keys[ikey]]['geometries']
        savedRois1 = self.keyFrames[keys[ikey+1]]['geometries']
        for roi in rois:
            rr = (ind-keys[ikey]) / (keys[ikey+1]-keys[ikey])
            for roi, savedRoi0, savedRoi1 in zip(rois, savedRois0, savedRois1):
                savedRoi = {k0: (v1-v0)*rr + v0 for (k0, v0), (k1, v1) in zip(
                    savedRoi0.items(), savedRoi1.items())}
                self.bypassRoiUpdate = True
                model.setRoi(roi, savedRoi)

    def syncRoi(self):
        rois = self.roiManager.getRois()
        horHeaders = self.table.horizontalHeader()
        rows = min(len(rois), self.maxVisibleTableRows)
        heights = sum([self.table.rowHeight(i) for i in range(rows)])
        newHeight = horHeaders.height() + 2 + heights
        self.table.setFixedHeight(newHeight)

        curRoi = self.roiManager.getCurrentRoi()
        model = self.table.roiModel
        if not self.bypassRoiUpdate:
            if self.isStack:
                key = self.plot._browser.value()
                if key not in self.keyFrames:
                    self.keyFrames[key] = {}
                self.keyFrames[key]['classNames'] = [
                    roi.__class__.__name__ for roi in rois]
                self.keyFrames[key]['geometries'] = [
                    model.getRoiGeometry(roi) for roi in rois]
                self.keyFrames[key]['ids'] = [id(roi) for roi in rois]
                if 'widget' not in self.keyFrames[key]:
                    keyFrameWidget = gco.KeyFrameWithCloseButton(
                        self.keyFramesFrame, key)
                    keyFrameWidget.deleteFrame.connect(self._deleteKeyFrame)
                    self.keyFrames[key]['widget'] = keyFrameWidget
                    self.keyFramesLayout.addWidget(keyFrameWidget)
                # self.keyFrameEdit.setText(
                #     ', '.join(str(k) for k in self.keyFrames.keys()))
            if curRoi is not None:
                row = rois.index(curRoi)
                ind = model.index(row, 2)
                model.dataChanged.emit(ind, ind)
            else:
                model.reset()
        else:
            self.bypassRoiUpdate = False
            ind0 = model.index(0, 2)
            inde = model.index(len(rois)-1, 2)
            model.dataChanged.emit(ind0, inde)

    def _deleteKeyFrame(self, key):
        if key in self.keyFrames:
            self.keyFramesLayout.removeWidget(self.keyFrames[key]['widget'])
            self.keyFrames[key]['widget'].close()
            del self.keyFrames[key]

    def _removeRoiFromKeys(self, roiRemove):
        for key in self.keyFrames:
            fr = self.keyFrames[key]
            for iroi, id_ in enumerate(fr['ids']):
                if id_ == id(roiRemove):
                    del fr['classNames'][iroi]
                    del fr['geometries'][iroi]
                    del fr['ids'][iroi]
                    break
