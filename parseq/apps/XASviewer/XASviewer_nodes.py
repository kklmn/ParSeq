# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "04 Mar 2019"
# !!! SEE CODERULES.TXT !!!

from ...core import nodes as cno
from collections import OrderedDict


class Node1(cno.Node):
    name = 'currents'
    arrays = OrderedDict()
    arrays['e'] = dict(qLabel='E', qUnit='eV', plotRole='x', plotLabel=r'$E$')
    arrays['i0'] = dict(
        qLabel='I0', qUnit='counts', plotRole='lefty', plotLabel=r'$I_0$',
        plotParams={'linewidth': 2})
    arrays['i1'] = dict(
        qLabel='I1', qUnit='counts', plotRole='righty', plotLabel=r'$I_1$')


class Node2(cno.Node):
    name = u'µd'
    arrays = OrderedDict()
    arrays['e'] = dict(qLabel='E', qUnit='eV', plotRole='x', plotLabel=r'$E$')
    arrays['mu'] = dict(
        qLabel='E', qUnit=u'µd', plotRole='lefty', plotLabel=r'$\mu d$',
        plotParams={'linewidth': 2.0})
