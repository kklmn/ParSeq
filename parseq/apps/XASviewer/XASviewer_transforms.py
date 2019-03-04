# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "04 Mar 2019"
# !!! SEE CODERULES.TXT !!!

import numpy as np
# from ...core import singletons as csi
from ...core import transforms as ctr


class Tr1(ctr.Transform):
    name = 'make mu'
    params = dict()

    def run_main(self, data):
        # dparams = data.transformParams[self.name]

        try:
            i1 = np.where(data.i1 > 0, data.i1, np.ones_like(data.i1))
            ratio = data.i0 / i1
            ratio[ratio <= 0] = 1
            data.mu = np.log(ratio)
            data.isGood[self.toNode.name] = True
        except (TypeError, IndexError, ValueError):
            data.isGood[self.toNode.name] = False
