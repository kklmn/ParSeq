# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "30 Jun 2021"


def parse_slice_str(slice_str):
    parts = slice_str.split(':')
    if len(parts) == 1:
        try:
            return int(slice_str)
        except ValueError:
            return slice(None)
    intParts = []
    for p in parts:
        try:
            intp = int(p)
        except ValueError:
            intp = None
        intParts.append(intp)
    return slice(*intParts)


if __name__ == '__main__':
    print(parse_slice_str('1:10:2'))
    print(parse_slice_str('1:10'))
    print(parse_slice_str(':-1'))
    print(parse_slice_str(':10'))
    print(parse_slice_str('1:'))
    print(parse_slice_str('22'))
    print(parse_slice_str(''))
    print()
    print(parse_slice_str(' 1:10:2'))
    print(parse_slice_str(' 1:10'))
    print(parse_slice_str(' :-1'))
    print(parse_slice_str(' :10'))
    print(parse_slice_str(' 1:'))
    print(parse_slice_str(' 22'))
    print(parse_slice_str(' '))
