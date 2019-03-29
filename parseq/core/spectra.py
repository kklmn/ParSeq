# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import os
import re
import time
import copy
import numpy as np
from collections import Counter
import silx.io as silx_io

from . import singletons as csi
from . import commons as cco

DEFAULT_COLOR_AUTO_UPDATE = False

DATA_COLUMN_FILE, DATA_DATASET, DATA_COMBINATION, DATA_FUNCTION, DATA_GROUP =\
    range(5)
COMBINE_NONE, COMBINE_AVE, COMBINE_SUM, COMBINE_PCA, COMBINE_RMS = range(5)
combineName = '', 'ave', 'sum', 'PCA', 'RMS'


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
        self.aliasExtra = None
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
                    res = self.madeOf
                    if self.aliasExtra:
                        res += ': {0}'.format(self.aliasExtra)
                    return res

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
        parentItem = self.parentItem
        try:
            parentItem.childItems.remove(self)
            if parentItem.child_count() == 0:
                parentItem.delete()
        except (AttributeError, ValueError):
            pass

    def insert_item(self, name, insertAt=None, **kwargs):
        return TreeItem(name, self, insertAt, **kwargs)

    def insert_data(self, data, insertAt=None, isRecursive=False, **kwargs):
        items = []
        if hasattr(self, 'alias'):
            alias = self.alias
        elif hasattr(self, 'madeOf'):
            alias = self.madeOf
        elif hasattr(self, 'name'):
            alias = self.name

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
                    subItems = si.insert_data(
                        subdata, isRecursive=True, **kwargs)  # no insertAt
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
        shouldMakeColor = (not isRecursive  # *items* is the full list of data
                           and ('dataFormat' in kwargs)  # data, not a group
                           and csi.withGUI)
        if shouldMakeColor:
            self.init_colors(items)
        return items

    def init_colors(self, items=None):
        from ..gui import gcommons as gco
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
            if csi.withGUI:
                from ..gui import gcommons as gco
                self.colorPolicy = gco.COLOR_POLICY_LOOP1
                self.colorAutoUpdate = DEFAULT_COLOR_AUTO_UPDATE
            return

        self.alias = kwargs.get('alias', 'auto')
        self.dataFormat = copy.deepcopy(kwargs.get('dataFormat', {}))
        originNode = kwargs.get('originNode', None)
        if originNode is None:
            originNode = list(csi.nodes.values())[0]
        self.originNode = originNode
        self.terminalNode = kwargs.get('terminalNode', None)

        self.isExpanded = True
        self.colorTag = kwargs.get('colorTag', 0)
        self.hasChanged = False
        self.isGood = dict((node.name, False) for node in csi.nodes.values())
        self.aliasExtra = None
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
            for ind, yName in enumerate(node.yNames):
                plotParams = {'symbolsize': 2}
                for k, v in node.plotParams.items():
                    if isinstance(v, (list, tuple)):
                        pv = v[ind]
                    else:
                        pv = v
                    plotParams[k] = pv
                self.plotProps[node.name][yName] = plotParams

    def is_good(self, column):
        leadingColumns = len(csi.modelLeadingColumns)
        if column < leadingColumns:
            return True
        node = csi.modelDataColumns[column-leadingColumns][0]
        return self.isGood[node.name]

    def read_data(self, shouldLoadNow=True, runDownstream=True):
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
                self.alias = "{0}_{1}{2}".format(cs, combineName[what], lenC)
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

            basename = os.path.basename(self.madeOf)
            if self.alias == 'auto':
                self.alias = os.path.splitext(basename)[0]
                if self.aliasExtra:
                    self.alias += ': {0}'.format(self.aliasExtra)
                # check duplicates:
                if True:  # should check duplicates
                    allLoadedItemsCount = Counter(
                        os.path.normcase(d.madeOf) for d in csi.allLoadedItems)
                    n = allLoadedItemsCount[os.path.normcase(self.madeOf)]
                    if n > 0:
                        self.alias += " ({0})".format(n)

#        csi.undo.append([self, insertAt, lenData])

        # init self.transformParams:
        for tr in csi.transforms.values():
            if tr.name not in self.transformParams:
                self.transformParams[tr.name] = tr.params.copy()

        if runDownstream:
            for tr in self.originNode.transformsOut:
                tr.run(dataItems=[self])

    def insert_item(self, name, insertAt=None, **kwargs):
        return Spectrum(name, self, insertAt, **kwargs)

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
            except (ValueError, KeyError):
                pass
            try:
                header.append(silx_io.get_data(madeOf + "/start_time"))
                header.append(silx_io.get_data(madeOf + "/end_time"))
            except (ValueError, KeyError):
                pass
        else:
            raise TypeError('wrong datafile type')
        xF = df.pop('xFactor') if 'xFactor' in df else None

        try:
            df['skip_header'] = df.pop('skiprows', 0)
            dataSource = df.pop('dataSource', None)
            if dataSource is None:
                raise ValueError('bad dataSource settings')
            if self.dataType == DATA_COLUMN_FILE:
                with np.warnings.catch_warnings():
                    np.warnings.simplefilter("ignore")
                    arrs = np.genfromtxt(madeOf, unpack=True, **df)
                if len(arrs) == 0:
                    raise ValueError('bad data file')

            txt = dataSource[0]
            if self.dataType == DATA_COLUMN_FILE:
                if isinstance(txt, int):
                    arr = arrs[txt]
                else:
                    arr = self.interpretArrayFormula(txt, arrs)
            else:
                arr = self.interpretArrayFormula(txt)
            if arr is None:
                raise ValueError('bad dataSource settings')
            if hasattr(toNode, 'xNameRaw'):
                setattr(self, toNode.xNameRaw, arr)
            else:
                setattr(self, toNode.xName, arr)
            if xF is not None:
                x = getattr(self, toNode.xName)
                x *= xF

            if hasattr(toNode, 'yNamesRaw'):
                yNames = toNode.yNamesRaw
            else:
                yNames = toNode.yNames
            for iy, yName in enumerate(yNames):
                txt = dataSource[iy+1]
                if self.dataType == DATA_COLUMN_FILE:
                    if isinstance(txt, int):
                        arr = arrs[txt]
                    else:
                        arr = self.interpretArrayFormula(txt, arrs)
                else:
                    arr = self.interpretArrayFormula(txt)
                try:
                    setattr(self, yName, arr)
                except:
                    setattr(self, yName, None)

            self.isGood[toNode.name] = True
        except:
            self.isGood[toNode.name] = False
            csi.model.invalidateData()
            return

        # define metadata
        if self.dataType == DATA_COLUMN_FILE:
            self.meta['text'] = r''.join(header)
            self.meta['modified'] = time.strftime(
                "%a, %d %b %Y %H:%M:%S", time.gmtime(os.path.getmtime(madeOf)))
            self.meta['size'] = os.path.getsize(madeOf)
        else:
            if isinstance(header[0], bytes):
                self.meta['text'] = '\n'.join(
                    h.decode("utf-8") for h in header)
            else:
                self.meta['text'] = '\n'.join(header)
        self.meta['length'] = len(arr)

    def interpretArrayFormula(self, colStr, treeObj=None):
        keys = re.findall(r'\[(.*?)\]', colStr)
        if len(keys) == 0:
            keys = colStr,
            colStr = 'd["{0}"]'.format(colStr)
        else:
            # remove outer quotes:
            keys = [k[1:-1] if k.startswith(('"', "'")) else k for k in keys]
        d = {}
        if treeObj is None:  # is Hdf5Item
            for k in keys:
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
            combineName[what], ', '.join(it.alias for it in madeOf))
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
