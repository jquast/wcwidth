"""Tests for clip() and strip_sequences() functions."""

# std imports
import os
import sys
import importlib
from itertools import product

# 3rd party
import pytest

# local
import wcwidth._clip as _clip_module
from wcwidth import clip, width, propagate_sgr, strip_sequences
from wcwidth.escape_sequences import _HORIZONTAL_CURSOR_MOVEMENT

STRIP_SEQUENCES_CASES = [
    ('', ''),
    ('hello', 'hello'),
    ('hello world', 'hello world'),
    ('\x1b[31m', ''),
    ('\x1b[0m', ''),
    ('\x1b[m', ''),
    ('\x1b[31mred\x1b[0m', 'red'),
    ('\x1b[1m\x1b[31mbold red\x1b[0m', 'bold red'),
    ('\x1b[1m\x1b[31m\x1b[4m', ''),
    ('\x1b[1mbold\x1b[0m \x1b[3mitalic\x1b[0m', 'bold italic'),
    ('\x1b]0;title\x07', ''),
    ('\x1b]0;title\x07text', 'text'),
    ('\x1b]8;;https://example.com\x07link\x1b]8;;\x07', 'link'),
    ('\x1b[31m中文\x1b[0m', '中文'),
    ('\x1b[1m\U0001F468\u200D\U0001F469\u200D\U0001F467\x1b[0m',
     '\U0001F468\u200D\U0001F469\u200D\U0001F467'),
    ('\x1b', '\x1b'),
    ('a\x1bb', 'a'),
    ('\x1b[', ''),
    ('text\x1b[mmore', 'textmore'),
]


@pytest.mark.parametrize('text,expected', STRIP_SEQUENCES_CASES)
def test_strip_sequences(text, expected):
    assert strip_sequences(text) == expected


CLIP_BASIC_CASES = [
    ('', 0, 5, ''),
    ('', 0, 0, ''),
    ('hello', 0, 0, ''),
    ('hello', 5, 5, ''),
    ('hello', 5, 3, ''),
    ('hello', -5, 3, 'hel'),
    ('hello', 0, 5, 'hello'),
    ('hello', 0, 3, 'hel'),
    ('hello', 2, 5, 'llo'),
    ('hello', 1, 4, 'ell'),
    ('hello world', 0, 5, 'hello'),
    ('hello world', 6, 11, 'world'),
    ('hello world', 0, 11, 'hello world'),
    ('hi', 0, 100, 'hi'),
    ('hi', 100, 200, ''),
]


@pytest.mark.parametrize('text,start,end,expected', CLIP_BASIC_CASES)
def test_clip_basic(text, start, end, expected):
    assert clip(text, start, end) == expected


CLIP_CJK_CASES = [
    ('中文字', 0, 6, '中文字'),
    ('中文字', 0, 4, '中文'),
    ('中文字', 0, 2, '中'),
    ('中文字', 2, 4, '文'),
    ('中文字', 0, 3, '中 '),
    ('中文字', 1, 6, ' 文字'),
    ('中文字', 1, 5, ' 文 '),
    ('A中B', 0, 4, 'A中B'),
    ('A中B', 0, 3, 'A中'),
    ('A中B', 1, 4, '中B'),
    ('A中B', 1, 3, '中'),
    ('A中B', 2, 4, ' B'),
    ('中', 0, 2, '中'),
    ('中', 0, 1, ' '),
    ('中', 1, 2, ' '),
]


@pytest.mark.parametrize('text,start,end,expected', CLIP_CJK_CASES)
def test_clip_cjk(text, start, end, expected):
    assert clip(text, start, end) == expected


def test_clip_cjk_custom_fillchar():
    assert clip('中文字', 1, 5, fillchar='.') == '.文.'
    assert clip('中文', 1, 3, fillchar='\u00b7') == '\u00b7\u00b7'


CLIP_CJK_WIDTH_CASES = [
    ('中文字', 0, 6, 6),
    ('中文字', 0, 3, 3),
    ('中文字', 1, 6, 5),
    ('中文字', 1, 5, 4),
]


@pytest.mark.parametrize('text,start,end,expected_width', CLIP_CJK_WIDTH_CASES)
def test_clip_cjk_width_consistency(text, start, end, expected_width):
    assert width(clip(text, start, end)) == expected_width


def test_clip_sequences_preserve_sgr():
    result = clip('\x1b[31mred\x1b[0m', 0, 3)
    assert result == '\x1b[31mred\x1b[0m'
    assert strip_sequences(result) == 'red'


def test_clip_sequences_before_start():
    assert clip('\x1b[31mred text\x1b[0m', 4, 8) == '\x1b[31mtext\x1b[0m'


def test_clip_sequences_after_end():
    # With propagate_sgr=True (default), no style active at start, so no prefix
    assert clip('hello\x1b[31m world\x1b[0m', 0, 5) == 'hello'
    # With propagate_sgr=False, all sequences preserved
    assert repr(clip('hello\x1b[31m world\x1b[0m', 0, 5, propagate_sgr=False)) == repr('hello\x1b[31m\x1b[0m')


def test_clip_sequences_multiple():
    # With propagate_sgr=True (default), sequences collapsed to minimal
    assert clip('\x1b[1m\x1b[31mbold red\x1b[0m', 0, 4) == '\x1b[1;31mbold\x1b[0m'
    # With propagate_sgr=False, all sequences preserved separately
    assert repr(clip('\x1b[1m\x1b[31mbold red\x1b[0m', 0, 4, propagate_sgr=False)) == repr('\x1b[1m\x1b[31mbold\x1b[0m')


def test_clip_sequences_only():
    # With propagate_sgr=True (default), no visible text means empty result
    assert clip('\x1b[31m\x1b[0m', 0, 10) == ''
    # With propagate_sgr=False, sequences preserved
    assert repr(clip('\x1b[31m\x1b[0m', 0, 10, propagate_sgr=False)) == repr('\x1b[31m\x1b[0m')


SGR_PATH_KWARGS = [{}, {'overtyping': True}, {'control_codes': 'ignore'}]


@pytest.mark.parametrize('kwargs', SGR_PATH_KWARGS)
def test_clip_sgr_inside_window_preserved(kwargs):
    """Style changes within (start, end) are emitted at their original position."""
    # nothing is clipped away, so nothing changes,
    assert (clip('\x1b[1mbold\x1b[m normal', 0, 20, **kwargs) ==
            '\x1b[1mbold\x1b[m normal')
    # and the same holds when the tail is clipped, the trailing reset is
    # synthesized because the final style is still active.
    assert (clip('\x1b[31mred\x1b[32mgreen\x1b[0m', 0, 4, **kwargs) ==
            '\x1b[31mred\x1b[32mg\x1b[0m')


@pytest.mark.parametrize('kwargs', SGR_PATH_KWARGS)
def test_clip_sgr_before_start_folded_into_prefix(kwargs):
    """Style set before *start* is synthesized as a prefix, not emitted twice."""
    assert clip('\x1b[1;34mHello world\x1b[0m', 6, 11, **kwargs) == '\x1b[1;34mworld\x1b[0m'
    # the style in effect at *start* is the most recent one,
    assert clip('\x1b[31mred\x1b[32mgreen\x1b[0m', 4, 8, **kwargs) == '\x1b[32mreen\x1b[0m'


@pytest.mark.parametrize('kwargs', SGR_PATH_KWARGS)
def test_clip_sgr_after_end_discarded(kwargs):
    """Style set at or beyond *end* does not appear in the result."""
    assert clip('hello\x1b[31m world\x1b[0m', 0, 5, **kwargs) == 'hello'


@pytest.mark.parametrize('kwargs', SGR_PATH_KWARGS)
@pytest.mark.parametrize('text', [
    'plain text',
    '\x1b[31mred',
    '\x1b[31mred\x1b[0m',
    '\x1b[1mbold\x1b[m normal',
    '\x1b[31mred\x1b[32mgreen\x1b[0m',
    'plain \x1b[4munderline',
])
def test_clip_matches_propagate_sgr(text, kwargs):
    """Clipping nothing away agrees with :func:`propagate_sgr`."""
    assert clip(text, 0, width(text), **kwargs) == propagate_sgr([text])[0]


@pytest.mark.parametrize('kwargs', SGR_PATH_KWARGS)
@pytest.mark.parametrize('text', [
    '\x1b[1m\x1b[31mbold red\x1b[0m',
    '\x1b[31mred\x1b[32mgreen\x1b[0m',
    '\x1b[?25l\x1b[31mred',
])
def test_clip_sgr_result_is_self_contained(text, kwargs):
    """The result carries its own style: propagating it again is a no-op."""
    result = clip(text, 0, width(text), **kwargs)
    assert propagate_sgr([result])[0] == result
    assert strip_sequences(result) == strip_sequences(text)


@pytest.mark.parametrize('kwargs', SGR_PATH_KWARGS)
def test_clip_sgr_after_non_sgr_sequence(kwargs):
    """A non-SGR sequence before the first visible cell does not swallow the style."""
    assert clip('\x1b[?25l\x1b[31mred', 0, 10, **kwargs) == '\x1b[31m\x1b[?25lred\x1b[0m'


@pytest.mark.parametrize('kwargs', [{}, {'overtyping': True}])
def test_clip_sgr_inside_hyperlink_tracked(kwargs):
    """Style changed by hyperlink inner text still terminates with a reset."""
    text = '\x1b]8;;http://x\x07a\x1b[31mb\x1b]8;;\x07c'
    assert clip(text, 0, 10, **kwargs) == text + '\x1b[0m'


@pytest.mark.parametrize('kwargs', [{}, {'overtyping': True}])
def test_clip_sgr_inside_hyperlink_untracked(kwargs):
    """With ``propagate_sgr=False``, hyperlink inner style is neither tracked nor reset."""
    text = '\x1b]8;;http://x\x07a\x1b[31mb\x1b]8;;\x07c'
    # sequences pass through verbatim, no synthesized prefix or trailing reset,
    assert clip(text, 0, 10, propagate_sgr=False, **kwargs) == text
    # and that holds when 'c', the only cell outside the hyperlink, is clipped away.
    assert (clip(text, 0, 2, propagate_sgr=False, **kwargs) ==
            '\x1b]8;;http://x\x07a\x1b[31mb\x1b]8;;\x07')


def test_clip_sequences_osc_hyperlink():
    assert repr(clip('\x1b]8;;https://example.com\x07link\x1b]8;;\x07', 0, 4)) == repr(
        '\x1b]8;;https://example.com\x07link\x1b]8;;\x07'
    )


# OSC 8 hyperlink clipping

OSC_START_BEL = '\x1b]8;;http://example.com\x07'
OSC_END_BEL = '\x1b]8;;\x07'
OSC_START_ST = '\x1b]8;;http://example.com\x1b\\'
OSC_END_ST = '\x1b]8;;\x1b\\'


CLIP_HYPERLINK_CASES = [
    # Full hyperlink visible -- preserved as-is
    (f'{OSC_START_BEL}link{OSC_END_BEL}', 0, 4,
     f'{OSC_START_BEL}link{OSC_END_BEL}'),
    # Clipping middle of hyperlink text -- rebuild around clipped inner text
    (f'{OSC_START_BEL}Click This link{OSC_END_BEL}', 6, 10,
     f'{OSC_START_BEL}This{OSC_END_BEL}'),
    # Clipping from start -- only first portion
    (f'{OSC_START_BEL}Click This{OSC_END_BEL}', 0, 5,
     f'{OSC_START_BEL}Click{OSC_END_BEL}'),
    # Clipping from end -- only last portion
    (f'{OSC_START_BEL}Click This{OSC_END_BEL}', 6, 10,
     f'{OSC_START_BEL}This{OSC_END_BEL}'),
    # Hyperlink entirely before clip window -- dropped
    (f'{OSC_START_BEL}link{OSC_END_BEL}world', 0, 4,
     f'{OSC_START_BEL}link{OSC_END_BEL}'),
    # Hyperlink entirely after clip window -- dropped
    (f'hello{OSC_START_BEL}link{OSC_END_BEL}', 0, 5, 'hello'),
    # Hyperlink clipped to nothing -- empty hyperlink dropped
    (f'{OSC_START_BEL}link{OSC_END_BEL}', 5, 10, ''),
    # Empty hyperlink (no inner text) -- dropped
    (f'before{OSC_START_BEL}{OSC_END_BEL}after', 0, 11, 'beforeafter'),
    # Hyperlink with CJK text clipped
    (f'{OSC_START_BEL}中文文字{OSC_END_BEL}', 0, 4,
     f'{OSC_START_BEL}中文{OSC_END_BEL}'),
    # Hyperlink with CJK text clipped at odd column
    (f'{OSC_START_BEL}中文文字{OSC_END_BEL}', 0, 3,
     f'{OSC_START_BEL}中 {OSC_END_BEL}'),
    # Hyperlink with ST terminator
    (f'{OSC_START_ST}Click This{OSC_END_ST}', 0, 5,
     f'{OSC_START_ST}Click{OSC_END_ST}'),
    # Multiple non-overlapping hyperlinks
    (f'{OSC_START_BEL}ab{OSC_END_BEL} {OSC_START_ST}cd{OSC_END_ST}', 0, 5,
     f'{OSC_START_BEL}ab{OSC_END_BEL} {OSC_START_ST}cd{OSC_END_ST}'),
    # Hyperlink with params preserved
    ('\x1b]8;id=myid;http://example.com\x07link\x1b]8;;\x07', 1, 3,
     '\x1b]8;id=myid;http://example.com\x07in\x1b]8;;\x07'),
    # Hyperlink text before clip window, hyperlink within
    (f'before{OSC_START_BEL}link{OSC_END_BEL}', 6, 10,
     f'{OSC_START_BEL}link{OSC_END_BEL}'),
    # SGR inside hyperlink is preserved
    (f'{OSC_START_BEL}\x1b[31mred link\x1b[0m{OSC_END_BEL}', 4, 8,
     f'{OSC_START_BEL}\x1b[31mlink\x1b[0m{OSC_END_BEL}'),
    # Hyperlink open without matching close -- preserved as regular sequence
    ('\x1b]8;;http://example.com\x07link', 0, 4, '\x1b]8;;http://example.com\x07link'),
    # Bare ESC between hyperlink markers
    ('\x1b]8;;url\x07ab\x1bxcd\x1b]8;;\x07', 0, 6,
     '\x1b]8;;url\x07ab\x1bxcd\x1b]8;;\x07'),
    # Per OSC 8 spec "A note on opening/closing hyperlinks": terminal
    # emulators treat hyperlinks as a state attribute, not nested anchors.
    # Opening a new hyperlink replaces the current one; a single close
    # terminates the hyperlink regardless of how many opens preceded it.
    #
    # Two opens, one close: URL "b" replaces "a", close terminates.
    ('\x1b]8;;a\x07AB\x1b]8;;b\x07CD\x1b]8;;\x07EF', 0, 6,
     '\x1b]8;;a\x07AB\x1b]8;;b\x07CD\x1b]8;;\x07EF'),
    # URL switch without closing: "b" replaces "a", no close in input.
    ('\x1b]8;;a\x07AB\x1b]8;;b\x07CD', 0, 4,
     '\x1b]8;;a\x07AB\x1b]8;;b\x07CD'),
    # Multiple opens, close, bare close: "b" replaces "a", first close
    # terminates, trailing close is harmless (closing when not open).
    ('\x1b]8;;a\x07ABCD \x1b]8;;b\x07XY\x1b]8;;\x07 EF\x1b]8;;\x07', 0, 10,
     '\x1b]8;;a\x07ABCD \x1b]8;;b\x07XY\x1b]8;;\x07 EF\x1b]8;;\x07'),
]


@pytest.mark.parametrize('text,start,end,expected', CLIP_HYPERLINK_CASES)
def test_clip_osc_hyperlink_text_clipping(text, start, end, expected):
    """OSC 8 hyperlink inner text is clipped and hyperlink rebuilt."""
    assert repr(clip(text, start, end)) == repr(expected)


# Control_codes variants with cursor movement into hyperlink
#
# Overwriting hyperlink cells causes corrupted "run on" hyperlinks in practical
# testing with kitty, presumably the hidden "end hyperlink" sequence is
# overwritten, in any case, we make no attempt to parse overwrite of
# hyperlinks, we consider it a "glitch sequence
_HLINK_OVERWRITE = f'{OSC_START_BEL}link{OSC_END_BEL}\x1b[2Dxy'
CLIP_HYPERLINK_CONTROL_CODES_CASES = [
    ('parse', 0, 4, f'{OSC_START_BEL}link{OSC_END_BEL}'),
    ('parse', 0, 3, f'{OSC_START_BEL}lin{OSC_END_BEL}'),
    ('parse', 0, 2, f'{OSC_START_BEL}li{OSC_END_BEL}'),
    ('parse', 0, 1, f'{OSC_START_BEL}l{OSC_END_BEL}'),
    # these next two are certainly "in error"
    ('parse', 1, 4, f'{OSC_START_BEL}ink{OSC_END_BEL}y'),
    ('parse', 1, 3, f'{OSC_START_BEL}in{OSC_END_BEL}x'),
    ('parse', 1, 2, f'{OSC_START_BEL}i{OSC_END_BEL}'),
    ('ignore', 0, 20, f'{_HLINK_OVERWRITE}'),
    # and these two, 'xy' are missing entirely, also "in error"
    ('parse', 0, 20, f'{OSC_START_BEL}link{OSC_END_BEL}'),
    ('strict', 0, 20, f'{OSC_START_BEL}link{OSC_END_BEL}'),
]


@pytest.mark.parametrize('control_codes,start,end,expected',
                         CLIP_HYPERLINK_CONTROL_CODES_CASES)
def test_clip_hyperlink_control_codes_overwrite(control_codes, start, end, expected):
    assert repr(clip(_HLINK_OVERWRITE, start, end, control_codes=control_codes)) == repr(expected)


# Painter-path hyperlink edge cases
CLIP_HYPERLINK_PAINTER_CASES = [
    # Empty hyperlink dropped
    (f'\x1b[2D{OSC_START_BEL}{OSC_END_BEL}xy', 'parse', 0, 4, 'xy'),
    # Hyperlink entirely after clip window -- skipped
    (f'\x1b[2Dab{OSC_START_BEL}cde{OSC_END_BEL}', 'parse', 0, 2, 'ab'),
    # Hyperlink entirely before clip window -- skipped
    (f'{OSC_START_BEL}ab{OSC_END_BEL}\x1b[2Dcdef', 'parse', 2, 4, 'ef'),
    # Hyperlink overlapping clip window -- clipped
    (f'\x1b[2D{OSC_START_BEL}abcdef{OSC_END_BEL}', 'parse', 0, 3,
     f'{OSC_START_BEL}abc{OSC_END_BEL}'),
    # Bare ESC inside hyperlink in painter path
    (f'\x1b[2D{OSC_START_BEL}a\x1bb{OSC_END_BEL}', 'parse', 0, 4,
     f'{OSC_START_BEL}a\x1bb{OSC_END_BEL}'),
    # strict mode: non-hyperlink cells don't overlap hyperlink_cells
    (f'{OSC_START_BEL}link{OSC_END_BEL}\x1b[5Chi', 'strict', 0, 11,
     f'{OSC_START_BEL}link{OSC_END_BEL}     hi'),
]


@pytest.mark.parametrize('text,control_codes,start,end,expected',
                         CLIP_HYPERLINK_PAINTER_CASES)
def test_clip_hyperlink_painter_cases(text, control_codes, start, end, expected):
    assert repr(clip(text, start, end, control_codes=control_codes)) == repr(expected)


def test_clip_sequences_cjk_with_sequences():
    assert clip('\x1b[31m中文\x1b[0m', 0, 3) == '\x1b[31m中 \x1b[0m'


def test_clip_sequences_partial_wide_at_start():
    assert clip('\x1b[31m中文\x1b[0m', 1, 4) == '\x1b[31m 文\x1b[0m'


def test_clip_sequences_between_chars():
    assert clip('a\x1b[31mb\x1b[0mc', 1, 2) == '\x1b[31mb\x1b[0m'


def test_clip_sequences_fs_escape():
    assert clip('a\x1bb', 0, 2) == 'a\x1bb'


CLIP_EMOJI_CASES = [
    ('\U0001F600', 2),
    ('\U0001F468\u200D\U0001F469\u200D\U0001F467', 2),
    ('\u2764\uFE0F', 2),
    ('\U0001F1FA\U0001F1F8', 2),
]


@pytest.mark.parametrize('emoji,full_width', CLIP_EMOJI_CASES)
def test_clip_emoji(emoji, full_width):
    assert clip(emoji, 0, full_width) == emoji
    assert clip(emoji, 0, 1) == ' '
    assert width(emoji) == full_width


def test_clip_emoji_with_sequences():
    assert clip('\x1b[1m\U0001F600\x1b[0m', 0, 2) == '\x1b[1m\U0001F600\x1b[0m'


def test_clip_combining_accent():
    assert clip('cafe\u0301', 0, 4) == 'cafe\u0301'
    assert clip('cafe\u0301', 0, 3) == 'caf'


def test_clip_combining_multiple():
    assert clip('e\u0301\u0327', 0, 1) == 'e\u0301\u0327'


def test_clip_zero_width_position_bounds():
    # Standalone combining mark before visible region should NOT be included
    assert clip('\u0301hello', 1, 4) == 'ell'
    # Standalone combining mark after visible region should NOT be included
    assert clip('hello\u0301', 0, 3) == 'hel'
    # Combining mark within visible region should be included (attached to base)
    assert clip('he\u0301llo', 0, 4) == 'he\u0301ll'


def test_clip_prepend_grapheme():
    # PREPEND characters (Arabic Number Sign) cluster with following char, width 2
    # Full cluster fits
    assert clip('\u0600abc', 0, 2) == '\u0600a'
    # Cluster split at start boundary - replaced with fillchar
    assert clip('\u0600abc', 0, 1) == ' '
    # Cluster split at end boundary - partial overlap gets fillchar
    assert clip('\u0600abc', 1, 3) == ' b'
    # Clipping after the prepend cluster
    assert clip('\u0600abc', 2, 4) == 'bc'


def test_clip_ambiguous_width_1():
    assert clip('\u00b1test', 0, 3, ambiguous_width=1) == '\u00b1te'


def test_clip_ambiguous_width_2():
    assert clip('\u00b1test', 0, 3, ambiguous_width=2) == '\u00b1t'


CLIP_TAB_CASES = [
    ('a\tb', 0, 10, 8, 'a       b'),
    ('a\tb', 0, 4, 8, 'a   '),
    ('a\tb', 0, 10, 4, 'a   b'),
    ('a\tb', 4, 10, 8, '    b'),
    ('a\tb\tc', 0, 20, 4, 'a   b   c'),
    ('中\tb', 0, 10, 4, '中  b'),
    ('a\tb', 0, 5, 0, 'a\tb'),
]


@pytest.mark.parametrize('text,start,end,tabsize,expected', CLIP_TAB_CASES)
def test_clip_tab_expansion(text, start, end, tabsize, expected):
    assert clip(text, start, end, tabsize=tabsize) == expected


def test_clip_tab_with_sequences():
    assert clip('\x1b[31mab\tc\x1b[0m', 0, 12, tabsize=4) == '\x1b[31mab  c\x1b[0m'


CLIP_CONTROL_CHAR_CASES = [
    ('abc\bde', 0, 5, 'abde'),
    ('ab\acd', 0, 4, 'ab\x07cd'),
    ('ab\x00cd', 0, 4, 'ab\x00cd'),
    ('abc\rde', 0, 5, 'dec'),
    ('\a\b\rHello', 0, 5, '\x07Hello'),
    ('ab\x01\x02cd', 0, 4, 'ab\x01\x02cd'),
    ('ab\x1b\x00cd', 0, 4, 'ab\x1b\x00cd'),
]


@pytest.mark.parametrize('text,start,end,expected', CLIP_CONTROL_CHAR_CASES)
def test_clip_control_chars_zero_width(text, start, end, expected):
    assert clip(text, start, end) == expected


def test_clip_tab_first_visible_with_sgr():
    """Tab as first visible character with SGR propagation."""
    assert clip('\x1b[31m\tb', 0, 4, tabsize=8) == '\x1b[31m    \x1b[0m'


def test_clip_overtyping_override_by_control_codes_ignore():
    """When overtyping=True and control_codes='ignore', overtyping is overridden to False."""
    # elif entered: overtyping=True + control_codes='ignore': overtyping becomes False
    assert clip('hello world', 0, 5, overtyping=True, control_codes='ignore') == 'hello'
    # Verify that overtyping is actually disabled: cursor movement chars are
    # treated as zero-width, so the result is the same as without overtyping.
    assert clip('ab\x08cd', 0, 4, overtyping=True, control_codes='ignore') == 'ab\x08cd'


def test_clip_overtyping_without_ignore():
    """When overtyping=True and control_codes='parse', elif is not entered."""
    # elif skipped: overtyping=True + control_codes='parse': overtyping stays True
    # The painter path is used, cursor movement sequences affect output.
    assert clip('ab\x1b[2Dcd', 0, 4, overtyping=True, control_codes='parse') == 'cd'


# Indeterminate-effect sequences that raise ValueError in strict mode
# (matching width() behavior).  These are not cursor-movement sequences,
# so they exercise the simple (non-overtyping) path.

INDETERMINATE_SEQUENCES = [
    ('\x1b[K', 'erase_in_line'),
    ('\x1b[2K', 'erase_in_line_params'),
    ('\x1b[J', 'erase_in_display'),
    ('\x1b[2J', 'erase_in_display_params'),
    ('\x1b[H', 'cursor_home'),
    ('\x1b[1;1H', 'cursor_address'),
    ('\x1b[A', 'cursor_up'),
    ('\x1b[2A', 'cursor_up_params'),
    ('\x1b[B', 'cursor_down'),
    ('\x1b[5B', 'cursor_down_params'),
    ('\x1b[P', 'delete_character'),
    ('\x1b[1P', 'parm_dch'),
    ('\x1b[M', 'delete_line'),
    ('\x1b[1M', 'parm_delete_line'),
    ('\x1b[L', 'insert_line'),
    ('\x1b[1L', 'parm_insert_line'),
    ('\x1b[@', 'insert_character'),
    ('\x1b[1X', 'erase_chars'),
    ('\x1b[S', 'scroll_up'),
    ('\x1b[T', 'scroll_down'),
    ('\x1b[?1049h', 'enter_fullscreen'),
    ('\x1b[?1049l', 'exit_fullscreen'),
    ('\x1bD', 'scroll_forward'),
    ('\x1bM', 'scroll_reverse'),
    ('\x1b8', 'restore_cursor'),
    ('\x1bc', 'full_reset'),
]


@pytest.mark.parametrize('seq,cap_name', INDETERMINATE_SEQUENCES)
def test_clip_strict_indeterminate_raises(seq, cap_name):
    """Clip() strict mode raises ValueError on indeterminate-effect sequences."""
    with pytest.raises(ValueError, match='Indeterminate cursor sequence'):
        clip(f'hello{seq}world', 0, 10, control_codes='strict')


@pytest.mark.parametrize('seq,cap_name', INDETERMINATE_SEQUENCES)
def test_clip_parse_indeterminate_preserved(seq, cap_name):
    """Clip() parse mode preserves indeterminate sequences as zero-width."""
    result = clip(f'hello{seq}world', 0, 10, control_codes='parse')
    # The sequence is preserved, visible text is hello + world = 10 chars
    assert 'hello' in result
    assert 'world' in result
    assert seq in result


@pytest.mark.parametrize('text,expected', [
    ('\x1b]66;bad\x07', ''),
    ('\x1b]66;w=5;hello\x07', 'hello'),
    ('before\x1b]66;bad\x07after', 'beforeafter'),
    ('before\x1b]66;w=5;hello\x07after', 'beforehelloafter'),
])
def test_strip_sequences_osc66_stripped(text, expected):
    """strip_sequences() preserves OSC 66 display text."""
    assert strip_sequences(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('\x1b\x1b]66;bad\x07[31m', '\x1b[31m'),
    ('\x1b\x1b]66;w=5;hello\x07[31m', '\x1bhello[31m'),
])
def test_strip_sequences_osc66_no_splice(text, expected):
    """strip_sequences() does not join the text on either side of an OSC 66 sequence."""
    assert strip_sequences(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('a\x1b[', 'a'),
    ('\x1b[\x1b[31mc', 'c'),
    ('a\x1b[\x1b[31mb', 'ab'),
])
def test_strip_sequences_unterminated_csi(text, expected):
    """strip_sequences() strips bare ESC[ (unterminated CSI)."""
    assert strip_sequences(text) == expected


@pytest.mark.parametrize('text,start,end,expected', [
    ('\x1b]66;bad\x07text', 0, 4, '\x1b]66;;\x07text'),
    ('a\x1b]66;bad\x07b', 0, 5, 'a\x1b]66;;\x07b'),
])
def test_clip_canonicalizes_osc66_without_display_text(text, start, end, expected):
    """Clip() canonicalizes OSC 66 with no display text (invalid meta dropped)."""
    assert clip(text, start, end) == expected


@pytest.mark.parametrize('text,start,end,expected', [
    ('\x1b]66;s=1:w=1;\x1b\\abc', 0, 5, '\x1b]66;w=1;\x1b\\abc'),
    ('\x1b]66;s=1:w=1;XY\x1b\\', 0, 10, '\x1b]66;w=1;XY\x1b\\'),
    ('\x1b]66;s=1:w=1;\x1b\\X', 1, 2, 'X'),
])
def test_clip_osc66_zero_text_unit(text, start, end, expected):
    """Clip() treats zero-text OSC 66 as a width unit with default params omitted."""
    assert clip(text, start, end) == expected


def test_clip_osc8_empty_unit_skipped():
    """Clip() drops empty OSC 8 units formed by dangling close sequences."""
    assert clip('\x1b]8;;\x1b\\\x1b]8;;\x07X', 0, 5) == 'X'


def test_clip_sgr_captured_only_at_visible_content():
    """Clip() captures SGR only at visible content emission, not passthrough."""
    assert clip('\x1b[31m\x1b]66;w=5;hello\x07', 10, 20) == ''


@pytest.mark.parametrize('text,start,expected', [
    ('', 0, ''),
    ('hello world', 0, 'hello world'),
    ('hello world', 6, 'world'),
    ('hello', 5, ''),
    ('hello', 99, ''),
    ('hello', -5, 'hello'),
    ('中文字', 1, ' 文字'),
    ('中文字', 2, '文字'),
    ('中文字', 6, ''),
    ('cafe\u0301', 3, 'e\u0301'),
    ('a\tb', 4, '    b'),
    ('\x1b[1;34mHello world\x1b[0m', 6, '\x1b[1;34mworld\x1b[0m'),
    ('\x1b[31mred\x1b[32mgreen\x1b[0m', 4, '\x1b[32mreen\x1b[0m'),
    ('\x1b]8;;http://example.com\x07Click This link\x1b]8;;\x07', 6,
     '\x1b]8;;http://example.com\x07This link\x1b]8;;\x07'),
    ('\x1b]66;w=4:s=4;Look\x07', 1, '   \x1b]66;s=4:w=3;ook\x07'),
    ('hello\rworld', 2, 'rld'),
    ('hello\x08\x08world', 2, 'lworld'),
    ('abc\x1b[5Gde', 2, 'c de'),
])
def test_clip_to_end_of_line(text, start, expected):
    """Clip() end=-1 (default) clips from start through the final column."""
    assert repr(clip(text, start)) == repr(expected)
    assert repr(clip(text, start, -1)) == repr(expected)
    assert repr(clip(text, start, width(text))) == repr(expected)


def test_clip_default_arguments_whole_line():
    """Clip() without start or end returns the whole line, matching propagate_sgr()."""
    assert clip('hello world') == 'hello world'
    text = '\x1b[1mbold\x1b[m normal \x1b[31mred\x1b[0m'
    assert clip(text) == propagate_sgr([text])[0]


@pytest.mark.parametrize('kwargs', [
    {}, {'control_codes': 'parse'}, {'control_codes': 'ignore'}, {'control_codes': 'strict'},
    {'overtyping': True}, {'overtyping': False}, {'tabsize': 0}, {'ambiguous_width': 2},
    {'propagate_sgr': False}, {'fillchar': '.'},
])
def test_clip_to_end_of_line_matches_unbounded_end(kwargs):
    """Clip() end=-1 matches any end beyond the final column, for all argument modes."""
    text = '\x1b[1m§ hello \x1b]8;;http://x\x07link\x1b]8;;\x07 中文\x1b[0m'
    for start in (0, 1, 5, 12, 40):
        assert repr(clip(text, start, **kwargs)) == repr(clip(text, start, 10000, **kwargs))


@pytest.mark.parametrize('text', [
    'hello world',
    '\x1b[31mred text\x1b[0m',
    'a\tbcd',
    '\x1b]8;;http://example.com\x07Click This link\x1b]8;;\x07',
])
def test_clip_to_end_of_line_width_invariant(text):
    """Clip() end=-1 removes exactly *start* columns of display width."""
    total = width(text)
    for start in range(total + 2):
        assert width(clip(text, start)) == max(0, total - start)


@pytest.mark.parametrize('text,end,kwargs', [
    ('hello world', -2, {}),
    ('hello world', -(2 ** 32), {}),
    ('中文字', -2, {}),
    ('\x1b[31mred\x1b[0m', -5, {'control_codes': 'ignore'}),
])
def test_clip_negative_end_raises(text, end, kwargs):
    """Clip() raises ValueError for a negative end other than -1."""
    with pytest.raises(ValueError, match='end must be -1'):
        clip(text, 0, end, **kwargs)


pytestmark_parity = pytest.mark.skipif(
    _clip_module._c_clip is None,
    reason="C extension not built; there is nothing to compare against")

HERE = os.path.dirname(__file__)

PARITY_WINDOWS = ((0, 0), (0, 1), (0, 2), (1, 2), (3, 4), (2, 9), (0, 40),
                  (0, -1), (5, -1), (40, 60))

PARITY_OPTIONS = (
    {},
    {'propagate_sgr': False},
    {'ambiguous_width': 2},
    {'fillchar': '?'},
    {'tabsize': 4},
    {'control_codes': 'ignore'},
    {'control_codes': 'strict'},
    {'overtyping': False},
)


def python_clip(*args, **kwargs):
    """Call clip() with the C offload disabled, for use as the reference."""
    saved = _clip_module._c_clip
    _clip_module._c_clip = None
    try:
        return _clip_module.clip(*args, **kwargs)
    finally:
        _clip_module._c_clip = saved


def _read_parity_lines(filename):
    """Return non-comment, non-empty lines of *filename*, or [] when absent."""
    path = os.path.join(HERE, filename)
    if not os.path.exists(path):
        return []
    result = []
    with open(path, encoding='utf-8') as fp:
        for line in fp:
            line = line.rstrip('\n')
            if not line or line.lstrip().startswith(('#', '@')):
                continue
            result.append(line)
    return result


def _read_parity_sequences(filename):
    """Parse a unicode.org '0041 FE0F ; comment' file into strings."""
    sequences = []
    for line in _read_parity_lines(filename):
        try:
            sequences.append(''.join(
                chr(int(cp, 16)) for cp in line.split(';', 1)[0].strip().split()))
        except ValueError:
            continue
    return sequences


# udhr_combined.txt holds 113,957 lines, far more than these tests can measure
# against both implementations on every run, so they take an evenly spaced
# sample.  Printable ASCII is excluded from it because clip() answers that from
# the slicing fast path without ever reaching the offload.
#
# The two sizes are tuned to a wall-clock budget rather than to coverage: under
# half a second per test by default, and a few seconds per test when running
# fully.  Full runs happen automatically under CI, and locally with
# FULL_TESTING=1.
UDHR_SAMPLE_DEFAULT = 40
UDHR_SAMPLE_FULL = 3000


def _full_testing():
    """Whether to use the wider corpora: automatic under CI, or FULL_TESTING=1."""
    return bool(os.environ.get('FULL_TESTING', '') or os.environ.get('CI', ''))


def _read_udhr_lines():
    """Return an evenly spaced sample of the non-ASCII lines of udhr_combined.txt."""
    lines = [line for line in _read_parity_lines('udhr_combined.txt')
             if not (line.isascii() and line.isprintable())]
    if not lines:
        return []
    count = UDHR_SAMPLE_FULL if _full_testing() else UDHR_SAMPLE_DEFAULT
    return lines[::max(1, len(lines) // count)][:count]


PARITY_CORPUS = (
    _read_udhr_lines() +
    _read_parity_sequences('emoji-zwj-sequences.txt') +
    _read_parity_sequences('emoji-variation-sequences.txt') +
    [
        '', 'hello world', '中文字', 'コンニチハ、セカイ！', 'a\tb\tc',
        '\x1b[31mred\x1b[0m plain', '\x1b[1mbold\x1b[m normal',
        '\x1b[38;2;10;20;30mtruecolor\x1b[0m',
        '\x1b[38:2::10:20:30mcolon form\x1b[0m',
        '\x1b[31m\tb', 'é́combining', '\U0001f469\U0001f3fb‍\U0001f4bb x',
        '\x1b]8;;http://example.com\x07link text\x1b]8;;\x07',
        '\x1b]66;s=2;scaled\x07 after',
        'over\rtype', 'back\x08space', 'csi\x1b[3Cforward', 'csi\x1b[2Dback',
        'hpa\x1b[10Gabsolute', '\x1b[2Jclear screen', 'trailing esc \x1b',
        'malformed \x1b[ unterminated', '\x1b(\ncharset',
    ]
)


def assert_clip_parity(text, start, end, **kwargs):
    """Clip() must equal the pure-Python path for this input."""
    try:
        expected = python_clip(text, start, end, **kwargs)
    except ValueError:
        with pytest.raises(ValueError):
            clip(text, start, end, **kwargs)
        return
    actual = clip(text, start, end, **kwargs)
    assert actual == expected, (
        f"clip({text!r}, {start}, {end}, **{kwargs})\n"
        f"  offloaded: {actual!r}\n"
        f"  python   : {expected!r}")


@pytestmark_parity
@pytest.mark.parametrize('options', PARITY_OPTIONS)
def test_clip_parity_corpus(options):
    """Every corpus input clips identically through C and through Python."""
    for text in PARITY_CORPUS:
        for start, end in PARITY_WINDOWS:
            assert_clip_parity(text, start, end, **options)


@pytestmark_parity
def test_clip_parity_lone_surrogate():
    """A lone surrogate has no UTF-8 form; the C path must decline it."""
    assert clip('a\ud800b', 0, 3) == python_clip('a\ud800b', 0, 3)


@pytestmark_parity
def test_clip_offload_is_actually_used():
    """
    The offload must fire for ordinary non-ASCII text.

    Without this, an over-tightened gate would silently disable the C path while every parity
    assertion above still trivially held.  Printable ASCII is excluded because clip() answers it
    from the slicing fast path before the offload is reached, and never calls C at all.
    """
    calls = []
    saved = _clip_module._c_clip

    def _counting_clip(*args, **kwargs):
        calls.append(args[0])
        return saved(*args, **kwargs)

    lines = _read_udhr_lines() or ['中文字']

    _clip_module._c_clip = _counting_clip
    try:
        for line in lines:
            _clip_module.clip(line, 0, 20)
    finally:
        _clip_module._c_clip = saved

    assert len(calls) / len(lines) >= 0.95, (
        f"offload fired for only {len(calls)}/{len(lines)} non-ASCII lines")


@pytestmark_parity
def test_clip_ascii_does_not_reach_offload():
    """Printable ASCII is answered by the fast path, without calling C."""
    calls = []
    saved = _clip_module._c_clip

    def _counting_clip(*args, **kwargs):
        calls.append(args[0])
        return saved(*args, **kwargs)

    _clip_module._c_clip = _counting_clip
    try:
        for text in ('hello world', 'ab-cd', 'The quick brown fox ' * 10):
            _clip_module.clip(text, 0, 20)
    finally:
        _clip_module._c_clip = saved

    assert not calls


# Includes every shape the offload accepts and every shape it must reject, so
# both branches are exercised.
_FUZZ_ALPHABET = (
    list('abcdefghij klmnop') +
    list('中文字日本語') +
    ['\U0001f600', '\U0001f469\U0001f3fb‍\U0001f4bb', 'é', '́'] +
    ['\t', '\x1b[31m', '\x1b[0m', '\x1b[1m', '\x1b[38;5;120m'] +
    ['\x1b]8;;http://x\x07', '\x1b]8;;\x07', '\x1b]66;s=2;ab\x07'] +
    ['\r', '\x08', '\x1b[3C', '\x1b[2D', '\x1b[5G', '\x1b[2J'] +
    ['\x1b', '\x1b[', '\x1b(\n', '\x1b]8;']
)

# Every atom and every ordered pair of atoms is always tested: divergences
# between the two implementations are adjacency bugs, and the one this suite was
# written for -- a tab followed by an escape past the clip window -- is a pair.
# Triples are enumerated in order and sampled one in N, N being coprime with the
# alphabet size so that no atom is systematically skipped in any position.
# Longer inputs are covered by the UDHR and emoji corpus above.
FUZZ_TRIPLE_STRIDE_DEFAULT = 32
FUZZ_TRIPLE_STRIDE_FULL = 2

# Narrow windows matter more than long inputs here: a combination only reaches
# the "past the clip window" branches when its columns exceed *end*, and three
# atoms rarely exceed four columns.  Without (0, 1) and (0, 2), a tab followed
# by an escape past the window -- the divergence this suite was written for --
# goes undetected.
FUZZ_WINDOWS = ((0, 1), (0, 2), (0, 4), (2, 6), (0, -1))


def _fuzz_corpus():
    """Atoms, every ordered pair, and a strided sample of ordered triples."""
    stride = FUZZ_TRIPLE_STRIDE_FULL if _full_testing() else FUZZ_TRIPLE_STRIDE_DEFAULT
    corpus = list(_FUZZ_ALPHABET)
    corpus += [a + b for a in _FUZZ_ALPHABET for b in _FUZZ_ALPHABET]
    corpus += [''.join(t) for i, t in enumerate(product(_FUZZ_ALPHABET, repeat=3))
               if i % stride == 0]
    return corpus


@pytestmark_parity
def test_clip_parity_fuzz():
    """
    Differential test over combinations of accepted and rejected shapes.

    The corpus is enumerated, not sampled randomly, so it is the same on every
    run and every machine, with no seed to record or reproduce.  A denser sample
    runs under CI, or locally with ``FULL_TESTING=1``.
    """
    for text in _fuzz_corpus():
        for start, end in FUZZ_WINDOWS:
            assert_clip_parity(text, start, end)


UNSUPPORTED_SEQUENCES = (
    '\x1b[5C',
    '\x1b[7D',
    '\x1b[2G',
    '\b\b\b',
    '\r\r\r',
    '\x1b]8;;http://e\x1b\\LNK\x1b]8;;\x1b\\',
    '\x1b]66;w=2:A\x1b\\',
    '\x1b(\n',
    '',
)
UNSUPPORTED_PREFIXES = ('', '\x1b[31m', '中文', 'ab\t')
UNSUPPORTED_SUFFIXES = ('', 'ZZZ', '\x1b[0m', '中')
UNSUPPORTED_PADDING = (0, 1, 5, 20, 200)


@pytestmark_parity
@pytest.mark.parametrize('sequence', UNSUPPORTED_SEQUENCES)
def test_clip_parity_unsupported_past_window(sequence):
    """Sequences libwcwidth rejects stay rejected far past the clip window."""
    for prefix, suffix in product(UNSUPPORTED_PREFIXES, UNSUPPORTED_SUFFIXES):
        for pad in UNSUPPORTED_PADDING:
            text = prefix + 'abcdef' + 'x' * pad + sequence + suffix
            for start, end in FUZZ_WINDOWS:
                assert_clip_parity(text, start, end)
                assert_clip_parity(text, start, end, propagate_sgr=False)


@pytestmark_parity
@pytest.mark.parametrize('text', [
    'abcdef\x1b[5Cgh',
    'abcdef\x1b[3Dgh',
    'abcdef\x1b[2Ggh',
    'abcdef\bgh',
    'abcdef\rgh',
    'abcdefghijklmnop\x1b[3D',
    'abcdefghijklmnop\b',
    'ab\x1b]8;;http://e\x1b\\LNK\x1b]8;;\x1b\\',
    'ab\x1b]66;w=2:A\x1b\\',
])
def test_c_clip_returns_none_for_unsupported(text):
    assert _clip_module._c_clip(
        text, 0, 3, fillchar=' ', tabsize=8, ambiguous_width=1,
        propagate_sgr=True, control_codes='parse', term_program=False) is None


@pytestmark_parity
@pytest.mark.parametrize('text', ['abcdef', 'ab\x1b[31mcd\x1b[0m', 'ab\x1b]0;t\x07cd', '中文字'])
def test_c_clip_accepts_supported(text):
    assert _clip_module._c_clip(
        text, 0, 3, fillchar=' ', tabsize=8, ambiguous_width=1,
        propagate_sgr=True, control_codes='parse', term_program=False) is not None


@pytestmark_parity
def test_c_clip_declines_every_movement_python_resolves():
    """Libwcwidth declines wherever Python's painter would resolve movement."""
    # Its scan accepts any CSI parameter byte before a C/D/G final where Python's pattern
    # accepts only digits, so it declines a superset.  The reverse would silently offload
    # text whose movement Python resolves.
    accepted = []
    for text in _fuzz_corpus():
        if _HORIZONTAL_CURSOR_MOVEMENT.search(text) is None:
            continue
        if _clip_module._c_clip(
                text, 0, 3, fillchar=' ', tabsize=8, ambiguous_width=1,
                propagate_sgr=True, control_codes='parse', term_program=False) is not None:
            accepted.append(text)
    assert not accepted[:10]


# PARITY_OPTIONS sets overtyping= itself in one case, which these tests supply.
PATH_PARITY_OPTIONS = tuple(o for o in PARITY_OPTIONS if 'overtyping' not in o)


def _movement_free(corpus):
    """Drop inputs whose answer is meant to differ between the two paths."""
    return [t for t in corpus if not
            ('\r' in t or '\x08' in t or _HORIZONTAL_CURSOR_MOVEMENT.search(t))]


def assert_clip_path_parity(text, start, end, **kwargs):
    """Both Python paths must clip *text* identically."""
    try:
        painter = python_clip(text, start, end, overtyping=True, **kwargs)
    except ValueError:
        with pytest.raises(ValueError):
            python_clip(text, start, end, overtyping=False, **kwargs)
        return
    simple = python_clip(text, start, end, overtyping=False, **kwargs)
    assert simple == painter, (
        f"clip({text!r}, {start}, {end}, **{kwargs})\n"
        f"  overtyping=False: {simple!r}\n  overtyping=True : {painter!r}")


@pytest.mark.parametrize('options', PATH_PARITY_OPTIONS)
def test_clip_paths_agree_corpus(options):
    """Every movement-free corpus input clips identically through both paths."""
    for text in _movement_free(PARITY_CORPUS):
        for start, end in PARITY_WINDOWS:
            assert_clip_path_parity(text, start, end, **options)


def test_clip_paths_agree_fuzz():
    """Differential test of the two Python paths over the fuzz corpus."""
    for text in _movement_free(_fuzz_corpus()):
        for start, end in FUZZ_WINDOWS:
            assert_clip_path_parity(text, start, end)


def test_clip_fast_path_is_dispatched():
    """Movement-free text must reach _clip_simple(), not the painter."""
    simple, offload = _clip_module._clip_simple, _clip_module._c_clip
    calls = []

    def _counting(**kwargs):
        calls.append(kwargs['text'])
        return simple(**kwargs)

    movement_free = ['\u4e2d\u6587\u5b57', '\x1b[31mred\x1b[0m plain', 'a\tb\tc\xe9']
    _clip_module._clip_simple, _clip_module._c_clip = _counting, None
    try:
        for text in movement_free + ['over\rtype', 'back\x08space', 'csi\x1b[2Dback']:
            _clip_module.clip(text, 0, 20)
    finally:
        _clip_module._clip_simple, _clip_module._c_clip = simple, offload

    assert calls == movement_free


def test_clip_import_error_fallback():
    """A missing extension at import time leaves clip() on the Python path."""
    sys.modules['wcwidth._wcwidth_c'] = None
    try:
        importlib.reload(_clip_module)
        assert _clip_module._c_clip is None
        assert _clip_module.clip('\u4e2d\u6587\u5b57', 0, 3) == '\u4e2d '
    finally:
        del sys.modules['wcwidth._wcwidth_c']
        importlib.reload(_clip_module)
