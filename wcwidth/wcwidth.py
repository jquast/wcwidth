"""
This is a python implementation of wcwidth() and wcswidth().

https://github.com/jquast/wcwidth

Derived from Markus Kuhn's C code,

This is an implementation of wcwidth() and wcswidth() (defined in
IEEE Std 1002.1-2001) for Unicode.

http://www.opengroup.org/onlinepubs/007904975/functions/wcwidth.html
http://www.opengroup.org/onlinepubs/007904975/functions/wcswidth.html

In fixed-width output devices, Latin characters all occupy a single
"cell" position of equal width, whereas ideographic CJK characters
occupy two such cells. Interoperability between terminal-line
applications and (teletype-style) character terminals using the
UTF-8 encoding requires agreement on which character should advance
the cursor by how many cell positions. No established formal
standards exist at present on which Unicode character shall occupy
how many cell positions on character terminals. These routines are
a first attempt of defining such behavior based on simple rules
applied to data provided by the Unicode Consortium.

For some graphical characters, the Unicode standard explicitly
defines a character-cell width via the definition of the East Asian
FullWidth (F), Wide (W), Half-width (H), and Narrow (Na) classes.
In all these cases, there is no ambiguity about which width a
terminal shall use. For characters in the East Asian Ambiguous (A)
class, the width choice depends purely on a preference of backward
compatibility with either historic CJK or Western practice.
Choosing single-width for these characters is easy to justify as
the appropriate long-term solution, as the CJK practice of
displaying these characters as double-width comes from historic
implementation simplicity (8-bit encoded characters were displayed
single-width and 16-bit ones double-width, even for Greek,
Cyrillic, etc.) and not any typographic considerations.

Much less clear is the choice of width for the Not East Asian
(Neutral) class. Existing practice does not dictate a width for any
of these characters. It would nevertheless make sense
typographically to allocate two character cells to characters such
as for instance EM SPACE or VOLUME INTEGRAL, which cannot be
represented adequately with a single-width glyph. The following
routines at present merely assign a single-cell width to all
neutral characters, in the interest of simplicity. This is not
entirely satisfactory and should be reconsidered before
establishing a formal standard in this area. At the moment, the
decision which Not East Asian (Neutral) characters should be
represented by double-width glyphs cannot yet be answered by
applying a simple rule from the Unicode database content. Setting
up a proper standard for the behavior of UTF-8 character terminals
will require a careful analysis not only of each Unicode character,
but also of each presentation form, something the author of these
routines has avoided to do so far.

http://www.unicode.org/unicode/reports/tr11/

Latest version: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
"""

from __future__ import annotations

# std imports
from functools import lru_cache

from typing import Literal

# local
# pylint: disable=unused-import
# Some CONSTANTS imported are now unused, like _wcversion_value(), they were first defined in this
# file location, and remain there for API compatibility purposes _wcversion_value and
# _wcmatch_version are no longer used internally since version 0.5.0 (only the latest Unicode
# version is shipped), and many global constants, now unused here, were moved to _constants.py in
# version 0.6.1.
#
# They are retained for API compatibility with external tools like ucs-detect
# that may use these private functions.
#
from ._width import width
from ._wcwidth import wcwidth
from .bisearch import bisearch as _bisearch
from .grapheme import iter_graphemes
from ._wcswidth import wcswidth
from .sgr_state import (_SGR_PATTERN,
                        _SGR_STATE_DEFAULT,
                        _sgr_state_update,
                        _sgr_state_is_active,
                        _sgr_state_to_sequence)
from ._constants import _LATEST_VERSION
from .table_vs16 import VS16_NARROW_TO_WIDE
from .table_wide import WIDE_EASTASIAN
from .table_zero import ZERO_WIDTH
from .control_codes import ILLEGAL_CTRL, VERTICAL_CTRL, HORIZONTAL_CTRL, ZERO_WIDTH_CTRL
from .table_grapheme import ISC_CONSONANT
from .table_ambiguous import AMBIGUOUS_EASTASIAN
from .escape_sequences import (ZERO_WIDTH_PATTERN,
                               CURSOR_LEFT_SEQUENCE,
                               CURSOR_RIGHT_SEQUENCE,
                               INDETERMINATE_EFFECT_SEQUENCE,
                               iter_sequences,
                               strip_sequences)
from .unicode_versions import list_versions

# Type aliases for output_tokens used by clip().
# ('vis', text, width_in_cols, start_col) or ('seq', seq_text)
VisToken = tuple[Literal['vis'], str, int, int]
SeqToken = tuple[Literal['seq'], str]
Token = VisToken | SeqToken

# Unlike wcwidth.__all__, wcwidth.wcwidth.__all__ is NOT for the purpose of defining a public API,
# or what we prefer to be imported with statement, "from wcwidth.wcwidth import *".  Explicitly
# re-export imports here for no other reason than to satisfy the type checkers (mypy). Yak shavings.
__all__ = (
    'ZERO_WIDTH',
    'WIDE_EASTASIAN',
    'AMBIGUOUS_EASTASIAN',
    'VS16_NARROW_TO_WIDE',
    'list_versions',
    'wcwidth',
    'wcswidth',
    'width',
    'iter_sequences',
    'ljust',
    'rjust',
    'center',
    'clip',
    'strip_sequences',
    '_wcmatch_version',
    '_wcversion_value',
)


@lru_cache(maxsize=128)
def _wcversion_value(ver_string: str) -> tuple[int, ...]:  # pragma: no cover
    """
    Integer-mapped value of given dotted version string.

    .. deprecated:: 0.3.0

        This function is no longer used internally by wcwidth but is retained
        for API compatibility with external tools.

    :param ver_string: Unicode version string, of form ``n.n.n``.
    :returns: tuple of digit tuples, ``tuple(int, [...])``.
    """
    retval = tuple(map(int, (ver_string.split('.'))))
    return retval


@lru_cache(maxsize=8)
def _wcmatch_version(given_version: str) -> str:  # pylint: disable=unused-argument
    """
    Return the supported Unicode version level.

    .. deprecated:: 0.3.0
        This function now always returns the latest version.

        This function is no longer used internally by wcwidth but is retained
        for API compatibility with external tools.

    :param given_version: Ignored. Any value is accepted for compatibility.
    :returns: The latest unicode version string.
    """
    return _LATEST_VERSION


def ljust(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    ambiguous_width: int = 1,
) -> str:
    r"""
    Return text left-justified in a string of given display width.

    :param text: String to justify, may contain terminal sequences.
    :param dest_width: Total display width of result in terminal cells.
    :param fillchar: Single character for padding (default space). Must have
        display width of 1 (not wide, not zero-width, not combining). Unicode
        characters like ``'·'`` are acceptable. The width is not validated.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: Text padded on the right to reach ``dest_width``.

    .. versionadded:: 0.3.0

    Example::

        >>> wcwidth.ljust('hi', 5)
        'hi   '
        >>> wcwidth.ljust('\x1b[31mhi\x1b[0m', 5)
        '\x1b[31mhi\x1b[0m   '
        >>> wcwidth.ljust('\U0001F468\u200D\U0001F469\u200D\U0001F467', 6)
        '👨‍👩‍👧    '
    """
    if text.isascii() and text.isprintable():
        text_width = len(text)
    else:
        text_width = width(text, control_codes=control_codes, ambiguous_width=ambiguous_width)
    padding_cells = max(0, dest_width - text_width)
    return text + fillchar * padding_cells


def rjust(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    ambiguous_width: int = 1,
) -> str:
    r"""
    Return text right-justified in a string of given display width.

    :param text: String to justify, may contain terminal sequences.
    :param dest_width: Total display width of result in terminal cells.
    :param fillchar: Single character for padding (default space). Must have
        display width of 1 (not wide, not zero-width, not combining). Unicode
        characters like ``'·'`` are acceptable. The width is not validated.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: Text padded on the left to reach ``dest_width``.

    .. versionadded:: 0.3.0

    Example::

        >>> wcwidth.rjust('hi', 5)
        '   hi'
        >>> wcwidth.rjust('\x1b[31mhi\x1b[0m', 5)
        '   \x1b[31mhi\x1b[0m'
        >>> wcwidth.rjust('\U0001F468\u200D\U0001F469\u200D\U0001F467', 6)
        '    👨‍👩‍👧'
    """
    if text.isascii() and text.isprintable():
        text_width = len(text)
    else:
        text_width = width(text, control_codes=control_codes, ambiguous_width=ambiguous_width)
    padding_cells = max(0, dest_width - text_width)
    return fillchar * padding_cells + text


def center(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    ambiguous_width: int = 1,
) -> str:
    r"""
    Return text centered in a string of given display width.

    :param text: String to center, may contain terminal sequences.
    :param dest_width: Total display width of result in terminal cells.
    :param fillchar: Single character for padding (default space). Must have
        display width of 1 (not wide, not zero-width, not combining). Unicode
        characters like ``'·'`` are acceptable. The width is not validated.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: Text padded on both sides to reach ``dest_width``.

    For odd-width padding, the extra cell goes on the right (matching
    Python's :meth:`str.center` behavior).

    .. versionadded:: 0.3.0

    Example::

        >>> wcwidth.center('hi', 6)
        '  hi  '
        >>> wcwidth.center('\x1b[31mhi\x1b[0m', 6)
        '  \x1b[31mhi\x1b[0m  '
        >>> wcwidth.center('\U0001F468\u200D\U0001F469\u200D\U0001F467', 6)
        '  👨‍👩‍👧  '
    """
    if text.isascii() and text.isprintable():
        text_width = len(text)
    else:
        text_width = width(text, control_codes=control_codes, ambiguous_width=ambiguous_width)
    total_padding = max(0, dest_width - text_width)
    # matching https://jazcap53.github.io/pythons-eccentric-strcenter.html
    left_pad = total_padding // 2 + (total_padding & dest_width & 1)
    right_pad = total_padding - left_pad
    return fillchar * left_pad + text + fillchar * right_pad


def clip(
    text: str,
    start: int,
    end: int,
    *,
    fillchar: str = ' ',
    tabsize: int = 8,
    ambiguous_width: int = 1,
    propagate_sgr: bool = True,
) -> str:
    r"""
    Clip text to display columns ``(start, end)`` while preserving all terminal sequences.

    This function extracts a substring based on visible column positions rather than
    character indices. Terminal escape sequences are preserved in the output since
    they have zero display width. If a wide character (width 2) would be split at
    either boundary, it is replaced with ``fillchar``.

    TAB characters (``\t``) are expanded to spaces up to the next tab stop,
    controlled by the ``tabsize`` parameter.

    Other cursor movement characters (backspace, carriage return) and cursor
    movement sequences are passed through unchanged as zero-width.

    :param text: String to clip, may contain terminal escape sequences.
    :param start: Absolute starting column (inclusive, 0-indexed).
    :param end: Absolute ending column (exclusive).
    :param fillchar: Character to use when a wide character must be split at
        a boundary (default space). Must have display width of 1.
    :param tabsize: Tab stop width (default 8). Set to 0 to pass tabs through
        as zero-width (preserved in output but don't advance column position).
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :param propagate_sgr: If True (default), SGR (terminal styling) sequences
        are propagated. The result begins with any active style at the start
        position and ends with a reset sequence if styles are active.
    :returns: Substring of ``text`` spanning display columns ``(start, end)``,
        with all terminal sequences preserved and wide characters at boundaries
        replaced with ``fillchar``.

    SGR (terminal styling) sequences are propagated by default. The result
    begins with any active style and ends with a reset::

        >>> clip('\x1b[1;34mHello world\x1b[0m', 6, 11)
        '\x1b[1;34mworld\x1b[0m'

    Set ``propagate_sgr=False`` to disable this behavior.

    .. versionadded:: 0.3.0

    .. versionchanged:: 0.5.0
       Added ``propagate_sgr`` parameter (default True).

    Example::

        >>> clip('hello world', 0, 5)
        'hello'
        >>> clip('中文字', 0, 3)  # Wide char split at column 3
        '中 '
        >>> clip('a\tb', 0, 10)  # Tab expanded to spaces
        'a       b'
    """
    # pylint: disable=too-complex,too-many-locals,too-many-branches,too-many-statements,too-many-nested-blocks,W0101
    # Again, for 'hot path', we avoid additional delegate functions and accept the cost
    # of complexity for improved python performance.
    start = max(start, 0)
    if end <= start:
        return ''

    # Fast path: printable ASCII only (no tabs, escape sequences, or wide or zero-width chars)
    if text.isascii() and text.isprintable():
        return text[start:end]

    # Fast path: no escape sequences means no SGR tracking needed
    if propagate_sgr and '\x1b' not in text:
        propagate_sgr = False

    # SGR tracking state (only when propagate_sgr=True)
    # sgr_at_clip_start is sgr state when first visible char emitted (None = not yet)
    sgr_at_clip_start = None
    # current active sgr state
    sgr = None  # current SGR state, updated by matches of _SGR_PATTERN
    if propagate_sgr:
        sgr = _SGR_STATE_DEFAULT

    # output_tokens stores tuples ('vis', text) for visible content and ('seq', seq)
    # for preserved zero-width sequences. This allows cursor-left overwrites to
    # remove previously emitted visible characters while keeping the sequence order.
    # For visible tokens we store ('vis', text, width_in_columns)
    # For sequences we store ('seq', seq)
    output_tokens: list[Token] = []
    visible_count = 0  # number of visible columns emitted so far
    col = 0
    idx = 0

    def _append_visible(s: str, w: int, start_col: int | None = None) -> None:
        nonlocal visible_count, sgr_at_clip_start
        if w <= 0:
            return
        if start_col is None:
            start_col = col
        prev = output_tokens[-1] if (output_tokens and output_tokens[-1][0] == 'vis') else None
        if prev is not None and prev[3] + prev[2] == start_col:
            # merge with previous contiguous visible token: append text and add widths
            prev_s = prev[1]
            prev_w = prev[2]
            prev_start = prev[3]
            output_tokens[-1] = ('vis', prev_s + s, prev_w + w, prev_start)
        else:
            output_tokens.append(('vis', s, w, start_col))
        visible_count += w
        if propagate_sgr and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _append_seq(seq: str) -> None:
        nonlocal sgr_at_clip_start
        output_tokens.append(('seq', seq))
        if propagate_sgr and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _remove_visible_tail(n: int) -> None:
        """Remove n visible columns from the end of output_tokens (overwrite semantics)."""
        nonlocal visible_count
        to_remove = n
        while to_remove > 0 and visible_count > 0:
            # find last visible token
            i = len(output_tokens) - 1
            while i >= 0 and output_tokens[i][0] != 'vis':
                i -= 1
            if i < 0:
                break
            tok = output_tokens[i]
            assert tok[0] == 'vis'  # guaranteed by while loop above
            tok_s = tok[1]
            tok_w = tok[2]
            tok_start = tok[3]
            if tok_w <= to_remove:
                # remove entire token
                output_tokens.pop(i)
                to_remove -= tok_w
                visible_count -= tok_w
            else:
                # shorten token by removing columns from the end
                keep_cols = tok_w - to_remove
                # slice the string by grapheme widths
                kept_text = ''
                acc = 0
                for g in iter_graphemes(tok_s):
                    gw = width(g, ambiguous_width=ambiguous_width)
                    if acc + gw > keep_cols:
                        break
                    kept_text += g
                    acc += gw
                output_tokens[i] = ('vis', kept_text, acc, tok_start)
                visible_count -= to_remove
                to_remove = 0

    while idx < len(text):
        char = text[idx]

        # Early exit: past visible region, SGR captured, no escape ahead
        if col >= end and sgr_at_clip_start is not None and char != '\x1b':
            break

        # 1. Handle escape sequences
        if char == '\x1b':
            if (match := ZERO_WIDTH_PATTERN.match(text, idx)):
                seq = match.group()
                if (propagate_sgr and sgr) and _SGR_PATTERN.match(seq):
                    # Update SGR state; will be applied as prefix when visible content starts
                    sgr = _sgr_state_update(sgr, seq)
                    # we've consumed the sequence; advance index and continue
                    idx = match.end()
                    continue

                # Handle cursor movement sequences specially to simulate visible
                # effects (fillchar padding for rightward moves, overwrite for left).
                if (match_cleft := CURSOR_RIGHT_SEQUENCE.match(seq)):
                    # parse numeric argument (default 1)
                    digit_txt = match_cleft.group(1)
                    n_left = int(digit_txt) if digit_txt else 1
                    # If movement crosses into the clip window, emit fillchars
                    move_start = col
                    move_end = col + n_left
                    if move_start < end and move_end > start:
                        overlap_start = max(move_start, start)
                        overlap_end = min(move_end, end)
                        overlap = overlap_end - overlap_start
                        if overlap > 0:
                            _append_visible(fillchar * overlap, overlap, overlap_start)
                    col += n_left
                    idx = match.end()
                    continue

                if (match_cright := CURSOR_LEFT_SEQUENCE.match(seq)):
                    digit_txt = match_cright.group(1)
                    n_right = int(digit_txt) if digit_txt else 1
                    prev_col = col
                    col = max(0, col - n_right)
                    # If we moved left and had emitted visible columns beyond
                    # the new col, they are now potentially overwritten.
                    if prev_col > col:
                        to_remove = min(prev_col - col, visible_count)
                        if to_remove > 0:
                            _remove_visible_tail(to_remove)
                    idx = match.end()
                    continue
                # Other zero-width sequences (OSC hyperlinks, etc.) — preserve as-is
                _append_seq(seq)
                idx = match.end()
                continue

        # 2. Handle bare ESC (not a valid sequence)
        if char == '\x1b':
            _append_seq(char)
            idx += 1
            continue

        # 3. TAB expansion
        if char == '\t':
            if tabsize > 0:
                next_tab = col + (tabsize - (col % tabsize))
                while col < next_tab:
                    if start <= col < end:
                        _append_visible(' ', 1)
                    col += 1
            else:
                # preserve tab as-is
                _append_seq(char)
            idx += 1
            continue

        # 4. Grapheme clustering for everything else
        grapheme = next(iter_graphemes(text, start=idx))
        grapheme_w = width(grapheme, ambiguous_width=ambiguous_width)

        if grapheme_w == 0:
            # combining/zero-width grapheme; preserve as sequence-like token at this column
            if start <= col < end:
                _append_seq(grapheme)
        elif col >= start and col + grapheme_w <= end:
            # Fully visible
            _append_visible(grapheme, grapheme_w)
            col += grapheme_w
        elif col < end and col + grapheme_w > start:
            # Partially visible (wide char at boundary) -> emit fillchars for visible portion
            overlap = min(end, col + grapheme_w) - max(start, col)
            abs_start = max(start, col)
            _append_visible(fillchar * overlap, overlap, abs_start)
            col += grapheme_w
        else:
            col += grapheme_w

        idx += len(grapheme)

    # Reconstruct result from output_tokens, slicing visible content to [start,end)
    parts: list[str] = []
    for tok in output_tokens:
        if tok[0] == 'seq':
            parts.append(tok[1])
        else:
            # visible chunk: ('vis', text, width_in_cols, start_col)
            _, text, tok_w, tok_start = tok
            chunk_len = tok_w
            chunk_start = tok_start
            chunk_end = chunk_start + chunk_len
            if chunk_end <= start:
                continue
            if chunk_start >= end:
                continue
            s0 = max(0, start - chunk_start)
            s1 = min(chunk_len, end - chunk_start)
            # slice `text` for columns [s0, s1)
            acc = 0
            slice_text = ''
            for g in iter_graphemes(text):
                gw = width(g, ambiguous_width=ambiguous_width)
                next_acc = acc + gw
                if next_acc <= s0:
                    acc = next_acc
                    continue
                if acc >= s1:
                    break
                # include this grapheme (or part of it)
                # graphemes are atomic; if they partially overlap, use fillchar instead
                if acc < s0 or next_acc > s1:
                    # partial grapheme -> fill with appropriate number of fillchars
                    left = max(0, s0 - acc)
                    right = min(gw, s1 - acc)
                    slice_text += fillchar * (right - left)
                else:
                    slice_text += g
                acc = next_acc
            parts.append(slice_text)

    result = ''.join(parts)

    # Apply SGR prefix/suffix
    if sgr_at_clip_start is not None:
        if prefix := _sgr_state_to_sequence(sgr_at_clip_start):
            result = prefix + result
        if _sgr_state_is_active(sgr_at_clip_start):
            result += '\x1b[0m'

    return result
