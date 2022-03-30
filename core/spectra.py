# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "21 Jul 2021"
# !!! SEE CODERULES.TXT !!!

import os.path as osp
import re
import time
import copy
import json
import numpy as np
from collections import Counter

import silx.io as silx_io

from . import singletons as csi
from . import commons as cco
from . import config

DEFAULT_COLOR_AUTO_UPDATE = False

DATA_COLUMN_FILE, DATA_DATASET, DATA_COMBINATION, DATA_FUNCTION, DATA_GROUP =\
    range(5)
COMBINE_NONE, COMBINE_AVE, COMBINE_SUM, COMBINE_PCA, COMBINE_RMS = range(5)
combineNames = '', 'ave', 'sum', 'PCA', 'RMS'


class TreeItem(object):
    def __init__(self, name, parentItem=None, insertAt=None, **kwargs):
        alias = kwargs.get('alias', 'auto')
        if '?' in name and alias == 'auto':  # string with name and alias
            self.name, self.alias = name.split('?')[:2]
        else:
            self.name = name
            if alias == 'auto':
                base = osp.basename(name)
                self.alias = osp.splitext(base)[0]
            else:
                self.alias = alias
        self.aliasExtra = None
        self.childItems = []
        self.isExpanded = True
        self.colorTag = 0
        self.isVisible = True
        self.beingTransformed = False
        self.parentItem = parentItem
        if parentItem is None:
            assert csi.dataRootItem is None, "Data tree already exists."
            csi.dataRootItem = self
            return
        if insertAt is None:
            parentItem.childItems.append(self)
        else:
            parentItem.childItems.insert(insertAt, self)

    def child(self, row):
        return self.childItems[row]

    def child_count(self):
        return len(self.childItems)

    def row(self):
        try:
            if self.parentItem is not None:  # else return None
                return self.parentItem.childItems.index(self)
        except ValueError:
            return

    def _childItemsRepr(self):
        return '[' + ', '.join(repr(it) for it in self.childItems) + ']'

    def __repr__(self):
        if self.parentItem is None:
            return self._childItemsRepr()
        if self.childItems:
            return "'{0}', {1}".format(self.alias, self._childItemsRepr())
        return "'" + self.alias + "'"

    def tooltip(self):
        if self.childItems or csi.dataRootItem is self:
            items = self.get_items()
            if self.has_groups():
                childCount = self.child_count()
                tip = "{0} top group{1} with {2} item{3}".format(
                    childCount, 's' if childCount > 1 else '',
                    len(items), 's' if len(items) > 1 else '')
            else:
                if len(items) == 0:
                    return "no items"
                tip = "{0} item{1}".format(
                    len(items), 's' if len(items) > 1 else '')
            if hasattr(self, 'alias'):
                tip = ': '.join([self.alias, tip])
            return tip
        else:
            res = ""
            if hasattr(self, 'name'):
                if isinstance(self.name, type("")):
                    res = self.name
            elif hasattr(self, 'madeOf'):
                if isinstance(self.madeOf, type("")):
                    res = self.madeOf
                    if self.aliasExtra:
                        res += ': {0}'.format(self.aliasExtra)
                    dataSource = self.dataFormat.get('dataSource', [])
                    for ds in dataSource:
                        if isinstance(ds, type("")):
                            if ds.startswith('silx'):
                                res += '\n' + ds
                    if csi.currentNode is not None:
                        node = csi.currentNode
                        if self.state[node.name] == cco.DATA_STATE_BAD:
                            res += '\nincopatible data shapes!'
            try:
                if csi.currentNode is not None:
                    node = csi.currentNode
                    if node.plotDimension == 1:
                        sh = getattr(self, node.plotXArray).shape[0]
                    elif node.plotDimension == 2:
                        sh = getattr(self, node.plot2DArray).shape
                    elif node.plotDimension == 3:
                        sh = getattr(self, node.plot3DArray).shape
                    else:
                        sh = None
                    if sh:
                        nl = '\n' if res else ''
                        what = 'shape' if node.plotDimension > 1 else 'length'
                        res += nl + '{0}: {1}'.format(what, sh)
            except Exception as e:
                res += '\n' + str(e)
                pass
            return res

    def data(self, column):
        leadingColumns = len(csi.modelLeadingColumns)
        if column < leadingColumns:
            if column == 0:
                return self.alias
        elif 0 <= column-leadingColumns < len(csi.modelDataColumns):
            if not hasattr(self, 'plotProps'):  # i.e. is a group
                return len(self.get_items())
            node, key = csi.modelDataColumns[column-leadingColumns]
            role = node.getProp(key, 'role')
            if role.startswith('0'):
                try:
                    res = getattr(self, key)
                except AttributeError:
                    return "---"
                if res is None:
                    return "---"
                formatStr = node.getProp(key, 'plotLabel')
                if '{' not in formatStr:
                    formatStr = '{0}'
                return formatStr.format(res)
            return self.color, self.plotProps[node.name][key]
        else:
            raise ValueError("invalid column")

    def get_state(self, column):
        return 1

    def set_data(self, column, value):
        if column == 0:
            self.alias = value
        else:
            raise ValueError("invalid column")

    def set_visible(self, value):
        self.isVisible = bool(value)
        for item in self.get_items(True):
            item.isVisible = bool(value)

    def find_data_item(self, alias=None):
        if alias is not None:
            for item in self.get_items():
                if item.alias == alias:
                    return item

    def get_top(self):
        return csi.dataRootItem

    def get_items(self, alsoGroupHeads=False):
        items = []
        for item in self.childItems:
            if item.childItems:
                if alsoGroupHeads:
                    if item not in items:
                        items.append(item)
                items += [i for i in item.get_items(alsoGroupHeads) if i not in
                          items]
            else:
                if item not in items:
                    items.append(item)
        return items

    def get_nongroups(self):
        return [item for item in self.childItems if len(item.childItems) == 0]

    def get_groups(self):
        return [item for item in self.childItems if len(item.childItems) > 0]

    def has_groups(self):
        for item in self.childItems:
            if item.childItems:
                return True
        return False

    def climb_rows(self):
        """Returns a list of rows starting from the item itself and continuing
        with its parents further up to the rootItem."""
        res, i = [], self
        while True:
            res.append(i.row())
            i = i.parentItem
            if i is None:
                return res[:-1]

    def is_ancestor_of(self, item):
        i = item
        while True:
            if i.parentItem is self:
                return True
            i = i.parentItem
            if i is None:
                return False

    def delete(self):
        try:
            self.parentItem.childItems.remove(self)
            if self.parentItem.child_count() == 0:
                self.parentItem.delete()
        except (AttributeError, ValueError):
            pass

    def insert_item(self, name, insertAt=None, **kwargs):
        return TreeItem(name, self, insertAt, **kwargs)

    def insert_data(self, data, insertAt=None, isTop=True, **kwargs):
        items = []
        if hasattr(self, 'alias'):
            alias = self.alias
        elif hasattr(self, 'madeOf'):
            alias = self.madeOf
        elif hasattr(self, 'name'):
            alias = self.name

        if isinstance(data, (type(""), type(u""))):
            item = self.insert_item(data, insertAt, **kwargs)
            if item not in items:  # inclusion check that keeps the order
                items.append(item)
        elif isinstance(data, (list, tuple)):
            si = self
            for subdata in data:
                if isinstance(subdata, (type(""), type(u""))):
                    si = self.insert_item(subdata, insertAt, **kwargs)
                    subItems = [si]
                elif isinstance(subdata, (list, tuple)):
                    if si in items:
                        items.remove(si)
                    subItems = si.insert_data(
                        subdata, isTop=False, **kwargs)  # no insertAt
                else:
                    raise ValueError(
                        "data in '{0}' must be a sequence or a string, not {1}"
                        " of type {2}".format(alias, subdata, type(subdata)))
                items += [it for it in subItems if it not in items]
        else:
            raise ValueError(
                "data in {0} must be a sequence or a string, not {1}"
                " of type {2}".format(alias, data, type(data)))
#        csi.recentlyLoadedItems.clear()
        csi.recentlyLoadedItems[:] = []
        csi.recentlyLoadedItems.extend(items)
        csi.allLoadedItems[:] = []
        csi.allLoadedItems.extend(csi.dataRootItem.get_items())
        if len(csi.selectedItems) == 0:
            csi.selectedItems = [csi.allLoadedItems[0]]
            csi.selectedTopItems = [csi.allLoadedItems[0]]

        shouldMakeColor = (len(self.childItems) > 0
                           and csi.withGUI)
        if shouldMakeColor:
            self.init_colors(self.childItems)
        return items

    def init_colors(self, items=None):
        from ..gui import gcommons as gco  # only needed with gui
        if not hasattr(self, 'colorAutoUpdate'):
            return
        citems = self.childItems if self.colorAutoUpdate else items
        if citems is None:
            return

        if self.colorPolicy == gco.COLOR_POLICY_GRADIENT:
            colors = gco.makeGradientCollection(
                self.color1, self.color2, len(citems))
        for i, item in enumerate(citems):
            if hasattr(item, 'colorIndividual'):
                item.color = item.colorIndividual
                continue
            if self.colorPolicy == gco.COLOR_POLICY_INDIVIDUAL:
                item.color = gco.getColorName(self.color)
            elif self.colorPolicy == gco.COLOR_POLICY_LOOP1:
                item.color = gco.colorCycle1[item.row() % len(gco.colorCycle1)]
            elif self.colorPolicy == gco.COLOR_POLICY_LOOP2:
                item.color = gco.colorCycle2[item.row() % len(gco.colorCycle2)]
            elif self.colorPolicy == gco.COLOR_POLICY_GRADIENT:
                item.color = colors[i].name()  # in the format "#RRGGBB"
            else:
                raise ValueError("wrong choice of color type")


class Spectrum(TreeItem):
    #  TODO describe configFieldsData and configFieldsGroup

    """ bla """

    configFieldsData = (  # to parse ini file section of data
        'madeOf', 'madeOf_relative', 'dataFormat', 'dataFormat_relative',
        'suffix', 'originNode', 'terminalNode', 'colorTag', 'color')
    configFieldsGroup = (  # to parse ini file section of group
         'colorPolicy', 'colorTag', 'colorAutoUpdate')

    def __init__(self, madeOf, parentItem=None, insertAt=None, **kwargs):
        """ *madeOf* is either a file name, a callable or a list of other
        Spectrum instances.

        *insertAt* is the position in parentItem.childItems list. If None, the
        spectrum is appended.

        *kwargs* defaults to the dictionary:
        dict(alias='auto', dataFormat={}, originNode=None, terminalNode=None)
        *dataFormat* is assumed to be empty for a data group and non-empty for
        a spectrum.

        *dataFormat*: dict
        As a minimum, it defines the key 'dataSource' and sets it to a list of
        hdf5 names (for the hdf5 data), column numbers or expressions of
        'Col1', 'Col2' etc variables (for column data). It may define
        'conversionFactors' as a list of either floats or strings; a foat is a
        multiplicaive factor that converts to the node's array unit and a
        string is another unit that cannot be converted to the node's array
        unit, e.g. the node defines an array with a 'mA' unit while the data
        was measured with a 'count' unit.

        The data propagation is between *originNode* and *terminalNode*, both
        ends are included. *originNode* can be int (the ordinal number of the
        node) or a node instance obtained from the OrderedDict
        `core.singletons.nodes`. If *originNode* is None, it defaults to the
        0th node (the head of the pipeline). If *terminalNode* is None, the
        data propagates down to the end(s) of the pipeline. If a node is
        between *originNode* and *terminalNode* (in the sense of data
        propagation) then the data is present in the node's data manager as
        *alias* and is displayed in the plot.

        """
        assert len(csi.nodes) > 0, "A data pipeline must be first created."
        self.madeOf = madeOf
        self.parentItem = parentItem
        self.childItems = []
        self.isVisible = True
        self.beingTransformed = False
        if parentItem is None:  # self is the root item
            assert csi.dataRootItem is None, "Data tree already exists."
            csi.dataRootItem = self
            if csi.withGUI:
                from ..gui import gcommons as gco
                self.colorPolicy = gco.COLOR_POLICY_LOOP1
                self.colorAutoUpdate = DEFAULT_COLOR_AUTO_UPDATE
            return

        self.alias = kwargs.get('alias', 'auto')
        self.suffix = kwargs.get('suffix', None)
        self.dataFormat = copy.deepcopy(kwargs.get('dataFormat', {}))
        originNode = kwargs.get('originNode', None)
        if originNode is None:
            originNode = list(csi.nodes.values())[0]
        elif isinstance(originNode, int):
            originNode = list(csi.nodes.values())[originNode]
        self.originNode = originNode
        terminalNode = kwargs.get('terminalNode', None)
        if isinstance(terminalNode, int):
            terminalNode = list(csi.nodes.values())[terminalNode]
        self.terminalNode = terminalNode

        self.isExpanded = True
        self.colorTag = kwargs.get('colorTag', 0)
        self.hasChanged = False
        self.state = dict((nn, cco.DATA_STATE_UNDEFINED) for nn in csi.nodes)
        self.aliasExtra = None  # for extra name qualifier
        self.meta = {}
        self.combinesTo = []  # list of instances of Spectrum if not empty
        self.transformParams = {}  # each transform will add to this dict

        if insertAt is None:
            parentItem.childItems.append(self)
        else:
            parentItem.childItems.insert(insertAt, self)

        if self.dataFormat:
            if 'conversionFactors' not in self.dataFormat:
                self.dataFormat['conversionFactors'] = \
                    [None for arr in self.originNode.arrays]
            copyTransformParams = kwargs.pop('copyTransformParams', False)
            transformParams = kwargs.pop('transformParams', {})
            runDownstream = kwargs.pop('runDownstream', True)
            if csi.withGUI:
                self.init_plot_props()
            self.read_data(runDownstream=runDownstream,
                           copyTransformParams=copyTransformParams,
                           transformParams=transformParams)
        else:  # i.e. is a group
            self.dataType = DATA_GROUP
            if csi.withGUI:
                from ..gui import gcommons as gco
                cp = (kwargs.pop('colorPolicy', 'loop1')).lower()
                if 'color' in kwargs:
                    cp = 'individual'
                if cp.startswith('ind'):  # individual
                    self.colorPolicy = gco.COLOR_POLICY_INDIVIDUAL
                    self.color = kwargs.pop('color', 'k')
                elif cp.startswith('loop1'):
                    self.colorPolicy = gco.COLOR_POLICY_LOOP1
                elif cp.startswith('loop2'):
                    self.colorPolicy = gco.COLOR_POLICY_LOOP2
                elif cp.startswith('grad'):
                    self.colorPolicy = gco.COLOR_POLICY_GRADIENT
                    self.color1 = kwargs.pop('color1', 'r')
                    self.color2 = kwargs.pop('color2', 'g')
                else:
                    raise ValueError("wrong choice of color type")
                self.colorAutoUpdate = bool(kwargs.pop(
                    'colorAutoUpdate', DEFAULT_COLOR_AUTO_UPDATE))
            if self.alias == 'auto':
                self.alias = madeOf

    def init_plot_props(self):
        row = self.row()
        if row is None:
            row = 0
        self.color = 'k'
        self.plotProps = {}
        for node in csi.nodes.values():
            self.plotProps[node.name] = {}
            if node.plotDimension == 1:
                for ind, yName in enumerate(node.plotYArrays):
                    plotParams = {'symbolsize': 2}
                    plotParams['yaxis'] = \
                        'right' if node.getProp(yName, 'role').endswith(
                            'right') else 'left'
                    defPlotParams = node.getProp(yName, 'plotParams')
                    for k, v in defPlotParams.items():
                        if isinstance(v, (list, tuple)):
                            pv = v[ind]
                        else:
                            pv = v
                        plotParams[k] = pv
                    if 'linestyle' not in plotParams:
                        plotParams['linestyle'] = '-'
                    self.plotProps[node.name][yName] = plotParams

    def get_state(self, column):
        leadingColumns = len(csi.modelLeadingColumns)
        if column < leadingColumns:
            return cco.DATA_STATE_GOOD
        node, key = csi.modelDataColumns[column-leadingColumns]
        role = node.getProp(key, 'role')
        if role.startswith('0'):
            return cco.DATA_STATE_GOOD
        return self.state[node.name]

    def read_data(self, shouldLoadNow=True, runDownstream=True,
                  copyTransformParams=True, transformParams={}):
        if callable(self.madeOf):
            self.dataType = DATA_FUNCTION
            if shouldLoadNow:
                self.create_data()
            if self.alias == 'auto':
                self.alias = "generated_{0}".format(self.madeOf.__name__)
        elif isinstance(self.madeOf, (list, tuple)):
            self.dataType = DATA_COMBINATION
            if shouldLoadNow:
                self.calc_combined()
            if self.alias == 'auto':
                cs = self.madeOf[0].alias
                for data in self.madeOf[1:]:
                    cs = cco.common_substring(cs, data.alias)
                what = self.dataFormat['combine']
                lenC = len(self.madeOf)
                self.alias = "{0}_{1}{2}".format(cs, combineNames[what], lenC)
        else:
            if self.madeOf.startswith('silx:'):
                self.dataType = DATA_DATASET
                if self.colorTag == 0:
                    self.colorTag = 1
            else:
                self.dataType = DATA_COLUMN_FILE
                if self.colorTag == 0:
                    self.colorTag = 2
            if shouldLoadNow:
                self.read_file()
            if not self.check_shape():
                print('Incopatible data shapes!')
                self.state[self.originNode.name] = cco.DATA_STATE_BAD
                self.colorTag = 3

            basename = osp.basename(self.madeOf)
            if self.alias == 'auto':
                tmpalias = osp.splitext(basename)[0]
                if '::' in self.madeOf:
                    h5name = osp.splitext(osp.basename(
                        self.madeOf[:self.madeOf.find('::')]))[0]
                    tmpalias = '/'.join([h5name, tmpalias])

                if self.aliasExtra:
                    tmpalias += ': {0}'.format(self.aliasExtra)
                if self.suffix:
                    tmpalias += self.suffix

                # check duplicates:
                allLoadedItemNames = []
                for d in csi.allLoadedItems:
                    if d is self:
                        continue
                    lfn = d.madeOf[5:] if d.madeOf.startswith('silx:') else \
                        d.madeOf
                    lfns = osp.normcase(osp.abspath(lfn))
                    if d.madeOf.startswith('silx:'):
                        lfns = 'silx:' + lfns
                    allLoadedItemNames.append(lfns)
                allLoadedItemsCount = Counter(allLoadedItemNames)
                n = allLoadedItemsCount[osp.normcase(self.madeOf)]
                if n > 0:
                    tmpalias += " ({0})".format(n)
                self.alias = tmpalias

#        csi.undo.append([self, insertAt, lenData])

        # init self.transformParams:
        for tr in csi.transforms.values():
            self.transformParams.update(tr.defaultParams)
        if copyTransformParams:
            if len(csi.selectedItems) > 0:
                self.transformParams.update(
                    csi.selectedItems[0].transformParams)
            else:
                for tr in csi.transforms.values():
                    self.transformParams.update(tr.iniParams)
        self.transformParams.update(transformParams)

        if runDownstream:
            tr = self.originNode.transformsOut[0]
            tr.run(dataItems=[self])  # no need for multiprocessing here
            if csi.model is not None:
                csi.model.invalidateData()

    def check_shape(self):
        toNode = self.originNode
        for iarr, arrName in enumerate(toNode.checkShapes):
            pos = arrName.find('[')
            if pos > 0:
                stem = arrName[:pos]
                sl = arrName[pos+1:-1]
            else:
                stem = arrName
                sl = '0'
            checkName = toNode.getProp(stem, 'raw')
            arr = getattr(self, checkName)
            shape = arr.shape[eval(sl)]
            if iarr == 0:
                shape0 = shape
                continue
            if shape != shape0:
                return False
        return True

    def insert_item(self, name, insertAt=None, **kwargs):
        """This method searches for one ore more sequences in the elements of
        `dataSource` list. If found, these sequences should be of an equal
        length and the same number of spectra will be added to the data model
        in a separate group. If a shorter sequence is found, only its first
        element will be used for the expansion of this sequence to the length
        of the longest sequence(s)."""

        nameFull = None
        if 'configData' in kwargs:  # ini file
            configData = kwargs['configData']
            if name in configData:
                if 'dataFormat' in configData[name]:  # data entry
                    tmp = {entry: config.get(configData, name, entry)
                           for entry in self.configFieldsData}
                    if 'dataFormat_relative' in tmp:
                        tmp['dataFormat'] = tmp['dataFormat_relative']
                        del tmp['dataFormat_relative']
                    if tmp['originNode'] is not None:
                        tmp['originNode'] = csi.nodes[tmp['originNode']]
                    if tmp['terminalNode'] is not None:
                        tmp['terminalNode'] = csi.nodes[tmp['terminalNode']]
                    tmp['alias'] = name
                    trParams = {}
                    for tr in csi.transforms.values():
                        for key in tr.defaultParams:
                            trParams[key] = config.get(configData, name, key)
                    tmp['transformParams'] = trParams
                    name = tmp.pop('madeOf_relative')
                    nameFull = tmp.pop('madeOf')
                    kwargs = dict(tmp)
                elif 'colorPolicy' in configData[name]:  # group entry
                    tmp = {entry: config.get(configData, name, entry)
                           for entry in self.configFieldsGroup}
                else:
                    tmp = {}
            else:
                kwargs = {}
            kwargs['runDownstream'] = False
        elif 'configDict' in kwargs:
            configDict = kwargs['configDict']
            kwargs = dict(configDict[name]) if name in configDict else {}

        df = dict(kwargs.get('dataFormat', {}))
        if not df:  # is a group
            return Spectrum(name, self, insertAt, **kwargs)

        spectraInOneFile = 1
        dataSource = list(df.get('dataSource', []))
        dataSourceSplit = []
        for ds in dataSource:
            ds = str(ds)
            try:
                # to expand possible list comprehension or string expressions
                ds = str(eval(ds))
            except:  # noqa
                pass

            if ((ds.startswith('[') and ds.endswith(']')) or
                    (ds.startswith('(') and ds.endswith(')'))):
                ds = ds[1:-1]
            els = [el.strip() for el in ds.split(',')]
            dataSourceSplit.append(els)
            spectraInOneFile = max(spectraInOneFile, len(els))

        if spectraInOneFile == 1:
            try:
                return Spectrum(name, self, insertAt, **kwargs)
            except (FileNotFoundError, OSError) as e:
                print('local file {0} not found'.format(name))
                if nameFull is not None:
                    return Spectrum(nameFull, self, insertAt, **kwargs)
                else:
                    raise(e)

        basename = osp.basename(name)
        groupName = osp.splitext(basename)[0]
        group = Spectrum(groupName, self, insertAt, colorPolicy='loop1')

        multiDataSource = []
        for ids, ds in enumerate(dataSourceSplit):
            if len(ds) < spectraInOneFile:
                dataSourceSplit[ids] = [ds[0] for i in range(spectraInOneFile)]
            else:
                multiDataSource.append(ids)

        kwargs.pop('dataFormat', '')
        kwargs.pop('alias', '')
        for ds in zip(*dataSourceSplit):
            alias = '{0}_{1}'.format(
                groupName, '_'.join(ds[i] for i in multiDataSource))
            df['dataSource'] = list(ds)
            Spectrum(name, group, dataFormat=df, alias=alias, **kwargs)

        if csi.withGUI:
            group.init_colors(group.childItems)

        return group

    def read_file(self):
        madeOf = self.madeOf
        toNode = self.originNode
        df = dict(self.dataFormat)
        df.update(csi.extraDataFormat)

        if self.dataType == DATA_COLUMN_FILE:
            header = cco.get_header(madeOf, df)
        elif self.dataType == DATA_DATASET:
            header = []
            try:
                label = silx_io.get_data(madeOf + "/" + df["labelName"])
                self.aliasExtra = label.decode("utf-8")
                header.append(label)
            except (ValueError, KeyError):
                pass
            try:
                header.append(silx_io.get_data(madeOf + "/title"))
            except (ValueError, KeyError, OSError) as e:
                print(e)
                pass
            try:
                label = silx_io.get_data(madeOf + "/start_time")
                if isinstance(label, bytes):
                    header.append(b"start time " + label)
                else:
                    header.append("start time " + label)
                label = silx_io.get_data(madeOf + "/end_time")
                if isinstance(label, bytes):
                    header.append(b"end time " + label)
                else:
                    header.append("end time " + label)
            except (ValueError, KeyError, OSError) as e:
                print(e)
                pass
        else:
            raise TypeError('wrong datafile type')

        try:
            df['skip_header'] = df.pop('skiprows', 0)
            dataSource = df.pop('dataSource', None)
            sliceStrs = df.pop('slices', ['' for ds in dataSource])
            conversionFactors = df.pop('conversionFactors', [])
            if dataSource is None:
                raise ValueError('bad dataSource settings')
            if self.dataType == DATA_COLUMN_FILE:
                with np.warnings.catch_warnings():
                    np.warnings.simplefilter("ignore")
                    arrs = np.genfromtxt(madeOf, unpack=True, **df)
                if len(arrs) == 0:
                    raise ValueError('bad data file')

            for aName, txt, sliceStr in zip(
                    toNode.arrays, dataSource, sliceStrs):
                if self.dataType == DATA_COLUMN_FILE:
                    if isinstance(txt, int):
                        arr = arrs[txt]
                    else:
                        arr = self.interpretArrayFormula(txt, arrs)
                else:
                    arr = self.interpretArrayFormula(txt)
                    if sliceStr:
                        if 'axis' in sliceStr or 'sum' in sliceStr:  # sum axes
                            sumlst = sliceStr[sliceStr.find('=')+1:].split(',')
                            arr = arr.sum(axis=[int(ax) for ax in sumlst])
                        else:
                            sliceTuple = tuple(cco.parse_slice_str(slc)
                                               for slc in sliceStr.split(','))
                            arr = arr[sliceTuple]

                setName = toNode.getProp(aName, 'raw')
                try:
                    setattr(self, setName, arr)
                except Exception:
                    setattr(self, setName, None)

            self.state[toNode.name] = cco.DATA_STATE_GOOD
        except (ValueError, OSError, IndexError) as e:
            print(e)
            self.state[toNode.name] = cco.DATA_STATE_NOTFOUND
            return

        self.convert_units(conversionFactors)
        # define metadata
        if self.dataType == DATA_COLUMN_FILE:
            self.meta['text'] = r''.join(header)
            self.meta['modified'] = time.strftime(
                "%a, %d %b %Y %H:%M:%S", time.gmtime(osp.getmtime(madeOf)))
            self.meta['size'] = osp.getsize(madeOf)
        else:
            if len(header) > 0:
                if isinstance(header[0], bytes):
                    self.meta['text'] = '\n'.join(
                        h.decode("utf-8") for h in header)
                else:
                    self.meta['text'] = '\n'.join(header)
        self.meta['length'] = len(arr)

        config.put(config.configDirs, 'Load', toNode.name, madeOf)

    def interpretArrayFormula(self, colStr, treeObj=None):
        try:
            # to expand string expressions
            colStr = str(eval(colStr))
        except:  # noqa
            pass

        keys = re.findall(r'\[(.*?)\]', colStr)
        if len(keys) == 0:
            keys = [colStr]
            colStr = 'd[r"{0}"]'.format(colStr)
        else:
            # remove outer quotes:
            keys = [k[1:-1] if k.startswith(('"', "'")) else k for k in keys]
        d = {}
        if treeObj is None:  # is Hdf5Item
            for k in keys:
                if k.startswith("silx:"):
                    d[k] = silx_io.get_data(k)
                    config.put(config.configDirs, 'Load',
                               self.originNode.name+'_silx', k)
                else:
                    d[k] = silx_io.get_data('/'.join((self.madeOf, k)))
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
        return eval(colStr)

    def convert_units(self, conversionFactors):
        if not conversionFactors:
            return
        toNode = self.originNode
        for aName, cFactor in zip(toNode.arrays, conversionFactors):
            if not cFactor or isinstance(cFactor, type("")):
                continue
            setName = toNode.getProp(aName, 'raw')
            try:
                arr = getattr(self, setName)
                arr *= cFactor
                self.hasChanged = True
            except Exception as e:
                print(e)
                setattr(self, setName, None)

    def calc_combined(self):
        """Case of *madeOf* as list of Spectrum instances. self.dataFormat is
        the type of the combination being made: one of COMBINE_XXX constants.
        """
        madeOf = self.madeOf
        what = self.dataFormat['combine']
        # define metadata
        self.meta['text'] = '{0} of {1}'.format(
            combineNames[what], ', '.join(it.alias for it in madeOf))
#        self.meta['modified'] = osp.getmtime(madeOf)
        self.meta['modified'] = time.strftime("%a, %d %b %Y %H:%M:%S")
        self.meta['size'] = -1

        try:
            assert isinstance(madeOf, (list, tuple))
            toNode = self.originNode

            xNames = []
            # check equal length of data to combine:
            len0 = 0
            for arrayName in toNode.arrays:
                if toNode.getProp(arrayName, 'role').startswith('x'):
                    xNames.append(arrayName)
                setName = toNode.getProp(arrayName, 'raw')
                for data in madeOf:
                    lenN = len(getattr(data, setName))
                    if len0 == 0:
                        len0 = lenN
                    else:
                        assert len0 == lenN

            for data in madeOf:
                if self not in data.combinesTo:
                    data.combinesTo.append(self)

            # x is so far taken from the 1st spectrum:  # TODO
            for arrayName in xNames:
                setName = toNode.getProp(arrayName, 'raw')
                arr = np.array(getattr(madeOf[0], setName))
                setattr(self, setName, arr)

            lenC = len(madeOf)
            for arrayName in toNode.arrays:
                if arrayName in xNames:
                    continue
                if what in (COMBINE_AVE, COMBINE_SUM, COMBINE_RMS):
                    s = sum(getattr(data, arrayName) for data in madeOf)
                    if what == COMBINE_AVE:
                        v = s / lenC
                    elif what == COMBINE_SUM:
                        v = s
                    elif what == COMBINE_RMS:
                        s2 = sum((getattr(d, arrayName) - s/lenC)**2
                                 for d in madeOf)
                        v = (s2 / lenC)**0.5
                elif what == COMBINE_PCA:
                    raise NotImplementedError  # TODO
                else:
                    raise ValueError("unknown data combination")
                setattr(self, arrayName, v)

            self.meta['length'] = len(v)
            self.state[toNode.name] = cco.DATA_STATE_GOOD
        except AssertionError:
            self.state[toNode.name] = cco.DATA_STATE_MATHERROR
            self.meta['text'] += '\nThe conbined arrays have different lengths'

    def create_data(self):
        """Case of *madeOf* as callable"""
        toNode = self.originNode
        try:
            res = self.madeOf(**self.dataFormat)
            for arrayName, arr in zip(toNode.arrays, res):
                setName = toNode.getProp(arrayName, 'raw')
                setattr(self, setName, arr)
            self.state[toNode.name] = cco.DATA_STATE_GOOD
        except Exception:
            self.state[toNode.name] = cco.DATA_STATE_BAD

    def save_transform_params(self):
        dtparams = self.transformParams
        for tr in csi.transforms.values():
            for key in tr.defaultParams:
                if isinstance(dtparams[key], np.ndarray):
                    toSave = dtparams[key].tolist()
                else:
                    toSave = dtparams[key]
                config.put(config.configTransforms, tr.name, key, str(toSave))

    def save_to_project(self, configProject, dirname):
        from ..gui import gcommons as gco  # only needed with gui
        item = self
        if item.dataFormat:
            config.put(configProject, item.alias, 'madeOf', item.madeOf)

            start = 5 if item.madeOf.startswith('silx:') else 0
            end = item.madeOf.find('::') if '::' in item.madeOf else None
            path = item.madeOf[start:end]
            madeOfRel = \
                item.madeOf[:start] + osp.relpath(path, dirname) +\
                item.madeOf[end:]
            config.put(configProject, item.alias, 'madeOf_relative', madeOfRel)

            dataFormat = json.dumps(item.dataFormat)
            config.put(configProject, item.alias, 'dataFormat', dataFormat)

            dataSource = list(item.dataFormat.get('dataSource', []))
            for ds in dataSource:
                if 'silx:' in ds:
                    needRelative = True
                    break
            else:
                needRelative = False
            if needRelative:
                dataFormatRel = copy.deepcopy(item.dataFormat)
                dataSourceRel = dataFormatRel['dataSource']
                for ids, ds in enumerate(dataSourceRel):
                    if 'silx:' in ds:
                        start = 5
                        end = ds.find('::') if '::' in ds else None
                        path = ds[start:end]
                        madeOfRel = ds[:start] + \
                            osp.relpath(path, dirname) + ds[end:]
                        dataSourceRel[ids] = madeOfRel
                dataFormat = json.dumps(dataFormatRel)
                config.put(
                    configProject, item.alias, 'dataFormat_relative',
                    dataFormat)

            config.put(configProject, item.alias, 'suffix', str(item.suffix))
            config.put(
                configProject, item.alias, 'originNode',
                item.originNode.name if item.originNode else 'None')
            config.put(
                configProject, item.alias, 'terminalNode',
                item.terminalNode.name if item.terminalNode else 'None')
            config.put(
                configProject, item.alias, 'colorTag', str(item.colorTag))
            config.put(configProject, item.alias, 'color', str(item.color))

            configProject.set(
                item.alias, ';transform params:')  # ';'=comment out
            dtparams = item.transformParams
            for key in dtparams:
                if isinstance(dtparams[key], np.ndarray):
                    toSave = dtparams[key].tolist()
                else:
                    toSave = dtparams[key]
                config.put(configProject, item.alias, key, str(toSave))
        else:  # i.e. is a group
            config.put(
                configProject, item.alias, 'colorPolicy',
                gco.COLOR_POLICY_NAMES[item.colorPolicy])
            if item.colorPolicy == gco.COLOR_POLICY_GRADIENT:
                config.put(
                    configProject, item.alias, 'color1', str(item.color1))
                config.put(
                    configProject, item.alias, 'color2', str(item.color2))
            elif item.colorPolicy == gco.COLOR_POLICY_INDIVIDUAL:
                config.put(configProject, item.alias, 'color', str(item.color))
            config.put(
                configProject, item.alias, 'colorTag', str(item.colorTag))
            config.put(
                configProject, item.alias, 'colorAutoUpdate',
                str(item.colorAutoUpdate))
