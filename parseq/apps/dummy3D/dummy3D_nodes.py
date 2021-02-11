# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "6 Feb 2021"
# !!! SEE CODERULES.TXT !!!

from ...core import nodes as cno
from collections import OrderedDict
import hdf5plugin  # needed to prevent h5py's "OSError: Can't read data"


class Node1(cno.Node):
    name = 'theta scan'
    arrays = OrderedDict()
    arrays['theta'] = dict(
        qLabel='θ', qUnit='°', plotRole='1D', plotLabel=r'$\theta$')
    arrays['i0'] = dict(
        qLabel='I0', qUnit='counts', plotRole='1D', plotLabel=r'$I_0$')
    arrays['iXES'] = dict(
        qLabel='I_XES', qUnit='counts', plotRole='3D',
        plotLabel=[r'$\theta$', r'horizontal pixel', r'tangential pixel'])
