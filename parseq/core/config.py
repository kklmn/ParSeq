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

iniFileTransforms = (os.path.join(iniDir, 'transforms.ini'))
configTransforms = ConfigParser()
configTransforms.read(iniFileTransforms)

iniLoad = (os.path.join(iniDir, 'load.ini'))
configLoad = ConfigParser()
configLoad.read(iniLoad)

iniFileGUI = (os.path.join(iniDir, 'gui.ini'))
configGUI = ConfigParser()
configGUI.read(iniFileGUI)


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


def write_configs(what=(1, 1, 1)):  # in mainWindow's closeEvent
    if what[0]:
        with open(iniLoad, 'w+') as cf:
            configLoad.write(cf)
    if what[1]:
        with open(iniFileGUI, 'w+') as cf:
            configGUI.write(cf)
    if what[2]:
        with open(iniFileTransforms, 'w+') as cf:
            configTransforms.write(cf)
