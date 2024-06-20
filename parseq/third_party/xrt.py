from __future__ import absolute_import  # needed for Py2
__author__ = "Konstantin Klementiev"
__date__ = "28 Aug 2022"
# !!! SEE CODERULES.TXT !!!

# path to xrt under 'c:\Ray-tracing':
# import sys; sys.path.append(r'c:\Ray-tracing')  # analysis:ignore
import os, sys; sys.path.append(os.path.join('..', '..', 'Ray-tracing'))  # analysis:ignore
from os.path import expanduser, join
home = expanduser("~")
# path to xrt under 'Ray-tracing' in home directory:
sys.path.append(join(home, 'Ray-tracing'))  # analysis:ignore

import xrt.backends.raycing.materials as rm

crystalSi111 = rm.CrystalSi(hkl=(1, 1, 1))
crystalSi311 = rm.CrystalSi(hkl=(3, 1, 1))
crystals = dict(Si111=crystalSi111, Si311=crystalSi311)

refl, rc = dict(), dict()
for cryst in crystals:
    refl[cryst] = None
    rc[cryst] = None
