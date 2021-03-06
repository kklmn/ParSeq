# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import sys
# import os
# import numpy as np

if sys.version_info < (3, 1):
    from inspect import getargspec
else:
    from inspect import getfullargspec as getargspec

import multiprocessing
import threading
import errno

from . import singletons as csi
from .config import configTransforms

_DEBUG = 10

# class Param(object):
#     def __init__(self, value, limits=[], step=None):
#         self.limits = limits
#         self.step = step
#         self.value = value

#     @property
#     def value(self):
#         return self._value

#     @value.setter
#     def value(self, val):
#         try:
#             if val < self.limits[0]:
#                 self._value = self.limits[0]
#             elif val > self.limits[1]:
#                 self._value = self.limits[1]
#             else:
#                 self._value = val
#         except (IndexError, TypeError):
#             self._value = val


class Transform(object):
    """Parental Transform class. Must be subclassed to define the following
    class variables:

    *name*: str.

    *defaultParams*: dict of default parameters of transform for new data.

    Transforms, if several are present, must be instantiated in the order of
    data flow.
    """
    nThreads = 1  # can be 'all' or 'half'
    nProcesses = 1  # can be 'all' or 'half'
    inArrays = []
    outArrays = []

    def __init__(self, fromNode, toNode, widgetClass=None):
        """
        *fromNode* and *toNode* are instances of :class:`core.nodes.Node`. They
        may be the same object.
        """
        if (not hasattr(self, 'name')) or (not hasattr(self, 'defaultParams')):
            raise NotImplementedError(
                "The class Transform must be properly subclassed")
        self.fromNode = fromNode
        self.toNode = toNode
        csi.transforms[self.name] = self

        if self not in fromNode.transformsOut:
            fromNode.transformsOut.append(self)
        toNode.transformIn = self
        self.widgetClass = widgetClass
        self.sendSignals = False
        self.read_ini_params()

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

    def read_ini_params(self):
        self.iniParams = self.defaultParams.copy()
        if configTransforms.has_section(self.name):
            for key in self.defaultParams:
                try:
                    testStr = configTransforms.get(self.name, key)
                except Exception:
                    self.iniParams[key] = self.defaultParams[key]
                    continue
                try:
                    self.iniParams[key] = eval(testStr)
                except (SyntaxError, NameError):
                    self.iniParams[key] = testStr

    def update_params(self, params, dataItems):
        for data in dataItems:
            for par in params:
                if par not in data.transformParams:
                    raise KeyError("Unknown parameter '{0}'".format(par))
                data.transformParams[par] = params[par]

    def run(self, params={}, updateUndo=True, runDownstream=True,
            dataItems=None):
        items = dataItems if dataItems is not None else csi.selectedItems
        self.run_pre(params, items, updateUndo)

        if isinstance(self.nThreads, type('')):
            tmp = multiprocessing.cpu_count()
            self.nThreads = tmp/2 if self.nThreads.startswith('h') else tmp
        if isinstance(self.nProcesses, type('')):
            tmp = multiprocessing.cpu_count()
            self.nProcesses = tmp/2 if self.nProcesses.startswith('h') else tmp

        if self.nThreads > 1:
            workerClass = BackendThread
            cpus = self.nThreads
            workerStr = 'thread'
        elif self.nProcesses > 1:
            workerClass = BackendProcess
            cpus = self.nProcesses
            workerStr = 'process'
        else:
            workerClass = None
        if workerClass is not None:
            workers, workedItems = [], []

        for idata, data in enumerate(items):
            if (data.isGood[self.fromNode.name] and
                self.fromNode.is_between_nodes(
                    data.originNode, data.terminalNode, node1in=True,
                    node2in=False)):
                if workerClass is not None:
                    worker = workerClass(self.__class__.run_main,
                                         self.inArrays, self.outArrays)
                    workers.append(worker)
                    workedItems.append(data)
                    if len(workers) == cpus or idata == len(items)-1:
                        if _DEBUG > 1:
                            print('run_main in {0} {1}{2} on {3}'.format(
                                len(workers), workerStr,
                                '' if len(workers) == 1 else 's',
                                [d.alias for d in workedItems]))
                        for worker, item in zip(workers, workedItems):
                            worker.put_in_data(item)
                            worker.start()
                            item.beingTransformed = True
                        if self.sendSignals:
                            csi.mainWindow.beforeDataTransformSignal.emit(
                                workedItems)
                        for worker, item in zip(workers, workedItems):
                            worker.get_out_data(item)
                            item.isGood[self.toNode.name] = \
                                worker.get_results(self)
                            item.beingTransformed = False
                        for worker in workers:
                            worker.join(60.)
                        if self.sendSignals:
                            csi.mainWindow.afterDataTransformSignal.emit(
                                workedItems)
                        workers, workedItems = [], []
                else:
                    data.beingTransformed = True
                    if self.sendSignals:
                        csi.mainWindow.beforeDataTransformSignal.emit([data])
                    if _DEBUG > 1:
                        print('run_main', self.name, data.alias)
                    args = getargspec(self.run_main)
                    if 'allData' in args[0]:
                        allData = csi.allLoadedItems
                        res = self.run_main(data, allData)
                    else:
                        res = self.run_main(data)
                    if isinstance(res, dict):
                        for field in res:
                            setattr(self, field, res[field])
                    data.isGood[self.toNode.name] = res is not None
                    data.beingTransformed = False
                    if self.sendSignals:
                        csi.mainWindow.afterDataTransformSignal.emit([data])
            else:
                data.isGood[self.toNode.name] = False
        self.run_post(runDownstream, items)

    def run_pre(self, params={}, dataItems=None, updateUndo=True):
        if params:
            # if updateUndo:
            #     self.push_to_undo_list(params, dataItems)
            self.update_params(params, dataItems)
        if self.sendSignals:
            csi.mainWindow.beforeTransformSignal.emit(self.toNode.widget)

    @staticmethod
    def run_main(data, allData):
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

        if self.sendSignals:
            csi.mainWindow.afterTransformSignal.emit(self.toNode.widget)

        if runDownstream:
            for tr in self.toNode.transformsOut:
                if self is tr:
                    continue
                tr.run(dataItems=dataItems)


class GenericProcessOrThread(object):
    def __init__(self, func, inArrays, outArrays):
        self.func = func
        self.inArrays = inArrays
        self.outArrays = outArrays
        # self.started_event.clear()
        # self.finished_event.clear()

    def put_in_data(self, item):
        if _DEBUG > 20:
            print('put_in_data', item.alias)
        res = {'transformParams': item.transformParams,
               'alias': item.alias}
        for key in self.inArrays:
            res[key] = getattr(item, key)
        if _DEBUG > 20:
            print('put_in_data keys', res.keys())
        self.inDataQueue.put(res)

    def get_in_data(self, item):
        if _DEBUG > 20:
            print('get_in_data enter')
        outDict = retry_on_eintr(self.inDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])
        if _DEBUG > 20:
            print('get_in_data exit', item.alias)

    def put_out_data(self, item):
        res = {'transformParams': item.transformParams}
        for key in self.outArrays:
            try:
                res[key] = getattr(item, key)
            except AttributeError:
                pass
        if _DEBUG > 20:
            print('put_out_data keys', res.keys())
        self.outDataQueue.put(res)

    def get_out_data(self, item):
        if _DEBUG > 20:
            print('get_out_data enter')
        outDict = retry_on_eintr(self.outDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])
        if _DEBUG > 20:
            print('get_out_data exit', item.alias)

    def put_results(self, obj):
        self.resultQueue.put(obj)

    def get_results(self, obj):
        res = retry_on_eintr(self.resultQueue.get)
        if isinstance(res, dict):
            for field in res:
                setattr(obj, field, res[field])
        return res is not None

    def run(self):
        # self.started_event.set()
        if _DEBUG > 20:
            print('enter run')
        data = DataProxy()
        self.get_in_data(data)
        res = self.func(data)
        self.put_results(res)
        self.put_out_data(data)
        if _DEBUG > 20:
            print('exit run', data.alias)
        # self.started_event.clear()
        # self.finished_event.set()


def retry_on_eintr(function, *args, **kw):
    """
    Suggested in:
    http://mail.python.org/pipermail/python-list/2011-February/1266462.html
    as a solution for `IOError: [Errno 4] Interrupted system call` in Linux.
    """
    while True:
        try:
            return function(*args, **kw)
        except IOError as e:
            if e.errno == errno.EINTR:
                continue
            else:
                raise


class DataProxy(object):
    """An empty object to attach fields to it. With a simple instance of
    object() this is impossible but doable with an empty class."""
    pass


class BackendProcess(GenericProcessOrThread, multiprocessing.Process):
    def __init__(self, func, inArrays, outArrays):
        multiprocessing.Process.__init__(self)
        self.inDataQueue = multiprocessing.Queue()
        self.outDataQueue = multiprocessing.Queue()
        self.resultQueue = multiprocessing.Queue()
        # self.started_event = multiprocessing.Event()
        # self.finished_event = multiprocessing.Event()
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)


class BackendThread(GenericProcessOrThread, threading.Thread):
    def __init__(self, func, inArrays, outArrays):
        threading.Thread.__init__(self)
        if sys.version_info < (3, 1):
            import Queue
        else:
            import queue
            Queue = queue

        self.inDataQueue = Queue.Queue()
        self.outDataQueue = Queue.Queue()
        self.resultQueue = Queue.Queue()
        # self.started_event = threading.Event()
        # self.finished_event = threading.Event()
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)
