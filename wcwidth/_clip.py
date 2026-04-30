"""This is a python implementation of clip()."""
from __future__ import annotations

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

    When no horizontal cursor movements are present (backspace, carriage return, or
    CSI C/D/G sequences), cursor movement characters and sequences are passed through
    as zero-width sequences.  When cursor movement is detected, a "painter's
    algorithm" is used instead: cursor movements actively change the write position,
    allowing cursor-left and carriage return to overwrite previously written cells.

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

    # Inner helpers
    # Closure-based to avoid LOAD_GLOBAL overhead on hot-path calls.
    # Each has low individual McCabe complexity.

    def _mark_sgr_capture() -> None:
        """Record SGR state at first visible emit, if not already captured."""
        nonlocal sgr_at_clip_start
        if propagate_sgr and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _process_hyperlink(
        hl_state: _HyperlinkState, match_end: int, col: int,
    ) -> tuple[str, object]:
        """Process OSC 8 hyperlink unit.

        Returns (action, data):
          action='no_close'  -> data unused (emit as regular seq, advance past match_end)
          action='empty'     -> data is close_end (skip entirely)
          action='outside'   -> data is (inner_width, close_end) (advance col, skip)
          action='visible'   -> data is (open_seq, clipped_inner, close_seq,
                                         inner_width, hl_col_end, close_end)
        """
        close_span = _find_hyperlink_close(text, match_end)
        if close_span is None:
            return ('no_close', None)

        close_start, close_end = close_span
        inner_text = text[match_end:close_start]
        inner_width = width(
            inner_text, control_codes=control_codes,
            tabsize=tabsize, ambiguous_width=ambiguous_width,
        )

        if inner_width == 0:
            return ('empty', close_end)

        hl_col_start = col
        hl_col_end = col + inner_width

        if hl_col_end <= start or hl_col_start >= end:
            return ('outside', (inner_width, close_end))

        inner_clip_start = max(0, start - col)
        inner_clip_end = end - col

        clipped_inner = clip(
            inner_text, inner_clip_start, inner_clip_end,
            fillchar=fillchar, tabsize=tabsize,
            ambiguous_width=ambiguous_width,
            propagate_sgr=False,
            control_codes=control_codes,
        )

        return ('visible', (
            _make_hyperlink_open(hl_state),
            clipped_inner,
            _make_hyperlink_close(hl_state.terminator),
            inner_width,
            hl_col_end,
            close_end,
        ))

    def _emit_tab_simple(col: int, output: list[str]) -> int:
        """Expand tab for simple-path, appending spaces to output list."""
        if tabsize > 0:
            next_tab = col + (tabsize - (col % tabsize))
            while col < next_tab:
                if start <= col < end:
                    output.append(' ')
                    _mark_sgr_capture()
                col += 1
        else:
            output.append('\t')
        return col

    def _emit_tab_painter(col: int, write_cells, append_seq) -> int:
        """Expand tab for painter-path."""
        if tabsize > 0:
            next_tab = col + (tabsize - (col % tabsize))
            while col < next_tab:
                if start <= col < end:
                    write_cells(' ', 1, col)
                col += 1
        else:
            append_seq('\t')
        return col

    def _handle_grapheme_simple(
        grapheme: str, gw: int, col: int, output: list[str],
    ) -> None:
        """Emit grapheme to simple-path output list based on visibility."""
        if gw == 0:
            if start <= col < end:
                output.append(grapheme)
        elif col >= start and col + gw <= end:
            output.append(grapheme)
            _mark_sgr_capture()
        elif col < end and col + gw > start:
            output.append(fillchar * (min(end, col + gw) - max(start, col)))
            _mark_sgr_capture()

    def _handle_grapheme_painter(
        grapheme: str, gw: int, col: int, write_cells, append_seq,
    ) -> None:
        """Emit grapheme to painter-path based on visibility."""
        if gw == 0:
            if start <= col < end:
                append_seq(grapheme)
        elif col >= start and col + gw <= end:
            write_cells(grapheme, gw, col)
        elif col < end and col + gw > start:
            clip_start = max(start, col)
            for offset in range(min(end, col + gw) - clip_start):
                write_cells(fillchar, 1, clip_start + offset)

    def _apply_sgr_wrap(result: str) -> str:
        """Apply SGR prefix/suffix around result."""
        if sgr_at_clip_start is not None:
            if prefix := _sgr_state_to_sequence(sgr_at_clip_start):
                result = prefix + result
            if _sgr_state_is_active(sgr_at_clip_start):
                result += '\x1b[0m'
        return result

    # Main loops

    if not use_painter:
        # Simple path: no cursor movement
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

                # SGR handling: update state, don't emit sequence
                if m.group('sgr_params') is not None and propagate_sgr and sgr:
                    sgr = _sgr_state_update(sgr, m.group())
                    idx = m.end()
                    continue

                # OSC 8 hyperlink
                if hl_state := _parse_hyperlink_open(m.group()):
                    action, data = _process_hyperlink(hl_state, m.end(), col)
                    if action == 'no_close':
                        output.append(m.group())
                        idx = m.end()
                    elif action == 'empty':
                        idx = data
                    elif action == 'outside':
                        inner_width, close_end = data
                        col += inner_width
                        idx = close_end
                    else:  # 'visible'
                        open_seq, clipped_inner, close_seq, inner_width, _, close_end = data
                        output.append(open_seq)
                        output.append(clipped_inner)
                        output.append(close_seq)
                        _mark_sgr_capture()
                        col += inner_width
                        idx = close_end
                    continue

                # Any other recognized sequence preserved as-is
                output.append(m.group())
                idx = m.end()
                continue

            # TAB expansion
            if char == '\t':
                col = _emit_tab_simple(col, output)
                idx += 1
                continue

            # Grapheme clustering
            grapheme = next(iter_graphemes(text, start=idx))
            grapheme_w = width(grapheme, ambiguous_width=ambiguous_width)
            _handle_grapheme_simple(grapheme, grapheme_w, col, output)
            col += grapheme_w
            idx += len(grapheme)

        result = _apply_sgr_wrap(''.join(output))
        return result

    # Painter's algorithm path: handles cursor movement
    cells: dict[int, tuple[str, int]] = {}
    hyperlink_cells: set[int] = set()
    sequences: list[tuple[int, int, str]] = []
    seq_order = 0

    col = 0
    idx = 0

    def _write_cells(s: str, w: int, write_col: int,
                     is_hyperlink: bool = False) -> None:
        nonlocal sgr_at_clip_start
        if strict and not is_hyperlink:
            for offset in range(w):
                if write_col + offset in hyperlink_cells:
                    raise ValueError(
                        f"Cursor movement at column {write_col + offset} "
                        f"would overwrite an OSC 8 hyperlink cell. "
                        f"Use control_codes='parse' to allow this."
                    )
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
        _mark_sgr_capture()

    def _append_seq(seq: str, at_col: Optional[int] = None) -> None:
        nonlocal seq_order
        c = col if at_col is None else at_col
        sequences.append((c, seq_order, seq))
        seq_order += 1
        _mark_sgr_capture()

    while idx < len(text):
        char = text[idx]

        # Early exit: past visible region, SGR captured, no escape ahead
        if col >= end and sgr_at_clip_start is not None and char != '\x1b':
            break

        # 1. Handle escape sequences -- single regex dispatch
        if char == '\x1b':
            m = _SEQUENCE_CLASSIFY.match(text, idx)
            if not m:
                _append_seq(char)
                idx += 1
                continue

            # SGR handling: update state, don't emit sequence
            if m.group('sgr_params') is not None and propagate_sgr and sgr:
                sgr = _sgr_state_update(sgr, m.group())
                idx = m.end()
                continue

            # OSC 8 hyperlink
            if hl_state := _parse_hyperlink_open(m.group()):
                action, data = _process_hyperlink(hl_state, m.end(), col)
                if action == 'no_close':
                    _append_seq(m.group())
                    idx = m.end()
                elif action == 'empty':
                    idx = data
                elif action == 'outside':
                    inner_width, close_end = data
                    col += inner_width
                    idx = close_end
                else:  # 'visible'
                    open_seq, clipped_inner, close_seq, inner_width, hl_col_end, close_end = data
                    _append_seq(open_seq)
                    inner_clipped_width = width(
                        clipped_inner, control_codes=control_codes,
                        tabsize=tabsize, ambiguous_width=ambiguous_width,
                    )
                    _write_cells(clipped_inner, inner_clipped_width, col,
                                 is_hyperlink=True)
                    col += inner_clipped_width
                    _append_seq(close_seq, at_col=col)
                    # Advance past the original hyperlink content
                    col = hl_col_end
                    idx = close_end
                continue

            # 1a. HPA: horizontal position absolute (CSI n G)
            if (hpa_n := m.group('hpa_n')) is not None:
                col = int(hpa_n) - 1 if hpa_n else 0
                idx = m.end()
                continue

            # 1b. Cursor forward
            if (cforward_n := m.group('cforward_n')) is not None:
                n_forward = int(cforward_n) if cforward_n else 1
                move_end = col + n_forward
                if col < end and move_end > start:
                    for i in range(max(col, start), min(move_end, end)):
                        _write_cells(fillchar, 1, i)
                col = move_end
                idx = m.end()
                continue

            # 1c. Cursor backward
            if (cbackward_n := m.group('cbackward_n')) is not None:
                n_backward = int(cbackward_n) if cbackward_n else 1
                if strict and n_backward > col:
                    raise ValueError(
                        f"Cursor left movement at position {idx} would move "
                        f"{n_backward} cells left from column {col}, "
                        f"exceeding string start"
                    )
                col = max(0, col - n_backward)
                idx = m.end()
                continue

            # 1d. Any other recognized zero-width sequence
            _append_seq(m.group())
            idx = m.end()
            continue

        # 2. Carriage return and backspace (before TAB/grapheme fallthrough)
        if char == '\r':
            col = 0
            idx += 1
            continue

        if char == '\x08':
            if col > 0:
                col -= 1
            idx += 1
            continue

        # 3. TAB expansion
        if char == '\t':
            col = _emit_tab_painter(col, _write_cells, _append_seq)
            idx += 1
            continue

        # 4. Grapheme clustering
        grapheme = next(iter_graphemes(text, start=idx))
        grapheme_w = width(grapheme, ambiguous_width=ambiguous_width)
        _handle_grapheme_painter(grapheme, grapheme_w, col, _write_cells, _append_seq)
        col += grapheme_w
        idx += len(grapheme)

    # Reconstruct result from "painter's algorithm"
    seqs_by_col: dict[int, list[tuple[int, str]]] = {}
    for col_pos, order, seq_text in sequences:
        seqs_by_col.setdefault(col_pos, []).append((order, seq_text))
    for entries in seqs_by_col.values():
        entries.sort()

    max_cell_col = max(cells.keys()) if cells else -1
    max_seq_col = max(seqs_by_col.keys()) if seqs_by_col else -1
    max_col = max(max_cell_col, max_seq_col)

    parts: list[str] = []
    walk_col = 0
    col_limit = min(max_col, end)
    while walk_col <= col_limit:
        for _, seq_text in seqs_by_col.get(walk_col, ()):
            parts.append(seq_text)

        if walk_col >= end:
            walk_col += 1
            continue

        if walk_col in cells:
            cell_text, cell_w = cells[walk_col]
            parts.append(cell_text)
            walk_col += cell_w
        else:
            if start <= walk_col <= max_cell_col:
                parts.append(fillchar)
            walk_col += 1

    for c in sorted(seqs_by_col.keys()):
        if c > col_limit:
            for _, seq_text in seqs_by_col[c]:
                parts.append(seq_text)

    return _apply_sgr_wrap(''.join(parts))