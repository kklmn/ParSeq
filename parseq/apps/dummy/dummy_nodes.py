# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

from ...core import nodes as cno


class Node1(cno.Node):
    name = 'currents'

    xNameRaw = 'eraw'
    yNamesRaw = ['i0raw', 'i1raw']

    xName = 'e'
    xQLabel, xPlotLabel = 'E', r'$E$'
    xQUnit, xPlotUnit = 'eV', 'eV'

    yNames = ['i0', 'i1']
    yQLabels, yPlotLabels = ['I0', 'I1'], [r'$I_0$', r'$I_1$']
    yQUnits, yPlotUnits = ['counts']*2, ['counts']*2

    plotParams = {'linewidth': [3, 1], 'style': ['-', '-'],
                  'symbol': [None, 'd'], 'symbolsize': [None, 5],
                  'yaxis': ['left', 'right']}


class Node2(cno.Node):
    name = 'k-space'

    xName = 'k'
    xPlotLabel = r'$k$'
    xQUnit, xPlotUnit = u'Å<sup>-1</sup>', u'Å$^{-1}$'

    yNames = ['chi']
    yQLabels, yPlotLabels = [u'χ'], [r'$\chi$']

    plotParams = {}


class Node3(cno.Node):
    name = 'r-space'

    xName = 'r'
    xPlotLabel = r'$r$'
    xQUnit, xPlotUnit = u'Å', u'Å'

    yNames = ['ft']
    yQLabels, yPlotLabels = [u'|FT(χ)|'], [u'|FT($\chi$)|']
    yQUnits, yPlotUnits = [u'Å<sup>-1</sup>'], [u'Å$^{-1}$']

    plotParams = {}
