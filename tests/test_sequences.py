"""Tests for sequence-aware text manipulation functions."""
import pytest

from wcwidth import (
    iter_sequences,
    ljust,
    rjust,
    center,
    width,
)

# Common test strings
SGR_RED = '\x1b[31m'
SGR_BOLD = '\x1b[1m'
SGR_RESET = '\x1b[0m'
CSI_RIGHT_2 = '\x1b[2C'
OSC_TITLE = '\x1b]0;title\x07'

# CJK test strings
CJK_HELLO = 'コンニチハ'  # 10 cells (5 chars * 2)
CJK_WORD = '\u4e2d\u6587'  # 4 cells (2 chars * 2)

# Emoji test strings
EMOJI_WOMAN = '\U0001F469'  # 2 cells
EMOJI_FAMILY = '\U0001F468\u200D\U0001F469\u200D\U0001F467'  # ZWJ sequence, 2 cells
EMOJI_TRIO = '\U0001F469\U0001F467\U0001F466'  # 6 cells (3 * 2)

# Combining marks
CAFE_COMBINING = 'cafe\u0301'  # café with combining acute, 4 cells

# Hangul (composes to wide character)
HANGUL_GA = '\u1100\u1161'  # CHOSEONG KIYEOK + JUNGSEONG A


def test_iter_sequences_basic():
    # plain text
    assert list(iter_sequences('hello')) == [('hello', False)]
    # empty string
    assert list(iter_sequences('')) == []
    # SGR sequence
    assert list(iter_sequences('\x1b[31mred\x1b[0m')) == [
        ('\x1b[31m', True), ('red', False), ('\x1b[0m', True)]
    # OSC sequence
    assert list(iter_sequences('\x1b]0;title\x07text')) == [
        ('\x1b]0;title\x07', True), ('text', False)]
    # cursor movement
    assert list(iter_sequences('a\x1b[2Cb')) == [
        ('a', False), ('\x1b[2C', True), ('b', False)]
    # Fe sequence (ESC + 0x40-0x5F)
    assert list(iter_sequences('\x1bX')) == [('\x1bX', True)]
    # wide characters
    assert list(iter_sequences(CJK_WORD)) == [(CJK_WORD, False)]
    # combining marks
    assert list(iter_sequences(CAFE_COMBINING)) == [(CAFE_COMBINING, False)]


def test_iter_sequences_edge_cases():
    # escape alone at end - not a sequence
    assert list(iter_sequences('abc\x1b')) == [('abc\x1b', False)]
    # unmatched escape followed by sequence
    assert list(iter_sequences('\x1b\x1b[31mred')) == [
        ('\x1b', False), ('\x1b[31m', True), ('red', False)]
    # Fe sequence with trailing text
    assert list(iter_sequences('\x1bXYZ')) == [('\x1bX', True), ('YZ', False)]


def test_iter_sequences_mixed():
    # mixed content
    assert list(iter_sequences('a\x1b[1mb\x1b[0mc')) == [
        ('a', False), ('\x1b[1m', True), ('b', False), ('\x1b[0m', True), ('c', False)]
    # multiple consecutive SGR
    assert list(iter_sequences('\x1b[1m\x1b[31mX\x1b[0m')) == [
        ('\x1b[1m', True), ('\x1b[31m', True), ('X', False), ('\x1b[0m', True)]
    # CSI cursor position
    assert list(iter_sequences('\x1b[5;10HAB')) == [('\x1b[5;10H', True), ('AB', False)]


def test_iter_sequences_fp_sequences():
    # cursor save/restore (Fp sequences ESC 7, ESC 8)
    assert list(iter_sequences('\x1b7AB\x1b8CD')) == [
        ('\x1b7', True), ('AB', False), ('\x1b8', True), ('CD', False)]
    # keypad modes (ESC =, ESC >)
    assert list(iter_sequences('\x1b=AB\x1b>CD')) == [
        ('\x1b=', True), ('AB', False), ('\x1b>', True), ('CD', False)]
    # character set designation
    assert list(iter_sequences('\x1b(0abc')) == [('\x1b(0', True), ('abc', False)]


def test_iter_sequences_hyperlink():
    hyperlink = '\x1b]8;;https://example.com\x07link\x1b]8;;\x07'
    assert list(iter_sequences(hyperlink)) == [
        ('\x1b]8;;https://example.com\x07', True),
        ('link', False),
        ('\x1b]8;;\x07', True)]


def test_ljust_basic():
    assert ljust('hi', 5) == 'hi   '
    assert ljust('', 5) == '     '  # empty string
    assert ljust('hello', 3) == 'hello'  # already wider
    assert ljust('hello', 5) == 'hello'  # exact width
    assert ljust('\x1b[31mhi\x1b[0m', 5) == '\x1b[31mhi\x1b[0m   '  # with sequences
    assert ljust('\u4e2d', 4) == '\u4e2d  '  # wide character


def test_ljust_fillchar():
    assert ljust('hi', 5, fillchar='-') == 'hi---'  # custom fillchar
    assert ljust('hi', 6, fillchar='\u4e2d') == 'hi\u4e2d\u4e2d'  # wide fillchar
    # empty fillchar raises
    with pytest.raises(ValueError):
        ljust('hi', 5, fillchar='')
    # zero-width fillchar raises
    with pytest.raises(ValueError):
        ljust('hi', 5, fillchar='\u0301')


def test_ljust_unicode():
    # CJK
    assert ljust(CJK_WORD, 8) == CJK_WORD + '    '
    assert width(ljust(CJK_WORD, 8)) == 8
    # combining marks
    assert width(ljust(CAFE_COMBINING, 8)) == 8
    # ZWJ emoji
    assert width(ljust(EMOJI_FAMILY, 6)) == 6


def test_ljust_control_codes():
    text = f'{SGR_RED}hi{SGR_RESET}'
    # ignore mode measures without sequences
    assert len(ljust(text, 6, control_codes='ignore')) - len(SGR_RED) - len(SGR_RESET) == 6


def test_rjust_basic():
    assert rjust('hi', 5) == '   hi'
    assert rjust('', 5) == '     '  # empty string
    assert rjust('hello', 3) == 'hello'  # already wider
    assert rjust('hello', 5) == 'hello'  # exact width
    assert rjust('\x1b[31mhi\x1b[0m', 5) == '   \x1b[31mhi\x1b[0m'  # with sequences
    assert rjust('\u4e2d', 4) == '  \u4e2d'  # wide character
    assert rjust('hi', 5, fillchar='-') == '---hi'  # custom fillchar


def test_rjust_fillchar_errors():
    with pytest.raises(ValueError):
        rjust('hi', 5, fillchar='')
    with pytest.raises(ValueError):
        rjust('hi', 5, fillchar='\u0301')


def test_rjust_unicode():
    assert rjust(CJK_WORD, 8) == '    ' + CJK_WORD
    assert width(rjust(CAFE_COMBINING, 8)) == 8
    assert width(rjust(EMOJI_FAMILY, 6)) == 6


def test_center_basic():
    assert center('hi', 6) == '  hi  '  # even padding
    assert center('hi', 5) == ' hi  '  # odd padding, extra on right
    assert center('', 4) == '    '  # empty string
    assert center('hello', 3) == 'hello'  # already wider
    assert center('hello', 5) == 'hello'  # exact width
    assert center('\x1b[31mhi\x1b[0m', 6) == '  \x1b[31mhi\x1b[0m  '  # with sequences
    assert center('\u4e2d', 6) == '  \u4e2d  '  # wide character
    assert center('hi', 6, fillchar='-') == '--hi--'  # custom fillchar
    assert center('x', 4) == ' x  '  # odd padding verification


def test_center_fillchar_errors():
    with pytest.raises(ValueError):
        center('hi', 6, fillchar='')
    with pytest.raises(ValueError):
        center('hi', 6, fillchar='\u0301')


def test_center_unicode():
    assert width(center(CJK_WORD, 8)) == 8
    assert width(center(CAFE_COMBINING, 8)) == 8
    assert width(center(EMOJI_FAMILY, 6)) == 6
    assert '\u4e2d' in center('x', 5, fillchar='\u4e2d')  # wide fillchar
