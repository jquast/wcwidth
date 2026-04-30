"""This is a python implementation of clip()."""
# std imports
from itertools import islice

from typing import Union, Callable, NamedTuple

# local
from .width import width
from .grapheme import iter_graphemes
from .sgr_state import (_SGR_STATE_DEFAULT,
                        _sgr_state_update,
                        _sgr_state_is_active,
                        _sgr_state_to_sequence)
from .text_sizing import TextSizing, TextSizingParams
from .escape_sequences import _SEQUENCE_CLASSIFY


class VisToken(NamedTuple):
    """A visible text segment with its display width and starting column."""

    text: str
    width: int
    start_col: int


class SeqToken(NamedTuple):
    """A zero-width terminal sequence (escape sequences, control chars, etc.)."""

    text: str


Token = Union[VisToken, SeqToken]


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
    start = max(start, 0)
    if end <= start:
        return ''

    # Fast path: printable ASCII only (no tabs, escape sequences, or wide or zero-width chars)
    if text.isascii() and text.isprintable():
        return text[start:end]

    # Fast path: no escape sequences means no SGR tracking needed
    if propagate_sgr and '\x1b' not in text:
        propagate_sgr = False

    # SGR tracking state (only when propagate_sgr=True) sgr_at_clip_start is
    # sgr state when first visible char emitted (None = not yet)
    sgr_at_clip_start = None
    # current active sgr state
    sgr = None  # current SGR state, updated by SGR matches
    if propagate_sgr:
        sgr = _SGR_STATE_DEFAULT

    # Painter's algorithm data structures:
    # map column integer to a visible character (with its width)
    cells: dict[int, tuple[str, int]] = {}
    # map column integer to a list of zero-width sequences emitted at that position
    # (col, seq_order, text)
    sequences: list[tuple[int, int, str]] = []
    # ordering of sequences
    seq_order = 0

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

        # 1. Handle escape sequences and bare ESC — single regex dispatch
        if char == '\x1b':
            m = _SEQUENCE_CLASSIFY.match(text, idx)
            if not m:
                _append_seq(char)
                idx += 1
                continue

            # Dispatch on which named group captured:
            if (m.group('sgr_params')) is not None and (propagate_sgr and sgr):
                sgr = _sgr_state_update(sgr, m.group())
                idx = m.end()
                continue

            # 1a. Cursor forward,
            if (cforward_n := m.group('cforward_n')) is not None:
                n_forward = int(cforward_n) if cforward_n else 1
                move_end = col + n_forward
                if col < end and move_end > start:
                    for i in range(max(col, start), min(move_end, end)):
                        _write_cells(fillchar, 1, i)
                col = move_end
                idx = m.end()
                continue

            # 1b. Cursor backward,
            if (cbackward_n := m.group('cbackward_n')) is not None:
                n_backward = int(cbackward_n) if cbackward_n else 1
                col = max(0, col - n_backward)
                idx = m.end()
                continue

            # 1c. OSC 66 Text Sizing
            if (ts_meta := m.group('ts_meta')) is not None:
                ts_text = m.group('ts_text')
                ts_term = m.group('ts_term')
                col = _text_sizing_clip(
                    TextSizing(
                        TextSizingParams.from_params(ts_meta),
                        ts_text,
                        ts_term),
                    col=col, start=start, end=end,
                    write_cells=_write_cells,
                    fillchar=fillchar, ambiguous_width=ambiguous_width,
                )
                if propagate_sgr and sgr_at_clip_start is None:
                    sgr_at_clip_start = sgr
                idx = m.end()
                continue

            # 1d. Any other recognized zero-width sequence
            _append_seq(m.group())
            idx = m.end()
            continue

        # 2. TAB expansion
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

        # 3. Grapheme clustering for everything else
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

    # Reconstruct result from "painter's algorithm", this allows us to
    # accurately depict clipping with horizontal movement
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
            walk_col += cell_w
        else:
            # Hole: emit fillchar for columns inside (start, end) that lie
            # within the written cell area
            if start <= walk_col <= max_cell_col:
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
    # pylint: disable=too-many-locals,too-many-branches,too-complex
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
        for _, g in enumerate(islice(iter_graphemes(ts.text), ts.params.width)):
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
