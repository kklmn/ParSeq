# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "16 Apr 2023"
# !!! SEE CODERULES.TXT !!!

# import time
import os.path as osp
import numpy as np
from functools import partial
import weakref

from scipy.interpolate import InterpolatedUnivariateSpline

from silx.gui import qt, utils
from silx.gui.plot.tools.roi import (
    RegionOfInterestManager, RoiModeSelectorAction)
from silx.gui.plot.items.roi import InteractionModeMixIn, HorizontalRangeROI
import silx.gui.plot.items as plot_items
from silx.gui.colors import rgba

from . import gcommons as gco
from ..core import singletons as csi
from .propWidget import PropWidget

HEADERS = '🏷', 'use', 'geometry'
columnWidths = 36, 32, 124

__iconDir__ = osp.join(osp.dirname(__file__), '_images')
ICON_SIZE = 32


def makeMarker(obj, symbol):
    if symbol in ('X', 'Y'):
        handle = plot_items.YMarker()
    else:
        handle = plot_items.Marker()
        handle.setSymbol(symbol)
    color = rgba(gco.COLOR_CORRECTION)[:3]
    if symbol in ('d', 's', 'o'):
        color += (0.5,)
    handle.setColor(color)
    handle._setSelectable(True)
    handle.setVisible(True)
    handle._setDraggable(True)
    handle.sigDragStarted.connect(obj._editingStarted)
    handle.sigItemChanged.connect(obj._editingUpdated)
    handle.sigDragFinished.connect(obj._editingFinished)
    return handle


class CorrectionDelete(HorizontalRangeROI):
    ICON = "add-correction-delete"
    NAME = "delete region"
    SHORT_NAME = "cdelete"

    def setCorrection(self, lim):
        self.setRange(lim[0], lim[1])

    def getCorrection(self):
        return dict(name=self.getName(), kind='delete', lim=self.getRange())

    def __str__(self):
        rng = self.getRange()
        prX = self.parent().precisionX
        return 'lim:\n{0[0]:.{1}f}, {0[1]:.{1}f}'.format(rng, prX)

    def setFromTxt(self, txt):
        try:
            txt = txt.replace(':', '=(')
            kw = eval('dict({0}))'.format(txt))
            self.setCorrection(**kw)
        except Exception as e:
            print("Error in `CorrectionDelete.setFromTxt()`: " + str(e))
            return False
        return True


class CorrectionScale(HorizontalRangeROI):
    ICON = "add-correction-scale"
    NAME = "scale region"
    SHORT_NAME = "cscale"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._scale = 1.
        # self._scaleHandle = makeMarker(self, 'd')
        self._scaleHandle = makeMarker(self, 'Y')
        self.addItem(self._scaleHandle)

    def setFirstShapePoints(self, points):
        y = points[-1][1]
        self.setScale(y)
        super().setFirstShapePoints(points)

    def getScale(self):
        return self._scaleHandle.getPosition()[1]

    def setScale(self, scale):
        self._scale = scale
        handle = self._scaleHandle
        with utils.blockSignals(handle):
            handle.setPosition(None, scale)
        self.sigRegionChanged.emit()

    def _editingUpdated(self):
        handle = self.sender()
        if handle is not self._scaleHandle:
            return
        self._scale = np.array(handle.getPosition())[1]
        self.sigRegionChanged.emit()

    def setVisible(self, visible):
        self._scaleHandle.setVisible(visible)
        super().setVisible(visible)

    def _updatedStyle(self, event, style):
        super()._updatedStyle(event, style)
        m = self._scaleHandle
        m.setColor(style.getColor())
        m.setLineWidth(style.getLineWidth()*0.75)

    def setCorrection(self, lim, scale):
        self.setRange(lim[0], lim[1])
        self.setScale(scale)

    def getCorrection(self):
        return dict(name=self.getName(), kind='scale',
                    lim=self.getRange(), scale=self.getScale())

    def __str__(self):
        prX = self.parent().precisionX
        prY = self.parent().precisionY
        text = 'lim:\n{0[0]:.{1}f}, {0[1]:.{1}f}'.format(self.getRange(), prX)
        text += '\nscale:\n{0:.{1}f}'.format(self.getScale(), prY)
        return text

    def setFromTxt(self, txt):
        try:
            rows = txt.split('\n')
            kw = dict(lim=list(eval(rows[1])), scale=eval(rows[3]))
            self.setCorrection(**kw)
        except Exception as e:
            print("Error in `CorrectionScale.setFromTxt()`: " + str(e))
            return False
        return True


class CorrectionSpline(HorizontalRangeROI):
    ICON = "add-correction-spline"
    NAME = "replace region by spline"
    SHORT_NAME = "cspline"
    SPLINE_LEN = 100

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._knots = [[0, 0]]
        self._handlesKnots = []

        shape = plot_items.Shape("polylines")
        shape.setColor(rgba(gco.COLOR_CORRECTION))
        shape.setFill(False)
        shape.setOverlay(True)
        shape.setLineStyle(':')
        shape.setLineWidth(1)
        self.__shape = shape
        self.addItem(shape)

    def setFirstShapePoints(self, points):
        self.setKnots(points)
        super().setFirstShapePoints(points)

    def getKnots(self):
        knots = []
        for handle in self._handlesKnots:
            knots.append(handle.getPosition())
        knots = sorted(knots, key=lambda k: k[0])
        return np.array(knots)

    def setKnots(self, knots):
        self._knots = knots
        self.setSpline()

        if len(self._handlesKnots) > len(knots):
            for handle in reversed(self._handlesKnots[len(knots):]):
                self.removeItem(handle)
                self._handlesKnots.remove(handle)
                handle.sigDragStarted.disconnect(self._editingStarted)
                handle.sigItemChanged.disconnect(self._editingUpdated)
                handle.sigDragFinished.disconnect(self._editingFinished)
        elif len(self._handlesKnots) < len(knots):
            for i in range(len(knots) - len(self._handlesKnots)):
                handle = makeMarker(self, 'o')
                self.addItem(handle)
                self._handlesKnots.append(handle)

        for handle, point in zip(self._handlesKnots, self._knots):
            with utils.blockSignals(handle):
                handle.setPosition(point[0], point[1])
        self.sigRegionChanged.emit()

    def setSpline(self):
        if len(self._knots) == 0:
            return
        rng = self.getRange()
        knots = sorted(self._knots.tolist(), key=lambda k: k[0])
        if len(knots) == 1:
            y = knots[0][1]
            if rng[0] < knots[0][0]:  # add a leg to the left limit
                knots.insert(0, [rng[0], y])
            if rng[1] > knots[-1][0]:  # add a leg to the right limit
                knots.append([rng[1], y])
            self.__shape.setPoints(knots)
        else:  # len(knots) >= 2:
            kns = np.array(knots)  # knots is a list of lists
            k = min(len(knots)-1, 3)
            try:
                spl = InterpolatedUnivariateSpline(kns[:, 0], kns[:, 1], k=k)
                xs = np.linspace(rng[0], rng[1], self.SPLINE_LEN)
                ys = spl(xs)
                self.__shape.setPoints(np.column_stack((xs, ys)))
            except ValueError:
                self.__shape.setPoints([[0., 0.]])
                # print('Error in `setSpline()`: {0}'.format(e))
                pass

    def _editingUpdated(self):
        handle = self.sender()
        if handle not in self._handlesKnots:
            return
        iKnot = self._handlesKnots.index(handle)
        self._knots[iKnot] = np.array(handle.getPosition())
        self.setSpline()
        self.sigRegionChanged.emit()

    def _editingFinished(self):
        self.setSpline()
        super()._editingFinished()

    def setVisible(self, visible):
        for handle in self._handlesKnots:
            handle.setVisible(visible)
        self.__shape.setVisible(visible)
        super().setVisible(visible)

    def setCorrection(self, lim, knots, length=None):
        self.setRange(lim[0], lim[1])
        if length is not None and len(knots) != length:
            if len(knots) < length:
                newKnots = [knot for knot in knots]
                x0, x1 = knots[-1][0], lim[1]
                dN = length - len(knots)
                newKnots += [[x0 + (i+1)*(x1-x0)/(dN+1), knots[-1][1]]
                             for i in range(dN)]
            elif len(knots) > length:
                newKnots = knots[:length]
            knots = newKnots
        self.setKnots(np.array(knots))
        self.setSpline()

    def getCorrection(self):
        return dict(name=self.getName(), kind='spline',
                    lim=self.getRange(), knots=self.getKnots())

    def __str__(self):
        rng = self.getRange()
        prX = self.parent().precisionX
        prY = self.parent().precisionY
        text = 'lim:\n{0[0]:.{1}f}, {0[1]:.{1}f}'.format(rng, prX)
        if len(self._knots) > 0:
            text += '\nknots: {0}'.format(len(self._knots))
            for knot in self._knots:
                text += '\n{0[0]:.{1}f}, {0[1]:.{2}f}'.format(knot, prX, prY)
        return text

    def setFromTxt(self, txt):
        try:
            txt = txt.replace(':', '=(')
            rows = txt.split('\n')
            s = 'dict(' + ''.join(rows[:2]) + '))'
            kw = eval(s)
            s = rows[2]
            kw['length'] = int(s[s.find('knots')+7:])
            if kw['length'] < 1:
                raise ValueError('length must be > 0')
            kw['knots'] = []
            for row in rows[3:]:
                kw['knots'].append(list(eval(row)))
            self.setCorrection(**kw)
        except Exception as e:
            print("Error in `CorrectionSpline.setFromTxt()`: " + str(e))
            return False
        return True


class CorrectionStep(HorizontalRangeROI):
    ICON = "add-correction-step"
    NAME = "remove data step"
    SHORT_NAME = "cstep"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._right = [0, 0]
        self._rightHandle = makeMarker(self, '+')
        self.addItem(self._rightHandle)
        self._markerMin._setConstraint(self.__positionMinConstraint)

    def setFirstShapePoints(self, points):
        self.setRight(points[-1])
        self._markerMax.setVisible(False)
        self._markerCen.setVisible(False)
        super().setFirstShapePoints(points)

    def _updateText(self, text: str):
        self._markerMin.setText(text)

    def getRight(self):
        return self._rightHandle.getPosition()

    def setRight(self, right):
        self._right = np.array(right)
        handle = self._rightHandle
        with utils.blockSignals(handle):
            handle.setPosition(right[0], right[1])
        self.sigRegionChanged.emit()

    def _editingUpdated(self):
        handle = self.sender()
        if handle is not self._rightHandle:
            return
        self._right = np.array(handle.getPosition())
        self.sigRegionChanged.emit()

    # left: x left of the step; right: [x right of the step, y where to put it]
    def setCorrection(self, left, right):
        self.setRange(left, left+1)
        if right[0] < left:
            right[0] = left
        self.setRight(right)

    def setVisible(self, visible):
        super().setVisible(visible)
        self._markerMax.setVisible(False)
        self._markerCen.setVisible(False)
        self._rightHandle.setVisible(visible)

    def __positionMinConstraint(self, x, y):
        return x, y

    def getCorrection(self):
        return dict(name=self.getName(), kind='step',
                    left=self.getRange()[0], right=self.getRight())

    def __str__(self):
        prX = self.parent().precisionX
        prY = self.parent().precisionY
        text = 'left:\n{0[0]:.{1}f}'.format(self.getRange(), prX)
        text += '\nright:\n{0[0]:.{1}f}, {0[1]:.{2}f}'.format(
            self.getRight(), prX, prY)
        return text

    def setFromTxt(self, txt):
        try:
            rows = txt.split('\n')
            kw = dict(left=eval(rows[1]), right=list(eval(rows[3])))
            self.setCorrection(**kw)
        except Exception as e:
            print("Error in `CorrectionStep.setFromTxt()`: " + str(e))
            return False
        return True


class CreateCorrectionModeAction(qt.QAction):
    def __init__(self, parent, roiManager, roiClass):
        assert roiManager is not None
        assert roiClass is not None
        qt.QAction.__init__(self, parent=parent)
        self._roiManager = weakref.ref(roiManager)
        self._roiClass = roiClass
        self._singleShot = False
        self._initAction()
        self.triggered[bool].connect(self._actionTriggered)

    def _initAction(self):
        """Default initialization of the action"""
        roiClass = self._roiClass

        name = None
        iconName = None
        if hasattr(roiClass, "NAME"):
            name = roiClass.NAME
        if hasattr(roiClass, "ICON"):
            iconName = roiClass.ICON

        if name is None:
            name = roiClass.__name__
        text = 'Add "{0}"\nby pressing this button\nand dragging in the plot'\
            .format(name)

        if iconName is not None:
            iname = 'icon-{0}-{1}.png'.format(iconName, ICON_SIZE)
            icon = qt.QIcon(osp.join(__iconDir__, iname))
            self.setIcon(icon)
        self.setText(text)
        self.setCheckable(True)
        self.setToolTip(text)

    def getRoiClass(self):
        return self._roiClass

    def getRoiManager(self):
        return self._roiManager()

    def setSingleShot(self, singleShot):
        self._singleShot = singleShot

    def getSingleShot(self):
        return self._singleShot

    def _actionTriggered(self, checked):
        """Handle mode actions being checked by the user

        :param bool checked:
        :param str kind: Corresponding shape kind
        """
        roiManager = self.getRoiManager()
        if roiManager is None:
            return

        if checked:
            roiManager.start(self._roiClass, self)
            self.__interactiveModeStarted(roiManager)
        else:
            source = roiManager.getInteractionSource()
            if source is self:
                roiManager.stop()

    def __interactiveModeStarted(self, roiManager):
        roiManager.sigInteractiveRoiCreated.connect(self.initRoi)
        roiManager.sigInteractiveRoiFinalized.connect(self.__finalizeRoi)
        roiManager.sigInteractiveModeFinished.connect(
            self.__interactiveModeFinished)

    def __interactiveModeFinished(self):
        roiManager = self.getRoiManager()
        if roiManager is not None:
            roiManager.sigInteractiveRoiCreated.disconnect(self.initRoi)
            roiManager.sigInteractiveRoiFinalized.disconnect(
                self.__finalizeRoi)
            roiManager.sigInteractiveModeFinished.disconnect(
                self.__interactiveModeFinished)
        self.setChecked(False)

    def initRoi(self, roi):
        """Inherit it to custom the new ROI at it's creation during the
        interaction."""
        pass

    def __finalizeRoi(self, roi):
        self.finalizeRoi(roi)
        if self._singleShot:
            roiManager = self.getRoiManager()
            if roiManager is not None:
                roiManager.stop()

    def finalizeRoi(self, roi):
        """Inherit it to custom the new ROI after it's creation when the
        interaction is finalized."""
        pass


# class CorrectionManager(InteractiveRegionOfInterestManager):
class CorrectionManager(RegionOfInterestManager):

    def __init__(self, parent):
        super().__init__(parent)
        self.precisionX = 2
        self.precisionY = 2
        self.setColor(gco.COLOR_CORRECTION)
        self.sigRoiAdded.connect(self.updateAddedRegionOfInterest)
        self._modeActions = {}

    def updateAddedRegionOfInterest(self, roi):
        # silx.gui.plot.tools.roi.RegionOfInterestManager.ROI_CLASSES:
        if roi.getName() == '':
            if isinstance(roi, CorrectionDelete):
                name = 'del'
            elif isinstance(roi, CorrectionScale):
                name = 'scl'
            elif isinstance(roi, CorrectionSpline):
                name = 'spl'
            elif isinstance(roi, CorrectionStep):
                name = 'stp'
            else:
                name = 'cor'
            roi.setName('{0}{1}'.format(name, len(self.getRois())))
        try:
            roi.setLineWidth(0.5)
            roi.setLineStyle('-')
        except AttributeError as e:
            print(e)
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
                            print(e)

                removeAction = qt.QAction(menu)
                removeAction.setText("Remove %s" % roi.getName())
                callback = partial(self.removeRoi, roi)
                removeAction.triggered.connect(callback)
                menu.addAction(removeAction)

    def getInteractionModeAction(self, roiClass):
        action = self._modeActions.get(roiClass, None)
        if action is None:  # Lazy-loading
            action = CreateCorrectionModeAction(self, self, roiClass)
            self._modeActions[roiClass] = action
        return action


class CorrectionModel(qt.QAbstractTableModel):
    def __init__(self, roiManager=None):
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
                return str(roi)
        elif role == qt.Qt.CheckStateRole:
            if column == 1:  # use
                return qt.Qt.Checked if roi.isVisible() else qt.Qt.Unchecked
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
                return roi.setFromTxt(value)
            else:
                return False
        elif role == qt.Qt.CheckStateRole:
            row = index.row()
            roi = rois[row]
            roi.setVisible(bool(value))
            return True
        return False


class CorrectionToolBar(qt.QToolBar):
    """A toolbar which hide itself if no actions are visible"""

    def __init__(self, parent, roiManager, roiClassNames):
        super().__init__(parent)
        # self.setStyleSheet('QToolBar{margin: 0px 10px;}')
        self.setIconSize(qt.QSize(32, 32))

        for roiClassName in roiClassNames:
            if roiClassName == 'CorrectionDelete':
                roiClass = CorrectionDelete
            elif roiClassName == 'CorrectionScale':
                roiClass = CorrectionScale
            elif roiClassName == 'CorrectionSpline':
                roiClass = CorrectionSpline
            elif roiClassName == 'CorrectionStep':
                roiClass = CorrectionStep
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


class CorrectionTable(qt.QTableView):
    sigCorrectionChanged = qt.pyqtSignal()

    def __init__(self, parent, roiManager):
        super().__init__(parent)
        self.roiModel = CorrectionModel(roiManager)
        self.setModel(self.roiModel)

        self.setSelectionMode(self.SingleSelection)
        self.setSelectionBehavior(self.SelectRows)
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

        if "qt4" in qt.BINDING.lower():
            horHeaders.setClickable(True)
        else:
            horHeaders.setSectionsClickable(True)
        horHeaders.sectionClicked.connect(self.headerClicked)

        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenu)

        self.setItemDelegateForColumn(1, gco.CheckBoxDelegate(self))
        self.setItemDelegateForColumn(2, gco.MultiLineEditDelegate(self))

        for i in range(len(HEADERS)):
            self.setColumnWidth(i, int(columnWidths[i]*csi.screenFactor))
        self.setMinimumWidth(int(sum(columnWidths)*csi.screenFactor) + 2)
        self.setMinimumHeight(int(horHeaders.height()*4*csi.screenFactor))

        roiManager.sigCurrentRoiChanged.connect(self.currentRoiChanged)
        roiManager.sigRoiChanged.connect(self.syncRoi)

    def onCustomContextMenu(self, point):
        rois = self.roiModel.roiManager.getRois()
        ind = self.indexAt(point)
        row = ind.row()
        if row < 0:
            return
        roi = rois[row]
        menu = qt.QMenu()

        removeAction = qt.QAction(menu)
        removeAction.setText("Remove %s" % roi.getName())
        callback = partial(self.roiModel.roiManager.removeRoi, roi)
        removeAction.triggered.connect(callback)
        menu.addAction(removeAction)

        menu.exec_(self.viewport().mapToGlobal(point))

    def headerClicked(self, column):
        if column in [0, 1, 2]:
            rois = self.roiModel.roiManager.getRois()
            for roi in rois:
                roi.setVisible(not roi.isVisible())

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

    def syncRoi(self):
        model = self.roiModel
        rois = model.roiManager.getRois()

        curRoi = model.roiManager.getCurrentRoi()
        if curRoi is None and rois:
            curRoi = rois[0]
        if curRoi is None:
            return

        row = rois.index(curRoi)
        ind1 = model.index(row, 2)
        ind2 = model.index(row, 3)
        model.dataChanged.emit(ind1, ind2)

        if self.parent().isLive:
            self.sigCorrectionChanged.emit()

    def getCorrections(self):
        corrs = self.roiModel.roiManager.getRois()
        return [corr.getCorrection() for corr in corrs if corr.isVisible()]


class Correction1DWidget(PropWidget):
    def __init__(self, parent, node, plot, roiClassNames):
        """
        *roiClassNames*: sequence of class names to appear in the toolbar
        """
        super().__init__(parent, node)
        self.plot = plot
        self.isLive = False
        self.is3dStack = hasattr(self.plot, '_plot')
        self.roiManager = CorrectionManager(
            plot._plot if self.is3dStack else plot)

        layout = qt.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.roiToolbar = CorrectionToolBar(
            self, self.roiManager, roiClassNames)
        layout.addWidget(self.roiToolbar)

        layoutP = qt.QHBoxLayout()
        self.liveCB = qt.QCheckBox('live')
        self.liveCB.setChecked(self.isLive)
        self.liveCB.toggled.connect(self.setLive)
        self.liveCB.setToolTip('live correction update\n'
                               'while dragging in the plot')
        layoutP.addWidget(self.liveCB)
        layoutP.addStretch()
        lp = qt.QLabel('precisions:')
        lp.setToolTip('decimals in X and Y geometry values')
        layoutP.addWidget(lp)
        self.precisionXSB = qt.QSpinBox()
        self.precisionXSB.setMaximum(9)
        self.precisionXSB.setMaximumWidth(30)
        self.precisionXSB.setValue(self.roiManager.precisionX)
        self.precisionXSB.setToolTip('decimals in X geometry values')
        self.precisionXSB.valueChanged.connect(self.precisionXChanged)
        layoutP.addWidget(self.precisionXSB)
        self.precisionYSB = qt.QSpinBox()
        self.precisionYSB.setMaximum(9)
        self.precisionYSB.setMaximumWidth(30)
        self.precisionYSB.setValue(self.roiManager.precisionY)
        self.precisionYSB.setToolTip('decimals in Y geometry values')
        self.precisionYSB.valueChanged.connect(self.precisionYChanged)
        layoutP.addWidget(self.precisionYSB)
        layout.addLayout(layoutP)

        self.table = CorrectionTable(self, self.roiManager)
        layout.addWidget(self.table, 1)

        self.acceptButton = qt.QPushButton('Accept Corrections')
        self.acceptButton.clicked.connect(self.table.sigCorrectionChanged.emit)
        layout.addWidget(self.acceptButton, 1)
        layout.addStretch()
        self.setLayout(layout)

        if node is not None:
            corr_param_name = 'correction_' + node.name
            self.registerPropWidget(self.table, 'correction', corr_param_name)
            # transformNames=[tr.name for tr in node.transformsIn])

        self.setSizePolicy(qt.QSizePolicy.Minimum, qt.QSizePolicy.Minimum)

    def setLive(self, checked):
        self.isLive = checked

    def precisionXChanged(self, i):
        self.roiManager.precisionX = i
        model = self.table.roiModel
        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def precisionYChanged(self, i):
        self.roiManager.precisionY = i
        model = self.table.roiModel
        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def setCorrections(self, roiDicts):
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
                if kind == 'CorrectionDelete':
                    roi = CorrectionDelete()
                elif kind == 'CorrectionScale':
                    roi = CorrectionScale()
                elif kind == 'CorrectionSpline':
                    roi = CorrectionSpline()
                elif kind == 'CorrectionStep':
                    roi = CorrectionStep()
                else:
                    # continue
                    raise ValueError('unsupported ROI "{0}"'.format(kind))
                if name:
                    roi.setName(name)
                roi.setVisible(True)
                roi.setCorrection(**roid)
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
                roi.setCorrection(**roid)

        model.reset()
        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def getCurrentCorrection(self):
        curRoi = self.roiManager.getCurrentRoi()
        if curRoi is None or not curRoi.isVisible():
            return
        return curRoi.getCorrection()

    def getCorrections(self):
        return self.table.getCorrections()
