# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import os
import time
import numpy as np

from . import singletons as csi
from .commons import common_substring

MAX_HEADER_LINES = 256
COMBINE_NONE, COMBINE_AVE, COMBINE_SUM, COMBINE_PCA, COMBINE_RMS = range(5)
combineName = '', 'ave', 'sum', 'PCA', 'RMS'

colorCycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
              '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
colorCycle2 = ['#0000ff', '#00ee00', '#ff0000', '#00ffff', '#ff00ff',
               '#ffff00', '#000000']


class TreeItem(object):
    def __init__(self, name, parentItem=None, insertAt=None, **kwargs):
        alias = kwargs.get('alias', 'auto')
        if '?' in name and alias == 'auto':  # string with name and alias
            self.name, self.alias = name.split('?')[:2]
        else:
            self.name = name
            if alias == 'auto':
                base = os.path.basename(name)
                self.alias = os.path.splitext(base)[0]
            else:
                self.alias = alias
        self.childItems = []
        self.isExpanded = True
        self.colorTag = 0
        self.isVisible = True
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

    def tooltip(self):
        if self.childItems:
            items = self.get_items()
            if self.has_groups():
                childCount = self.child_count()
                tip = "{0} top item{1} with {2} spectr{3}".format(
                    childCount, 's' if childCount > 1 else '',
                    len(items), 'a' if len(items) > 1 else 'um')
            else:
                tip = "{0} spectr{1}".format(
                    len(items), 'a' if len(items) > 1 else 'um')
            return tip
        else:
            if hasattr(self, 'name'):
                if isinstance(self.name, type("")):
                    return self.name
            elif hasattr(self, 'madeOf'):
                if isinstance(self.madeOf, type("")):
                    return self.madeOf

    def data(self, column):
        leadingColumns = len(csi.modelLeadingColumns)
        if column < leadingColumns:
            if column == 0:
                return self.alias
        elif 0 <= column-leadingColumns < len(csi.modelDataColumns):
            if not hasattr(self, 'plotProps'):
                return len(self.get_items())
            node, yName = csi.modelDataColumns[column-leadingColumns]
            return self.color, self.plotProps[node.name][yName]
        else:
            raise ValueError("invalid column")

    def is_good(self, column):
        return True

    def set_data(self, column, value):
        if column == 0:
            self.alias = value
        else:
            raise ValueError("invalid column")

    def set_visible(self, value):
        self.isVisible = bool(value)
        for item in self.get_items(True):
            item.isVisible = bool(value)

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

    def insert_item(self, name, insertAt=None, **kwargs):
        return TreeItem(name, self, insertAt, **kwargs)

    def delete(self):
        parentItem = self.parentItem
        try:
            parentItem.childItems.remove(self)
            if parentItem.child_count() == 0:
                parentItem.delete()
        except (AttributeError, ValueError):
            pass

    def insert_data(self, data, insertAt=None, **kwargs):
        items = []
        if isinstance(data, type("")):
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
                    subItems = si.insert_data(subdata, **kwargs)  # no insertAt
                else:
                    raise ValueError(
                        "data in '{0}' must be a sequence or a string, not {1}"
                        " of type {2}".format(
                            self.alias, subdata, type(subdata)))
                items += [it for it in subItems if it not in items]
        else:
            raise ValueError(
                "data in {0} must be a sequence or a string, not {1}"
                " of type {2}".format(self.alias, data, type(data)))
#        csi.recentlyLoadedItems.clear()
        csi.recentlyLoadedItems[:] = []
        csi.recentlyLoadedItems.extend(items)
        return items


class Spectrum(TreeItem):
    def __init__(self, madeOf, parentItem=None, insertAt=None, **kwargs):
        """ *madeOf* is either a file name, a callable or a list of other
        Spectrum instances.

        *insertAt* is the position in parentItem.childItems list. If None, the
        spectrum is appended.

        *kwargs* defaults to the dictionary:
        dict(alias='auto', dataFormat={}, originNode=None, terminalNode=None)
        *dataFormat* is assumed to be empty for a data group and non-empty for
        a spectrum.

        The data propagation is between *originNode* and *terminalNode*, both
        ends are included. If *originNode* is None, it defaults to the 0th node
        (head of the pipeline). If *terminalNode* is None, the data propagates
        down to the end(s) of the pipeline.

        If a node is between *originNode* and *terminalNode* (in the sense of
        data propagation) then the data is present in the node's data manager
        as *alias* and is displayed in the plot.


        """
        assert len(csi.nodes) > 0, "A data pipeline must be first created."
        self.madeOf = madeOf
        self.parentItem = parentItem
        self.childItems = []
        self.isVisible = True
        if parentItem is None:
            assert csi.dataRootItem is None, "Data tree already exists."
            csi.dataRootItem = self
            return

        self.alias = kwargs.get('alias', 'auto')
        self.dataFormat = dict(kwargs.get('dataFormat', {}))
        originNode = kwargs.get('originNode', None)
        if originNode is None:
            originNode = list(csi.nodes.values())[0]
        self.originNode = originNode
        self.terminalNode = kwargs.get('terminalNode', None)

        self.isExpanded = True
        self.colorTag = kwargs.get('colorTag', 0)
        self.hasChanged = False
        self.isGood = dict((node.name, False) for node in csi.nodes.values())
        self.meta = {}
        self.combinesTo = []  # list of instances of Spectrum if not empty
        self.transformParams = {}  # each transform will add dicts to this dict

        if insertAt is None:
            parentItem.childItems.append(self)
        else:
            parentItem.childItems.insert(insertAt, self)

        if self.dataFormat:
            self.read_data()
            if csi.withGUI:
                self.init_plot_props()
        else:  # i.e. is a group
            self.dataType = 'group'
            if self.alias == 'auto':
                self.alias = madeOf

    def is_good(self, column):
        leadingColumns = len(csi.modelLeadingColumns)
        if column < leadingColumns:
            return True
        node = csi.modelDataColumns[column-leadingColumns][0]
        return self.isGood[node.name]

    def read_data(self, shouldLoadNow=True, runDownstream=True):
        if callable(self.madeOf):
            self.dataType = 'function'
            if shouldLoadNow:
                self.create_data()
            if self.alias == 'auto':
                self.alias = "generated_{0}".format(self.madeOf.__name__)
        elif isinstance(self.madeOf, (list, tuple)):
            self.dataType = 'combination'
            if shouldLoadNow:
                self.calc_combined()
            if self.alias == 'auto':
                cs = self.madeOf[0].alias
                for data in self.madeOf[1:]:
                    cs = common_substring(cs, data.alias)
                what = self.dataFormat['combine']
                lenC = len(self.madeOf)
                self.alias = "{0}_{1}{2}".format(cs, combineName[what], lenC)
        else:
            if self.madeOf.endswith(('.hdf5', '.h5', '.nxs')):
                self.dataType = 'hdf5 file'
                if shouldLoadNow:
                    self.read_hdf5_file()
            else:
                self.dataType = 'column file'
                if shouldLoadNow:
                    self.read_column_file()

            basename = os.path.basename(self.madeOf)
            if self.alias == 'auto':
                self.alias = os.path.splitext(basename)[0]

#        csi.undo.append([self, insertAt, lenData])

        # init self.transformParams:
        for tr in csi.transforms.values():
            if tr.name not in self.transformParams:
                self.transformParams[tr.name] = tr.params.copy()

        if runDownstream:
            for tr in self.originNode.transformsOut:
                tr.run(dataItems=[self])

    def init_plot_props(self):
        row = self.row()
        if row is None:
            row = 0
        self.color = colorCycle[row % len(colorCycle)] if self.colorTag == 0\
            else colorCycle2[row % len(colorCycle2)]
        self.plotProps = {}
        for node in csi.nodes.values():
            self.plotProps[node.name] = {}
            for ind, yName in enumerate(node.yNames):
                plotParams = {'symbolsize': 2}
                for k, v in node.plotParams.items():
                    if isinstance(v, (list, tuple)):
                        pv = v[ind]
                    else:
                        pv = v
                    plotParams[k] = pv
                self.plotProps[node.name][yName] = plotParams

    def insert_item(self, name, insertAt=None, **kwargs):
        return Spectrum(name, self, insertAt, **kwargs)

    def read_hdf5_file(self):
        raise

    def read_column_file(self):
        madeOf = self.madeOf
        toNode = self.originNode
        readkwargs = dict(self.dataFormat)

        # define header
        skipUntil = readkwargs.pop('lastSkipRowContains', '')
        headerLen = -1
        if 'skiprows' not in readkwargs:
            if skipUntil:
                with open(madeOf, 'r') as f:
                    for il, line in enumerate(f):
                        if skipUntil in line:
                            headerLen = il
                        if il == MAX_HEADER_LINES:
                            break
                if headerLen >= 0:
                    readkwargs['skiprows'] = headerLen + 1
        else:
            headerLen = readkwargs['skiprows']
        header = []
        with open(madeOf, 'r') as f:
            for il, line in enumerate(f):
                if il == MAX_HEADER_LINES:
                    break
                if ((headerLen >= 0) and (il <= headerLen)) or \
                        line.startswith('#'):
                    header.append(line)

        xF = readkwargs.pop('xFactor') if 'xFactor' in readkwargs else None

        # read data
        try:
            arr = np.loadtxt(madeOf, unpack=True, **readkwargs)
            self.isGood[toNode.name] = True
        except:
            self.isGood[toNode.name] = False
            csi.model.invalidateData()
            return

        if hasattr(toNode, 'xNameRaw'):
            setattr(self, toNode.xNameRaw, arr[0])
        else:
            setattr(self, toNode.xName, arr[0])
        if xF is not None:
            x = getattr(self, toNode.xName)
            x *= xF

        if hasattr(toNode, 'yNamesRaw'):
            yNames = toNode.yNamesRaw
        else:
            yNames = toNode.yNames
        for iy, yName in enumerate(yNames):
            try:
                setattr(self, yName, arr[iy+1])
            except IndexError:
                setattr(self, yName, None)

        # define metadata
        self.meta['text'] = ''.join(header)
#        self.meta['modified'] = os.path.getmtime(madeOf)
        self.meta['modified'] = time.strftime(
            "%a, %d %b %Y %H:%M:%S", time.gmtime(os.path.getmtime(madeOf)))
        self.meta['size'] = os.path.getsize(madeOf)
        self.meta['length'] = len(arr[0])

    def calc_combined(self):
        """Case of *madeOf* as list of Spectrum instances. self.dataFormat is
        the type of the combination being made: one of COMBINE_XXX constants.
        """
        madeOf = self.madeOf
        assert isinstance(madeOf, (list, tuple))
        toNode = self.originNode
        what = self.dataFormat['combine']

        # check equal length of data to combine:
        len0 = 0
        for data in madeOf:
            lenN = len(getattr(data, toNode.xName))
            if len0 == 0:
                len0 = lenN
            else:
                assert len0 == lenN
            for yName in toNode.yNames:
                assert len0 == len(getattr(data, yName))

        for data in madeOf:
            if self not in data.combinesTo:
                data.combinesTo.append(self)

        # x is so far taken from the 1st spectrum:  # TODO
        setattr(self, toNode.xName, np.array(getattr(madeOf[0], toNode.xName)))

        lenC = len(madeOf)
        for yName in toNode.yNames:
            if what in (COMBINE_AVE, COMBINE_SUM, COMBINE_RMS):
                s = sum(getattr(data, yName) for data in madeOf)
                if what == COMBINE_AVE:
                    v = s / lenC
                elif what == COMBINE_SUM:
                    v = s
                elif what == COMBINE_RMS:
                    s2 = sum((getattr(d, yName) - s/lenC)**2 for d in madeOf)
                    v = (s2 / lenC)**0.5
            elif what == COMBINE_PCA:
                raise NotImplementedError  # TODO
            else:
                raise ValueError("unknown data combination")
            setattr(self, yName, v)

        self.isGood[toNode.name] = True
        # define metadata
        self.meta['text'] = '{0} of {1}'.format(
            combineName[what], ', '.join([it.alias for it in madeOf]))
#        self.meta['modified'] = os.path.getmtime(madeOf)
        self.meta['modified'] = time.strftime("%a, %d %b %Y %H:%M:%S")
        self.meta['size'] = -1
        self.meta['length'] = len(v)

    def create_data(self):
        """Case of *madeOf* as callable"""
        toNode = self.originNode
        res = self.madeOf(**self.dataFormat)
        setattr(self, toNode.xName, res[0])
        for iy, yName in enumerate(toNode.yNames):
            try:
                setattr(self, yName, res[iy+1])
            except IndexError:
                setattr(self, yName, None)
        self.isGood[toNode.name] = True

#    def set_transform_param(self, transformName, key, val):
#        tr = csi.transforms[transformName]
#        if tr.fromNode.is_between_nodes(
#                self.originNode, self.terminalNode,
#                node1in=True, node2in=False):
#            self.transformParams[transformName][key] = val
