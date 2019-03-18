# -*- coding: utf-8 -*-
"""
The XASviewer is a simple data analysis pipeline that displays experimental
currents and absorption spectra."""

__author__ = "Konstantin Klementiev"
__date__ = "04 Mar 2019"
# !!! SEE CODERULES.TXT !!!

import os.path as osp

from ...core import singletons as csi
from .XASviewer_pipeline import make_pipeline

__author__ = "Konstantin Klementiev (MAX IV Laboratory)"
__email__ = "first dot last at gmail dot com"
__license__ = "MIT license"
__synopsis__ = "XASviewer for ParSeq framework"

csi.pipelineName = 'XASviewer'
csi.appPath = osp.dirname(osp.abspath(__file__))
csi.appIconPath = osp.join(csi.appPath, '_images', 'XASviewer_icon.ico')
csi.appSynopsis = __synopsis__
csi.appDescription = __doc__
csi.appAuthor = __author__
csi.appLicense = __license__
