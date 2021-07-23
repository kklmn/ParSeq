# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "18 Jul 2021"
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
# !!! SEE CODERULES.TXT !!!

from functools import partial
import pickle
from silx.gui import qt

from ..core import commons as cco
from ..core import singletons as csi
from . import gcommons as gco
from . import undoredo as gur
from .plotOptions import lineStyles, lineSymbols, noSymbols, LineProps

COLUMN_NAME_WIDTH = 140
COLUMN_EYE_WIDTH = 28
LEGEND_WIDTH = 48  # '|FT(χ)|' fits into 48

GROUP_BKGND = '#f4f0f0'
BAD_BKGND = '#f46060'
BUSY_BKGND = '#ffff88'
FONT_COLOR_TAG = ['black', gco.COLOR_HDF5_HEAD, gco.COLOR_FS_COLUMN_FILE,
                  'red', 'magenta', 'cyan']
LEFT_SYMBOL = u"\u25c4"  # ◄
RIGHT_SYMBOL = u"\u25ba"  # ►

DEBUG = 10


class DataTreeModel(qt.QAbstractItemModel):

    needReplot = qt.pyqtSignal()

    def __init__(self, parent=None):
        super(DataTreeModel, self).__init__(parent)
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
        # res = super(DataTreeModel, self).flags(index) |
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
#        cond = cond and item.childItems  # editable only if a group
        if cond:
            res |= qt.Qt.ItemIsEditable
        return res

    def data(self, index, role=qt.Qt.DisplayRole):
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
            if index.column() == 0:
                return item.tooltip()
        elif role == qt.Qt.BackgroundRole:
            if item.beingTransformed and index.column() == 0:
                return qt.QColor(BUSY_BKGND)
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

    def setData(self, index, value, role=qt.Qt.EditRole):
        if role == qt.Qt.EditRole:
            item = index.internalPointer()
            item.set_data(index.column(), str(value))
#            item.aliasExtra = None
            self.dataChanged.emit(index, index)
            self.needReplot.emit()
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
        topItems = [it for it in items if it in parentItem.childItems]
        bottomItems = [it for it in items if it not in parentItem.childItems]

        if len(csi.transforms.values()) > 0:
            tr = list(csi.transforms.values())[0]
            if True:  # with a threaded transform
                csi.transformer.prepare(
                    tr, dataItems=bottomItems+topItems, starter=tr.widget)
                csi.transformer.thread().start()
            else:  # in the same thread
                tr.run(dataItems=bottomItems+topItems)

        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

        mode = qt.QItemSelectionModel.Select | qt.QItemSelectionModel.Rows
        for item in items:
            row = item.row()
            index = self.createIndex(row, 0, item)
            csi.selectionModel.select(index, mode)
        return items

    def removeData(self, data):
        gur.pushDataToUndo(
            data.copy(), [it.parentItem for it in data],
            [it.row() for it in data], strChange='remove')
        self.beginResetModel()
        for item in reversed(data):
            item.delete()
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.needReplot.emit()

    def undoRemove(self, undoEntry):
        if undoEntry[-1] != 'remove':
            return
        self.beginResetModel()
        for data, parentItem, row in zip(*undoEntry[0:3]):
            if parentItem is not csi.dataRootItem and parentItem.row() is None:
                csi.dataRootItem.childItems.append(data)
                data.parentItem = csi.dataRootItem
            else:
                parentItem.childItems.insert(row, data)
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
#        return super(DataTreeModel, self).canDropMimeData(
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
                        oldParentItem.delete()
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
            if hasattr(node, 'widget'):
                items = node.widget.loadFiles(urls, parentItem, insertAt)
#            if DEBUG > 0:
#                if items is not None:
#                    for item in items:
#                        item.colorTag = 3
            return True
        else:
            return False

    def invalidateData(self):
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.needReplot.emit()


class HeaderModel(qt.QAbstractItemModel):
    def __init__(self, parent=None, node=None):
        super(HeaderModel, self).__init__(parent)
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
                return node.getProp(key, 'qLabel')
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
                role = node.getProp(key, 'role')
                if role.startswith('0'):
                    label = node.getProp(key, 'qLabel')
                    unit = node.getProp(key, 'qUnit')
                    unitStr = ' ({0})'.format(unit) if unit else ''
                    return label + unitStr
                else:
                    return "line properties"
        elif role == qt.Qt.TextAlignmentRole:
            if section > 0:
                return qt.Qt.AlignHCenter


class SelectionModel(qt.QItemSelectionModel):
    pass


class LineStyleDelegate(qt.QItemDelegate):
    def __init__(self, parent=None):
        qt.QItemDelegate.__init__(self, parent)

    def paint(self, painter, option, index):
        data = index.data(qt.Qt.DisplayRole)
        if data is None:
            return
        bknd = index.data(qt.Qt.BackgroundRole)

        rect = option.rect
        painter.save()
        painter.setRenderHint(qt.QPainter.Antialiasing, False)
        painter.setPen(qt.Qt.NoPen)
        if ((option.state & qt.QStyle.State_Selected or
             option.state & qt.QStyle.State_MouseOver) and
                bknd not in [qt.QColor(BAD_BKGND), qt.QColor(BUSY_BKGND)]):
            color = self.parent().palette().highlight().color()
            color.setAlphaF(0.1)
        else:
            color = bknd
        if color is not None:
            painter.setBrush(color)
        painter.drawRect(rect)

        if type(data) is tuple and bknd != qt.QColor(BAD_BKGND):  # plot props
            lineColor = qt.QColor(data[0])
            lineProps = data[1]
            lineWidth = (lineProps.get('linewidth', 1) + 0.5)
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
                painter.setPen(qt.QPen(qt.Qt.lightGray))
            else:
                painter.setPen(qt.QPen(qt.Qt.black))
            font = painter.font()
            # font.setFamily("Arial")
            # font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(
                option.rect, qt.Qt.AlignCenter, "{0}".format(data))

        painter.restore()


class EyeHeader(qt.QHeaderView):
    EYE_IRIS = '#87aecf'  # blue
    # EYE_IRIS = '#7B3F00'  # brown
    EYE_BROW = '#999999'
    coords1 = [(0, 0), (12, 0), (12, 12), (0, 12), 'close, 0.5']
    coords2 = [(2, 6), (5, 9), (10, 4), 'open, 1.5']

    def __init__(self, orientation=qt.Qt.Horizontal, parent=None, node=None):
        super(EyeHeader, self).__init__(orientation, parent)
        self.node = node
        self.plotDimension = 1 if node is None else self.node.plotDimension
        self.setModel(HeaderModel(node=node))

    def paintCheckBox(self, painter, rect):
        for coords in [self.coords1, self.coords2]:
            pointerPath = qt.QPainterPath()
            pointerPath.moveTo(*coords[0])
            for xy in coords[1:]:
                if isinstance(xy, tuple):
                    pointerPath.lineTo(*xy)
                if isinstance(xy, type('')):
                    end = xy.split(',')
                    if end[0] == 'close':
                        pointerPath.closeSubpath()
                    symbolPen = qt.QPen(
                        qt.Qt.black, float(end[1].strip()))
            symbolBrush = qt.QBrush(qt.Qt.white)
            painter.setPen(symbolPen)
            painter.setBrush(symbolBrush)
            pointerPath.translate(rect.x()+12, rect.y()+16)
            painter.drawPath(pointerPath)

    def paintEye(self, painter, rect):
        color = qt.QColor(self.EYE_IRIS)
        painter.setBrush(color)
        painter.setPen(color)
        radius0 = 5
        painter.drawEllipse(rect.center(), radius0, radius0)
        color = qt.QColor('black')
        painter.setBrush(color)
        painter.setPen(color)
        radius1 = 1.5
        painter.drawEllipse(rect.center(), radius1, radius1)
        painter.setPen(qt.QPen(qt.QColor(self.EYE_BROW), radius1))
        c0 = rect.center()
        x0, y0 = c0.x(), c0.y()
        ww, hh = min(2.5*radius0, rect.width()//2), radius0
        painter.drawArc(
            x0-ww+0.5, y0-radius0-1, ww*2, hh*5+1, 35*16, 110*16)
        painter.drawArc(
            x0-ww+0.5, y0+radius0, ww*2, -hh*5+3, -35*16, -110*16)

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super(EyeHeader, self).paintSection(painter, rect, logicalIndex)
        painter.restore()
        painter.setRenderHint(qt.QPainter.Antialiasing, True)
        if logicalIndex == 1:
            if csi.dataRootItem.isVisible and self.plotDimension == 1:
                # self.paintCheckBox(painter, rect)
                # rect.moveTo(rect.x(), rect.y()-6)
                # self.paintEye(painter, rect)
                rect.moveTo(rect.x(), rect.y()-15)
                self.paintEye(painter, rect)
                rect.moveTo(rect.x(), rect.y()+15)
                self.paintEye(painter, rect)
                rect.moveTo(rect.x(), rect.y()+15)
                self.paintEye(painter, rect)
            else:
                self.paintEye(painter, rect)


class DataTreeView(qt.QTreeView):

    def __init__(self, node=None, parent=None):
        super(DataTreeView, self).__init__(parent)
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
        self.setColumnWidth(0, COLUMN_NAME_WIDTH)
        self.setColumnWidth(1, COLUMN_EYE_WIDTH)
        if node is not None:
            totalWidth = 0
            leadingColumns = len(csi.modelLeadingColumns)
            for i, col in enumerate(csi.modelDataColumns):
                isHidden = col[0] is not node
                self.setColumnHidden(i+leadingColumns, isHidden)
                if isHidden:
                    continue
                fm = qt.QFontMetrics(self.font())
                role = col[0].getProp(col[1], 'role')
                if role.startswith('0'):
                    width = fm.width(col[0].getProp(col[1], 'qLabel')) + 20
                else:
                    width = LEGEND_WIDTH
                totalWidth += width
                self.setColumnWidth(i+leadingColumns, width)
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
                COLUMN_NAME_WIDTH + COLUMN_EYE_WIDTH + totalWidth, 100))

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

        self.makeActions()
        self.dataChanged()

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

        self.actionRemove = self._addAction("Remove", self.deleteItems, "Del")

        self.actionAUCC = self._addAction(
            "Auto update collective colors", self.autoUpdateColors)
        self.actionAUCC.setCheckable(True)

        self.actionLines = self._addAction(
            "Line properties", self.setLines, "Ctrl+L")

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

        menu.exec_(self.viewport().mapToGlobal(point))

    def headerClicked(self, column):
        csi.currentNode = self.node
        leadingColumns = len(csi.modelLeadingColumns)
        if column == 0:
            self.selectAll()
        elif column == 1:
            if self.plotDimension == 1:
                self.model().setVisible(
                    csi.dataRootItem, not csi.dataRootItem.isVisible, True)
            # else:
                # self.model().setVisible(csi.dataRootItem, False, True)
        else:
            node, key = csi.modelDataColumns[column-leadingColumns]
            role = node.getProp(key, 'role')
            if role.startswith('0'):
                return
            self.setLines(column - leadingColumns)

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
            self.model().dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
            self.model().needReplot.emit()

    def moveItems(self, to):
        for topItem in csi.selectedTopItems[::to]:
            self.model().moveItem(topItem, to)
        row = csi.selectedTopItems[0].row()
        newInd = self.model().createIndex(row, 0, csi.selectedTopItems[0])
        self.setCurrentIndex(newInd)

    def groupItems(self):
        if len(csi.selectedTopItems) <= 1:
            return
        group = self.model().groupItems(csi.selectedTopItems)
        row = group.row()
        newInd = self.model().createIndex(row, 0, group)
        self.setCurrentIndex(newInd)

    def ungroup(self):
        if len(csi.selectedTopItems) != 1:
            return
        if csi.selectedTopItems[0].child_count() == 0:
            return
        self.model().ungroup(csi.selectedTopItems[0])
        mode = qt.QItemSelectionModel.Select | qt.QItemSelectionModel.Rows
        for item in csi.selectedItems:
            row = item.row()
            index = self.model().createIndex(row, 0, item)
            csi.selectionModel.select(index, mode)

    def deleteItems(self):
        prevRow = csi.selectedTopItems[0].row()
        prevParentItem = csi.selectedTopItems[0].parentItem
        self.model().removeData(csi.selectedTopItems)
        csi.selectionModel.clear()
        if self.model().rowCount() == 0:
            csi.selectedItems[:] = []
            csi.selectedTopItems[:] = []
            if csi.mainWindow is not None:
                csi.mainWindow.selChanged()
            if DEBUG > 0:
                self.setWindowTitle('')
            return
        # select same row:
        try:
            prevRow = min(prevRow, len(prevParentItem.childItems)-1)
            newInd = self.model().createIndex(
                prevRow, 0, prevParentItem.childItems[prevRow])
        except Exception:
            newInd = self.model().createIndex(0, 0, self.model().rootItem)
        self.setCurrentIndex(newInd)

    def setLines(self, column=0):
        if self.node is None:
            return
        lineDialog = LineProps(self, self.node, column)
        lineDialog.exec_()

    def _setVisibleItems(self, value, emit=True):
        if self.plotDimension == 1:
            if not csi.dataRootItem.isVisible:  # visible are those selected
                for it in csi.selectedItems:
                    self.model().setVisible(it, value, emit)
        else:
            if value:
                it = csi.selectedItems[0]
                self.model().setVisible(it, value, emit)
            else:
                self.model().setVisible(csi.dataRootItem, False, True)
                for it in csi.selectedItems:
                    self.model().setVisible(it, value, emit)

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
        csi.selectedTopItems.extend(self.model().getTopItems(selectedIndexes))

        if csi.selectionModel.customSelectionMode:
            self._setVisibleItems(True, True)

        if csi.mainWindow is not None:
            csi.mainWindow.selChanged()

        if DEBUG > 0 and self.parent() is None:  # only for test purpose
            selNames = ', '.join([i.alias for i in csi.selectedItems])
            dataCount = len(csi.allLoadedItems)
            self.setWindowTitle('{0} total; {1}'.format(dataCount, selNames))

    def dragMoveEvent(self, event):
        super(DataTreeView, self).dragMoveEvent(event)
        mimedata = event.mimeData()
        if (mimedata.hasFormat(cco.MIME_TYPE_DATA) or
            mimedata.hasFormat(cco.MIME_TYPE_TEXT) or
                mimedata.hasFormat(cco.MIME_TYPE_HDF5)):
            event.accept()

    def dropEvent(self, event):
        csi.currentNode = self.node
        super(DataTreeView, self).dropEvent(event)
