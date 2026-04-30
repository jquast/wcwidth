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

# local
from .bisearch import bisearch
from ._constants import _LATEST_VERSION, _AMBIGUOUS_TABLE, _ZERO_WIDTH_TABLE, _WIDE_EASTASIAN_TABLE


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


# maxsize=1024: western scripts need ~64 unique codepoints per session, but
# CJK sessions may use ~2000 of ~3500 common hanzi/kanji. 1024 accommodates
# heavy CJK use. Performance floor at 32; bisearch is ~100ns per miss.

@lru_cache(maxsize=1024)
def wcwidth(wc: str, unicode_version: str = 'auto', ambiguous_width: int = 1) -> int:  # pylint: disable=unused-argument
    r"""
    Given one Unicode codepoint, return its printable length on a terminal.

    :param wc: A single Unicode character.
    :param unicode_version: Ignored. Retained for backwards compatibility.

        .. deprecated:: 0.3.0
           Only the latest Unicode version is now shipped.

    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts
        where ambiguous characters display as double-width. See
        :ref:`ambiguous_width` for details.
    :returns: The width, in cells, necessary to display the character of
        Unicode string character, ``wc``.  Returns 0 if the ``wc`` argument has
        no printable effect on a terminal (such as NUL '\0'), -1 if ``wc`` is
        not printable, or has an indeterminate effect on the terminal, such as
        a control character.  Otherwise, the number of column positions the
        character occupies on a graphic terminal (1 or 2) is returned.

    See :ref:`Specification` for details of cell measurement.
    """
    ucs = ord(wc) if wc else 0

    # small optimization: early return of 1 for printable ASCII, this provides
    # approximately 40% performance improvement for mostly-ascii documents, with
    # less than 1% impact to others.
    if 32 <= ucs < 0x7f:
        return 1

    # C0/C1 control characters are -1 for compatibility with POSIX-like calls
    if ucs and ucs < 32 or 0x07F <= ucs < 0x0A0:
        return -1

    # Zero width
    if bisearch(ucs, _ZERO_WIDTH_TABLE):
        return 0

    # Wide (F/W categories)
    if bisearch(ucs, _WIDE_EASTASIAN_TABLE):
        return 2

    # Ambiguous width (A category) - only when ambiguous_width=2
    if ambiguous_width == 2 and bisearch(ucs, _AMBIGUOUS_TABLE):
        return 2

<<<<<<< HEAD
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

    # Painter's algorithm data structures:
    # 1. cells: maps column integer to a visible character (with its width)
    #    cells that are part of a wide character's right half are not populated.
    # 2. sequences: maps column integer to a list of zero-width sequences emitted at that position
    #    and their chronological order number.
    cells: dict[int, tuple[str, int]] = {}
    sequences: list[tuple[int, int, str]] = []  # (col, seq_order, text)
    seq_order = 0  # relative ordering of sequences

    col = 0
    idx = 0

    def _write_cells(s: str, w: int, write_col: int) -> None:
        nonlocal sgr_at_clip_start
        if w > 0:
            # Fix up wide-char orphans and clear overwritten cells in one pass
            for offset in range(w):
                src_col = write_col + offset
                if src_col > 0 and cells.get(src_col - 1, ('', 0))[1] == 2:
                    cells[src_col - 1] = (fillchar, 1)
                if cells.get(src_col, ('', 0))[1] == 2:
                    cells[src_col + 1] = (fillchar, 1)
                cells.pop(src_col, None)
            cells[write_col] = (s, w)
        if propagate_sgr and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _append_seq(seq: str, at_col: int | None = None) -> None:
        nonlocal sgr_at_clip_start, seq_order
        c = col if at_col is None else at_col
        sequences.append((c, seq_order, seq))
        seq_order += 1
        if propagate_sgr and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    while idx < len(text):
        char = text[idx]

        # Early exit: past visible region, SGR captured, no escape ahead
        if col >= end and sgr_at_clip_start is not None and char != '\x1b':
            break

        # 1. Handle escape sequences and bare ESC
        if char == '\x1b':
            if (match := ZERO_WIDTH_PATTERN.match(text, idx)):
                seq = match.group()
                if (propagate_sgr and sgr) and _SGR_PATTERN.match(seq):
                    # Update SGR state; will be applied as prefix when visible content starts
                    sgr = _sgr_state_update(sgr, seq)
                    idx = match.end()
                    continue

                # Cursor-forward sequences (e.g. CSI n C) advance the column;
                # simulate by emitting fillchars for the visible portion.
                if (match_cforward := CURSOR_RIGHT_SEQUENCE.match(seq)):
                    digit_txt = match_cforward.group(1)
                    n_forward = int(digit_txt) if digit_txt else 1
                    move_end = col + n_forward
                    if col < end and move_end > start:
                        for i in range(max(col, start), min(move_end, end)):
                            _write_cells(fillchar, 1, i)
                    col = move_end
                    idx = match.end()
                    continue

                # Cursor-backward sequences (e.g. CSI n D) retreat the column.
                if (match_cbackward := CURSOR_LEFT_SEQUENCE.match(seq)):
                    digit_txt = match_cbackward.group(1)
                    n_backward = int(digit_txt) if digit_txt else 1
                    col = max(0, col - n_backward)
                    idx = match.end()
                    continue

                if (ts_match := TEXT_SIZING_PATTERN.match(seq)):
                    # OSC 66 (text sizing) has positive width
                    col = _text_sizing_clip(
                        TextSizing.from_match(ts_match),
                        col=col, start=start, end=end,
                        write_cells=_write_cells,
                        fillchar=fillchar, ambiguous_width=ambiguous_width,
                    )
                    if propagate_sgr and sgr_at_clip_start is None:
                        sgr_at_clip_start = sgr
                    idx = match.end()
                    continue

                # Other zero-width sequences (OSC hyperlinks, etc.) are preserved as-is
                _append_seq(seq)
                idx = match.end()
                continue
            else:
                # Bare ESC not matching any recognized sequence pattern
                _append_seq(char)
                idx += 1
                continue

        # 3. TAB expansion
        if char == '\t':
            if tabsize > 0:
                next_tab = col + (tabsize - (col % tabsize))
                while col < next_tab:
                    if start <= col < end:
                        _write_cells(' ', 1, col)
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
            # combining/zero-width grapheme; preserve as token at this column
            if start <= col < end:
                _append_seq(grapheme)
        elif col >= start and col + grapheme_w <= end:
            # Fully visible
            _write_cells(grapheme, grapheme_w, col)
        elif col < end and col + grapheme_w > start:
            # Partially visible (wide char at boundary) — emit fillchars
            clip_start = max(start, col)
            for i in range(min(end, col + grapheme_w) - clip_start):
                _write_cells(fillchar, 1, clip_start + i)
        # advance column whether visible or not
        col += grapheme_w
        idx += len(grapheme)

    # ── Reconstruct result from painter's algorithm grid ──────────────────
    # Build column→sorted sequences index
    seqs_by_col: dict[int, list[tuple[int, str]]] = {}
    for col_pos, order, seq_text in sequences:
        seqs_by_col.setdefault(col_pos, []).append((order, seq_text))
    for entries in seqs_by_col.values():
        entries.sort()

    max_cell_col = max(cells.keys()) if cells else -1
    max_seq_col = max(seqs_by_col.keys()) if seqs_by_col else -1
    max_col = max(max_cell_col, max_seq_col)

    # Walk columns 0..min(max_col, end), emitting sequences then any cell
    # or fillchar occupying each position.  Visits *inclusive* of
    # min(max_col, end) so sequences at `end` are preserved.
    parts: list[str] = []
    walk_col = 0
    col_limit = min(max_col, end)
    while walk_col <= col_limit:
        # Zero-width sequences at this column
        for _, seq_text in seqs_by_col.get(walk_col, ()):
            parts.append(seq_text)

        if walk_col >= end:
            walk_col += 1
            continue

        if walk_col in cells:
            cell_text, cell_w = cells[walk_col]
            cell_end = walk_col + cell_w

            if walk_col >= start and cell_end <= end:
                # Fully inside clip window
                parts.append(cell_text)
            elif cell_end > start:
                # Partial overlap (wide char split at boundary)
                parts.append(fillchar * (min(cell_end, end) - max(walk_col, start)))
            # else: cell entirely before start — skip

            walk_col += cell_w
        else:
            # Hole: emit fillchar for columns inside [start, end) that
            # lie within the written cell area
            if walk_col >= start and walk_col <= max_cell_col:
                parts.append(fillchar)
            walk_col += 1

    # Trailing sequences past col_limit (SGR resets after short text, etc.)
    for c in sorted(seqs_by_col.keys()):
        if c > col_limit:
            for _, seq_text in seqs_by_col[c]:
                parts.append(seq_text)

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
    write_cells: Callable[[str, int, int], None],
    fillchar: str = ' ',
    ambiguous_width: int = 1,
) -> int:
    """
    Emit tokens for a text-sizing (OSC 66) sequence, clipped to ``[start, end)``.

    Returns ``new_col`` (column position after the sequence).
    """
    # pylint: disable=too-many-locals
    ts_width = ts.display_width(ambiguous_width)

    # Sequence fully visible or fully outside: simple cases
    if col >= start and col + ts_width <= end:
        write_cells(ts.make_sequence(), ts_width, col)
        return col + ts_width
    if col >= end or col + ts_width <= start:
        return col + ts_width

    # Partial overlap: the sequence straddles a clip boundary.
    # Decompose into unit cells (each grapheme occupies `scale` cells),
    # emit as many whole units as fit inside [start, end), filling the
    # remainder with `fillchar`.
    rel_start = max(0, start - col)
    rel_end = min(end, col + ts_width) - col
    scale = ts.params.scale

    # Build the list of (grapheme, cell_width) units
    units: list[tuple[str, int]] = []
    if ts.params.width > 0:
        # Fixed-width mode: explicit count at `scale` cells each.
        # Use itertools.islice to avoid materializing the full grapheme list.
        # std imports
        from itertools import islice
        for j, g in enumerate(islice(iter_graphemes(ts.text), ts.params.width)):
            units.append((g, scale))
        # Pad with empty graphemes if text had fewer than width
        for _ in range(ts.params.width - len(units)):
            units.append(('', scale))
    else:
        # Auto-width mode: grapheme count derived from content, width varies
        for g in iter_graphemes(ts.text):
            units.append((g, width(g, ambiguous_width=ambiguous_width) * scale))

    # Batch of consecutive fully-visible units that can be emitted as a
    # single text-sizing sequence.
    pending_units: list[tuple[str, int]] = []  # (grapheme_text, cell_width)

    def flush(flush_col: int) -> None:
        """Emit accumulated graphemes as one text-sizing sequence."""
        if not pending_units:
            return
        texts = [u[0] for u in pending_units]
        total_w = sum(u[1] for u in pending_units)
        params = TextSizingParams(
            scale,
            len(texts) if ts.params.width > 0 else 0,
            ts.params.numerator,
            ts.params.denominator,
            ts.params.vertical_align,
            ts.params.horizontal_align)
        write_cells(
            TextSizing(params, ''.join(texts), ts.terminator).make_sequence(),
            total_w,
            flush_col)
        pending_units.clear()

    # Walk units in cell-coordinate space, collecting consecutive fully-visible
    # ones into a batch (flushed as one sequence) and emitting fillchars for
    # partial units at the boundaries.
    flush_col_pos = col + rel_start
    unit_pos = 0  # current position in cell-coordinates within the sequence
    for unit_text, unit_w in units:
        unit_end = unit_pos + unit_w
        if unit_end <= rel_start:
            # Unit is entirely before the clip window
            unit_pos = unit_end
            continue
        if unit_pos >= rel_end:
            # Unit is entirely past the clip window
            break

        overlap = min(unit_end, rel_end) - max(unit_pos, rel_start)
        if overlap == unit_w and unit_w > 0:
            # Unit fits completely — batch it with others
            if not pending_units:
                flush_col_pos = col + max(unit_pos, rel_start)
            pending_units.append((unit_text, unit_w))
        else:
            # Unit is partially clipped — flush batch, emit fillchars for remainder
            flush(flush_col_pos)
            abs_start = col + max(unit_pos, rel_start)
            for i in range(overlap):
                write_cells(fillchar, 1, abs_start + i)
        unit_pos = unit_end

    flush(flush_col_pos)
    return col + ts_width
=======
    return 1
>>>>>>> jq/refactor
