# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "2 Apr 2021"
# !!! SEE CODERULES.TXT !!!

import os

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser  # python 2

iniDir = os.path.expanduser(os.path.join('~', '.parseq'))
if not os.path.exists(iniDir):
    os.makedirs(iniDir)

encoding = 'utf-8'

iniFileLoad = (os.path.join(iniDir, 'load.ini'))
configLoad = ConfigParser()
configLoad.read(iniFileLoad)

iniFileGUI = (os.path.join(iniDir, 'gui.ini'))
configGUI = ConfigParser()
configGUI.read(iniFileGUI)

iniFileTransforms = (os.path.join(iniDir, 'transforms.ini'))
configTransforms = ConfigParser()
configTransforms.read(iniFileTransforms)

iniFileFormats = (os.path.join(iniDir, 'formats.ini'))
configFormats = ConfigParser()
configFormats.read(iniFileFormats)
configFormats.optionxform = str  # makes it case sensitive


def get(conf, section, entry, default=None):
    if conf.has_option(section, entry):
        res = conf.get(section, entry)
        if isinstance(default, (type(''), type(u''))):
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
    if (what == 'all') or ('format' in whatl):
        with open(iniFileFormats, 'w+', encoding=encoding) as cf:
            configFormats.write(cf)
