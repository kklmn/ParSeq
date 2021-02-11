# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "8 Feb 2021"
# !!! SEE CODERULES.TXT !!!

from ...core import nodes as cno
from collections import OrderedDict


class Node1(cno.Node):
    name = 'currents'
    arrays = OrderedDict()
    arrays['e'] = dict(
        qLabel='E', qUnit='eV', raw='eraw', plotRole='x', plotLabel=r'$E$')
    arrays['i0'] = dict(
        qLabel='I0', qUnit='counts', raw='i0raw', plotRole='yleft',
        plotLabel=r'$I_0$', plotParams=dict(linewidth=3))
    arrays['i1'] = dict(
        qLabel='I1', qUnit='counts', raw='i1raw', plotRole='yright',
        plotLabel=r'$I_1$',
        plotParams=dict(linewidth=1, linestyle='--', symbol='d', symbolsize=5))


class Node2(cno.Node):
    name = 'k-space'
    arrays = OrderedDict()
    arrays['k'] = dict(
        qUnit=u'Å\u207B\u00B9', plotRole='x', plotLabel=r'$k$',
        plotUnit=r'Å$^{-1}$')
    arrays['chi'] = dict(qLabel=u'χ', plotRole='yleft', plotLabel=r'$\chi$')


class Node3(cno.Node):
    name = 'r-space'
    arrays = OrderedDict()
    arrays['r'] = dict(qUnit=u'Å', plotRole='x', plotLabel=r'$r$')
    arrays['ft'] = dict(
        qLabel=u'|FT(χ)|', qUnit=u'Å\u207B\u00B9', plotRole='yleft',
        plotLabel=r'|FT($\chi$)|', plotUnit=r'Å$^{-1}$')
