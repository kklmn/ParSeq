# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from . import singletons as csi


class Node(object):
    """Parental Node class. Must be subclassed to define the following class
    variables:

    *name*: also the section name in ini file

    *xName*: str
        name of x array

    (*xQLabel*): str
        if exists, is used in the GUI labels, otherwise *xName* is taken.

    *xPlotLabel*: str
        x label for the GUI plot

    (*xQUnit*): str
        if exists, is attached to the GUI labels in parentheses, otherwise no
        unit is displayed in the GUI labels.

    (*xPlotUnit*): str
        if exists, is attached to the plot label in parentheses

    *yNames*: list of str
        names of y arrays

    (*yQLabels*): list of str
        if exist, are used in the GUI labels, otherwise *yNames* are taken.

    *yPlotLabels*: list of str
        y labels for the GUI plot

    (*yQUnits*): list of str
        if exist, are attached to the GUI labels in parentheses, otherwise no
        units are displayed in the GUI labels.

    (*yPlotUnits*): list of str
        if exist, are attached to the plot labels in parentheses

    (*xNameRaw*, *yNamesRaw*):
        can be used instead of *xName* and *yNames* at the pipeline head when
        *xName* and *yNames* are supposed to be obtained by an after load
        transformation. The plotted arrays are still *xName* and *yNames*.

    *plotParams*: dict of default parameters for plotting. Can have the
        following keys: *linewidth* (or *lw*), *style*, *symbol*, *symbolsize*
        and *yaxis*. The values must correspond to the length of *yNames*.
        Note that color is set for a data entry and is equal across the nodes,
        so it is set not here.

    """

    def __init__(self):
        for attr in ['name', 'xName', 'xPlotLabel', 'yNames', 'yPlotLabels',
                     'plotParams']:
            if not hasattr(self, attr):
                raise NotImplementedError(
                    "The class Node must be properly subclassed!")
        # filled automatically by transforms after creation of all nodes:
        self.upstreamNodes = []
        # filled automatically by transforms after creation of all nodes:
        self.downstreamNodes = []
        # filled automatically by transforms:
        self.transformsOut = []  # list of transforms from this node
        # assigned automatically by transform:
        self.transformIn = None
        csi.nodes[self.name] = self
        csi.modelColumns.extend([(self, yName) for yName in self.yNames])

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
