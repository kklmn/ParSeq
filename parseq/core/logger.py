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
    cyan = colorama.Fore.CYAN
    red = colorama.Fore.RED
    yellow = colorama.Fore.YELLOW
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

timeLevels = 0.1, 0.5  # in s, borders that separate green, cyan and red


def logger(minLevel=1, printClass=False, attrs=None):
    """Printed if csi.DEBUG_LEVEL > *minLevel*.

    *attrs*: a list of (iarg[int], attr[str]) pairs to print out, where
             iarg refers to the position in the *args* list of the function.
    """
    def decorate(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if csi.DEBUG_LEVEL > minLevel:
                out = f"{func.__name__}()"
                timesKey = str(out)
                if printClass:
                    out += f" of {args[0].__class__.__name__}"
                if attrs:
                    for iarg, attr in attrs:
                        try:
                            dout = f", {attr}={getattr(args[iarg], attr)}"
                            out += dout
                            if attr != 'alias':
                                timesKey += dout
                        except Exception as e:
                            out += f", {e}"
                syslogger.log(csi.DEBUG_LEVEL, f"enter {out}")
                tstart = time.time()
                lastAction = "replot(), node='{0}'".format(
                    list(csi.nodes.keys())[-1])
            res = func(*args, **kwargs)
            if csi.DEBUG_LEVEL > minLevel:
                dt = time.time() - tstart
                if timesKey not in csi.exectimes:
                    csi.exectimes[timesKey] = dt
                else:
                    csi.exectimes[timesKey] += dt
                mark = green if dt < timeLevels[0] else \
                    cyan if dt < timeLevels[1] else red
                syslogger.log(
                    csi.DEBUG_LEVEL, f"{out} has taken {mark}{dt:.6f}{reset}s")
                if 'worker' in out:
                    syslogger.log(csi.DEBUG_LEVEL, "")

                if out == lastAction and (csi.DEBUG_LEVEL > minLevel):
                    syslogger.log(csi.DEBUG_LEVEL, "")
                    for tkey, dt in dict(csi.exectimes).items():
                        mark = green if dt < timeLevels[0] else \
                            cyan if dt < timeLevels[1] else red
                        syslogger.log(
                            csi.DEBUG_LEVEL, f"{yellow}cumulative{reset} "
                            f"{tkey} took {mark}{dt:.6f}{reset}s")
                    csi.exectimes = dict()
            return res
        return wrapper

    return decorate
