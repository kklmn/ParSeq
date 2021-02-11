# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from . import singletons as csi


class Node(object):
    """Parental Node class. Must be subclassed to define the following class
    variables:

    *name*: the name of the GUI tab and also the section name in ini file.

    *arrays*: OrderedDict of dicts
        describes the arrays operated in this node. The keys are names of these
        arrays, the values are dictionaries optionally containg these kwargs:

        *qLabel*: str, default = array name (the key in *arrays*)
            used in the GUI labels

        *qUnit*: str, default = None (no displayed units)
            attached to the GUI labels in parentheses

        *raw*: str, default = array name
            can define an intermediate array at the pipeline head when the main
            array (the key in *arrays*) is supposed to be obtained by an after
            load transformation. The plotted array is still the main one.

        *plotRole*: str, default = '1D' (not plotted)
            the array's role in ploting, Can be 'x', 'yleft', 'yright' or '1D'
            for 1D arrays (one and only one x-axis array is required), '2D' for
            2D plots and '3D' for stacked 2D images.

        *plotLabel*: str, default = qLabel
            axis label for the GUI plot

        *plotUnit*: str: default = qUnit
            attached to the plot label in parentheses

        *plotParams*: dict , default is `{}` that assumes thin solid lines
            default parameters for plotting. Can have the following keys:
                *linewidth* (or *lw*), *style*, *symbol* and *symbolsize*.
            Note that color is set for a data entry and is equal across the
            nodes, so it is set not here.

    """

    def __init__(self):
        for attr in ['name', 'arrays']:
            if not hasattr(self, attr):
                raise NotImplementedError(
                    "The class Node must be properly subclassed!")
        for array in self.arrays:
            for key in self.arrays[array]:
                self.getProp(array, key)  # validate the keys

        # filled automatically by transforms after creation of all nodes:
        self.upstreamNodes = []
        # filled automatically by transforms after creation of all nodes:
        self.downstreamNodes = []
        # filled automatically by transforms:
        self.transformsOut = []  # list of transforms from this node
        # assigned automatically by transform:
        self.transformIn = None
        csi.nodes[self.name] = self

        plotRoles = self.getPropList('plotRole')
        for key, plotRole in zip(self.arrays, plotRoles):
            prl = plotRole.lower()
            if prl[0] == '3':
                self.arrays[key]['ndim'] = 3
                self.plot3DArray = key
            elif prl[0] == '2':
                self.arrays[key]['ndim'] = 2
                self.plot2DArray = key
            elif prl[0] in ('x', 'y', '1'):
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
            else:
                self.arrays[key]['ndim'] = 0

        dims = self.getPropList('ndim')
        self.plotDimension = max(dims)

        if self.plotDimension == 1:
            csi.modelDataColumns.extend(
                [(self, key) for key in self.plotYArrays])
            self.columnCount = len(self.plotYArrays)
        else:
            self.columnCount = 0

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
            return self.arrays[arrayName].get(prop, arrayName)
        elif prop == 'qUnit':
            return self.arrays[arrayName].get(prop, None)
        elif prop == 'raw':
            return self.arrays[arrayName].get(prop, arrayName)
        elif prop == 'plotRole':
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

    def getPropList(self, prop, keys=[], plotRole=''):
        scope = keys if keys else self.arrays
        if plotRole:
            return [self.getProp(key, prop) for key in scope
                    if self.getProp(key, 'plotRole').startswith(plotRole)]
        else:
            return [self.getProp(key, prop) for key in scope]
