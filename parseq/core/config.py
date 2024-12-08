# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "5 May 2021"
# !!! SEE CODERULES.TXT !!!

import os

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser  # python 2

import numpy as np  # for doing eval() in `get`
from . import singletons as csi

iniDir = os.path.expanduser(os.path.join('~', '.parseq'))
if not os.path.exists(iniDir):
    os.makedirs(iniDir)

encoding = 'utf-8'

iniFileLoad = os.path.join(iniDir, '{0}_load.ini'.format(csi.pipelineName))
configLoad = ConfigParser()
configLoad.read(iniFileLoad, encoding=encoding)

iniFileGUI = os.path.join(iniDir, '{0}_gui.ini'.format(csi.pipelineName))
configGUI = ConfigParser()
configGUI.read(iniFileGUI, encoding=encoding)

iniFileTransforms = os.path.join(
    iniDir, '{0}_transforms.ini'.format(csi.pipelineName))
configTransforms = ConfigParser()
configTransforms.read(iniFileTransforms, encoding=encoding)

iniFileFits = os.path.join(iniDir, '{0}_fits.ini'.format(csi.pipelineName))
configFits = ConfigParser()
configFits.read(iniFileFits, encoding=encoding)

iniFileFormats = os.path.join(
    iniDir, '{0}_formats.ini'.format(csi.pipelineName))
configFormats = ConfigParser()
configFormats.read(iniFileFormats, encoding=encoding)
configFormats.optionxform = str  # makes it case sensitive


def get(conf, section, entry, default=None):
    if conf.has_option(section, entry):
        res = conf.get(section, entry)
        if isinstance(default, str):
            return res
        else:
            try:
                return eval(res)
            except (SyntaxError, NameError):
                return res
    else:
        return default


def put(conf, section, entry, value):
    if not conf.has_section(section):
        conf.add_section(section)
    conf.set(section, entry, value)


def write_configs(what='all'):  # in mainWindow's closeEvent
    whatl = what.lower() if what != 'all' else ''
    if (what == 'all') or ('load' in whatl):
        with open(iniFileLoad, 'w+', encoding=encoding) as cf:
            configLoad.write(cf)
    if (what == 'all') or ('gui' in whatl):
        with open(iniFileGUI, 'w+', encoding=encoding) as cf:
            configGUI.write(cf)
    if (what == 'all') or ('transform' in whatl):
        with open(iniFileTransforms, 'w+', encoding=encoding) as cf:
            configTransforms.write(cf)
    if (what == 'all') or ('fit' in whatl):
        with open(iniFileFits, 'w+', encoding=encoding) as cf:
            configFits.write(cf)
    if (what == 'all') or ('format' in whatl):
        with open(iniFileFormats, 'w+', encoding=encoding) as cf:
            configFormats.write(cf)
