#!/usr/bin/env python
# coding: utf-8
"""
Manual tests comparing wcwidth.py to libc's wcwidth(3) and wcswidth(3).

    https://github.com/jquast/wcwidth

This suite of tests compares the libc return values with the pure-python return
values. Although wcwidth(3) is POSIX, its actual implementation may differ,
so these tests are not guaranteed to be successful on all platforms, especially
where wcwidth(3)/wcswidth(3) is out of date. This is especially true for many
platforms -- usually conforming only to unicode specification 1.0 or 2.0.
"""
# standard imports
from __future__ import print_function
import unicodedata
import ctypes.util
import warnings
import locale
import sys

# local imports
import wcwidth


def is_named(ucs):
    try:
        return bool(unicodedata.name(ucs))
    except ValueError:
        return False


isnt_combining = lambda ucs: not unicodedata.combining(ucs)


def report_ucs_msg(ucs, wcwidth_libc, wcwidth_local):
    ucp = (ucs.encode('unicode_escape')[2:]
           .decode('ascii')
           .upper()
           .lstrip('0'))
    url = "http://codepoints.net/U+{}".format(ucp)
    name = unicodedata.name(ucs)
    return (u"libc,ours={},{} [--o{}o--] name={} val={} {}"
            " ".format(wcwidth_libc, wcwidth_local, ucs, name, ord(ucs), url))

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


def _is_equal_wcwidth(libc, ucs):
    w_libc = libc.wcwidth(ucs)
    w_local = wcwidth.wcwidth(ucs)
    assert w_libc == w_local, report_ucs_msg(ucs, w_libc, w_local)


def main(using_locale=('en_US', 'UTF-8',)):
    """
    Program entry point.

    Load the entire Unicode table into memory, excluding those that:

        - are not named (func unicodedata.name returns empty string),
        - are combining characters.

    Using ``locale``, for each unicode character string compare libc's
    wcwidth with local wcwidth.wcwidth() function; when they differ,
    report a detailed AssertionError to stdout.
    """
    ALL_UCS = [ucs for ucs in
               [unichr(val) for val in range(sys.maxunicode)]
               if is_named(ucs) and isnt_combining(ucs)]

    libc_name = ctypes.util.find_library('c')
    if not libc_name:
        raise ImportError("Can't find C library.")

    libc = ctypes.cdll.LoadLibrary(libc_name)
    libc.wcwidth.argtypes = [ctypes.c_wchar, ]
    libc.wcwidth.restype = ctypes.c_int

    assert getattr(libc, 'wcwidth', None) is not None
    assert getattr(libc, 'wcswidth', None) is not None

    locale.setlocale(locale.LC_ALL, using_locale)

    for ucs in ALL_UCS:
        try:
            _is_equal_wcwidth(libc, ucs)
        except AssertionError as err:
            print(err)

if __name__ == '__main__':
    main()
