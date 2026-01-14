#!/usr/bin/env python
"""
Manual tests comparing wcwidth.py to libc's wcwidth(3) and wcswidth(3).

    https://github.com/jquast/wcwidth

This suite of tests compares the libc return values with the pure-python return
values. Although wcwidth(3) is POSIX, its actual implementation may differ,
so these tests are not guaranteed to be successful on all platforms, especially
where wcwidth(3)/wcswidth(3) is out of date. This is especially true for many
platforms -- usually conforming only to unicode specification 1.0 or 2.0.

This program accepts one optional command-line argument, the unicode version
level for our library to use when comparing to libc.
"""
# pylint: disable=C0103
#         Invalid module name "wcwidth-libc-comparator"

# standard imports

# std imports
import sys
import locale
import warnings
import ctypes.util
import unicodedata

# local
# local imports
import wcwidth


def is_named(ucs):
    """
    Whether the unicode point ``ucs`` has a name.

    :rtype bool
    """
    try:
        return bool(unicodedata.name(ucs))
    except ValueError:
        return False


def is_not_combining(ucs):
    return not unicodedata.combining(ucs)


def report_ucs_msg(ucs, wcwidth_libc, wcwidth_local):
    """
    Return string report of combining character differences.

    :param ucs: unicode point.
    :type ucs: unicode
    :param wcwidth_libc: libc-wcwidth's reported character length.
    :type comb_py: int
    :param wcwidth_local: wcwidth's reported character length.
    :type comb_wc: int
    :rtype: unicode
    """
    ucp = (ucs.encode('unicode_escape')[2:]
           .decode('ascii')
           .upper()
           .lstrip('0'))
    url = f"http://codepoints.net/U+{ucp}"
    name = unicodedata.name(ucs)
    return (
        f"libc,ours={wcwidth_libc},{wcwidth_local} "
        f"[--o{ucs}o--] name={name} val={ord(ucs)} {url} ")


if sys.maxunicode < 1114111:
    warnings.warn('narrow Python build, only a small subset of '
                  'characters may be tested.')


def _is_equal_wcwidth(libc, ucs, unicode_version):
    w_libc = libc.wcwidth(ucs)
    w_local = wcwidth.wcwidth(ucs, unicode_version)
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
    all_ucs = (ucs for ucs in
               [chr(val) for val in range(sys.maxunicode)]
               if is_named(ucs) and is_not_combining(ucs))

    libc_name = ctypes.util.find_library('c')
    if not libc_name:
        raise ImportError("Can't find C library.")

    libc = ctypes.cdll.LoadLibrary(libc_name)
    libc.wcwidth.argtypes = [ctypes.c_wchar, ]
    libc.wcwidth.restype = ctypes.c_int

    assert getattr(libc, 'wcwidth', None) is not None
    assert getattr(libc, 'wcswidth', None) is not None

    locale.setlocale(locale.LC_ALL, using_locale)
    unicode_version = 'latest'
    if len(sys.argv) > 1:
        unicode_version = sys.argv[1]

    for ucs in all_ucs:
        try:
            _is_equal_wcwidth(libc, ucs, unicode_version)
        except AssertionError as err:
            print(err)


if __name__ == '__main__':
    main()
