# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "23 Mar 2021"

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.commons as cco


def test_make_int_ranges(names):
    combinedNames = cco.combine_names(names)
    print(combinedNames)


if __name__ == '__main__':
    test_make_int_ranges(['entry10190', 'entry10190_1'])
    test_make_int_ranges(['entry10190_1', 'entry10191_1'])
