# -*- coding: utf-8 -*-
u"""
ParSeq implements a general analysis framework with a data model, plotter,
cross-data analysis and tunable widget work space. It also sets a structure to
implement particular analysis pipelines as relatively lightweight Python
packages.

ParSeq is intended for synchrotron based techniques, first of all spectroscopy.
"""

# !!! SEE CODERULES.TXT !!!

from .version import __versioninfo__, __version__, __date__

__module__ = "parseq"
__author__ = "Konstantin Klementiev (MAX IV Laboratory)"
__email__ = "first dot last at gmail dot com"
__license__ = "MIT license"
__synopsis__ = "ParSeq is a python software library for Parallel execution of"\
    " Sequential data analysis"

#__all__ = ['core']
