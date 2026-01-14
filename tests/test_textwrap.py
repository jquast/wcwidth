"""Tests for sequence-aware text wrapping functions."""
import pytest

from wcwidth import (
    width,
)
from wcwidth.textwrap import (
    iter_sequences,
    wrap,
    SequenceTextWrapper,
)

# Common test strings
SGR_RED = '\x1b[31m'
SGR_RESET = '\x1b[0m'

# CJK test strings
CJK_HELLO = 'コンニチハ'  # 10 cells (5 chars * 2)

# Emoji test strings
EMOJI_WOMAN = '\U0001F469'  # 2 cells
EMOJI_FAMILY = '\U0001F468\u200D\U0001F469\u200D\U0001F467'  # ZWJ sequence, 2 cells
EMOJI_TRIO = '\U0001F469\U0001F467\U0001F466'  # 6 cells (3 * 2)

# Combining marks
CAFE_COMBINING = 'cafe\u0301'  # café with combining acute, 4 cells

# Hangul (composes to wide character)
HANGUL_GA = '\u1100\u1161'  # CHOSEONG KIYEOK + JUNGSEONG A


def _strip(text):
    return ''.join(seg for seg, is_seq in iter_sequences(text) if not is_seq)


def test_wrap_basic():
    assert wrap('hello world', 5) == ['hello', 'world']
    assert wrap('', 10) == []  # empty string
    assert wrap('   ', 10) == []  # whitespace only
    assert wrap('hello', 5) == ['hello']  # exact width
    assert wrap('hi', 10) == ['hi']  # shorter than width


def test_wrap_long_words():
    # break on graphemes
    assert wrap('abcdefghij', 3, break_on_graphemes=True) == ['abc', 'def', 'ghi', 'j']
    # no break
    assert wrap('abcdefghij', 3, break_long_words=False) == ['abcdefghij']
    # very long word
    result = wrap('abcdefghijklmnopqrstuvwxyz', 5, break_on_graphemes=True)
    assert len(result) >= 5
    for line in result:
        assert width(line) <= 5


def test_wrap_sequences():
    result = wrap('\x1b[31mhello world\x1b[0m', 5)
    assert len(result) == 2
    assert _strip(result[0]) == 'hello'
    assert _strip(result[1]) == 'world'
    # long word with sequences
    result = wrap(f'x{SGR_RED}abcdefghij{SGR_RESET}', 3, break_on_graphemes=True)
    assert len(result) >= 2 and SGR_RED in ''.join(result)
    # unmatched escape in word
    assert len(wrap('abc\x1bdefghij', 3, break_on_graphemes=True)) >= 1


def test_wrap_indents():
    result = wrap('hello world', 10, initial_indent='> ')
    assert result[0].startswith('> ')
    result = wrap('hello world foo bar', 8, subsequent_indent='  ')
    if len(result) > 1:
        assert result[1].startswith('  ')
    # long word with indent
    assert len(wrap('abcdefghij', 5, break_on_graphemes=True, initial_indent='> ')) >= 1


def test_wrap_unicode():
    # wide characters
    assert len(wrap('\u4e2d\u6587 test', 5)) >= 1
    # CJK
    result = wrap(CJK_HELLO, 4)
    for line in result:
        assert width(line) <= 4
    # CJK at width 1 (can't fit, but shouldn't crash)
    assert wrap('\u5973', 1) == ['\u5973']
    # emoji at width 2
    assert wrap(EMOJI_WOMAN, 2) == [EMOJI_WOMAN]
    # emoji trio
    for line in wrap(EMOJI_TRIO, 4):
        assert width(line) <= 4
    # ZWJ family
    assert wrap(EMOJI_FAMILY, 2) == [EMOJI_FAMILY]
    # combining marks kept together
    for line in wrap(f'{CAFE_COMBINING}-latte', 5, break_on_hyphens=False):
        if 'cafe' in line:
            assert '\u0301' in line
    # various widths for combining marks
    for w in [5, 4, 3, 2]:
        assert len(wrap(CAFE_COMBINING, w)) >= 1
    # hangul
    assert len(wrap(HANGUL_GA, 2)) >= 1
    # mixed ASCII + CJK
    for line in wrap('hello\u4e2d\u6587world', 8):
        assert width(line) <= 8
    # long CJK word
    for line in wrap(CJK_HELLO + CJK_HELLO, 6, break_on_graphemes=True):
        assert width(line) <= 6


def test_wrap_hyphenation():
    import textwrap

    # Test that behavior matches stdlib exactly for various cases
    test_cases = [
        ('hello-world', 6),
        ('hello-world', 8),
        ('super-long-hyphenated-word', 10),
        ('a-b-c-d', 3),
    ]
    for text, w in test_cases:
        for break_hyphens in [True, False]:
            expected = textwrap.wrap(text, width=w, break_on_hyphens=break_hyphens)
            result = wrap(text, w, break_on_hyphens=break_hyphens)
            assert result == expected

    # With sequences: content should match when stripped
    text_colored = '\x1b[31mhello-world\x1b[0m'
    result = wrap(text_colored, 6, break_on_hyphens=True)
    assert len(result) == 2
    assert _strip(result[0]) == 'hello-'
    assert _strip(result[1]) == 'world'


def test_wrap_break_on_hyphens_in_handle_long_word():
    import textwrap

    text = 'a-b-c-d'
    w = 3

    result = wrap(text, width=w, break_on_hyphens=True)
    expected = textwrap.wrap(text, width=w, break_on_hyphens=True)
    assert result == expected

    result = wrap(text, width=w, break_on_hyphens=False)
    expected = textwrap.wrap(text, width=w, break_on_hyphens=False)
    assert result == expected


def test_wrap_break_on_hyphens_colored():
    import textwrap

    ATTRS = ('\x1b[31m', '\x1b[34m', '\x1b[4m')

    test_cases = [
        ('hello-world', 8),
        ('super-long-hyphenated-word', 10),
        ('a-b-c-d', 3),
    ]

    for text, w in test_cases:
        # Create colored version: each character (except hyphen) gets a color
        text_colored = ''
        attr_idx = 0
        for char in text:
            if char == '-':
                text_colored += char
            else:
                text_colored += ATTRS[attr_idx % len(ATTRS)] + char + '\x1b[0m'
                attr_idx += 1

        for break_hyphens in [True, False]:
            expected = textwrap.wrap(text, width=w, break_on_hyphens=break_hyphens)
            result_plain = wrap(text, w, break_on_hyphens=break_hyphens)
            result_colored = wrap(text_colored, w, break_on_hyphens=break_hyphens)
            result_stripped = [_strip(line) for line in result_colored]

            assert result_plain == expected
            assert result_stripped == expected


def test_wrap_whitespace():
    assert len(wrap('hello   world', 20)) == 1  # multiple spaces
    assert len(wrap('line1\nline2\nline3', 10)) >= 1  # multiline


def test_wrap_colored_matches_plain():
    plain = 'hello world foo bar'
    colored = ''.join(f'\x1b[{31 + i % 7}m{ch}\x1b[0m' for i, ch in enumerate(plain))
    assert len(wrap(plain, 10)) == len(wrap(colored, 10))


def test_sequence_text_wrapper():
    wrapper = SequenceTextWrapper(width=5)
    assert wrapper.wrap('hello world') == ['hello', 'world']
    # width measurement
    wrapper = SequenceTextWrapper(width=10)
    assert wrapper._width('hello') == 5
    assert wrapper._width('\u4e2d\u6587') == 4
    assert wrapper._width('\x1b[31mhi\x1b[0m') == 2
    # strip sequences
    assert wrapper._strip_sequences('\x1b[31mred\x1b[0m') == 'red'
    # custom tabstop
    assert SequenceTextWrapper(width=20, tabstop=4).tabstop == 4
    # control_codes parameter
    assert SequenceTextWrapper(width=20, control_codes='ignore').control_codes == 'ignore'
    # drop_whitespace=False
    assert len(SequenceTextWrapper(width=10, drop_whitespace=False).wrap('hello   world')) >= 1


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


@pytest.mark.parametrize("kwargs", TEXTWRAP_KEYWORD_COMBINATIONS)
@pytest.mark.parametrize("many_columns", [10, 20, 40])
def test_wrap_matches_stdlib(kwargs, many_columns):
    import textwrap

    ATTRS = ('\x1b[31m', '\x1b[34m', '\x1b[4m', '\x1b[7m', '\x1b[41m', '\x1b[37m', '\x1b[107m')
    pgraph = ' Z! a bc defghij klmnopqrstuvw<<>>xyz012345678900 ' * 2

    pgraph_colored = ''.join(
        ATTRS[idx % len(ATTRS)] + char + '\x1b[0m' if char != ' ' else ' '
        for idx, char in enumerate(pgraph))

    internal_wrapped = textwrap.wrap(pgraph, width=many_columns, **kwargs)
    wrapper = SequenceTextWrapper(width=many_columns, **kwargs)
    my_wrapped = wrapper.wrap(pgraph)
    my_wrapped_colored = wrapper.wrap(pgraph_colored)

    assert internal_wrapped == my_wrapped

    for left, right in zip(internal_wrapped, my_wrapped_colored):
        assert left == _strip(right)

    assert len(internal_wrapped) == len(my_wrapped_colored)


def test_wrap_emojis_width_2_and_greater():
    given = '\U0001F469\U0001F467\U0001F466'  # woman, girl, boy
    assert wrap(given, 2) == list(given)
    assert wrap(given, 3) == list(given)
    assert wrap(given, 4) == ['\U0001F469\U0001F467', '\U0001F466']
    assert wrap(given, 5) == ['\U0001F469\U0001F467', '\U0001F466']
    assert wrap(given, 6) == ['\U0001F469\U0001F467\U0001F466']
    assert wrap(given, 7) == ['\U0001F469\U0001F467\U0001F466']


def test_wrap_combining_characters():
    given = 'cafe\u0301-latte'
    assert wrap(given, 5, break_on_hyphens=False) == ['cafe\u0301-', 'latte']
    assert wrap(given, 4, break_on_hyphens=False) == ['cafe\u0301', '-lat', 'te']
    assert wrap(given, 3, break_on_hyphens=False) == ['caf', 'e\u0301-l', 'att', 'e']
    assert wrap(given, 2, break_on_hyphens=False) == ['ca', 'fe\u0301', '-l', 'at', 'te']
