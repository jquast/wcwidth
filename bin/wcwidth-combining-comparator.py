#!/usr/bin/env python
# coding: utf-8
"""
Manual tests comparing python's unicodedata.combining
and internal combining comparison in wcwidth.wcwidth()

https://github.com/jquast/wcwidth

No assertions raised with python 3.4
"""
# standard imports
from __future__ import print_function
import unicodedata
import ctypes.util
import warnings
import locale
import sys

# local imports
from wcwidth.wcwidth import _bisearch, NONZERO_COMBINING

is_combining = lambda ucs: unicodedata.combining(ucs)


def report_comb_msg(ucs, comb_py, comb_wc):
    ucp = (ucs.encode('unicode_escape')[2:]
           .decode('ascii')
           .upper()
           .lstrip('0'))
    url = "http://codepoints.net/U+{0}".format(ucp)
    try:
        name = unicodedata.name(ucs)
    except:
        name = u''
    return (u"py,comb_table={0},{1} [--o{2}o--] name={3} val={4} {5}"
            " ".format(comb_py, comb_wc, ucs, name, ord(ucs), url))

# use chr() for py3.x,
# unichr() for py2.x
try:
    _ = unichr(0)
except NameError as err:
    if err.args[0] == "name 'unichr' is not defined":
        unichr = chr
    else:
        raise

if sys.maxunicode < 1114111:
    warnings.warn('narrow Python build, only a small subset of '
                  'characters may be tested.')


def _is_equal_combining(ucs):
    comb_py = bool(unicodedata.combining(ucs))
    comb_wc = bool(_bisearch(ord(ucs), NONZERO_COMBINING))
    assert comb_py == comb_wc, report_comb_msg(ucs, comb_py, comb_wc)


def main(using_locale='en_US.UTF-8'):
    """
    Program entry point.

    Load the entire Unicode table into memory, for each character deemed
    a combining character by either python or wcwidth.table_comb, display
    their differences.
    """
    ALL_UCS = [ucs for ucs in
               [unichr(val) for val in range(sys.maxunicode)]]

    locale.setlocale(locale.LC_ALL, using_locale)

    for ucs in ALL_UCS:
        try:
            _is_equal_combining(ucs)
        except AssertionError as err:
            print(u'{0}'.format(err))

if __name__ == '__main__':
    main()
