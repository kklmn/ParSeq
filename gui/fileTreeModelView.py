# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "12 Jul 2022"
u"""
The `files and containers` model is a file system model (qt.QFileSystemModel)
extended by the hdf5 model from silx (silx.gui.hdf5.Hdf5TreeModel), so that
hdf5 containers can be viewed in the same tree. This interconnection of the two
models is almost complete except for sorting functionality by pressing the
column headers.
"""
# !!! SEE CODERULES.TXT !!!

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

useProxyModel = True  # only for decoration, sorting doesn't work so far

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


class FileSystemWithHdf5Model(qt.QFileSystemModel):
    resetRootPath = qt.pyqtSignal(qt.QModelIndex)
    requestSaveExpand = qt.pyqtSignal()
    requestRestoreExpand = qt.pyqtSignal()

    def __init__(self, transformNode=None, parent=None):
        super().__init__(parent)
        self.transformNode = transformNode
        self.h5Model = MyHdf5TreeModel(self)
        self.h5ModelRoot = self.h5Model.nodeFromIndex(qt.QModelIndex())
        if useProxyModel:
            self.h5ProxyModel = NexusSortFilterProxyModel(self)
            self.h5ProxyModel.setSourceModel(self.h5Model)
            self.h5ProxyModel.getNxIcon = \
                self.h5ProxyModel._NexusSortFilterProxyModel__getNxIcon
        self.h5Model.setFileMoveEnabled(False)
        # this won't handle renames, deletes, and moves:
        self.h5Model.nodesH5 = []
        self.nodesHead = []
        self.nodesNoHead = []
        self._roothPath = None
        # self.layoutAboutToBeChanged.connect(self._resetModel)
        self.layoutChanged.connect(self._restoreExpand)
        self.directoryLoaded.connect(self._fetchHdf5)
        # self.setOption(qt.QFileSystemModel.DontUseCustomDirectoryIcons)

    def _resetModel(self):
        """Without reset it crashes if hdf5 nodes are expanded... or not"""
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
        return super().headerData(section, orientation, role)

    def flags(self, index):
        if not index.isValid():
            return qt.Qt.NoItemFlags
        res = super().flags(index) | qt.Qt.ItemIsEnabled | \
            qt.Qt.ItemIsSelectable | qt.Qt.ItemIsDragEnabled
        return res

    def _mapIndex(self, indexFrom, modelFrom, modelTo):
        if modelFrom is modelTo:
            return indexFrom
        if not indexFrom.isValid():
            return qt.QModelIndex()
        # assert indexFrom.model() is modelFrom
        pntr = indexFrom.internalPointer()
        return modelTo.createIndex(indexFrom.row(), indexFrom.column(), pntr)

    def mapFromFS(self, indexFS):
        return self._mapIndex(indexFS, self, self)

    def mapFromH5(self, indexH5):
        return self._mapIndex(indexH5, self.h5Model, self)

    def mapToFS(self, index):
        return self._mapIndex(index, self, self)

    def mapToH5(self, index):
        return self._mapIndex(index, self, self.h5Model)

    def setRootPath(self, dirname):
        self._roothPath = dirname
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

    def mapFStoH5(self, indexFS):
        index = self.mapFromFS(indexFS)
        if index.internalId() in self.nodesHead:
            fileInfo = self.fileInfo(indexFS)
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
        if nodeType == NODE_FS:
            return super().rowCount(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.rowCount(self.mapFStoH5(self.mapToFS(parent)))
        elif nodeType == NODE_HDF5:
            return self.h5Model.rowCount(self.mapToH5(parent))
        else:
            raise ValueError('unknown node type in `rowCount`')

    def columnCount(self, parent=qt.QModelIndex()):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().columnCount(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.columnCount(
                self.mapFStoH5(self.mapToFS(parent)))
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
            return self.h5Model.canFetchMore(
                self.mapFStoH5(self.mapToFS(parent)))
        elif nodeType == NODE_HDF5:
            return self.h5Model.canFetchMore(self.mapToH5(parent))
        else:
            raise ValueError('unknown node type in `canFetchMore`')

    def _fetchHdf5(self, path):
        parent = self.indexFileName(path)
        # t0 = time.time()
        # print('loading', path, self.rowCount(parent))
        countHdf5 = 0
        for row in range(self.rowCount(parent)):
            indexFS = self.index(row, 0, parent)
            fileInfo = self.fileInfo(indexFS)
            fname = fileInfo.filePath()
            ext = '.' + fileInfo.suffix()
            # index = self.mapFromFS(indexFS)
            intId = indexFS.internalId()
            if (intId not in self.nodesHead and intId not in self.nodesNoHead):
                if ext in silx_io.utils.NEXUS_HDF5_EXT:
                    # = [".h5", ".nx5", ".nxs",  ".hdf", ".hdf5", ".cxi"]
                    try:
                        self.nodesHead.append(intId)
                        self.beginInsertRows(parent, row, -1)
                        # self.h5Model.appendFile(fname)  # slower, not always
                        self.h5Model.insertFileAsync(fname)  # faster sometimes
                        self.endInsertRows()
                        countHdf5 += 1
                    except IOError:
                        self.nodesNoHead.append(intId)
                else:
                    self.nodesNoHead.append(intId)
        if countHdf5 > 0:
            self.layoutChanged.emit()
        # print("loaded {0} htf5's in {1} s".format(countHdf5, time.time()-t0))

    def fetchMore(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            super().fetchMore(parent)
        elif nodeType == NODE_HDF5_HEAD:
            self.h5Model.fetchMore(self.mapFStoH5(self.mapToFS(parent)))
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
        if not indexFS.isValid():
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
        if not indexH5.isValid():
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
            slices = df.get('slices', ['' for ds in datas])  # from dataEdits
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
            indexFS = self.mapToFS(index)
            fileInfo = self.fileInfo(indexFS)
            if not is_text_file(fileInfo.filePath()):
                return
            return self.tryLoadColDataset(indexFS)
        elif nodeType == NODE_HDF5_HEAD:
            indexFS = self.mapToFS(index)
            indexH5 = self.mapFStoH5(indexFS)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)
        return self.tryLoadHDF5Dataset(indexH5)

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
            node = self.h5Model.nodeFromIndex(indexH5)
            if node.dataLink(qt.Qt.DisplayRole) == 'External':
                nodePath = self.getHDF5NodePath(node)
            else:
                nodePath = node.obj.name
            try:
                if (len(node.obj.shape) >= 1):
                    return nodePath
            except:  # noqa
                pass
        return

    def getHDF5NodePath(self, node):
        if node.parent is None or not hasattr(node.parent, 'basename'):
            return ''
        else:
            return '/'.join((self.getHDF5NodePath(node.parent), node.basename))

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

        node = self.h5Model.nodeFromIndex(indexH5)
        if node.dataLink(qt.Qt.DisplayRole) == 'External':
            nodePath = self.getHDF5NodePath(node)
        else:
            nodePath = node.obj.name
        return 'silx:' + '::'.join((node.obj.file.filename, nodePath))

    def data(self, index, role=qt.Qt.DisplayRole):
        shouldSkip = False
        if csi.currentNode is not None:
            node = csi.currentNode
            if node.widget.onTransform:
                shouldSkip = True
        if shouldSkip and role in [LOAD_DATASET_ROLE, USE_HDF5_ARRAY_ROLE,
                                   LOAD_ITEM_PATH_ROLE, qt.Qt.ToolTipRole]:
            return

        if not index.isValid():
            return
        if role == LOAD_DATASET_ROLE:
            return self.tryLoadDataset(index)
        if role == USE_HDF5_ARRAY_ROLE:
            return self.getHDF5ArrayPath(index)

        nodeType = self.nodeType(index)
        if nodeType == NODE_FS:
            indexFS = self.mapToFS(index)
            if role == LOAD_ITEM_PATH_ROLE:
                return self.filePath(indexFS)
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
            if useProxyModel:
                if role == qt.Qt.ToolTipRole:
                    res = self.h5Model.data(indexH5, role)
                    if res is None:
                        return
                    node = self.h5Model.nodeFromIndex(indexH5)
                    if node.dataLink(qt.Qt.DisplayRole) == 'External':
                        path = node.obj.name
                        truePath = self.getHDF5NodePath(node)
                        res = res.replace(path, truePath)
                        res = res.replace(' Dataset', ' External Dataset')
                    return res
                return self.h5ProxyModel.data(
                    self.h5ProxyModel.mapFromSource(indexH5), role)
            else:
                return self.h5Model.data(indexH5, role)
        elif nodeType == NODE_HDF5_HEAD:
            indexFS = self.mapToFS(index)
            fileInfo = self.fileInfo(indexFS)
            if role == qt.Qt.ToolTipRole:
                indexH5 = self.mapFStoH5(indexFS)
                return self.h5Model.data(indexH5, role)
            elif role == qt.Qt.ForegroundRole:
                return qt.QColor(gco.COLOR_HDF5_HEAD)
            elif role == qt.Qt.DecorationRole:
                if useProxyModel and \
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
            if False:  # useProxyModel: !!! doesn't help in sorting !!!
                if parentType == NODE_HDF5:
                    parentProxyH5 = self.h5ProxyModel.mapFromSource(
                        self.mapToH5(parent))
                elif parentType == NODE_HDF5_HEAD:
                    parentProxyH5 = self.h5ProxyModel.mapFromSource(
                        self.mapFStoH5(self.mapToFS(parent)))
                indexH5 = self.h5ProxyModel.index(row, column, parentProxyH5)
                index = self.mapFromH5(self.h5ProxyModel.mapToSource(indexH5))
            else:
                if parentType == NODE_HDF5:
                    parentH5 = self.mapToH5(parent)
                elif parentType == NODE_HDF5_HEAD:
                    parentH5 = self.mapFStoH5(self.mapToFS(parent))
                indexH5 = self.h5Model.index(row, column, parentH5)
                index = self.mapFromH5(indexH5)

            intId = indexH5.internalId()
            if intId not in self.h5Model.nodesH5:
                self.h5Model.nodesH5.append(intId)
            return index

        indexFS = super().index(row, column, parent)
        return self.mapFromFS(indexFS)

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
                indexFS = self.mapToFS(index)
                if checkValidity:
                    if self.tryLoadColDataset(indexFS) is None:
                        return
                indexesFS.append(indexFS)
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
        if csi.currentNode is not None:
            node = csi.currentNode
            if node.widget.onTransform:
                super().paint(painter, option, index)
                return

        path = index.data(LOAD_ITEM_PATH_ROLE)
        if path:
            # lastPath = configLoad.get(
            #     'Load', self.parent().transformNode.name, fallback='')
            if configLoad.has_option(
                    'Data', self.parent().transformNode.name):
                lastPath = configLoad.get(
                    'Data', self.parent().transformNode.name)
            else:
                lastPath = ''
            if lastPath:
                if osp.normpath(path).lower() == \
                        osp.normpath(lastPath).lower():
                    option.font.setWeight(qt.QFont.Bold)
            if configLoad.has_option(
                    'Data', self.parent().transformNode.name+'_silx'):
                lastPathSilx = configLoad.get(
                    'Data', self.parent().transformNode.name+'_silx')
            else:
                lastPathSilx = ''
            if lastPathSilx:
                if osp.normpath(path).lower() == \
                        osp.normpath(lastPathSilx).lower():
                    option.font.setWeight(qt.QFont.Bold)

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
        super().__init__(parent)
        model = FileSystemWithHdf5Model(transformNode, self)
        # model = qt.QFileSystemModel(self)  # for test purpose
        if hasattr(transformNode, 'fileNameFilters'):
            # model.setFilter(qt.QDir.NoDotAndDotDot | qt.QDir.Files)
            model.setNameFilters(transformNode.fileNameFilters)
            model.setNameFilterDisables(False)
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
            if parent is not None:
                self.parent().setMouseTracking(True)

        if roothPath is None:
            roothPath = ''
        rootIndex = model.setRootPath(roothPath)
        self.setRootIndex(rootIndex)
        self._expandedNodes = []

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
            self.actionLoad.setShortcut('Ctrl+L')
        self.actionSynchronize = self._addAction(
            "Synchronize container", self.synchronizeHDF5, "Ctrl+R")
        self.actionSynchronize.setShortcut('Ctrl+R')
        self.actionViewTextFile = self._addAction(
            "View text file (will be diplayed in 'metadata' panel)",
            self.viewTextFile, "F3")
        self.actionViewTextFile.setShortcut('F3')

        # for testing the file model:
        # from ..tests.modeltest import ModelTest
        # self.ModelTest = ModelTest
        # self.actionTestModel = self._addAction("Test Model", self.testModel)

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

        shape = None
        if lenSelectedIndexes >= 1:
            paths, fullPaths = [], []
            for index in selectedIndexes:
                path = index.data(USE_HDF5_ARRAY_ROLE)
                fullPath = index.data(LOAD_ITEM_PATH_ROLE)
                if path is not None:
                    fullPaths.append(fullPath)
                    paths.append(path)
                    shape = self.model().h5Model.nodeFromIndex(index).obj.shape
                else:
                    paths, fullPaths = [], []
                    break

            if len(paths) == 1:
                strSum = ''
                strSumOf = ''
            else:
                strSum = 'the sum '
                strSumOf = 'of the sum '

            if len(paths) > 0:
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
                            partial(self.setAsArray, iLbl, paths))
                        if len(paths) == 1:
                            menu.addAction("Set full path as {0} array".format(
                                yLbl),
                                partial(self.setAsArray, iLbl, fullPaths))
                    elif len(shape) > ndim:
                        menu.addAction(
                            "Set a {0}D slice {1}as {2} array".format(
                                ndim, strSumOf, yLbl),
                            partial(self.setAsArray, iLbl, paths,
                                    needSlice=(len(shape), ndim)))
                        if len(paths) == 1:
                            menu.addAction(
                                "Set a {0}D slice {1}of full path as {2} array"
                                .format(ndim, strSumOf, yLbl),
                                partial(self.setAsArray, iLbl, fullPaths,
                                        needSlice=(len(shape), ndim)))
                menu.addSeparator()

            if len(paths) > 1:
                for iLbl, yLbl in enumerate(yLbls):
                    menu.addAction("Set as a list of {0} arrays".format(yLbl),
                                   partial(self.setAsArray, iLbl, paths,
                                           isList=True))
                menu.addSeparator()

        isEnabled = False
        for index in selectedIndexes:
            if index.data(LOAD_DATASET_ROLE) is None:
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

        if nodeType0 == NODE_FS:
            try:
                fname = self.model().filePath(selectedIndexes[0])
                if not qt.QFileInfo(fname).isDir():
                    menu.addSeparator()
                    menu.addAction(self.actionViewTextFile)
            except Exception:
                pass

        if hasattr(self, 'ModelTest'):
            menu.addSeparator()
            menu.addAction(self.actionTestModel)

        menu.exec_(
            self.transformNode.widget.files.viewport().mapToGlobal(point))

    def viewTextFile(self):
        if self.transformNode is None:
            return
        sIndexes = self.selectionModel().selectedRows()
        lenSelectedIndexes = len(sIndexes)
        if lenSelectedIndexes != 1:
            return
        nodeType = self.model().nodeType(sIndexes[0])
        if nodeType != NODE_FS:
            return

        try:
            fname = self.model().filePath(sIndexes[0])
            if qt.QFileInfo(fname).isDir():
                return
            with open(fname, 'r') as f:
                lines = f.readlines()
            self.transformNode.widget.metadata.setText(''.join(lines))
        except Exception:
            return

    def testModel(self):
        if hasattr(self, 'ModelTest'):
            self.ModelTest(self.model(), self)

    def synchronizeHDF5(self):
        selectedIndexes = self.selectionModel().selectedRows()
        if len(selectedIndexes) == 0:
            selectedIndexes = self.prevSelectedIndexes
        if len(selectedIndexes) == 0:
            return
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

    def expandFurther(self, index):
        """Further expand a tree node if it has only one child."""
        if self.model().rowCount(index) == 1:
            child = self.model().index(0, 0, index)
            self.expand(child)

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
        except:  # noqa
            pass

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
            nodeType = self.model().nodeType(index)
            if nodeType == NODE_FS:
                indexFS = self.model().mapToFS(index)
                fileInfo = self.model().fileInfo(indexFS)
                if is_text_file(fileInfo.filePath()):
                    cf.setHeaderEnabled(True)
                else:
                    cf.setHeaderEnabled(False)
                    return
            else:
                cf.setHeaderEnabled(False)
                return

    def setAsArray(self, iArray, paths, isList=False, needSlice=None):
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
