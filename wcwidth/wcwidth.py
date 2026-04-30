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
from typing import Literal, NamedTuple, Union

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
from .text_sizing import TextSizing, TextSizingParams
from .control_codes import ILLEGAL_CTRL, VERTICAL_CTRL, HORIZONTAL_CTRL, ZERO_WIDTH_CTRL
from .table_grapheme import ISC_CONSONANT
from .table_ambiguous import AMBIGUOUS_EASTASIAN
from .escape_sequences import (ZERO_WIDTH_PATTERN,
                               TEXT_SIZING_PATTERN,
                               CURSOR_LEFT_SEQUENCE,
                               CURSOR_RIGHT_SEQUENCE,
                               INDETERMINATE_EFFECT_SEQUENCE,
                               iter_sequences,
                               strip_sequences)
from .unicode_versions import list_versions

# Token types for output_tokens used by clip().
# NamedTuple subclasses provide named attribute access while remaining
# plain tuples at runtime — zero overhead over the old bare-tuple approach,
# but with isinstance() type discrimination and meaningful attribute names.


class VisToken(NamedTuple):
    """A visible text segment with its display width and starting column."""

    text: str
    width: int
    start_col: int


class SeqToken(NamedTuple):
    """A zero-width terminal sequence (escape sequences, control chars, etc.)."""

    text: str


Token = Union[VisToken, SeqToken]

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

    .. versionchanged:: 0.6.1
       Parses OSC 66 Sequences.

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

    # output_tokens stores VisToken for visible content and SeqToken for preserved
    # zero-width sequences. This allows cursor-left overwrites to remove previously
    # emitted visible characters while keeping the sequence order.
    output_tokens: list[Token] = []
    visible_count = 0  # number of visible columns emitted so far
    col = 0
    idx = 0

    def _append_visible(s: str, w: int, start_col: int | None = None) -> None:
        nonlocal visible_count, sgr_at_clip_start
        if start_col is None:
            start_col = col
        prev = output_tokens[-1] if (output_tokens and isinstance(output_tokens[-1], VisToken)) else None
        if prev is not None and prev.start_col + prev.width == start_col:
            # merge with previous contiguous visible token: append text and add widths
            output_tokens[-1] = VisToken(prev.text + s, prev.width + w, prev.start_col)
        else:
            output_tokens.append(VisToken(s, w, start_col))
        visible_count += w
        if propagate_sgr and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _append_seq(seq: str) -> None:
        nonlocal sgr_at_clip_start
        output_tokens.append(SeqToken(seq))
        if propagate_sgr and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _remove_visible_tail(n: int) -> None:
        """Remove n visible columns from the end of output_tokens (overwrite semantics)."""
        nonlocal visible_count
        to_remove = n
        while to_remove > 0 and visible_count > 0:
            # find last visible token
            i = len(output_tokens) - 1
            while i >= 0 and not isinstance(output_tokens[i], VisToken):
                i -= 1
            if i < 0:
                break
            tok = output_tokens[i]
            if tok.width <= to_remove:
                # remove entire token
                output_tokens.pop(i)
                to_remove -= tok.width
                visible_count -= tok.width
            else:
                # shorten token by removing columns from the end
                keep_cols = tok.width - to_remove
                # slice the string by grapheme widths
                kept_text = ''
                acc = 0
                g_iter = iter_graphemes(tok.text)
                while acc < keep_cols:
                    g = next(g_iter)
                    gw = width(g, ambiguous_width=ambiguous_width)
                    if acc + gw > keep_cols:
                        break
                    kept_text += g
                    acc += gw
                output_tokens[i] = VisToken(kept_text, acc, tok.start_col)
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
                        _append_visible(fillchar * (overlap_end - overlap_start),
                                        overlap_end - overlap_start, overlap_start)
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

                if (ts_match := TEXT_SIZING_PATTERN.match(seq)):
                    # OSC 66 (text sizing) has positive width
                    col, visible_count = _text_sizing_clip(
                        TextSizing.from_match(ts_match),
                        col=col, start=start, end=end,
                        output_tokens=output_tokens,
                        visible_count=visible_count,
                        fillchar=fillchar, ambiguous_width=ambiguous_width,
                    )
                    if propagate_sgr and sgr_at_clip_start is None:
                        sgr_at_clip_start = sgr
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

    # Reconstruct result from output_tokens.  The emission phase guarantees that
    # all visible tokens are fully within the clip window, so no sub-token slicing
    # or boundary checks are needed here.
    parts: list[str] = []
    for tok in output_tokens:
        if isinstance(tok, SeqToken):
            parts.append(tok.text)
        else:
            parts.append(tok.text)

    result = ''.join(parts)

    # Apply SGR prefix/suffix
    if sgr_at_clip_start is not None:
        if prefix := _sgr_state_to_sequence(sgr_at_clip_start):
            result = prefix + result
        if _sgr_state_is_active(sgr_at_clip_start):
            result += '\x1b[0m'

    return result


def _text_sizing_clip(
    ts: TextSizing,
    *,
    col: int,
    start: int,
    end: int,
    output_tokens: list[Token],
    visible_count: int,
    fillchar: str = ' ',
    ambiguous_width: int = 1,
) -> tuple[int, int]:
    """
    Emit tokens for a text-sizing sequence into ``output_tokens``, clipped to ``[start, end)``.

    Returns ``(new_col, new_visible_count)``.

    This was formerly ``TextSizing.clip()`` in :mod:`wcwidth.text_sizing`.  It was moved here to
    break a circular dependency loop (:mod:`text_sizing` imported :mod:`_width`, and :mod:`_width`
    imported :mod:`text_sizing`).
    """
    # pylint: disable=too-many-locals
    ts_width = ts.display_width(ambiguous_width)
    if col >= start and col + ts_width <= end:
        output_tokens.append(SeqToken(ts.make_sequence()))
        return col + ts_width, visible_count
    if col >= end or col + ts_width <= start:
        return col + ts_width, visible_count

    # Partial overlap: decompose into units (graphemes at `scale` cells each),
    # emit whole units as sequences and partial units as fillchars.
    rel_start = max(0, start - col)
    rel_end = min(end, col + ts_width) - col
    scale = ts.params.scale

    units: list[tuple[str, int]] = []
    if ts.params.width > 0:
        inner_graphemes = list(iter_graphemes(ts.text))
        for j in range(ts.params.width):
            g = inner_graphemes[j] if j < len(inner_graphemes) else ''
            units.append((g, scale))
    else:
        for g in iter_graphemes(ts.text):
            units.append((g, width(g, ambiguous_width=ambiguous_width) * scale))

    pos = 0
    pending_texts: list[str] = []

    def flush():
        if not pending_texts:
            return
        params = TextSizingParams(
            scale,
            len(pending_texts) if ts.params.width > 0 else 0,
            ts.params.numerator,
            ts.params.denominator,
            ts.params.vertical_align,
            ts.params.horizontal_align)
        output_tokens.append(
            SeqToken(TextSizing(params, ''.join(pending_texts), ts.terminator).make_sequence()))
        pending_texts.clear()

    for unit_text, unit_w in units:
        unit_start = pos
        unit_end = pos + unit_w
        if unit_end <= rel_start:
            pos = unit_end
            continue
        if unit_start >= rel_end:
            break
        overlap = min(unit_end, rel_end) - max(unit_start, rel_start)
        if overlap == unit_w and unit_w > 0:
            pending_texts.append(unit_text)
        else:
            flush()
            abs_start = col + max(unit_start, rel_start)
            output_tokens.append(VisToken(fillchar * overlap, overlap, abs_start))
            visible_count += overlap
        pos = unit_end

    flush()
    return col + ts_width, visible_count