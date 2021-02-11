# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "17 Nov 2018"
# !!! SEE CODERULES.TXT !!!

import os

try:
    from ConfigParser import ConfigParser
except ImportError:
    from configparser import ConfigParser

iniDir = os.path.expanduser(os.path.join('~', '.parseq'))
if not os.path.exists(iniDir):
    os.makedirs(iniDir)

iniFileTransforms = (os.path.join(iniDir, 'transforms.ini'))
configTransforms = ConfigParser()
configTransforms.read(iniFileTransforms)

iniFileDirs = (os.path.join(iniDir, 'directories.ini'))
configDirs = ConfigParser()
configDirs.read(iniFileDirs)
if not configDirs.has_section('Load'):
    configDirs.add_section('Load')


def write_configs():
    with open(iniFileTransforms, 'w+') as cf:
        configTransforms.write(cf)
    with open(iniFileDirs, 'w+') as cf:
        configDirs.write(cf)
