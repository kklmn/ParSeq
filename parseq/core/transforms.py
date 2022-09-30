# -*- coding: utf-8 -*-
u"""
Data transformations
--------------------

Data transformations provide values for all the arrays defined in one
transformation node given arrays defined in another transformation node. Each
transformation defines a dictionary of transformation parameters; the values of
these parameters are individual per data item. Each transformation in a
pipeline requires subclassing from :class:`Transform`.
"""
__author__ = "Konstantin Klementiev"
__date__ = "24 Sep 2022"
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

import time
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
    u"""
    Parental Transform class. Must be subclassed to define the following class
    variables:

    *name*: str name that must be unique within the pipeline.

    *defaultParams*: dict of default transformation parameters for new data.

    Transforms, if several are present, must be instantiated in the order of
    data flow.

    The method :meth:`run_main` must be declared with @staticmethod
    decorator. A returned not None value indicates success.

    *nThreads* or *nProcesses* can be > 1 to use threading or multiprocessing.
    If both are > 1, threading is used. If *nThreads* or *nProcesses* > 1, the
    lists *inArrays* and *outArrays* must be defined to send the operational
    arrays (those used in :meth:`run_main`) over process-shared queues. The
    value can be an integer, 'all' or 'half' which refer to the hardware limit
    `multiprocessing.cpu_count()`.

    *progressTimeDelta*, float, default 1.0 sec, a timeout delta to report on
    transformation progress. Only needed if :meth:`run_main` is defined with
    a parameter *progress*.
    """

    nThreads = 1
    nProcesses = 1
    inArrays = []
    outArrays = []
    progressTimeDelta = 1.0  # sec

    def __init__(self, fromNode, toNode):
        """
        *fromNode* and *toNode* are instances of :class:`.Node`. They may be
        the same object.
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

    def _get_progress1(self, alias, progress):
        if hasattr(self.toNode, 'widget'):
            if self.toNode.widget is not None:
                self.toNode.widget.tree.transformProgress.emit(
                    [alias, progress.value])

    def _get_progressN(self, alias, worker):
        if hasattr(self.toNode, 'widget'):
            if self.toNode.widget is not None:
                ps = worker.get_progress()
                if len(ps) == 0:
                    return
                self.toNode.widget.tree.transformProgress.emit([alias, ps[-1]])

    def _run_multi_worker(self, workers, workedItems, args):
        wt = workers[0].workerType
        if csi.DEBUG_LEVEL > 1:
            print('run "{0}" in {1} {2}{3} for {4}'.format(
                self.name, len(workers), wt, '' if len(workers) == 1 else 's',
                [d.alias for d in workedItems]))
        if self.sendSignals:
            csi.mainWindow.beforeDataTransformSignal.emit(workedItems)

        for worker, item in zip(workers, workedItems):
            if not worker.put_in_data(item):
                item.state[self.toNode.name] = cco.DATA_STATE_BAD
                item.beingTransformed = False
                continue
            else:
                item.beingTransformed = True
            if 'progress' in args and self.sendSignals:
                worker.timer = NTimer(
                    self.progressTimeDelta,
                    self._get_progressN, [item.alias, worker])
                worker.timer.start()
            worker.start()
            item.transfortm_t0 = time.time()

        for worker, item in zip(workers, workedItems):
            if not item.beingTransformed:
                continue
            worker.get_out_data(item)
            res = worker.get_results(self)
            item.state[self.toNode.name] = cco.DATA_STATE_GOOD\
                if res else cco.DATA_STATE_BAD
            item.error = worker.get_error()
            item.transfortmTimes[self.name] = time.time() - item.transfortm_t0

        for worker, item in zip(workers, workedItems):
            if 'progress' in args and self.sendSignals:
                worker.timer.cancel()
            if not item.beingTransformed:
                continue
            worker.join(60.)
            item.beingTransformed = False

        if self.sendSignals:
            csi.mainWindow.afterDataTransformSignal.emit(workedItems)

    def _run_single_worker(self, data, args):
        data.beingTransformed = True
        data.transfortm_t0 = time.time()
        if self.sendSignals:
            csi.mainWindow.beforeDataTransformSignal.emit([data])
        if csi.DEBUG_LEVEL > 1:
            print('run "{0}" for {1}'.format(self.name, data.alias))
        try:
            argVals = [data]
            if 'allData' in args:
                allData = csi.allLoadedItems
                argVals.append(allData)
            if 'progress' in args:
                progress = DataProxy()
                progress.value = 1.
                argVals.append(progress)
                timer = NTimer(self.progressTimeDelta, self._get_progress1,
                               [data.alias, progress])
                timer.start()
            else:
                timer = None
            res = self.run_main(*argVals)
            if timer is not None:
                timer.cancel()
            data.error = None
        except Exception:
            if timer is not None:
                timer.cancel()
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
        data.transfortmTimes[self.name] = \
            time.time() - data.transfortm_t0
        if self.sendSignals:
            csi.mainWindow.afterDataTransformSignal.emit([data])

    def run(self, params={}, updateUndo=True, runDownstream=True,
            dataItems=None):
        np.seterr(all='raise')
        if csi.DEBUG_LEVEL > 20:
            print('enter run() of "{0}"'.format(self.name))
        items = dataItems if dataItems is not None else csi.selectedItems
        self.run_pre(params, items, updateUndo)

        nC = multiprocessing.cpu_count()
        if isinstance(self.nThreads, type('')):
            self.nThreads = nC//2 if self.nThreads.startswith('h') else nC
        if isinstance(self.nProcesses, type('')):
            self.nProcesses = nC//2 if self.nProcesses.startswith('h') else nC

        if self.nThreads > 1:
            workerClass = BackendThread
            cpus = self.nThreads
        elif self.nProcesses > 1:
            workerClass = BackendProcess
            cpus = self.nProcesses
        else:
            workerClass = None
        if workerClass is not None:
            workers, workedItems = [], []

        args = getargspec(self.__class__.run_main)[0]
        if 'allData' in args and workerClass is not None:
            raise SyntaxError(
                'IMPORTANT: remove "allData" when running in multithreading'
                ' or multiprocessing!')
        if args[0] == 'self':
            raise SyntaxError(
                'IMPORTANT: remove "self" from "run_main()" parameters as'
                ' this is a static method, not an instance method!')

        for data in items:
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
                    if data.dataType != cco.DATA_COMBINATION:
                        data.state[self.toNode.name] = cco.DATA_STATE_UNDEFINED
                    if csi.DEBUG_LEVEL > 20:
                        print(data.alias, 'not between "{0}" and "{1}"'.format(
                            self.fromNode.name, self.toNode.name))
                    continue
                # if not data.state[self.fromNode.name] == cco.DATA_STATE_GOOD:
                #     continue
            elif isinstance(data.transformNames, (tuple, list)):
                if self.name not in data.transformNames:
                    if data.dataType != cco.DATA_COMBINATION:
                        data.state[self.toNode.name] = cco.DATA_STATE_UNDEFINED
                    if csi.DEBUG_LEVEL > 20:
                        print(data.alias, 'not between "{0}" and "{1}"'.format(
                            self.fromNode.name, self.toNode.name))
                    continue
            else:
                raise ValueError('unknown `transformNames`="{0}" for "{1}"'
                                 .format(data.transformNames, data.alias))

            if workerClass is not None:  # with multipro
                worker = workerClass(
                    self.__class__.run_main, self.__class__.name,
                    self.inArrays, self.outArrays, self.progressTimeDelta)
                workers.append(worker)
                workedItems.append(data)
                if len(workers) == cpus:
                    self._run_multi_worker(workers, workedItems, args)
                    workers, workedItems = [], []
            else:  # no multipro
                self._run_single_worker(data, args)
        if workerClass is not None:  # with multipro on remaining workedItems
            if len(workers) > 0:
                self._run_multi_worker(workers, workedItems, args)

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
    def run_main(data):
        u"""
        Provides the actual functionality of the class.
        Other possible signatures:

        | run_main(data, allData, progress)
        | run_main(data, allData)
        | run_main(data, progress)

        *data* is a data item, instance of :class:`.Spectrum`.

        *allData* and *progress* are both optional in the method’s signature.
        The keyword names must be kept as given above if they are used and must
        be in this given order if both are present.

        *allData* is a list of all data items living in the data model. If
        *allData* is needed, both *nThreads* or *nProcesses* must be set to 1.

        *progress* is an object having a field `value`. A heavy transformation
        should periodically update this field, like this:
        :code:`progress.value = 0.5` (means 50% completion). If used with GUI,
        progress will be visualized as an expanding colored background
        rectangle in the data tree. Quick transformations do not need progress
        reporting.

        Should an error happen during the transformation, the error state will
        be notified in the ParSeq status bar and the traceback will be shown in
        the data item's tooltip in the data tree view.
        """
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
        if toBeUpdated:
            for d in toBeUpdated:
                d.calc_combined()
            if self.fromNode.name == self.toNode.name:
                self.run(dataItems=toBeUpdated, runDownstream=False)

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
                newItems += [it for it in toBeUpdated if it not in newItems]
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
                print('{0} for spectrum {1}'.format(e, item.alias))
                # raise e
                return False
        if csi.DEBUG_LEVEL > 20:
            print('put_in_data keys', item.alias, res.keys())
        self.inDataQueue.put(res)
        return True

    def get_in_data(self, item):
        outDict = retry_on_eintr(self.inDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])
        if csi.DEBUG_LEVEL > 20:
            print('get_in_data exit', item.alias, outDict.keys())

    def put_out_data(self, item):
        if csi.DEBUG_LEVEL > 20:
            print('put_out_data enter', item.alias)
        res = {'transformParams': item.transformParams}
        for key in self.outArrays:
            try:
                res[key] = getattr(item, key)
            except AttributeError:  # arrays can be conditionally missing
                pass
        if csi.DEBUG_LEVEL > 20:
            print('put_out_data exit', item.alias, res.keys())
        self.outDataQueue.put(res)

    def get_out_data(self, item):
        if csi.DEBUG_LEVEL > 20:
            print('get_out_data enter', item.alias)
        outDict = retry_on_eintr(self.outDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])
        if csi.DEBUG_LEVEL > 20:
            print('get_out_data exit', item.alias, outDict.keys())

    def put_results(self, obj):
        self.resultQueue.put(obj)

    def get_results(self, obj):
        if csi.DEBUG_LEVEL > 20:
            print('get_results enter', obj.name)
        res = retry_on_eintr(self.resultQueue.get)
        if isinstance(res, dict):
            for field in res:
                setattr(obj, field, res[field])
        if csi.DEBUG_LEVEL > 20:
            print('get_results exit', obj.name, res)
        return res is not None

    def put_error(self, obj):
        self.errorQueue.put(obj)

    def get_error(self):
        return retry_on_eintr(self.errorQueue.get)

    def put_progress(self):
        self.progressQueue.put_nowait(self.progress.value)

    def get_progress(self):
        values = []
        try:
            while not self.progressQueue.empty():
                values.append(retry_on_eintr(self.progressQueue.get_nowait))
        except Exception:
            pass
        return values

    def run(self):
        # self.started_event.set()
        if csi.DEBUG_LEVEL > 20:
            print('enter run of GenericProcessOrThread')
        np.seterr(all='raise')
        data = DataProxy()
        self.get_in_data(data)
        try:
            args = getargspec(self.func)[0]
            if 'progress' in args:
                self.progress = DataProxy()
                self.progress.value = 1.
                timer = NTimer(self.progressTimeDelta, self.put_progress)
                timer.start()
                res = self.func(data, self.progress)
                timer.cancel()
                self.progress.value = 1.
                self.put_progress()
            else:
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
    def __init__(self, func, transformName, inArrays, outArrays,
                 progressTimeDelta):
        multiprocessing.Process.__init__(self)
        self.transformName = transformName
        self.progressTimeDelta = progressTimeDelta
        self.multiName = 'multiprocessing'
        self.workerType = 'process'
        self.inDataQueue = multiprocessing.Queue()
        self.outDataQueue = multiprocessing.Queue()
        self.resultQueue = multiprocessing.Queue()
        self.errorQueue = multiprocessing.Queue()
        # self.started_event = multiprocessing.Event()
        # self.finished_event = multiprocessing.Event()
        self.progressQueue = multiprocessing.Queue()
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)


class BackendThread(GenericProcessOrThread, threading.Thread):
    def __init__(self, func, transformName, inArrays, outArrays,
                 progressTimeDelta):
        threading.Thread.__init__(self)
        self.transformName = transformName
        self.progressTimeDelta = progressTimeDelta
        self.multiName = 'multithreading'
        self.workerType = 'thread'
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
        self.progressQueue = Queue.Queue()
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)


class NTimer(threading.Timer):
    def run(self):
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


def connect_combined(items, parentItem):
    """Used at project loading to connect combined data to underlying data."""
    toBeUpdated = []
    for item in items:
        if isinstance(item.madeOf, (list, tuple)):  # combined
            newMadeOf = []
            for itemName in item.madeOf:
                if isinstance(itemName, str):
                    dataItem = parentItem.find_data_item(itemName)
                    newMadeOf.append(dataItem)
                    if item not in dataItem.combinesTo:
                        dataItem.combinesTo.append(item)
            if newMadeOf:
                item.madeOf = newMadeOf
                toBeUpdated.append(item)
    try:
        for d in toBeUpdated:
            d.calc_combined()
    except AttributeError:
        pass


def run_transforms(items, parentItem):
    topItems = [it for it in items if it in parentItem.childItems]
    bottomItems = [it for it in items if it not in parentItem.childItems
                   and (not isinstance(it.madeOf, (dict, list, tuple)))]
    # dependentItems = [it for it in items if it not in parentItem.childItems
    #                   and isinstance(it.madeOf, (dict, list, tuple))]

    # first bottomItems, then topItems...:
    if len(csi.transforms.values()) > 0:
        tr = list(csi.transforms.values())[0]
        if csi.transformer is not None:  # with a threaded transform
            csi.transformer.prepare(
                tr, dataItems=bottomItems+topItems, starter=tr.widget)
            csi.transformer.thread().start()
        else:  # in the same thread
            tr.run(dataItems=bottomItems+topItems)
            if hasattr(tr, 'widget'):  # when with GUI
                tr.widget.replotAllDownstream(tr.name)

    # no need for this, it is invoked in run_post:
    # # ...then dependentItems:
    # if len(csi.transforms.values()) > 0:
    #     tr = list(csi.transforms.values())[0]
    #     if csi.transformer is not None:  # with a threaded transform
    #         csi.transformer.prepare(
    #             tr, dataItems=dependentItems, starter=tr.widget)
    #         csi.transformer.thread().start()
    #     else:  # in the same thread
    #         tr.run(dataItems=dependentItems)
    #         tr.widget.replotAllDownstream(tr.name)
