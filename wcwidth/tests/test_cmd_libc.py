#!/usr/bin/env python
# coding: utf-8
"""
Tests for wcwidth.py vs libc wcwidth(3) and wcswidth(3).

    https://github.com/jquast/wcwidth

This suite of tests compares the libc return values with
the pure-python return values. Although wcwidth(3) is POSIX,
its actual implementation may differ, so these tests are
not guaranteed to be successful on all platforms, especially
where wcwidth(3)/wcswidth(3) is out of date.
"""
# standard
import unicodedata
import ctypes.util
import itertools
import warnings
import locale
import sys

# local
import wcwidth


def is_named(ucs):
    try:
        return bool(unicodedata.name(ucs))
    except ValueError:
        return False


def isnt_combining(ucs):
    return not unicodedata.combining(ucs)


def report_ucs_msg(ucs, wcwidth_libc, wcwidth_local):
    ucp = (ucs.encode('unicode_escape')[2:]
           .decode('ascii')
           .upper()
           .lstrip('0'))
    url = "http://codepoints.net/U+{}".format(ucp)
    name = unicodedata.name(ucs)
    return ("libc={}, ours={}, name={}, url={} "
            " --oo{}oo--{}".format(
                wcwidth_libc, wcwidth_local,
                name, url, ucs, (" :libc failed to identify combining"
                                 if wcwidth_local == -1 else '')))

# use chr() for py3.x, unichr() for py2.x
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


# Load the entire table into memory, excluding those values
# that are not named, or are combining characters.
ALL_UCS = [ucs for ucs in
           [unichr(val) for val in range(sys.maxunicode)]
           if is_named(ucs) and isnt_combining(ucs)
           ]


def test_hello_jp():
    """
    Simple test of Japanese phrase: コンニチハ, セカイ!

    Given a phrase of 5 and 3 katakana ideographs, joined with
    3 english-ascii punctuation characters, totaling 11, this
    phrase consumes 19 cells of a terminal emulator.
    """
    # given,
    phrase = u'コンニチハ, セカイ!'
    expect_length_each = (2, 2, 2, 2, 2, 1, 1, 2, 2, 2, 1)
    expect_length_phrase = sum(expect_length_each)

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase = wcwidth.wcswidth(phrase, len(phrase))

    # verify,
    assert length_each == expect_length_each
    assert length_phrase == expect_length_phrase


class Test_libc_width:

    def setup_class(self):
        libc_name = ctypes.util.find_library('c')
        if not libc_name:
            raise ImportError("Can't find C library.")

        self.libc = ctypes.cdll.LoadLibrary(libc_name)
        self.libc.wcwidth.argtypes = [ctypes.c_wchar, ]
        self.libc.wcwidth.restype = ctypes.c_int

        assert getattr(self.libc, 'wcwidth', None) is not None
        assert getattr(self.libc, 'wcswidth', None) is not None

    def _is_equal_wcwidth(self, ucs):
        w_libc, w_local = self.libc.wcwidth(ucs), wcwidth.wcwidth(ucs)
        assert w_libc == w_local, report_ucs_msg(ucs, w_libc, w_local)

    def test_libc_wcwidth_equality(self):
        """
        Compare libc.wcwidth and wcwidth.wcwidth in chunks of ``step``,
        so that py.test generates test "blocks" (we have a lot of failures!)
        """
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))

        for ucs in ALL_UCS:
            yield self._is_equal_wcwidth, ucs

#    def _is_equal_wcswidth(self, ucs_chunk):
#        for a, b in itertools.combinations(range(len(ucs_chunk)), 2):
#            idx = slice(a, b) if a < b else slice(b, a)
#            ucs = ucs_chunk[idx]
#            assert self.libc.wcswidth(ucs, len(ucs)) == wcwidth.wcswidth(ucs)
#
#    def disabled_test_libc_wcswidth_equality(self, step=50):
#        """
#        Compare libc.wcswidth and wcwidth.wcswidth in chunks of ``step``,
#        so that py.test generates test "blocks" (we have a lot of failures!)
#        """
#        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))
#
#        for val in range(0, LIMIT_UCS, step):
#            (start, end) = (val, val + step)
#            ucs = u''.join([unichr(_num) for _num in range(start, end)])
#            yield self._is_equal_wcswidth, ucs
