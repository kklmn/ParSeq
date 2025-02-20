# -*- coding: utf-8 -*-
u"""
Data transformations
--------------------

Data transformations provide values for all the arrays defined in one
transformation node (`fromNode`) given arrays defined in another transformation
node (`toNode`). Each transformation defines a dictionary of transformation
parameters; the values of these parameters are individual per data item. Each
transformation in a pipeline requires subclassing from :class:`Transform`.
"""
__author__ = "Konstantin Klementiev"
__date__ = "28 Apr 2024"
# !!! SEE CODERULES.TXT !!!

import sys
import os
import numpy as np

import traceback
# import types
if sys.version_info < (3, 1):
    from inspect import getargspec
else:
    from inspect import getfullargspec as getargspec
if sys.version_info < (3, 2):
    from inspect import getattr as getattr_static
else:
    from inspect import getattr_static


import time
import multiprocessing
import threading
import errno

from . import singletons as csi
from . import commons as cco
from .logger import logger, syslogger
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

    The method :meth:`run_main()` must be declared either with @staticmethod or
    @classmethod decorator. A returned not None value indicates success.

    *nThreads* or *nProcesses* can be > 1 to use threading or multiprocessing.
    If both are > 1, threading is used. If *nThreads* or *nProcesses* > 1, the
    lists *inArrays* and *outArrays* must be defined to send the operational
    arrays (those used in :meth:`run_main`) over process-shared queues. The
    value can be an integer, 'all' or 'half' which refer to the hardware limit
    `multiprocessing.cpu_count()`.

    *progressTimeDelta*, float, default 1.0 sec, a timeout delta to report on
    transformation progress. Only needed if :meth:`run_main` is defined with
    a parameter *progress*.

    *dontSaveParamsWhenUnused*, dict, is a class variable that optionally
    defines transformation parameters to be removed from saved project files if
    those parameters are not used. The idea is to unclutter the saved project
    files. The dictionary binds a parameter with another parameter that serves
    as a usage switch. For example:
    {'selfAbsorptionCorrectionDict': 'selfAbsorptionCorrectionNeeded'}.
    """

    nThreads = 1
    nProcesses = 1
    inArrays = []
    outArrays = []
    progressTimeDelta = 1.0  # sec
    dontSaveParamsWhenUnused = dict()  # paramName=paramUsed

    def __init__(self, fromNode, toNode):
        """
        *fromNode* and *toNode* are instances of :class:`.Node`. They may be
        the same object.
        """
        if (not hasattr(self, 'name')) or (not hasattr(self, 'defaultParams')):
            raise NotImplementedError(
                "The class Transform must be properly subclassed")

        # isstatic = isinstance(self.run_main, types.FunctionType)
        isStatic = isinstance(getattr_static(self, "run_main"), staticmethod)
        isClass = isinstance(getattr_static(self, "run_main"), classmethod)
        if not (isStatic or isClass):
            raise NotImplementedError(
                "The method run_main() of {0} must be declared with either"
                "@staticmethod or @classmethod".format(self.__class__))

        self.fromNode = fromNode
        self.toNode = toNode
        if self.name in csi.transforms:
            raise ValueError("A transform '{0}' already exists. One instance "
                             "is allowed".format(self.name))
        self.isHeadTransform = len(csi.transforms) == 0
        csi.transforms[self.name] = self

        if self not in fromNode.transformsOut:
            fromNode.transformsOut.append(self)
        if self not in toNode.transformsIn:
            toNode.transformsIn.append(self)
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
                if '.' in par:
                    parSplits = par.split('.')
                    obj = data.transformParams
                    for parSplit in parSplits[:-1]:
                        obj = obj[parSplit]
                    paru = parSplits[-1]
                    if paru not in obj and not paru.startswith(
                            'correction_'):
                        raise KeyError(u"Unknown parameter '{0}'".format(paru))
                    obj[paru] = params[par]
                else:
                    if par not in data.transformParams and not par.startswith(
                            'correction_'):
                        raise KeyError(u"Unknown parameter '{0}'".format(par))
                    data.transformParams[par] = params[par]
        # data = csi.selectedItems[0]
        # dtparams = data.transformParams

    def _get_progress1(self, alias, progress):
        if not hasattr(self.toNode, 'widget'):
            return
        if self.toNode.widget is None:
            return
        self.toNode.widget.tree.transformProgress.emit([alias, progress.value])

    def _get_progressN(self, alias, worker=None):
        if not hasattr(self.toNode, 'widget'):
            return
        if self.toNode.widget is None:
            return
        if worker is None:
            self.toNode.widget.tree.transformProgress.emit([alias, 1.0])
        else:
            ps = worker.get_progress()
            if len(ps) == 0:
                return
            self.toNode.widget.tree.transformProgress.emit([alias, ps[-1]])

    @logger(minLevel=20, attrs=[(0, 'name')])
    def _run_multi_worker(self, workers, workedItems, args):
        wt = workers[0].workerType
        syslogger.info(
            'run "{0}" in {1} {2}{3}'.format(
                self.name, len(workers), wt, '' if len(workers) == 1 else 's'))
        if self.sendSignals:
            csi.mainWindow.beforeDataTransformSignal.emit(workedItems)

        for worker, item in zip(workers, workedItems):
            if 'progress' in args and self.sendSignals:
                worker.timer = NTimer(
                    self.progressTimeDelta,
                    self._get_progressN, [item.alias, worker])
                worker.timer.start()
            if not worker.put_in_data(item):
                item.state[self.toNode.name] = cco.DATA_STATE_BAD
                item.beingTransformed = False
                continue
            else:
                item.beingTransformed = self.name
            item.transfortm_t0 = time.time()
            worker.start()

        for worker, item in zip(workers, workedItems):
            if not item.beingTransformed:
                continue
            worker.get_out_data(item)
            res = worker.get_results(self)
            if isinstance(res, bool):
                item.state[self.toNode.name] = cco.DATA_STATE_GOOD\
                    if res else cco.DATA_STATE_BAD
            elif isinstance(res, int):
                item.state[self.toNode.name] = res
            item.error = worker.get_error()
            item.transfortmTimes[self.name] = time.time() - item.transfortm_t0

        for worker, item in zip(workers, workedItems):
            if 'progress' in args and self.sendSignals:
                worker.timer.cancel()
            if not item.beingTransformed:
                continue
            worker.join(60.)
            item.beingTransformed = False
            if 'progress' in args and self.sendSignals:
                self._get_progressN(item.alias)

        if self.sendSignals:
            csi.mainWindow.afterDataTransformSignal.emit(workedItems)

    @logger(minLevel=20, attrs=[(0, 'name')])
    def _run_single_worker(self, data, args):
        data.beingTransformed = self.name
        data.transfortm_t0 = time.time()
        if self.sendSignals:
            csi.mainWindow.beforeDataTransformSignal.emit([data])
        syslogger.info('run "{0}" for {1}'.format(self.name, data.alias))
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
            if 'progress' in args:
                progress.value = 1.
                self._get_progress1(data.alias, progress)
        except Exception:
            if timer is not None:
                timer.cancel()
            res = None
            errorMsg = 'failed "{0}" transform for data: {1}'.format(
                self.name, data.alias)
            errorMsg += "\nwith the following traceback:\n"
            tb = traceback.format_exc()
            errorMsg += "".join(tb[:-1])  # remove last empty line
            syslogger.log(100, errorMsg)
            data.error = errorMsg
        if res is None:
            data.state[self.toNode.name] = cco.DATA_STATE_BAD
        elif isinstance(res, dict):
            for field in res:
                setattr(self, field, res[field])
        elif isinstance(res, bool):
            data.state[self.toNode.name] = cco.DATA_STATE_GOOD \
                if res is not None else cco.DATA_STATE_BAD
        elif isinstance(res, int):
            data.state[self.toNode.name] = res
        data.beingTransformed = False
        data.transfortmTimes[self.name] = time.time() - data.transfortm_t0
        if self.sendSignals:
            csi.mainWindow.afterDataTransformSignal.emit([data])

    @logger(minLevel=20, attrs=[(0, 'name')])
    def run(self, params={}, updateUndo=True, runDownstream=True,
            dataItems=None):
        np.seterr(all='raise')
        items = dataItems if dataItems is not None else csi.selectedItems
        self.run_pre(params, items, updateUndo)

        nC = multiprocessing.cpu_count()
        if isinstance(self.nThreads, str):
            self.nThreads = max(nC//2, 1) if self.nThreads.startswith('h')\
                else nC
        if isinstance(self.nProcesses, str):
            self.nProcesses = max(nC//2, 1) if self.nProcesses.startswith('h')\
                else nC

        workerClass = None
        if len(items) > 1:
            if self.nThreads > 1:
                workerClass = BackendThread
                cpus = self.nThreads
            elif self.nProcesses > 1:
                workerClass = BackendProcess
                cpus = self.nProcesses
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
            # if (not self.isHeadTransform and
            #         data.state[self.fromNode.name] == cco.DATA_STATE_BAD):
            if data.state[self.fromNode.name] == cco.DATA_STATE_BAD:
                data.state[self.toNode.name] = cco.DATA_STATE_BAD
                syslogger.error('bad data {0} at {1}'.format(
                    data.alias, self.fromNode.name))
                continue
            elif data.state[self.fromNode.name] == cco.DATA_STATE_NOTFOUND:
                syslogger.error('data {0} not found'.format(data.alias))
                continue

            if data.transformNames == 'each':
                if not (self.fromNode.is_between_nodes(
                            data.originNodeName, data.terminalNodeName) and
                        self.toNode.is_between_nodes(
                            data.originNodeName, data.terminalNodeName)):
                    if data.dataType != cco.DATA_COMBINATION:
                        data.state[self.toNode.name] = cco.DATA_STATE_UNDEFINED
                    syslogger.info(
                        data.alias, 'not between "{0}" and "{1}"'.format(
                            self.fromNode.name, self.toNode.name))
                    continue
                # if not data.state[self.fromNode.name] == cco.DATA_STATE_GOOD:
                #     continue
            elif isinstance(data.transformNames, (tuple, list)):
                if self.name not in data.transformNames:
                    if data.dataType != cco.DATA_COMBINATION:
                        data.state[self.toNode.name] = cco.DATA_STATE_UNDEFINED
                    syslogger.info(
                        data.alias, 'not between "{0}" and "{1}"'.format(
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
            csi.mainWindow.afterTransformSignal.emit(self.fromNode.widget)
            csi.mainWindow.beforeTransformSignal.emit(self.toNode.widget)

        # do pre-corrections only for originNode:
        for data in dataItems:
            if data.originNodeName == self.fromNode.name:
                data.make_corrections(self.fromNode)

    # @staticmethod
    # def run_main(data):
    @classmethod
    def run_main(cls, data):
        u"""
        Provides the actual functionality of the class.
        Other possible signatures:

        | run_main(cls, data, allData, progress)
        | run_main(cls, data, allData)
        | run_main(cls, data, progress)

        *data* is a data item, instance of :class:`.Spectrum`.

        *allData* and *progress* are both optional in the method’s signature.
        The keyword names must be kept as given above if they are used and must
        be in this given order.

        *allData* is a list of all data items living in the data model. If
        *allData* is needed, both *nThreads* or *nProcesses* must be set to 1.

        *progress* is an object having a field `value`. A heavy transformation
        should periodically update this field, like this:
        :code:`progress.value = 0.5` (means 50% completion). If used with GUI,
        progress will be visualized as an expanding colored background
        rectangle in the data tree. Quick transformations do not need progress
        reporting.

        Should an error happen during the transformation, the error state will
        be reported in the ParSeq status bar and the traceback will be shown in
        the data item's tooltip in the data tree view.

        Returns True when successful. If returns an int, this int will be set
        as the data state at the destination node (the state is a dict of node
        names).
        """
        raise NotImplementedError  # must be overridden

    def run_post(self, dataItems, runDownstream=True):
        for data in dataItems:
            data.make_corrections(self.toNode)

        # do data.calc_combined() if a member of data.combinesTo has
        # its originNode as toNode:
        toBeUpdated = []
        for data in dataItems:
            for d in data.combinesTo:
                if data.state[self.toNode.name] == cco.DATA_STATE_BAD:
                    d.state[self.toNode.name] = cco.DATA_STATE_BAD
                    continue
                if d.originNodeName in [self.toNode.name, self.fromNode.name] \
                        and d not in toBeUpdated:
                    toBeUpdated.append(d)
        if toBeUpdated:
            for d in toBeUpdated:
                d.calc_combined()
            if d.originNodeName in [self.toNode.name, self.fromNode.name]:
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
                # for data in dataItems:
                #     if data.branch is not None:
                #         newItems += [it for it in data.branch.get_items()
                #                      if it not in newItems]
                tr.run(dataItems=newItems)


class GenericProcessOrThread(object):
    def __init__(self, func, inArrays, outArrays):
        self.func = func
        self.inArrays = inArrays
        self.outArrays = outArrays
        # self.started_event.clear()
        # self.finished_event.clear()

    @logger(minLevel=20, attrs=[(0, 'transformName'), (1, 'alias')])
    def put_in_data(self, item):
        res = {'transformParams': item.transformParams,
               'alias': item.alias}
        for key in self.inArrays:
            try:
                # if not hasattr(item, key):
                #     setattr(item, key, None)
                res[key] = getattr(item, key)
            except AttributeError as e:
                syslogger.error(
                    'Error in put_in_data() for spectrum {0}:\n{1}'.format(
                        item.alias, e))
                # raise e
                return False
                # res[key] = None
        self.inDataQueue.put(res)
        return True

    @logger(minLevel=20, attrs=[(0, 'transformName')])
    def get_in_data(self, item):
        outDict = retry_on_eintr(self.inDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])

    @logger(minLevel=20, attrs=[(0, 'transformName'), (1, 'alias')])
    def put_out_data(self, item):
        res = {'transformParams': item.transformParams}
        for key in self.outArrays:
            try:
                res[key] = getattr(item, key)
            except AttributeError:  # arrays can be conditionally missing
                pass
        self.outDataQueue.put(res)

    @logger(minLevel=20, attrs=[(0, 'transformName'), (1, 'alias')])
    def get_out_data(self, item):
        outDict = retry_on_eintr(self.outDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])

    def put_results(self, obj):
        self.resultQueue.put(obj)

    @logger(minLevel=20, attrs=[(0, 'transformName'), (1, 'name')])
    def get_results(self, obj):
        res = retry_on_eintr(self.resultQueue.get)
        if res is None:
            return False
        elif isinstance(res, dict):
            for field in res:
                setattr(obj, field, res[field])
            return True
        return res

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

    # @logger(minLevel=20, printClass=True)
    def run(self):
        # self.started_event.set()
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
            errorMsg += "\nwith the following traceback:\n"
            tb = traceback.format_exc()
            errorMsg += "".join(tb[:-1])  # remove last empty line
            self.put_error(errorMsg)
            syslogger.log(100, errorMsg)
        finally:
            self.put_out_data(data)
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

    def __repr__(self):
        return "DataProxy object for '{0}'".format(self.alias)


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
        sys.path.append(csi.parseqPath)  # to find parseq in multiprocessing
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)

    def run(self):
        sys.path.append(csi.parseqPath)  # to find parseq in multiprocessing
        GenericProcessOrThread.run(self)


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
        if (hasattr(item, 'madeOf') and  # instance of Spectrum
                isinstance(item.madeOf, (list, tuple))):  # combined
            newMadeOf = []
            for itemName in item.madeOf:
                if isinstance(itemName, str):
                    dataItem = parentItem.find_data_item(itemName)
                    if dataItem is not None:
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


def run_transforms(items, parentItem, runParallel=True):
    topItems = [it for it in items if it in parentItem.childItems]
    try:
        bottomItems = [it for it in items if it not in parentItem.childItems
                       and (not isinstance(it.madeOf, (dict, list, tuple)))]
    except AttributeError:  # can happen in tests
        bottomItems = [it for it in items if it not in parentItem.childItems]
    # dependentItems = [it for it in items if it not in parentItem.childItems
    #                   and isinstance(it.madeOf, (dict, list, tuple))]

    itemsByOrigin = {}
    for it in bottomItems+topItems:
        if it.originNodeName not in itemsByOrigin:
            itemsByOrigin[it.originNodeName] = [it]
        else:
            itemsByOrigin[it.originNodeName].append(it)

    for originNodeName, its in itemsByOrigin.items():
        for tr in csi.nodes[originNodeName].transformsOut:
            # first bottomItems, then topItems...:
            if (csi.tasker is not None) and len(itemsByOrigin) == 1 and \
                    runParallel:
                # with a threaded transform
                widget = tr.widget if hasattr(tr, 'widget') else None
                csi.tasker.prepare(
                    tr, runDownstream=True, dataItems=its, starter=widget)
                csi.tasker.thread().start()
            else:
                # if len(itemsByOrigin) > 1, the transforms cannot be
                # parallelized, so do it in the same thread:
                tr.run(dataItems=its)
                if hasattr(tr, 'widget'):  # when with GUI
                    tr.widget.replotAllDownstream(tr.name)

            if tr.fromNode is tr.toNode:
                break

            # # no need for dependentItems, it is invoked in run_post:
            # # ...then dependentItems:
            # if len(csi.transforms.values()) > 0:
            #     if csi.tasker is not None:  # with a threaded transform
            #         csi.tasker.prepare(
            #             tr, runDownstream=True, dataItems=dependentItems,
            #             starter=tr.widget)
            #         csi.tasker.thread().start()
            #     else:  # in the same thread
            #         tr.run(dataItems=dependentItems)
            #         tr.widget.replotAllDownstream(tr.name)
