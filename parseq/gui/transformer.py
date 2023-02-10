# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "10 Feb 2023"
# !!! SEE CODERULES.TXT !!!

import time
from silx.gui import qt


class Transformer(qt.QObject):
    ready = qt.pyqtSignal(qt.QWidget, str, str, dict, float, list)

    def prepare(self, transform, params={}, runDownstream=True, dataItems=None,
                starter=None):
        self.transform = transform
        self.params = params
        self.runDownstream = runDownstream
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
        errorItems = self.transform.run(
            params=self.params, runDownstream=self.runDownstream,
            dataItems=self.dataItems)
        self.thread().terminate()
        self.timeEnd = time.time()
        self.timeDuration = self.timeEnd - self.timeStart
        self.dataItems = None  # remove the reference to data
        if self.runDownstream:
            transformNames = self.getTransformNames(self.transform)
            trStr = ' + '.join(transformNames)
        else:
            trStr = self.transform.name

        self.ready.emit(self.starter, self.transform.name, trStr, self.params,
                        self.timeDuration, errorItems)
