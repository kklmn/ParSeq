# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "23 Jul 2021"
# !!! SEE CODERULES.TXT !!!

import sys
# import os
# import numpy as np

import types
if sys.version_info < (3, 1):
    from inspect import getargspec
else:
    from inspect import getfullargspec as getargspec

import multiprocessing
import threading
import errno

from . import singletons as csi
from . import commons as cco
from .config import configTransforms


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
        The name must be unique.

    *defaultParams*: dict of default parameters of transform for new data.

    Transforms, if several are present, must be instantiated in the order of
    data flow.

    The method run_main(data) must be declared with @staticmethod. It returns
    True if the transformation is successful otherwise it returns False.

    *nThreads* or *nProcesses* can be > 1 to use threading or multiprocessing.
    If both are > 1, threading is used. If *nThreads* or *nProcesses* > 1, the
    lists *inArrays* and *outArrays* must be defined to send those arrays over
    process-shared queues.

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

        if not isinstance(self.run_main, types.FunctionType):
            raise NotImplementedError(
                "The method run_main() of {0} must be declared with "
                "@staticmethod".format(self.__class__))

        self.fromNode = fromNode
        self.toNode = toNode
        if self.name in csi.transforms:
            raise ValueError("A transform '{0}' already exists. One instance "
                             "is allowed".format(self.name))
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
            nC = multiprocessing.cpu_count()
            self.nThreads = nC//2 if self.nThreads.startswith('h') else nC
        if isinstance(self.nProcesses, type('')):
            nC = multiprocessing.cpu_count()
            self.nProcesses = nC//2 if self.nProcesses.startswith('h') else nC

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
            if (data.state[self.fromNode.name] == cco.DATA_STATE_GOOD and
                self.fromNode.is_between_nodes(
                    data.originNode, data.terminalNode, node1in=True,
                    node2in=False)):
                args = getargspec(self.__class__.run_main)[0]
                if args[0] == 'self':
                    print('IMPORTANT!: remove "self" from "run_main()" '
                          'parameters as this is a static method, '
                          'not an instance method')
                if workerClass is not None:
                    worker = workerClass(self.__class__.run_main,
                                         self.inArrays, self.outArrays)
                    workers.append(worker)
                    workedItems.append(data)
                    if len(workers) == cpus or idata == len(items)-1:
                        if csi.DEBUG_LEVEL > 1:
                            print('run {0} in {1} {2}{3} for {4}'.format(
                                self.name, len(workers), workerStr,
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
                            item.state[self.toNode.name] = cco.DATA_STATE_GOOD\
                                if worker.get_results(self) else\
                                cco.DATA_STATE_BAD
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
                    if csi.DEBUG_LEVEL > 1:
                        print('run {0} for {1}'.format(self.name, data.alias))
                    # args = getargspec(self.run_main)
                    if 'allData' in args:
                        allData = csi.allLoadedItems
                        res = self.run_main(data, allData)
                    else:
                        res = self.run_main(data)
                    if isinstance(res, dict):
                        for field in res:
                            setattr(self, field, res[field])
                    data.state[self.toNode.name] = cco.DATA_STATE_GOOD \
                        if res is not None else cco.DATA_STATE_BAD
                    data.beingTransformed = False
                    if self.sendSignals:
                        csi.mainWindow.afterDataTransformSignal.emit([data])
            else:
                data.state[self.toNode.name] = cco.DATA_STATE_BAD
        self.run_post(runDownstream, items)

    def run_pre(self, params={}, dataItems=None, updateUndo=True):
        if params:
            # if updateUndo:
            #     self.push_to_undo_list(params, dataItems)
            self.update_params(params, dataItems)
        if hasattr(self.toNode, 'widget'):
            self.toNode.widget.onTransform = True
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
                if data.state[self.toNode.name] != cco.DATA_STATE_GOOD:
                    d.state[self.toNode.name] = cco.DATA_STATE_BAD
                    continue
                if (d.originNode is self.toNode) and (d not in toBeUpdated):
                    toBeUpdated.append(d)
        for d in toBeUpdated:
            d.calc_combined()

        if self.sendSignals:
            csi.mainWindow.afterTransformSignal.emit(self.toNode.widget)
        if hasattr(self.toNode, 'widget'):
            self.toNode.widget.onTransform = False

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
        if csi.DEBUG_LEVEL > 20:
            print('put_in_data', item.alias)
        res = {'transformParams': item.transformParams,
               'alias': item.alias}
        for key in self.inArrays:
            try:
                res[key] = getattr(item, key)
            except AttributeError as e:
                print(e)
                print('also check the capitalization of array names in nodes '
                      'and transforms')
                raise e
        if csi.DEBUG_LEVEL > 20:
            print('put_in_data keys', res.keys())
        self.inDataQueue.put(res)

    def get_in_data(self, item):
        if csi.DEBUG_LEVEL > 20:
            print('get_in_data enter')
        outDict = retry_on_eintr(self.inDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])
        if csi.DEBUG_LEVEL > 20:
            print('get_in_data exit', item.alias)

    def put_out_data(self, item):
        res = {'transformParams': item.transformParams}
        for key in self.outArrays:
            try:
                res[key] = getattr(item, key)
            except AttributeError:
                pass
        if csi.DEBUG_LEVEL > 20:
            print('put_out_data keys', res.keys())
        self.outDataQueue.put(res)

    def get_out_data(self, item):
        if csi.DEBUG_LEVEL > 20:
            print('get_out_data enter')
        outDict = retry_on_eintr(self.outDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])
        if csi.DEBUG_LEVEL > 20:
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
        if csi.DEBUG_LEVEL > 20:
            print('enter run')
        data = DataProxy()
        self.get_in_data(data)
        try:
            res = self.func(data)
            self.put_results(res)
        except (TypeError, ValueError) as e:
            self.put_results(False)
            print('failed {0}: {1}'.format(self.func, e))
        finally:
            self.put_out_data(data)
            if csi.DEBUG_LEVEL > 20:
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
