# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "31 Mar 2021"
# !!! SEE CODERULES.TXT !!!

import time
from silx.gui import qt


class Transformer(qt.QObject):
    ready = qt.pyqtSignal(qt.QWidget, float)

    def prepare(self, transform, params={}, runDownstream=True, dataItems=None,
                starter=None):
        self.transform = transform
        self.params = params
        self.runDownstream = runDownstream
        self.dataItems = dataItems
        self.starter = starter

    def run(self):
        self.timeStart = time.time()
        self.transform.run(
            params=self.params, runDownstream=self.runDownstream,
            dataItems=self.dataItems)
        self.thread().terminate()
        self.timeEnd = time.time()
        self.timeDuration = self.timeEnd - self.timeStart
        self.ready.emit(self.starter, self.timeDuration)
