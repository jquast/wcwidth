"""This is a python implementation of clip()."""
# std imports
import re

from typing import Literal, Optional, NamedTuple

# local
from ._width import width
from .grapheme import iter_graphemes
from .sgr_state import (_SGR_STATE_DEFAULT,
                        _sgr_state_update,
                        _sgr_state_is_active,
                        _sgr_state_to_sequence)
from .escape_sequences import _SEQUENCE_CLASSIFY, _HORIZONTAL_CURSOR_MOVEMENT

# OSC 8 hyperlink parsing (mirrors textwrap.py to avoid circular import)
_HYPERLINK_OPEN_RE = re.compile(r'\x1b]8;([^;]*);([^\x07\x1b]*)(\x07|\x1b\\)')
_HYPERLINK_CLOSE_RE = re.compile(r'\x1b]8;;(?:\x07|\x1b\\)')


class _HyperlinkState(NamedTuple):
    """Open OSC 8 hyperlink: url, params, terminator (BEL or ST)."""

    url: str
    params: str
    terminator: str


def _parse_hyperlink_open(seq: str) -> Optional[_HyperlinkState]:
    if (m := _HYPERLINK_OPEN_RE.match(seq)):
        return _HyperlinkState(url=m.group(2), params=m.group(1), terminator=m.group(3))
    return None


def _make_hyperlink_open(state: _HyperlinkState) -> str:
    return f'\x1b]8;{state.params};{state.url}{state.terminator}'


def _make_hyperlink_close(terminator: str) -> str:
    return f'\x1b]8;;{terminator}'


def _find_hyperlink_close(text: str, open_end: int) -> Optional[tuple[int, int]]:
    """
    Find matching OSC 8 close, handling nesting.

    Returns (start, end) or None.
    """
    depth = 1
    idx = open_end
    while idx < len(text):
        if text[idx] != '\x1b':
            idx += 1
            continue
        m = _SEQUENCE_CLASSIFY.match(text, idx)
        if not m:
            idx += 1
            continue
        seq = m.group()
        if _HYPERLINK_CLOSE_RE.match(seq):
            depth -= 1
            if depth == 0:
                return (idx, m.end())
        elif _parse_hyperlink_open(seq):
            depth += 1
        idx = m.end()
    return None


def clip(
    text: str,
    start: int,
    end: int,
    *,
    fillchar: str = ' ',
    tabsize: int = 8,
    ambiguous_width: int = 1,
    propagate_sgr: bool = True,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
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

    **OSC 8 hyperlinks** are handled specially: the visible text inside a hyperlink
    is clipped to the requested column range, and the hyperlink is rebuilt around
    the clipped text.  Empty hyperlinks (those with no remaining visible text after
    clipping) are removed::

        >>> clip('\x1b]8;;http://example.com\x07Click This link\x1b]8;;\x07', 6, 10)
        '\x1b]8;;http://example.com\x07This\x1b]8;;\x07'

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
    :param control_codes: How to handle control characters and sequences:

        - ``'parse'`` (default): Track horizontal cursor movement and clip
          hyperlink text.  Cursor overwrite of hyperlink cells is allowed
          (the hyperlink open/close are preserved as sequences).
        - ``'strict'``: Like ``parse``, but raises :exc:`ValueError` when a
          cursor movement would overwrite a cell that is part of an OSC 8
          hyperlink, as this produces indeterminate results on real terminals.
        - ``'ignore'``: All control characters are treated as zero-width.
          Cursor movement is not tracked (fastest path).

    :returns: Substring of ``text`` spanning display columns ``(start, end)``,
        with all terminal sequences preserved and wide characters at boundaries
        replaced with ``fillchar``.

    :raises ValueError: If ``control_codes='strict'`` and a cursor movement
        would overwrite a cell that was emitted as part of an OSC 8 hyperlink.

    SGR (terminal styling) sequences are propagated by default. The result
    begins with any active style and ends with a reset::

        >>> clip('\x1b[1;34mHello world\x1b[0m', 6, 11)
        '\x1b[1;34mworld\x1b[0m'

    Set ``propagate_sgr=False`` to disable this behavior.

    .. versionadded:: 0.3.0

    .. versionchanged:: 0.5.0
       Added ``propagate_sgr`` parameter (default True).

    .. versionchanged:: 0.7.0
       Added ``control_codes`` parameter and OSC 8 hyperlink-aware clipping.

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

    strict = control_codes == 'strict'

    # Fast path: printable ASCII only (no tabs, escape sequences, or wide or zero-width chars)
    if text.isascii() and text.isprintable():
        return text[start:end]

    # Fast path: no escape sequences means no SGR tracking needed
    has_esc = '\x1b' in text
    if propagate_sgr and not has_esc:
        propagate_sgr = False

    # Use painter's algorithm only when cursor movement (BS, CR, CSI C/D) can overwrite
    # previously emitted cells. Text without any horizontal movement uses the fast simple path.
    # Use direct char checks to avoid regex scan overhead for the common (no-cursor) case.
    use_painter = (
        control_codes != 'ignore' and
        ('\x08' in text or '\r' in text or
         (has_esc and bool(_HORIZONTAL_CURSOR_MOVEMENT.search(text))))
    )

    # SGR tracking state (only when propagate_sgr=True) sgr_at_clip_start is
    # sgr state when first visible char emitted (None = not yet)
    sgr_at_clip_start = None
    # current active sgr state
    sgr = None  # current SGR state, updated by SGR matches
    if propagate_sgr:
        sgr = _SGR_STATE_DEFAULT

    if not use_painter:
        # Simple path: no cursor movement — direct output.append() is sufficient.
        # This matches the original (master-branch) clip performance characteristics.
        output: list[str] = []
        col = 0
        idx = 0

        while idx < len(text):
            char = text[idx]

            # Early exit: past visible region, SGR captured, no escape ahead
            if col >= end and sgr_at_clip_start is not None and char != '\x1b':
                break

            # Handle escape sequences
            if char == '\x1b':
                m = _SEQUENCE_CLASSIFY.match(text, idx)
                if not m:
                    output.append(char)
                    idx += 1
                    continue

                seq = m.group()

                # SGR handling: update state, don't emit sequence
                if m.group('sgr_params') is not None and propagate_sgr and sgr:
                    sgr = _sgr_state_update(sgr, seq)
                    idx = m.end()
                    continue

                # OSC 8 hyperlink open: process as a unit (recursively clip inner text)
                if (hl_state := _parse_hyperlink_open(seq)):
                    close_span = _find_hyperlink_close(text, m.end())
                    if close_span is None:
                        # No matching close: treat as regular zero-width sequence
                        output.append(seq)
                        idx = m.end()
                        continue

                    close_start, close_end = close_span
                    inner_text = text[m.end():close_start]
                    inner_width = width(
                        inner_text, control_codes=control_codes,
                        tabsize=tabsize, ambiguous_width=ambiguous_width,
                    )

                    if inner_width == 0:
                        # Empty hyperlink: drop entirely
                        idx = close_end
                        continue

                    # Determine if hyperlink column range overlaps clip window
                    hl_col_start = col
                    hl_col_end = col + inner_width

                    if hl_col_end <= start or hl_col_start >= end:
                        # Hyperlink entirely outside clip window: skip it
                        col += inner_width
                        idx = close_end
                        continue

                    # Hyperlink overlaps clip window: recursively clip inner text
                    inner_clip_start = max(0, start - col)
                    inner_clip_end = end - col

                    clipped_inner = clip(
                        inner_text, inner_clip_start, inner_clip_end,
                        fillchar=fillchar, tabsize=tabsize,
                        ambiguous_width=ambiguous_width,
                        propagate_sgr=False,
                        control_codes=control_codes,
                    )

                    output.append(_make_hyperlink_open(hl_state))
                    output.append(clipped_inner)
                    output.append(_make_hyperlink_close(hl_state.terminator))
                    if propagate_sgr and sgr_at_clip_start is None:
                        sgr_at_clip_start = sgr

                    col += inner_width
                    idx = close_end
                    continue

                # Any other recognized sequence preserved as-is
                output.append(seq)
                idx = m.end()
                continue

            # TAB expansion
            if char == '\t':
                if tabsize > 0:
                    next_tab = col + (tabsize - (col % tabsize))
                    while col < next_tab:
                        if start <= col < end:
                            output.append(' ')
                            if propagate_sgr and sgr_at_clip_start is None:
                                sgr_at_clip_start = sgr
                        col += 1
                else:
                    output.append(char)
                idx += 1
                continue

            # Grapheme clustering for everything else
            grapheme = next(iter_graphemes(text, start=idx))
            grapheme_w = width(grapheme, ambiguous_width=ambiguous_width)

            if grapheme_w == 0:
                # combining/zero-width grapheme; preserve as token at this column
                if start <= col < end:
                    output.append(grapheme)
            elif col >= start and col + grapheme_w <= end:
                # Fully visible
                output.append(grapheme)
                if propagate_sgr and sgr_at_clip_start is None:
                    sgr_at_clip_start = sgr
            elif col < end and col + grapheme_w > start:
                # Partially visible (wide char at boundary) — emit fillchars
                output.append(fillchar * (min(end, col + grapheme_w) - max(start, col)))
                if propagate_sgr and sgr_at_clip_start is None:
                    sgr_at_clip_start = sgr
            # advance column whether visible or not
            col += grapheme_w
            idx += len(grapheme)

        result = ''.join(output)
    else:
        # Painter's algorithm path: handles cursor movement (BS, CR, CSI C/D/G)
        # that can overwrite previously emitted cells.

        # map column integer to a visible character (with its width)
        cells: dict[int, tuple[str, int]] = {}
        # set of column positions belonging to hyperlink visible cells (for strict mode)
        hyperlink_cells: set[int] = set()
        # map column integer to a list of zero-width sequences emitted at that position
        # (col, seq_order, text)
        sequences: list[tuple[int, int, str]] = []
        # ordering of sequences
        seq_order = 0

        col = 0
        idx = 0

        def _write_cells(s: str, w: int, write_col: int,
                         is_hyperlink: bool = False) -> None:
            nonlocal sgr_at_clip_start
            # Strict-mode check: overwriting hyperlink cells is indeterminate
            if strict and not is_hyperlink:
                for offset in range(w):
                    if write_col + offset in hyperlink_cells:
                        raise ValueError(
                            f"Cursor movement at column {write_col + offset} "
                            f"would overwrite an OSC 8 hyperlink cell. "
                            f"Use control_codes='parse' to allow this."
                        )
            # Fix up wide-char orphans and clear overwritten cells in one pass
            for offset in range(w):
                src_col = write_col + offset
                if src_col > 0 and cells.get(src_col - 1, ('', 0))[1] == 2:
                    cells[src_col - 1] = (fillchar, 1)
                    hyperlink_cells.discard(src_col - 1)
                if cells.get(src_col, ('', 0))[1] == 2:
                    cells[src_col + 1] = (fillchar, 1)
                    hyperlink_cells.discard(src_col + 1)
                cells.pop(src_col, None)
                hyperlink_cells.discard(src_col)
            cells[write_col] = (s, w)
            if is_hyperlink:
                for offset in range(w):
                    hyperlink_cells.add(write_col + offset)
            if propagate_sgr and sgr_at_clip_start is None:
                sgr_at_clip_start = sgr

        def _append_seq(seq: str, at_col: Optional[int] = None) -> None:
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

                seq = m.group()

                # Dispatch on which named group captured:
                if (m.group('sgr_params')) is not None and (propagate_sgr and sgr):
                    sgr = _sgr_state_update(sgr, seq)
                    idx = m.end()
                    continue

                # OSC 8 hyperlink open: process as a unit (recursively clip inner text)
                if (hl_state := _parse_hyperlink_open(seq)):
                    close_span = _find_hyperlink_close(text, m.end())
                    if close_span is None:
                        # No matching close: treat as regular sequence
                        _append_seq(seq)
                        idx = m.end()
                        continue

                    close_start, close_end = close_span
                    inner_text = text[m.end():close_start]
                    inner_width = width(
                        inner_text, control_codes=control_codes,
                        tabsize=tabsize, ambiguous_width=ambiguous_width,
                    )

                    if inner_width == 0:
                        # Empty hyperlink: drop entirely
                        idx = close_end
                        continue

                    # Determine if hyperlink column range overlaps clip window
                    hl_col_start = col
                    hl_col_end = col + inner_width

                    if hl_col_end <= start or hl_col_start >= end:
                        # Hyperlink entirely outside clip window: skip it
                        col += inner_width
                        idx = close_end
                        continue

                    # Hyperlink overlaps clip window: recursively clip inner text
                    inner_clip_start = max(0, start - col)
                    inner_clip_end = end - col

                    clipped_inner = clip(
                        inner_text, inner_clip_start, inner_clip_end,
                        fillchar=fillchar, tabsize=tabsize,
                        ambiguous_width=ambiguous_width,
                        propagate_sgr=False,
                        control_codes=control_codes,
                    )

                    # Emit hyperlink open as sequence, then clipped cells
                    _append_seq(_make_hyperlink_open(hl_state))
                    inner_clipped_width = width(
                        clipped_inner, control_codes=control_codes,
                        tabsize=tabsize, ambiguous_width=ambiguous_width,
                    )
                    _write_cells(clipped_inner, inner_clipped_width, col,
                                 is_hyperlink=True)
                    col += inner_clipped_width
                    # Emit hyperlink close as sequence after the cells
                    _append_seq(_make_hyperlink_close(hl_state.terminator),
                                at_col=col)

                    # Advance past the original hyperlink content
                    col = hl_col_end
                    idx = close_end
                    continue

                # 1a. HPA: horizontal position absolute (CSI n G)
                if (hpa_n := m.group('hpa_n')) is not None:
                    col = int(hpa_n) - 1 if hpa_n else 0
                    idx = m.end()
                    continue

                # 1b. Cursor forward,
                if (cforward_n := m.group('cforward_n')) is not None:
                    n_forward = int(cforward_n) if cforward_n else 1
                    move_end = col + n_forward
                    if col < end and move_end > start:
                        for i in range(max(col, start), min(move_end, end)):
                            _write_cells(fillchar, 1, i)
                    col = move_end
                    idx = m.end()
                    continue

                # 1c. Cursor backward,
                if (cbackward_n := m.group('cbackward_n')) is not None:
                    n_backward = int(cbackward_n) if cbackward_n else 1
                    col = max(0, col - n_backward)
                    idx = m.end()
                    continue

                # 1d. Any other recognized zero-width sequence
                _append_seq(seq)
                idx = m.end()
                continue

            # 2. Carriage return and backspace (before TAB/grapheme fallthrough)
            if char == '\r':
                # CR: reset column to 0
                col = 0
                idx += 1
                continue

            if char == '\x08':
                # BS: decrement column
                if col > 0:
                    col -= 1
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
                # All cells satisfy walk_col >= start and walk_col + cell_w <= end
                parts.append(cell_text)
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
