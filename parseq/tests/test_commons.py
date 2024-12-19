# -*- coding: utf-8 -*-
"""Test of building a common string from several strings. Common left and right
parts are first found and the middle part is a list of variable sub-parts."""
__author__ = "Konstantin Klementiev"
__date__ = "19 Dec 2024"

import sys; sys.path.append('../..')  # analysis:ignore
import parseq.core.commons as cco


if __name__ == '__main__':
    # a = ['2', '3', '4', '5', '7', '8', '9', '11', '15', '16', '17', '18']
    # print(cco.make_int_ranges(a))
    # # -> "[02..05, 07..09, 11, 15..18]"

    # a = ['03', '02', '04', '05']
    # print(cco.make_int_ranges(a))
    # # -> "[2..5]"

    # names = ['entry10190', 'entry10190_1']
    # print(cco.combine_names(names))
    # # -> "entry10190[, _1]"

    # names = ['entry10190_1', 'entry10191_1']
    # print(cco.combine_names(names))
    # # -> entry1019[0..1]_1

    # base = '20221030/entry'
    # names = [base+str(i) for i in range(1214, 1314)]
    # print(cco.combine_names(names))
    # # -> 20221030/entry1[214..313]

    names = [
        'Cr-foil_EXAFS_23293', 'Cr-foil_EXAFS_23294', 'Cr-foil_EXAFS_23295',
        'Fe-foil_EXAFS_23147', 'Fe-foil_EXAFS_23148', 'Fe-foil_EXAFS_23149',
        'Co-foil_EXAFS_23107', 'Co-foil_EXAFS_23108', 'Co-foil_EXAFS_23109',
        'bla',
        'Cu-foil_EXAFS_23068', 'Cu-foil_EXAFS_23069', 'Cu-foil_EXAFS_23070']
    print(cco.combine_names(names))
    # -> ['Cr-foil_EXAFS_2329[3..5]', 'Fe-foil_EXAFS_2314[7..9]',
    # ->  'Co-foil_EXAFS_2310[7..9]', 'bla', 'Cu-foil_EXAFS_230[68..70]']
