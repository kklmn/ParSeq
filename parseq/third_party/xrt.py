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

import numpy as np

try:
    import xrt.backends.raycing.materials as rm
    import xrt.backends.raycing.materials.crystals as rmx
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


def validate_reflex(reflexStr):
    try:
        i = next((n for n, c in enumerate(reflexStr) if c.isdigit()),
                 len(reflexStr))
        xtalStr, hklStr = reflexStr[:i], reflexStr[i:]
        if xtalStr in rmx.__all__:
            return xtalStr, hklStr
    except Exception:
        return


def get_reflex_energy(reflexStr, thetaDeg):
    res = validate_reflex(reflexStr)
    if res is None:
        return
    xtalStr, hklStr = res
    if xtalStr == 'Si':
        xtal = rm.CrystalSi(hkl=hklStr)
    else:
        xtal = getattr(rmx, xtalStr)(hkl=hklStr)

    try:
        theta = np.radians(thetaDeg)
        E0raw = rm.ch / (2 * xtal.d * np.sin(theta))
        dTheta = xtal.get_dtheta_symmetric_Bragg(E0raw)
        E0 = rm.ch / (2 * xtal.d * np.sin(theta + dTheta))
        return E0
    except Exception as err:
        print(err)
