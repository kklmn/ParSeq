# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "23 Jul 2021"
# !!! SEE CODERULES.TXT !!!

import sys
# import os
import numpy as np

import traceback
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

    def __init__(self, fromNode, toNode):
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
        self.isHeadNode = len(csi.transforms) == 0
        csi.transforms[self.name] = self

        if self not in fromNode.transformsOut:
            fromNode.transformsOut.append(self)
        toNode.transformIn = self
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
        # data = csi.selectedItems[0]
        # dtparams = data.transformParams

    def run(self, params={}, updateUndo=True, runDownstream=True,
            dataItems=None):
        np.seterr(all='raise')
        if csi.DEBUG_LEVEL > 20:
            print('enter run() of "{0}"'.format(self.name))
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
            if (not self.isHeadNode and
                    data.state[self.fromNode.name] == cco.DATA_STATE_BAD):
                data.state[self.toNode.name] = cco.DATA_STATE_BAD
                if csi.DEBUG_LEVEL > 20:
                    print('bad data at', self.fromNode.name, data.alias)
                continue
            elif data.state[self.fromNode.name] == cco.DATA_STATE_NOTFOUND:
                if csi.DEBUG_LEVEL > 20:
                    print('data not found', data.alias)
                continue

            if data.transformNames == 'each':
                if not (self.fromNode.is_between_nodes(
                            data.originNodeName, data.terminalNodeName) and
                        self.toNode.is_between_nodes(
                            data.originNodeName, data.terminalNodeName)):
                    data.state[self.toNode.name] = cco.DATA_STATE_UNDEFINED
                    if csi.DEBUG_LEVEL > 20:
                        print(data.alias, 'not between "{0}" and "{1}"'.format(
                            self.fromNode.name, self.toNode.name))
                    continue
                # if not data.state[self.fromNode.name] == cco.DATA_STATE_GOOD:
                #     continue
            elif isinstance(data.transformNames, (tuple, list)):
                if self.name not in data.transformNames:
                    data.state[self.toNode.name] = cco.DATA_STATE_UNDEFINED
                    if csi.DEBUG_LEVEL > 20:
                        print(data.alias, 'not between "{0}" and "{1}"'.format(
                            self.fromNode.name, self.toNode.name))
                    continue
            else:
                raise ValueError('unknown `transformNames`="{0}" for "{1}"'
                                 .format(data.transformNames, data.alias))

            args = getargspec(self.__class__.run_main)[0]
            if args[0] == 'self':
                print('IMPORTANT!: remove "self" from "run_main()" '
                      'parameters as this is a static method, '
                      'not an instance method')
            if workerClass is not None:
                worker = workerClass(
                    self.__class__.run_main, self.__class__.name,
                    self.inArrays, self.outArrays)
                workers.append(worker)
                workedItems.append(data)
                if len(workers) == cpus or idata == len(items)-1:
                    if csi.DEBUG_LEVEL > 1:
                        print('run "{0}" in {1} {2}{3} for {4}'.format(
                            self.name, len(workers), workerStr,
                            '' if len(workers) == 1 else 's',
                            [d.alias for d in workedItems]))
                    if self.sendSignals:
                        csi.mainWindow.beforeDataTransformSignal.emit(
                            workedItems)

                    for worker, item in zip(workers, workedItems):
                        worker.put_in_data(item)
                        worker.start()
                        item.beingTransformed = True
                    for worker, item in zip(workers, workedItems):
                        worker.get_out_data(item)
                        res = worker.get_results(self)
                        item.state[self.toNode.name] = cco.DATA_STATE_GOOD\
                            if res else cco.DATA_STATE_BAD
                        item.error = worker.get_error()
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
                    print('run "{0}" for {1}'.format(self.name, data.alias))
                # args = getargspec(self.run_main)
                try:
                    if 'allData' in args:
                        allData = csi.allLoadedItems
                        res = self.run_main(data, allData)
                    else:
                        res = self.run_main(data)
                    data.error = None
                except Exception:
                    res = None
                    errorMsg = 'failed "{0}" transform for data: {1}'.format(
                        self.name, data.alias)
                    errorMsg += "\nwith the followith traceback:\n"
                    tb = traceback.format_exc()
                    errorMsg += "".join(tb[:-1])  # remove last empty line
                    if csi.DEBUG_LEVEL > 20:
                        print(errorMsg)
                    data.error = errorMsg
                if isinstance(res, dict):
                    for field in res:
                        setattr(self, field, res[field])
                data.state[self.toNode.name] = cco.DATA_STATE_GOOD \
                    if res is not None else cco.DATA_STATE_BAD
                data.beingTransformed = False
                if self.sendSignals:
                    csi.mainWindow.afterDataTransformSignal.emit([data])

        postItems = [it for it in items
                     if it.state[self.toNode.name] == cco.DATA_STATE_GOOD]
        self.run_post(postItems, runDownstream)
        if csi.DEBUG_LEVEL > 20:
            print('exit run() of "{0}"'.format(self.name))
        np.seterr(all='warn')

        return [it for it in items if it.error is not None]  # error items

    def run_pre(self, params={}, dataItems=None, updateUndo=True):
        if params:
            # if updateUndo:
            #     self.push_to_undo_list(params, dataItems)
            self.update_params(params, dataItems)
        if hasattr(self.toNode, 'widget'):
            if self.toNode.widget is not None:
                self.toNode.widget.onTransform = True
        if self.sendSignals:
            csi.mainWindow.beforeTransformSignal.emit(self.toNode.widget)

    @staticmethod
    def run_main(data, allData):
        """The actual functionality of Transform comes here."""
        raise NotImplementedError  # must be overridden

    def run_post(self, dataItems, runDownstream=True):
        # do data.calc_combined() if a member of data.combinesTo has
        # its originNode as toNode:
        toBeUpdated = []
        for data in dataItems:
            for d in data.combinesTo:
                if data.state[self.toNode.name] == cco.DATA_STATE_BAD:
                    d.state[self.toNode.name] = cco.DATA_STATE_BAD
                    continue
                if (csi.nodes[d.originNodeName] is self.toNode) and \
                        (d not in toBeUpdated):
                    toBeUpdated.append(d)
        for d in toBeUpdated:
            d.calc_combined()

        if self.sendSignals:
            csi.mainWindow.afterTransformSignal.emit(self.toNode.widget)
        if hasattr(self.toNode, 'widget'):
            if self.toNode.widget is not None:
                self.toNode.widget.onTransform = False

        if runDownstream:
            for tr in self.toNode.transformsOut:
                if self is tr:
                    continue
                newItems = dataItems.copy()
                for data in dataItems:
                    if data.branch is not None:
                        newItems += [it for it in data.branch.get_items()
                                     if it not in newItems]
                tr.run(dataItems=newItems)


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
                print('for spectrum {0}'.format(item.alias))
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
            except AttributeError:  # arrays can be conditionally missing
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

    def put_error(self, obj):
        self.errorQueue.put(obj)

    def get_error(self):
        return retry_on_eintr(self.errorQueue.get)

    def run(self):
        # self.started_event.set()
        if csi.DEBUG_LEVEL > 20:
            print('enter run of GenericProcessOrThread')
        np.seterr(all='raise')
        data = DataProxy()
        self.get_in_data(data)
        try:
            res = self.func(data)
            self.put_results(res)
            self.put_error(None)
        except Exception:
            self.put_results(None)
            errorMsg = 'Failed "{0}" transform for data: {1}'.format(
                self.transformName, data.alias)
            errorMsg += "\nwith the followith traceback:\n"
            tb = traceback.format_exc()
            errorMsg += "".join(tb[:-1])  # remove last empty line
            self.put_error(errorMsg)
            if csi.DEBUG_LEVEL > 20:
                print(errorMsg)
        finally:
            self.put_out_data(data)
            if csi.DEBUG_LEVEL > 20:
                print('exit run of GenericProcessOrThread', data.alias)
            np.seterr(all='warn')
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
    def __init__(self, func, transformName, inArrays, outArrays):
        multiprocessing.Process.__init__(self)
        self.transformName = transformName
        self.multiName = 'multiprocessing'
        self.inDataQueue = multiprocessing.Queue()
        self.outDataQueue = multiprocessing.Queue()
        self.resultQueue = multiprocessing.Queue()
        self.errorQueue = multiprocessing.Queue()
        # self.started_event = multiprocessing.Event()
        # self.finished_event = multiprocessing.Event()
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)


class BackendThread(GenericProcessOrThread, threading.Thread):
    def __init__(self, func, transformName, inArrays, outArrays):
        threading.Thread.__init__(self)
        self.transformName = transformName
        self.multiName = 'multithreading'
        if sys.version_info < (3, 1):
            import Queue
        else:
            import queue
            Queue = queue

        self.inDataQueue = Queue.Queue()
        self.outDataQueue = Queue.Queue()
        self.resultQueue = Queue.Queue()
        self.errorQueue = Queue.Queue()
        # self.started_event = threading.Event()
        # self.finished_event = threading.Event()
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)
