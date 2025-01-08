from __future__ import absolute_import  # needed for Py2
__author__ = "Konstantin Klementiev"
__date__ = "28 Aug 2022"
# !!! SEE CODERULES.TXT !!!

"""
`xrt` can reside in the parent directory of `parseq`, i.e. `parseq` and `xrt`
are on the same level. Alternatively, `xrt` can reside in the user's home
directory.
"""

import os
import sys
sys.path.append('../..')
sys.path.append('../../Ray-tracing')

home = os.path.expanduser("~")
sys.path.append(home)

try:
    import xrt.backends.raycing.materials as rm
except ImportError:
    rm = None

if rm is not None:
    crystalSi111 = rm.CrystalSi(hkl=(1, 1, 1))
    crystalSi311 = rm.CrystalSi(hkl=(3, 1, 1))
    crystals = dict(Si111=crystalSi111, Si311=crystalSi311)
else:
    crystals = dict()

refl, rc = dict(), dict()
for cryst in crystals:
    refl[cryst] = None
    rc[cryst] = None
