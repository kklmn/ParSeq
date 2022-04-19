# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "31 Mar 2022"
# !!! SEE CODERULES.TXT !!!


def format_memory_size(size, decimals=1):
    for unit in ['B', 'kB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimals}f} {unit}"
