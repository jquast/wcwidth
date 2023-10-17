# coding: utf-8
"""Core tests for wcwidth module. isort:skip_file"""
try:
    # std import
    import importlib.metadata as importmeta
except ImportError:
    # 3rd party for python3.7 and earlier
    import importlib_metadata as importmeta

# local
import wcwidth


def test_package_version():
    """wcwidth.__version__ is expected value."""
    # given,
    expected = importmeta.version('wcwidth')

    # exercise,
    result = wcwidth.__version__

    # verify.
    assert result == expected


def test_hello_jp():
    u"""
    Width of Japanese phrase: コンニチハ, セカイ!

    Given a phrase of 5 and 3 Katakana ideographs, joined with
    3 English-ASCII punctuation characters, totaling 11, this
    phrase consumes 19 cells of a terminal emulator.
    """
    # given,
    phrase = u'コンニチハ, セカイ!'
    expect_length_each = (2, 2, 2, 2, 2, 1, 1, 2, 2, 2, 1)
    expect_length_phrase = sum(expect_length_each)

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase
    assert length_phrase == expect_length_phrase


def test_wcswidth_substr():
    """
    Test wcswidth() optional 2nd parameter, ``n``.

    ``n`` determines at which position of the string
    to stop counting length.
    """
    # given,
    phrase = u'コンニチハ, セカイ!'
    end = 7
    expect_length_each = (2, 2, 2, 2, 2, 1, 1,)
    expect_length_phrase = sum(expect_length_each)

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase, end)

    # verify.
    assert length_phrase_wcs == expect_length_phrase


def test_null_width_0():
    """NULL (0) reports width 0."""
    # given,
    phrase = u'abc\x00def'
    expect_length_each = (1, 1, 1, 0, 1, 1, 1)
    expect_length_phrase = sum(expect_length_each)

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase
    assert length_phrase == expect_length_phrase


def test_control_c0_width_negative_1():
    """How the API reacts to CSI (Control sequence initiate)."""
    # given,
    phrase = u'\x1b[0m'
    expect_length_each = (-1, 1, 1, 1)
    expect_length_phrase_wcs = -1
    expect_length_phrase = 3

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify, our API gets it wrong in every case, this is actually
    # of 0 width for a terminal
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase_wcs
    assert length_phrase == expect_length_phrase


def test_control_c0_width_zero():
    """Using width() function reports 0 for ESC in terminal sequence."""
    # given a maybe poor example, as the terminal sequence is a width of 0
    # rendered on all terminals, but wcwidth doesn't parse
    # Control-Sequence-Inducer (CSI) sequences. Also the "legacy" posix
    # functions wcwidth and wcswidth return -1 for any string containing the C1
    # control character \x1b (ESC).
    phrase = u'\x1b[0m'
    expect_length_each = (-1, 1, 1, 1)
    expect_length_phrase_wcs = -1
    expect_length_phrase = 3

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase_wcs
    assert length_phrase == expect_length_phrase


def test_combining_width():
    """Simple test combining reports total width of 4."""
    # given,
    phrase = u'--\u05bf--'
    expect_length_each = (1, 1, 0, 1, 1)
    expect_length_phrase = 4

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase
    assert length_phrase == expect_length_phrase


def test_combining_cafe():
    u"""Phrase cafe + COMBINING ACUTE ACCENT is café of length 4."""
    phrase = u"cafe\u0301"
    expect_length_each = (1, 1, 1, 1, 0)
    expect_length_phrase = 4

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase
    assert length_phrase == expect_length_phrase


def test_combining_enclosing():
    u"""CYRILLIC CAPITAL LETTER A + COMBINING CYRILLIC HUNDRED THOUSANDS SIGN is А҈ of length 1."""
    phrase = u"\u0410\u0488"
    expect_length_each = (1, 0)
    expect_length_phrase = 1

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase
    assert length_phrase == expect_length_phrase


def test_combining_spacing():
    u"""Balinese kapal (ship) is ᬓᬨᬮ᭄ of length 4."""
    phrase = u"\u1B13\u1B28\u1B2E\u1B44"
    expect_length_each = (1, 1, 1, 1)
    expect_length_phrase = 4

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase
    assert length_phrase == expect_length_phrase


def test_kr_jamo_filler():
    u"""
    Jamo filler is 0 width.

    According to https://www.unicode.org/L2/L2006/06310-hangul-decompose9.pdf this character and others
    like it, ``\uffa0``, ``\u1160``, ``\u115f``, ``\u1160``, are not commonly viewed with a terminal,
    seems it doesn't matter whether it is implemented or not, they are not typically used !
    """
    phrase = "\u1100\u1160"
    expect_length_each = (2, 1)
    expect_length_phrase = 3

    # exercise,
    length_each = tuple(map(wcwidth.wcwidth, phrase))
    length_phrase_wcs = wcwidth.wcswidth(phrase)
    length_phrase = wcwidth.width(phrase)

    # verify.
    assert length_each == expect_length_each
    assert length_phrase_wcs == expect_length_phrase
    assert length_phrase == expect_length_phrase
