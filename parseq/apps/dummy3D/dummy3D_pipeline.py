# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "20 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import os
from ...core import singletons as csi
from ...core import spectra as csp
from ...gui import dataTreeModelView as tmv
from . import dummy3D_nodes as dno
#from . import dummy3D_transforms as dtr
#from . import dummy3D_widgets as dwi


def make_pipeline(withGUI=False):
    csi.pipelineName = 'Dummy XES'
    csi.appPath = os.path.dirname(os.path.abspath(__file__))
    csi.withGUI = withGUI

    node1 = dno.Node1()
#    node2 = dno.Node2()

#    dtr.Tr0(node1, node1, dwi.Tr0Widget if withGUI else None)
#    dtr.Tr1(node1, node2, dwi.Tr1Widget if withGUI else None)

    csi.dataRootItem = csp.Spectrum('root')
    if withGUI:
        csi.model = tmv.DataTreeModel()
