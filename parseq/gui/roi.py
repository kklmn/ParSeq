# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Feb 2023"
# !!! SEE CODERULES.TXT !!!

# import time
import numpy as np
# from collections import OrderedDict
from functools import partial

from silx.gui import qt
from silx.gui.plot.tools.roi import (
    RegionOfInterestManager, RoiModeSelectorAction)
from silx.gui.plot.items.roi import (
    ArcROI, RectangleROI, BandROI, CrossROI, PointROI, HorizontalRangeROI,
    InteractionModeMixIn)

from . import gcommons as gco
from ..core import singletons as csi
from ..core.logger import syslogger
from ..utils import math as uma

HEADERS = 'label', 'use', 'geometry', 'counts'
columnWidths = 45, 32, 164, 55


class RoiManager(RegionOfInterestManager):
    def __init__(self, parent):
        super().__init__(parent)
        self.setColor(gco.COLOR_ROI)
        self.sigRoiAdded.connect(self.updateAddedRegionOfInterest)

    def updateAddedRegionOfInterest(self, roi):
        # silx.gui.plot.tools.roi.RegionOfInterestManager.ROI_CLASSES:
        if roi.getName() == '':
            if isinstance(roi, RectangleROI):
                name = 'rect'
            elif isinstance(roi, ArcROI):
                name = 'arc'
            elif isinstance(roi, BandROI):
                name = 'band'
                roi.setAvailableInteractionModes([BandROI.UnboundedMode])
            elif isinstance(roi, (CrossROI, PointROI)):
                name = 'p'
            elif isinstance(roi, HorizontalRangeROI):
                name = 'range'
            roi.setName('{0}{1}'.format(name, len(self.getRois())))

        try:
            roi.setLineWidth(0.5)
            roi.setLineStyle('-')
        except AttributeError as e:
            # print(e)
            pass
        # roi.setSymbolSize(5)
        roi.setSelectable(True)
        roi.setEditable(True)

    def _feedContextMenu(self, menu):
        """when the default plot context menu is about to be displayed"""
        roi = self.getCurrentRoi()
        if roi is not None:
            if roi.isEditable():
                # Filter by data position
                plot = self.parent()
                pos = plot.getWidgetHandle().mapFromGlobal(qt.QCursor.pos())
                data = plot.pixelToData(pos.x(), pos.y())
                if roi.contains(data):
                    if isinstance(roi, InteractionModeMixIn):
                        try:
                            intMenu = roi.createMenuForInteractionMode(menu)
                            menu.addMenu(intMenu)
                        except Exception as e:
                            syslogger.error(str(e))

                removeAction = qt.QAction(menu)
                removeAction.setText("Remove %s" % roi.getName())
                callback = partial(self.removeRoi, roi)
                removeAction.triggered.connect(callback)
                menu.addAction(removeAction)


class RoiModel(qt.QAbstractTableModel):
    def __init__(self, roiManager=None, fmt='auto'):
        super().__init__()
        self.roiCounts = []
        self.setRoiManager(roiManager)
        self.fmt = fmt
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
                return qt.Qt.Checked if roi.isVisible() else qt.Qt.Unchecked
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
        elif isinstance(roi, BandROI):
            geom = roi.getGeometry()
            return dict(kind='BandROI', name=roi.getName(),
                        use=roi.isVisible(),
                        begin=(geom.begin.x, geom.begin.y),
                        end=(geom.end.x, geom.end.y), width=geom.width)
        elif isinstance(roi, (CrossROI, PointROI)):
            return dict(kind=roi.__class__.__name__, name=roi.getName(),
                        use=roi.isVisible(),
                        pos=list(roi.getPosition()))
        elif isinstance(roi, HorizontalRangeROI):
            range_ = roi.getRange()
            return dict(kind=roi.__class__.__name__, name=roi.getName(),
                        use=roi.isVisible(),
                        vmin=range_[0], vmax=range_[1])
        else:
            return dict()

    def getFmt(self, startStr):
        if isinstance(self.fmt, str):
            fmt = self.fmt
            if fmt.startswith(startStr):
                return fmt
        elif isinstance(self.fmt, (list, tuple)):
            for fmt in self.fmt:
                if fmt.startswith(startStr):
                    return fmt
        return 'auto'

    def getReadableRoiDescription(self, roi):
        if isinstance(roi, RectangleROI):
            x, y = roi.getOrigin()
            w, h = roi.getSize()
            fmt = self.getFmt('origin')
            s = 'origin: {0:.1f}, {1:.1f}\nwidth: {2:.1f}\nheight: {3:.1f}' \
                if fmt == 'auto' else fmt
            text = s.format(x, y, w, h)
        elif isinstance(roi, ArcROI):
            geom = roi._geometry
            x, y = geom.center
            innerR, outerR = roi.getInnerRadius(), roi.getOuterRadius()
            startAngle, endAngle = geom.startAngle, geom.endAngle
            fmt = self.getFmt('center')
            s = 'center: {0:.1f}, {1:.1f}\nradii: {2:.1f}, {3:.1f}\n'\
                'angles: {4:.4f}, {5:.4f}' if fmt == 'auto' else fmt
            text = s.format(x, y, innerR, outerR, startAngle, endAngle)
        elif isinstance(roi, BandROI):
            geom = roi.getGeometry()
            fmt = self.getFmt('begin')
            s = 'begin: {0[0]:.3f}, {0[1]:.3f}\n'\
                'end: {1[0]:.3f}, {1[1]:.3f}\n'\
                'width: {2:.3f}' if fmt == 'auto' else fmt
            text = s.format(geom.begin, geom.end, geom.width)
        elif isinstance(roi, (CrossROI, PointROI)):
            x, y = roi.getPosition()
            fmt = self.getFmt('pos')
            s = 'pos: {0:.3f}, {1:.3f}' if fmt == 'auto' else fmt
            text = s.format(x, y)
        elif isinstance(roi, HorizontalRangeROI):
            range_ = roi.getRange()
            fmt = self.getFmt('range')
            s = 'range: {0[0]:.3f}, {0[1]:.3f}' if fmt == 'auto' else fmt
            text = s.format(range_)
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
            elif isinstance(roi, BandROI):
                kw = res
            elif isinstance(roi, (CrossROI, PointROI)):
                kw = res
            elif isinstance(roi, HorizontalRangeROI):
                kw = dict(vmin=res['range'][0], vmax=res['range'][1])
            else:
                return False
            self.setRoi(roi, kw)
            return True
        except Exception as e:
            syslogger.error(str(e))
            return False

    def setRoi(self, roi, kw):
        if isinstance(roi, (RectangleROI, ArcROI, BandROI)):
            roi.setGeometry(**kw)
        elif isinstance(roi, (PointROI, CrossROI)):
            roi.setPosition(kw['pos'])
        elif isinstance(roi, HorizontalRangeROI):
            roi.setRange(**kw)


class RoiToolBar(qt.QToolBar):
    """A toolbar that hides itself if no actions are visible"""

    def __init__(self, parent, roiManager, roiClassNames):
        super().__init__(parent)
        # self.setStyleSheet('QToolBar{margin: 0px 10px;}')
        self.setIconSize(qt.QSize(24, 24))

        # to add more, add classes from:
        # silx.gui.plot.tools.roi.RegionOfInterestManager.ROI_CLASSES:
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
            if roiClassName == 'RectangleROI':
                roiClass = RectangleROI
            elif roiClassName == 'ArcROI':
                roiClass = ArcROI
            elif roiClassName == 'BandROI':
                roiClass = BandROI
            elif roiClassName == 'CrossROI':
                roiClass = CrossROI
            elif roiClassName == 'PointROI':
                roiClass = PointROI
            elif roiClassName == 'HorizontalRangeROI':
                roiClass = HorizontalRangeROI
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

    def __init__(self, parent, roiManager, fmt='auto'):
        super().__init__(parent)
        self.roiModel = RoiModel(roiManager, fmt)
        self.setModel(self.roiModel)

        self.setSelectionMode(self.SingleSelection)
        self.setSelectionBehavior(self.SelectItems)
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

        self.setItemDelegateForColumn(1, gco.CheckBoxDelegate(self))
        self.setItemDelegateForColumn(2, gco.MultiLineEditDelegate(self))

        for i in range(len(HEADERS)):
            self.setColumnWidth(i, int(columnWidths[i]*csi.screenFactor))
        self.setMinimumWidth(int(sum(columnWidths)*csi.screenFactor) + 2)
        self.setMinimumHeight(int(horHeaders.height()*4*csi.screenFactor))

        roiManager.sigCurrentRoiChanged.connect(self.currentRoiChanged)

    def selChanged(self):
        if not self.hasFocus():
            return
        selectedIndexes = self.selectionModel().selectedIndexes()
        if not selectedIndexes:
            return
        selectedIndex = selectedIndexes[0]
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
        if len(rois) <= self.maxVisibleTableRows:
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
        if data is None:  # when data file is missing
            return
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

            try:
                if isinstance(roi, (RectangleROI, ArcROI, HorizontalRangeROI)):
                    xs = np.arange(sh[1])[None, :]
                    ys = np.arange(sh[0])[:, None]
                    mask = uma.get_roi_mask(geom, xs, ys)
                    model.roiCounts[row] = frame[mask].sum()
                elif isinstance(roi, BandROI):
                    if self.dataToCountX is not None:
                        xs = self.dataToCountX[None, :]
                    else:
                        xs = np.arange(sh[1])[None, :]
                    if self.dataToCountY is not None:
                        ys = self.dataToCountY[:, None]
                    else:
                        ys = np.arange(sh[0])[:, None]
                    mask = uma.get_roi_mask(geom, xs, ys)
                    model.roiCounts[row] = frame[mask].sum()
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
            except IndexError as e:
                syslogger.error(str(e))
                model.roiCounts[row] = 0

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

        roiClassNames = ('RectangleROI', 'ArcROI', 'BandROI',
                         'HorizontalRangeROI')
        self.roiToolbar = RoiToolBar(self, self.roiManager, roiClassNames)
        layout.addWidget(self.roiToolbar)

        self.table = RoiTableView(self, self.roiManager)
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
                if kind == 'RectangleROI':
                    roi = RectangleROI()
                elif kind == 'ArcROI':
                    roi = ArcROI()
                elif kind == 'BandROI':
                    roi = BandROI()
                    roi.setAvailableInteractionModes([BandROI.UnboundedMode])
                elif kind == 'HorizontalRangeROI':
                    roi = HorizontalRangeROI()
                else:
                    raise ValueError('unsupported ROI type')
                roi.setName(name)
                roi.setVisible(bool(use))
                model.setRoi(roi, roiKW)
                self.roiManager.addRoi(roi)
                # if kind == 'RectangleROI':
                #     roi.setColor('white')  # has to be after addROI
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
                syslogger.error('The dict of rois is broken:\n'+str(e))


class RoiWidget(RoiWidgetBase):
    def __init__(self, parent, plot, roiClassNames, roiMaxN=1, fmt='auto'):
        """
        *roiClassNames*: sequence of class names to appear in the toolbar
        *roiMaxN*: max number of rois in the tabel
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

        self.table = RoiTableView(self, self.roiManager, fmt=fmt)
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
        if not roiDicts:
            return
        if not isinstance(roiDicts, (tuple, list)):
            roiDicts = roiDicts,
        roiDicts = [dict(roid) for roid in roiDicts]  # deep copy
        rois = self.roiManager.getRois()
        if len(rois) != len(roiDicts):
            needReset = True
        else:
            for roi, roid in zip(rois, roiDicts):
                try:
                    if roi.__class__.__name__ != roid['kind']:
                        needReset = True
                        break
                except KeyError:
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
                if kind == 'RectangleROI':
                    roi = RectangleROI()
                elif kind == 'ArcROI':
                    roi = ArcROI()
                elif kind == 'BandROI':
                    roi = BandROI()
                    roi.setAvailableInteractionModes([BandROI.UnboundedMode])
                elif kind == 'CrossROI':
                    roi = CrossROI()
                elif kind == 'PointROI':
                    roi = PointROI()
                elif kind == 'HorizontalRangeROI':
                    roi = HorizontalRangeROI()
                else:
                    # continue
                    raise ValueError('unsupported ROI "{0}"'.format(kind))
                if name:
                    roi.setName(name)
                roi.setVisible(True)
                model.setRoi(roi, roid)
                self.roiManager.addRoi(roi)
            self.roiManager.setCurrentRoi(roi)
        else:
            for roi, roid in zip(rois, roiDicts):
                kind = roid.pop('kind')
                name = roid.pop('name', '')
                use = roid.pop('use', True)
                if name:
                    roi.setName(name)
                roi.setVisible(bool(use))
                model.setRoi(roi, roid)

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


class BaseRangeWidget(qt.QWidget):
    rangeChanged = qt.pyqtSignal(list)
    rangeToggled = qt.pyqtSignal(bool)

    def createRoi(self, vmin=None, vmax=None):
        if self.plot is None:
            return
        elif isinstance(self.plot, str):
            if csi.nodes[self.plot].widget is None:
                return
            self.plot = csi.nodes[self.plot].widget.plot

        needNew = False
        if self.roiManager is None:
            if self.is3dStack:
                self.roiManager = RoiManager(self.plot._plot)
            else:
                self.roiManager = RoiManager(self.plot)
            needNew = True
        else:
            if len(self.roiManager.getRois()) == 0:
                needNew = True
        if needNew:
            try:
                roi = self.roiClass()
                if isinstance(roi, (CrossROI, PointROI)):
                    roi.setName(' ')
                    names = self.rangeName.split(',')
                    roi._vmarker.setText(names[1])
                    roi._hmarker.setText(names[0])
                elif isinstance(roi, HorizontalRangeROI):
                    roi.setName(self.rangeName)
                self.roi = roi
            except ValueError:
                return
            self.roiManager.addRoi(self.roi)
            self.roi.setColor(self.color)
            self.roiManager.sigRoiChanged.connect(self.syncRange)
            self.roi.sigEditingFinished.connect(self.rangeFinished)

        try:
            if hasattr(self, 'visibleCB'):
                self.roi.setVisible(self.visibleCB.isChecked())
            if vmin is None or vmax is None:
                if callable(self.defaultRange):
                    defRange = self.defaultRange()
                else:
                    defRange = self.defaultRange
                vmin, vmax = defRange
            ran = self.convert(1, vmin, vmax)
            if ran is None:
                return
            if isinstance(self.roi, (CrossROI, PointROI)):
                self.roi.setPosition(ran)
            elif isinstance(self.roi, HorizontalRangeROI):
                self.roi.setRange(vmin=ran[0], vmax=ran[1])
        except ValueError:
            return

    def syncRange(self):
        if isinstance(self.roi, (CrossROI, PointROI)):
            ran = self.roi.getPosition()
        elif isinstance(self.roi, HorizontalRangeROI):
            ran = self.roi.getRange()
        ran = self.convert(-1, *ran)
        self.setRange(ran)

    def rangeFinished(self):
        if isinstance(self.roi, (CrossROI, PointROI)):
            vmin, vmax = self.roi.getPosition()
        elif isinstance(self.roi, HorizontalRangeROI):
            vmin, vmax = self.roi.getRange()
        ran = self.convert(-1, vmin, vmax)
        if ran is not None:
            self.rangeChanged.emit(list(ran))

    def convert(self, direction, vmin, vmax):
        """Converts from spinbox values to roi limits and backward.
        direction: 1: from spinbox values to roi limits, -1: from roi limits to
        spinbox values.
        """
        return vmin, vmax  # just pass through


class SimpleRangeWidget(BaseRangeWidget):
    def __init__(self, parent, plot, caption, tooltip, rangeName, color,
                 formatStr, defaultRange=[0, 1]):
        """
        *defaultRange*: callable or 2-sequence
        """
        super().__init__(parent)
        self.plot = plot
        self.is3dStack = hasattr(plot, '_plot')
        self.formatStr = formatStr
        if callable(defaultRange):
            self.defaultRange = defaultRange
        else:
            self.defaultRange = list(defaultRange)
        self.tooltip = tooltip
        self.rangeName = rangeName
        self.roiManager = None
        self.roi = None
        self.color = color
        self.roiClass = HorizontalRangeROI

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.panel = qt.QGroupBox(self)
        self.panel.setFlat(True)
        self.panel.setTitle(caption)
        # self.panel is by default uncheckable
        self.panel.toggled.connect(self.toggled)
        layoutP = qt.QHBoxLayout()
        layoutP.setContentsMargins(10, 0, 0, 0)
        self.setCustomRange()
        self.editCustom = qt.QLineEdit()
        self.editCustom.setStyleSheet("QLineEdit{color: " + color + ";}")
        if not callable(self.defaultRange):
            self.editSetText(self.defaultRange)
        layoutP.addWidget(self.editCustom)
        if tooltip:
            self.editCustom.setToolTip(tooltip)
        self.panel.setLayout(layoutP)
        layout.addWidget(self.panel)
        self.setLayout(layout)

    def toggled(self, on):
        self.rangeToggled.emit(on)
        if self.roi is None:
            ran = self.defaultRange() if callable(self.defaultRange) else \
                self.defaultRange
            self.createRoi(ran)
        if self.roi is None:  # cannot create roi because self.plot is stll str
            return
        self.roi.blockSignals(True)
        self.roi.setVisible(on)
        self.roi.blockSignals(False)

    def editSetText(self, ran):
        try:
            self.editCustom.setText(self.formatStr.format(ran))
        except Exception:
            self.editCustom.setText('')

    def setRange(self, ran):
        if not isinstance(ran, (tuple, list)):
            return
        if self.roi is None:
            ran = self.defaultRange() if callable(self.defaultRange) else \
                self.defaultRange
            self.createRoi(ran)
        if self.roi is None:  # cannot create roi because self.plot is stll str
            return

        if len(ran) == 2:
            self.editSetText(ran)
            self.createRoi(*ran)
            self.roi.blockSignals(True)
            if self.panel.isCheckable():
                use = self.panel.isChecked()
            else:
                use = True
            self.roi.setVisible(use)
            self.roi.blockSignals(False)

    def setCustomRange(self):
        self.createRoi()
        if self.roi is None:
            return
        vmin, vmax = self.roi.getRange()
        ran = self.convert(-1, vmin, vmax)
        if ran is None:
            return
        self.roi.blockSignals(True)
        self.roi.setVisible(True)
        self.rangeChanged.emit(list(ran))
        self.roi.blockSignals(False)

    def acceptEdit(self):
        if self.roi is None:
            return
        txt = self.editCustom.text()
        try:
            t1, t2 = txt.split(',')
            vmin = float(t1.strip())
            vmax = float(t2.strip())
            self.setRange([vmin, vmax])
            return [vmin, vmax]
        except Exception:
            pass


class AutoRangeWidget(BaseRangeWidget):
    def __init__(self, parent, plot, caption, tooltip, rangeName, color,
                 formatStr, defaultRange=[0, 1]):
        """
        *defaultRange*: callable or 2-sequence
        """
        super().__init__(parent)
        self.plot = plot
        self.is3dStack = hasattr(plot, '_plot')
        self.formatStr = formatStr
        if callable(defaultRange):
            self.defaultRange = defaultRange
        else:
            self.defaultRange = list(defaultRange)
        self.tooltip = tooltip
        self.rangeName = rangeName
        self.roiManager = None
        self.roi = None
        self.color = color
        self.roiClass = HorizontalRangeROI

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.panel = qt.QGroupBox(self)
        self.panel.setFlat(True)
        self.panel.setTitle(caption)
        # self.panel is by default uncheckable
        self.panel.toggled.connect(self.toggled)
        self.panelLayout = qt.QVBoxLayout()
        self.panelLayout.setContentsMargins(10, 0, 0, 0)
        self.rangeLayout = qt.QHBoxLayout()
        self.rangeLayout.setContentsMargins(0, 0, 0, 0)
        self.rbAuto = qt.QRadioButton('auto', self.panel)
        self.rbAuto.clicked.connect(self.setAutoRange)
        self.rangeLayout.addWidget(self.rbAuto)
        self.rbCustom = qt.QRadioButton('custom', self.panel)
        self.rbCustom.setStyleSheet("QRadioButton{color: " + color + ";}")
        self.rbCustom.clicked.connect(self.setCustomRange)
        self.rangeLayout.addWidget(self.rbCustom)
        self.editCustom = qt.QLineEdit()
        self.editCustom.setStyleSheet("QLineEdit{color: " + color + ";}")
        if not callable(self.defaultRange):
            self.editSetText(self.defaultRange)
        self.rangeLayout.addWidget(self.editCustom)
        if tooltip:
            self.editCustom.setToolTip(tooltip)
        self.panelLayout.addLayout(self.rangeLayout)
        self.panel.setLayout(self.panelLayout)
        layout.addWidget(self.panel)
        self.setLayout(layout)

    def toggled(self, on):
        self.rangeToggled.emit(on)
        if self.roi is None:
            return
        self.roi.blockSignals(True)
        self.roi.setVisible(on and self.rbCustom.isChecked())
        self.roi.blockSignals(False)

    def editSetText(self, ran):
        try:
            self.editCustom.setText(self.formatStr.format(ran))
        except Exception:
            self.editCustom.setText('')

    def setRange(self, ran, use=True):
        if not isinstance(ran, (tuple, list)):
            self.rbAuto.setChecked(True)
            self.rbCustom.setChecked(False)
            return

        if len(ran) == 2:
            self.editSetText(ran)
            self.createRoi(*ran)
            if callable(self.defaultRange):
                defRange = self.defaultRange()
            else:
                defRange = self.defaultRange
            isDefault = np.allclose(ran, defRange)
            self.rbAuto.setChecked(isDefault)
            self.rbCustom.setChecked(not isDefault)

            if self.roi is None:
                return
            self.roi.blockSignals(True)
            self.roi.setVisible(use and not isDefault)
            self.roi.blockSignals(False)

    def setAutoRange(self):
        if callable(self.defaultRange):
            defRange = self.defaultRange()
            if defRange is None:
                return
        else:
            defRange = self.defaultRange
            fs = "[" + self.formatStr + "]{1}{2}"
            self.rbAuto.setToolTip(fs.format(
                defRange, ' as ' if self.tooltip else '', self.tooltip))
        if self.roi is not None:
            self.setRange(defRange)
        self.rangeChanged.emit(list(defRange))
        self.editSetText(defRange)
        self.rbAuto.setChecked(True)
        self.rbCustom.setChecked(False)

    def setCustomRange(self):
        self.createRoi()
        vmin, vmax = self.roi.getRange()
        ran = self.convert(-1, vmin, vmax)
        if ran is None:
            return
        self.roi.blockSignals(True)
        self.roi.setVisible(True)
        self.rangeChanged.emit(list(ran))
        self.roi.blockSignals(False)

    def acceptEdit(self):
        if self.roi is None:
            return
        txt = self.editCustom.text()
        try:
            t1, t2 = txt.split(',')
            vmin = float(t1.strip())
            vmax = float(t2.strip())
            self.setRange([vmin, vmax])
            return [vmin, vmax]
        except Exception:
            pass


class SplitRangeWidget(BaseRangeWidget):
    spinBoxDelay = 500  # ms

    def __init__(self, parent, plot, var, optionsMin, optionsMax, rangeName,
                 color, defaultRange, addVisibleCB=False):
        """
        *optionsMin*, *optionsMax*: list [min, max, step, decimals]
        *defaultRange*: callable or 2-sequence
        """
        super().__init__(parent)
        self.plot = plot
        self.is3dStack = hasattr(plot, '_plot')
        self.roiManager = None
        self.roi = None
        self.color = color
        if callable(defaultRange):
            self.defaultRange = defaultRange
        else:
            self.defaultRange = list(defaultRange)
        minLabelTxt, maxLabelTxt = var[0:2]
        if 'min' in minLabelTxt:
            self.roiClass = HorizontalRangeROI
        else:
            self.roiClass = CrossROI
        varSuffix = var[2] if len(var) > 2 else None
        self.rangeName = rangeName

        self.spinTimer = qt.QTimer(self)
        self.spinTimer.setSingleShot(True)
        self.spinTimer.timeout.connect(self.spinDelayed)
        self.spinBoxProps = None

        layout = qt.QGridLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setVerticalSpacing(2)

        minLabel = qt.QLabel(minLabelTxt)
        layout.addWidget(minLabel, 0, 0, qt.Qt.AlignRight)
        self.minSpinBox = qt.QDoubleSpinBox()
        if optionsMin[0] is not None:
            self.minSpinBox.setMinimum(optionsMin[0])
        if optionsMin[1] is not None:
            self.minSpinBox.setMaximum(optionsMin[1])
        self.minSpinBox.setSingleStep(optionsMin[2])
        self.minSpinBox.setDecimals(optionsMin[3])
        self.minSpinBox.valueChanged.connect(partial(self.fromSpinBox, 0))
        if varSuffix:
            self.minSpinBox.setSuffix(varSuffix)
        layout.addWidget(self.minSpinBox, 0, 1)

        maxLabel = qt.QLabel(maxLabelTxt)
        if 'min' in minLabelTxt:
            layout.addWidget(maxLabel, 1, 0, qt.Qt.AlignRight)
        else:
            layout.setColumnStretch(2, 1)
            layout.addWidget(maxLabel, 0, 3, qt.Qt.AlignRight)
        self.maxSpinBox = qt.QDoubleSpinBox()
        if optionsMax[0] is not None:
            self.maxSpinBox.setMinimum(optionsMax[0])
        if optionsMax[1] is not None:
            self.maxSpinBox.setMaximum(optionsMax[1])
        self.maxSpinBox.setSingleStep(optionsMax[2])
        self.maxSpinBox.setDecimals(optionsMax[3])
        if self.roiClass == HorizontalRangeROI:
            self.maxSpinBox.setSpecialValueText("max data")
        self.maxSpinBox.valueChanged.connect(partial(self.fromSpinBox, 1))
        if varSuffix:
            self.maxSpinBox.setSuffix(varSuffix)
        if 'min' in minLabelTxt:
            layout.addWidget(self.maxSpinBox, 1, 1)
        else:
            layout.addWidget(self.maxSpinBox, 0, 4)

        if addVisibleCB:
            self.visibleCB = qt.QCheckBox('visible range widget')
            self.visibleCB.setStyleSheet(
                "QCheckBox:checked{color: " + color + ";}")
            self.visibleCB.toggled.connect(self.toggleVisible)
            layout.addWidget(self.visibleCB, 0, 3, 1, 3)

        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)

    def setRange(self, ran):
        if not isinstance(ran, (tuple, list)):
            return
        if len(ran) == 2:
            if ran[0] is None or ran[1] is None:
                if callable(self.defaultRange):
                    defRange = self.defaultRange()
                else:
                    defRange = self.defaultRange
                if self.roiClass == HorizontalRangeROI:
                    vmin = defRange[0]
                    vmax = self.maxSpinBox.minimum()  # special value
                elif self.roiClass == CrossROI:
                    vmin, vmax = defRange
            self.minSpinBox.blockSignals(True)
            self.maxSpinBox.blockSignals(True)
            self.minSpinBox.setValue(vmin if ran[0] is None else ran[0])
            self.maxSpinBox.setValue(vmax if ran[1] is None else ran[1])
            self.minSpinBox.blockSignals(False)
            self.maxSpinBox.blockSignals(False)
            self.createRoi(*ran)
            return

    def fromSpinBox(self, ind, value=None):
        if self.roi is None:
            return
        self.roi.blockSignals(True)

        if ind == 0:
            smin, smax = value, self.maxSpinBox.value()
        elif ind == 1:
            smin, smax = self.minSpinBox.value(), value
        elif ind == 100:
            smin, smax = self.minSpinBox.value(), self.maxSpinBox.value()
        ran = self.convert(1, smin, smax)
        if ran is None:
            return
        if self.roiClass == HorizontalRangeROI:
            if ind == 0:
                self.roi.setMin(ran[0])
            elif ind == 1:
                self.roi.setMax(ran[1])
        elif self.roiClass == CrossROI:
            self.roi.setPosition(ran)

        self.roi.blockSignals(False)
        self.spinBoxProps = [smin, smax]
        if value is not None:
            self.spinTimer.start(self.spinBoxDelay)

    def acceptEdit(self):
        self.fromSpinBox(100)
        return self.spinBoxProps

    def spinDelayed(self):
        if self.spinBoxProps is None:
            return
        self.rangeChanged.emit(list(self.spinBoxProps))
        self.spinBoxProps = None

    def toggleVisible(self, on):
        if self.roi is None:
            return
        self.roi.setVisible(on)

    def setRangeVisible(self, on):
        if hasattr(self, 'visibleCB'):
            self.visibleCB.setChecked(on)
        self.toggleVisible(on)
