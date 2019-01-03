# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "01 Jan 2019"
# !!! SEE CODERULES.TXT !!!
from silx.gui import qt
import silx.io as silx_io
from silx.gui.hdf5.Hdf5TreeModel import Hdf5TreeModel
from silx.gui.hdf5.NexusSortFilterProxyModel import NexusSortFilterProxyModel

NODE_FS, NODE_HDF5, NODE_HDF5_HEAD = range(3)

if True:
    ModelBase = qt.QFileSystemModel
else:  # for test purpose
    ModelBase = qt.QAbstractItemModel

useProxyModel = True  # only for decoration, sorting doesn't work so far

HDF5_GROUP_PARENT_COLOR = '#22A7F0'
HDF5_DATASET_PARENT_COLOR = '#22A7F0'


class MyHdf5TreeModel(Hdf5TreeModel):
    TYPE_COLUMN = 2
    SHAPE_COLUMN = 1

    def findIndex(self, hdf5Obj):
        return self.index(self.h5pyObjectRow(hdf5Obj.obj), 0)


class FileSystemWithHdf5Model(ModelBase):
    resetRootPath = qt.pyqtSignal(qt.QModelIndex)
    requestSaveExpand = qt.pyqtSignal()
    requestRestoreExpand = qt.pyqtSignal()

    def __init__(self, parent=None):
        super(FileSystemWithHdf5Model, self).__init__(parent)
        if ModelBase == qt.QFileSystemModel:
            self.fsModel = self
        elif ModelBase == qt.QAbstractItemModel:
            self.fsModel = qt.QFileSystemModel(self)
        self.h5Model = MyHdf5TreeModel(self)
        if useProxyModel:
            self.h5ProxyModel = NexusSortFilterProxyModel(self)
            self.h5ProxyModel.setSourceModel(self.h5Model)
            self.h5ProxyModel.getNxIcon = \
                self.h5ProxyModel._NexusSortFilterProxyModel__getNxIcon
        self.h5Model.setFileMoveEnabled(False)
        # this won't handle renames, deletes, and moves:
        self.hdf5buddies = {}
        self.nodesFS = []
        self.nodesH5 = []
        self.nodesHeads = []
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

    def mapToH5(self, index, pointer=None):
        return self._mapIndex(index, self, self.h5Model)

    def setRootPath(self, dirname):
        self._roothPath = dirname
        if self.fsModel is self:
            return super(FileSystemWithHdf5Model, self).setRootPath(dirname)
        return self.mapFromFS(self.fsModel.setRootPath(dirname))

    def nodeType(self, index):
        if index == qt.QModelIndex():
            return NODE_FS
        id0 = index.internalId()
        if id0 in self.nodesFS:
            return NODE_FS
        elif id0 in self.nodesH5:
            return NODE_HDF5
        elif id0 in self.nodesHeads:
            return NODE_HDF5_HEAD
        else:
            return NODE_FS

    def mapFStoH5(self, indexFS):
        fileInfo = self.fsModel.fileInfo(indexFS)
        if fileInfo.filePath() in self.hdf5buddies:
            hdf5Obj = self.hdf5buddies[fileInfo.filePath()]['hdf5Obj']
#            return self.h5Model.indexFromH5Object(hdf5Obj) # does't work
            return self.h5Model.findIndex(hdf5Obj)
        else:
            return qt.QModelIndex()

    def mapH5toFS(self, indexH5):
        hdf5Obj = self.h5Model.nodeFromIndex(indexH5)
        if hasattr(hdf5Obj, 'headInfo'):
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).index(
                    hdf5Obj.headInfo['FilePath'])
            return self.fsModel.index(hdf5Obj.headInfo['FilePath'])
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

    def data(self, index, role=qt.Qt.DisplayRole):
        if not index.isValid():
            return None
        nodeType = self.nodeType(index)
        if nodeType == NODE_FS:
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).data(index, role)
            return self.fsModel.data(self.mapToFS(index), role)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)
            if useProxyModel:
                return self.h5ProxyModel.data(
                    self.h5ProxyModel.mapFromSource(indexH5), role)
            else:
                return self.h5Model.data(indexH5, role)
        elif nodeType == NODE_HDF5_HEAD:
            fileInfo = self.fsModel.fileInfo(self.mapToFS(index))
            buddy = self.hdf5buddies[fileInfo.filePath()]
            if role == qt.Qt.ToolTipRole:
                return buddy['tooltip']
            elif role == qt.Qt.ForegroundRole:
                return buddy['color']
            elif role == qt.Qt.DecorationRole:
                if useProxyModel and \
                        index.column() == self.h5Model.NAME_COLUMN:
                    indexH5 = self.mapFStoH5(self.mapToFS(index))
                    ic = super(FileSystemWithHdf5Model, self).data(index, role)
                    return self.h5ProxyModel.getNxIcon(ic)
            if self.fsModel is self:
                return super(FileSystemWithHdf5Model, self).data(index, role)
            return self.fsModel.data(self.mapToFS(index), role)
        else:
            return

    def parent(self, index):
        if not index.isValid():
            return qt.QModelIndex()
        nodeType = self.nodeType(index)
        if nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)
            parentH5 = self.h5Model.parent(indexH5)
            hdf5Obj = self.h5Model.nodeFromIndex(parentH5)
            if hasattr(hdf5Obj, 'headInfo'):
                parent = self.mapFromFS(self.mapH5toFS(parentH5))
            else:
                parent = self.mapFromH5(parentH5)
            return parent
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
            if False:  # useProxyModel:
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
        index = self.mapFromFS(indexFS)
        if fileInfo.filePath() not in self.hdf5buddies:
            try:
                with silx_io.open(fileInfo.filePath()) as h5f:
                    if not silx_io.is_file(h5f):
                        raise IOError()
                    gs = [silx_io.is_group(it) for it in h5f.values()]
                    groupsN = gs.count(True)
                    out = ''
                    if groupsN > 0:
                        out = '{0} group{1}'.format(
                            groupsN, 's' if groupsN > 1 else '')
                    else:
                        ds = [silx_io.is_dataset(it) for it in
                              h5f.values()]
                        datasN = ds.count(True)
                        if datasN > 0:
                            out = '{0} dataset{1}'.format(
                                datasN, 's' if datasN > 1 else '')
                    color = 'black'
                    if groupsN > 0:
                        color = HDF5_GROUP_PARENT_COLOR
                    elif datasN > 0:
                        color = HDF5_DATASET_PARENT_COLOR

                    self.beginInsertRows(parent, row, row)
                    self.h5Model.appendFile(fileInfo.filePath())
                    self.endInsertRows()

#                    hdf5Obj = self.h5Model.index(-1,0).internalPointer()
                    root = self.h5Model.nodeFromIndex(qt.QModelIndex())
                    hdf5Obj = root.child(-1)
                    buddy = dict(
                        tooltip=out, color=qt.QColor(color), hdf5Obj=hdf5Obj,
                        FilePath=fileInfo.filePath())
                    self.hdf5buddies[fileInfo.filePath()] = buddy
                    hdf5Obj.headInfo = buddy
#                    print(fileInfo.filePath())
                    if index.internalId() not in self.nodesHeads:
                        self.nodesHeads.append(index.internalId())
                    self.layoutChanged.emit()
            except IOError:
                if index.internalId() not in self.nodesFS:
                    self.nodesFS.append(index.internalId())

        return index

    def indexFileName(self, fName):
        if self.fsModel is self:
            return super(FileSystemWithHdf5Model, self).index(fName)
        else:
            return self.fsModel.index(fName)


class FileTreeView(qt.QTreeView):
    def __init__(self, parent=None, roothPath=None):
        super(FileTreeView, self).__init__(parent)
        model = FileSystemWithHdf5Model(self)
#        model = qt.QFileSystemModel(self)  # for test purpose
        self.setModel(model)
        if isinstance(model, FileSystemWithHdf5Model):
            model.resetRootPath.connect(self._resetRootPath)
            model.requestSaveExpand.connect(self.saveExpand)
            model.requestRestoreExpand.connect(self.restoreExpand)
        else:
            model.indexFileName = model.index
        if roothPath is not None:
            rootIndex = model.setRootPath(roothPath)
            self.setRootIndex(rootIndex)

    def _resetRootPath(self, rtIndex):
        self.setRootIndex(rtIndex)

    def saveExpand(self, parent=qt.QModelIndex()):
        if parent == qt.QModelIndex():
            self._expandedNodes = []
        for row in range(self.model().rowCount(parent)):
            ind = self.model().index(row, 0, parent)
            if self.model().rowCount(ind) > 0:
                if self.isExpanded(ind):
                    self._expandedNodes.append(ind.data())
                self.saveExpand(ind)

    def restoreExpand(self, parent=qt.QModelIndex()):
        if parent == qt.QModelIndex():
            if len(self._expandedNodes) == 0:
                return
        for row in range(self.model().rowCount(parent)):
            ind = self.model().index(row, 0, parent)
            if self.model().rowCount(ind) > 0:
                if ind.data() in self._expandedNodes:
                    self.setExpanded(ind, True)
                self.restoreExpand(ind)
