# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "18 Feb 2023"
# !!! SEE CODERULES.TXT !!!

import time
from functools import wraps

from . import singletons as csi


def logger(minLevel=1, printClass=False, attrs=None):
    """Printed if csi.DEBUG_LEVEL > *minLevel*.
       *attrs*: a list of (iarg[int], attr[str]) pairs to print out.
    """
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if csi.DEBUG_LEVEL > minLevel:
                out = f"{func.__name__}()"
                if printClass:
                    out += f" of {args[0].__class__.__name__}"
                if attrs:
                    for iarg, attr in attrs:
                        try:
                            out += f", {attr}={getattr(args[iarg], attr)}"
                        except Exception as e:
                            out += f", {e}"
                print(f"enter {out}")
                tstart = time.time()
            res = func(*args, **kwargs)
            if csi.DEBUG_LEVEL > minLevel:
                dt = time.time() - tstart
                print(f"exit {out} in {dt:.5f}s")
            return res
        return wrapper
    return decorate
