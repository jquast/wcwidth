#!/usr/bin/env python
# coding: utf-8
"""
Manual tests comparing python and wcwidth's combining characters.

https://github.com/jquast/wcwidth

No assertions raised with python 3.4
"""
# pylint: disable=C0103
#         Invalid module name "wcwidth-combining-comparator"

# standard imports
from __future__ import print_function
import unicodedata
import warnings
import locale
import sys

# local imports
from wcwidth.wcwidth import _bisearch, COMBINING


def report_comb_msg(ucs, comb_py, comb_wc):
    """
    Return string report of combining character differences.

    :param ucs: unicode point.
    :type ucs: unicode
    :param comb_py: python's reported combining character length.
    :type comb_py: int
    :param comb_wc: wcwidth's reported combining character length.
    :type comb_wc: int
    :rtype: unicode
    """
    ucp = (ucs.encode('unicode_escape')[2:]
           .decode('ascii')
           .upper()
           .lstrip('0'))
    url = "http://codepoints.net/U+{0}".format(ucp)
    # pylint: disable=W0703
    #         Catching too general exception Exception (col 11)
    try:
        name = unicodedata.name(ucs)
    except ValueError:
        name = u''
    return (u"py,comb_table={0},{1} [--o{2}o--] name={3} val={4} {5}"
            " ".format(comb_py, comb_wc, ucs, name, ord(ucs), url))

# use chr() for py3.x,
# unichr() for py2.x
try:
    _ = unichr(0)
except NameError as err:
    if err.args[0] == "name 'unichr' is not defined":
        # pylint: disable=W0622
        #         Redefining built-in 'unichr' (col 8)

        unichr = chr
    else:
        raise

if sys.maxunicode < 1114111:
    warnings.warn('narrow Python build, only a small subset of '
                  'characters may be tested.')


def _is_equal_combining(ucs):
    comb_py = bool(unicodedata.category(ucs) in ['Mc', 'Me', 'Mn'])
    comb_wc = bool(_bisearch(ord(ucs), COMBINING))
    assert comb_py == comb_wc, report_comb_msg(ucs, comb_py, comb_wc)


def main(using_locale='en_US.UTF-8'):
    """
    Program entry point.

    Load the entire Unicode table into memory, for each character deemed
    a combining character by either python or wcwidth.table_comb, display
    their differences.
    """
    all_ucs = (ucs for ucs in
               [unichr(val) for val in range(sys.maxunicode)])

    locale.setlocale(locale.LC_ALL, using_locale)

    for ucs in all_ucs:
        try:
            _is_equal_combining(ucs)
        except AssertionError as err:
            print(u'{0}'.format(err))


if __name__ == '__main__':
    main()
