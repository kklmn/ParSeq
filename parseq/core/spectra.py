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
methods.
"""
__author__ = "Konstantin Klementiev"
__date__ = "22 Apr 2024"
# !!! SEE CODERULES.TXT !!!

# import sys
import os.path as osp
import re
import time
import copy
import json
import numpy as np
from scipy.interpolate import interp1d
import scipy.linalg as spl
import warnings
from collections import Counter

import silx.io as silx_io

from . import singletons as csi
from . import commons as cco
from . import config
from .correction import calc_correction
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
                if isinstance(self.name, str):
                    res = self.name
            elif hasattr(self, 'madeOf'):  # instance of Spectrum
                if self.error is not None:
                    res = self.error
                elif self.beingTransformed:
                    res = '{0} is {1:.0f}% done'.format(self.beingTransformed,
                                                        self.progress*100)
                elif isinstance(self.madeOf, (str, dict, tuple, list)):
                    if isinstance(self.madeOf, str):
                        res = str(self.madeOf)
                    elif isinstance(self.madeOf, (tuple, list)) and\
                            'combine' in self.dataFormat:
                        what = self.dataFormat['combine']
                        if isinstance(self.madeOf[0], str):
                            names = self.madeOf
                        else:  # class Spectrum
                            names = [it.alias for it in self.madeOf]
                            if what == cco.COMBINE_TT:
                                names = names[:-1]
                        cNames = cco.combine_names(names)
                        if what == cco.COMBINE_PCA:
                            iSpectrumPCA = self.dataFormat['iSpectrumPCA']
                            it = self.madeOf[iSpectrumPCA]
                            ws = ', '.join(
                                ['{0:.3g}'.format(w) for w in it.wPCA]) \
                                if hasattr(it, 'wPCA') else '...'
                            res = '{0} of {1}\nbase={2}\nw=[{3}]'.format(
                                cco.combineNames[what], it.alias, cNames, ws)
                        elif what == cco.COMBINE_TT:
                            it = self.madeOf[-1]
                            ws = ', '.join(
                                ['{0:.3g}'.format(w) for w in it.wPCA]) \
                                if hasattr(it, 'wPCA') else '...'
                            res = '{0} of {1}\nbase={2}\nw=[{3}]'.format(
                                cco.combineNames[what], it.alias, cNames, ws)
                        else:
                            res = '{0} of [{1}]'.format(
                                cco.combineNames[what], cNames)
                        # res = self.meta['shortText']
                    else:
                        res = ""
                    if self.aliasExtra:
                        res += ': {0}'.format(self.aliasExtra)
                    dataSource = self.dataFormat.get('dataSource', [])
                    for ds in dataSource:
                        if isinstance(ds, str):
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
                            res += 'incompatible data shapes in {0}'.format(
                                node.name)
                            if hasattr(self, 'badShapes'):
                                res += ':\n'
                                res += ', '.join(
                                    ['{0}={1}'.format(k, v) for
                                     k, v in self.badShapes.items()])
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
                        elif self.state[node.name] == cco.DATA_STATE_MATHERROR:
                            res += '\nSee the error message in `metadata` '\
                                'widget for this data item '\
                                '(click the splitter button first)'

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

        if isinstance(data, (list, tuple)) and \
                'concatenate' in kwargs and kwargs['concatenate']:
            item = self.insert_item(data, insertAt, **kwargs)
            if item not in items:  # inclusion check that keeps the order
                items.append(item)
        elif isinstance(data, str):
            item = self.insert_item(data, insertAt, **kwargs)
            if item.state[item.originNodeName] == \
                    cco.DATA_STATE_MARKED_FOR_DELETION:
                item.remove_from_parent()
            else:
                if item not in items:  # inclusion check that keeps the order
                    items.append(item)
        elif isinstance(data, (list, tuple)):
            si = self
            for subdata in data:
                if isinstance(subdata, str):
                    si = self.insert_item(subdata, insertAt, **kwargs)
                    if si.state[si.originNodeName] == \
                            cco.DATA_STATE_MARKED_FOR_DELETION:
                        si.remove_from_parent()
                        subItems = []
                    else:
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
        # if len(csi.selectedItems) == 0:
        #     if len(csi.allLoadedItems) == 0:
        #         raise ValueError("No valid data added")
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

        if not hasattr(self, 'colorPolicy'):
            self.colorPolicy = gco.COLOR_POLICY_GRADIENT
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
            dictionary (for creating branches). Here, combination is one of
            ('ave', 'sum', 'PCA', 'RMS') and branching can be used to create
            several data items from one, e.g. multiple 1D cuts from a 2D data
            set.

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

        assert len(csi.nodes) > 0, "A data pipeline must first be created."
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

        self.state = dict((nn, cco.DATA_STATE_UNDEFINED) for nn in csi.nodes)
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
        self.aliasExtra = None  # for extra name qualifier
        self.meta = {'text': '', 'modified': '', 'size': 0}
        self.combinesTo = []  # list of instances of Spectrum if not empty

        self.transformParams = {}  # each transform will add to this dict
        self.dontSaveParamsWhenUnused = {}  # paramName=paramUsed
        # init self.transformParams:
        for tr in csi.transforms.values():
            self.transformParams.update(copy.deepcopy(tr.defaultParams))
            self.dontSaveParamsWhenUnused.update(tr.dontSaveParamsWhenUnused)

        self.fitParams = {}  # each fit will add to this dict
        # init self.fitParams:
        for fit in csi.fits.values():
            self.fitParams.update(copy.deepcopy(fit.defaultParams))

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
            fitParams = kwargs.pop('fitParams', {})
            shouldLoadNow = kwargs.pop(
                'shouldLoadNow',
                csi.dataRootItem.kwargs.get('shouldLoadNow', True))
            runDownstream = kwargs.pop(
                'runDownstream',
                csi.dataRootItem.kwargs.get('runDownstream', False))
            if csi.withGUI:
                self.color = kwargs.pop('color', 'k')
                self.init_plot_props()
                plotProps = kwargs.pop('plotProps', {})
                if plotProps:
                    self.plotProps.update(copy.deepcopy(plotProps))

            if 'concatenate' in kwargs and kwargs['concatenate']:
                concatenate = kwargs['concatenate']
                self.concatenateOf = self.madeOf
                self.concatenate = concatenate
            else:
                concatenate = False
            lengthCheck = kwargs.pop('lengthCheck', None)
            self.read_data(shouldLoadNow=shouldLoadNow,
                           runDownstream=runDownstream,
                           copyTransformParams=copyTransformParams,
                           transformParams=transformParams,
                           fitParams=fitParams,
                           concatenate=concatenate,
                           lengthCheck=lengthCheck)

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
            raise ValueError('unknown data type {0} of {1}'.format(
                type(self.madeOf), self.alias))

    def init_plot_props(self):
        row = self.row()
        if row is None:
            row = 0
        self.plotProps = {}
        for node in csi.nodes.values():
            self.plotProps[node.name] = {}
            if node.plotDimension == 1:
                # items = csi.selectedItems
                items = csi.allLoadedItems
                if len(items) > 0:
                    if hasattr(items[0], 'plotProps'):
                        self.plotProps[node.name] = dict(
                            items[0].plotProps[node.name])
                    else:
                        self.init_default_plot_props(node)
                else:
                    self.init_default_plot_props(node)

    def init_default_plot_props(self, node):
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
        if self.error is not None:
            return cco.DATA_STATE_BAD
        return self.state[nodeName]

    def read_data(self, shouldLoadNow=True, runDownstream=False,
                  copyTransformParams=True, transformParams={}, fitParams={},
                  concatenate=False, lengthCheck=None):
        fromNode = csi.nodes[self.originNodeName]
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
            if concatenate:
                axis, reduce = concatenate[:2] \
                    if isinstance(concatenate, (list, tuple)) else (0, False)
                madeOfTmp = list(self.madeOf)
                for iconcat, madeOf in enumerate(madeOfTmp):
                    self.madeOf = madeOf.replace('\\', '/')
                    if iconcat == 0:
                        if self.madeOf.startswith('silx:'):
                            self.dataType = cco.DATA_DATASET
                        else:
                            self.dataType = cco.DATA_COLUMN_FILE
                        self.set_auto_color_tag()
                    if shouldLoadNow:
                        self.read_file()
                    for aName in fromNode.arrays:
                        setName = fromNode.get_prop(aName, 'raw')
                        if iconcat == 0:
                            if reduce:
                                concatTmp = getattr(self, setName).sum(
                                    axis=axis, keepdims=True)
                            else:
                                concatTmp = copy.copy(getattr(self, setName))
                            setattr(self, setName+'Concat', concatTmp)
                        else:
                            if reduce:
                                tmp = getattr(self, setName).sum(
                                    axis=axis, keepdims=True)
                            else:
                                tmp = copy.copy(getattr(self, setName))
                            if getattr(self, setName+'Concat') is not None:
                                concatTmp = np.concatenate(
                                    (getattr(self, setName+'Concat'), tmp))
                                setattr(self, setName+'Concat', concatTmp)
                                setattr(self, setName, concatTmp)
                            else:
                                setattr(self, setName, None)
                if self.state[fromNode.name] == cco.DATA_STATE_GOOD:
                    shapes = self.check_shape()
                    if isinstance(shapes, dict):
                        print('Incompatible data shapes in {0}:\n{1}'.format(
                            fromNode.name, shapes))
                        self.state[self.originNodeName] = cco.DATA_STATE_BAD
                        self.badShapes = shapes
                        self.colorTag = 3
                if self.alias == 'auto':
                    tmpalias = 'concatenation'
            else:
                self.dataType = cco.DATA_COMBINATION
                self.colorTag = 5
                if self.alias == 'auto':
                    cs = self.madeOf[0].alias
                    for data in self.madeOf[1:]:
                        cs = cco.common_substring((cs, data.alias))
                    what = self.dataFormat['combine']
                    lenC = len(self.madeOf)
                    tmpalias = "{0}_{1}{2}".format(
                        cs, cco.combineNames[what], lenC)
                if shouldLoadNow:
                    self.calc_combined()
        elif isinstance(self.madeOf, str):
            self.madeOf = self.madeOf.replace('\\', '/')
            if self.madeOf.startswith('silx:'):
                self.dataType = cco.DATA_DATASET
            else:
                self.dataType = cco.DATA_COLUMN_FILE
            self.set_auto_color_tag()
            if shouldLoadNow:
                self.read_file(lengthCheck=lengthCheck)

            if self.state[fromNode.name] == cco.DATA_STATE_MARKED_FOR_DELETION:
                return
            elif self.state[fromNode.name] == cco.DATA_STATE_GOOD:
                shapes = self.check_shape()
                if isinstance(shapes, dict):
                    print('Incompatible data shapes in {0}:\n{1}'.format(
                        fromNode.name, shapes))
                    self.state[self.originNodeName] = cco.DATA_STATE_BAD
                    self.badShapes = shapes
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
                    copy.deepcopy(csi.selectedItems[0].transformParams))
                self.fitParams.update(
                    copy.deepcopy(csi.selectedItems[0].fitParams))
            else:
                for tr in csi.transforms.values():
                    self.transformParams.update(
                        copy.deepcopy(tr.iniParams))
                for fit in csi.fits.values():
                    self.fitParams.update(
                        copy.deepcopy(fit.iniParams))

        self.transformParams.update(copy.deepcopy(transformParams))
        self.fitParams.update(copy.deepcopy(fitParams))

        # replot if fromNode is not reached by any transform, otherwise it will
        # be replotted by that transform:
        for tr in fromNode.transformsOut:
            if tr.fromNode is tr.toNode:
                break
        else:
            csi.nodesToReplot = [fromNode]

        self.make_corrections(fromNode)

        if runDownstream and fromNode.transformsOut and \
                self.state[fromNode.name] == cco.DATA_STATE_GOOD:
            for tr in fromNode.transformsOut:
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
        fromNode = csi.nodes[self.originNodeName]
        shapes = {}
        hasFailed = False
        for iarr, arrName in enumerate(fromNode.checkShapes):
            pos = arrName.find('[')
            if pos > 0:
                stem = arrName[:pos]
                sl = arrName[pos+1:-1]
            else:
                stem = arrName
                sl = '0'
            checkName = fromNode.get_prop(stem, 'raw')
            arr = getattr(self, checkName)
            try:
                shape = arr.shape[eval(sl)] if arr is not None else []
                shapes[checkName] = shape
            except IndexError:
                return False
            if iarr == 0:
                shape0 = shape
                continue
            if shape != shape0:
                hasFailed = True
        if hasFailed:
            return shapes
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

        def getTransformParams(configData):
            res = {}
            for tr in csi.transforms.values():
                for key, val in tr.defaultParams.items():
                    res[key] = config.get(configData, name, key, default=val)
                    if isinstance(res[key], dict):
                        for keyd, vald in tr.defaultParams[key].items():
                            res[key][keyd] = res[key].get(keyd, vald)
            for node in csi.nodes.values():
                corr_param_name = 'correction_' + node.name
                vv = config.get(configData, name, corr_param_name)
                if vv is not None:
                    res[corr_param_name] = vv
            return res

        def getFitParams(configData):
            res = {}
            for fit in csi.fits.values():
                for key, val in fit.defaultParams.items():
                    if key == fit.ioAttrs['result']:
                        continue
                    res[key] = config.get(configData, name, key, default=val)
            return res

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
                    tmp['transformParams'] = getTransformParams(configData)
                    tmp['fitParams'] = getFitParams(configData)
                    nameRel = tmp.pop('madeOf_relative')
                    if nameRel is not None:
                        name = nameRel
                    else:
                        name = tmp.get('madeOf')
                    nameFull = tmp.pop('madeOf')
                elif isinstance(madeOf, (dict, list, tuple)):
                    tmp = {entry: config.get(configData, name, entry)
                           for entry in self.configFieldsCombined}
                    tmp['alias'] = name
                    tmp['transformParams'] = getTransformParams(configData)
                    tmp['fitParams'] = getFitParams(configData)
                    if isinstance(madeOf, dict):
                        tmp['dataFormat'] = {}
                        name = tmp.pop('madeOf')
                    elif isinstance(madeOf, (list, tuple)):
                        if 'concatenate' in configData[name]:
                            tmp['concatenate'] = config.get(
                                configData, name, 'concatenate')
                            tmp['shouldLoadNow'] = True
                        else:
                            tmp['shouldLoadNow'] = False
                        name = tmp.pop('madeOf')
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
                    if tmp['colorPolicy'] == 'gradient':
                        tmp['color1'] = config.get(configData, name, 'color1')
                        tmp['color2'] = config.get(configData, name, 'color2')
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

        if 'concatenate' in kwargs and kwargs['concatenate']:
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
                    raise e

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

    def read_file(self, lengthCheck=None):
        madeOf = self.madeOf
        fromNode = csi.nodes[self.originNodeName]
        df = dict(self.dataFormat)
        df.update(csi.extraDataFormat)
        formatSection = 'Format_' + fromNode.name
        config.configLoad[formatSection] = dict(df)

        arr = []
        if self.dataType == cco.DATA_COLUMN_FILE:
            header = cco.get_header(madeOf, df, searchAllLines=True)
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

        try:  # if True:
            df['skip_header'] = df.pop('skiprows', 0)
            dataSource = df.pop('dataSource', None)
            sliceStrs = df.pop('slices', ['' for ds in dataSource])
            conversionFactors = df.pop('conversionFactors',
                                       [None for arr in fromNode.arrays])
            df.pop('metadata', None)
            cols = 0
            for ds in dataSource:
                try:
                    ds = int(ds)
                except Exception:
                    pass
                if isinstance(ds, str) and "Col" in ds:
                    regex = re.compile('Col([0-9]*)')
                    # remove possible duplicates by list(dict.fromkeys())
                    subkeys = list(dict.fromkeys(regex.findall(ds)))
                    for ch in subkeys:
                        cols = max(cols, int(ch))
                elif isinstance(ds, int):
                    cols = max(cols, ds)
            # important for column files that have incomplete columns:
            df['usecols'] = list(range(cols+1))
            if dataSource is None:
                raise ValueError('bad dataSource settings')
            if self.dataType == cco.DATA_COLUMN_FILE:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    arrs = np.genfromtxt(madeOf, unpack=True, **df)
                if len(arrs) == 0:
                    raise ValueError('bad data file')

            roles = fromNode.get_arrays_prop('role')

            # Create optional arrays and assign None.
            # This loop is needed when dataSource list is shorter than arrays.
            for aName, role in zip(fromNode.arrays, roles):
                setName = fromNode.get_prop(aName, 'raw')
                if role == 'optional':
                    setattr(self, setName, None)

            sortIndices = None
            sortArrayName = 'x'
            for aName, txt, sliceStr, role in zip(
                    fromNode.arrays, dataSource, sliceStrs, roles):
                setName = fromNode.get_prop(aName, 'raw')
                if (role == 'optional') and (txt == ''):
                    setattr(self, setName, None)
                    continue
                try:
                    if self.dataType == cco.DATA_COLUMN_FILE:
                        try:
                            txt = int(txt)
                        except Exception:
                            pass
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
                    setattr(self, setName, None)
                    raise ValueError(e)

                if lengthCheck and role == 'x':
                    if isinstance(lengthCheck, (int, float)):
                        if arr.max() - arr.min() < lengthCheck:
                            # print('too short')
                            self.state[fromNode.name] = \
                                cco.DATA_STATE_MARKED_FOR_DELETION
                            return
                if role == 'x':
                    sortArrayName = aName
                    _, sortIndices, sortCounts = np.unique(
                        arr, return_index=True, return_counts=True)

            if sortIndices is not None:
                count = sortCounts[sortCounts > 1].sum()
                if count > 0:
                    errorTxt = "{0} duplicate {1} value{2} ha{3} been removed"\
                        .format(count,
                                fromNode.get_prop(sortArrayName, 'qLabel'),
                                '' if count == 1 else 's',
                                's' if count == 1 else 've')
                    print(errorTxt)
                    header.append(errorTxt+'\n')

                for aName in fromNode.arrays:
                    setName = fromNode.get_prop(aName, 'raw')
                    arrt = getattr(self, setName)
                    if isinstance(arrt, np.ndarray):
                        setattr(self, setName, arrt[sortIndices])
            self.state[fromNode.name] = cco.DATA_STATE_GOOD
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
        try:
            self.meta['length'] = len(arr)
        except TypeError:  # another type, not array
            pass

        start = 5 if self.madeOf.startswith('silx:') else 0
        end = self.madeOf.find('::') if '::' in self.madeOf else None
        path = self.madeOf[start:end]
        abspath = osp.abspath(path).replace('\\', '/')
        toSave = self.madeOf[:start] + abspath
        if end is not None:
            toSave += self.madeOf[end:]
        config.put(config.configLoad, 'Data', fromNode.name, toSave)
        config.write_configs('transform, load')

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
            colStr = colStr.replace('col', 'Col')
            if "Col" in colStr:
                regex = re.compile('Col([0-9]*)')
                # remove possible duplicates by list(dict.fromkeys())
                subkeys = list(dict.fromkeys(regex.findall(colStr)))
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
        fromNode = csi.nodes[self.originNodeName]
        secondPassNeeded = False
        for aName, cFactor in zip(fromNode.arrays, conversionFactors):
            if not cFactor:
                continue
            setName = fromNode.get_prop(aName, 'raw')
            arr = getattr(self, setName)
            if arr is None:
                continue
            try:
                if isinstance(cFactor, str):
                    if cFactor.startswith('lim'):
                        secondPassNeeded = True
                        mn, mx = eval(cFactor[3:])
                        where = ((mn < arr) if mn is not None else True) & \
                            ((arr < mx) if mx is not None else True)
                    elif cFactor.startswith('transpose'):
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
                    self.hasChanged = True
                    continue
                arr *= cFactor
            except Exception as e:
                print(e, aName)
                setattr(self, setName, None)

        if secondPassNeeded:
            for aName in fromNode.arrays:
                setName = fromNode.get_prop(aName, 'raw')
                arr = getattr(self, setName)
                if arr is None:
                    continue
                try:
                    setattr(self, setName, arr[where])
                except Exception as e:
                    print(aName, e)
                    setattr(self, setName, None)

    @logger(minLevel=50, attrs=[(0, 'alias')])
    def calc_combined(self):
        """Case of *madeOf* as list of Spectrum instances. self.dataFormat is
        the type of the combination being made: one of COMBINE_XXX constants.
        """
        madeOf = self.madeOf
        what = self.dataFormat['combine']
        combineInterpolate = 'combineInterpolate' in self.dataFormat and \
            self.dataFormat['combineInterpolate']
        # define metadata
        self.meta['text'] = '{0} of {1}'.format(
            cco.combineNames[what], ', '.join(it.alias for it in madeOf))

#        self.meta['modified'] = osp.getmtime(madeOf)
        self.meta['modified'] = time.strftime("%a, %d %b %Y %H:%M:%S")
        self.meta['size'] = -1

        try:
            assert isinstance(madeOf, (list, tuple))
            fromNode = csi.nodes[self.originNodeName]

            # if no 'raw' present, returns arrayName itself:
            # dNames = fromNode.get_arrays_prop('raw')
            # xNames = fromNode.get_arrays_prop('raw', role='x') +\
            #     fromNode.get_arrays_prop('raw', role='0D')

            dNames = fromNode.get_arrays_prop('key')
            xNames = fromNode.get_arrays_prop('key', role='x') +\
                fromNode.get_arrays_prop('key', role='0D')
            dims = fromNode.get_arrays_prop('ndim')

            if not combineInterpolate:
                # check equal shape of data to combine:
                shapes = [None]*4
                for dName, dim in zip(dNames, dims):
                    if 1 <= dim <= 3:
                        for data in madeOf:
                            if getattr(data, dName) is None:  # optional
                                continue
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

            if combineInterpolate:
                it = madeOf[0]
                for arrayName in xNames:
                    setattr(self, arrayName, np.array(getattr(it, arrayName)))
                x0 = getattr(it, xNames[0])
            else:
                for arrayName in xNames:
                    sumx = 0
                    for data in madeOf:
                        sumx += np.array(getattr(data, arrayName))
                    setattr(self, arrayName, sumx/ns)

            dimArray = None
            for arrayName, dim in zip(dNames, dims):
                if arrayName in xNames:
                    continue
                if what in (cco.COMBINE_AVE, cco.COMBINE_SUM, cco.COMBINE_RMS,
                            cco.COMBINE_PCA, cco.COMBINE_TT):
                    arrays = []
                    for data in madeOf:
                        arr = getattr(data, arrayName)
                        if combineInterpolate and arr is not None:
                            x = getattr(data, xNames[0])
                            interp = interp1d(x, arr, fill_value="extrapolate",
                                              assume_sorted=True)
                            arrays.append(interp(x0))
                        else:
                            arrays.append(arr)
                    ns = sum(1 for arr in arrays if arr is not None)
                    if ns == 0:  # arrayName is optional, all arrays are None
                        setattr(self, arrayName, None)
                        continue
                    s = sum(arr for arr in arrays if arr is not None)

                    if what == cco.COMBINE_AVE:
                        v = s / ns
                    elif what == cco.COMBINE_SUM:
                        v = s
                    elif what == cco.COMBINE_RMS:
                        s2 = sum((a-s/ns)**2 for a in arrays if a is not None)
                        v = (s2 / ns)**0.5
                    elif what == cco.COMBINE_PCA:
                        iSpectrumPCA = self.dataFormat['iSpectrumPCA']
                        iPCA = self.dataFormat['iPCA']
                        nPCA = self.dataFormat['nPCA']
                        D = np.array(
                            [ar for ar in arrays if ar is not None]).T
                        k, nN = D.shape

                        if hasattr(madeOf[0], 'skip_eigh'):
                            doeigh = False
                        else:
                            doeigh = iPCA == 0
                        if doeigh:
                            DTD = np.dot(D.T, D)
                            DTD /= np.diag(DTD).sum()
                            kweigh = dict(eigvals=(nN-nPCA, nN-1))
                            w, v = spl.eigh(DTD, **kweigh)
                            # rec = np.dot(np.dot(v, np.diag(w)), v.T)
                            # print("diff DTD--decomposed(DTD) = {0}".format(
                            #     np.abs(DTD-rec).sum()))
                            for data in madeOf:
                                data.wPCA, data.vPCA = w, v
                        else:
                            sPCA = madeOf[iSpectrumPCA]
                            w, v = sPCA.wPCA, sPCA.vPCA

                        if iPCA == 0:
                            outPCA = np.zeros((k, nPCA))
                            for i in range(nPCA):
                                ii = -1-i
                                pr = np.dot(v[:, ii:], v[:, ii:].T)
                                outPCA[:, i] = np.dot(D, pr)[:, iSpectrumPCA]
                            if not hasattr(self.parentItem, 'pcas'):
                                self.parentItem.pcas = dict()
                            self.parentItem.pcas[fromNode.name] = outPCA

                        v = self.parentItem.pcas[fromNode.name][:, iPCA]
                    elif what == cco.COMBINE_TT:
                        B = np.array(
                            [ar for ar in arrays[:-1] if ar is not None]).T
                        d = arrays[-1]
                        BTB = np.dot(B.T, B)
                        w, v = spl.eigh(BTB)
                        revBTB = np.dot(np.dot(v, np.diag(1/w)), v.T)
                        BTd = np.dot(B.T, d)
                        revBTBBTd = np.dot(revBTB, BTd)
                        v = np.dot(B, revBTBBTd)
                        norm = sum(w)
                        madeOf[-1].wPCA = [i/norm for i in w]
                else:
                    raise ValueError("unknown data combination")
                setattr(self, arrayName, v)
                if dim == fromNode.plotDimension:
                    dimArray = v

            self.meta['length'] = len(dimArray) if dimArray is not None else 0
            self.state[fromNode.name] = cco.DATA_STATE_GOOD
        except AssertionError:
            self.state[fromNode.name] = cco.DATA_STATE_MATHERROR
            msg = '\nThe conbined arrays have different lengths. '\
                'Use "interpolate".'
            self.meta['text'] += msg
            if csi.DEBUG_LEVEL > -1:
                print('calc_combined', self.alias, msg)
        except AttributeError as e:
            self.state[fromNode.name] = cco.DATA_STATE_BAD
            msg = str(e)
            self.meta['text'] += msg
            if csi.DEBUG_LEVEL > -1:
                print('calc_combined', self.alias, msg)

    @logger(minLevel=50, attrs=[(0, 'alias')])
    def branch_data(self):
        """Case of *madeOf* as dict, when branching out."""
        fromNode = csi.nodes[self.originNodeName]
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
            self.state[fromNode.name] = cco.DATA_STATE_GOOD

        except Exception as e:
            print('Exception in "branch_data()" for "{0}":'.format(
                self.alias), e)
            self.state[fromNode.name] = cco.DATA_STATE_BAD

    @logger(minLevel=50, attrs=[(0, 'alias')])
    def create_data(self):
        """Case of *madeOf* as callable"""
        fromNode = csi.nodes[self.originNodeName]
        try:
            res = self.madeOf(self, **self.dataFormat)
            if res is not None:
                for arrayName, arr in zip(fromNode.arrays, res):
                    setName = fromNode.get_prop(arrayName, 'raw')
                    setattr(self, setName, arr)
            self.state[fromNode.name] = cco.DATA_STATE_GOOD
        except Exception as e:
            print('Exception in "create_data":', e)
            self.state[fromNode.name] = cco.DATA_STATE_BAD

    def save_transform_params(self):
        dtparams = self.transformParams
        for tr in csi.transforms.values():
            for key in tr.defaultParams:
                if isinstance(dtparams[key], np.ndarray):
                    toSave = dtparams[key].tolist()
                else:
                    toSave = dtparams[key]
                config.put(config.configTransforms, tr.name, key, str(toSave))

    def save_fit_params(self):
        dtparams = self.fitParams
        for fit in csi.fits.values():
            for key in fit.defaultParams:
                if isinstance(dtparams[key], np.ndarray):
                    toSave = dtparams[key].tolist()
                else:
                    toSave = dtparams[key]
                config.put(config.configFits, fit.name, key, str(toSave))

    def save_to_project(self, configProject, dirname):
        from ..gui import gcommons as gco  # only needed with gui

        def cleanJSON(inputStr):
            res = inputStr.replace('null', 'None')
            res = res.replace('true', 'True')
            res = res.replace('false', 'False')
            return res

        item = self
        if ((isinstance(item.madeOf, str) and item.dataFormat) or
                isinstance(item.madeOf, (list, tuple, dict))):
            if isinstance(item.madeOf, str):
                if hasattr(item, 'concatenateOf'):
                    config.put(configProject, item.alias, 'madeOf',
                               str(item.concatenateOf))
                    config.put(configProject, item.alias, 'concatenate',
                               str(item.concatenate))
                else:
                    start = 5 if item.madeOf.startswith('silx:') else 0
                    end = item.madeOf.find('::') if '::' in item.madeOf else \
                        None
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
                    if isinstance(ds, str) and 'silx:' in ds:
                        start = 5
                        end = ds.find('::') if '::' in ds else None
                        path = ds[start:end]
                        abspath = osp.abspath(path).replace('\\', '/')
                        dsabs = ds[:start] + abspath + ds[end:]
                        ind = dataFormatCopy['dataSource'].index(ds)
                        dataFormatCopy['dataSource'][ind] = dsabs

                dataFormat = cleanJSON(json.dumps(dataFormatCopy))
                config.put(configProject, item.alias, 'dataFormat', dataFormat)
            elif isinstance(item.madeOf, (list, tuple)):
                config.put(configProject, item.alias, 'madeOf',
                           str(item.madeOf))
                dataFormat = cleanJSON(json.dumps(item.dataFormat))
                cf = item.dataFormat['combine']
                dataFormat += "  # {0}='{1}'".format(cf, cco.combineNames[cf])
                config.put(configProject, item.alias, 'dataFormat', dataFormat)
            elif isinstance(item.madeOf, dict):
                config.put(configProject, item.alias, 'madeOf',
                           str(item.madeOf))

            dataSource = list(item.dataFormat.get('dataSource', []))
            for ds in dataSource:
                if isinstance(ds, str) and 'silx:' in ds:
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
                    if isinstance(ds, str) and 'silx:' in ds:
                        start = 5
                        end = ds.find('::') if '::' in ds else None
                        path = ds[start:end]
                        relpath = osp.relpath(path, dirname).replace('\\', '/')
                        madeOfRel = ds[:start] + relpath + ds[end:]
                        dataSourceRel[ids] = madeOfRel
                dataFormat = cleanJSON(json.dumps(dataFormatRel))
                config.put(configProject, item.alias, 'dataFormat_relative',
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
                if key in self.dontSaveParamsWhenUnused and \
                        (not dtparams[self.dontSaveParamsWhenUnused[key]]):
                    continue
                if isinstance(dtparams[key], np.ndarray):
                    toSave = dtparams[key].tolist()
                else:
                    toSave = dtparams[key]
                config.put(configProject, item.alias, key, str(toSave))

            noFitsSoFar = True
            dtparams = item.fitParams
            for fit in csi.fits.values():
                if dtparams[fit.ioAttrs['result']] == fit.defaultResult:
                    continue
                if noFitsSoFar:
                    configProject.set(
                        item.alias, ';fit params:')  # ';'=comment out
                    noFitsSoFar = False
                for key in fit.defaultParams:
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
                   transformNames=[], groupLabel='_rois', label=''):
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
            c1, c2 = '#ff0000', '#0000ff'
            kw = dict(colorPolicy='grad', color1=c1, color2=c2, colorTag=4)
            self.branch = self.parentItem.insert_item(
                self.alias+groupLabel, self.row()+1, **kw)
            self.branch.color1 = c1
            self.branch.color2 = c2
            self.branch.colorAutoUpdate = csi.dataRootItem.colorAutoUpdate
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
            newItem.fitParams = self.fitParams
            newItem.meta = self.meta
            newItem.colorTag = 4
        self.branch.init_colors(self.branch.childItems)
        for newItem in self.branch.childItems:
            newItem.state[nodeStart] = cco.DATA_STATE_GOOD
            for key in toTransfer:
                setattr(newItem, key, getattr(self, key))
        self.state[nodeStart] = cco.DATA_STATE_UNDEFINED

        if csi.model is not None:
            csi.model.endResetModel()

    @logger(minLevel=50, attrs=[(0, 'alias'), (1, 'name')])
    def make_corrections(self, node):
        corr_param_name = 'correction_' + node.name
        if corr_param_name not in self.transformParams:
            return False
        corrections = self.transformParams[corr_param_name]
        if corrections is None:
            return False

        wasCorrected = False
        for correction in corrections:
            # if correction['kind'] in ('delete',):
            #     prop = 'raw'
            # else:
            #     prop = 'key'
            prop = 'raw'
            if 'ndim' not in correction:
                correction['ndim'] = 1

            if correction['ndim'] == 1:
                xkeys = node.get_arrays_prop('name', role='x')
                if len(xkeys) == 0:
                    continue
                # xkey = xkeys[0]
                xkey = node.get_prop(xkeys[0], prop)
                try:
                    x = getattr(self, xkey)
                except AttributeError:
                    continue
                shapeBefore = x.shape

                corrKeys = []
                datainds = None
                for k, arr in node.arrays.items():
                    key = node.get_prop(k, prop)
                    if key == xkey:
                        continue
                    try:
                        y = getattr(self, key)
                    except AttributeError:
                        continue
                    if y is not None and y.shape == shapeBefore:
                        res = calc_correction(x, y, correction, datainds)
                        if res is None:
                            continue
                        wasCorrected = True
                        xn, yn = res[:2]
                        datainds = res[2] if len(res) > 2 else None
                        if correction['kind'] in ('spline-',):
                            setattr(self, key, y-yn)
                        else:
                            setattr(self, key, yn)
                        corrKeys.append(key)

                if correction['kind'] in ('delete', 'spikes'):
                    for nodeOther in csi.nodes.values():
                        if nodeOther is node:
                            continue
                        xkeysOther = nodeOther.get_arrays_prop(
                            'name', role='x')
                        if len(xkeysOther) == 0:
                            continue
                        xkeyOther = xkeysOther[0]
                        if xkeyOther != xkey:
                            continue
                        for k, arr in nodeOther.arrays.items():
                            key = nodeOther.get_prop(k, prop)
                            try:
                                attr = getattr(self, key)
                            except AttributeError:
                                continue
                            if key in corrKeys:
                                continue
                            if attr is not None and attr.shape == shapeBefore:
                                aC = calc_correction(
                                    x, attr, correction, datainds)[1]
                                setattr(self, key, aC)
                    setattr(self, xkey, xn)

            elif correction['ndim'] == 2:
                pass
        return wasCorrected
