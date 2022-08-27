# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "12 Aug 2022"
# !!! SEE CODERULES.TXT !!!

# import time
import numpy as np
# from collections import OrderedDict
# from functools import partial

from silx.gui import qt
from silx.gui.plot.tools.roi import (
    RegionOfInterestManager, RoiModeSelectorAction)
from silx.gui.plot.items.roi import ArcROI, RectangleROI, PointROI, CrossROI

from . import gcommons as gco
from ..core import singletons as csi
from ..utils import math as uma

HEADERS = 'label', 'use', 'geometry', 'counts'
columnWidths = 45, 32, 164, 52


class RoiManager(RegionOfInterestManager):
    def __init__(self, parent):
        super().__init__(parent)
        self.setColor(gco.COLOR_ROI)
        self.sigRoiAdded.connect(self.updateAddedRegionOfInterest)

    def updateAddedRegionOfInterest(self, roi):
        if roi.getName() == '':
            if isinstance(roi, RectangleROI):
                name = 'rect'
            elif isinstance(roi, ArcROI):
                name = 'arc'
            elif isinstance(roi, (CrossROI, PointROI)):
                name = 'p'
            roi.setName('{0}{1}'.format(name, len(self.getRois())))

        try:
            roi.setLineWidth(0.5)
            roi.setLineStyle('-')
        except AttributeError:
            pass
        # roi.setSymbolSize(5)
        roi.setSelectable(True)
        roi.setEditable(True)


class RoiModel(qt.QAbstractTableModel):
    def __init__(self, roiManager=None, dim=2):
        super().__init__()
        self.roiCounts = []
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
        if column == 1:  # use
            res |= qt.Qt.ItemIsUserCheckable
        elif column in (0, 2):  # label, geometry
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
            elif column == 3:  # counts
                while len(self.roiCounts) < row+1:
                    self.roiCounts.append(0)
                return '{0:.0f}'.format(self.roiCounts[row])
        elif role == qt.Qt.CheckStateRole:
            if column == 1:  # use
                return int(
                    qt.Qt.Checked if roi.isVisible() else qt.Qt.Unchecked)
        elif role == qt.Qt.ToolTipRole:
            return "{0}\ncan be removed via the plot's popup menu".format(
                roi.__class__.__name__)
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
        elif isinstance(roi, (CrossROI, PointROI)):
            return dict(kind=roi.__class__.__name__, name=roi.getName(),
                        use=roi.isVisible(),
                        pos=list(roi.getPosition()))
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
                'angles: {4:.4f}, {5:.4f}'.format(
                    x, y, innerR, outerR, startAngle, endAngle)
        elif isinstance(roi, (CrossROI, PointROI)):
            x, y = roi.getPosition()
            text = 'pos: {0:.3f}, {1:.3f}'.format(x, y)
        else:
            text = ''
        return text

    def setRoiFromTxt(self, roi, txt):
        try:
            txt = txt.replace(':', '=(')
            res = {}
            for row in txt.split('\n'):
                res.update(eval('dict({0}))'.format(row)))
            if isinstance(roi, RectangleROI):
                kw = dict(origin=res['origin'],
                          size=(res['width'], res['height']))
            elif isinstance(roi, ArcROI):
                kw = dict(
                    center=res['center'],
                    innerRadius=res['radii'][0], outerRadius=res['radii'][1],
                    startAngle=res['angles'][0], endAngle=res['angles'][1])
            elif isinstance(roi, (CrossROI, PointROI)):
                kw = res
            else:
                return False
            self.setRoi(roi, kw)
            return True
        except Exception as e:
            print(e)
            return False

    def setRoi(self, roi, kw):
        if isinstance(roi, (ArcROI, RectangleROI)):
            roi.setGeometry(**kw)
        elif isinstance(roi, (PointROI, CrossROI)):
            roi.setPosition(kw['pos'])


class RoiToolBar(qt.QToolBar):
    """A toolbar which hide itself if no actions are visible"""

    def __init__(self, parent, roiManager, roiClassNames):
        super().__init__(parent)
        # self.setStyleSheet('QToolBar{margin: 0px 10px;}')
        self.setIconSize(qt.QSize(24, 24))

        # to add more, add classes from:
        # silx.gui.plot.items.roi.RegionOfInterestManager.ROI_CLASSES:
        # roi_items.PointROI,
        # roi_items.CrossROI,
        # roi_items.RectangleROI,
        # roi_items.CircleROI,
        # roi_items.EllipseROI,
        # roi_items.PolygonROI,
        # roi_items.LineROI,
        # roi_items.HorizontalLineROI,
        # roi_items.VerticalLineROI,
        # roi_items.ArcROI,
        # roi_items.HorizontalRangeROI,
        for roiClassName in roiClassNames:
            if roiClassName == 'ArcROI':
                roiClass = ArcROI
            elif roiClassName == 'RectangleROI':
                roiClass = RectangleROI
            elif roiClassName == 'CrossROI':
                roiClass = CrossROI
            elif roiClassName == 'PointROI':
                roiClass = PointROI
            else:
                raise ValueError('unsupported ROI {0}'.format(roiClassName))
            action = roiManager.getInteractionModeAction(roiClass)
            action.setSingleShot(True)
            self.addAction(action)

        self.modeSelectorAction = RoiModeSelectorAction(self)
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
    maxVisibleTableRows = 4  # in the scroll area

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
            horHeaders.setResizeMode(2, qt.QHeaderView.Stretch)
            horHeaders.setClickable(True)
            verHeaders.setResizeMode(qt.QHeaderView.ResizeToContents)
        else:
            horHeaders.setSectionsMovable(False)
            for i in range(len(HEADERS)):
                horHeaders.setSectionResizeMode(i, qt.QHeaderView.Interactive)
            horHeaders.setSectionResizeMode(2, qt.QHeaderView.Stretch)
            horHeaders.setSectionsClickable(True)
            verHeaders.setSectionResizeMode(qt.QHeaderView.ResizeToContents)
        horHeaders.setStretchLastSection(False)
        horHeaders.setMinimumSectionSize(20)
        # verHeaders.setMinimumSectionSize(70)

        self.setItemDelegateForColumn(2, gco.MultiLineEditDelegate(self))

        for i in range(len(HEADERS)):
            self.setColumnWidth(i, int(columnWidths[i]*csi.screenFactor))
        self.setMinimumWidth(int(sum(columnWidths)*csi.screenFactor) + 2)
        self.setMinimumHeight(int(horHeaders.height()*4*csi.screenFactor))

        roiManager.sigCurrentRoiChanged.connect(self.currentRoiChanged)

    def selChanged(self):
        if not self.hasFocus():
            return
        selectedIndex = self.selectionModel().selectedRows()[0]
        manager = self.roiModel.roiManager
        rois = manager.getRois()
        manager.setCurrentRoi(rois[selectedIndex.row()])

    def currentRoiChanged(self, roi):
        rois = self.roiModel.roiManager.getRois()
        try:
            self.selectRow(rois.index(roi))
        except Exception:
            pass

    def updateRoiTableSize(self):
        rois = self.roiModel.roiManager.getRois()
        rows = min(len(rois), self.maxVisibleTableRows)
        heights = sum([self.rowHeight(i) for i in range(rows)])
        horHeaders = self.horizontalHeader()
        newHeight = horHeaders.height() + 2 + heights
        self.setFixedHeight(newHeight)
        if rows <= self.maxVisibleTableRows:
            self.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)
        else:
            self.setVerticalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOn)


class RoiWidgetBase(qt.QWidget):
    def _updateRoiLabelPos(self, roi):
        if not hasattr(roi, '_handleLabel'):
            return
        labelPosX, labelPosY = roi._handleLabel.getPosition()
        plot = self.plot._plot if self.is3dStack else self.plot
        lims = plot.getYAxis().getLimits()
        if labelPosY > lims[1]:
            labelPosY = lims[1]
        elif labelPosY < (lims[0] + 0.05*(lims[1]-lims[0])):
            labelPosY = (lims[0] + 0.05*(lims[1]-lims[0]))
        roi._handleLabel.setPosition(labelPosX, labelPosY)

    def updateCounts(self):
        if self.dataToCount is None:
            return
        data = self.dataToCount
        rois = self.roiManager.getRois()
        if len(rois) == 0:
            return
        model = self.table.roiModel
        while len(model.roiCounts) < len(rois):
            model.roiCounts.append(0)
        for row, roi in enumerate(rois):
            geom = model.getRoiGeometry(roi)
            if self.is3dStack:
                iframe = self.plot._browser.value()
                frame = data[iframe, :, :]
            else:
                frame = data
            sh = frame.shape

            if isinstance(roi, (RectangleROI, ArcROI)):
                xs = np.arange(sh[1])[None, :]
                ys = np.arange(sh[0])[:, None]
                m = uma.get_roi_mask(geom, xs, ys)
                model.roiCounts[row] = frame[m].sum()
            elif isinstance(roi, (CrossROI, PointROI)):
                x, y = geom['pos']
                xs = self.dataToCountX
                ys = self.dataToCountY
                if xs is not None:
                    dx = xs[1] - xs[0]
                    ix = np.searchsorted(xs+dx, x)
                else:
                    ix = int(x)
                if ys is not None:
                    dy = ys[1] - ys[0]
                    iy = np.searchsorted(ys+dy, y)
                else:
                    iy = int(y)
                ix = abs(min(ix, sh[1]-1))
                iy = abs(min(iy, sh[0]-1))
                model.roiCounts[row] = frame[iy, ix]

        ind0 = model.index(0, 3)
        inde = model.index(row, 3)
        model.dataChanged.emit(ind0, inde)


class RoiWidgetWithKeyFrames(RoiWidgetBase):
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

        roiClassNames = 'ArcROI', 'RectangleROI'
        self.roiToolbar = RoiToolBar(self, self.roiManager, roiClassNames)
        layout.addWidget(self.roiToolbar)

        self.table = RoiTableView(self, self.roiManager, plot)
        layout.addWidget(self.table)
        if self.is3dStack:
            layoutF = qt.QHBoxLayout()
            keyFrameLabel = qt.QLabel('Key frames')
            layoutF.addWidget(keyFrameLabel)
            keyFramesFrame = qt.QFrame(self)
            layoutF.addWidget(keyFramesFrame, 1)
            self.keyFramesLayout = gco.FlowLayout()
            keyFramesFrame.setLayout(self.keyFramesLayout)
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

        self.dataToCount = None
        self.dataToCountX, self.dataToCountY = None, None
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
        interpolatedRois = uma.interpolate_frames(
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

    def syncRoi(self):
        rois = self.roiManager.getRois()
        for roi in rois:
            self._updateRoiLabelPos(roi)
        self.table.updateRoiTableSize()
        if self.bypassForSetup:
            return

        curRoi = self.roiManager.getCurrentRoi()
        if curRoi is None and rois:
            curRoi = rois[0]
        if curRoi is None:
            return

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
            self.updateCounts()
            row = rois.index(curRoi)
            ind0 = model.index(row, 2)
            inde = model.index(row, 3)
        else:
            self.bypassForUpdate = False
            self.updateCounts()
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
            model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.bypassForSetup = False

    def _addKeyFrameWidget(self, key):
        keyFrameWidget = gco.IntButtonWithCloseButton(self, key)
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


class RoiWidget(RoiWidgetBase):
    def __init__(self, parent, plot, roiClassNames, roiMaxN=1):
        """
        *roiClassNames*: sequence of class names to appear in the toolbar
        *roiMaxN*: max number of rois in the tabe
        """
        super().__init__(parent)
        self.plot = plot
        self.is3dStack = hasattr(self.plot, '_plot')
        if self.is3dStack:
            self.roiManager = RoiManager(plot._plot)
        else:
            self.roiManager = RoiManager(plot)

        self.roiMaxN = roiMaxN

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.roiToolbar = RoiToolBar(self, self.roiManager, roiClassNames)
        layout.addWidget(self.roiToolbar)

        self.table = RoiTableView(self, self.roiManager, plot)
        layout.addWidget(self.table)

        self.acceptButton = qt.QPushButton('Accept ROI')
        layout.addWidget(self.acceptButton, 1)
        layout.addStretch()
        self.setLayout(layout)

        self.dataToCount = None
        self.dataToCountX, self.dataToCountY = None, None
        self.roiManager.sigRoiChanged.connect(self.syncRoi)

        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)

    def syncRoi(self):
        rois = self.roiManager.getRois()
        actions = self.roiToolbar.actions()
        for action in actions:
            action.setEnabled(len(rois) < self.roiMaxN)
        for roi in rois:
            self._updateRoiLabelPos(roi)
        self.table.updateRoiTableSize()

        curRoi = self.roiManager.getCurrentRoi()
        if curRoi is None and rois:
            curRoi = rois[0]
        if curRoi is None:
            return

        self.updateCounts()

        model = self.table.roiModel
        row = rois.index(curRoi)
        ind1 = model.index(row, 2)
        ind2 = model.index(row, 3)
        model.dataChanged.emit(ind1, ind2)

    def setRois(self, roiDicts):
        if not isinstance(roiDicts, (tuple, list)):
            roiDicts = roiDicts,
        roiDicts = [dict(roid) for roid in roiDicts]  # deep copy

        rois = self.roiManager.getRois()
        if len(rois) != len(roiDicts):
            needReset = True
        else:
            for roi, roid in zip(rois, roiDicts):
                if roi.__class__.__name__ != roid['kind']:
                    needReset = True
                    break
            else:
                needReset = False

        model = self.table.roiModel
        if needReset:
            self.roiManager.setCurrentRoi(None)
            self.roiManager.clear()
            # model.reset()
            for roid in roiDicts:
                kind = roid.pop('kind', '')
                roid.pop('use', True)
                name = roid.pop('name', '')
                # model.reset()
                if kind == 'ArcROI':
                    roi = ArcROI()
                elif kind == 'RectangleROI':
                    roi = RectangleROI()
                elif kind == 'PointROI':
                    roi = PointROI()
                elif kind == 'CrossROI':
                    roi = CrossROI()
                else:
                    raise ValueError('unsupported ROI {0}'.format(kind))
                self.roiManager.addRoi(roi)
                if name:
                    roi.setName(name)
                roi.setVisible(True)
                model.setRoi(roi, roid)
        else:
            for roi, roid in zip(rois, roiDicts):
                kind = roid.pop('kind')
                name = roid.pop('name', '')
                use = roid.pop('use', True)
                if name:
                    roi.setName(name)
                roi.setVisible(bool(use))
                model.setRoi(roi, roid)

        self.roiManager.setCurrentRoi(roi)
        model.reset()
        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def getCurrentRoi(self):
        curRoi = self.roiManager.getCurrentRoi()
        model = self.table.roiModel
        return model.getRoiGeometry(curRoi)

    def getRois(self):
        rois = self.roiManager.getRois()
        model = self.table.roiModel
        return [model.getRoiGeometry(roi) for roi in rois]
