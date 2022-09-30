# -*- coding: utf-8 -*-
u"""
Data nodes
----------

Data nodes are intermediate stops along the data pipeline. Their main purposes
are to visualize data, display transformation status, select parameters of data
transformations, possibly stop or split data propagation or combine with other
data. Each data node defines and operates arrays that get their values in the
upstream part of the pipeline.
"""
__author__ = "Konstantin Klementiev"
__date__ = "19 Apr 2022"
# !!! SEE CODERULES.TXT !!!

import sys
from . import singletons as csi

isOldPyton = sys.version_info.major == 2


class Node(object):
    u"""Parental Node class. Must be subclassed to define the following class
    variables:

    *name*: str
        The name of the node, also shown as a GUI tab and also is a section
        name in ini file.

    *arrays*: OrderedDict of dicts
        Describes the arrays operated in this node. Note, this object only
        contains data description; the actual data arrays will be attributed to
        data objects (items). The keys of *arrays* are names of these arrays,
        the values are dictionaries that optionally contain the following
        kwargs:

        *role*: str, default = '1D' (not plotted)
            The array's role. Can be 'x', 'y', 'yleft', 'yright', 'z' or '1D'
            for 1D arrays (one and only one x-axis array is required), '2D' for
            2D plots and '3D' for stacked 2D images. '0D' values are listed in
            the data tree. Unless has a '0D' role, each array will appear in
            `data location` dialog to be able to import it from a file.

        *raw*: str, default = array name
            Can define an intermediate array at the pipeline head when the main
            array (the key in *arrays*) is supposed to be obtained by an after
            load transformation. The plotted array is still the main one. The
            idea of having a *raw* version of an array is in the possibility of
            creating a transformation that not only begins at the first node
            but can also *end* at the first node.

        *qLabel*: str, default = array name
            Used in the GUI labels.

        *plotLabel*: str, or list of str, default = qLabel
            Axis label for the GUI plot. For 2D or 3D plots the 2- or 3-list
            that corresponds to the plot axes. The list may contain keys from
            *arrays* and then the label and unit are taken from that dictionary
            (the entry of *arrays*) or, alternatively, the list elements
            themselves are axis labels. For 0D values, this parameter may hold
            a format string to be used with the format() method.

        *qUnit*: str, default None
            Optional data unit to be displayed in the GUI.

        *plotUnit*: str, default = *qUnit*
            Attached to the plot label in parentheses. For example,
            for Å^-1: *qUnit* = u'Å\u207B\u00B9' and *plotUnit* = r'Å$^{-1}$'.

        *plotParams*: dict, default is `{}` that assumes thin solid lines
            Default parameters for plotting. Can have the following keys:
            *linewidth* (or *lw*), *style*, *symbol* and *symbolsize*. Note
            that color is set for a data item and is equal across the nodes, so
            it is set not here.

    *checkShapes*: list of str
        Can be useful at data file reading. If given, the list contains keys of
        *arrays*. The corresponding arrays will be checked for equal shape. The
        names of multidimensional arrays can be ended by a slice. Example:
        `checkShapes = ['theta', 'i0', 'xes3D[0]']`.

    *auxArrays*: list of lists
        Can be useful only for data export. Array names are grouped together so
        that the 1st element in a group is an x array and the others are y
        arrays. This grouping is respected only for the export of 1D data.

    """

    properties = ('qLabel', 'qUnit', 'raw', 'role', 'plotLabel', 'plotUnit',
                  'plotParams', 'ndim')
    defaultPlotParams = {'symbolsize': 2, 'linewidth': 1.3, 'linestyle': '-'}

    def __init__(self, widgetClass=None):
        u"""Instantiates the node and optionally passes a Qt widget class of a
        user dialog that defines transformation parameters."""

        for attr in ['name', 'arrays']:
            if not hasattr(self, attr):
                raise NotImplementedError(
                    "The class Node must be properly subclassed!")
        for array in self.arrays:
            for key in self.arrays[array]:
                self.get_prop(array, key)  # validate the keys
        if not hasattr(self, 'auxArrays'):
            self.auxArrays = []
        if not hasattr(self, 'checkShapes'):
            self.checkShapes = []
        self.widgetClass = widgetClass
        self.widget = None

        # filled automatically by transforms after creation of all nodes:
        self.upstreamNodes = []
        # filled automatically by transforms after creation of all nodes:
        self.downstreamNodes = []
        # filled automatically by transforms:
        self.transformsOut = []  # list of transforms from this node
        # assigned automatically by transform:
        self.transformIn = None
        csi.nodes[self.name] = self

        roles = self.get_arrays_prop('role')
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
                elif prl[0] == 'z':
                    self.plotZArray = key
            elif prl[0] == '0':
                self.arrays[key]['ndim'] = 0
            else:
                raise ValueError(
                    "unknown role '{0}' of arrays['{1}']".format(role, key))

        dims = self.get_arrays_prop('ndim')
        self.plotDimension = max(dims)

        added = 0
        if self.plotDimension == 1:
            for key, role in zip(self.arrays, roles):
                prl = role.lower()
                if prl[0] == 'y' or prl[0] == '0':
                    csi.modelDataColumns.append([self, key])
                    added += 1
        self.columnCount = added

    def is_between_nodes(
            self, nodeName1, nodeName2, node1in=True, node2in=True):
        u"""
        Returns True if this transformation node is between the given two nodes
        in the sense of data propagation in the pipeline. This method can be
        useful in creating the GUI part of a transformation node.

        *nodeName1* and *nodeName2*: Node
            *nodeName2* can be None, the right end is infinite then.

        *node1in* and *node2in*: bool
            define whether the interval is closed (when True) or open.
        """

        node1 = csi.nodes[nodeName1]
        node2 = csi.nodes[nodeName2] if nodeName2 else None
        ans = (node1 in self.upstreamNodes) or (node1in and (self is node1))
        if ans and (node2 is not None):
            ans = (node2 in self.downstreamNodes) or\
                (node2in and (self is node2))
        return ans

    def get_prop(self, arrayName, prop):
        u"""Returns the property *prop* for a given array name defined in this
        node. This method can be useful in creating the GUI part of a
        transformation node."""

        if prop not in self.properties:
            raise ValueError("unknown prop {0} in arrays['{1}']".format(
                prop, arrayName))

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
                prop, self.get_prop(arrayName, 'qLabel'))
        elif prop == 'plotUnit':
            return self.arrays[arrayName].get(
                prop, self.get_prop(arrayName, 'qUnit'))
        elif prop == 'plotParams':
            return self.arrays[arrayName].get(
                prop, dict(self.defaultPlotParams))
        elif prop == 'ndim':
            return self.arrays[arrayName].get(prop, 0)

    def get_arrays_prop(self, prop, arrays=[], role=''):
        """Get the property *prop* of several arrays, returned as a list. All
        arrays in the node are searched if *arrays* are not specified. The
        arrays can be restricted to those having a certain *role*."""
        scope = arrays if arrays else self.arrays
        if role:
            return [self.get_prop(key, prop) for key in scope
                    if self.get_prop(key, 'role').startswith(role)]
        else:
            return [self.get_prop(key, prop) for key in scope]
