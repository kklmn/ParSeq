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
iniTransforms = (os.path.join(iniDir, 'transforms.ini'))
config = ConfigParser()


def write_config():
    with open(iniTransforms, 'w+') as cf:
        config.write(cf)
