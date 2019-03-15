# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "01 Jan 2019"
# !!! SEE CODERULES.TXT !!!
import os
import re
from functools import partial
import pickle
import numpy as np
import silx
from distutils.version import LooseVersion, StrictVersion
assert LooseVersion(silx.version) >= LooseVersion("0.9.0")
from silx.gui import qt
import silx.io as silx_io
from silx.gui.hdf5.Hdf5TreeModel import Hdf5TreeModel
from silx.gui.hdf5.NexusSortFilterProxyModel import NexusSortFilterProxyModel

from ..core import commons as cco
from . import gcommons as gco

if True:
    ModelBase = qt.QFileSystemModel
else:  # for test purpose
    ModelBase = qt.QAbstractItemModel
useProxyModel = True  # only for decoration, sorting doesn't work so far

NODE_FS, NODE_HDF5, NODE_HDF5_HEAD = range(3)
LOAD_DATASET_ROLE = Hdf5TreeModel.USER_ROLE
USE_HDF5_ARRAY_ROLE = Hdf5TreeModel.USER_ROLE + 1
H5PY_OBJECT_ROLE = Hdf5TreeModel.H5PY_OBJECT_ROLE
LOAD_CANNOT, LOAD_CAN, LOAD_NA = range(3)

COLUMN_NAME_WIDTH = 240
NODE_INDENTATION = 12


def is_text_file(file_name):
    try:
        with open(file_name, 'r') as check_file:  # try open file in text mode
            check_file.read()
            return True
    except:  # if fail then file is non-text (binary)
        return False


class MyHdf5TreeModel(Hdf5TreeModel):
    TYPE_COLUMN = 2
    SHAPE_COLUMN = 1

    def findIndex(self, hdf5Obj):
        return self.index(self.h5pyObjectRow(hdf5Obj.obj), 0)

    def hdf5ObjFromFileName(self, filename):
        root = self.nodeFromIndex(qt.QModelIndex())
        for ic in range(root.childCount()):
            c = root.child(ic)
            if c.obj is None:
                continue
            else:
                if c.obj.file.filename == filename:
                    return c

    def indexFromPath(self, parent, path):
        if path.startswith('/'):
            pathList = path[1:].split('/')
        else:
            pathList = path.split('/')
        return self._indexFromPathList(parent, pathList)

    def _indexFromPathList(self, parent, pathList):
        for row in range(self.rowCount(parent)):
            ind = self.index(row, 0, parent)
            name = self.nodeFromIndex(ind).obj.name
            if name.split('/')[-1] == pathList[0]:
                if len(pathList) == 1:
                    return ind
                return self._indexFromPathList(ind, pathList[1:])
        else:
            return qt.QModelIndex()


class FileSystemWithHdf5Model(ModelBase):
    resetRootPath = qt.pyqtSignal(qt.QModelIndex)
    requestSaveExpand = qt.pyqtSignal()
    requestRestoreExpand = qt.pyqtSignal()

    def __init__(self, transformNode=None, parent=None):
        super(FileSystemWithHdf5Model, self).__init__(parent)
        self.transformNode = transformNode
        if ModelBase == qt.QFileSystemModel:
            self.fsModel = self
        elif ModelBase == qt.QAbstractItemModel:
            self.fsModel = qt.QFileSystemModel(self)
        self.h5Model = MyHdf5TreeModel(self)
        self.h5ModelRoot = self.h5Model.nodeFromIndex(qt.QModelIndex())
        if useProxyModel:
            self.h5ProxyModel = NexusSortFilterProxyModel(self)
            self.h5ProxyModel.setSourceModel(self.h5Model)
            self.h5ProxyModel.getNxIcon = \
                self.h5ProxyModel._NexusSortFilterProxyModel__getNxIcon
        self.h5Model.setFileMoveEnabled(False)
        # this won't handle renames, deletes, and moves:
        self.nodesH5 = []
        self.nodesHead = []
        self.nodesNoHead = []
        self._roothPath = None
        self.layoutAboutToBeChanged.connect(self._resetModel)
        self.layoutChanged.connect(self._restoreExpand)

    def _resetModel(self):
        """Without reset it crashes if hdf5 nodes are expanded."""
        self.requestSaveExpand.emit()
        self.beginResetModel()
        self.endResetModel()
        if self._roothPath is not None:
            rtIndex = self.setRootPath(self._roothPath)
            self.resetRootPath.emit(rtIndex)

    def _restoreExpand(self):
        self.requestRestoreExpand.emit()

    def headerData(self, section, orientation, role):
        if section == 3:
            return "Date Modified / HDF5 Value"
        if self.fsModel is self:
            return super(FileSystemWithHdf5Model, self).headerData(
                section, orientation, role)
        return self.fsModel.headerData(section, orientation, role)

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        res = super(FileSystemWithHdf5Model, self).flags(index) | \
            qt.Qt.ItemIsEnabled | qt.Qt.ItemIsSelectable | \
            qt.Qt.ItemIsDragEnabled
        return res

    def _mapIndex(self, indexFrom, modelFrom, modelTo):
        if modelFrom is modelTo:
            return indexFrom
        if not indexFrom.isValid():
            return qt.QModelIndex()
        assert indexFrom.model() is modelFrom
        pntr = indexFrom.internalPointer()
        return modelTo.createIndex(indexFrom.row(), indexFrom.column(), pntr)

    def mapFromFS(self, indexFS):
        return self._mapIndex(indexFS, self.fsModel, self)

    def mapFromH5(self, indexH5):
        return self._mapIndex(indexH5, self.h5Model, self)

    def mapToFS(self, index):
        return self._mapIndex(index, self, self.fsModel)

    def mapToH5(self, index):
        return self._mapIndex(index, self, self.h5Model)

    def setRootPath(self, dirname):
        self._roothPath = dirname
        if self.fsModel is self:
            return super(FileSystemWithHdf5Model, self).setRootPath(dirname)
        return self.mapFromFS(self.fsModel.setRootPath(dirname))

    def nodeType(self, index):
        if not index.isValid():
            return NODE_FS
        id0 = index.internalId()
        if id0 in self.nodesH5:
            return NODE_HDF5
        elif id0 in self.nodesHead:
            return NODE_HDF5_HEAD
        else:
            return NODE_FS

    def mapFStoH5(self, indexFS):
        index = self.mapFromFS(indexFS)
        if index.internalId() in self.nodesHead:
            fileInfo = self.fsModel.fileInfo(indexFS)
            filename = fileInfo.filePath()
            hdf5Obj = self.h5Model.hdf5ObjFromFileName(filename)
            if hdf5Obj is not None:
                return self.h5Model.findIndex(hdf5Obj)
        return qt.QModelIndex()

    def mapH5toFS(self, indexH5):
        parentH5 = self.h5Model.parent(indexH5)
        if not parentH5.isValid():
            hdf5Obj = self.h5Model.nodeFromIndex(indexH5)
            return self.indexFileName(hdf5Obj.obj.file.filename)
        else:
            return qt.QModelIndex()

    def rowCount(self, parent=qt.QModelIndex()):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_HDF5:
            return self.h5Model.rowCount(self.mapToH5(parent))
        elif nodeType == NODE_FS:
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).rowCount(parent)
            return self.fsModel.rowCount(self.mapToFS(parent))
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.rowCount(self.mapFStoH5(self.mapToFS(parent)))
        else:
            raise ValueError('unknown node type in `rowCount`')

    def columnCount(self, parent=qt.QModelIndex()):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_HDF5:
            return self.h5Model.columnCount(self.mapToH5(parent))
        elif nodeType == NODE_FS:
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).columnCount(parent)
            return self.fsModel.columnCount(self.mapToFS(parent))
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.columnCount(
                self.mapFStoH5(self.mapToFS(parent)))
        else:
            raise ValueError('unknown node type in `columnCount`')

    def hasChildren(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).hasChildren(parent)
            return self.fsModel.hasChildren(self.mapToFS(parent))
        return self.rowCount(parent) > 0

    def canLoadColDataset(self, indexFS):
        return True

    def canInterpretArrayFormula(self, colStr, treeObj):
        keys = re.findall(r'\[(.*?)\]', colStr)
        if len(keys) == 0:
            keys = colStr,
            colStr = 'd["{0}"]'.format(colStr)
        else:
            # remove outer quotes:
            keys = [k[1:-1] if k.startswith(('"', "'")) else k for k in keys]
        d = {}
        if hasattr(treeObj, 'isGroupObj'):  # is Hdf5Item
            for k in keys:
                if not self.hasChildPath(treeObj, k):
                    return False
                d[k] = np.ones(2)
        else:  # arrays from column file
            for k in keys:
                kl = k.lower()
                if "col" in kl:
                    kn = int(kl[kl.find('col')+3])
                else:
                    kn = int(k)
                d[k] = treeObj[kn]
                d[kn] = d[k]
                locals()[k] = k
        try:
            eval(colStr)
            return True
        except:
            return False

    def hasChildPath(self, node, path):
        nodeNames = path.split('/')
        for ichild in range(node.childCount()):
            child = node.child(ichild)
            if child.dataName(qt.Qt.DisplayRole) == nodeNames[0]:
                if len(nodeNames) > 1:
                    return self.hasChildPath(child, '/'.join(nodeNames[1:]))
                else:
                    return True
        return False

    def stateLoadColDataset(self, indexFS):
        if not indexFS.isValid():
            return LOAD_CANNOT
        cf = self.transformNode.widget.columnFormat
        df = cf.getDataFormat()
        if not df:
            return LOAD_CANNOT
        fileInfo = self.fsModel.fileInfo(indexFS)
        fname = fileInfo.filePath()
        try:
            cco.get_header(fname, df)
            df['skip_header'] = df.pop('skiprows', 0)
            df.pop('dataSource', None)
            with np.warnings.catch_warnings():
                np.warnings.simplefilter("ignore")
                arrs = np.genfromtxt(fname, unpack=True, max_rows=2, **df)
            if len(arrs) == 0:
                return LOAD_CANNOT

            txt = cf.dataXEdit.text()
            if len(txt) == 0:
                return LOAD_CANNOT
            if not self.canInterpretArrayFormula(txt, arrs):
                return LOAD_CANNOT
            for yEdit in cf.dataYEdits:
                txt = yEdit.text()
                if len(txt) == 0:
                    return LOAD_CANNOT
                if not self.canInterpretArrayFormula(txt, arrs):
                    return LOAD_CANNOT
            return LOAD_CAN
        except:
            return LOAD_CANNOT

    def stateLoadHDF5Dataset(self, indexH5):
        if not indexH5.isValid():
            return LOAD_NA
        nodeH5 = self.h5Model.nodeFromIndex(indexH5)
        if not nodeH5.isGroupObj():
            return LOAD_NA
        cf = self.transformNode.widget.columnFormat

        txt = cf.dataXEdit.text()
        if len(txt) == 0:
            return LOAD_CANNOT
        if not self.canInterpretArrayFormula(txt, nodeH5):
            return LOAD_CANNOT

        for yEdit in cf.dataYEdits:
            txt = yEdit.text()
            if len(txt) == 0:
                return LOAD_CANNOT
            if not self.canInterpretArrayFormula(txt, nodeH5):
                return LOAD_CANNOT
        return LOAD_CAN

    def stateLoadDataset(self, index):
        if not index.isValid():
            return LOAD_NA
        nodeType = self.nodeType(index)
        if nodeType == NODE_FS:
            indexFS = self.mapToFS(index)
            fileInfo = self.fsModel.fileInfo(indexFS)
            if not is_text_file(fileInfo.filePath()):
                return LOAD_NA
            return self.stateLoadColDataset(indexFS)
        if nodeType == NODE_HDF5_HEAD:
            indexFS = self.mapToFS(index)
            indexH5 = self.mapFStoH5(indexFS)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)
        return self.stateLoadHDF5Dataset(indexH5)

    def getHDF5ArrayPath(self, index):
        if not index.isValid():
            return
        nodeType = self.nodeType(index)
        if nodeType not in (NODE_HDF5_HEAD, NODE_HDF5):
            return
        if nodeType == NODE_HDF5_HEAD:
            indexFS = self.mapToFS(index)
            indexH5 = self.mapFStoH5(indexFS)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)

        if not indexH5.isValid():
            return
        class_ = self.h5Model.nodeFromIndex(indexH5).h5Class
        if class_ == silx_io.utils.H5Type.DATASET:
            obj = self.h5Model.nodeFromIndex(indexH5).obj
            try:
                if (len(obj.shape) == 1) and (obj.shape[0] > 1):
                    return obj.name
            except:
                pass
        return

    def getHDF5FullPath(self, index):
        if not index.isValid():
            return
        nodeType = self.nodeType(index)
        if nodeType not in (NODE_HDF5_HEAD, NODE_HDF5):
            return
        if nodeType == NODE_HDF5_HEAD:
            indexFS = self.mapToFS(index)
            indexH5 = self.mapFStoH5(indexFS)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)

        return 'silx:' + '::'.join(
            (self.h5Model.nodeFromIndex(indexH5).obj.file.filename,
             self.h5Model.nodeFromIndex(indexH5).obj.name))

    def data(self, index, role=qt.Qt.DisplayRole):
        if not index.isValid():
            return
        nodeType = self.nodeType(index)
        if role == LOAD_DATASET_ROLE:
            return self.stateLoadDataset(index)
        if role == USE_HDF5_ARRAY_ROLE:
            return self.getHDF5ArrayPath(index)
        if nodeType == NODE_FS:
            indexFS = self.mapToFS(index)
            if role == qt.Qt.ForegroundRole:
                fileInfo = self.fsModel.fileInfo(indexFS)
                if is_text_file(fileInfo.filePath()):
                    return qt.QColor(gco.COLOR_FS_COLUMN_FILE)
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).data(index, role)
            return self.fsModel.data(indexFS, role)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)
            if useProxyModel:
                return self.h5ProxyModel.data(
                    self.h5ProxyModel.mapFromSource(indexH5), role)
            else:
                return self.h5Model.data(indexH5, role)
        elif nodeType == NODE_HDF5_HEAD:
            indexFS = self.mapToFS(index)
            fileInfo = self.fsModel.fileInfo(indexFS)
            if role == qt.Qt.ToolTipRole:
                indexH5 = self.mapFStoH5(indexFS)
                return self.h5Model.data(indexH5, role)
            elif role == qt.Qt.ForegroundRole:
                return qt.QColor(gco.COLOR_HDF5_HEAD)
            elif role == qt.Qt.DecorationRole:
                if useProxyModel and \
                        index.column() == self.h5Model.NAME_COLUMN:
                    ic = super(FileSystemWithHdf5Model, self).data(index, role)
                    return self.h5ProxyModel.getNxIcon(ic)
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).data(index, role)
            return self.fsModel.data(indexFS, role)
        else:
            return

    def parent(self, index):
        if not index.isValid():
            return qt.QModelIndex()
        nodeType = self.nodeType(index)
        if nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)
            parentH5 = self.h5Model.parent(indexH5)
            if not parentH5.isValid():
                return qt.QModelIndex()
            grandparentH5 = self.h5Model.parent(parentH5)
            if not grandparentH5.isValid():
                hdf5Obj = self.h5Model.nodeFromIndex(parentH5)
                return self.indexFileName(hdf5Obj.obj.file.filename)
            return self.mapFromH5(parentH5)
        else:
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).parent(index)
            pind = self.mapFromFS(self.fsModel.parent(self.mapToFS(index)))
            return pind

    def index(self, row, column, parent=qt.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return qt.QModelIndex()
        parentType = self.nodeType(parent)
        if parentType in (NODE_HDF5, NODE_HDF5_HEAD):
            if False:  # useProxyModel: !!! doesn't help in sorting !!!
                if parentType == NODE_HDF5:
                    parentProxyH5 = self.h5ProxyModel.mapFromSource(
                        self.mapToH5(parent))
                elif parentType == NODE_HDF5_HEAD:
                    parentProxyH5 = self.h5ProxyModel.mapFromSource(
                        self.mapFStoH5(self.mapToFS(parent)))
                indexProxyH5 = self.h5ProxyModel.index(
                        row, column, parentProxyH5)
                index = self.mapFromH5(
                    self.h5ProxyModel.mapToSource(indexProxyH5))
            else:
                if parentType == NODE_HDF5:
                    parentH5 = self.mapToH5(parent)
                elif parentType == NODE_HDF5_HEAD:
                    parentH5 = self.mapFStoH5(self.mapToFS(parent))
                indexH5 = self.h5Model.index(row, column, parentH5)
                index = self.mapFromH5(indexH5)

            if index.internalId() not in self.nodesH5:
                self.nodesH5.append(index.internalId())
            return index

        if self.fsModel is self:
            indexFS = super(FileSystemWithHdf5Model, self).index(
                row, column, parent)
        else:
            indexFS = self.fsModel.index(row, column, self.mapToFS(parent))
        fileInfo = self.fsModel.fileInfo(indexFS)
        filename = fileInfo.filePath()
        index = self.mapFromFS(indexFS)
        if (index.internalId() not in self.nodesHead and
                index.internalId() not in self.nodesNoHead):
            try:
                if os.path.splitext(filename)[1] not in \
                        silx_io.utils.NEXUS_HDF5_EXT:
                    # = [".h5", ".nx5", ".nxs",  ".hdf", ".hdf5", ".cxi"]
                    raise IOError()
                with silx_io.open(filename) as h5f:
                    if not silx_io.is_file(h5f):
                        raise IOError()
                    self.beginInsertRows(parent, row, row)
#                    self.h5Model.appendFile(filename)
                    self.h5Model.insertFileAsync(filename)
                    self.endInsertRows()
                    self.nodesHead.append(index.internalId())
                    self.layoutChanged.emit()
            except IOError:
                self.nodesNoHead.append(index.internalId())
        return index

    def synchronizeHdf5Index(self, index):
        h5pyObject = self.data(index, role=H5PY_OBJECT_ROLE)
        if isinstance(h5pyObject, type('')):
            filename = h5pyObject
        else:
            filename = h5pyObject.file.filename
        indexFS = self.indexFileName(filename)
        indexH5 = self.mapFStoH5(indexFS)
        indexHead = self.mapFromFS(indexFS)

        h5py_object = self.h5Model.data(indexH5, role=H5PY_OBJECT_ROLE)
#        if not h5py_object.ntype is h5py.File:
#            return

        self.beginResetModel()
        self.h5Model.beginResetModel()
#        self.nodesHead.remove(indexHead.internalId())
        self.h5Model.removeH5pyObject(h5py_object)
        self.h5Model.insertFile(filename, indexH5.row())
        self.h5Model.endResetModel()
        self.endResetModel()
        return indexHead

    def indexFileName(self, fName):
        if self.fsModel is self:
            return super(FileSystemWithHdf5Model, self).index(fName)
        else:
            return self.fsModel.index(fName)

    def indexFromH5Path(self, path):
        fNameStart = path.find("silx:")
        if fNameStart < 0:
            return qt.QModelIndex()
        fNameEnd = path.find("::/")
        if fNameEnd < 0:
            return qt.QModelIndex()
        fnameH5 = path[fNameStart+5:fNameEnd]
        fnameH5sub = path[fNameEnd+3:]

        headIndexFS = self.indexFileName(fnameH5)
        headIndexH5 = self.mapFStoH5(headIndexFS)
        indexH5 = self.h5Model.indexFromPath(headIndexH5, fnameH5sub)
        return self.mapFromH5(indexH5)

    def mimeData(self, indexes):
        indexes0 = [index for index in indexes if index.column() == 0]
        nodeTypes = [self.nodeType(index) for index in indexes0]
        if nodeTypes.count(nodeTypes[0]) != len(nodeTypes):  # not all equal
            return
        if nodeTypes[0] in (NODE_HDF5_HEAD, NODE_FS):
            indexesFS = []
            for index in indexes0:
                indexFS = self.mapToFS(index)
                if self.stateLoadColDataset(indexFS) != LOAD_CAN:
                    return
                indexesFS.append(indexFS)
            if ModelBase == qt.QFileSystemModel:
                return super(FileSystemWithHdf5Model, self).mimeData(indexesFS)
            else:
                return self.fsModel.mimeData(indexesFS)
        elif nodeTypes[0] == NODE_HDF5:
            paths = []
            for index in indexes0:
                indexH5 = self.mapToH5(index)
                if self.stateLoadHDF5Dataset(indexH5) != LOAD_CAN:
                    return
                try:
                    path = 'silx:' + '::'.join(
                        (self.h5Model.nodeFromIndex(indexH5).obj.file.filename,
                         self.h5Model.nodeFromIndex(indexH5).obj.name))
                    paths.append(path)
                except:  # noqa
                    return
            mimedata = qt.QMimeData()
            mimedata.setData(cco.MIME_TYPE_HDF5, pickle.dumps(paths))
            return mimedata


class SelectionDelegate(qt.QItemDelegate):
    def __init__(self, parent=None):
        qt.QItemDelegate.__init__(self, parent)
        self.pen2Width = 3

    def paint(self, painter, option, index):
        loadState = index.data(LOAD_DATASET_ROLE)
        if option.state & qt.QStyle.State_MouseOver:
            color = self.parent().palette().highlight().color()
            if loadState == LOAD_CAN:
                color = qt.QColor(gco.COLOR_LOAD_CAN)
            elif loadState == LOAD_CANNOT:
                color = qt.QColor(gco.COLOR_LOAD_CANNOT)
            color.setAlphaF(0.2)
            painter.fillRect(option.rect, color)

        painter.save()
        color = None
        active = (option.state & qt.QStyle.State_Selected or
                  option.state & qt.QStyle.State_MouseOver)
        if active:
            if loadState == LOAD_CAN:
                color = qt.QColor(gco.COLOR_LOAD_CAN)
            elif loadState == LOAD_CANNOT:
                color = qt.QColor(gco.COLOR_LOAD_CANNOT)
        if color is not None:
            color.setAlphaF(0.2)
            option.palette.setColor(qt.QPalette.Highlight, color)
        super(SelectionDelegate, self).paint(painter, option, index)
        path = index.data(USE_HDF5_ARRAY_ROLE)
        if path is not None and active:
            pen = qt.QPen(qt.QColor(gco.COLOR_LOAD_CAN))
            pen.setWidth(self.pen2Width)
            painter.setPen(pen)
            painter.drawRect(option.rect.x() + self.pen2Width//2,
                             option.rect.y() + self.pen2Width//2,
                             option.rect.width() - self.pen2Width,
                             option.rect.height() - self.pen2Width)
        painter.restore()


class FileTreeView(qt.QTreeView):
    def __init__(self, transformNode=None, parent=None, roothPath=None):
        super(FileTreeView, self).__init__(parent)
        model = FileSystemWithHdf5Model(transformNode, self)
#        model = qt.QFileSystemModel(self)  # for test purpose
        self.setModel(model)
        if isinstance(model, FileSystemWithHdf5Model):
            model.resetRootPath.connect(self._resetRootPath)
            model.requestSaveExpand.connect(self.saveExpand)
            model.requestRestoreExpand.connect(self.restoreExpand)
        else:
            model.indexFileName = model.index
        self.transformNode = transformNode
        if transformNode is not None:
            self.setItemDelegateForColumn(0, SelectionDelegate(self))
            self.parent().setMouseTracking(True)

        if roothPath is None:
            roothPath = ''
        rootIndex = model.setRootPath(roothPath)
        self.setRootIndex(rootIndex)

        self.setMinimumSize(qt.QSize(COLUMN_NAME_WIDTH, 250))
        self.setColumnWidth(0, COLUMN_NAME_WIDTH)
        self.setIndentation(NODE_INDENTATION)
        self.setSortingEnabled(True)
        self.sortByColumn(0, qt.Qt.AscendingOrder)
        self.setSelectionMode(qt.QAbstractItemView.ExtendedSelection)

        self.setDragEnabled(True)
        self.setDragDropMode(qt.QAbstractItemView.DragOnly)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(True)

        self.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenu)
        self.selectionModel().selectionChanged.connect(self.selChanged)

        if transformNode is not None:
            strLoad = "Load data (you can also drag it to the data tree)"
            self.actionLoad = self._addAction(
                strLoad, self.transformNode.widget.loadFiles, "Ctrl+O")
        self.actionSynchronize = self._addAction(
            "Synchronize container", self.synchronizeHDF5, "Ctrl+R")
#        self.testModel = self._addAction("Test Model", self.testModel)

    def _addAction(self, text, slot, shortcut=None):
        action = qt.QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(qt.QKeySequence(shortcut))
        action.setShortcutContext(qt.Qt.WidgetWithChildrenShortcut)
        self.addAction(action)
        return action

    def _resetRootPath(self, rtIndex):
        self.setRootIndex(rtIndex)

    def onCustomContextMenu(self, point):
        if self.transformNode is None:
            return
        selectedIndexes = self.selectionModel().selectedRows()
        lenSelectedIndexes = len(selectedIndexes)
        if lenSelectedIndexes == 0:
            return
        menu = qt.QMenu()

        if lenSelectedIndexes >= 1:
            paths = []
            for index in selectedIndexes:
                path = index.data(USE_HDF5_ARRAY_ROLE)
                if path is not None:
                    paths.append(path)
                else:
                    paths = []
                    break

            if len(paths) == 1:
                strSum = ''
            else:
                strSum = 'the sum '

            if len(paths) > 0:
                try:
                    xLbl = self.transformNode.xQLabel
                except AttributeError:
                    xLbl = self.transformNode.xName
                menu.addAction("Set {0}as {1} array".format(strSum, xLbl),
                               partial(self.setAsArray, 0, paths))

                try:
                    yLbls = self.transformNode.yQLabels
                except AttributeError:
                    yLbls = self.transformNode.yNames
                for iLbl, yLbl in enumerate(yLbls):
                    menu.addAction("Set {0}as {1} array".format(strSum, yLbl),
                                   partial(self.setAsArray, iLbl+1, paths))
                menu.addSeparator()

        isEnabled = False
        for index in selectedIndexes:
            if not index.data(LOAD_DATASET_ROLE) == LOAD_CAN:
                break
        else:
            isEnabled = True

        menu.addAction(self.actionLoad)
        self.actionLoad.setEnabled(isEnabled)
        if lenSelectedIndexes > 1:
            actionN = menu.addAction(
                "Concatenate {0} datasets and load as one".format(
                    lenSelectedIndexes))
            actionN.setEnabled(isEnabled)

        menu.addSeparator()
        nodeType0 = self.model().nodeType(selectedIndexes[0])
        menu.addAction(self.actionSynchronize)
        self.actionSynchronize.setEnabled(
            nodeType0 in (NODE_HDF5_HEAD, NODE_HDF5))

#        menu.addSeparator()
#        menu.addAction(self.testModel)

        menu.exec_(
            self.transformNode.widget.files.viewport().mapToGlobal(point))

#    def testModel(self):
#        self.ModelTest(self.model(), self)

    def synchronizeHDF5(self):
        selectedIndexes = self.selectionModel().selectedRows()
        ind = selectedIndexes[0]
        row = ind.row()
        nodeType0 = self.model().nodeType(ind)
        if nodeType0 not in (NODE_HDF5_HEAD, NODE_HDF5):
            return
        indexHead = self.model().synchronizeHdf5Index(ind)
        self.setCurrentIndex(indexHead)
        self.setExpanded(indexHead, True)
        self.scrollTo(self.model().index(row, 0, indexHead))

    def saveExpand(self, parent=qt.QModelIndex()):
        if not parent.isValid():
            self._expandedNodes = []
        for row in range(self.model().rowCount(parent)):
            ind = self.model().index(row, 0, parent)
            if self.model().rowCount(ind) > 0:
                if self.isExpanded(ind):
                    self._expandedNodes.append(ind.data())
                self.saveExpand(ind)

    def restoreExpand(self, parent=qt.QModelIndex()):
        if not parent.isValid():
            if len(self._expandedNodes) == 0:
                return
        try:
            for row in range(self.model().rowCount(parent)):
                ind = self.model().index(row, 0, parent)
                if self.model().rowCount(ind) > 0:
                    if ind.data() in self._expandedNodes:
                        self.setExpanded(ind, True)
                    self.restoreExpand(ind)
        except:
            pass

    def selChanged(self, selected, deselected):
        # self.updateForSelectedFiles(selected.indexes()) #  × num of columns
        selectedIndexes = self.selectionModel().selectedRows()
        self.updateForSelectedFiles(selectedIndexes)

    def updateForSelectedFiles(self, indexes):
        if self.transformNode is None:
            return
        cf = self.transformNode.widget.columnFormat
        for index in indexes:
            nodeType = self.model().nodeType(index)
            if nodeType == NODE_FS:
                indexFS = self.model().mapToFS(index)
                fileInfo = self.model().fsModel.fileInfo(indexFS)
                if is_text_file(fileInfo.filePath()):
                    cf.setHeaderEnabled(True)
                else:
                    cf.setHeaderEnabled(False)
                    return
            else:
                cf.setHeaderEnabled(False)
                return

    def setAsArray(self, iArray, paths):
        subpaths = []
        for path in paths:
            slashC = path.count('/')
            if slashC == 1:
                subpath = path[1:]  # without leading "/"
            elif slashC > 1:
                pos2 = path.find('/', path.find('/')+1)  # 2nd occurrence
                subpath = path[pos2+1:]  # without leading "/"
            else:
                return
            subpaths.append(subpath)

        cf = self.transformNode.widget.columnFormat
        if iArray == 0:
            edit = cf.dataXEdit
        else:
            edit = cf.dataYEdits[iArray-1]

        if len(subpaths) == 1:
            txt = subpaths[0]
        elif len(subpaths) > 1:
            txt = ' + '.join(['d["{0}"]'.format(sp) for sp in subpaths])
        else:
            return
        edit.setText(txt)

    def startDrag(self, supportedActions):
        listsQModelIndex = self.selectedIndexes()
        if listsQModelIndex:
            mimeData = self.model().mimeData(listsQModelIndex)
            if mimeData is None:
                return
            dragQDrag = qt.QDrag(self)
            dragQDrag.setMimeData(mimeData)
            defaultDropAction = qt.Qt.IgnoreAction
            dragQDrag.exec_(supportedActions, defaultDropAction)
