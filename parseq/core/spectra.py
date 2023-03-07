# -*- coding: utf-8 -*-
u"""
Data model
----------

The ParSeq data model is a hierarchical tree model, where each element has zero
or more children. If an element has zero children, it is called item and is a
data container. If an element has at least one child, it is called group. All
items and groups are instances of :class:`Spectrum`.

The tree model can be manipulated in a script, and the following reference
documentation explains how. Otherwise, most typically it is used within the
ParSeq GUI, where the tree model feeds the `model-view-controller
<https://doc.qt.io/qt-6/model-view-programming.html>`_ software architecture of
Qt, where the user does not have to know about the underlying objects and
methods. See :ref:`Notes on usage of GUI <notesgui>`.
"""
__author__ = "Konstantin Klementiev"
__date__ = "3 Mar 2023"
# !!! SEE CODERULES.TXT !!!

# import sys
import os.path as osp
import re
import time
import copy
import json
import numpy as np
import warnings
from collections import Counter

import silx.io as silx_io

from . import singletons as csi
from . import commons as cco
from . import config
from .logger import logger
from ..utils.format import format_memory_size

DEFAULT_COLOR_AUTO_UPDATE = False


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

    def _child_items_repr(self):
        return '[' + ', '.join(repr(it) for it in self.childItems) + ']'

    def __repr__(self):
        if self.parentItem is None:
            return self._child_items_repr()
        if self.childItems:
            return "'{0}', {1}".format(self.alias, self._child_items_repr())
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
            if hasattr(self, 'name'):  # instance of TreeItem
                if isinstance(self.name, type("")):
                    res = self.name
            elif hasattr(self, 'madeOf'):  # instance of Spectrum
                if self.error is not None:
                    return self.error
                elif self.beingTransformed:
                    return '{0} is {1:.0f}% done'.format(
                        self.beingTransformed, self.progress*100)
                elif isinstance(self.madeOf, (type(""), dict, tuple, list)):
                    if isinstance(self.madeOf, type("")):
                        res = str(self.madeOf)
                    elif isinstance(self.madeOf, (tuple, list)):
                        what = self.dataFormat['combine']
                        if type(self.madeOf[0]) is str:
                            names = self.madeOf
                        else:
                            names = [it.alias for it in self.madeOf]
                        cNames = cco.combine_names(names)
                        res = '{0} of [{1}]'.format(
                            cco.combineNames[what], cNames)
                        # res = self.meta['shortText']
                    else:
                        res = ""
                    if self.aliasExtra:
                        res += ': {0}'.format(self.aliasExtra)
                    dataSource = self.dataFormat.get('dataSource', [])
                    for ds in dataSource:
                        if isinstance(ds, type("")):
                            if ds.startswith('silx'):
                                if res:
                                    res += '\n'
                                res += ds
                    if csi.currentNode is not None:
                        node = csi.currentNode
                        if self.state[node.name] == cco.DATA_STATE_NOTFOUND:
                            if res:
                                res += '\n'
                            res += 'data not found!'
                        elif self.state[node.name] == cco.DATA_STATE_BAD:
                            if res:
                                res += '\n'
                            res += 'incompatible data shapes!'
                        elif self.state[node.name] == cco.DATA_STATE_GOOD:
                            try:
                                if self.terminalNodeName is not None:
                                    res += \
                                        '\nthis data terminates at node "{0}"'\
                                        .format(self.terminalNodeName)
                                if node.plotDimension == 1:
                                    arr = getattr(self, node.plotXArray)
                                    sh = arr.shape[0]
                                    whatSize = 'size of one 1D array'
                                elif node.plotDimension == 2:
                                    arr = getattr(self, node.plot2DArray)
                                    sh = arr.shape
                                    whatSize = 'size of 2D array'
                                elif node.plotDimension == 3:
                                    arr = getattr(self, node.plot3DArray)
                                    sh = arr.shape
                                    whatSize = 'size of 3D array'
                                else:
                                    arr = None
                                    sh = None
                                    whatSize = 'size'
                                if sh:
                                    nl = '\n' if res else ''
                                    what = 'shape' if node.plotDimension > 1\
                                        else 'length'
                                    res += nl + '{0}: {1}'.format(what, sh)
                                    size = arr.nbytes
                                    res += '\n{0}: {1}'.format(
                                        whatSize, format_memory_size(size))
                                for tr in node.transformsIn:
                                    if tr.name not in self.transfortmTimes:
                                        continue
                                    tt = self.transfortmTimes[tr.name]
                                    factor, unit, ff = \
                                        (1e3, 'ms', '{1:.0f}') if tt < 1\
                                        else (1, 's', '{1:.1f}')
                                    ss = '\nmade by "{0}" in ' + ff + ' {2}'
                                    res += ss.format(tr.name, tt*factor, unit)
                            except Exception as e:
                                res += '\n' + str(e)
                        elif self.state[node.name] == cco.DATA_STATE_UNDEFINED:
                            if self.originNodeName is not None or \
                                    self.terminalNodeName is not None:
                                if self.originNodeName is not None:
                                    if res:
                                        res += '\n'
                                    res += 'This data starts at node "{0}"'\
                                        .format(self.originNodeName)
                                if self.terminalNodeName is not None:
                                    if res:
                                        res += '\n'
                                    res += 'This data finishes at node "{0}"'\
                                        .format(self.terminalNodeName)
                            else:
                                res += 'This node is out of the pipeline'\
                                    ' for this data'
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
            role = node.get_prop(key, 'role')
            if role.startswith('0'):
                try:
                    res = getattr(self, key)
                except AttributeError:
                    return "---"
                if res is None:
                    return "---"
                formatStr = node.get_prop(key, 'plotLabel')
                if '{' not in formatStr:
                    formatStr = '{0}'
                return formatStr.format(res)
            try:
                return self.color, self.plotProps[node.name][key]
            except KeyError:
                return "---"
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
        u"""Finds the first data item with a given alias. Returns None if
        fails."""
        if alias is None:
            return
        for item in self.get_items():
            if item.alias == alias:
                return item

    def get_top(self):
        return csi.dataRootItem

    def get_items(self, alsoGroupHeads=False):
        u"""Returns a list of all items in a given group, also included in all
        subgroups."""

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

    def remove_from_parent(self):
        try:
            self.parentItem.childItems.remove(self)
        except (AttributeError, ValueError):
            pass

    def insert_item(self, name, insertAt=None, **kwargs):
        return TreeItem(name, self, insertAt, **kwargs)

    def insert_data(self, data, insertAt=None, **kwargs):
        items = []
        if hasattr(self, 'alias'):
            alias = self.alias
        elif hasattr(self, 'madeOf'):
            alias = self.madeOf
        elif hasattr(self, 'name'):
            alias = self.name

        if isinstance(data, str):
            item = self.insert_item(data, insertAt, **kwargs)
            if item not in items:  # inclusion check that keeps the order
                items.append(item)
        elif isinstance(data, (list, tuple)):
            si = self
            for subdata in data:
                if isinstance(subdata, str):
                    si = self.insert_item(subdata, insertAt, **kwargs)
                    subItems = [si]
                elif isinstance(subdata, (list, tuple)):
                    if si in items:
                        items.remove(si)
                    subItems = si.insert_data(subdata, **kwargs)  # no insertAt
                else:
                    raise ValueError(
                        "data in '{0}' must be a sequence or a string, not {1}"
                        " of type {2}".format(alias, subdata, type(subdata)))
                items += [it for it in subItems if it not in items]
        else:
            raise ValueError(
                "data in {0} must be a sequence or a string, not {1}"
                " of type {2}".format(alias, data, type(data)))

        csi.recentlyLoadedItems = list(items)
        csi.allLoadedItems[:] = []
        csi.allLoadedItems.extend(csi.dataRootItem.get_items())
        if len(csi.selectedItems) == 0:
            if len(csi.allLoadedItems) == 0:
                raise ValueError("No valid data added")
        csi.selectedItems = list(items)
        csi.selectedTopItems = list(items)

        shouldMakeColor = len(self.childItems) > 0 and csi.withGUI
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
    u"""
    This class is the main building block of the ParSeq data model and is
    either a group that contains other instances of :class:`Spectrum` or an
    item (data container). All elements, except the root, have a parent
    referred to by `parentItem` field, and parents have their children in a
    list `childItems`. Only the root item is explicitly created by the
    constructor of :class:`Spectrum`, and this is done in the module that
    defines the pipeline. All other tree elements are typically created by the
    parent’s :meth:`insert_data` or :meth:`insert_item` methods.
    """

    configFieldsData = (  # to parse ini file section of data
        'madeOf', 'madeOf_relative', 'dataFormat', 'dataFormat_relative',
        'suffix', 'originNodeName', 'terminalNodeName', 'transformNames',
        'colorTag', 'color')
    configFieldsCombined = (  # to parse ini file section of combined data
        'madeOf', 'dataFormat',
        'suffix', 'originNodeName', 'terminalNodeName', 'transformNames',
        'colorTag', 'color')
    configFieldsGroup = (  # to parse ini file section of group
         'colorPolicy', 'colorTag', 'colorAutoUpdate')

    def __init__(self, madeOf, parentItem=None, insertAt=None, **kwargs):
        u"""
        *madeOf*
            is either a file name, a callable, a list of other
            :class:`Spectrum` instances (for making a combination) or a
            dictionary (for creating branches).

        *parentItem*
            is another :class:`Spectrum` instance or None (for the tree root).

        *insertAt*: int
            the position in `parentItem.childItems` list. If None, the spectrum
            is appended.

        *kwargs*: dict
            defaults to the dictionary: dict(alias='auto', dataFormat={},
            originNodeName=None, terminalNodeName=None, transformNames='each',
            copyTransformParams=True). The default *kwargs* can be changed in
            `parseq.core.singletons.dataRootItem.kwargs`, where `dataRootItem`
            is the root item of the data model that gets instantiated in the
            module that defines the pipeline.

            *dataFormat*: dict
                is assumed to be an empty dict for a data group and must be
                non-empty for a data item. As a minimum, it defines the key
                `dataSource` and sets it to a list of hdf5 names (when for
                hdf5 data), column numbers or expressions of 'Col1', 'Col2'
                etc variables (when for column data). It may define
                'conversionFactors' as a list of either floats or strings;
                a float is a multiplicative factor that converts to the node's
                array unit and a string is another unit that cannot be
                converted to the node's array unit, e.g. the node defines an
                array with a 'mA' unit while the data was measured with a
                'count' unit. It may define 'metadata': a comma separated str
                of hdf5 attribute names that define metadata.

            *originNodeName*, *terminalNodeName*: str
                The data propagation is between origin node and terminal node,
                both ends are included. If undefined, they default to the 0th
                node (the head of the pipeline) and the open end(s). If a node
                is between the origin node and the terminal node (in the data
                propagation sense) then the data is present in the node's data
                tree view as *alias* and is displayed in the plot.

            *transformNames*
                A list of transform names (or a single str 'each'). It defines
                whether a particular transform should be run for this data.

            *copyTransformParams*: bool, default True.
                Controls the way the *transformParams* of the Spectrum are
                initialized: If False, they are copied from *defaultParams* of
                all transforms. If True, they are copied from the first
                selected spectrum when at least one is selected or otherwise
                from the ini file.
        """

        assert len(csi.nodes) > 0, "A data pipeline must be first created."
        self.madeOf = madeOf
        self.parentItem = parentItem
        self.childItems = []
        self.branch = None  # can be a group of branched out items
        self.error = None  # if a transform fails, contains traceback
        self.transfortmTimes = {}
        self.progress = 1.
        self.isVisible = True
        self.beingTransformed = False
        if parentItem is None:  # i.e. self is the root item
            assert csi.dataRootItem is None, "Data tree already exists."
            csi.dataRootItem = self
            if csi.withGUI:
                from ..gui import gcommons as gco
                self.colorPolicy = gco.COLOR_POLICY_LOOP1
                self.colorAutoUpdate = DEFAULT_COLOR_AUTO_UPDATE
            self.kwargs = dict(
                alias='auto', dataFormat={}, originNodeName=None,
                terminalNodeName=None, transformNames='each',
                copyTransformParams=True)
            return

        originNodeName = kwargs.get(
            'originNodeName', csi.dataRootItem.kwargs['originNodeName'])
        if originNodeName is None:
            originNodeName = list(csi.nodes.keys())[0]
        else:
            assert originNodeName in csi.nodes
        self.originNodeName = originNodeName

        terminalNodeName = kwargs.get(
            'terminalNodeName', csi.dataRootItem.kwargs['terminalNodeName'])
        if terminalNodeName is not None:
            assert terminalNodeName in csi.nodes
        self.terminalNodeName = terminalNodeName

        self.transformNames = kwargs.get(
            'transformNames', csi.dataRootItem.kwargs['transformNames'])
        if self.transformNames is None:
            self.transformNames = 'each'

        self.alias = kwargs.get('alias',
                                csi.dataRootItem.kwargs['alias'])
        self.suffix = kwargs.get('suffix',
                                 csi.dataRootItem.kwargs.get('suffix', None))
        self.dataFormat = copy.deepcopy(
            kwargs.get('dataFormat', csi.dataRootItem.kwargs['dataFormat']))
        # make forward slashes in file names:
        if self.dataFormat:
            if 'dataSource' in self.dataFormat:
                self.dataFormat['dataSource'] = [
                    ds.replace('\\', '/') if isinstance(ds, str) else ds for
                    ds in self.dataFormat['dataSource']]
        self.isExpanded = True
        self.colorTag = kwargs.get('colorTag',
                                   csi.dataRootItem.kwargs.get('colorTag', 0))
        if 'colorIndividual' in kwargs:
            self.colorIndividual = kwargs['colorIndividual']

        self.hasChanged = False
        self.state = dict((nn, cco.DATA_STATE_UNDEFINED) for nn in csi.nodes)
        self.aliasExtra = None  # for extra name qualifier
        self.meta = {'text': '', 'modified': '', 'size': 0}
        self.combinesTo = []  # list of instances of Spectrum if not empty

        self.transformParams = {}  # each transform will add to this dict
        # init self.transformParams:
        for tr in csi.transforms.values():
            self.transformParams.update(tr.defaultParams)

        if insertAt is None:
            parentItem.childItems.append(self)
        else:
            parentItem.childItems.insert(insertAt, self)

        if ((isinstance(self.madeOf, str) and self.dataFormat) or
                isinstance(self.madeOf, (list, tuple, dict))):
            copyTransformParams = kwargs.pop(
                'copyTransformParams',
                csi.dataRootItem.kwargs['copyTransformParams'])
            transformParams = kwargs.pop(
                'transformParams',
                csi.dataRootItem.kwargs.get('transformParams', {}))
            shouldLoadNow = kwargs.pop(
                'shouldLoadNow',
                csi.dataRootItem.kwargs.get('shouldLoadNow', True))
            runDownstream = kwargs.pop(
                'runDownstream',
                csi.dataRootItem.kwargs.get('runDownstream', False))
            if csi.withGUI:
                self.init_plot_props()
                plotProps = kwargs.pop('plotProps', {})
                if plotProps:
                    self.plotProps.update(plotProps)

            self.read_data(shouldLoadNow=shouldLoadNow,
                           runDownstream=runDownstream,
                           copyTransformParams=copyTransformParams,
                           transformParams=transformParams)

        elif isinstance(self.madeOf, str) and not self.dataFormat:
            # i.e. is a group
            self.dataType = cco.DATA_GROUP
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
                self.alias = str(madeOf)
        else:
            raise ValueError('unknown data type of {0}'.format(self.alias))

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
                    plotParams = {}
                    plotParams['yaxis'] = \
                        'right' if node.get_prop(yName, 'role').endswith(
                            'right') else 'left'
                    nodePlotParams = node.get_prop(yName, 'plotParams')
                    for k, v in nodePlotParams.items():
                        if isinstance(v, (list, tuple)):
                            pv = v[ind]
                        else:
                            pv = v
                        plotParams[k] = pv
                    self.plotProps[node.name][yName] = plotParams

    def get_state(self, nodeName):
        return self.state[nodeName]

    def read_data(self, shouldLoadNow=True, runDownstream=False,
                  copyTransformParams=True, transformParams={}):
        toNode = csi.nodes[self.originNodeName]
        if isinstance(self.madeOf, dict):
            self.dataType = cco.DATA_BRANCH
            if self.alias == 'auto':
                tmpalias = '{0}_{1}'.format(
                    self.parentItem.alias, self.parentItem.child_count())
            if shouldLoadNow:
                self.branch_data()
        elif callable(self.madeOf):
            self.dataType = cco.DATA_FUNCTION
            if self.alias == 'auto':
                tmpalias = "generated_{0}".format(self.madeOf.__name__)
            if shouldLoadNow:
                self.create_data()
        elif isinstance(self.madeOf, (list, tuple)):
            self.dataType = cco.DATA_COMBINATION
            self.colorTag = 5
            if shouldLoadNow:
                self.calc_combined()
            if self.alias == 'auto':
                cs = self.madeOf[0].alias
                for data in self.madeOf[1:]:
                    cs = cco.common_substring((cs, data.alias))
                what = self.dataFormat['combine']
                lenC = len(self.madeOf)
                tmpalias = "{0}_{1}{2}".format(
                    cs, cco.combineNames[what], lenC)
        elif isinstance(self.madeOf, str):
            self.madeOf = self.madeOf.replace('\\', '/')
            if self.madeOf.startswith('silx:'):
                self.dataType = cco.DATA_DATASET
            else:
                self.dataType = cco.DATA_COLUMN_FILE
            self.set_auto_color_tag()
            if shouldLoadNow:
                self.read_file()

            if self.state[toNode.name] == cco.DATA_STATE_GOOD:
                if not self.check_shape():
                    print('Incompatible data shapes!')
                    self.state[self.originNodeName] = cco.DATA_STATE_BAD
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
        else:
            raise ValueError('unknown data type of {0}'.format(self.alias))
        if self.alias == 'auto':
            # check duplicates:
            allLoadedItemNames = [d.alias for d in csi.allLoadedItems
                                  if d is not self]
            if len(allLoadedItemNames) > 0:
                allLoadedItemsCount = Counter(allLoadedItemNames)
                n = allLoadedItemsCount[tmpalias]
                if n > 0:
                    tmpalias += " ({0})".format(n)
            self.alias = tmpalias

#        csi.undo.append([self, insertAt, lenData])

        if copyTransformParams:
            if len(csi.selectedItems) > 0:
                self.transformParams.update(
                    csi.selectedItems[0].transformParams)
            else:
                for tr in csi.transforms.values():
                    self.transformParams.update(tr.iniParams)

        self.transformParams.update(transformParams)

        # replot if toNode is not reached by any transform, otherwise it will
        # be replotted by that transform:
        for tr in toNode.transformsOut:
            if tr.fromNode is tr.toNode:
                break
        else:
            csi.nodesToReplot = [toNode]

        if runDownstream and toNode.transformsOut and \
                self.state[toNode.name] == cco.DATA_STATE_GOOD:
            for tr in toNode.transformsOut:
                tr.run(dataItems=[self])  # no need for multiprocessing here
                if csi.model is not None:
                    csi.model.invalidateData()

    def set_auto_color_tag(self):
        if self.colorTag != 0:
            return
        if self.terminalNodeName is not None:
            self.colorTag = 3
            return

        if self.dataType == cco.DATA_DATASET:
            self.colorTag = 1
        elif self.dataType == cco.DATA_COLUMN_FILE:
            self.colorTag = 2

    def check_shape(self):
        toNode = csi.nodes[self.originNodeName]
        for iarr, arrName in enumerate(toNode.checkShapes):
            pos = arrName.find('[')
            if pos > 0:
                stem = arrName[:pos]
                sl = arrName[pos+1:-1]
            else:
                stem = arrName
                sl = '0'
            checkName = toNode.get_prop(stem, 'raw')
            arr = getattr(self, checkName)
            shape = arr.shape[eval(sl)] if arr is not None else []
            if iarr == 0:
                shape0 = shape
                continue
            if shape != shape0:
                return False
        return True

    def insert_data(self, data, insertAt=None, **kwargs):
        u"""This method inserts a tree-like structure *data* into the list of
        children. An example of *data*:
        :code:`data=["groupName", ["fName1.dat", "fName2.dat"]]` for a group
        with two items in it. All other key word parameters lumped into
        *kwargs* are the same as of :meth:`__init__`.
        """
        return super().insert_data(data, insertAt, **kwargs)

    def insert_item(self, name, insertAt=None, **kwargs):
        u"""
        This method inserts a data item *name* into the list of children. All
        other key word parameters lumped into *kwargs* are the same as of
        :meth:`__init__` and additionally *configData* that can pass an
        instance `config.ConfigParser()` that contains a saved project.
        """

        """This method searches for one or more sequences in the elements of
        `dataSource` list. If found, these sequences should be of an equal
        length and the same number of spectra will be added to the data model
        in a separate group. If a shorter sequence is found, only its first
        element will be used for the expansion of this sequence to the length
        of the longest sequence(s)."""

        nameFull = None
        if 'configData' in kwargs:  # ini file
            configData = kwargs['configData']
            if name in configData:
                madeOf = config.get(configData, name, 'madeOf')
                if (isinstance(madeOf, str) and
                        'dataFormat' in configData[name]):
                    tmp = {entry: config.get(configData, name, entry)
                           for entry in self.configFieldsData}
                    tmp['alias'] = name
                    dataFormatFull = dict(tmp['dataFormat'])
                    dataFormatRel = tmp['dataFormat_relative']
                    if dataFormatRel is not None:
                        tmp['dataFormat'] = tmp['dataFormat_relative']
                    if 'colorIndividual' in configData[name]:
                        tmp['colorIndividual'] = config.get(
                            configData, name, 'colorIndividual')
                    if 'plotProps' in configData[name]:
                        tmp['plotProps'] = config.get(
                            configData, name, 'plotProps')
                    trParams = {}
                    for tr in csi.transforms.values():
                        for key, val in tr.defaultParams.items():
                            trParams[key] = config.get(configData, name, key,
                                                       default=val)
                    tmp['transformParams'] = trParams
                    name = tmp.pop('madeOf_relative')
                    nameFull = tmp.pop('madeOf')
                elif isinstance(madeOf, (dict, list, tuple)):
                    tmp = {entry: config.get(configData, name, entry)
                           for entry in self.configFieldsCombined}
                    tmp['alias'] = name
                    trParams = {}
                    for tr in csi.transforms.values():
                        for key, val in tr.defaultParams.items():
                            trParams[key] = config.get(configData, name, key,
                                                       default=val)
                    tmp['transformParams'] = trParams
                    if isinstance(madeOf, dict):
                        tmp['dataFormat'] = {}
                        name = tmp.pop('madeOf')
                    elif isinstance(madeOf, (list, tuple)):
                        name = tmp.pop('madeOf')
                        tmp['shouldLoadNow'] = False
                        # for spName in madeOf:
                        #     item = self.get_top().find_data_item(spName)
                        #     if item is None:
                        #         raise ValueError(
                        #             'Error while loading "{0}": '
                        #             'no data "{1}" among the loaded ones!'
                        #             .format(tmp['alias'], spName))
                        #     name.append(item)
                elif 'colorPolicy' in configData[name]:  # group entry
                    tmp = {entry: config.get(configData, name, entry)
                           for entry in self.configFieldsGroup}
                else:
                    tmp = {}
                kwargs = dict(tmp)
            else:
                kwargs = {}
            kwargs['runDownstream'] = False
        elif 'configDict' in kwargs:
            configDict = kwargs['configDict']
            kwargs = dict(configDict[name]) if name in configDict else {}

        df = kwargs.get('dataFormat', {})
        if isinstance(name, str) and not df:
            # is a group
            return Spectrum(name, self, insertAt, **kwargs)

        spectraInOneFile = 1
        dataSource = list(df.get('dataSource', []))
        dataSourceSplit = []
        for ds in dataSource:
            ds = str(ds)
            if "np." in ds:
                continue
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
                if nameFull is not None:
                    # remove the Spectrum from the failed attempt in 'try:'
                    if insertAt is None:
                        self.childItems.pop()
                    else:
                        self.childItems.pop(insertAt)
                    print('local file {0} not found, will load {1}'.format(
                        name, nameFull))
                    kwargs['dataFormat'] = dataFormatFull
                    return Spectrum(nameFull, self, insertAt, **kwargs)
                else:
                    raise(e)

        basename = osp.basename(name)
        groupName = osp.splitext(basename)[0]
        group = Spectrum(groupName, self, insertAt, colorPolicy='loop1')

        multiArr = []
        for ids, ds in enumerate(dataSourceSplit):
            if len(ds) < spectraInOneFile:
                dataSourceSplit[ids] = [ds[0] for i in range(spectraInOneFile)]
            else:
                multiArr.append(ids)

        kwargs.pop('dataFormat', '')
        kwargs.pop('alias', '')
        diffs = []
        for ij, ids in enumerate(multiArr):
            names = dataSourceSplit[ids]
            nL = min(len(s) for s in names)
            diffs.append([i for i in range(nL) if names[0][i] != names[1][i]])
        for ds in zip(*dataSourceSplit):
            suffs = []
            for i, diff in zip(multiArr, diffs):
                suffs.append(''.join(ds[i][j] for j in diff))
            alias = '{0}_{1}'.format(groupName, '_'.join(suffs))
            df['dataSource'] = list(ds)
            Spectrum(name, group, dataFormat=df, alias=alias, **kwargs)

        if csi.withGUI:
            group.init_colors(group.childItems)

        return group

    def read_file(self):
        madeOf = self.madeOf
        toNode = csi.nodes[self.originNodeName]
        df = dict(self.dataFormat)
        df.update(csi.extraDataFormat)
        formatSection = 'Format_' + toNode.name
        config.configLoad[formatSection] = dict(df)

        arr = []
        if self.dataType == cco.DATA_COLUMN_FILE:
            header = cco.get_header(madeOf, df)
        elif self.dataType == cco.DATA_DATASET:
            header = []
            try:
                label = silx_io.get_data(madeOf + "/" + df["labelName"])
                self.aliasExtra = label.decode("utf-8")
                header.append(label)
            except (ValueError, KeyError):
                pass

            mdtxt = df.get('metadata', '')
            if mdtxt:
                mds = [md.strip() for md in mdtxt.split(',')]
            else:
                mds = []

            for md in mds:
                try:
                    mdres = silx_io.get_data(madeOf + "/" + md)
                    if isinstance(mdres, bytes):
                        mdres = mdres.decode("utf-8")
                    header.append("<b>{0}</b>: {1}<br>".format(md, mdres))
                except (ValueError, KeyError, OSError) as e:
                    print('No metadata: {0}'.format(e))
        else:
            raise TypeError('wrong datafile type')

        try:
            df['skip_header'] = df.pop('skiprows', 0)
            dataSource = df.pop('dataSource', None)
            sliceStrs = df.pop('slices', ['' for ds in dataSource])
            conversionFactors = df.pop('conversionFactors',
                                       [None for arr in toNode.arrays])
            df.pop('metadata', None)
            if dataSource is None:
                raise ValueError('bad dataSource settings')
            if self.dataType == cco.DATA_COLUMN_FILE:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    arrs = np.genfromtxt(madeOf, unpack=True, **df)
                if len(arrs) == 0:
                    raise ValueError('bad data file')

            roles = toNode.get_arrays_prop('role')

            # Create optional arrays and assign None.
            # This loop is needed when dataSource list is shorter than arrays.
            for aName, role in zip(toNode.arrays, roles):
                setName = toNode.get_prop(aName, 'raw')
                if role == 'optional':
                    setattr(self, setName, None)

            for aName, txt, sliceStr, role in zip(
                    toNode.arrays, dataSource, sliceStrs, roles):
                setName = toNode.get_prop(aName, 'raw')
                if (role == 'optional') and (txt == ''):
                    setattr(self, setName, None)
                    continue
                try:
                    if self.dataType == cco.DATA_COLUMN_FILE:
                        if isinstance(txt, int):
                            arr = arrs[txt]
                        else:
                            arr = self.interpret_array_formula(txt, arrs)
                    else:
                        arr = self.interpret_array_formula(txt)
                        if sliceStr:
                            if 'axis' in sliceStr or 'sum' in sliceStr:
                                # sum axes
                                sumlst = \
                                    sliceStr[sliceStr.find('=')+1:].split(',')
                                arr = arr.sum(axis=[int(ax) for ax in sumlst])
                            else:
                                sliceTuple = tuple(
                                    cco.parse_slice_str(slc)
                                    for slc in sliceStr.split(','))
                                arr = arr[sliceTuple]
                    setattr(self, setName, arr)
                except Exception as e:
                    print(e)
                    setattr(self, setName, None)

            self.state[toNode.name] = cco.DATA_STATE_GOOD
        except (ValueError, OSError, IndexError) as e:
            print('Error in read_file(): {0}'.format(e))
            self.state = dict((n, cco.DATA_STATE_NOTFOUND) for n in csi.nodes)
            return

        self.convert_units(conversionFactors)
        # define metadata
        if self.dataType == cco.DATA_COLUMN_FILE:
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
            else:
                self.meta['text'] = ''
        self.meta['length'] = len(arr)

        start = 5 if self.madeOf.startswith('silx:') else 0
        end = self.madeOf.find('::') if '::' in self.madeOf else None
        path = self.madeOf[start:end]
        abspath = osp.abspath(path).replace('\\', '/')
        toSave = self.madeOf[:start] + abspath
        if end is not None:
            toSave += self.madeOf[end:]
        config.put(config.configLoad, 'Data', toNode.name, toSave)
        config.write_configs('transform')

    def interpret_array_formula(self, colStr, treeObj=None):
        if "np." in colStr:
            try:
                arr = eval(colStr)
                return arr
            except Exception:
                pass
        try:
            # to expand string expressions
            colStr = str(eval(colStr))
        except Exception:
            pass

        keys = re.findall(r'\[(.*?)\]', colStr)
        if len(keys) == 0:
            if "Col" in colStr:
                regex = re.compile('Col([0-9]*)')
                subkeys = regex.findall(colStr)
                keys = ['Col'+ch for ch in subkeys]
                for ch in subkeys:
                    colStr = colStr.replace('Col'+ch, 'd["Col{0}"]'.format(ch))
            else:
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
                    config.put(config.configLoad, 'Data',
                               self.originNodeName+'_silx', k)
                else:
                    d[k] = silx_io.get_data('/'.join((self.madeOf, k)))
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
        return eval(colStr)

    def convert_units(self, conversionFactors):
        if not conversionFactors:
            return
        toNode = csi.nodes[self.originNodeName]
        for aName, cFactor in zip(toNode.arrays, conversionFactors):
            if not cFactor:
                continue
            setName = toNode.get_prop(aName, 'raw')
            arr = getattr(self, setName)
            try:
                if isinstance(cFactor, str):
                    if cFactor.startswith('transpose'):
                        axes = eval(cFactor[9:])
                        setattr(self, setName, arr.transpose(*axes))
                    elif cFactor.startswith('f'):
                        arr *= 1e15
                    elif cFactor.startswith('p'):
                        arr *= 1e12
                    elif cFactor.startswith('n'):
                        arr *= 1e9
                    elif cFactor.startswith('µ'):
                        arr *= 1e6
                    elif cFactor.startswith('m'):
                        arr *= 1e3
                    elif cFactor.startswith('k'):
                        arr *= 1e-3
                    elif cFactor.startswith('M'):
                        arr *= 1e-6
                    elif cFactor.startswith('G'):
                        arr *= 1e-9
                    continue
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
            cco.combineNames[what], ', '.join(it.alias for it in madeOf))

#        self.meta['modified'] = osp.getmtime(madeOf)
        self.meta['modified'] = time.strftime("%a, %d %b %Y %H:%M:%S")
        self.meta['size'] = -1

        try:
            assert isinstance(madeOf, (list, tuple))
            toNode = csi.nodes[self.originNodeName]

            # if no 'raw' present, returns arrayName itself:
            dNames = toNode.get_arrays_prop('raw')
            xNames = toNode.get_arrays_prop('raw', role='x') +\
                toNode.get_arrays_prop('raw', role='0D')
            dims = toNode.get_arrays_prop('ndim')

            # check equal shape of data to combine:
            shapes = [None]*4
            for dName, dim in zip(dNames, dims):
                if 0 < dim < 4:
                    for data in madeOf:
                        sh = getattr(data, dName).shape
                        if shapes[dim] is None:
                            shapes[dim] = sh
                        else:
                            assert shapes[dim] == sh

            for data in madeOf:
                if self not in data.combinesTo:
                    data.combinesTo.append(self)

            ns = len(madeOf)
            # x and 0D as average over all contributing spectra:
            for arrayName in xNames:
                sumx = 0
                setName = toNode.get_prop(arrayName, 'raw')
                for data in madeOf:
                    sumx += np.array(getattr(data, setName))
                setattr(self, setName, sumx/ns)

            dimArray = None
            for arrayName, dim in zip(dNames, dims):
                if arrayName in xNames:
                    continue
                if what in (cco.COMBINE_AVE, cco.COMBINE_SUM, cco.COMBINE_RMS):
                    s = sum(getattr(data, arrayName) for data in madeOf)
                    if what == cco.COMBINE_AVE:
                        v = s / ns
                    elif what == cco.COMBINE_SUM:
                        v = s
                    elif what == cco.COMBINE_RMS:
                        s2 = sum((getattr(d, arrayName) - s/ns)**2
                                 for d in madeOf)
                        v = (s2 / ns)**0.5
                elif what == cco.COMBINE_PCA:
                    raise NotImplementedError  # TODO
                else:
                    raise ValueError("unknown data combination")
                setattr(self, arrayName, v)
                if dim == toNode.plotDimension:
                    dimArray = v

            self.meta['length'] = len(dimArray) if dimArray is not None else 0
            self.state[toNode.name] = cco.DATA_STATE_GOOD
        except AssertionError:
            self.state[toNode.name] = cco.DATA_STATE_MATHERROR
            msg = '\nThe conbined arrays have different lengths'
            self.meta['text'] += msg
            if csi.DEBUG_LEVEL > 50:
                print('calc_combined', self.alias, msg)

    @logger(minLevel=50, attrs=[(0, 'alias')])
    def branch_data(self):
        """Case of *madeOf* as dict, when branching out."""
        toNode = csi.nodes[self.originNodeName]
        try:
            for key, value in self.madeOf.items():
                if isinstance(value, np.ndarray):
                    setattr(self, key, value)
                elif isinstance(value, str):
                    base = self.get_top().find_data_item(value)
                    try:
                        setattr(self, key, getattr(base, key))
                    except Exception:
                        pass
                    self.meta = base.meta
                    if base.branch is None:
                        base.branch = self.parentItem
                else:
                    raise ValueError('unknown data type')
            self.state[toNode.name] = cco.DATA_STATE_GOOD

        except Exception as e:
            print('Exception in "branch_data()" for "{0}":'.format(
                self.alias), e)
            self.state[toNode.name] = cco.DATA_STATE_BAD

    @logger(minLevel=50, attrs=[(0, 'alias')])
    def create_data(self):
        """Case of *madeOf* as callable"""
        toNode = csi.nodes[self.originNodeName]
        try:
            res = self.madeOf(self, **self.dataFormat)
            if res is not None:
                for arrayName, arr in zip(toNode.arrays, res):
                    setName = toNode.get_prop(arrayName, 'raw')
                    setattr(self, setName, arr)
            self.state[toNode.name] = cco.DATA_STATE_GOOD
        except Exception as e:
            print('Exception in "create_data":', e)
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
        if ((isinstance(item.madeOf, str) and item.dataFormat) or
                isinstance(item.madeOf, (list, tuple, dict))):
            if isinstance(item.madeOf, str):
                start = 5 if item.madeOf.startswith('silx:') else 0
                end = item.madeOf.find('::') if '::' in item.madeOf else None
                path = item.madeOf[start:end]
                abspath = osp.abspath(path).replace('\\', '/')
                madeOf = item.madeOf[:start] + abspath
                if end is not None:
                    madeOf += item.madeOf[end:]
                config.put(configProject, item.alias, 'madeOf', madeOf)
                relpath = osp.relpath(path, dirname).replace('\\', '/')
                madeOfRel = item.madeOf[:start] + relpath
                if end is not None:
                    madeOfRel += item.madeOf[end:]
                config.put(configProject, item.alias, 'madeOf_relative',
                           madeOfRel)

                dataFormatCopy = copy.deepcopy(item.dataFormat)
                dataSource = list(dataFormatCopy.get('dataSource', []))
                if 'conversionFactors' in dataFormatCopy:
                    if dataFormatCopy['conversionFactors'] == \
                            [None for ds in dataSource]:  # all None's
                        dataFormatCopy.pop('conversionFactors', None)
                for ids, ds in enumerate(dataSource):
                    if 'silx:' in ds:
                        start = 5
                        end = ds.find('::') if '::' in ds else None
                        path = ds[start:end]
                        abspath = osp.abspath(path).replace('\\', '/')
                        dsabs = ds[:start] + abspath + ds[end:]
                        ind = dataFormatCopy['dataSource'].index(ds)
                        dataFormatCopy['dataSource'][ind] = dsabs

                dataFormat = json.dumps(dataFormatCopy)
                dataFormat = dataFormat.replace('null', 'None')
                config.put(configProject, item.alias, 'dataFormat', dataFormat)
            elif isinstance(item.madeOf, (list, tuple)):
                config.put(configProject, item.alias, 'madeOf',
                           str(item.madeOf))
                dataFormat = json.dumps(item.dataFormat)
                cf = item.dataFormat['combine']
                dataFormat += "  # {0}='{1}'".format(cf, cco.combineNames[cf])
                dataFormat = dataFormat.replace('null', 'None')
                config.put(configProject, item.alias, 'dataFormat', dataFormat)
            elif isinstance(item.madeOf, dict):
                config.put(configProject, item.alias, 'madeOf',
                           str(item.madeOf))

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
                if 'conversionFactors' in dataFormatRel:
                    if dataFormatRel['conversionFactors'] == \
                            [None for ds in dataSourceRel]:  # all None's
                        dataFormatRel.pop('conversionFactors', None)
                for ids, ds in enumerate(dataSourceRel):
                    if 'silx:' in ds:
                        start = 5
                        end = ds.find('::') if '::' in ds else None
                        path = ds[start:end]
                        relpath = osp.relpath(path, dirname).replace('\\', '/')
                        madeOfRel = ds[:start] + relpath + ds[end:]
                        dataSourceRel[ids] = madeOfRel
                dataFormat = json.dumps(dataFormatRel)
                dataFormat = dataFormat.replace('null', 'None')
                config.put(
                    configProject, item.alias, 'dataFormat_relative',
                    dataFormat)

            config.put(configProject, item.alias, 'suffix', str(item.suffix))
            config.put(
                configProject, item.alias, 'originNodeName',
                item.originNodeName if item.originNodeName else 'None')
            config.put(
                configProject, item.alias, 'terminalNodeName',
                item.terminalNodeName if item.terminalNodeName else 'None')
            config.put(
                configProject, item.alias, 'transformNames',
                str(item.transformNames)
                if isinstance(item.transformNames, (list, tuple)) else 'each')
            config.put(
                configProject, item.alias, 'colorTag', str(item.colorTag))
            config.put(configProject, item.alias, 'color', str(item.color))
            if hasattr(item, 'colorIndividual'):
                config.put(configProject, item.alias, 'colorIndividual',
                           str(item.color))
            config.put(configProject, item.alias, 'plotProps',
                       str(item.plotProps))

            configProject.set(
                item.alias, ';transform params:')  # ';'=comment out
            dtparams = item.transformParams
            for key in dtparams:
                if isinstance(dtparams[key], np.ndarray):
                    toSave = dtparams[key].tolist()
                else:
                    toSave = dtparams[key]
                config.put(configProject, item.alias, key, str(toSave))

        elif isinstance(item.madeOf, str) and not item.dataFormat:
            # i.e. is a group
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

    @logger(minLevel=50, attrs=[(0, 'alias')])
    def branch_out(self, nbrunch, toTransfer, nodeStop, nodeStart,
                   transformNames, label=''):
        """Brach this spectrum into a group of *nbrunch* new items. Example:
        a 3D item has n ROIs that result in n 1D spectra; these spectra are put
        to a new group and start at *nodeStart* (str) whereas the original data
        item stops at *nodeStop* (str). The sequence *toTransfer* has field
        names that will be created in the new branches and will be assigned the
        values of the same fields from the branched out spectrum.
        """

        if csi.model is not None:
            csi.model.beginResetModel()
        self.terminalNodeName = nodeStop
        self.colorTag = 3
        if self.branch is None:
            kw = dict(colorPolicy='loop2', colorTag=4)
            self.branch = self.parentItem.insert_item(
                self.alias+'_rois', self.row()+1, **kw)
            if hasattr(self.branch.parentItem, 'colorAutoUpdate'):
                self.branch.colorAutoUpdate = \
                    self.branch.parentItem.colorAutoUpdate
        while self.branch.child_count() > nbrunch:
            self.branch.childItems[-1].remove_from_parent()
        while self.branch.child_count() < nbrunch:
            kw = dict(
                alias='{0}_{1}{2}'.format(self.alias, label,
                                          self.branch.child_count()+1),
                originNodeName=nodeStart, transformNames=transformNames,
                runDownstream=False)
            dictToTransfer = {key: self.alias for key in toTransfer}
            newItem = self.branch.insert_item(
                dictToTransfer, self.branch.child_count(), **kw)
            newItem.transformParams = self.transformParams
            newItem.meta = self.meta
            newItem.colorTag = 4
        self.init_colors(self.branch.childItems)
        for newItem in self.branch.childItems:
            newItem.state[nodeStart] = cco.DATA_STATE_GOOD
            for key in toTransfer:
                setattr(newItem, key, getattr(self, key))

        if csi.model is not None:
            csi.model.endResetModel()
