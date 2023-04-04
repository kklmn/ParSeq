from __future__ import absolute_import  # needed for Py2
__author__ = "Konstantin Klementiev"
__date__ = "13 Feb 2022"
# !!! SEE CODERULES.TXT !!!

# path to xrt:
import sys; sys.path.append(r'c:\Ray-tracing\XAFSmass')  # analysis:ignore
import os
# import XAFSmass as xm
# import XAFSmass.XAFSmassQt as xmq

edges = ("K", "L1", "L2", "L3", "M1", "M2", "M3", "M4", "M5", "N1", "N2", "N3")

# selfDir = os.path.dirname(xm.__file__)
selfDir = os.path.dirname(__file__)


def read_energies():
    """Read `Energies.txt` and return a list of 'Z Element edge energy'."""
    efname = os.path.join(selfDir, 'data', 'Energies.txt')
    energies = []
    with open(efname, 'r') as f:
        f.readline()
        f.readline()
        for line in f.readlines():
            cs = line.strip().split()
            if len(cs[0]) == 1:
                cs[0] = '0' + cs[0]
            pre = cs[0] + ' ' + cs[1] + ' '
            for ic, c in enumerate(cs[2:]):
                energies.append(pre + edges[ic] + ' ' + c)
    return energies
