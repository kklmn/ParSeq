# -*- coding: utf-8 -*-
u"""
The `DataTreeModel` implements view model of a collection of data loaded into a
Parseq app. The model has several columns: the 1st one is the data name
(or alias), the 2nd is the data view state and the next columns refer to all y
columns listed over all pipeline nodes and contain their plotting properties.
For each node, visible in `DataTreeView` are the first two columns plus the y
column(s) defined for this node. Note again, the model is only one, it includes
data in _all_ nodes.

The underlying items in the model (obtained by item = index.internalPointer())
are instances of :class:`core.spectra.Spectrum`. The root item is stored in
core.singletons.dataRootItem.

The selected items can be accessed by core.singletons.selectedItems and
core.singletons.selectedTopItems lists.
"""
__author__ = "Konstantin Klementiev"
__date__ = "19 Jul 2022"
# !!! SEE CODERULES.TXT !!!

import sys
from functools import partial
import pickle

from silx.gui import qt

from ..core import commons as cco
from ..core import singletons as csi
from ..core import transforms as ctr
from . import gcommons as gco
from . import undoredo as gur
from .plotOptions import lineStyles, lineSymbols, noSymbols, LineProps

COLUMN_NAME_WIDTH = 140
COLUMN_EYE_WIDTH = 28
LEGEND_WIDTH = 48  # '|FT(χ)|' fits into 48

GROUP_BKGND = gco.GROUP_COLOR
BUSY_BKGND = gco.BUSY_COLOR_BGND
BAD_BKGND = gco.BAD_COLOR
UNDEFINED_BKGND = gco.UNDEFINED_COLOR
NOTFOUND_BKGND = gco.NOTFOUND_COLOR
MATHERROR_BKGND = gco.MATHERROR_COLOR
BKGND = {cco.DATA_STATE_GOOD: None,
         cco.DATA_STATE_BAD: BAD_BKGND,
         cco.DATA_STATE_UNDEFINED: UNDEFINED_BKGND,
         cco.DATA_STATE_NOTFOUND: NOTFOUND_BKGND,
         cco.DATA_STATE_MATHERROR: MATHERROR_BKGND}

FONT_COLOR_TAG = ['black', gco.COLOR_HDF5_HEAD, gco.COLOR_FS_COLUMN_FILE,
                  gco.COLOR_UNDEFINED, gco.COLOR_ROI, gco.COLOR_COMBINED,
                  'cyan']
LEFT_SYMBOL = u"\u25c4"  # ◄
RIGHT_SYMBOL = u"\u25ba"  # ►
SELECTION_ALPHA = 0.15
# CHECKED_SYMBOL = u"\u2611"  # ☑
# UNCHECKED_SYMBOL = u"\u2610"  # ☐
# CHECKED_SYMBOL = u"\u2714"  # ✔
# CHECKED_SYMBOL = u"\u2713"  # ✓
# UNCHECKED_SYMBOL = None

PROGRESS_ROLE = qt.Qt.UserRole + 1


class DataTreeModel(qt.QAbstractItemModel):

    needReplot = qt.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rootItem = csi.dataRootItem

    def rowCount(self, parent=qt.QModelIndex()):
        parentItem = parent.internalPointer() if parent.isValid() else\
            self.rootItem
        return parentItem.child_count()

    def columnCount(self, parent):
        return len(csi.modelLeadingColumns) + len(csi.modelDataColumns)

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        # res = super().flags(index) |
        res = qt.Qt.ItemIsSelectable | qt.Qt.ItemIsDragEnabled | \
            qt.Qt.ItemIsDropEnabled
        if index.column() == 1:
            res |= qt.Qt.ItemIsUserCheckable
            isDim1 = True
            if csi.currentNode is not None:
                isDim1 = csi.currentNode.plotDimension == 1
            if csi.dataRootItem.isVisible and isDim1:
                res |= qt.Qt.ItemIsEnabled
        else:
            res |= qt.Qt.ItemIsEnabled

        cond = index.column() == 0  # editable for all items in column 0
#        item = index.internalPointer()
#        cond = cond and item.childItems  # editable only if is a group
        if cond:
            res |= qt.Qt.ItemIsEditable
        return res

    def data(self, index, role=qt.Qt.DisplayRole, nodeName=''):
        if not index.isValid():
            return
        item = index.internalPointer()
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            return item.data(index.column())
        elif role == qt.Qt.CheckStateRole:
            if index.column() == 1:
                return int(
                    qt.Qt.Checked if item.isVisible else qt.Qt.Unchecked)
        elif role == qt.Qt.ToolTipRole:
            if csi.currentNode is not None:
                node = csi.currentNode
                if node.widget is not None:
                    if node.widget.onTransform:
                        return
            return item.tooltip()
        elif role == PROGRESS_ROLE:
            return item.progress if item.beingTransformed else None
        elif role == qt.Qt.BackgroundRole:
            if item.beingTransformed and index.column() == 0:
                return BUSY_BKGND
            if item.childItems:  # is a group
                return GROUP_BKGND
            color = BKGND[item.get_state(nodeName)] if nodeName else None
            return color
        elif role == qt.Qt.ForegroundRole:
            if index.column() < len(csi.modelLeadingColumns):
                return qt.QColor(FONT_COLOR_TAG[item.colorTag])
            else:
                return qt.QColor(item.color)
        elif role == qt.Qt.FontRole:
            if item.childItems and (index.column() == 0):  # group in bold
                myFont = qt.QFont()
                myFont.setBold(True)
                return myFont
        elif role == qt.Qt.TextAlignmentRole:
            if index.column() == 1:
                return qt.Qt.AlignCenter

    def setData(self, index, value, role=qt.Qt.EditRole):
        if role == qt.Qt.EditRole:
            item = index.internalPointer()
            item.set_data(index.column(), str(value))
#            item.aliasExtra = None
            self.dataChanged.emit(index, index)
            self.needReplot.emit()
            return True
        elif role == qt.Qt.CheckStateRole:
            item = index.internalPointer()
            self.setVisible(item, value)
            return True
        return False

    def setVisible(self, item, value, emit=True):
        item.set_visible(value)
        if emit:
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            self.needReplot.emit()
        if item is csi.dataRootItem:  # by click on header
            for it in csi.selectedItems:
                self.setVisible(it, True, True)
            return
        if item.parentItem is csi.dataRootItem:
            return

        # make group (un)checked if all group items are (un)checked:
        siblingsEqual = False
        for itemSib in item.parentItem.childItems:
            if itemSib.isVisible != item.isVisible:
                break
        else:
            siblingsEqual = True
        if siblingsEqual and (item.parentItem.isVisible != item.isVisible):
            item.parentItem.set_visible(value)

    def index(self, row, column=0, parent=None):
        if parent is None:
            parent = qt.QModelIndex()
        if not self.hasIndex(row, column, parent):
            return qt.QModelIndex()
        parentItem = parent.internalPointer() if parent.isValid() else\
            self.rootItem
        rowItem = parentItem.child(row)
        if rowItem is None:
            return qt.QModelIndex()
        return self.createIndex(row, column, rowItem)

    def indexFromItem(self, item):
        return self.createIndex(item.row(), 0, item)

    def parent(self, index):
        if not index.isValid():
            return qt.QModelIndex()
        item = index.internalPointer()
        parentItem = item.parentItem
        if parentItem is self.rootItem:
            return qt.QModelIndex()
        try:
            return self.createIndex(parentItem.row(), 0, parentItem)
        except (TypeError, AttributeError):
            return qt.QModelIndex()

    def getItems(self, indexes):
        items = []
        for index in indexes:
            item = index.internalPointer()
            childN = item.child_count()
            if childN > 0:  # is a group
                subInd = [self.index(i, 0, index) for i in range(childN)]
                items += [i for i in self.getItems(subInd) if i not in items]
            else:
                if item not in items:  # inclusion check that keeps the order
                    items.append(item)
        return items

    def getTopItems(self, indexes):
        items = [i.internalPointer() for i in indexes]
        return [item for item in items if item.parentItem not in items]

    def importData(self, data, parentItem=None, insertAt=None, **kwargs):
        if parentItem is None:
            parentItem = self.rootItem
        self.beginResetModel()
        items = parentItem.insert_data(data, insertAt, **kwargs)
        ctr.connect_combined(items, parentItem)
        ctr.run_transforms(items, parentItem)
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

        mode = qt.QItemSelectionModel.Select | qt.QItemSelectionModel.Rows
        for item in items:
            row = item.row()
            index = self.createIndex(row, 0, item)
            csi.selectionModel.select(index, mode)
        return items

    def _removeFromGlobalLists(self, item):
        for ll in (csi.selectedItems, csi.selectedTopItems,
                   csi.recentlyLoadedItems, csi.allLoadedItems):
            if item in ll:
                ll.remove(item)

    def removeData(self, data):
        struct = [(d.parentItem, d.childItems.copy(), d.row()) for d in data]
        gur.pushDataToUndo(data.copy(), struct, strChange='remove')
        self.beginResetModel()
        for item in reversed(data):
            item.remove_from_parent()
            self._removeFromGlobalLists(item)

            # subs = item.get_items(True)
            subs = item.childItems
            for subItem in reversed(subs):
                subItem.remove_from_parent()
                self._removeFromGlobalLists(subItem)
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.needReplot.emit()

    def undoRemove(self, undoEntry):
        if undoEntry[-1] != 'remove':
            return
        self.beginResetModel()
        data, struct = undoEntry[0:2]
        for item, (parentItem, childItems, row) in zip(data, struct):
            item.childItems = childItems
            if parentItem is not csi.dataRootItem and parentItem.row() is None:
                csi.dataRootItem.childItems.append(item)
                item.parentItem = csi.dataRootItem
            else:
                parentItem.childItems.insert(row, item)
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.needReplot.emit()

    def moveItem(self, item, to):  # to = +1(up) or -1(down)
        parentItem = item.parentItem
        row = item.row()
        if row is None:
            return
        endRow = 0 if to == +1 else parentItem.child_count()-1
        if parentItem is self.rootItem and row == endRow:
            return

        siblings = parentItem.childItems
        self.beginResetModel()
        if row == endRow:
            insertAt = parentItem.row() if to == +1 else parentItem.row()+1
            parentItem.parentItem.childItems.insert(insertAt, item)
            item.parentItem = parentItem.parentItem
            del siblings[row]
            if parentItem.child_count() == 0:
                parentItem.remove_from_parent()
        elif (siblings[row-to].child_count() > 0):
            insertAt = len(siblings[row-to].childItems) if to == +1 else 0
            siblings[row-to].childItems.insert(insertAt, item)
            item.parentItem = siblings[row-to]
            del siblings[row]
            if parentItem.child_count() == 0:
                parentItem.remove_from_parent()
        else:
            siblings[row-to], siblings[row] = siblings[row], siblings[row-to]
        self.endResetModel()
        item.parentItem.init_colors()
        if not (parentItem is item.parentItem):
            parentItem.init_colors()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def groupItems(self, items):
        parentItem, row = items[0].parentItem, items[0].row()
        self.beginResetModel()

        # make group name:
        cs = items[0].alias
        for item in items[1:]:
            cs = cco.common_substring((cs, item.alias))
        groupName = "{0}_{1}items".format(cs, len(items)) if len(cs) > 0 else\
            "new group"
        group = parentItem.insert_item(groupName, row)
        for item in items:
            parentItem, row = item.parentItem, item.row()
            group.childItems.append(item)
            item.parentItem = group
            del parentItem.childItems[row]
            if parentItem.child_count() == 0:
                parentItem.remove_from_parent()
        self.endResetModel()
        if hasattr(group.parentItem, 'colorAutoUpdate'):
            group.colorAutoUpdate = group.parentItem.colorAutoUpdate
        group.init_colors()
        group.parentItem.init_colors()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        return group

    def ungroup(self, group):
        parentItem, row = group.parentItem, group.row()
        self.beginResetModel()
        for item in reversed(group.childItems):
            parentItem.childItems.insert(row, item)
            item.parentItem = parentItem
        parentItem.childItems.remove(group)
        self.endResetModel()
        parentItem.init_colors()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def supportedDropActions(self):
        return qt.Qt.MoveAction | qt.Qt.CopyAction

    def mimeTypes(self):
        return [cco.MIME_TYPE_DATA, cco.MIME_TYPE_TEXT, cco.MIME_TYPE_HDF5]

    def mimeData(self, indexes):
        indexes0 = [index for index in indexes if index.column() == 0]
        mimedata = qt.QMimeData()
        items = self.getTopItems(indexes0)
        bstream = pickle.dumps([item.climb_rows() for item in items])
        mimedata.setData(cco.MIME_TYPE_DATA, bstream)
        return mimedata

#    def canDropMimeData(self, data, action, row, column, parent):
#        print(data.formats())
#        return super().canDropMimeData(
#             data, action, row, column, parent)

    def dropMimeData(self, mimedata, action, row, column, parent):
        if mimedata.hasFormat(cco.MIME_TYPE_DATA):
            toItem = parent.internalPointer()
            if toItem is None:
                toItem = csi.dataRootItem
                newParentItem, newRow = toItem, toItem.child_count()
                parents = []
            else:
                newParentItem, newRow = toItem.parentItem, toItem.row()
                parents = [toItem.parentItem]
            rowss = pickle.loads(mimedata.data(cco.MIME_TYPE_DATA))
            dropedItems = []
            for rows in rowss:
                parentItem = self.rootItem
                for r in reversed(rows):
                    item = parentItem.child(r)
                    parentItem = item
                dropedItems.append(item)
                if item.parentItem not in parents:
                    parents.append(item.parentItem)
            for item in dropedItems:
                if item.is_ancestor_of(toItem):
                    msg = qt.QMessageBox()
                    msg.setIcon(qt.QMessageBox.Warning)
                    msg.setText("Cannot drop a group onto its child. Ignored")
                    msg.setWindowTitle("Illegal drop")
                    msg.setStandardButtons(qt.QMessageBox.Close)
                    msg.exec_()
                    return False

            self.beginResetModel()
            if toItem is csi.dataRootItem:
                rdropedItems = dropedItems
            else:
                rdropedItems = reversed(dropedItems)
            for item in rdropedItems:
                oldParentItem, oldRow = item.parentItem, item.row()
                if newParentItem is oldParentItem:
                    sibl = newParentItem.childItems
                    sibl.insert(newRow, sibl.pop(oldRow))
                else:
                    newParentItem.childItems.insert(newRow, item)
                    item.parentItem = newParentItem
                    del oldParentItem.childItems[oldRow]
                    if oldParentItem.child_count() == 0:
                        oldParentItem.remove_from_parent()
            self.endResetModel()
            for parent in parents:
                parent.init_colors()
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            self.needReplot.emit()
            return True
        elif mimedata.hasFormat(cco.MIME_TYPE_TEXT) or \
                mimedata.hasFormat(cco.MIME_TYPE_HDF5):
            toItem = parent.internalPointer()
            if mimedata.hasFormat(cco.MIME_TYPE_TEXT):
                urls = [url.toLocalFile() for url in reversed(mimedata.urls())]
            else:
                urls = pickle.loads(mimedata.data(cco.MIME_TYPE_HDF5))[::-1]
            if toItem is None:
                toItem = csi.dataRootItem
                urls = urls[::-1]

            if toItem.child_count() > 0:  # is a group
                parentItem, insertAt = toItem, None
            else:
                parentItem, insertAt = toItem.parentItem, toItem.row()
            if csi.currentNode is None:
                return False
            node = csi.currentNode
            if node.widget is not None:
                node.widget.loadFiles(urls, parentItem, insertAt)
                # items = node.widget.loadFiles(urls, parentItem, insertAt)
                # if DEBUG > 0:
                #     if items is not None:
                #         for item in items:
                #             item.colorTag = 3
            return True
        else:
            return False

    def invalidateData(self):
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.needReplot.emit()


class HeaderModel(qt.QAbstractItemModel):
    def __init__(self, parent=None, node=None):
        super().__init__(parent)
        self.rootItem = csi.dataRootItem
        self.node = node
        self.plotDimension = 1 if node is None else self.node.plotDimension

    def columnCount(self, parent):
        return len(csi.modelLeadingColumns) + len(csi.modelDataColumns)

    def headerData(self, section, orientation, role):
        leadingColumns = len(csi.modelLeadingColumns)
        if role == qt.Qt.DisplayRole:
            if section < leadingColumns:
                return csi.modelLeadingColumns[section]
            else:
                node, key = csi.modelDataColumns[section-leadingColumns]
                return node.get_prop(key, 'qLabel')
        elif role == qt.Qt.ToolTipRole:
            if section == 0:
                return self.rootItem.tooltip()
            elif section == 1:
                if self.plotDimension == 1:
                    return u"toggle visible: dynamic\u2194static"
                else:
                    return u"plot visibility status\n"\
                        "only one image can be displayed at a time"
            else:
                node, key = csi.modelDataColumns[section-leadingColumns]
                role = node.get_prop(key, 'role')
                if role.startswith('0'):
                    label = node.get_prop(key, 'qLabel')
                    unit = node.get_prop(key, 'qUnit')
                    unitStr = ' ({0})'.format(unit) if unit else ''
                    return label + unitStr
                else:
                    return "line properties (Ctrl+P)"
        elif role == qt.Qt.TextAlignmentRole:
            if section > 0:
                return qt.Qt.AlignHCenter


class SelectionModel(qt.QItemSelectionModel):
    pass


class NodeDelegate(qt.QItemDelegate):
    def __init__(self, parent, nodeName=''):
        self.nodeName = nodeName
        super().__init__(parent)


class DataNameDelegate(NodeDelegate):
    def paint(self, painter, option, index):
        # if index.column() == 1:
        #     super().paint(painter, option, index)
        data = index.data(qt.Qt.DisplayRole)
        if data is None:
            return
        rect = option.rect.translated(0, 0)  # a copy of option.rect
        progress = index.data(PROGRESS_ROLE)
        if progress is not None:
            rect.setWidth(int(progress*rect.width()))
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, False)
        painter.setPen(qt.Qt.NoPen)
        bd = index.data(qt.Qt.BackgroundRole)
        # bd = index.model().data(index, qt.Qt.BackgroundRole, self.nodeName)
        if (option.state & qt.QStyle.State_Selected or
                option.state & qt.QStyle.State_MouseOver) and bd is None:
            color = self.parent().palette().highlight().color()
            color.setAlphaF(SELECTION_ALPHA)
        else:
            color = bd
        if color is not None:
            painter.setBrush(color)
        painter.drawRect(rect)

        fd = index.data(qt.Qt.ForegroundRole)
        painter.setPen(qt.QPen(fd))

        font = index.data(qt.Qt.FontRole)
        if font is not None:
            painter.setFont(font)
        rect = option.rect
        painter.drawText(option.rect, qt.Qt.AlignLeft, "{0}".format(data))

        painter.restore()


class DataCheckDelegate(NodeDelegate):
    coords = [(-5, 1), (-2, 4), (5, -4), 'open, 1.5']

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, True)
        painter.setPen(qt.Qt.NoPen)
        # bd = index.data(qt.Qt.BackgroundRole)
        bd = index.model().data(index, qt.Qt.BackgroundRole, self.nodeName)
        if (option.state & qt.QStyle.State_Selected or
                option.state & qt.QStyle.State_MouseOver) and bd is None:
            color = self.parent().palette().highlight().color()
            color.setAlphaF(SELECTION_ALPHA)
        else:
            color = bd
        if color is not None:
            painter.setBrush(color)
        painter.drawRect(option.rect)

        state = index.data(qt.Qt.CheckStateRole)
        if state == qt.Qt.Checked:
            pointerPath = qt.QPainterPath()
            pointerPath.moveTo(*self.coords[0])
            for xy in self.coords[1:]:
                if isinstance(xy, tuple):
                    pointerPath.lineTo(*xy)
                if isinstance(xy, type('')):
                    end = xy.split(',')
                    if end[0] == 'close':
                        pointerPath.closeSubpath()
            thick = float(end[1].strip())
            if option.state & qt.QStyle.State_Enabled:
                if option.state & qt.QStyle.State_MouseOver:
                    painter.setPen(qt.QPen(qt.Qt.darkBlue, thick))
                else:
                    painter.setPen(qt.QPen(qt.Qt.darkGray, thick))
            else:
                painter.setPen(qt.QPen(qt.Qt.lightGray, thick))
            pointerPath.translate(option.rect.x() + option.rect.width()//2,
                                  option.rect.y() + option.rect.height()//2)
            color = qt.QColor(qt.Qt.white)
            color.setAlphaF(0.)
            symbolBrush = qt.QBrush(color)
            painter.setBrush(symbolBrush)
            painter.drawPath(pointerPath)
        painter.restore()


class LineStyleDelegate(NodeDelegate):
    def paint(self, painter, option, index):
        if csi.currentNode is not None:
            node = csi.currentNode
            if node.widget is not None:
                if node.widget.onTransform:
                    return
        data = index.data(qt.Qt.DisplayRole)
        if data is None:
            return
        # bknd = index.data(qt.Qt.BackgroundRole)
        bknd = index.model().data(index, qt.Qt.BackgroundRole, self.nodeName)

        rect = option.rect
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, True)
        painter.setPen(qt.Qt.NoPen)
        if (option.state & qt.QStyle.State_Selected or
            option.state & qt.QStyle.State_MouseOver) and bknd not in [
                BAD_BKGND, UNDEFINED_BKGND, NOTFOUND_BKGND, MATHERROR_BKGND]:
            color = self.parent().palette().highlight().color()
            color.setAlphaF(SELECTION_ALPHA)
        else:
            color = bknd
        if color is not None:
            painter.setBrush(color)
        painter.drawRect(rect)

        if (type(data) is tuple and
                bknd not in [BAD_BKGND, UNDEFINED_BKGND, NOTFOUND_BKGND,
                             MATHERROR_BKGND]):  # plot props
            lineColor = qt.QColor(data[0])
            lineProps = data[1]
            lineWidth = lineProps.get('linewidth', 1.0) + 0.7
            lineStyle = lineStyles[lineProps.get('linestyle', '-')]

            if lineStyle == qt.Qt.NoPen:
                painter.setPen(qt.QPen(qt.Qt.lightGray))
                painter.drawText(option.rect, qt.Qt.AlignCenter, "hidden")
            else:
                axisY = lineProps.get('yaxis', -1)
                if isinstance(axisY, type("")):
                    axisY = -1 if axisY.startswith("l") else 1

                # line
                linePen = qt.QPen(
                    qt.QBrush(lineColor), lineWidth, lineStyle, qt.Qt.FlatCap)
                painter.setPen(linePen)
                linePath = qt.QPainterPath()
                if axisY == -1:  # forbid left arrow, comment out to allow it
                    axisY = 0
                dl = lineWidth if axisY == -1 else 0
                dr = lineWidth if axisY == 1 else 0
                linePath.moveTo(
                    rect.left()+3+dl, (rect.top()+rect.bottom())*0.5)
                linePath.lineTo(
                    rect.right()-3-dr, (rect.top()+rect.bottom())*0.5)
                painter.drawPath(linePath)

                # > or < symbol
                font = painter.font()
                font.setFamily("Arial")
                font.setPointSize(4 + round(lineWidth))
                painter.setFont(font)

                dh = 2
                rect.setBottom(rect.bottom()-dh)
                if axisY == -1:
                    painter.drawText(
                        rect, qt.Qt.AlignLeft | qt.Qt.AlignVCenter,
                        LEFT_SYMBOL)
                elif axisY == 1:
                    painter.drawText(
                        rect, qt.Qt.AlignRight | qt.Qt.AlignVCenter,
                        RIGHT_SYMBOL)
                rect.setBottom(rect.bottom()+dh)

            symbol = lineProps.get('symbol', None)
            if symbol in noSymbols:
                symbol = None
            if symbol:
                painter.setRenderHint(qt.QPainter.Antialiasing, True)
#                symbolFC = lineProps.get(
#                    'fc', lineProps.get('facecolor', qt.Qt.black))
#                symbolEC = lineProps.get(
#                    'ec', lineProps.get('edgecolor', qt.Qt.black))
                symbolFC = lineColor
                symbolEC = lineColor
                symbolSize = (lineProps.get('symbolsize', 2) + 1) * 1.75
                symbolPath = qt.QPainterPath(lineSymbols[symbol])

                scale = symbolSize
                painter.scale(scale, scale)
                symbolOffset = qt.QPointF(
                    (rect.left() + rect.right() - symbolSize)*0.5 / scale,
                    (rect.top() + rect.bottom() - symbolSize)*0.5 / scale)
                symbolPath.translate(symbolOffset)
                symbolBrush = qt.QBrush(symbolFC, qt.Qt.SolidPattern)
                # symbolPen = qt.QPen(symbolEC, 1./scale, qt.Qt.SolidLine)
                symbolPen = qt.QPen(symbolEC, 0, qt.Qt.SolidLine)

                painter.setPen(symbolPen)
                painter.setBrush(symbolBrush)
                painter.drawPath(symbolPath)
        elif type(data) is not tuple:
            if isinstance(data, int):
                if option.state & qt.QStyle.State_MouseOver:
                    painter.setPen(qt.QPen(qt.Qt.darkBlue))
                else:
                    painter.setPen(qt.QPen(qt.Qt.lightGray))
            else:
                painter.setPen(qt.QPen(qt.Qt.black))
            font = painter.font()
            # font.setFamily("Arial")
            # font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(
                option.rect, qt.Qt.AlignCenter, "{0}".format(data))
        elif bknd == UNDEFINED_BKGND:
            painter.setPen(qt.QPen(qt.Qt.red))
            font = painter.font()
            painter.setFont(font)
            painter.drawText(option.rect, qt.Qt.AlignCenter, "out")
        elif bknd == MATHERROR_BKGND:
            painter.setPen(qt.QPen(qt.Qt.red))
            font = painter.font()
            painter.setFont(font)
            painter.drawText(option.rect, qt.Qt.AlignCenter, "error")
        elif bknd == NOTFOUND_BKGND:
            painter.setPen(qt.QPen(qt.Qt.red))
            font = painter.font()
            painter.setFont(font)
            painter.drawText(option.rect, qt.Qt.AlignCenter, "not found")
        painter.restore()


class EyeHeader(qt.QHeaderView):
    EYE_PUPIL = qt.QColor('black')
    EYE_IRIS = qt.QColor('#87aecf')  # blue
    # EYE_IRIS = qt.QColor('#7B3F00')  # brown
    EYE_BROW = qt.QColor('#999999')
    # coords1 = [(0, 0), (12, 0), (12, 12), (0, 12), 'close, 0.5']
    # coords2 = [(2, 6), (5, 9), (10, 4), 'open, 1.5']

    def __init__(self, orientation=qt.Qt.Horizontal, parent=None, node=None):
        super().__init__(orientation, parent)
        self.node = node
        self.plotDimension = 1 if node is None else self.node.plotDimension
        self.setModel(HeaderModel(node=node))

    # def paintCheckBox(self, painter, rect):
    #     for coords in [self.coords1, self.coords2]:
    #         pointerPath = qt.QPainterPath()
    #         pointerPath.moveTo(*coords[0])
    #         for xy in coords[1:]:
    #             if isinstance(xy, tuple):
    #                 pointerPath.lineTo(*xy)
    #             if isinstance(xy, type('')):
    #                 end = xy.split(',')
    #                 if end[0] == 'close':
    #                     pointerPath.closeSubpath()
    #                 symbolPen = qt.QPen(
    #                     qt.Qt.black, float(end[1].strip()))
    #         symbolBrush = qt.QBrush(qt.Qt.white)
    #         painter.setPen(symbolPen)
    #         painter.setBrush(symbolBrush)
    #         pointerPath.translate(rect.x()+12, rect.y()+16)
    #         painter.drawPath(pointerPath)

    def paintEye(self, painter, rect, pupilR=1.5):
        color = self.EYE_IRIS
        painter.setBrush(color)
        painter.setPen(color)
        radius0 = 5*csi.screenFactor
        painter.drawEllipse(rect.center(), radius0, radius0)
        color = self.EYE_PUPIL
        painter.setBrush(color)
        painter.setPen(color)
        radius1 = pupilR*csi.screenFactor
        painter.drawEllipse(rect.center(), radius1, radius1)
        painter.setPen(qt.QPen(self.EYE_BROW, 1.5))
        c0 = rect.center()
        x0, y0 = c0.x(), c0.y()
        ww, hh = round(min(2.5*radius0, rect.width()//2)), round(radius0)
        painter.drawArc(
            x0-ww, round(y0-radius0), ww*2, hh*5+1, 35*16, 110*16)
        painter.drawArc(
            x0-ww, round(y0+radius0), ww*2, -hh*5+3, -35*16, -110*16)

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()
        painter.setRenderHint(qt.QPainter.Antialiasing)
        if logicalIndex == 1:
            if csi.dataRootItem.isVisible and self.plotDimension == 1:
                # self.paintCheckBox(painter, rect)
                # rect.moveTo(rect.x(), rect.y()-6)
                # self.paintEye(painter, rect)

                rect.moveTo(rect.x(), rect.y()-12)
                self.paintEye(painter, rect)
                rect.moveTo(rect.x(), rect.y()+12)
                self.paintEye(painter, rect)
                rect.moveTo(rect.x(), rect.y()+12)
                self.paintEye(painter, rect)

            else:
                self.paintEye(painter, rect, pupilR=2.8)


class DataTreeView(qt.QTreeView):

    transformProgress = qt.pyqtSignal(list)  # alias, progress.value

    def __init__(self, node=None, parent=None):
        super().__init__(parent)
        self.node = node
        self.plotDimension = 1 if node is None else self.node.plotDimension

        if csi.model is None:
            csi.model = DataTreeModel()
        self.setModel(csi.model)

        if csi.selectionModel is None:
            csi.selectionModel = SelectionModel(csi.model)
        self.setSelectionModel(csi.selectionModel)
        self.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        self.setCustomSelectionMode()
        csi.selectionModel.selectionChanged.connect(self.selChanged)

        self.setHeader(EyeHeader(node=self.node))
        horHeaders = self.header()  # QHeaderView instance
        if 'pyqt4' in qt.BINDING.lower():
            horHeaders.setMovable(False)
            horHeaders.setResizeMode(0, qt.QHeaderView.Stretch)
            horHeaders.setResizeMode(1, qt.QHeaderView.Fixed)
        else:
            horHeaders.setSectionsMovable(False)
            horHeaders.setSectionResizeMode(0, qt.QHeaderView.Stretch)
            horHeaders.setSectionResizeMode(1, qt.QHeaderView.Fixed)
        horHeaders.setStretchLastSection(False)
        horHeaders.setMinimumSectionSize(5)
        self.setColumnWidth(0, int(COLUMN_NAME_WIDTH*csi.screenFactor))
        self.setColumnWidth(1, int(COLUMN_EYE_WIDTH*csi.screenFactor))
        if node is not None:
            dataNameDelegate = DataNameDelegate(self, node.name)
            self.setItemDelegateForColumn(0, dataNameDelegate)
            dataCheckDelegate = DataCheckDelegate(self, node.name)
            self.setItemDelegateForColumn(1, dataCheckDelegate)
            totalWidth = 0
            leadingColumns = len(csi.modelLeadingColumns)
            for i, col in enumerate(csi.modelDataColumns):
                isHidden = col[0] is not node
                self.setColumnHidden(i+leadingColumns, isHidden)
                if isHidden:
                    continue
                fm = qt.QFontMetrics(self.font())
                role = col[0].get_prop(col[1], 'role')
                if role.startswith('0'):
                    width = fm.width(col[0].get_prop(col[1], 'qLabel')) + 20
                else:
                    width = LEGEND_WIDTH
                totalWidth += width
                self.setColumnWidth(
                    i+leadingColumns, int(width*csi.screenFactor))
                if 'pyqt4' in qt.BINDING.lower():
                    horHeaders.setResizeMode(
                        i+leadingColumns, qt.QHeaderView.Fixed)
                else:
                    horHeaders.setSectionResizeMode(
                        i+leadingColumns, qt.QHeaderView.Fixed)
                lineStyleDelegate = LineStyleDelegate(self, node.name)
                self.setItemDelegateForColumn(
                    i+leadingColumns, lineStyleDelegate)
            self.setMinimumSize(qt.QSize(int(
                (COLUMN_NAME_WIDTH + COLUMN_EYE_WIDTH + totalWidth) *
                csi.screenFactor), 100))

        self.collapsed.connect(self.collapse)
        self.expanded.connect(self.expand)
#        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)

        self.setDragDropMode(qt.QAbstractItemView.DragDrop)
        self.isInnerDragNDropAllowed = False
        self.setDragEnabled(self.isInnerDragNDropAllowed)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

#        self.setHeaderHidden(True)
        if "qt4" in qt.BINDING.lower():
            horHeaders.setClickable(True)
        else:
            horHeaders.setSectionsClickable(True)
        horHeaders.sectionClicked.connect(self.headerClicked)
        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenu)
        self.setHorizontalScrollBarPolicy(qt.Qt.ScrollBarAlwaysOff)

        self.transformProgress.connect(self.updateProgress)

        self.makeActions()
        self.model().dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def setCustomSelectionMode(self, mode=1):
        if mode == 0:
            csi.selectionModel.customSelectionMode = 0  # ignore update
        else:
            csi.selectionModel.customSelectionMode = 1

    def makeActions(self):
        self.actionDND = self._addAction(
            "Allow internal drag-and-drop", self.allowDND)  # , "Ctrl+D")
        self.actionDND.setCheckable(True)

        self.actionMoveUp = self._addAction(
            "Move up", partial(self.moveItems, +1), "Ctrl+Up")
        self.actionMoveDown = self._addAction(
            "Move down", partial(self.moveItems, -1), "Ctrl+Down")

        self.actionMakeGroup = self._addAction(
            "Make group", self.groupItems, "Ctrl+G")
        self.actionUngroup = self._addAction("Ungroup", self.ungroup, "Ctrl+U")

        self.actionRemove = self._addAction(
            "Remove", self.removeItemsView, "Del")

        self.actionCopyError = self._addAction(
            "Copy error traceback", self.copyError, "Ctrl+C")

        self.actionAUCC = self._addAction(
            "Auto update collective colors", self.autoUpdateColors)
        self.actionAUCC.setCheckable(True)

        self.actionLines = self._addAction(
            "Line properties", self.setLines, "Ctrl+P")

    def _addAction(self, text, slot, shortcut=None):
        action = qt.QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(qt.QKeySequence(shortcut))
        action.setShortcutContext(qt.Qt.WidgetWithChildrenShortcut)
        self.addAction(action)
        return action

    def onCustomContextMenu(self, point):
        menu = qt.QMenu()
        if len(csi.selectedTopItems) == 0:
            return

        menu.addAction(self.actionDND)
        self.actionDND.setChecked(self.isInnerDragNDropAllowed)
        menu.addAction(self.actionMoveUp)
        menu.addAction(self.actionMoveDown)
        menu.addSeparator()

        isGroupSelected = False
        if len(csi.selectedTopItems) > 1:
            menu.addAction(self.actionMakeGroup)
        elif len(csi.selectedTopItems) == 1:
            if csi.selectedTopItems[0].child_count() > 0:
                isGroupSelected = True
                menu.addAction(self.actionUngroup)

        menu.addSeparator()
        menu.addAction(self.actionRemove)

        if self.node is not None:
            if self.node.columnCount > 0:
                menu.addSeparator()
                if isGroupSelected or csi.selectedTopItems == \
                        csi.dataRootItem.get_nongroups():
                    item = csi.selectedTopItems[0]
                    try:
                        if hasattr(item, 'colorAutoUpdate'):
                            cond = item.colorAutoUpdate
                        else:
                            cond = item.parentItem.colorAutoUpdate
                        menu.addAction(self.actionAUCC)
                        self.actionAUCC.setChecked(cond)
                    except AttributeError:
                        pass
                menu.addAction(self.actionLines)

        for item in csi.selectedTopItems:
            if not hasattr(item, 'error'):
                continue
            if item.error is not None:
                menu.addSeparator()
                menu.addAction(self.actionCopyError)
                break

        menu.exec_(self.viewport().mapToGlobal(point))

    def headerClicked(self, column):
        csi.currentNode = self.node
        leadingColumns = len(csi.modelLeadingColumns)
        if column == 0:
            self.selectAll()
        elif column == 1:
            if self.plotDimension == 1:
                csi.model.setVisible(
                    csi.dataRootItem, not csi.dataRootItem.isVisible, True)
            # else:
                # csi.model.setVisible(csi.dataRootItem, False, True)
        else:
            node, key = csi.modelDataColumns[column-leadingColumns]
            role = node.get_prop(key, 'role')
            if role.startswith('0'):
                return
            self.setLines(column - leadingColumns)

    def restoreExpand(self, parent=qt.QModelIndex()):
        for row in range(csi.model.rowCount(parent)):
            ind = csi.model.index(row, 0, parent)
            item = ind.internalPointer()
            if item.child_count() > 0:  # is a group
                self.setExpanded(ind, item.isExpanded)
                self.restoreExpand(ind)

    def collapse(self, ind):
        super().collapse(ind)
        item = ind.internalPointer()
        item.isExpanded = False

    def expand(self, ind):
        super().expand(ind)
        item = ind.internalPointer()
        item.isExpanded = True

    def dataChanged(self, topLeft=qt.QModelIndex(),
                    bottomRight=qt.QModelIndex(), roles=[]):
        if "qt5" in qt.BINDING.lower():
            super().dataChanged(topLeft, bottomRight, roles)
        else:
            super().dataChanged(topLeft, bottomRight)
        self.restoreExpand()
        csi.allLoadedItems[:] = []
        csi.allLoadedItems.extend(csi.dataRootItem.get_items())
        if len(csi.allLoadedItems) == 0:
            csi.selectedItems[:] = []

    def allowDND(self):
        self.isInnerDragNDropAllowed = not self.isInnerDragNDropAllowed
        self.setDragEnabled(self.isInnerDragNDropAllowed)
        self.actionDND.setChecked(self.isInnerDragNDropAllowed)

    def autoUpdateColors(self):
        it = csi.selectedTopItems[0]
        if hasattr(it, 'colorAutoUpdate'):
            parentItem = it
        else:
            parentItem = it.parentItem
        parentItem.colorAutoUpdate = not parentItem.colorAutoUpdate
        shouldUpdateModel = parentItem.colorAutoUpdate
        if shouldUpdateModel:
            parentItem.init_colors()
            csi.model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            csi.model.needReplot.emit()

    def moveItems(self, to):
        for topItem in csi.selectedTopItems[::to]:
            csi.model.moveItem(topItem, to)
        row = csi.selectedTopItems[0].row()
        newInd = csi.model.createIndex(row, 0, csi.selectedTopItems[0])
        self.setCurrentIndex(newInd)

    def groupItems(self):
        if len(csi.selectedTopItems) <= 1:
            return
        group = csi.model.groupItems(csi.selectedTopItems)
        row = group.row()
        newInd = csi.model.createIndex(row, 0, group)
        self.setCurrentIndex(newInd)

    def ungroup(self):
        if len(csi.selectedTopItems) != 1:
            return
        if csi.selectedTopItems[0].child_count() == 0:
            return
        csi.model.ungroup(csi.selectedTopItems[0])
        mode = qt.QItemSelectionModel.Select | qt.QItemSelectionModel.Rows
        for item in csi.selectedItems:
            row = item.row()
            index = csi.model.createIndex(row, 0, item)
            csi.selectionModel.select(index, mode)

    def removeItemsView(self):
        msg = qt.QMessageBox()
        msg.setIcon(qt.QMessageBox.Question)
        nd = len(csi.selectedTopItems)
        sd = 's' if nd > 1 else ''
        res = msg.question(
            self, "Remove selected item{0} from the data tree".format(sd),
            "Do you want to remove the selected {0} item{1}?".format(nd, sd),
            qt.QMessageBox.Yes | qt.QMessageBox.No, qt.QMessageBox.Yes)
        if res == qt.QMessageBox.No:
            return

        prevRow = csi.selectedTopItems[0].row()
        prevParentItem = csi.selectedTopItems[0].parentItem
        # toRemove = csi.selectedTopItems.copy()
        csi.model.removeData(csi.selectedTopItems)

        # # to check that the removed items have gone:
        # import objgraph
        # for item in toRemove:
        #     objgraph.show_backrefs(
        #         item,
        #         filename='graph-{0}.png'.format(item.alias).replace('/', ''))

        csi.selectionModel.clear()
        if csi.model.rowCount() == 0:
            if csi.mainWindow is not None:
                csi.mainWindow.selChanged()
            if csi.DEBUG_LEVEL > 0:
                self.setWindowTitle('')
            return

        # select same row:
        try:
            prevRow = min(prevRow, len(prevParentItem.childItems)-1)
            newInd = csi.model.createIndex(
                prevRow, 0, prevParentItem.childItems[prevRow])
        except Exception:
            newInd = csi.model.createIndex(0, 0, csi.model.rootItem)
        self.setCurrentIndex(newInd)

    def copyError(self):
        for item in csi.selectedTopItems:
            if item.error is not None:
                inst = qt.QCoreApplication.instance()
                cb = inst.clipboard()
                cb.clear(mode=cb.Clipboard)
                cb.setText(item.error, mode=cb.Clipboard)
                return

    def setLines(self, column=0):
        if self.node is None:
            return
        lineDialog = LineProps(self, self.node, column)
        lineDialog.exec_()

    def _setVisibleItems(self, value, emit=True):
        if self.plotDimension == 1:
            if not csi.dataRootItem.isVisible:  # visible are those selected
                for it in csi.selectedItems:
                    csi.model.setVisible(it, value, emit)
        else:
            if value:
                it = csi.selectedItems[0]
                csi.model.setVisible(it, value, emit)
            else:
                csi.model.setVisible(csi.dataRootItem, False, True)
                for it in csi.selectedItems:
                    csi.model.setVisible(it, value, emit)

    def selChanged(self):
        if not self.hasFocus():
            return
        csi.currentNode = self.node

        selectedIndexes = csi.selectionModel.selectedRows()
        items = csi.model.getItems(selectedIndexes)
        if len(items) == 0:
            return

        if csi.selectionModel.customSelectionMode:
            self._setVisibleItems(False, False)

        csi.selectedItems[:] = []
        csi.selectedItems.extend(items)
        csi.selectedTopItems[:] = []
        csi.selectedTopItems.extend(csi.model.getTopItems(selectedIndexes))

        if csi.selectionModel.customSelectionMode:
            self._setVisibleItems(True, True)

        if csi.mainWindow is not None:
            csi.mainWindow.selChanged()

        if csi.DEBUG_LEVEL > 0 and self.parent() is None:  # only for testing
            selNames = ', '.join([i.alias for i in csi.selectedItems])
            dataCount = len(csi.allLoadedItems)
            self.setWindowTitle('{0} total; {1}'.format(dataCount, selNames))

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        mimedata = event.mimeData()
        if (mimedata.hasFormat(cco.MIME_TYPE_DATA) or
            mimedata.hasFormat(cco.MIME_TYPE_TEXT) or
                mimedata.hasFormat(cco.MIME_TYPE_HDF5)):
            event.accept()

    def dropEvent(self, event):
        csi.currentNode = self.node
        super().dropEvent(event)

    def updateProgress(self, trData):
        alias, progress = trData
        item = csi.dataRootItem.find_data_item(alias)
        if item is None:
            return
        item.progress = progress if item.beingTransformed else 1.
        ind = csi.model.indexFromItem(item)
        self.model().dataChanged.emit(ind, ind)
