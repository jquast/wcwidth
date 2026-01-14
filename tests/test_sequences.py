"""Tests for sequence-aware text manipulation functions."""
import pytest

from wcwidth import (
    iter_sequences,
    ljust,
    rjust,
    center,
    wrap,
    width,
    SequenceTextWrapper,
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


def _strip(text):
    return ''.join(seg for seg, is_seq in iter_sequences(text) if not is_seq)


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
