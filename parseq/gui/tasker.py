# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "8 May 2023"
# !!! SEE CODERULES.TXT !!!

import time
from silx.gui import qt


class Tasker(qt.QObject):
    ready = qt.pyqtSignal(qt.QWidget, str, str, dict, float, list)

    def prepare(self, task, params={}, runDownstream=None, dataItems=None,
                starter=None):
        self.task = task
        self.params = params
        self.runDownstream = runDownstream  # used only with transforms
        self.dataItems = dataItems
        self.starter = starter

    def getTransformNames(self, transform):
        res = [transform.name]
        for tr in transform.toNode.transformsOut:
            if tr is transform:
                continue
            res.extend(self.getTransformNames(tr))
        return res

    def run(self):
        self.timeStart = time.time()
        # self.dataItems can be None; csi.selectedItems are processed then
        errorItems = self.task.run(
            params=self.params, runDownstream=self.runDownstream,
            dataItems=self.dataItems)
        self.thread().terminate()
        self.timeEnd = time.time()
        self.timeDuration = self.timeEnd - self.timeStart
        self.dataItems = None  # remove the reference to data
        if self.runDownstream:  # used only with transforms
            transformNames = self.getTransformNames(self.task)
            trStr = ' + '.join(transformNames)
        else:
            trStr = self.task.name

        self.ready.emit(self.starter, self.task.name, trStr, self.params,
                        self.timeDuration, errorItems)
