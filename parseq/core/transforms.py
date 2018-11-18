# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from . import singletons as csi
from .config import config, iniTransforms


#class Param(object):
#    def __init__(self, value, limits=[], step=None):
#        self.limits = limits
#        self.step = step
#        self.value = value
#
#    @property
#    def value(self):
#        return self._value
#
#    @value.setter
#    def value(self, val):
#        try:
#            if val < self.limits[0]:
#                self._value = self.limits[0]
#            elif val > self.limits[1]:
#                self._value = self.limits[1]
#            else:
#                self._value = val
#        except (IndexError, TypeError):
#            self._value = val


class Transform(object):
    """Parental Transform class. Must be subclassed to define the following
    class variables:

    *name*: str, used as section in config and key in data.transformParams dict

    *params*: dict of default parameters of transform for new data
    """

    def __init__(self, fromNode, toNode, widgetClass=None):
        if (not hasattr(self, 'name')) or (not hasattr(self, 'params')):
            raise NotImplementedError(
                "The class Transform must be properly subclassed")
        self.fromNode = fromNode
        self.toNode = toNode
        csi.transforms[self.name] = self

        if self not in fromNode.transformsOut:
            fromNode.transformsOut.append(self)
        toNode.transformIn = self

        self.widgetClass = widgetClass
        self.get_defaults()

        if fromNode is toNode:
            return

        # with guaranteed sorting
        grossDown = [toNode] + toNode.downstreamNodes
        fromNode.downstreamNodes.extend(
            n for n in grossDown if n not in fromNode.downstreamNodes)
        fromNode.downstreamNodes.sort(key=list(csi.nodes.values()).index)
        for node in fromNode.upstreamNodes:
            node.downstreamNodes.extend(
                n for n in grossDown if n not in node.downstreamNodes)
            node.downstreamNodes.sort(key=list(csi.nodes.values()).index)

        # with guaranteed sorting
        grossUp = fromNode.upstreamNodes + [fromNode]
        toNode.upstreamNodes.extend(
            n for n in grossUp if n not in toNode.upstreamNodes)
        toNode.upstreamNodes.sort(key=list(csi.nodes.values()).index)
        for node in toNode.downstreamNodes:
            node.upstreamNodes.extend(
                    n for n in grossUp if n not in node.upstreamNodes)
            node.upstreamNodes.sort(key=list(csi.nodes.values()).index)

    def get_defaults(self):
        config.read(iniTransforms)
        if config.has_section(self.name):
            for key in self.params:
                self.params[key] = eval(config.get(self.name, key))

    def set_defaults(self):
        if not config.has_section(self.name):
            config.add_section(self.name)
        for key in self.params:
            config.set(self.name, key, self.params[key])

    def update_params(self, params, dataItems):
        for data in dataItems:
            for par in params:
                if par not in data.transformParams[self.name]:
                    raise KeyError("Unknown parameter '{0}'. ".format(par))
                data.transformParams[self.name][par] = params[par]
        for par in params:
            self.params[par] = params[par]

#    def push_to_undo_list(self, params):
#        # Check for repeated change of parameters. Considered as repeated if
#        # same transform, same activeIndex and same set of params
#        if len(csi.undo) > 0:  # compare with the last record
#            lastUndo = csi.undo[-1]
#            isRepeated = ((lastUndo[0] is self) and
#                          (lastUndo[1] == csi.activeIndex) and
#                          (set(lastUndo[2]) == set(params)))  # set of keys
#            if isRepeated:
#                # update only the new params in the last entry without
#                # appending a new entry to undo list
#                lastUndo[2] = params
#                return
#
#        prev = []
#        for data in self.activeData:
#            curParams = data.transformParams[self.name]  # dict
#            modifiedParams = []  # list of keys
#            for par in params:
#                if curParams[par] != params[par]:
#                    modifiedParams.append(par)
#            if modifiedParams:
#                prev.append([data, {p: curParams[p] for p in modifiedParams}])
#        if prev:
#            csi.undo.append(
#                [self, csi.activeIndex, params, prev])

    def run(self, params={}, updateUndo=True, runDownstream=True,
            dataItems=None):
        items = dataItems if dataItems is not None else csi.selectedItems
        self.run_pre(params, items, updateUndo)
        for data in items:
            if (data.isGood[self.fromNode.name] and
                self.fromNode.is_between_nodes(
                    data.originNode, data.terminalNode, node1in=True,
                    node2in=False)):
                self.run_main(data)
            else:
                data.isGood[self.toNode.name] = False
        self.run_post(runDownstream, items)

    def run_pre(self, params={}, dataItems=None, updateUndo=True):
        if params:
#            if updateUndo:
#                self.push_to_undo_list(params)
            self.update_params(params, dataItems)

    def run_main(self, data):
        """The actual functionality of Transform comes here."""
        raise NotImplementedError  # must be overridden

    def run_post(self, runDownstream=True, dataItems=None):
        # do data.calc_combined() if a member of data.combinesTo has
        # its originNode as toNode:
        toBeUpdated = []
        for data in dataItems:
            for d in data.combinesTo:
                if not data.isGood[self.toNode.name]:
                    d.isGood[self.toNode.name] = False
                    continue
                if (d.originNode is self.toNode) and (d not in toBeUpdated):
                    toBeUpdated.append(d)
        for d in toBeUpdated:
            d.calc_combined()

        if runDownstream and not (self.fromNode is self.toNode):
            for tr in self.toNode.transformsOut:
                tr.run(dataItems=dataItems)
