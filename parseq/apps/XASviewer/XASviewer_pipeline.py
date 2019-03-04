# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "04 Mar 2019"
# !!! SEE CODERULES.TXT !!!

import os
from ...core import singletons as csi
from ...core import spectra as csp
from . import XASviewer_nodes as dno
from . import XASviewer_transforms as dtr


def make_pipeline(withGUI=False):
    csi.pipelineName = 'XAS viewer'
    csi.appPath = os.path.dirname(os.path.abspath(__file__))
    csi.withGUI = withGUI

    node1 = dno.Node1()
    node2 = dno.Node2()
    dtr.Tr1(node1, node2)

    csi.dataRootItem = csp.Spectrum('root')
    if withGUI:
        from ...gui import dataTreeModelView as tmv
        csi.model = tmv.DataTreeModel()
