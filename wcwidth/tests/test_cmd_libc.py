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
import locale
import ctypes
import ctypes.util
import warnings
import itertools

# local
import wcwidth

# use chr() for py3.x, unichr ()for py2.x
try:
    _ = unichr(0)
except NameError as err:
    if err.args[0] == "name 'unichr' is not defined":
        unichr = chr
    else:
        raise

# some poor python builds (apple, etc.) are narrow, presumably
# for smaller memory footprint of character strings.
try:
    _ = unichr(0x10000)
    LIMIT_UCS = 0x3fffd
except ValueError as err:
    assert 'narrow Python build' in err.args[0], err.args
    LIMIT_UCS = 0x10000
    warnings.warn('narrow Python build, only a small subset of '
                  'characters may be tested.')


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

    def _is_equal_wcwidth(self, ucs_chunk):
        for ucs in ucs_chunk:
            assert self.libc.wcwidth(ucs) == wcwidth.wcwidth(ucs)

    def test_libc_wcwidth_equality(self, step=1000):
        """
        Compare libc.wcwidth and wcwidth.wcwidth
        """
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))

        for val in range(0, LIMIT_UCS, step):
            ucs_chunk = [unichr(val) for val in range(val, val+step)]
            yield self._is_equal_wcwidth, ucs_chunk

    def _is_equal_wcswidth(self, ucs_chunk):
        for a, b in itertools.combinations(range(len(ucs_chunk)), 2):
            idx = slice(a, b) if a < b else slice(b, a)
            ucs = ucs_chunk[idx]
            assert self.libc.wcswidth(ucs, len(ucs)) == wcwidth.wcswidth(ucs)

    def test_libc_wcswidth_equality(self, step=1000):
        """
        Compare libc.wcswidth and wcwidth.wcswidth in chunks of ``step``,
        so that py.test generates test "blocks"; we have a lot of failures!
        """
        locale.setlocale(locale.LC_ALL, ('en_US', 'UTF-8'))

        for val in range(0, LIMIT_UCS, step):
            (start, end) = (val, val + step)
            ucs = u''.join([unichr(_num) for _num in range(start, end)])
            yield self._is_equal_wcswidth, ucs
