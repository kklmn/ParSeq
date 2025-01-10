# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "18 Feb 2023"
# !!! SEE CODERULES.TXT !!!

import os
import time
import datetime
import logging
from functools import wraps
try:
    import colorama
    colorama.init(autoreset=True)
    green = colorama.Fore.GREEN
    red = colorama.Fore.RED
    reset = colorama.Fore.RESET
except ImportError:
    colorama = None
    green = red = reset = ''

from . import singletons as csi
from . import config as cco

logFile = os.path.join(cco.iniDir, '{0}.log'.format(csi.pipelineName))
syslogger = logging.getLogger('parseq')
logging.basicConfig(filename=logFile, filemode='w', level=50-csi.DEBUG_LEVEL)
logging.raiseExceptions = False
now = datetime.datetime.now()
syslogger.log(100, "The log file has started by ParSeq on {0}".format(
              now.strftime('%Y-%m-%d %H:%M:%S')))
console = logging.StreamHandler()
console.setLevel(logging.INFO)
syslogger.addHandler(console)

longExecutionTime = 0.5  # s


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
                syslogger.log(csi.DEBUG_LEVEL, f"enter {out}")
                tstart = time.time()
            res = func(*args, **kwargs)
            if csi.DEBUG_LEVEL > minLevel:
                dt = time.time() - tstart
                mark = green if dt < longExecutionTime else red
                syslogger.log(csi.DEBUG_LEVEL,
                              f"{out} has taken {mark}{dt:.6f}{reset}s")
                if 'worker' in out:
                    syslogger.log(csi.DEBUG_LEVEL, "")
            return res
        return wrapper
    return decorate
