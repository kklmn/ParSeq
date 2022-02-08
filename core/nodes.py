# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys
from . import singletons as csi

isOldPyton = sys.version_info.major == 2


class Node(object):
    """Parental Node class. Must be subclassed to define the following class
    variables:

    *name*: the name of the GUI tab and also the section name in ini file.

    *arrays*: OrderedDict of dicts
        describes the arrays operated in this node. The keys are names of these
        arrays, the values are dictionaries optionally containg these kwargs:

        *role*: str, default = '1D' (not plotted)
            the array's role. Can be 'x', 'y', 'yleft', 'yright', 'z' or '1D'
            for 1D arrays (one and only one x-axis array is required), '2D' for
            2D plots and '3D' for stacked 2D images. '0D' values are listed in
            the data tree. Unless has a '0D' role, each array will appear in
            `data location` dialog to be able to import it from a file.

        *raw*: str, default = array name
            can define an intermediate array at the pipeline head when the main
            array (the key in *arrays*) is supposed to be obtained by an after
            load transformation. The plotted array is still the main one.

        *qLabel*: str, default = array name (the key in *arrays*)
            used in the GUI labels

        *qUnit*: str, default = None (no displayed units)
            attached to the GUI labels in parentheses

        *plotLabel*: str, or list of str, default = qLabel
            axis label for the GUI plot. For 2D or 3D plots the 2- or 3-list
            corresponds to the plot axes; if the list element is not in
            *arrays* then the str-element itself is the axis label, otherwise
            the label [and unit] are taken from that dictionary (entry of
            *arrays*).

        *plotUnit*: str: default = qUnit
            attached to the plot label in parentheses

        *plotParams*: dict , default is `{}` that assumes thin solid lines
            default parameters for plotting. Can have the following keys:
                *linewidth* (or *lw*), *style*, *symbol* and *symbolsize*.
            Note that color is set for a data entry and is equal across the
            nodes, so it is set not here.

    *auxArrays*: list of lists
        This field is needed only for data export. Array names are grouped
        together so that the 1st element in a group is an x array and the
        others are y arrays. This grouping is respected only for the export of
        1D data.

    """

    def __init__(self):
        for attr in ['name', 'arrays']:
            if not hasattr(self, attr):
                raise NotImplementedError(
                    "The class Node must be properly subclassed!")
        for array in self.arrays:
            for key in self.arrays[array]:
                self.getProp(array, key)  # validate the keys
        if not hasattr(self, 'auxArrays'):
            self.auxArrays = []

        # filled automatically by transforms after creation of all nodes:
        self.upstreamNodes = []
        # filled automatically by transforms after creation of all nodes:
        self.downstreamNodes = []
        # filled automatically by transforms:
        self.transformsOut = []  # list of transforms from this node
        # assigned automatically by transform:
        self.transformIn = None
        csi.nodes[self.name] = self

        roles = self.getPropList('role')
        for key, role in zip(self.arrays, roles):
            prl = role.lower()
            if prl[0] == '3':
                self.arrays[key]['ndim'] = 3
                self.plot3DArray = key
            elif prl[0] == '2':
                self.arrays[key]['ndim'] = 2
                self.plot2DArray = key
            elif prl[0] in ('x', 'y', 'z', '1'):
                self.arrays[key]['ndim'] = 1
                if prl[0] == 'x':
                    if hasattr(self, 'plotXArray'):
                        raise ValueError(
                            "there must be only one x array defined")
                    else:
                        self.plotXArray = key
                elif prl[0] == 'y':
                    if not hasattr(self, 'plotYArrays'):
                        self.plotYArrays = []
                    self.plotYArrays.append(key)
                    csi.modelDataColumns.append([self, key])
                elif prl[0] == 'z':
                    self.plotZArray = key
            elif prl[0] == '0':
                self.arrays[key]['ndim'] = 0
                if not hasattr(self, 'displayValues'):
                    self.displayValues = []
                self.displayValues.append(key)
                csi.modelDataColumns.append([self, key])
            else:
                raise ValueError("unknown role '{0}' of arrays['{1}']".format(
                    role, key))
                # self.arrays[key]['ndim'] = 0

        dims = self.getPropList('ndim')
        self.plotDimension = max(dims)

        if self.plotDimension == 1:
            self.columnCount = len(self.plotYArrays)
        else:
            self.columnCount = 0
        if hasattr(self, 'displayValues'):
            self.columnCount += len(self.displayValues)

    def is_between_nodes(self, node1, node2, node1in=True, node2in=False):
        """
        *node1* and *node2*: Node
            *node2* can be None, the right end is infinite then.

        *node1in* and *node2in*: bool
            define whether the interval is closed or open.
        """
        ans = (node1 in self.upstreamNodes) or (node1in and (self is node1))
        if ans and (node2 is not None):
            ans = (node2 in self.downstreamNodes) or\
                (node2in and (self is node2))
        return ans

    def getProp(self, arrayName, prop):
        if prop == 'qLabel':
            res = self.arrays[arrayName].get(prop, arrayName)
            return res.decode("utf-8") if isOldPyton else res
        elif prop == 'qUnit':
            res = self.arrays[arrayName].get(prop, None)
            return res.decode("utf-8") if isOldPyton else res
        elif prop == 'raw':
            return self.arrays[arrayName].get(prop, arrayName)
        elif prop == 'role':
            return self.arrays[arrayName].get(prop, '1D')
        elif prop == 'plotLabel':
            return self.arrays[arrayName].get(
                prop, self.getProp(arrayName, 'qLabel'))
        elif prop == 'plotUnit':
            return self.arrays[arrayName].get(
                prop, self.getProp(arrayName, 'qUnit'))
        elif prop == 'plotParams':
            return self.arrays[arrayName].get(prop, {})
        elif prop == 'ndim':
            return self.arrays[arrayName].get(prop, 0)
        else:
            raise ValueError("unknown prop {0} in arrays['{1}']".format(
                prop, arrayName))

    def getPropList(self, prop, keys=[], role=''):
        scope = keys if keys else self.arrays
        if role:
            return [self.getProp(key, prop) for key in scope
                    if self.getProp(key, 'role').startswith(role)]
        else:
            return [self.getProp(key, prop) for key in scope]
