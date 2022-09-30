# -*- coding: utf-8 -*-
__author__ = "Konstantin Klementiev"
__date__ = "12 Sep 2022"
# !!! SEE CODERULES.TXT !!!

import itertools

MAX_HEADER_LINES = 256
MIME_TYPE_DATA = 'parseq-data-model-items'
MIME_TYPE_TEXT = 'text/uri-list'
MIME_TYPE_HDF5 = 'parseq-hdf5-model-items'

(DATA_COLUMN_FILE, DATA_DATASET, DATA_COMBINATION, DATA_FUNCTION, DATA_GROUP,
 DATA_BRANCH) = range(6)
COMBINE_NONE, COMBINE_AVE, COMBINE_SUM, COMBINE_PCA, COMBINE_RMS = range(5)
combineNames = '', 'ave', 'sum', 'PCA', 'RMS'

(DATA_STATE_GOOD, DATA_STATE_BAD, DATA_STATE_UNDEFINED, DATA_STATE_NOTFOUND,
 DATA_STATE_MATHERROR) = 1, 0, -1, -2, -3


def expandDotAttr(attr):
    """ *attr* is str or list of str, each str can have a dot notation"""
    if not isinstance(attr, (tuple, list)):
        res = attr.split(".")
        try:
            return [eval(a) if '(' in a else a for a in res]
        except Exception:
            return res
    expanded = []
    for subattr in attr:
        try:
            res = subattr.split(".")
            try:
                expanded.extend([eval(a) if '(' in a else a for a in res])
            except Exception:
                expanded.extend(res)
        except AttributeError:
            expanded.append(subattr)
    return expanded


def expandTransformParam(prop):
    "add `transformParams` from the left of the prop name"
    if isinstance(prop, type("")):
        if '.' not in prop:
            # then a single attribute
            return '.'.join(('transformParams', prop))
            # return ['transformParams', prop]
    return prop


def shrinkTransformParam(prop):
    "remove `transformParams` from the left of the prop name"
    if isinstance(prop, (list, tuple)):
        if 'transformParams' in prop:
            prop = [pr for pr in prop if pr != 'transformParams']
    elif isinstance(prop, type("")):
        if 'transformParams.' in prop:
            prop = prop.replace('transformParams.', '')
    return prop


def getDotAttr(obj, attr, withContainer=False):
    """ *attr* is str or list of str, each str can have a dot notation"""
    for subattr in expandDotAttr(attr):
        container = obj
        try:
            obj = getattr(obj, subattr)
        except (AttributeError, TypeError):
            try:
                obj = obj[subattr]
            except (KeyError, TypeError):
                # print('no {0} attribute in {1}'.format(subattr, obj))
                return (container, subattr, None) if withContainer else None
    return (container, subattr, obj) if withContainer else obj


def setDotAttr(obj, attr, val):
    attrList = expandDotAttr(attr)
    if len(attrList) > 1:
        for name in attrList[:-1]:
            try:
                obj = getattr(obj, name)
            except (AttributeError, TypeError):
                obj = obj[name]
        attr = attrList[-1]
    setattr(obj, attr, val)


def str_not_blank(s):
    """https://stackoverflow.com/questions/9573244/
    most-elegant-way-to-check-if-the-string-is-empty-in-python"""
    return bool(s and s.strip())


def common_substring(strs, isReversed=False):
    """finds the longest common substring of strings in the sequence *strs* """
    def _iter():
        txts = [s[::-1] for s in strs] if isReversed else strs
        for letters in zip(*txts):
            if all(let == letters[0] for let in letters[1:]):
                yield letters[0]
            else:
                return
    assert isinstance(isReversed, bool)
    res = ''.join(_iter())
    return res[::-1] if isReversed else res


def combine_names(names, minLenLeft=2, minLenRight=2):
    if len(names) == 0:
        return ''
    elif len(names) == 1:
        return names[0]
    elif all(name == names[0] for name in names[1:]):
        return names[0]
    cleft = common_substring(names)
    cright = common_substring(names, isReversed=True)
    if len(cleft) < minLenLeft:
        cleft = ''
    if len(cright) < minLenRight:
        cright = ''
    nleft, nright = len(cleft), len(cright)
    numStr = [c[nleft:] if nright == 0 else c[nleft:-nright] for c in names]
    try:
        label = cleft + make_int_ranges(numStr) + cright
    except:  # noqa
        label = cleft + '[' + ', '.join(numStr) + ']' + cright
    return label


def slice_repr(slice_obj):
    """
    Get the best guess of a minimal representation of
    a slice, as it would be created by indexing.
    """
    slice_items = [slice_obj.start, slice_obj.stop, slice_obj.step]
    if slice_items[-1] is None:
        slice_items.pop()
    if slice_items[-1] is None:
        if slice_items[0] is None:
            return "all"
        else:
            return repr(slice_items[0]) + ":"
    else:
        return ":".join("" if x is None else repr(x) for x in slice_items)


def numbers_extract(strlist):
    "from each string, extract a number that is separated by '_' or spaces"
    res = []
    for strline in strlist:
        for sub in strline.split('_'):
            try:
                res.append(float(sub))
                break
            except ValueError:
                pass
        else:
            for sub in strline.split():
                try:
                    res.append(float(sub))
                    break
                except ValueError:
                    pass
            else:
                return []
    return res


def intervals_extract(iterable):
    iterable = sorted(set(iterable))
    for key, gr in itertools.groupby(
            enumerate(iterable), lambda t: int(t[1])-int(t[0])):
        gr = list(gr)
        yield [gr[0][1], gr[-1][1]]


def make_int_ranges(iterable):
    try:
        intit = [int('a') if '_' in i else int(i) for i in iterable]
    except Exception:
        intit = iterable
    ranges = list(intervals_extract(intit))
    nr = max([len(str(max(r[0], r[1]))) for r in ranges])
    aslist = ["{0:0{1}d[0]}..{0:0{1}d[1]}".format(r, nr) if r[0] < r[1] else
              "{0:0{1}d[0]}".format(r, nr) for r in ranges]
    return "[{}]".format(', '.join(aslist))

# examples:
#
#a = ['2', '3', '4', '5', '7', '8', '9', '11', '15', '16', '17', '18']
#print(make_int_ranges(a))
# -> "(2..5, 7..9, 11, 15..18)"
#
#a = ['03', '02', '04', '05']
#print(make_int_ranges(a))
# -> "(02..05)"


def get_header(fname, readkwargs):
    skipUntil = readkwargs.pop('lastSkipRowContains', '')
    headerLen = -1
    if 'skiprows' not in readkwargs:
        if skipUntil:
            with open(fname, 'r') as f:
                for il, line in enumerate(f):
                    if skipUntil in line:
                        headerLen = il
                    if il == MAX_HEADER_LINES:
                        break
            if headerLen >= 0:
                readkwargs['skiprows'] = headerLen + 1
    else:
        headerLen = readkwargs['skiprows']
    header = []
    with open(fname, 'r') as f:
        for il, line in enumerate(f):
            if il == MAX_HEADER_LINES:
                break
            if ((headerLen >= 0) and (il <= headerLen)) or \
                    line.startswith('#'):
                header.append(line)
    return header


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
