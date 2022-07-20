# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "19 Jul 2022"
u"""
The `files and containers` model is a file system model (qt.QFileSystemModel)
extended by the hdf5 model from silx (silx.gui.hdf5.Hdf5TreeModel), so that
hdf5 containers can be viewed in the same tree.

"""
# !!! SEE CODERULES.TXT !!!

import os
import os.path as osp
import re
from functools import partial
import pickle
import time
import numpy as np

import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"

import silx
from distutils.version import LooseVersion  # , StrictVersion
assert LooseVersion(silx.version) >= LooseVersion("0.9.0")
from silx.gui import qt
import silx.io as silx_io
from silx.gui.hdf5.Hdf5TreeModel import Hdf5TreeModel
from silx.gui.hdf5.NexusSortFilterProxyModel import NexusSortFilterProxyModel

from ..core import commons as cco
from ..core import singletons as csi
from ..core.config import configLoad
from . import gcommons as gco

useProxyFileModel = False  # presently QIdentityProxyModel, does nothing
useProxyH5Model = True  # for decoration and sorting

NODE_FS, NODE_HDF5, NODE_HDF5_HEAD = range(3)
LOAD_DATASET_ROLE = Hdf5TreeModel.USER_ROLE
USE_HDF5_ARRAY_ROLE = Hdf5TreeModel.USER_ROLE + 1
LOAD_ITEM_PATH_ROLE = Hdf5TreeModel.USER_ROLE + 2
H5PY_OBJECT_ROLE = Hdf5TreeModel.H5PY_OBJECT_ROLE

COLUMN_NAME_WIDTH = 300
NODE_INDENTATION = 12


def is_text_file(file_name):
    try:
        with open(file_name, 'r') as check_file:  # try open file in text mode
            check_file.read()
            return True
    except:  # if fails then file is non-text (binary)  # noqa
        return False


class MyHdf5TreeModel(Hdf5TreeModel):
    TYPE_COLUMN = 2
    SHAPE_COLUMN = 1

    def __init__(self, parent):
        super().__init__(parent)
        self.setFileMoveEnabled(False)
        # this won't handle renames, deletes, and moves:
        self.nodesH5 = []

    def rowCount(self, parent=qt.QModelIndex()):
        node = self.nodeFromIndex(parent)
        if node is None:
            return 0
        if node._Hdf5Node__child is None:
            return 0
        return node.childCount()

    def hasChildren(self, parent=qt.QModelIndex()):
        node = self.nodeFromIndex(parent)
        try:  # may fail during loading
            return node.isGroupObj()
        except Exception:
            return False

    def canFetchMore(self, parent):
        node = self.nodeFromIndex(parent)
        if node is None:
            return False
        try:
            if not node.isGroupObj():
                return False
            if node._Hdf5Node__child is None:
                return True
        except AttributeError:
            return False
        return True

    def fetchMore(self, parent):
        node = self.nodeFromIndex(parent)
        if node is None:
            return
        try:
            super().fetchMore(parent)
            for row in range(node.childCount()):
                node.child(row)
                ind = self.index(row, 0, parent)
                intId = ind.internalId()
                if intId not in self.nodesH5:
                    self.nodesH5.append(intId)
        except RuntimeError:
            pass

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
        parentNode = self.nodeFromIndex(parent)
        self.fetchMore(parent)
        for row in range(parentNode.childCount()):
            ind = self.index(row, 0, parent)
            node = self.nodeFromIndex(ind)
            if node.dataLink(qt.Qt.DisplayRole) == 'External':
                path = self.getHDF5NodePath(node)
            else:
                path = node.obj.name
            if path.split('/')[-1] == pathList[0]:
                if len(pathList) == 1:
                    return ind
                return self._indexFromPathList(ind, pathList[1:])
        else:
            return qt.QModelIndex()


class MySortFilterProxyModel(qt.QIdentityProxyModel):
    pass
    # def index(self, row, column, parent=qt.QModelIndex()):
    #     smodel = self.sourceModel()
    #     sparent = self.mapToSource(parent)
    #     res = smodel.index(row, column, sparent)
    #     parentType = smodel.nodeType(sparent)
    #     if parentType in (NODE_HDF5, NODE_HDF5_HEAD):
    #         return self.mapFromSource(res)

    #     fileInfo = smodel.fileInfo(res)
    #     baseName = fileInfo.baseName()
    #     if baseName.startswith('eiger'):
    #         return qt.QModelIndex()
    #     return self.mapFromSource(res)


class FileSystemWithHdf5Model(qt.QFileSystemModel):
    resetRootPath = qt.pyqtSignal(qt.QModelIndex)
    requestSaveExpand = qt.pyqtSignal()
    requestRestoreExpand = qt.pyqtSignal()
    pathReady = qt.pyqtSignal(str)

    def __init__(self, transformNode=None, parent=None):
        super().__init__(parent)
        self.transformNode = transformNode
        self.h5Model = MyHdf5TreeModel(self)
        if useProxyH5Model:
            self.h5ProxyModel = NexusSortFilterProxyModel(self)
            self.h5ProxyModel.setSourceModel(self.h5Model)
            self.h5ProxyModel.getNxIcon = \
                self.h5ProxyModel._NexusSortFilterProxyModel__getNxIcon
        self.folders = []
        self.nodesHead = []
        self.nodesNoHead = []
        self.pendingPath = None
        self._rootPath = None
        # self.layoutAboutToBeChanged.connect(self.resetModel)
        self.layoutChanged.connect(self.onLayoutChanged)
        self.directoryLoaded.connect(self.onDirectoryLoaded)
        # self.setOption(qt.QFileSystemModel.DontUseCustomDirectoryIcons)
        self.setFilter(qt.QDir.AllEntries | qt.QDir.NoDotAndDotDot)
        self.setNameFilterDisables(False)

    def resetModel(self):
        # self.requestSaveExpand.emit()
        self.beginResetModel()
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    def onLayoutChanged(self):
        self.requestRestoreExpand.emit()

    def headerData(self, section, orientation, role):
        if section == 3:
            return "Date Modified / HDF5 Value"
        return super().headerData(section, orientation, role)

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        res = super().flags(index) | qt.Qt.ItemIsEnabled | \
            qt.Qt.ItemIsSelectable | qt.Qt.ItemIsDragEnabled
        return res

    def _mapIndex(self, indexFrom, modelFrom, modelTo):
        # if modelFrom is modelTo:
        #     return indexFrom
        if not indexFrom.isValid():
            return qt.QModelIndex()
        assert indexFrom.model() is modelFrom
        pntr = indexFrom.internalPointer()
        return modelTo.createIndex(indexFrom.row(), indexFrom.column(), pntr)

    def mapFromH5(self, indexH5):
        return self._mapIndex(indexH5, self.h5Model, self)

    def mapToH5(self, index):
        return self._mapIndex(index, self, self.h5Model)

    def setRootPath(self, dirname):
        self._rootPath = dirname
        return super().setRootPath(dirname)

    def nodeType(self, index):
        if not index.isValid():
            return NODE_FS
        id0 = index.internalId()
        if id0 in self.h5Model.nodesH5:
            return NODE_HDF5
        elif id0 in self.nodesHead:
            return NODE_HDF5_HEAD
        else:
            return NODE_FS

    def mapFStoH5(self, indexFS):  # only for h5 heads
        if indexFS.internalId() in self.nodesHead:
            fileInfo = self.fileInfo(indexFS)
            filename = fileInfo.filePath()
            hdf5Obj = self.h5Model.hdf5ObjFromFileName(filename)
            if hdf5Obj is not None:
                return self.h5Model.findIndex(hdf5Obj)
        return qt.QModelIndex()

    def mapH5toFS(self, indexH5):  # only for h5 heads
        parentH5 = self.h5Model.parent(indexH5)
        if not parentH5.isValid():
            hdf5Obj = self.h5Model.nodeFromIndex(indexH5)
            return self.indexFileName(hdf5Obj.obj.file.filename)
        else:
            return qt.QModelIndex()

    def rowCount(self, parent=qt.QModelIndex()):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().rowCount(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.rowCount(self.mapFStoH5(parent))
        elif nodeType == NODE_HDF5:
            return self.h5Model.rowCount(self.mapToH5(parent))
        else:
            raise ValueError('unknown node type in `rowCount`')

    def columnCount(self, parent=qt.QModelIndex()):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().columnCount(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.columnCount(self.mapFStoH5(parent))
        elif nodeType == NODE_HDF5:
            return self.h5Model.columnCount(self.mapToH5(parent))
        else:
            raise ValueError('unknown node type in `columnCount`')

    def hasChildren(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().hasChildren(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return True
        elif nodeType == NODE_HDF5:
            return self.h5Model.hasChildren(self.mapToH5(parent))
        else:
            raise ValueError('unknown node type in `hasChildren`')

    def canFetchMore(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().canFetchMore(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.canFetchMore(self.mapFStoH5(parent))
        elif nodeType == NODE_HDF5:
            return self.h5Model.canFetchMore(self.mapToH5(parent))
        else:
            raise ValueError('unknown node type in `canFetchMore`')

    def onDirectoryLoaded(self, path):
        """fetch Hdf5's"""
        path = osp.abspath(path).replace('\\', '/')
        # on Windows, paths sometimes start with a capital C:, sometimes with
        # a small c:, which breaks the inclusion checking, that's why lower():
        self.folders.append(path.lower())
        parent = self.indexFileName(path)
        # t0 = time.time()
        # print('loading', path, self.rowCount(parent))
        countHdf5 = 0
        for row in range(self.rowCount(parent)):
            indexFS = self.index(row, 0, parent)
            if not indexFS.isValid():
                continue
            fileInfo = self.fileInfo(indexFS)
            fname = fileInfo.filePath()
            intId = indexFS.internalId()
            ext = '.' + fileInfo.suffix()
            if (intId not in self.nodesHead and intId not in self.nodesNoHead):
                if ext in silx_io.utils.NEXUS_HDF5_EXT:
                    # = [".h5", ".nx5", ".nxs",  ".hdf", ".hdf5", ".cxi"]
                    try:
                        self.nodesHead.append(intId)
                        self.beginInsertRows(parent, row, row)
                        self.h5Model.appendFile(fname)  # slower, not always
                        # don't use, it breaks the model:
                        # self.h5Model.insertFileAsync(fname)  # faster?
                        self.endInsertRows()
                        countHdf5 += 1
                    except IOError as e:
                        print(e)
                        self.nodesNoHead.append(intId)
                else:
                    self.nodesNoHead.append(intId)
        if countHdf5 > 0:
            self.layoutChanged.emit()
        # print("loaded {0} htf5's in {1} s".format(countHdf5, time.time()-t0))

        if self.pendingPath:
            if self.pendingPath[0] == path:
                self.pathReady.emit(self.pendingPath[1])

    def fetchMore(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            super().fetchMore(parent)
        elif nodeType == NODE_HDF5_HEAD:
            self.h5Model.fetchMore(self.mapFStoH5(parent))
        elif nodeType == NODE_HDF5:
            self.h5Model.fetchMore(self.mapToH5(parent))
        else:
            raise ValueError('unknown node type in `fetchMore`')

    def canLoadColDataset(self, indexFS):
        return True

    def interpretArrayFormula(self, dataStr, treeObj, kind):
        """Returnes a list of (expr, d[xx]-styled-expr, data-keys, shape).
        *dataStr* may have several expressions with the syntax of a list or a
        tuple or just one expression if it is a simple string.
        """
        try:
            # to expand list comprehension or string expressions
            dataStr = str(eval(dataStr))
        except:  # noqa
            pass

        if ((dataStr.startswith('[') and dataStr.endswith(']')) or
                (dataStr.startswith('(') and dataStr.endswith(')'))):
            dataStr = dataStr[1:-1]
        dataStr = [s.strip() for s in dataStr.split(',')]
        out = []
        for colStr in dataStr:
            keys = re.findall(r'\[(.*?)\]', colStr)
            if len(keys) == 0:
                keys = [colStr]
                colStrD = 'd[r"{0}"]'.format(colStr)
            else:
                colStrD = colStr
                # remove outer quotes:
                keys = [k[1:-1] if k.startswith(('"', "'")) else k
                        for k in keys]
            d = {}
            if kind == 'h5':
                for k in keys:
                    if k.startswith("silx:"):
                        tryInd = self.indexFromH5Path(k)
                        if tryInd == qt.QModelIndex():  # doesn't exist
                            return
                        shape = self.h5Model.nodeFromIndex(tryInd).obj.shape
                    else:
                        shape = self.hasH5ChildPath(treeObj, k)
                    if shape is None:
                        return
                    d[k] = np.ones([2 for dim in shape])
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
                shape = 2,
            try:
                eval(colStrD)
                out.append((colStr, colStrD, keys, shape))
            except:  # noqa
                return
        return out

    def hasH5ChildPath(self, node, path):
        if node.dataLink(qt.Qt.DisplayRole) == 'External':
            nodePath = self.getHDF5NodePath(node)
        else:
            nodePath = node.obj.name
        pathInH5 = '/'.join((nodePath, path))
        try:
            test = node.obj[pathInH5]  # test for existence
            return test.shape
        except KeyError:
            return

    def tryLoadColDataset(self, indexFS):
        if not indexFS.isValid() or not self.transformNode:
            return
        cf = self.transformNode.widget.columnFormat
        df = cf.getDataFormat(needHeader=True)
        if not df:
            return
        fileInfo = self.fileInfo(indexFS)
        fname = fileInfo.filePath()
        lres = []
        try:
            cdf = df.copy()
            cco.get_header(fname, cdf)
            cdf['skip_header'] = cdf.pop('skiprows', 0)
            dataS = cdf.pop('dataSource', [])
            cdf.pop('conversionFactors', [])
            with np.warnings.catch_warnings():
                np.warnings.simplefilter("ignore")
                arrs = np.genfromtxt(fname, unpack=True, max_rows=2, **cdf)
            if len(arrs) == 0:
                return

            for data in dataS:
                if len(data) == 0:
                    return
                colEval = self.interpretArrayFormula(data, arrs, 'col')
                if colEval is None:
                    return
                lres.append(colEval)
        except Exception:  # as e:
            # print('tryLoadColDataset:', e)
            return
        return lres, df

    def tryLoadHDF5Dataset(self, indexH5):
        if not indexH5.isValid() or not self.transformNode:
            return
        nodeH5 = self.h5Model.nodeFromIndex(indexH5)
        try:
            if not nodeH5.isGroupObj():
                return
        except Exception:
            return

        cf = self.transformNode.widget.columnFormat
        df = cf.getDataFormat(needHeader=False)
        if not df:
            return

        lres = []
        try:
            datas = df.get('dataSource', [])  # from dataEdits
            slices = df.get('slices', ['' for ds in datas])  # from sliceEdits
            for idata, (data, slc, nd) in enumerate(zip(
                    datas, slices, self.transformNode.getPropList('ndim'))):
                if len(data) == 0:
                    return
                colEval = self.interpretArrayFormula(data, nodeH5, 'h5')
                if colEval is None:
                    return
                if nd:
                    if len(colEval[0][3]) < nd:
                        return
                    elif len(colEval[0][3]) == nd:
                        pass
                    elif len(colEval[0][3]) > nd:
                        if 'axis' in slc or 'sum' in slc:  # sum axes
                            sumlist = slc[slc.find('=')+1:].split(',')
                            if len(colEval[0][3]) - len(sumlist) != nd:
                                return
                        else:
                            slicelist = [i for i in slc.split(',') if ':' in i]
                            if len(slicelist) != nd:
                                return
                lres.append(colEval)
        except Exception:
            return
        return lres, df

    def tryLoadDataset(self, index):
        if not index.isValid():
            return
        nodeType = self.nodeType(index)
        if nodeType == NODE_FS:
            fileInfo = self.fileInfo(index)
            if not is_text_file(fileInfo.filePath()):
                return
            return self.tryLoadColDataset(index)
        elif nodeType == NODE_HDF5_HEAD:
            indexH5 = self.mapFStoH5(index)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)
        return self.tryLoadHDF5Dataset(indexH5)

    def getHDF5ArrayPathAndShape(self, index):
        nodeType = self.nodeType(index)
        if nodeType not in (NODE_HDF5_HEAD, NODE_HDF5):
            return None, None
        if nodeType == NODE_HDF5_HEAD:
            indexH5 = self.mapFStoH5(index)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)

        if not indexH5.isValid():
            return None, None
        node = self.h5Model.nodeFromIndex(indexH5)
        class_ = node.h5Class
        if class_ == silx_io.utils.H5Type.DATASET:
            if node.dataLink(qt.Qt.DisplayRole) == 'External':
                nodePath = self.getHDF5NodePath(node)
            else:
                nodePath = node.obj.name
            try:
                shape = node.obj.shape
                if len(shape) >= 1:
                    return nodePath, shape
                else:
                    return nodePath, None
            except:  # noqa
                return nodePath, None
        return None, None

    def getHDF5NodePath(self, node):
        if node.parent is None or not hasattr(node.parent, 'basename'):
            return ''
        else:
            return '/'.join((self.getHDF5NodePath(node.parent), node.basename))

    def getHDF5FullPath(self, index):
        nodeType = self.nodeType(index)
        if nodeType not in (NODE_HDF5_HEAD, NODE_HDF5):
            return
        if nodeType == NODE_HDF5_HEAD:
            indexH5 = self.mapFStoH5(index)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)

        node = self.h5Model.nodeFromIndex(indexH5)
        if node.dataLink(qt.Qt.DisplayRole) == 'External':
            nodePath = self.getHDF5NodePath(node)
        else:
            nodePath = node.obj.name
        return 'silx:' + '::'.join((node.obj.file.filename, nodePath))

    def data(self, index, role=qt.Qt.DisplayRole):
        shouldSkip = False
        if csi.currentNode is not None:
            if csi.currentNode.widget.onTransform:
                shouldSkip = True
        if shouldSkip and role in [LOAD_DATASET_ROLE, USE_HDF5_ARRAY_ROLE,
                                   LOAD_ITEM_PATH_ROLE, qt.Qt.ToolTipRole]:
            return

        if not index.isValid():
            return
        if role == LOAD_DATASET_ROLE:
            return self.tryLoadDataset(index)
        if role == USE_HDF5_ARRAY_ROLE:
            return self.getHDF5ArrayPathAndShape(index)

        nodeType = self.nodeType(index)
        if nodeType == NODE_FS:
            if role == LOAD_ITEM_PATH_ROLE:
                return self.filePath(index)
            elif role == qt.Qt.ForegroundRole:
                fileInfo = self.fileInfo(index)
                if is_text_file(fileInfo.filePath()):
                    return qt.QColor(gco.COLOR_FS_COLUMN_FILE)
            elif role == qt.Qt.ToolTipRole:
                count = self.rowCount(index)
                if count:
                    return '{0} items in this folder'.format(count)
                else:
                    return
            else:
                return super().data(index, role)
        elif nodeType == NODE_HDF5:
            if role == LOAD_ITEM_PATH_ROLE:
                return self.getHDF5FullPath(index)
            indexH5 = self.mapToH5(index)
            res = self.h5Model.data(indexH5, role)
            if useProxyH5Model:
                if role == qt.Qt.ToolTipRole:
                    if res is None:
                        return
                    node = self.h5Model.nodeFromIndex(indexH5)
                    if node.dataLink(qt.Qt.DisplayRole) == 'External':
                        path = node.obj.name
                        truePath = self.getHDF5NodePath(node)
                        res = res.replace(path, truePath)
                        res = res.replace(' Dataset', ' External Dataset')
                    return res
                else:
                    return self.h5ProxyModel.data(
                        self.h5ProxyModel.mapFromSource(indexH5), role)
            else:
                return res
        elif nodeType == NODE_HDF5_HEAD:
            if role == qt.Qt.ToolTipRole:
                indexH5 = self.mapFStoH5(index)
                return self.h5Model.data(indexH5, role)
            elif role == qt.Qt.ForegroundRole:
                return qt.QColor(gco.COLOR_HDF5_HEAD)
            elif role == qt.Qt.DecorationRole:
                if useProxyH5Model and \
                        index.column() == self.h5Model.NAME_COLUMN:
                    ic = super().data(index, role)
                    return self.h5ProxyModel.getNxIcon(ic)
            return super().data(index, role)
        else:
            raise ValueError('unknown node type in `data`')

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
            return super().parent(index)

    def index(self, row, column, parent=qt.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return qt.QModelIndex()
        parentType = self.nodeType(parent)
        if parentType in (NODE_HDF5, NODE_HDF5_HEAD):
            # if useProxyH5Model:
            if False:  # no need to go through h5ProxyModel
                if parentType == NODE_HDF5:
                    parentProxyH5 = self.h5ProxyModel.mapFromSource(
                        self.mapToH5(parent))
                elif parentType == NODE_HDF5_HEAD:
                    parentProxyH5 = self.h5ProxyModel.mapFromSource(
                        self.mapFStoH5(parent))
                indexH5 = self.h5ProxyModel.index(row, column, parentProxyH5)
                index = self.mapFromH5(self.h5ProxyModel.mapToSource(indexH5))
            else:
                if parentType == NODE_HDF5:
                    parentH5 = self.mapToH5(parent)
                elif parentType == NODE_HDF5_HEAD:
                    parentH5 = self.mapFStoH5(parent)
                indexH5 = self.h5Model.index(row, column, parentH5)
                index = self.mapFromH5(indexH5)

            intId = indexH5.internalId()
            if intId not in self.h5Model.nodesH5:
                self.h5Model.nodesH5.append(intId)
            return index

        indexFS = super().index(row, column, parent)
        if hasattr(self.transformNode, 'excludeFilters'):
            fileInfo = self.fileInfo(indexFS)
            fileName = fileInfo.fileName()
            for filt in self.transformNode.excludeFilters:
                if re.search(filt.replace('*', '+'), fileName):
                    return qt.QModelIndex()
        return indexFS

    def synchronizeHdf5Index(self, index):
        h5pyObject = self.data(index, role=H5PY_OBJECT_ROLE)
        if isinstance(h5pyObject, type('')):
            filename = h5pyObject
        else:
            filename = h5pyObject.file.filename
        indexFS = self.indexFileName(filename)
        indexH5 = self.mapFStoH5(indexFS)

        h5py_object = self.h5Model.data(indexH5, role=H5PY_OBJECT_ROLE)
#        if not h5py_object.ntype is h5py.File:
#            return

        self.beginResetModel()
        self.h5Model.beginResetModel()
#        self.nodesHead.remove(indexFS.internalId())
        self.h5Model.removeH5pyObject(h5py_object)
        self.h5Model.insertFile(filename, indexH5.row())
        self.h5Model.endResetModel()
        self.endResetModel()
        return indexFS

    def indexFileName(self, fName):
        return super().index(fName)

    def indexFromH5Path(self, path, fallbackToHead=False):
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
        if headIndexH5 == qt.QModelIndex():
            if self.canFetchMore(headIndexFS):
                self.fetchMore(headIndexFS)
            headIndexH5 = self.mapFStoH5(headIndexFS)
            return headIndexFS if fallbackToHead else qt.QModelIndex()
        indexH5 = self.h5Model.indexFromPath(headIndexH5, fnameH5sub)
        return self.mapFromH5(indexH5)

    def mimeData(self, indexes, checkValidity=True):
        indexes0 = [index for index in indexes if index.column() == 0]
        nodeTypes = [self.nodeType(index) for index in indexes0]
        if nodeTypes.count(nodeTypes[0]) != len(nodeTypes):  # not all equal
            return
        if nodeTypes[0] in (NODE_HDF5_HEAD, NODE_FS):
            indexesFS = []
            for index in indexes0:
                if checkValidity:
                    if self.tryLoadColDataset(index) is None:
                        return
                indexesFS.append(index)
            return super().mimeData(indexesFS)
        elif nodeTypes[0] == NODE_HDF5:
            paths = []
            for index in indexes0:
                indexH5 = self.mapToH5(index)
                if checkValidity:
                    if self.tryLoadHDF5Dataset(indexH5) is None:
                        return
                try:
                    node = self.h5Model.nodeFromIndex(indexH5)
                    if node.dataLink(qt.Qt.DisplayRole) == 'External':
                        npath = self.getHDF5NodePath(node)
                    else:
                        npath = node.obj.name
                    path = 'silx:' + '::'.join((node.obj.file.filename, npath))
                    paths.append(path)
                except Exception:
                    return
            mimedata = qt.QMimeData()
            mimedata.setData(cco.MIME_TYPE_HDF5, pickle.dumps(paths))
            return mimedata


class SelectionDelegate(qt.QItemDelegate):
    def __init__(self, parent=None):
        qt.QItemDelegate.__init__(self, parent)
        self.pen2Width = 3

    def paint(self, painter, option, index):
        if csi.currentNode is not None:
            node = csi.currentNode
            if node.widget.onTransform:
                super().paint(painter, option, index)
                return

        path = index.data(LOAD_ITEM_PATH_ROLE)
        if path and self.parent().transformNode:
            if self.parent().comparePathWithLastLoaded(path):
                option.font.setWeight(qt.QFont.Bold)
            # if self.parent().comparePathWithLastLoaded(path, suffix='_silx'):
            #     option.font.setWeight(qt.QFont.Bold)

        active = (option.state & qt.QStyle.State_Selected or
                  option.state & qt.QStyle.State_MouseOver)
        if active:
            loadState = index.data(LOAD_DATASET_ROLE)

        if option.state & qt.QStyle.State_MouseOver:
            # color = self.parent().palette().highlight().color()
            if loadState is not None:
                color = qt.QColor(gco.COLOR_LOAD_CAN)
            else:
                color = qt.QColor(gco.COLOR_LOAD_CANNOT)
            color.setAlphaF(0.2)
            painter.fillRect(option.rect, color)

        painter.save()
        if active:
            if loadState is not None:
                color = qt.QColor(gco.COLOR_LOAD_CAN)
            else:
                color = qt.QColor(gco.COLOR_LOAD_CANNOT)
            color.setAlphaF(0.2)
            option.palette.setColor(qt.QPalette.Highlight, color)
        super().paint(painter, option, index)

        res = index.data(USE_HDF5_ARRAY_ROLE)  # returns (path, shape)
        if res[1] is not None and active:
            pen = qt.QPen(qt.QColor(gco.COLOR_LOAD_CAN))
            pen.setWidth(self.pen2Width)
            painter.setPen(pen)
            painter.drawRect(option.rect.x() + self.pen2Width//2,
                             option.rect.y() + self.pen2Width//2,
                             option.rect.width() - self.pen2Width,
                             option.rect.height() - self.pen2Width)
        painter.restore()


class FileTreeView(qt.QTreeView):
    def __init__(self, transformNode=None, parent=None, rootPath=''):
        super().__init__(parent)
        self.rootPath = rootPath
        self.transformNode = transformNode

        self.initModel()

        if transformNode is not None:
            self.setItemDelegateForColumn(0, SelectionDelegate(self))
            if parent is not None:
                self.parent().setMouseTracking(True)

        self.setMinimumSize(
            qt.QSize(int(COLUMN_NAME_WIDTH*csi.screenFactor), 250))
        self.setColumnWidth(0, int(COLUMN_NAME_WIDTH*csi.screenFactor))
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
        self.expanded.connect(self.expandFurther)
        self.prevSelectedIndexes = []

        if transformNode is not None:
            strLoad = "Load data (you can also drag it to the data tree)"
            self.actionLoad = self._addAction(
                strLoad, self.transformNode.widget.loadFiles, "Ctrl+L")
        self.actionSynchronize = self._addAction(
            "Synchronize container", self.synchronizeHDF5, "Ctrl+R")
        self.actionViewTextFile = self._addAction(
            "View text file (will be diplayed in 'metadata' panel)",
            self.viewTextFile, "F3")

        # uncomment for testing the file model:
        from ..tests.modeltest import ModelTest
        self.ModelTest = ModelTest
        self.actionTestModel = self._addAction(
            "Test file model", self.testModel)

    def initModel(self):
        model = FileSystemWithHdf5Model(self.transformNode, self)
        rootIndex = model.setRootPath(self.rootPath)
        # model = qt.QFileSystemModel(self)  # only for test purpose
        if isinstance(model, FileSystemWithHdf5Model):
            model.resetRootPath.connect(self._resetRootPath)
            model.requestSaveExpand.connect(self.saveExpand)
            model.requestRestoreExpand.connect(self.restoreExpand)
            model.pathReady.connect(self._gotoIsReady)
        else:
            model.indexFileName = model.index

        if useProxyFileModel:
            proxyModel = MySortFilterProxyModel(self)
            proxyModel.setSourceModel(model)
            # proxyModel.setDynamicSortFilter(False)
            self.setModel(proxyModel)
            rootIndex = self.model().mapFromSource(rootIndex)
        else:
            self.setModel(model)

        if self.transformNode is not None:
            if hasattr(self.transformNode, 'includeFilters'):
                model.setNameFilters(self.transformNode.includeFilters)

        self.setRootIndex(rootIndex)
        self._expandedNodes = []

    def gotoLastData(self):
        if configLoad.has_option('Data', self.transformNode.name):
            path = configLoad.get('Data', self.transformNode.name)
        else:
            path = ''
        if path:
            if path.startswith('silx:') or ('::' in path):
                start = 5 if path.startswith('silx:') else 0
                end = path.find('::') if '::' in path else None
                head = path[start:end]
            else:
                head = path
            dirname = osp.dirname(osp.abspath(head)).replace('\\', '/')
            if dirname:
                os.chdir(dirname)
            self.gotoWhenReady(path)

    def getSourceModel(self, index=None):
        if useProxyFileModel:
            model = self.model().sourceModel()
            if index:
                if isinstance(index, (list, tuple)):
                    ind = self.model().mapSelectionToSource(index)
                else:
                    ind = self.model().mapToSource(index)
        else:
            model = self.model()
            if index:
                ind = index
        return (model, ind) if index else model

    def getProxyIndex(self, index):
        if useProxyFileModel:
            return self.model().mapFromSource(index)
        return index

    def setNameFilters(self):
        # needs full model rebuilding, probably due to caching, just setting
        # name filters, see a few lines below, will corrupt the model.
        self.initModel()
        model = self.getSourceModel()

        # this doesn;t work:
        # model = self.getSourceModel()
        # if self.transformNode is not None:
        #     if hasattr(self.transformNode, 'includeFilters'):
        #         model.setNameFilters(self.transformNode.includeFilters)

        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())
        self.gotoLastData()

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
        selectedIndexes = self.selectionModel().selectedRows()
        lenSelectedIndexes = len(selectedIndexes)
        if lenSelectedIndexes == 0:
            return
        menu = qt.QMenu()

        shape = None
        paths, arrayPaths, fullPaths = [], [], []
        if lenSelectedIndexes > 0:
            for index in selectedIndexes:
                model, ind = self.getSourceModel(index)
                res = ind.data(USE_HDF5_ARRAY_ROLE)  # returns (path, shape)
                if res[0] is not None:
                    paths.append(res[0])
                if res[1] is not None:
                    fullPath = ind.data(LOAD_ITEM_PATH_ROLE)
                    fullPaths.append(fullPath)
                    arrayPaths.append(res[0])
                    shape = res[1]
                else:
                    arrayPaths, fullPaths = [], []

            if len(arrayPaths) == 1:
                strSum = ''
                strSumOf = ''
            else:
                strSum = 'the sum '
                strSumOf = 'of the sum '

            if len(arrayPaths) > 0 and self.transformNode:
                yLbls = self.transformNode.getPropList('qLabel')
                ndims = self.transformNode.getPropList('ndim')
                for iLbl, (yLbl, ndim) in enumerate(zip(yLbls, ndims)):
                    if not shape:
                        continue
                    if len(shape) < ndim:
                        continue
                    elif len(shape) == ndim:
                        menu.addAction("Set {0}as {1} array".format(
                            strSum, yLbl),
                            partial(self.setAsArray, iLbl, arrayPaths))
                        if len(arrayPaths) == 1:
                            menu.addAction("Set full path as {0} array".format(
                                yLbl),
                                partial(self.setAsArray, iLbl, fullPaths))
                    elif len(shape) > ndim:
                        menu.addAction(
                            "Set a {0}D slice {1}as {2} array".format(
                                ndim, strSumOf, yLbl),
                            partial(self.setAsArray, iLbl, arrayPaths,
                                    needSlice=(len(shape), ndim)))
                        if len(arrayPaths) == 1:
                            menu.addAction(
                                "Set a {0}D slice {1}of full path as {2} array"
                                .format(ndim, strSumOf, yLbl),
                                partial(self.setAsArray, iLbl, fullPaths,
                                        needSlice=(len(shape), ndim)))
                menu.addSeparator()

            if len(arrayPaths) > 1:
                for iLbl, yLbl in enumerate(yLbls):
                    menu.addAction("Set as a list of {0} arrays".format(yLbl),
                                   partial(self.setAsArray, iLbl, arrayPaths,
                                           isList=True))
                menu.addSeparator()

        isEnabled = False
        if self.transformNode is not None:
            for index in selectedIndexes:
                model, ind = self.getSourceModel(index)
                if ind.data(LOAD_DATASET_ROLE) is None:
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
        model, ind = self.getSourceModel(selectedIndexes[0])
        nodeType0 = model.nodeType(ind)
        menu.addAction(self.actionSynchronize)
        self.actionSynchronize.setEnabled(
            nodeType0 in (NODE_HDF5_HEAD, NODE_HDF5))

        if len(paths) > 0:
            menu.addSeparator()
            action = qt.QAction("Add to metadata list", menu)
            action.triggered.connect(partial(self.addMetadata, paths))
            menu.addAction(action)

        if nodeType0 == NODE_FS:
            # try:
            fname = model.filePath(ind)
            if not qt.QFileInfo(fname).isDir():
                menu.addSeparator()
                menu.addAction(self.actionViewTextFile)
            # except Exception:
            #     pass

        if hasattr(self, 'ModelTest'):
            menu.addSeparator()
            menu.addAction(self.actionTestModel)

        menu.exec_(self.viewport().mapToGlobal(point))

    def viewTextFile(self):
        if self.transformNode is None:
            return
        sIndexes = self.selectionModel().selectedRows()
        lenSelectedIndexes = len(sIndexes)
        if lenSelectedIndexes != 1:
            return
        model, ind = self.getSourceModel(sIndexes[0])
        nodeType = model.nodeType(ind)
        if nodeType != NODE_FS:
            return

        # try:
        fname = model.filePath(ind)
        if qt.QFileInfo(fname).isDir():
            return
        with open(fname, 'r') as f:
            lines = f.readlines()
        self.transformNode.widget.metadata.setText(''.join(lines))
        # except Exception:
        #     return

    def testModel(self):
        if hasattr(self, 'ModelTest'):
            self.ModelTest(self.model(), self)

    def getFullFileNames(self, urls):
        if isinstance(urls, qt.QModelIndex):
            model, ind = self.getSourceModel(urls)
            fname = model.filePath(ind)
            if qt.QFileInfo(fname).isDir():
                return
            urls = None
        if not urls:
            sIndexes = self.selectionModel().selectedRows()
            urls = []
            for index in sIndexes:
                model, ind = self.getSourceModel(index)
                nodeType = model.nodeType(ind)
                if nodeType == NODE_FS:
                    urls.append(model.filePath(ind))
                else:  # FileTreeView.NODE_HDF5, FileTreeView.NODE_HDF5_HEAD
                    urls.append(model.getHDF5FullPath(ind))
        return urls

    # def indexFromPath(self, path):
    #     model = self.getSourceModel()
    #     return model.indexFileName(path)

    # def indexFromH5Path(self, path, fallbackToHead=True):
    #     model = self.getSourceModel()
    #     return model.indexFromH5Path(path, fallbackToHead)

    def synchronizeHDF5(self):
        selectedIndexes = self.selectionModel().selectedRows()
        if len(selectedIndexes) == 0:
            selectedIndexes = self.prevSelectedIndexes
        if len(selectedIndexes) == 0:
            return
        index = selectedIndexes[0]
        row = index.row()
        model, ind = self.getSourceModel(index)
        nodeType0 = model.nodeType(ind)
        if nodeType0 not in (NODE_HDF5_HEAD, NODE_HDF5):
            return
        indexHead = model.synchronizeHdf5Index(ind)
        self.setCurrentIndex(indexHead)
        self.setExpanded(indexHead, True)
        self.scrollTo(model.index(row, 0, indexHead))

    def saveExpand(self, parent=qt.QModelIndex()):
        if not parent.isValid():
            self._expandedNodes = []
        for row in range(self.model().rowCount(parent)):
            ind = self.model().index(row, 0, parent)
            if self.model().rowCount(ind) > 0:
                if self.isExpanded(ind):
                    self._expandedNodes.append(ind.data())
                self.saveExpand(ind)

    def expandFurther(self, index):
        """Further expand a tree node if it has only one child."""
        if self.model().rowCount(index) == 1:
            child = self.model().index(0, 0, index)
            self.expand(child)

    def restoreExpand(self, parent=qt.QModelIndex()):
        if not parent.isValid():
            if len(self._expandedNodes) == 0:
                return
        # try:
        for row in range(self.model().rowCount(parent)):
            ind = self.model().index(row, 0, parent)
            if self.model().rowCount(ind) > 0:
                if ind.data() in self._expandedNodes:
                    self.setExpanded(ind, True)
                self.restoreExpand(ind)
        # except Exception:
        #     pass

    def selChanged(self, selected, deselected):
        # self.updateForSelectedFiles(selected.indexes()) #  × num of columns
        selectedIndexes = self.selectionModel().selectedRows()
        if selectedIndexes:
            self.prevSelectedIndexes = selectedIndexes  # in case selction is gone  # noqa
        self.updateForSelectedFiles(selectedIndexes)

    def updateForSelectedFiles(self, indexes):
        if self.transformNode is None:
            return
        cf = self.transformNode.widget.columnFormat
        for index in indexes:
            model, ind = self.getSourceModel(index)
            nodeType = model.nodeType(ind)
            if nodeType == NODE_FS:
                fileInfo = model.fileInfo(ind)
                if is_text_file(fileInfo.filePath()):
                    cf.setHeaderEnabled(True)
                    cf.setMetadataEnabled(False)
                else:
                    cf.setHeaderEnabled(False)
                    cf.setMetadataEnabled(True)
                    return
            else:
                cf.setHeaderEnabled(False)
                cf.setMetadataEnabled(True)
                return

    def _enrtySubpaths(self, paths):
        subpaths = []
        for path in paths:
            slashC = path.count('/')
            if slashC == 1:
                subpath = path[1:]  # without leading "/"
            elif slashC > 1:
                pos2 = path.find('/', path.find('/')+1)  # 2nd occurrence
                subpath = path[pos2+1:]  # without leading "/"
            else:
                return []
            subpaths.append(subpath)
        return subpaths

    def setAsArray(self, iArray, paths, isList=False, needSlice=None):
        if self.transformNode is None:
            return
        cf = self.transformNode.widget.columnFormat
        edit = cf.dataEdits[iArray]
        sliceEdit = cf.sliceEdits[iArray]
        sliceEdit.setVisible(needSlice is not None)
        if needSlice is not None:
            dataDims, needDims = needSlice  # dataDims > needDims
            txt = ', '.join([':']*dataDims)
            txt = txt.replace(':', '0', dataDims-needDims)
            sliceEdit.setText(txt)
        else:
            sliceEdit.setText('')

        if paths[0].startswith('silx'):
            edit.setText(paths[0])
            return

        subpaths = self._enrtySubpaths(paths)
        if len(subpaths) == 1:
            txt = subpaths[0]
        elif len(subpaths) == 2:
            txt = ' + '.join(['d["{0}"]'.format(sp) for sp in subpaths])
            if isList:
                txt = txt.replace(' + ', ', ')
        elif len(subpaths) > 2:
            cs = subpaths[0]
            for subpath in subpaths[1:]:
                cs = cco.common_substring((cs, subpath))
            colNames = [subpath[len(cs):] for subpath in subpaths]
            txt = '" + ".join([\'d[path]\'.format(i) for i in {0}])'.format(
                repr(colNames))
            txt = txt.replace('path', '"'+cs+'{0}"')
            if isList:
                txt = txt.replace(' + ', ', ')
        else:
            return
        edit.setText(txt)

    def addMetadata(self, paths):
        subpaths = self._enrtySubpaths(paths)
        cf = self.transformNode.widget.columnFormat
        cf.addMetadata(subpaths)

    def startDrag(self, supportedActions):
        listSelected = self.selectedIndexes()
        if listSelected:
            model, ind = self.getSourceModel(listSelected)
            mimeData = model.mimeData(ind)
            if mimeData is None:
                return
            dragQDrag = qt.QDrag(self)
            dragQDrag.setMimeData(mimeData)
            defaultDropAction = qt.Qt.IgnoreAction
            dragQDrag.exec_(supportedActions, defaultDropAction)

    def gotoWhenReady(self, path, callback=True):
        """Going directly to a file or directory is not possible because of the
        lazy loading mechanism. This is implemented here in 3 steps:

        1) Go to the containing dir. This sends reques to QFileSystemModel to
           populate it.

        2) When the dir is redy, QFileSystemModel emits directoryLoaded signal.
           We create hdf5 tree nodes if the dir contains hdf5 files.

        3) When hdf5's are ready, pathReady signal is emitted, in whose slot we
           scroll to the requested path after a delay. The view doesn't scroll
           there with 0 delay.
        """

        if path.startswith('silx:') or ('::' in path):
            start = 5 if path.startswith('silx:') else 0
            end = path.find('::') if '::' in path else None
            head = path[start:end]
            dirname = osp.dirname(osp.abspath(head)).replace('\\', '/')
            pathType = NODE_HDF5
        else:
            dirname = osp.dirname(osp.abspath(path)).replace('\\', '/')
            pathType = NODE_FS

        model = self.getSourceModel()
        if dirname.lower() in model.folders:
            model.pendingPath = None
            if pathType == NODE_HDF5:
                index = model.indexFromH5Path(path)
            elif pathType == NODE_FS:
                index = model.indexFileName(path)
        else:
            model.pendingPath = (dirname, path) if callback else None
            index = model.indexFileName(dirname)

        ind = self.getProxyIndex(index)
        self.scrollTo(ind, qt.QAbstractItemView.PositionAtCenter)
        self.setCurrentIndex(ind)

    def _gotoIsReady(self, path, delay=2500):  # ms
        """The delay can be as short as 500 ms for a stand alone treeView. In
        a bigger GUI it needs to be longer, otherwise it doesn't scroll to the
        path."""
        scrollTimer = qt.QTimer(self)
        scrollTimer.setSingleShot(True)
        scrollTimer.timeout.connect(partial(self.gotoWhenReady, path, False))
        scrollTimer.start(delay)

    def comparePathWithLastLoaded(self, path, suffix=''):
        if configLoad.has_option('Data', self.transformNode.name+suffix):
            lastPath = configLoad.get('Data', self.transformNode.name+suffix)
        else:
            lastPath = ''
        return osp.normpath(path).lower() == osp.normpath(lastPath).lower() \
            if lastPath else False
