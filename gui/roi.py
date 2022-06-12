# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "10 Apr 2022"
# !!! SEE CODERULES.TXT !!!

import time
# from collections import OrderedDict
# from functools import partial

from silx.gui import qt
from silx.gui.plot.tools.roi import (
    RegionOfInterestManager, RoiModeSelectorAction)
from silx.gui.plot.items.roi import ArcROI, RectangleROI

from . import gcommons as gco
from ..utils import math as uma

HEADERS = 'label', 'use', 'geometry'
columnWidths = 45, 32, 164


class RoiManager(RegionOfInterestManager):
    def __init__(self, parent):
        super().__init__(parent)
        self.setColor(gco.COLOR_ROI)
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
            return dict(kind='RectangleROI', name=roi.getName(),
                        use=roi.isVisible(),
                        origin=list(roi.getOrigin()), size=list(roi.getSize()))
        elif isinstance(roi, ArcROI):
            geom = roi._geometry
            return dict(kind='ArcROI', name=roi.getName(),
                        use=roi.isVisible(),
                        center=list(geom.center),
                        innerRadius=roi.getInnerRadius(),
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
        # self.setStyleSheet('QToolBar{margin: 0px 10px;}')
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
    maxVisibleTableRows = 4  # in the scroll area

    def __init__(self, parent, plot, wantExtrapolate=True):
        super().__init__(parent)
        self.plot = plot
        self.wantExtrapolate = wantExtrapolate
        self.is3dStack = hasattr(self.plot, '_plot')
        if self.is3dStack:
            self.roiManager = RoiManager(plot._plot)
        else:
            self.roiManager = RoiManager(plot)
        self.bypassForSetup = False
        self.bypassForUpdate = False

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        roiToolbar = RoiToolBar(self, self.roiManager)
        layout.addWidget(roiToolbar)
        self.table = RoiTableView(self, self.roiManager, plot)
        layout.addWidget(self.table)
        if self.is3dStack:
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
            self.keyFrameGeometries = {}
            self.keyFrameWidgets = {}
            plot.sigFrameChanged.connect(self.updateFrameIndex)
            self.roiManager.sigRoiAboutToBeRemoved.connect(
                self._removeRoiFromKeys)
        self.autoZoom = qt.QCheckBox('auto zoom the {0} plot'.format(
            '3D' if self.is3dStack else '2D'))
        self.autoZoom.setChecked(True)
        layout.addWidget(self.autoZoom)
        self.acceptButton = qt.QPushButton('Accept ROIs')
        layout.addWidget(self.acceptButton, 1)
        layout.addStretch()
        self.setLayout(layout)

        self.roiManager.sigRoiChanged.connect(self.syncRoi)

    def updateFrameIndex(self, ind):
        if len(self.keyFrameGeometries) < 2:
            return
        frame0 = list(self.keyFrameGeometries.values())[0]
        for frame in list(self.keyFrameGeometries.values())[1:]:
            for geom0, geom in zip(frame0, frame):
                if len(geom0) != len(geom):
                    raise ValueError(
                        "These geometries must have same key words:\n{0}\n{1}"
                        .format(geom0, geom))
        interpolatedRois = uma.interpolateFrames(
            self.keyFrameGeometries, ind, self.wantExtrapolate)
        rois = self.roiManager.getRois()
        model = self.table.roiModel
        for roi, interpolatedRoi in zip(rois, interpolatedRois):
            roiKW = dict(interpolatedRoi)
            roiKW.pop('kind', '')
            roiKW.pop('name', '')
            roiKW.pop('use', True)
            self.bypassForUpdate = True
            model.setRoi(roi, roiKW)

    def _updateRoiLabelPos(self, roi):
        labelPosX, labelPosY = roi._handleLabel.getPosition()
        plot = self.plot._plot if self.is3dStack else self.plot
        lims = plot.getYAxis().getLimits()
        if labelPosY > lims[1]:
            labelPosY = lims[1]
        elif labelPosY < (lims[0] + 0.05*(lims[1]-lims[0])):
            labelPosY = (lims[0] + 0.05*(lims[1]-lims[0]))
        roi._handleLabel.setPosition(labelPosX, labelPosY)

    def syncRoi(self):
        rois = self.roiManager.getRois()
        for roi in rois:
            self._updateRoiLabelPos(roi)
        horHeaders = self.table.horizontalHeader()
        rows = min(len(rois), self.maxVisibleTableRows)
        heights = sum([self.table.rowHeight(i) for i in range(rows)])
        newHeight = horHeaders.height() + 2 + heights
        self.table.setFixedHeight(newHeight)
        if self.bypassForSetup:
            return

        curRoi = self.roiManager.getCurrentRoi()
        if curRoi is None:
            curRoi = rois[0]
        model = self.table.roiModel
        if not self.bypassForUpdate:
            if self.is3dStack:
                key = self.plot._browser.value()
                self.keyFrameGeometries[key] = [
                    model.getRoiGeometry(roi) for roi in rois]
                if key not in self.keyFrameWidgets:
                    self._addKeyFrameWidget(key)
                    # add the last roi to the other key frames:
                for otherKey in self.keyFrameGeometries:
                    if key == otherKey:
                        continue
                    frame = self.keyFrameGeometries[otherKey]
                    for geom in frame:
                        geom['use'] = curRoi.isVisible()
                    if len(frame) < len(self.keyFrameGeometries[key]):
                        frame.append(model.getRoiGeometry(rois[-1]))
            # plot = self.plot._plot if self.is3dStack else self.plot
            # print([m.getName() for m in plot.getItems()])
            row = rois.index(curRoi)
            ind = model.index(row, 2)
            model.dataChanged.emit(ind, ind)
        else:
            self.bypassForUpdate = False
            ind0 = model.index(0, 2)
            inde = model.index(len(rois)-1, 2)
            model.dataChanged.emit(ind0, inde)

    def setKeyFrames(self, roiKeyFrames):
        """For setting up the widget from an external dictionary of key frames.
        """
        self.bypassForSetup = True
        rois = self.roiManager.getRois()
        newRois = list(roiKeyFrames.values())[0] if roiKeyFrames else []
        if len(rois) != len(newRois):
            needReset = True
        else:
            for roi, newRoi in zip(rois, newRois):
                if roi.__class__.__name__ != newRoi['kind']:
                    needReset = True
                    break
            else:
                needReset = False
        model = self.table.roiModel
        if needReset:
            if roiKeyFrames:
                self.plot._browser.setValue(list(roiKeyFrames.keys())[0])
            self.roiManager.setCurrentRoi(None)
            self.roiManager.clear()
            model.reset()
            for iroi, newRoi in enumerate(newRois):
                roiKW = dict(newRoi)
                kind = roiKW.pop('kind')
                name = roiKW.pop('name', 'roi{0}'.format(iroi))
                use = roiKW.pop('use', True)
                if kind == 'ArcROI':
                    roi = ArcROI()
                elif kind == 'RectangleROI':
                    roi = RectangleROI()
                else:
                    raise ValueError('unsupported ROI type')
                roi.setName(name)
                roi.setVisible(bool(use))
                model.setRoi(roi, roiKW)
                self.roiManager.addRoi(roi)
            model.reset()
            rois = self.roiManager.getRois()
            if rois:
                self.roiManager.setCurrentRoi(rois[0])

        remove = [k for k in self.keyFrameGeometries if k not in roiKeyFrames]
        for key in remove:
            self._deleteKeyFrame(key)
        add = [k for k in roiKeyFrames if k not in self.keyFrameGeometries]
        for key in add:
            self._addKeyFrameWidget(key)
        for key in roiKeyFrames:
            self.keyFrameGeometries[key] = list(roiKeyFrames[key])
            self.plot._browser.setValue(key)

        if not needReset and len(roiKeyFrames) > 0:
            newRois = list(roiKeyFrames.values())[-1] if roiKeyFrames else []
            for iroi, (roi, newRoi) in enumerate(zip(rois, newRois)):
                roiKW = dict(newRoi)
                kind = roiKW.pop('kind')
                name = roiKW.pop('name', 'roi{0}'.format(iroi))
                use = roiKW.pop('use', True)
                roi.setName(name)
                roi.setVisible(bool(use))
                model.setRoi(roi, roiKW)
            model.reset()
            # model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.bypassForSetup = False

    def _addKeyFrameWidget(self, key):
        keyFrameWidget = gco.KeyFrameWithCloseButton(
            self, key)
        keyFrameWidget.gotoFrame.connect(self._gotoKeyFrame)
        keyFrameWidget.deleteFrame.connect(self._deleteKeyFrame)
        self.keyFrameWidgets[key] = keyFrameWidget
        self.keyFramesLayout.addWidget(keyFrameWidget)

    def _gotoKeyFrame(self, key):
        self.plot._browser.setValue(key)

    def _deleteKeyFrame(self, key):
        keyFrameWidget = self.keyFrameWidgets[key]
        try:
            keyFrameWidget.gotoFrame.disconnect(self._gotoKeyFrame)
        except TypeError:  # 'method' object is not connected
            pass
        try:
            keyFrameWidget.deleteFrame.disconnect(self._deleteKeyFrame)
        except TypeError:  # 'method' object is not connected
            pass
        self.keyFramesLayout.removeWidget(keyFrameWidget)
        keyFrameWidget.close()
        del self.keyFrameGeometries[key]
        del self.keyFrameWidgets[key]

    def _removeRoiFromKeys(self, roiRemove):
        rois = self.roiManager.getRois()
        indRemove = rois.index(roiRemove)
        for geom in self.keyFrameGeometries.values():
            try:
                del geom[indRemove]
            except IndexError as e:
                print(e)
                print('The dict of rois is broken')
