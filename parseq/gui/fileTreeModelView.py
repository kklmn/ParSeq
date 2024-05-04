# -*- coding: utf-8 -*-
u"""
The `files and containers` model is a file system model (qt.QFileSystemModel)
extended by the hdf5 model from silx (silx.gui.hdf5.Hdf5TreeModel), so that
hdf5 containers can be viewed in the same tree.
"""
__author__ = "Konstantin Klementiev"
__date__ = "2 Mar 2023"
# !!! SEE CODERULES.TXT !!!


import os
import os.path as osp
import glob
import re
from functools import partial
import pickle
import time
import numpy as np
import warnings

os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"  # to work with external links
os.environ["QT_FILESYSTEMMODEL_WATCH_FILES"] = '1'  # potentially heavy load!!
# import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"

import silx
from distutils.version import LooseVersion  # , StrictVersion
assert LooseVersion(silx.version) >= LooseVersion("1.1.0")
from silx.gui import qt
import silx.io as silx_io
from silx.gui.hdf5.Hdf5TreeModel import Hdf5TreeModel

from ..core import commons as cco
from ..core import singletons as csi
from ..core import config
from . import gcommons as gco

useProxyFileModel = False  # proxy model for FileSystemWithHdf5Model
useProxyH5Model = True  # for decoration and sorting
if useProxyH5Model:
    from silx.gui.hdf5.NexusSortFilterProxyModel import \
        NexusSortFilterProxyModel

NODE_FS, NODE_HDF5, NODE_HDF5_HEAD = range(3)
LOAD_DATASET_ROLE = Hdf5TreeModel.USER_ROLE
USE_HDF5_ARRAY_ROLE = Hdf5TreeModel.USER_ROLE + 1
LOAD_ITEM_PATH_ROLE = Hdf5TreeModel.USER_ROLE + 2
H5PY_OBJECT_ROLE = Hdf5TreeModel.H5PY_OBJECT_ROLE

NEXUS_HDF5_EXT = [e[1:] if e.startswith('.') else e for e in
                  silx_io.utils.NEXUS_HDF5_EXT]
# = ["h5", "nx5", "nxs",  "hdf", "hdf5", "cxi"]
COLUMN_FILE_EXT = ["dat", "fio"]

COLUMN_NAME_WIDTH = 250
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
        # try:  # may fail during loading
        return node.isGroupObj()
        # except Exception:
        #     return False

    def canFetchMore(self, parent):
        node = self.nodeFromIndex(parent)
        if node is None:
            return False
        # try:
        if not node.isGroupObj():
            return False
        if node._Hdf5Node__child is None:
            return True
        # except AttributeError:
        #     return False
        return True

    def fetchMore(self, parent):
        node = self.nodeFromIndex(parent)
        if node is None:
            return
        super().fetchMore(parent)
        added = 0
        for row in range(node.childCount()):
            node.child(row)
            ind = self.index(row, 0, parent)
            intId = ind.internalId()
            if intId not in self.nodesH5:
                added += 1
                self.nodesH5.append(intId)
        # if added:
        #     print('Added from {0}: {1}'.format(node.basename, added))

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
        if pathList == ['']:
            return parent
        return self._indexFromPathList(parent, pathList)

    def _indexFromPathList(self, parent, pathList):
        parentNode = self.nodeFromIndex(parent)
        self.fetchMore(parent)
        for row in range(parentNode.childCount()):
            ind = self.index(row, 0, parent)
            node = self.nodeFromIndex(ind)
            path = self.getHDF5NodePath(node)
            # if node.dataLink(qt.Qt.DisplayRole) == 'External':
            #     path = self.getHDF5NodePath(node)
            # else:
            #     path = node.obj.name
            if path.split('/')[-1] == pathList[0]:
                if len(pathList) == 1:
                    return ind
                return self._indexFromPathList(ind, pathList[1:])
        else:
            # return qt.QModelIndex()
            return parent

    def getHDF5NodePath(self, node):
        if node.parent is None or not hasattr(node.parent, 'basename'):
            return ''
        else:
            return '/'.join((self.getHDF5NodePath(node.parent), node.basename))


# class MySortFilterProxyModel(qt.QSortFilterProxyModel):
# !!! Do not use QSortFilterProxyModel as it interferes with the joint of
# QFileSystemModel with Hdf5TreeModel: in onDirectoryLoaded() some indexes
# become dynamically invalid. Moreover, with QSortFilterProxyModel,
# onDirectoryLoaded() would load all hdf5's and only after the loading the
# filtering would apply, so the exclusion pattern would not accelerate the
# loading. !!!
class MySortFilterProxyModel(qt.QIdentityProxyModel):
    pass


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
        self.proxyModel = None
        # self.layoutAboutToBeChanged.connect(self.resetModel)
        # self.layoutChanged.connect(self.onLayoutChanged)
        self.directoryLoaded.connect(self.onDirectoryLoaded)

    def resetModel(self):
        # self.requestSaveExpand.emit()
        self.beginResetModel()
        self.endResetModel()
        self.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

    # def onLayoutChanged(self):
    #     self.requestRestoreExpand.emit()

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
        if not indexFrom.isValid():
            return qt.QModelIndex()
        assert indexFrom.model() is modelFrom
        # ii = indexFrom.internalPointer()  # don't use! seg fault on Linux
        ii = indexFrom.internalId()
        # try:
        index = modelTo.createIndex(indexFrom.row(), indexFrom.column(), ii)
        assert index.model() is modelTo
        return index
        # except (TypeError, AttributeError):
        #     return qt.QModelIndex()

    def mapFromH5(self, indexH5):
        return self._mapIndex(indexH5, self.h5Model, self)

    def mapToH5(self, index):
        return self._mapIndex(index, self, self.h5Model)

    def setRootPath(self, dirname):
        self._rootPath = dirname
        return super().setRootPath(dirname)

    def nodeType(self, index):
        if not index.isValid():
            # print('NODE_FS not valid')
            return NODE_FS
        indexH5 = self.mapToH5(index)
        if not indexH5.isValid():
            # print('NODE_FS indexH5 not valid')
            return NODE_FS
        idH5 = indexH5.internalId()
        if idH5 in self.h5Model.nodesH5:
            # print('NODE_HDF5', self.h5Model.nodeFromIndex(indexH5).obj.name)
            return NODE_HDF5

        id0 = index.internalId()
        # fileInfo = self.fileInfo(index)
        # filename = fileInfo.filePath()
        if id0 in self.nodesHead:
            # print('NODE_HDF5_HEAD', filename)
            return NODE_HDF5_HEAD
        else:
            # print('NODE_FS', filename)
            return NODE_FS

    def mapFStoH5(self, indexFS):  # only for h5 heads
        if indexFS.internalId() in self.nodesHead:
            fileInfo = self.fileInfo(indexFS)
            filename = fileInfo.filePath()
            hdf5Obj = self.h5Model.hdf5ObjFromFileName(filename)
            if hdf5Obj is not None:
                return self.h5Model.findIndex(hdf5Obj)
            else:
                return qt.QModelIndex()
        else:
            return qt.QModelIndex()

    # def mapH5toFS(self, indexH5):  # only for h5 heads
    #     parentH5 = self.h5Model.parent(indexH5)
    #     if not parentH5.isValid():
    #         hdf5Obj = self.h5Model.nodeFromIndex(indexH5)
    #         return self.indexFileName(hdf5Obj.obj.file.filename)
    #     else:
    #         return qt.QModelIndex()

    def rowCount(self, parent=qt.QModelIndex()):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().rowCount(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.rowCount(self.mapFStoH5(parent))
        elif nodeType == NODE_HDF5:
            return self.h5Model.rowCount(self.mapToH5(parent))
        else:
            return 0
            # raise ValueError('unknown node type in `rowCount`')

    def columnCount(self, parent=qt.QModelIndex()):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().columnCount(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.columnCount(self.mapFStoH5(parent))
        elif nodeType == NODE_HDF5:
            return self.h5Model.columnCount(self.mapToH5(parent))
        else:
            return 0
            # raise ValueError('unknown node type in `columnCount`')

    def hasChildren(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().hasChildren(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return True
        elif nodeType == NODE_HDF5:
            return self.h5Model.hasChildren(self.mapToH5(parent))
        else:
            return False
            # raise ValueError('unknown node type in `hasChildren`')

    def canFetchMore(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            return super().canFetchMore(parent)
        elif nodeType == NODE_HDF5_HEAD:
            return self.h5Model.canFetchMore(self.mapFStoH5(parent))
            # return True
        elif nodeType == NODE_HDF5:
            return self.h5Model.canFetchMore(self.mapToH5(parent))
        else:
            return False
            # raise ValueError('unknown node type in `canFetchMore`')

    def fetchMore(self, parent):
        nodeType = self.nodeType(parent)
        if nodeType == NODE_FS:
            super().fetchMore(parent)
        elif nodeType == NODE_HDF5_HEAD:
            self.h5Model.fetchMore(self.mapFStoH5(parent))
        elif nodeType == NODE_HDF5:
            self.h5Model.fetchMore(self.mapToH5(parent))
        else:
            pass
            # raise ValueError('unknown node type in `fetchMore`')

    def onDirectoryLoaded(self, path):
        """fetch Hdf5's"""
        path = osp.abspath(path).replace('\\', '/')
        # on Windows, paths sometimes start with a capital C:, sometimes with
        # a small c:, which breaks the inclusion checking, that's why lower():
        if path.lower() not in self.folders:
            self.folders.append(path.lower())
        parent = self.indexFileName(path)
        t0 = time.time()
        # print('loading', path, self.rowCount(parent))

        countHdf5 = 0
        self.beginInsertRows(parent, 0, -1)
        for row in range(self.rowCount(parent)):
            indexFS = self.index(row, 0, parent)
            if not indexFS.isValid():
                continue

            intId = indexFS.internalId()
            if intId not in self.nodesHead and intId not in self.nodesNoHead:
                fileInfo = self.fileInfo(indexFS)
                fname = fileInfo.filePath()

                # if (not isinstance(self.proxyModel, qt.QSortFilterProxyModel)
                #         and hasattr(self.transformNode, 'excludeFilters')):
                #     excluded = False
                #     for filt in self.transformNode.excludeFilters:
                #         if not filt:
                #             continue
                #         if re.search(filt.replace('*', '+'), fname):
                #             excluded = True
                #             break
                #     if excluded:
                #         self.nodesNoHead.append(intId)
                #         continue

                ext = fileInfo.suffix()
                if ext in NEXUS_HDF5_EXT:
                    try:
                        # self.beginInsertRows(indexFS, 0, 0)
                        # self.insertRow(0, indexFS)
                        self.nodesHead.append(intId)
                        self.h5Model.appendFile(fname)  # slower, not always
                        # don't use, it breaks the model:
                        # self.h5Model.insertFileAsync(fname)  # faster?
                        countHdf5 += 1
                        # self.endInsertRows()
                    except IOError as e:
                        print(e)
                        self.nodesNoHead.append(intId)
                else:
                    self.nodesNoHead.append(intId)

        self.endInsertRows()
        # if countHdf5 > 0:
        #     self.layoutChanged.emit()
        if csi.mainWindow and countHdf5 > 0:
            stat = "loaded {0} hdf5's".format(countHdf5)
            csi.mainWindow.displayStatusMessage(stat, duration=time.time()-t0)

        if self.pendingPath:
            if self.pendingPath[0].lower() == path.lower():
                self.pathReady.emit(self.pendingPath[1])

    def interpretArrayFormula(self, dataStr, treeObj, kind):
        """Returnes a list of (expr, d[xx]-styled-expr, data-keys, shape).
        *dataStr* may have several expressions with the syntax of a list or a
        tuple or just one expression if it is a simple string.
        """
        dataStr = str(dataStr)
        if "np." in dataStr:
            try:
                arr = eval(dataStr)
                return [(dataStr, None, None, arr.shape)]
            except Exception:
                pass
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
                if "Col" in colStr:
                    regex = re.compile('Col([0-9]*)')
                    # remove possible duplicates by list(dict.fromkeys())
                    subkeys = list(dict.fromkeys(regex.findall(colStr)))
                    keys = ['Col'+ch for ch in subkeys]
                    colStrD = str(colStr)
                    for ch in subkeys:
                        colStrD = colStrD.replace(
                            'Col'+ch, 'd["Col{0}"]'.format(ch))
                else:
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
                        indexH5 = self.indexFromH5Path(k, returnH5=True)
                        if not indexH5.isValid():  # doesn't exist
                            return
                        shape = self.h5Model.nodeFromIndex(indexH5).obj.shape
                    else:
                        shape = self.hasH5ChildPath(treeObj, k)
                    if shape is None:
                        return
                    d[k] = np.ones([2 for dim in shape])
            else:  # arrays from column file
                for k in keys:
                    kl = k.lower()
                    if "col" in kl:
                        kn = int(kl[kl.find('col')+3:])
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
        nodePath = self.h5Model.getHDF5NodePath(node)
        # if node.dataLink(qt.Qt.DisplayRole) == 'External':
        #     nodePath = self.h5Model.getHDF5NodePath(node)
        # else:
        #     nodePath = node.obj.name
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
            roles = self.transformNode.get_arrays_prop('role')
            nds = self.transformNode.get_arrays_prop('ndim')
            cdf.pop('conversionFactors', [])
            cdf.pop('metadata', [])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                arrs = np.genfromtxt(fname, unpack=True, max_rows=2, **cdf)
            if len(arrs) == 0:
                return

            for data, nd, role in zip(dataS, nds, roles):
                if role == 'optional':
                    lres.append('')
                    continue
                if isinstance(data, str) and len(data) == 0:
                    return
                colEval = self.interpretArrayFormula(data, arrs, 'col')
                if colEval is None:
                    return
                if nd:
                    if len(colEval[0][3]) < nd:
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
            roles = self.transformNode.get_arrays_prop('role')
            nds = self.transformNode.get_arrays_prop('ndim')
            slcs = df.get('slices', ['' for ds in datas])  # from sliceEdits
            for idata, (data, slc, nd, role) in enumerate(zip(
                    datas, slcs, nds, roles)):
                if role == 'optional':
                    lres.append('')
                    continue
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
            nodePath = self.h5Model.getHDF5NodePath(node)
            # if node.dataLink(qt.Qt.DisplayRole) == 'External':
            #     nodePath = self.h5Model.getHDF5NodePath(node)
            # else:
            #     nodePath = node.obj.name
            try:
                shape = node.obj.shape
                if len(shape) >= 1:
                    return nodePath, shape
                else:
                    return nodePath, None
            except:  # noqa
                return nodePath, None
        return None, None

    def getHDF5FullPath(self, index):
        nodeType = self.nodeType(index)
        if nodeType not in (NODE_HDF5_HEAD, NODE_HDF5):
            return
        if nodeType == NODE_HDF5_HEAD:
            indexH5 = self.mapFStoH5(index)
        elif nodeType == NODE_HDF5:
            indexH5 = self.mapToH5(index)

        node = self.h5Model.nodeFromIndex(indexH5)
        nodePath = self.h5Model.getHDF5NodePath(node)
        # if node.dataLink(qt.Qt.DisplayRole) == 'External':
        #     nodePath = self.h5Model.getHDF5NodePath(node)
        # else:
        #     nodePath = node.obj.name
        try:
            return 'silx:' + '::'.join((node.obj.file.filename, nodePath))
        except AttributeError:
            return

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
                ext = fileInfo.suffix()
                if ext in COLUMN_FILE_EXT:
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
                        truePath = self.h5Model.getHDF5NodePath(node)
                        res = res.replace(path, truePath)
                        res = res.replace(' Dataset', ' External Dataset')
                    return res
                else:
                    return self.h5ProxyModel.data(
                        self.h5ProxyModel.mapFromSource(indexH5), role)
            else:
                return res
        elif nodeType == NODE_HDF5_HEAD:
            if role == LOAD_ITEM_PATH_ROLE:
                return self.filePath(index)
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
            else:
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
                indexFS = self.mapFromH5(
                    self.h5ProxyModel.mapToSource(indexH5))
            else:
                if parentType == NODE_HDF5:
                    parentH5 = self.mapToH5(parent)
                elif parentType == NODE_HDF5_HEAD:
                    parentH5 = self.mapFStoH5(parent)
                indexH5 = self.h5Model.index(row, column, parentH5)
                indexFS = self.mapFromH5(indexH5)

            intId = indexH5.internalId()
            if intId not in self.h5Model.nodesH5:
                # should never come here
                self.h5Model.nodesH5.append(intId)
            return indexFS

        indexFS = super().index(row, column, parent)
        if (not isinstance(self.proxyModel, qt.QSortFilterProxyModel) and
                hasattr(self.transformNode, 'excludeFilters')):
            fileInfo = self.fileInfo(indexFS)
            fileName = fileInfo.fileName()
            for filt in self.transformNode.excludeFilters:
                if not filt:
                    continue
                if re.search(filt.replace('*', '+'), fileName):
                    return qt.QModelIndex()
        return indexFS

    def reloadHdf5(self, index):
        h5pyObject = self.data(index, role=H5PY_OBJECT_ROLE)
        if h5pyObject is None:
            return
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

    def indexFromH5Path(self, path, fallbackToHead=False, returnH5=False):
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
        if not headIndexH5.isValid():
            if super().canFetchMore(headIndexFS):
                super().fetchMore(headIndexFS)
            return headIndexFS if fallbackToHead else qt.QModelIndex()
        indexH5 = self.h5Model.indexFromPath(headIndexH5, fnameH5sub)
        if returnH5:
            return indexH5
        indexFS = self.mapFromH5(indexH5)
        return indexFS

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
                    npath = self.h5Model.getHDF5NodePath(node)
                    # if node.dataLink(qt.Qt.DisplayRole) == 'External':
                    #     npath = self.h5Model.getHDF5NodePath(node)
                    # else:
                    #     npath = node.obj.name
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
        if active and self.parent().transformNode:
            loadState = index.data(LOAD_DATASET_ROLE)
            cf = self.parent().transformNode.widget.columnFormat
            cf = cf.saveButton.setEnabled(loadState is not None)
        else:
            loadState = None

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
            # node.widget.enableAutoLoad.emit(loadState is not None)
            color.setAlphaF(0.2)
            option.palette.setColor(qt.QPalette.Highlight, color)
        super().paint(painter, option, index)

        res = index.data(USE_HDF5_ARRAY_ROLE)  # returns (path, shape)
        if isinstance(res, (list, tuple)):
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

        self.setItemDelegateForColumn(0, SelectionDelegate(self))
        if parent is not None:
            self.parent().setMouseTracking(True)  # for Windows
        self.viewport().setAttribute(qt.Qt.WA_Hover)  # for Linux

        # self.setMinimumSize(
        #     qt.QSize(int(COLUMN_NAME_WIDTH*csi.screenFactor), 250))
        # self.setColumnWidth(0, int(COLUMN_NAME_WIDTH*csi.screenFactor))
        self.setMinimumSize(qt.QSize(COLUMN_NAME_WIDTH, 50))
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
        self.expanded.connect(self.expandFurther)
        self.prevSelectedIndexes = []
        self.reloadDirFiles = {}

        if transformNode is not None:
            strLoad = "Load data (you can also drag it to the data tree)"
            self.actionLoad = self._addAction(
                strLoad, self.transformNode.widget.loadFiles, "Ctrl+L")
            iconLoad = self.style().standardIcon(qt.QStyle.SP_ArrowRight)
            self.actionLoad.setIcon(iconLoad)
        self.actionSynchronize = self._addAction(
            "Reload location", self.reload, ["Ctrl+R", "F5"])
        iconReload = self.style().standardIcon(qt.QStyle.SP_BrowserReload)
        self.actionSynchronize.setIcon(iconReload)
        self.actionViewTextFile = self._addAction(
            "View text file (will be displayed in 'metadata' panel)",
            self.viewTextFile, "F3")
        iconT = self.style().standardIcon(qt.QStyle.SP_FileDialogContentsView)
        self.actionViewTextFile.setIcon(iconT)

        # self.setStyleSheet("QTreeView"
        #                    "{selection-background-color: transparent;}")

        # # uncomment for testing the file model:
        # from ..tests.modeltest import ModelTest
        # self.ModelTest = ModelTest
        # self.actionTestModel = self._addAction(
        #     "Test file model", self.testModel)

    def initModel(self):
        try:
            model, index = self.getSourceModel(self.currentIndex())
            preservedPath = index.data(LOAD_ITEM_PATH_ROLE)
        except Exception:
            preservedPath = ''

        model = FileSystemWithHdf5Model(self.transformNode, self)
        # model = qt.QFileSystemModel(self)  # only for test purpose

        try:
            model.setOption(qt.QFileSystemModel.DontUseCustomDirectoryIcons)
        except AttributeError:  # added in Qt 5.14
            pass
        model.setFilter(
            qt.QDir.AllDirs | qt.QDir.AllEntries | qt.QDir.NoDotAndDotDot)
        model.setNameFilterDisables(False)
        rootIndex = model.setRootPath(self.rootPath)

        self._expandedNodes = []

        if isinstance(model, FileSystemWithHdf5Model):
            model.resetRootPath.connect(self._resetRootPath)
            # model.requestSaveExpand.connect(self.saveExpand)
            # model.requestRestoreExpand.connect(self.restoreExpand)
            model.pathReady.connect(self._gotoIsReady)
        else:
            model.indexFileName = model.index

        if useProxyFileModel:
            proxyModel = MySortFilterProxyModel(self)
            if isinstance(proxyModel, qt.QSortFilterProxyModel):
                proxyModel.setDynamicSortFilter(False)
                proxyModel.invalidate()
            proxyModel.setSourceModel(model)
            self.setModel(proxyModel)
            # model.layoutAboutToBeChanged.connect(proxyModel.invalidateFilter)
            # model.layoutChanged.connect(proxyModel.invalidateFilter)

            rootIndex = proxyModel.mapFromSource(rootIndex)
            if (isinstance(proxyModel, qt.QSortFilterProxyModel) and
                    hasattr(self.transformNode, 'excludeFilters')):
                model.proxyModel = proxyModel
                # example: r"^((?!excl1)(?!excl2).)*$")
                res = r"^("
                for excl in self.transformNode.excludeFilters:
                    if excl:
                        res += r"(?!{0})".format(excl)
                res += r".)*$"
                proxyModel.setFilterRegularExpression(res)
        else:
            self.setModel(model)

        if self.transformNode is not None:
            if hasattr(self.transformNode, 'includeFilters'):
                model.setNameFilters(self.transformNode.includeFilters)

        self.setRootIndex(rootIndex)

        # from ..tests.modeltest import ModelTest
        # ModelTest(self.model(), self)

        model = self.getSourceModel()
        model.dataChanged.emit(qt.QModelIndex(), qt.QModelIndex())

        if preservedPath:
            self.gotoWhenReady(preservedPath)
        if self.selectionModel():
            self.selectionModel().selectionChanged.connect(self.selChanged)

    def gotoLastData(self):
        if config.configLoad.has_option('Data', self.transformNode.name):
            path = config.configLoad.get('Data', self.transformNode.name)
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
                try:
                    os.chdir(dirname)
                except FileNotFoundError as e:  # can happen if disk is removed
                    print(e)
                    return
            self.gotoWhenReady(path)

    def getSourceModel(self, index=None):
        if useProxyFileModel:
            model = self.model().sourceModel()
            if index is not None:
                if isinstance(index, (list, tuple)):
                    ind = self.model().mapSelectionToSource(index)
                else:
                    ind = self.model().mapToSource(index)
        else:
            model = self.model()
            if index is not None:
                ind = index
        return (model, ind) if index is not None else model

    def getProxyIndex(self, index):
        if useProxyFileModel:
            return self.model().mapFromSource(index)
        return index

    def _addAction(self, text, slot, shortcut=None):
        action = qt.QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            if isinstance(shortcut, (list, tuple)):
                action.setShortcuts(shortcut)
            else:
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
                if isinstance(res, (list, tuple)):
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
                yLbls = self.transformNode.get_arrays_prop('qLabel')
                ndims = self.transformNode.get_arrays_prop('ndim')
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
                        menu.addAction(
                            "Set as a list of {0} arrays".format(yLbl),
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
            actionN0 = menu.addAction(
                "Concatenate {0} datasets along 0 axis and load as one".format(
                    lenSelectedIndexes),
                partial(self.transformNode.widget.loadFiles,
                        concatenate=(0, False)))
            actionN0.setEnabled(True)
            actionN1 = menu.addAction(
                "Sum {0} datasets individually".format(lenSelectedIndexes) +
                " along 0 axis, concatenate and load as one",
                partial(self.transformNode.widget.loadFiles,
                        concatenate=(0, True)))
            actionN1.setEnabled(True)

        if self.transformNode is not None:
            formats = self.getSavedFormats()
            if formats is not None:
                cf = self.transformNode.widget.columnFormat
                for fmtName, fmt in formats.items():
                    strFmt = "Define data format as '{0}'".format(fmtName)
                    action = qt.QAction(strFmt, menu)
                    action.triggered.connect(partial(cf.setDataFormat, fmt))
                    menu.addAction(action)

        menu.addSeparator()
        model, ind = self.getSourceModel(selectedIndexes[0])
        if hasattr(model, 'nodeType'):  # when not with a test model
            nodeType0 = model.nodeType(ind)
            menu.addAction(self.actionSynchronize)

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

    def getSavedFormats(self):
        cf = self.transformNode.widget.columnFormat
        section = ':'.join((self.transformNode.name, cf.fileType))
        if not config.configFormats.has_section(section):
            return
        formats = dict(config.configFormats[section])
        fullNames = self.getFullFileNames()  # all selected
        if fullNames is None:
            return
        url = fullNames[0]  # the 1st selected

        res = {}
        for formatName, val in formats.items():
            entry = eval(val)
            fmt = entry['dataFormat']  # dict
            inkeys = entry['inkeys']  # list
            outkeys = entry['outkeys']  # list
            header = ''
            if url.startswith('silx:'):
                if cf.fileType != 'h5':
                    continue
                with silx_io.open(url) as sf:
                    if silx_io.is_dataset(sf):
                        return
                    try:
                        headerList = list(sf['measurement'].keys())
                    except Exception:
                        headerList = []

                    mdt = fmt.get('metadata', '')
                    mds = [m.strip() for m in mdt.split(',')] if mdt else []
                    for md in mds:
                        try:
                            mdres = sf[md][()]
                            if isinstance(mdres, bytes):
                                mdres = mdres.decode("utf-8")
                            headerList.append(str(mdres))
                        except (ValueError, KeyError, OSError):
                            pass
                            # print('No metadata: {0}'.format(e))
            else:  # column file
                if cf.fileType != 'txt':
                    continue
                headerList = cco.get_header(url, fmt)
            header = ' '.join(headerList)
            if all(i in header for i in inkeys) and \
                    all(o not in header for o in outkeys if len(o) > 0):
                res[formatName] = fmt
        if len(res) == 0:
            return
        return res

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
        with open(fname, 'r', encoding="utf-8") as f:
            lines = f.readlines()
        self.transformNode.widget.metadata.setText(''.join(lines))
        # except Exception:
        #     return

    def testModel(self):
        if hasattr(self, 'ModelTest'):
            self.ModelTest(self.model(), self)

    def getFullFileNames(self, urls=None):
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
                else:  # NODE_HDF5, NODE_HDF5_HEAD
                    urls.append(model.getHDF5FullPath(ind))
        return urls

    def getActiveDir(self, path=None):  # used in autoLoad
        if path is None:
            sIndexes = self.selectionModel().selectedRows()
            if len(sIndexes) == 0:
                return '', []
            model, ind = self.getSourceModel(sIndexes[0])
        else:
            model = self.getSourceModel()
            if path.startswith('silx:'):
                if path.endswith('::/'):
                    ind = model.indexFileName(path[5:-3])
                else:
                    ind = model.indexFromH5Path(path)
            else:
                ind = model.indexFileName(path)
            if not ind.isValid():
                raise ValueError('invalid path')

        nodeType = model.nodeType(ind)
        if nodeType == NODE_FS:
            if not model.hasChildren(ind):
                ind = model.parent(ind)
            dirName = model.filePath(ind)
        else:  # NODE_HDF5, NODE_HDF5_HEAD
            if nodeType == NODE_HDF5:
                ind = model.parent(ind)
            dirName = model.getHDF5FullPath(ind)

        childPaths = []
        for row in range(model.rowCount(ind)):
            subInd = model.index(row, 0, ind)
            if not subInd.isValid():
                continue
            if nodeType == NODE_FS:
                childPaths.append(model.filePath(subInd))
            else:
                childPaths.append(model.getHDF5FullPath(subInd))

        return (dirName, childPaths) if path is None else childPaths

    def reload(self):
        selectedIndexes = self.selectionModel().selectedRows()
        if len(selectedIndexes) == 0:
            selectedIndexes = self.prevSelectedIndexes
        if len(selectedIndexes) == 0:
            return

        index = selectedIndexes[0]
        model, ind = self.getSourceModel(index)
        nodeType = model.nodeType(ind)
        if nodeType in (NODE_HDF5_HEAD, NODE_HDF5):
            try:
                indexHead = model.reloadHdf5(ind)
            except PermissionError as e:
                print(e)
                return
            self.setCurrentIndex(indexHead)
            self.setExpanded(indexHead, True)
            if nodeType == NODE_HDF5:
                row = index.row()
                indTo = model.index(row, 0, indexHead)
            elif nodeType == NODE_HDF5_HEAD:
                indTo = indexHead
            else:
                return
            self.scrollTo(indTo, qt.QAbstractItemView.PositionAtCenter)
        elif nodeType == NODE_FS:
            dirname = self.getActiveDir()[0]
            if not dirname.endswith('/'):
                dirname += '/'

            if dirname not in self.reloadDirFiles:
                self.reloadDirFiles[dirname] = []

            fileList = [p.replace('\\', '/') for p in
                        sorted(glob.glob(dirname + '*.*'), key=osp.getmtime)]
            updateList = [fn for fn in fileList
                          if fn not in self.reloadDirFiles[dirname]]
            for fn in updateList:
                self.gotoWhenReady(fn)
            self.reloadDirFiles[dirname].extend(updateList)

    # def saveExpand(self, parent=qt.QModelIndex()):
    #     if not parent.isValid():
    #         self._expandedNodes = []
    #     for row in range(self.model().rowCount(parent)):
    #         ind = self.model().index(row, 0, parent)
    #         if self.model().rowCount(ind) > 0:
    #             if self.isExpanded(ind):
    #                 self._expandedNodes.append(ind.data())
    #             self.saveExpand(ind)

    def expandFurther(self, index):
        """Further expand a tree node if it has only one child, and it has a
        group `measurement`."""
        model = self.model()

        if model.rowCount(index) == 1:
            child = model.index(0, 0, index)
            self.expand(child)

        # nodeType = model.nodeType(index)
        # if nodeType == NODE_HDF5:
        #     res = model.h5Model.indexFromPath(index, 'measurement')
        #     if res.isValid():
        #         child = model.index(res.row(), 0, index)
        #         self.expand(child)

    # def restoreExpand(self, parent=qt.QModelIndex()):
    #     if not parent.isValid():
    #         if len(self._expandedNodes) == 0:
    #             return
    #     # try:
    #     for row in range(self.model().rowCount(parent)):
    #         ind = self.model().index(row, 0, parent)
    #         if self.model().rowCount(ind) > 0:
    #             if ind.data() in self._expandedNodes:
    #                 self.setExpanded(ind, True)
    #             self.restoreExpand(ind)
    #     # except Exception:
    #     #     pass

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
        cf.setHeaderEnabled(True)
        cf.setMetadataEnabled(True)
        for index in indexes:
            model, ind = self.getSourceModel(index)
            if not hasattr(model, 'nodeType'):
                return
            nodeType = model.nodeType(ind)
            if nodeType == NODE_FS:
                fileInfo = model.fileInfo(ind)
                isTxtFile = is_text_file(fileInfo.filePath())
                cf.setHeaderEnabled(isTxtFile)
                cf.setMetadataEnabled(not isTxtFile)
                cf.fileType = 'txt' if isTxtFile else ''
                return
            else:
                cf.setHeaderEnabled(False)
                cf.setMetadataEnabled(True)
                cf.fileType = 'h5'
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
        if self.transformNode is None:
            return
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

        1) Go to the containing dir. This sends request to QFileSystemModel to
           populate it.

        2) When the dir is ready, QFileSystemModel emits directoryLoaded
           signal. We create hdf5 tree nodes if the dir contains hdf5 files.

        3) When hdf5's are ready, pathReady signal is emitted, in whose slot we
           scroll to the requested path after a delay. The view doesn't scroll
           there with 0 delay.
        """
        model = self.getSourceModel()
        if not hasattr(model, 'folders'):
            return
        if path.startswith('silx:') or ('::' in path):
            start = 5 if path.startswith('silx:') else 0
            end = path.find('::') if '::' in path else None
            head = path[start:end]
            dirname = osp.dirname(osp.abspath(head)).replace('\\', '/')
            pathType = NODE_HDF5
        else:
            if qt.QFileInfo(path).isDir():
                dirname = osp.abspath(path).replace('\\', '/')
            else:
                dirname = osp.dirname(osp.abspath(path)).replace('\\', '/')
            pathType = NODE_FS

        if dirname.lower() in model.folders:
            model.pendingPath = None
            if pathType == NODE_HDF5:
                index = model.indexFromH5Path(path)
            elif pathType == NODE_FS:
                index = model.indexFileName(path)
        else:
            model.pendingPath = (dirname, path) if callback else None
            index = model.indexFileName(dirname)

        if index.isValid():
            ind = self.getProxyIndex(index)
            if ind.isValid():
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
        opt = self.transformNode.name+suffix
        if config.configLoad.has_option('Data', opt):
            lastPath = config.configLoad.get('Data', opt)
        else:
            lastPath = ''
        return osp.normpath(path).lower() == osp.normpath(lastPath).lower() \
            if lastPath else False
