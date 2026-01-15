"""Tests for sequence-aware text wrapping functions."""
import textwrap

import pytest

from wcwidth import width, iter_sequences
from wcwidth.textwrap import wrap, SequenceTextWrapper

SGR_RED = '\x1b[31m'
SGR_RESET = '\x1b[0m'
ATTRS = ('\x1b[31m', '\x1b[34m', '\x1b[4m', '\x1b[7m', '\x1b[41m', '\x1b[37m', '\x1b[107m')


def _strip(text):
    return ''.join(seg for seg, is_seq in iter_sequences(text) if not is_seq)


def _colorize(text):
    return ''.join(
        ATTRS[idx % len(ATTRS)] + char + SGR_RESET if char not in ' -' else char
        for idx, char in enumerate(text)
    )


BASIC_WRAP_CASES = [
    ('hello world', 5, ['hello', 'world']),
    ('', 10, []),
    ('   ', 10, []),
    ('hello', 5, ['hello']),
    ('hi', 10, ['hi']),
    ('hello   world', 20, ['hello   world']),
]


@pytest.mark.parametrize('text,w,expected', BASIC_WRAP_CASES)
def test_wrap_basic(text, w, expected):
    assert wrap(text, w) == expected


LONG_WORD_CASES = [
    ('abcdefghij', 3, True, True, ['abc', 'def', 'ghi', 'j']),
    ('abcdefghij', 3, False, True, ['abcdefghij']),
    ('abcdefghijklmnopqrstuvwxyz', 5, True, True, ['abcde', 'fghij', 'klmno', 'pqrst', 'uvwxy', 'z']),
]


@pytest.mark.parametrize('text,w,break_long,break_graphemes,expected', LONG_WORD_CASES)
def test_wrap_long_words(text, w, break_long, break_graphemes, expected):
    result = wrap(text, w, break_long_words=break_long, break_on_graphemes=break_graphemes)
    assert result == expected


SEQUENCE_WRAP_CASES = [
    ('\x1b[31mhello world\x1b[0m', 5, ['hello', 'world']),
    ('x\x1b[31mabcdefghij\x1b[0m', 3, ['xab', 'cde', 'fgh', 'ij']),
    ('abc\x1bdefghij', 3, ['abc', 'def', 'ghi', 'j']),
]


@pytest.mark.parametrize('text,w,expected_stripped', SEQUENCE_WRAP_CASES)
def test_wrap_sequences(text, w, expected_stripped):
    result = wrap(text, w, break_on_graphemes=True)
    assert [_strip(line) for line in result] == expected_stripped


INDENT_CASES = [
    ('hello world', 10, '> ', '', ['> hello', 'world']),
    ('hello world foo bar', 8, '', '  ', ['hello', '  world', '  foo', '  bar']),
]


@pytest.mark.parametrize('text,w,initial,subsequent,expected', INDENT_CASES)
def test_wrap_indents(text, w, initial, subsequent, expected):
    result = wrap(text, w, initial_indent=initial, subsequent_indent=subsequent)
    assert result == expected


CJK_HELLO = '\u30b3\u30f3\u30cb\u30c1\u30cf'
EMOJI_WOMAN = '\U0001F469'
EMOJI_FAMILY = '\U0001F468\u200D\U0001F469\u200D\U0001F467'
EMOJI_TRIO = '\U0001F469\U0001F467\U0001F466'
CAFE_COMBINING = 'cafe\u0301'
HANGUL_GA = '\u1100\u1161'

UNICODE_WRAP_CASES = [
    ('\u4e2d\u6587 test', 5, 4),
    (CJK_HELLO, 4, 4),
    ('\u5973', 1, 2),
    (EMOJI_WOMAN, 2, 2),
    (EMOJI_FAMILY, 2, 2),
    (HANGUL_GA, 2, 2),
]


@pytest.mark.parametrize('text,w,max_width', UNICODE_WRAP_CASES)
def test_wrap_unicode(text, w, max_width):
    result = wrap(text, w)
    assert len(result) >= 1
    for line in result:
        assert width(line) <= max_width


EMOJI_WIDTH_CASES = [
    (EMOJI_TRIO, 2, list(EMOJI_TRIO)),
    (EMOJI_TRIO, 3, list(EMOJI_TRIO)),
    (EMOJI_TRIO, 4, ['\U0001F469\U0001F467', '\U0001F466']),
    (EMOJI_TRIO, 5, ['\U0001F469\U0001F467', '\U0001F466']),
    (EMOJI_TRIO, 6, ['\U0001F469\U0001F467\U0001F466']),
    (EMOJI_TRIO, 7, ['\U0001F469\U0001F467\U0001F466']),
]


@pytest.mark.parametrize('text,w,expected', EMOJI_WIDTH_CASES)
def test_wrap_emojis_width(text, w, expected):
    assert wrap(text, w) == expected


ZWJ_FAMILY_WWGB = '\U0001F469\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466'

ZWJ_WIDTH_1_CASES = [
    ('\u5973', 1, ['\u5973']),
    (ZWJ_FAMILY_WWGB, 1, [ZWJ_FAMILY_WWGB]),
    (HANGUL_GA, 1, [HANGUL_GA]),
]


@pytest.mark.parametrize('text,w,expected', ZWJ_WIDTH_1_CASES)
def test_wrap_zwj_width_1(text, w, expected):
    assert wrap(text, w) == expected


COMBINING_CHAR_CASES = [
    (CAFE_COMBINING + '-latte', 5, False, ['cafe\u0301-', 'latte']),
    (CAFE_COMBINING + '-latte', 4, False, ['cafe\u0301', '-lat', 'te']),
    (CAFE_COMBINING + '-latte', 3, False, ['caf', 'e\u0301-l', 'att', 'e']),
    (CAFE_COMBINING + '-latte', 2, False, ['ca', 'fe\u0301', '-l', 'at', 'te']),
]


@pytest.mark.parametrize('text,w,break_hyphens,expected', COMBINING_CHAR_CASES)
def test_wrap_combining_characters(text, w, break_hyphens, expected):
    assert wrap(text, w, break_on_hyphens=break_hyphens) == expected


HYPHENATION_CASES = [
    ('hello-world', 6, True),
    ('hello-world', 8, True),
    ('hello-world', 6, False),
    ('hello-world', 8, False),
    ('super-long-hyphenated-word', 10, True),
    ('super-long-hyphenated-word', 10, False),
    ('a-b-c-d', 3, True),
    ('a-b-c-d', 3, False),
]


@pytest.mark.parametrize('text,w,break_hyphens', HYPHENATION_CASES)
def test_wrap_hyphenation_matches_stdlib(text, w, break_hyphens):
    expected = textwrap.wrap(text, width=w, break_on_hyphens=break_hyphens)
    result = wrap(text, w, break_on_hyphens=break_hyphens)
    assert result == expected


@pytest.mark.parametrize('text,w,break_hyphens', HYPHENATION_CASES)
def test_wrap_hyphenation_colored_matches_stdlib(text, w, break_hyphens):
    text_colored = _colorize(text)
    expected = textwrap.wrap(text, width=w, break_on_hyphens=break_hyphens)
    result = wrap(text_colored, w, break_on_hyphens=break_hyphens)
    assert [_strip(line) for line in result] == expected


BREAK_ON_HYPHENS_LONG_WORD_CASES = [
    ('a-b-c-d', 3, True, ['a-', 'b-', 'c-d']),
    ('a-b-c-d', 3, False, ['a-b', '-c-', 'd']),
    ('one-two-three-four', 5, True, ['one-', 'two-t', 'hree-', 'four']),
    ('one-two-three-four', 5, False, ['one-t', 'wo-th', 'ree-f', 'our']),
    ('ab-cd-ef', 4, True, ['ab-', 'cd-', 'ef']),
    ('ab-cd-ef', 4, False, ['ab-c', 'd-ef']),
    ('---', 2, True, ['--', '-']),
    ('---', 2, False, ['--', '-']),
    ('a---b', 2, True, ['a-', '--', 'b']),
    ('a---b', 2, False, ['a-', '--', 'b']),
]


@pytest.mark.parametrize('text,w,break_hyphens,expected', BREAK_ON_HYPHENS_LONG_WORD_CASES)
def test_wrap_break_on_hyphens_long_word(text, w, break_hyphens, expected):
    result = wrap(text, w, break_on_hyphens=break_hyphens)
    assert result == expected


def test_wrap_multiline_matches_stdlib():
    given = '\n' + 32 * 'A' + '\n' + 32 * 'B' + '\n' + 32 * 'C' + '\n\n'
    expected = textwrap.wrap(given, 30)
    assert wrap(given, 30) == expected


TEXTWRAP_KEYWORD_COMBINATIONS = [
    {'break_long_words': False, 'drop_whitespace': False, 'subsequent_indent': ''},
    {'break_long_words': False, 'drop_whitespace': True, 'subsequent_indent': ''},
    {'break_long_words': False, 'drop_whitespace': False, 'subsequent_indent': ' '},
    {'break_long_words': False, 'drop_whitespace': True, 'subsequent_indent': ' '},
    {'break_long_words': True, 'drop_whitespace': False, 'subsequent_indent': ''},
    {'break_long_words': True, 'drop_whitespace': True, 'subsequent_indent': ''},
    {'break_long_words': True, 'drop_whitespace': False, 'subsequent_indent': ' '},
    {'break_long_words': True, 'drop_whitespace': True, 'subsequent_indent': ' '},
    {'break_long_words': True, 'drop_whitespace': True, 'break_on_hyphens': True},
    {'break_long_words': True, 'drop_whitespace': True, 'break_on_hyphens': False},
]


@pytest.mark.parametrize('kwargs', TEXTWRAP_KEYWORD_COMBINATIONS)
@pytest.mark.parametrize('many_columns', [10, 20, 40])
def test_wrap_matches_stdlib(kwargs, many_columns):
    pgraph = ' Z! a bc defghij klmnopqrstuvw<<>>xyz012345678900 ' * 2
    pgraph_colored = _colorize(pgraph)

    internal_wrapped = textwrap.wrap(pgraph, width=many_columns, **kwargs)
    wrapper = SequenceTextWrapper(width=many_columns, **kwargs)
    my_wrapped = wrapper.wrap(pgraph)
    my_wrapped_colored = wrapper.wrap(pgraph_colored)

    assert internal_wrapped == my_wrapped
    assert [_strip(line) for line in my_wrapped_colored] == internal_wrapped
    assert len(internal_wrapped) == len(my_wrapped_colored)


WRAPPER_WIDTH_CASES = [
    ('hello', 5),
    ('\u4e2d\u6587', 4),
    ('\x1b[31mhi\x1b[0m', 2),
]


@pytest.mark.parametrize('text,expected', WRAPPER_WIDTH_CASES)
def test_sequence_text_wrapper_width(text, expected):
    wrapper = SequenceTextWrapper(width=10)
    assert wrapper._width(text) == expected


def test_sequence_text_wrapper_basic():
    wrapper = SequenceTextWrapper(width=5)
    assert wrapper.wrap('hello world') == ['hello', 'world']


def test_sequence_text_wrapper_strip_sequences():
    wrapper = SequenceTextWrapper(width=10)
    assert wrapper._strip_sequences('\x1b[31mred\x1b[0m') == 'red'


def test_sequence_text_wrapper_options():
    assert SequenceTextWrapper(width=20, tabstop=4).tabstop == 4
    assert SequenceTextWrapper(width=20, control_codes='ignore').control_codes == 'ignore'
    assert len(SequenceTextWrapper(width=10, drop_whitespace=False).wrap('hello   world')) >= 1


def test_wrap_colored_matches_plain():
    plain = 'hello world foo bar'
    colored = _colorize(plain)
    assert len(wrap(plain, 10)) == len(wrap(colored, 10))


def test_wrap_sequences_preserved():
    result = wrap('x\x1b[31mabcdefghij\x1b[0m', 3, break_on_graphemes=True)
    joined = ''.join(result)
    assert '\x1b[31m' in joined
    assert '\x1b[0m' in joined


def test_wrap_lone_esc():
    result = wrap('abc\x1bdefghij', 3, break_on_graphemes=True)
    joined = ''.join(result)
    assert '\x1b' in joined
