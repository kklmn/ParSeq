# -*- coding: utf-8 -*-
"""
The Dummy pipeline serves as an example for creating analysis nodes, transforms
that connect these nodes and widgets that set options and parameters of the
transforms."""

__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import os.path as osp

from ...core import singletons as csi
from .dummy_pipeline import make_pipeline
from .dummy_tests import load_test_data

#__module__ = "dummy"
__author__ = "Konstantin Klementiev (MAX IV Laboratory)"
__email__ = "first dot last at gmail dot com"
__license__ = "MIT license"
__synopsis__ = "A dummy data analysis pipeline for ParSeq framework"

csi.pipelineName = 'Dummy'
csi.appPath = osp.dirname(osp.abspath(__file__))
csi.appIconPath = osp.join(csi.appPath, '_images', 'dummy_icon.ico')
csi.appSynopsis = __synopsis__
csi.appDescription = __doc__
csi.appAuthor = __author__
csi.appLicense = __license__
