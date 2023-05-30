# -*- coding: utf-8 -*-
u"""
Fitting workers
---------------

Fitting workers (fits) provide curve fitting. Each fit defines a dictionary of
fitting parameters; they are individual per data item. Each fit in a pipeline
requires subclassing from :class:`Fit`.
"""
__author__ = "Konstantin Klementiev"
__date__ = "30 May 2023"
# !!! SEE CODERULES.TXT !!!

import sys
# import os
import numpy as np
import time

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

import multiprocessing
import threading
import errno

from ..core import singletons as csi
from ..core.logger import logger
from ..core.config import configFits


class Fit:
    u"""
    Parental Fit class. Must be subclassed to define the following class
    variables:

    *name*: str name that must be unique within the pipeline.

    *defaultParams*: dict of default fitting parameters for new data.

    *dataAttrs*: dict of keys 'x', 'y' and 'fit' that defines the input and
    output arrays.

    *ioAttrs*: dict of keys 'range', 'params' and 'result' that defines the
    key names in `defaultParams` for, correspondingly, fitting range (2-list),
    fitting parameters (user specific) and results (dict).

    The method :meth:`run_main()` must be declared either with @staticmethod or
    @classmethod decorator. A returned not None value indicates success.

    *nThreads* or *nProcesses* can be > 1 to use threading or multiprocessing.
    If both are > 1, threading is used. The value can be an integer, 'all' or
    'half' which refer to the hardware limit `multiprocessing.cpu_count()`.

    *progressTimeDelta*, float, default 1.0 sec, a timeout delta to report on
    transformation progress. Only needed if :meth:`run_main` is defined with
    a parameter *progress*.
    """

    nThreads = 1
    nProcesses = 1
    progressTimeDelta = 1.0  # sec
    defaultResult = dict(R=1., mesg='', ier=None, info={}, nparam=0)
    # dataAttrs = dict(x='e', y='mu', fit='fit')
    # allDataAttrs = dict(x='e', y='mu')
    plotParams = dict(fit=dict(linewidth=1.5, linestyle=':'),
                      residue=dict(linewidth=1.5, linestyle='--'))
    tooltip = ""

    def __init__(self, node=None, widgetClass=None):  # node is None in test
        """
        *node* is instance of :class:`.core.nodes.Node`.

        *widgetClass* optional, widget class, descendant of
        :class:`.gui.fits.gbasefit.FitWidget`.
        """
        if (not hasattr(self, 'name')) or (not hasattr(self, 'defaultParams'))\
                or (not hasattr(self, 'dataAttrs'))\
                or (not hasattr(self, 'ioAttrs')):
            raise NotImplementedError(
                "The class Fit must be properly subclassed")

        isStatic = isinstance(getattr_static(self, "run_main"), staticmethod)
        isClass = isinstance(getattr_static(self, "run_main"), classmethod)
        if not (isStatic or isClass):
            raise NotImplementedError(
                "The method run_main() of {0} must be declared with either"
                "@staticmethod or @classmethod".format(self.__class__))

        self.node = node
        self.widgetClass = widgetClass
        if self.name in csi.fits:
            raise ValueError("A fit '{0}' already exists. Only one instance "
                             "is allowed".format(self.name))
        csi.fits[self.name] = self
        self.sendSignals = False
        self.read_ini_params()

    @classmethod
    def erase(cls, data):
        x = getattr(data, cls.dataAttrs['x'])
        fit = np.zeros_like(x)
        setattr(data, cls.dataAttrs['fit'], fit)
        lcfProps = dict(cls.defaultResult)
        dfparams = data.fitParams
        dfparams['lcf_result'] = lcfProps

    def read_ini_params(self):
        self.iniParams = self.defaultParams.copy()
        if configFits.has_section(self.name):
            for key in self.defaultParams:
                if key == self.ioAttrs['result']:
                    continue
                try:
                    testStr = configFits.get(self.name, key)
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
                if par not in data.fitParams:
                    raise KeyError("Unknown parameter '{0}'".format(par))
                data.fitParams[par] = params[par]

    def _get_progress1(self, alias, progress):
        if (self.node is None or not hasattr(self.node, 'widget') or
                self.node.widget is None):
            return
        self.node.widget.tree.transformProgress.emit([alias, progress.value])

    def _get_progressN(self, alias, worker=None):
        if (self.node is None or not hasattr(self.node, 'widget') or
                self.node.widget is None):
            return
        if worker is None:
            self.node.widget.tree.transformProgress.emit([alias, 1.0])
        else:
            ps = worker.get_progress()
            if len(ps) == 0:
                return
            self.node.widget.tree.transformProgress.emit([alias, ps[-1]])

    def _run_multi_worker(self, workers, workedItems, args):
        wt = workers[0].workerType
        if csi.DEBUG_LEVEL > 1:
            print('run "{0}" in {1} {2}{3} for {4}'.format(
                self.name, len(workers), wt, '' if len(workers) == 1 else 's',
                [d.alias for d in workedItems]))
        if self.sendSignals:
            csi.mainWindow.beforeDataTransformSignal.emit(workedItems)

        for worker, item in zip(workers, workedItems):
            if 'progress' in args and self.sendSignals:
                worker.timer = NTimer(
                    self.progressTimeDelta,
                    self._get_progressN, [item.alias, worker])
                worker.timer.start()
            if not worker.put_in_data(item):
                self.erase(item)
                item.beingTransformed = False
                continue
            else:
                item.beingTransformed = self.name
            worker.start()
            item.transfortm_t0 = time.time()

        for worker, item in zip(workers, workedItems):
            if not item.beingTransformed:
                continue
            worker.get_out_data(item)
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

    def _run_single_worker(self, data, args):
        data.beingTransformed = self.name
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
            self.run_main(*argVals)
            if timer is not None:
                timer.cancel()
            data.error = None
            if 'progress' in args:
                progress.value = 1.
                self._get_progress1(data.alias, progress)
        except Exception:
            if timer is not None:
                timer.cancel()
            errorMsg = 'failed "{0}" fit for data: {1}'.format(
                self.name, data.alias)
            errorMsg += "\nwith the followith traceback:\n"
            tb = traceback.format_exc()
            errorMsg += "".join(tb[:-1])  # remove last empty line
            # if csi.DEBUG_LEVEL > 20:
            data.error = errorMsg
        data.beingTransformed = False
        data.transfortmTimes[self.name] = \
            time.time() - data.transfortm_t0
        if self.sendSignals:
            csi.mainWindow.afterDataTransformSignal.emit([data])

    @logger(minLevel=20, attrs=[(0, 'name')])
    def run(self, params={}, updateUndo=True, dataItems=None):
        np.seterr(all='raise')
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
        if args[0] == 'self':
            raise SyntaxError(
                'IMPORTANT: remove "self" from "run_main()" parameters as'
                ' this is a static method, not an instance method!')
        if 'allData' in args:
            allData = []
            for data in csi.allLoadedItems:
                proxy = DataProxy()
                proxy.alias = str(data.alias)
                xname = self.allDataAttrs['x']
                setattr(proxy, xname, getattr(data, xname))
                yname = self.allDataAttrs['y']
                setattr(proxy, yname, getattr(data, yname))
                allData.append(proxy)

        inArrays = [self.dataAttrs['x'], self.dataAttrs['y']]
        outArrays = [self.dataAttrs['fit']]
        for data in items:
            if workerClass is not None:  # with multipro
                worker = workerClass(
                    self.__class__.run_main, self.__class__.name,
                    inArrays, outArrays, self.progressTimeDelta)
                if 'allData' in args:
                    worker.put_in_all_data(allData)
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

        self.run_post(items)
        np.seterr(all='warn')

        # for it in items:
        #     if it.error is None:
        #         del it.error

    def run_pre(self, params={}, dataItems=None, updateUndo=True):
        if params:
            # if updateUndo:
            #     self.push_to_undo_list(params, dataItems)
            self.update_params(params, dataItems)
        if (self.node is not None and hasattr(self.node, 'widget') and
                self.node.widget is not None):
            self.node.widget.onTransform = True
            if self.sendSignals:
                csi.mainWindow.beforeTransformSignal.emit(self.node.widget)

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
        be in this given order if both are present.

        *allData* is a list of all data items living in the data model. If
        *allData* is needed, both *nThreads* or *nProcesses* must be set to 1.

        *progress* is an object having a field `value`. A heavy fit routine
        should periodically update this field, like this:
        :code:`progress.value = 0.5` (means 50% completion). If used with GUI,
        progress will be visualized as an expanding colored background
        rectangle in the data tree. Quick fits do not need progress reporting.

        Should an error happen during the fitting, the error state will be
        notified in the ParSeq status bar and the traceback will be shown in
        the data item's tooltip in the data tree view.

        The method should update the 'result' entry in `data.fitParams`.
        """
        raise NotImplementedError  # must be overridden

    def run_post(self, dataItems):
        if (self.node is not None and hasattr(self.node, 'widget') and
                self.node.widget is not None):
            if self.sendSignals:
                csi.mainWindow.afterTransformSignal.emit(self.node.widget)
            self.node.widget.onTransform = False

    @classmethod
    def make_model_curve(cls, data):
        u"""
        Builds a data model and attributes it to data by defining data's arrays
        defined in the class variable `dataAttrs`. To be used by the fit's GUI
        widget that also defines the actual signature of this method.
        """
        pass


class GenericProcessOrThread(object):
    def __init__(self, func, inArrays, outArrays):
        self.func = func
        self.inArrays = inArrays
        self.outArrays = outArrays
        # self.started_event.clear()
        # self.finished_event.clear()

    @logger(minLevel=20)
    def put_in_all_data(self, allDataList):
        self.allDataQueue.put(allDataList)

    @logger(minLevel=20)
    def get_in_all_data(self):
        return retry_on_eintr(self.allDataQueue.get)

    @logger(minLevel=20, attrs=[(1, 'alias')])
    def put_in_data(self, item):
        res = {'fitParams': item.fitParams, 'alias': item.alias}
        for key in self.inArrays:
            try:
                # if not hasattr(item, key):
                #     setattr(item, key, None)
                res[key] = getattr(item, key)
            except AttributeError as e:
                print('Error in put_in_data():')
                print('{0} for spectrum {1}'.format(e, item.alias))
                # raise e
                return False
                # res[key] = None
        self.inDataQueue.put(res)
        return True

    @logger(minLevel=20)
    def get_in_data(self, item):
        outDict = retry_on_eintr(self.inDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])

    @logger(minLevel=20, attrs=[(1, 'alias')])
    def put_out_data(self, item):
        res = {'fitParams': item.fitParams}
        for key in self.outArrays:
            try:
                res[key] = getattr(item, key)
            except AttributeError:  # arrays can be conditionally missing
                pass
        self.outDataQueue.put(res)

    @logger(minLevel=20, attrs=[(1, 'alias')])
    def get_out_data(self, item):
        outDict = retry_on_eintr(self.outDataQueue.get)
        for field in outDict:
            setattr(item, field, outDict[field])

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

    @logger(minLevel=20, printClass=True)
    def run(self):
        # self.started_event.set()
        np.seterr(all='raise')
        data = DataProxy()
        self.get_in_data(data)
        try:
            args = getargspec(self.func)[0]
            argVals = [data]
            if 'allData' in args:
                allData = self.get_in_all_data()
                argVals.append(allData)
            if 'progress' in args:
                self.progress = DataProxy()
                self.progress.value = 1.
                argVals.append(self.progress)
                timer = NTimer(self.progressTimeDelta, self.put_progress)
                timer.start()
            else:
                timer = None
            self.func(*argVals)
            if timer is not None:
                timer.cancel()
                self.progress.value = 1.
                self.put_progress()
            self.put_error(None)
        except Exception:
            errorMsg = 'Failed "{0}" fit for data: {1}'.format(
                self.fitName, data.alias)
            errorMsg += "\nwith the followith traceback:\n"
            tb = traceback.format_exc()
            errorMsg += "".join(tb[:-1])  # remove last empty line
            self.put_error(errorMsg)
            # if csi.DEBUG_LEVEL > 20:
            # if True:
            #     print(errorMsg)
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
    pass


class BackendProcess(GenericProcessOrThread, multiprocessing.Process):
    def __init__(self, func, fitName, inArrays, outArrays,
                 progressTimeDelta):
        multiprocessing.Process.__init__(self)
        self.fitName = fitName
        self.progressTimeDelta = progressTimeDelta
        self.multiName = 'multiprocessing'
        self.workerType = 'process'
        self.allDataQueue = multiprocessing.Queue()
        self.inDataQueue = multiprocessing.Queue()
        self.outDataQueue = multiprocessing.Queue()
        self.errorQueue = multiprocessing.Queue()
        # self.started_event = multiprocessing.Event()
        # self.finished_event = multiprocessing.Event()
        self.progressQueue = multiprocessing.Queue()
        GenericProcessOrThread.__init__(self, func, inArrays, outArrays)


class BackendThread(GenericProcessOrThread, threading.Thread):
    def __init__(self, func, fitName, inArrays, outArrays,
                 progressTimeDelta):
        threading.Thread.__init__(self)
        self.fitName = fitName
        self.progressTimeDelta = progressTimeDelta
        self.multiName = 'multithreading'
        self.workerType = 'thread'
        if sys.version_info < (3, 1):
            import Queue
        else:
            import queue
            Queue = queue

        self.allDataQueue = Queue.Queue()
        self.inDataQueue = Queue.Queue()
        self.outDataQueue = Queue.Queue()
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


def run_fits(items, parentItem):
    topItems = [it for it in items if it in parentItem.childItems]
    bottomItems = [it for it in items if it not in parentItem.childItems
                   and (not isinstance(it.madeOf, (dict, list, tuple)))]
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
            if (csi.tasker is not None) and len(itemsByOrigin) == 1:
                # with a threaded transform
                csi.tasker.prepare(tr, dataItems=its, starter=tr.widget)
                csi.tasker.thread().start()
            else:
                # if len(itemsByOrigin) > 1, the transforms cannot be
                # parallelized, so do it in the same thread:
                tr.run(dataItems=its)
                if hasattr(tr, 'widget'):  # when with GUI
                    tr.widget.replotAllDownstream(tr.name)
