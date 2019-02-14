# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from functools import partial
import pickle
from silx.gui import qt
from ..core import commons as cco
from ..core import singletons as csi
from .plotOptions import lineStyles, lineSymbols, noSymbols, LineProps

COLUMN_NAME_WIDTH = 140
COLUMN_EYE_WIDTH = 28
LEGEND_WIDTH = 48  # '|FT(χ)|' fits into 48

GROUP_BKGND = '#f4f0f0'
BAD_BKGND = '#f46060'
FONT_COLOR_TAG = ['black', 'blue', 'green', 'red', 'magenta', 'cyan']
LEFT_SYMBOL = u"\u25c4"  # ◄
RIGHT_SYMBOL = u"\u25ba"  # ►

DEBUG = 10


class DataTreeModel(qt.QAbstractItemModel):
    def __init__(self, parent=None):
        super(DataTreeModel, self).__init__(parent)
        self.rootItem = csi.dataRootItem
        csi.selectionModel = ItemSelectionModel(self)

    def rowCount(self, parent=qt.QModelIndex()):
        parentItem = parent.internalPointer() if parent.isValid() else\
            self.rootItem
        return parentItem.child_count()

    def columnCount(self, parent):
        return len(csi.modelLeadingColumns) + len(csi.modelDataColumns)

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        res = super(DataTreeModel, self).flags(index) | qt.Qt.ItemIsEnabled | \
            qt.Qt.ItemIsSelectable | \
            qt.Qt.ItemIsDragEnabled | qt.Qt.ItemIsDropEnabled
        if index.column() == 1:
            res |= qt.Qt.ItemIsUserCheckable
        cond = index.column() == 0  # editable for all items in column 0
#        item = index.internalPointer()
#        cond = cond and item.childItems  # editable only if a group
        if cond:
            res |= qt.Qt.ItemIsEditable
        return res

    def data(self, index, role=qt.Qt.DisplayRole):
        if not index.isValid():
            return None
        item = index.internalPointer()
        if role in (qt.Qt.DisplayRole, qt.Qt.EditRole):
            return item.data(index.column())
        elif role == qt.Qt.CheckStateRole:
            if index.column() == 1:
                return int(
                    qt.Qt.Checked if item.isVisible else qt.Qt.Unchecked)
        elif role == qt.Qt.ToolTipRole:
            if index.column() == 0:
                return item.tooltip()
        elif role == qt.Qt.BackgroundRole:
            if item.childItems:  # is a group
                return qt.QColor(GROUP_BKGND)
            if not item.is_good(index.column()):
                return qt.QColor(BAD_BKGND)
        elif role == qt.Qt.ForegroundRole:
            if index.column() < len(csi.modelLeadingColumns):
                return qt.QColor(FONT_COLOR_TAG[item.colorTag])
            else:
                return qt.QColor(item.color())
        elif role == qt.Qt.FontRole:
            if item.childItems and (index.column() == 0):  # group in bold
                myFont = qt.QFont()
                myFont.setBold(True)
                return myFont
        elif role == qt.Qt.TextAlignmentRole:
            if index.column() == 1:
                return qt.Qt.AlignCenter

    def headerData(self, section, orientation, role):
        if role == qt.Qt.DisplayRole:
            leadingColumns = len(csi.modelLeadingColumns)
            if section < leadingColumns:
                return csi.modelLeadingColumns[section]
            else:
                node, yName = csi.modelDataColumns[section-leadingColumns]
                if hasattr(node, "yQLabels"):
                    ind = node.yNames.index(yName)
                    yName = node.yQLabels[ind]
                return yName
        elif role == qt.Qt.ToolTipRole:
            if section == 0:
                return self.rootItem.tooltip()
            elif section == 1:
                return u"toggle visible: selected\u2194all"
            else:
                return "line properties"
#        elif role == qt.Qt.FontRole:
#            myFont = qt.QFont()
##            myFont.setBold(True)
#            return myFont
        elif role == qt.Qt.TextAlignmentRole:
            if section > 0:
                return qt.Qt.AlignHCenter

    def setData(self, index, value, role=qt.Qt.EditRole):
        if role == qt.Qt.EditRole:
            item = index.internalPointer()
            item.set_data(index.column(), str(value))
            self.dataChanged.emit(index, index)
            return True
        if role == qt.Qt.CheckStateRole:
            item = index.internalPointer()
            self.setVisible(item, value)
            return True
        return False

    def setVisible(self, item, value, emit=True):
        item.set_visible(value)
        if emit:
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
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
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        return items

    def removeData(self, data):
        self.beginResetModel()
        # !!! TODO !!! ask user about deletion of dependent (combined) data
        for item in reversed(data):
            item.delete()
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

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
                parentItem.delete()
        elif (siblings[row-to].child_count() > 0):
            insertAt = len(siblings[row-to].childItems) if to == +1 else 0
            siblings[row-to].childItems.insert(insertAt, item)
            item.parentItem = siblings[row-to]
            del siblings[row]
            if parentItem.child_count() == 0:
                parentItem.delete()
        else:
            siblings[row-to], siblings[row] = siblings[row], siblings[row-to]
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def groupItems(self, items):
        parentItem, row = items[0].parentItem, items[0].row()
        self.beginResetModel()

        # make group name:
        cs = items[0].alias
        for item in items[1:]:
            cs = cco.common_substring(cs, item.alias)
        groupName = "{0}_{1}items".format(cs, len(items)) if len(cs) > 0 else\
            "new group"
        group = parentItem.insert_item(groupName, row)
        for item in items:
            parentItem, row = item.parentItem, item.row()
            group.childItems.append(item)
            item.parentItem = group
            del parentItem.childItems[row]
            if parentItem.child_count() == 0:
                parentItem.delete()
        self.endResetModel()
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
#        return super(DataTreeModel, self).canDropMimeData(
#             data, action, row, column, parent)

    def dropMimeData(self, mimedata, action, row, column, parent):
        if mimedata.hasFormat(cco.MIME_TYPE_DATA):
            toItem = parent.internalPointer()
            if toItem.parentItem is None:
                return False
            newParentItem, newRow = toItem.parentItem, toItem.row()
            rowss = pickle.loads(mimedata.data(cco.MIME_TYPE_DATA))
            dropedItems = []
            for rows in rowss:
                parentItem = self.rootItem
                for r in reversed(rows):
                    item = parentItem.child(r)
                    parentItem = item
                dropedItems.append(item)
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
            for item in reversed(dropedItems):
                oldParentItem, oldRow = item.parentItem, item.row()
                if newParentItem is oldParentItem:
                    sibl = newParentItem.childItems
                    sibl.insert(newRow, sibl.pop(oldRow))
                else:
                    newParentItem.childItems.insert(newRow, item)
                    item.parentItem = newParentItem
                    del oldParentItem.childItems[oldRow]
                    if oldParentItem.child_count() == 0:
                        oldParentItem.delete()
            self.endResetModel()
            self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            return True
        elif mimedata.hasFormat(cco.MIME_TYPE_TEXT) or \
                mimedata.hasFormat(cco.MIME_TYPE_HDF5):
            toItem = parent.internalPointer()
            if mimedata.hasFormat(cco.MIME_TYPE_TEXT):
                urls = [url.toLocalFile() for url in reversed(mimedata.urls())]
            else:
                urls = pickle.loads(mimedata.data(cco.MIME_TYPE_HDF5))[::-1]
            if toItem.child_count() > 0:  # is a group
                parentItem, insertAt = toItem, 0
            else:
                parentItem, insertAt = toItem.parentItem, toItem.row()
            if csi.currentNodeToDrop is None:
                return False
            node = csi.currentNodeToDrop
            items = node.widget.loadFiles(urls, parentItem, insertAt)
            if DEBUG > 0:
                if items is not None:
                    for item in items:
                        item.colorTag = 3
            return True
        else:
            return False

    def invalidateData(self):
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())


class ItemSelectionModel(qt.QItemSelectionModel):
    def __init__(self, model):
        super(ItemSelectionModel, self).__init__(model)
        self.selectionChanged.connect(self.selChanged)

    def selChanged(self):
        selectedIndexes = self.selectedRows()
        items = self.model().getItems(selectedIndexes)
        if len(items) == 0:
            return
#        csi.selectedItems.clear()
#        csi.selectedTopItems.clear()
        csi.selectedItems[:] = []
        csi.selectedTopItems[:] = []
        csi.selectedItems.extend(items)
        csi.selectedTopItems.extend(self.model().getTopItems(selectedIndexes))
        if csi.mainWindow is not None:
            csi.mainWindow.selChanged()


class LineStyleDelegate(qt.QItemDelegate):
    def __init__(self, parent=None):
        qt.QItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        data = index.data(qt.Qt.DisplayRole)
        bknd = index.data(qt.Qt.BackgroundRole)
        if data is None:
            return
        rect = option.rect
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing)

        painter.setPen(qt.Qt.NoPen)
        if ((option.state & qt.QStyle.State_Selected or
             option.state & qt.QStyle.State_MouseOver) and
                bknd != qt.QColor(BAD_BKGND)):
            color = self.parent().palette().highlight().color()
            color.setAlphaF(0.1)
            painter.setBrush(color)
            painter.drawRect(rect)
        else:
            if bknd is not None:
                painter.setBrush(bknd)
                painter.drawRect(rect)

        if type(data) is int:
            painter.setPen(qt.QPen(qt.Qt.lightGray))
            if data > 0:
                font = painter.font()
                font.setFamily("Arial")
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(
                    option.rect, qt.Qt.AlignCenter, "{0}".format(data))
        elif type(data) is tuple and bknd is None:
            lineColor = qt.QColor(data[0])
            lineProps = data[1]
            lineWidth = lineProps.get('linewidth', 1) * 1.5
            lineStyle = lineStyles[lineProps.get('linestyle', '-')]

            if lineStyle == qt.Qt.NoPen:
                painter.setPen(qt.QPen(qt.Qt.lightGray))
                painter.drawText(option.rect, qt.Qt.AlignCenter, "hidden")
            else:
                axisY = lineProps.get('yaxis', -1)
                if isinstance(axisY, type("")):
                    axisY = -1 if axisY.startswith("l") else 1

#                line
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

#                 > or < symbol
                font = painter.font()
                font.setFamily("Arial")
                font.setPointSize(4 + lineWidth)
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
#                symbolFC = lineProps.get(
#                    'fc', lineProps.get('facecolor', qt.Qt.black))
#                symbolEC = lineProps.get(
#                    'ec', lineProps.get('edgecolor', qt.Qt.black))
                symbolFC = lineColor
                symbolEC = lineColor
                symbolSize = lineProps.get('symbolsize', 2) * 2
                symbolPath = qt.QPainterPath(lineSymbols[symbol])

                scale = symbolSize
                painter.scale(scale, scale)
                symbolOffset = qt.QPointF(
                    (rect.left() + rect.right() - symbolSize)*0.5 / scale,
                    (rect.top() + rect.bottom() - symbolSize)*0.5 / scale)
                symbolPath.translate(symbolOffset)
                symbolBrush = qt.QBrush(symbolFC, qt.Qt.SolidPattern)
                symbolPen = qt.QPen(symbolEC, 1./scale, qt.Qt.SolidLine)

                painter.setPen(symbolPen)
                painter.setBrush(symbolBrush)
                painter.drawPath(symbolPath)
        else:
            pass

        painter.restore()


class EyeHeader(qt.QHeaderView):
        def __init__(self, orientation=qt.Qt.Horizontal, parent=None):
            super(EyeHeader, self).__init__(orientation, parent)

        def paintSection(self, painter, rect, logicalIndex):
            painter.save()
            super(EyeHeader, self).paintSection(painter, rect, logicalIndex)
            painter.restore()
            if logicalIndex == 1:
                painter.setRenderHint(qt.QPainter.Antialiasing)
                color = qt.QColor('#87aecf')
                painter.setBrush(color)
                painter.setPen(color)
                radius0 = 4
                painter.drawEllipse(rect.center(), radius0, radius0)
                color = qt.QColor('black')
                painter.setBrush(color)
                painter.setPen(color)
                radius1 = 1.2
                painter.drawEllipse(rect.center(), radius1, radius1)
                painter.setPen(qt.QPen(qt.QColor('#999999'), 2))
                yCenter = rect.center().y()
                painter.drawArc(rect.x()+3, yCenter-radius0,
                                rect.width()-7, 3*(radius0+2),
                                35*16, 110*16)
                painter.drawArc(rect.x()+3, yCenter+radius0,
                                rect.width()-7, -3*(radius0+2),
                                -35*16, -110*16)


class DataTreeView(qt.QTreeView):
    needReplot = qt.pyqtSignal()

    def __init__(self, node=None, parent=None):
        assert csi.model is not None, "Data model must exist!"
        super(DataTreeView, self).__init__(parent)
        self.setModel(csi.model)
        self.setSelectionModel(csi.selectionModel)

        self.setHeader(EyeHeader())
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
        self.setColumnWidth(0, COLUMN_NAME_WIDTH)
        self.setColumnWidth(1, COLUMN_EYE_WIDTH)
        self.node = node
        if node is not None:
            leadingColumns = len(csi.modelLeadingColumns)
            for i, col in enumerate(csi.modelDataColumns):
                isHidden = col[0] is not node
                self.setColumnHidden(i+leadingColumns, isHidden)
                self.setColumnWidth(i+leadingColumns, LEGEND_WIDTH)
                if 'pyqt4' in qt.BINDING.lower():
                    horHeaders.setResizeMode(
                        i+leadingColumns, qt.QHeaderView.Fixed)
                else:
                    horHeaders.setSectionResizeMode(
                        i+leadingColumns, qt.QHeaderView.Fixed)
                lineStyleDelegate = LineStyleDelegate(self)
                self.setItemDelegateForColumn(
                    i+leadingColumns, lineStyleDelegate)
            self.setMinimumSize(qt.QSize(
                COLUMN_NAME_WIDTH + COLUMN_EYE_WIDTH +
                len(node.yNames)*LEGEND_WIDTH, 250))

        self.collapsed.connect(self.collapse)
        self.expanded.connect(self.expand)
#        self.setAlternatingRowColors(True)
        self.setUniformRowHeights(True)

        self.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)
        if DEBUG > 0 and self.parent() is None:  # only for test purpose
            self.selectionModel().selectionChanged.connect(self.selChanged)

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

        self.dataChanged()

    def headerClicked(self, column):
        if column == 0:
            self.selectAll()
        elif column == 1:
            self.model().setVisible(
                csi.dataRootItem, not csi.dataRootItem.isVisible)
        else:
            self.setLines(column - len(csi.modelLeadingColumns))

    def restoreExpand(self, parent=qt.QModelIndex()):
        for row in range(self.model().rowCount(parent)):
            ind = self.model().index(row, 0, parent)
            item = ind.internalPointer()
            if item.child_count() > 0:  # is a group
                self.setExpanded(ind, item.isExpanded)
                self.restoreExpand(ind)

    def collapse(self, ind):
        super(DataTreeView, self).collapse(ind)
        item = ind.internalPointer()
        item.isExpanded = False

    def expand(self, ind):
        super(DataTreeView, self).expand(ind)
        item = ind.internalPointer()
        item.isExpanded = True

    def dataChanged(self, topLeft=qt.QModelIndex(),
                    bottomRight=qt.QModelIndex(), roles=[]):
        if "qt5" in qt.BINDING.lower():
            super(DataTreeView, self).dataChanged(topLeft, bottomRight, roles)
        else:
            super(DataTreeView, self).dataChanged(topLeft, bottomRight)
        self.restoreExpand()
        csi.allLoadedItems[:] = []
        csi.allLoadedItems.extend(csi.dataRootItem.get_items())
        self.needReplot.emit()

    def onCustomContextMenu(self, point):
        menu = qt.QMenu()
        if len(csi.selectedTopItems) == 0:
            return
        #  TODO accelerators do not work
        dnd = menu.addAction("Allow internal drag-and-drop", self.allowDND)
        dnd.setCheckable(True)
        dnd.setChecked(self.isInnerDragNDropAllowed)
        menu.addAction("Move up", partial(self.moveItems, +1), "Ctrl+Up")
        menu.addAction("Move down", partial(self.moveItems, -1), "Ctrl+Down")
        menu.addSeparator()

        if len(csi.selectedTopItems) > 1:
            menu.addAction("Make group", self.groupItems, "Ctrl+G")
        elif len(csi.selectedTopItems) == 1:
            if csi.selectedTopItems[0].child_count() > 0:
                menu.addAction("Ungroup", self.ungroup, "Ctrl+U")
        menu.addSeparator()
        menu.addAction("Remove", self.deleteItems, "Del")
        menu.addSeparator()
        menu.addAction("Line properties", self.setLines, "Ctrl+L")
        menu.exec_(self.viewport().mapToGlobal(point))

    def allowDND(self):
        self.isInnerDragNDropAllowed = not self.isInnerDragNDropAllowed
        self.setDragEnabled(self.isInnerDragNDropAllowed)

    def moveItems(self, to):
        for topItem in csi.selectedTopItems[::to]:
            self.model().moveItem(topItem, to)
        row = csi.selectedTopItems[0].row()
        newInd = self.model().createIndex(row, 0, csi.selectedTopItems[0])
        self.setCurrentIndex(newInd)

    def groupItems(self):
        group = self.model().groupItems(csi.selectedTopItems)
        row = group.row()
        newInd = self.model().createIndex(row, 0, group)
        self.setCurrentIndex(newInd)

    def ungroup(self):
        self.model().ungroup(csi.selectedTopItems[0])
        mode = qt.QItemSelectionModel.Select | qt.QItemSelectionModel.Rows
        for item in csi.selectedItems:
            row = item.row()
            index = self.model().createIndex(row, 0, item)
            self.selectionModel().select(index, mode)

    def deleteItems(self):
        prevRow = csi.selectedTopItems[0].row()
        prevParentItem = csi.selectedTopItems[0].parentItem
        self.model().removeData(csi.selectedTopItems)
        self.selectionModel().clear()
        if self.model().rowCount() == 0:
            csi.selectedItems[:] = []
            csi.selectedTopItems[:] = []
            if DEBUG > 0:
                self.setWindowTitle('')
            return
        # select same row:
        try:
            prevRow = min(prevRow, len(prevParentItem.childItems)-1)
            newInd = self.model().createIndex(
                prevRow, 0, prevParentItem.childItems[prevRow])
        except:  # analysis:ignore
            newInd = self.model().createIndex(0, 0, self.model().rootItem)
        self.setCurrentIndex(newInd)

    def setLines(self, column=0):
        lineDialog = LineProps(self, self.node, column)
        if (lineDialog.exec_()):
            pass

    def selChanged(self):
        if DEBUG > 0 and self.parent() is None:  # only for test purpose
            selNames = ', '.join([i.alias for i in csi.selectedItems])
            dataCount = len(csi.allLoadedItems)
            self.setWindowTitle('{0} total; {1}'.format(dataCount, selNames))

    def dropEvent(self, event):
        csi.currentNodeToDrop = self.node
        super(DataTreeView, self).dropEvent(event)
