# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "04 Mar 2019"
# !!! SEE CODERULES.TXT !!!

from ...core import nodes as cno


class Node1(cno.Node):
    name = 'currents'

    xName = 'e'
    xQLabel, xPlotLabel = 'E', r'$E$'
    xQUnit, xPlotUnit = 'eV', 'eV'

    yNames = ['i0', 'i1']
    yQLabels, yPlotLabels = ['I0', 'I1'], [r'$I_0$', r'$I_1$']
    yQUnits, yPlotUnits = ['counts']*2, ['counts']*2

    plotParams = {'linewidth': [2, 1],
                  'linestyle': ['-', '-'],
#                  'symbol': [None, None],
                  'yaxis': ['left', 'right']}


class Node2(cno.Node):
    name = u'µd'

    xName = 'e'
    xQLabel, xPlotLabel = 'E', r'$E$'
    xQUnit, xPlotUnit = 'eV', 'eV'

    yNames = ['mu']
    yQLabels, yPlotLabels = [u'µd'], [r'$\mu d$']

    plotParams = {'linewidth': 2.0}
