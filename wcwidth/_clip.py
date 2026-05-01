"""This is a python implementation of clip()."""
from __future__ import annotations

# std imports
import enum

from typing import Literal, Optional, NamedTuple

# local
from ._width import width
from .grapheme import iter_graphemes
from .hyperlink import Hyperlink, HyperlinkParams
from .sgr_state import (_SGR_STATE_DEFAULT,
                        _SGRState,
                        _sgr_state_update,
                        _sgr_state_is_active,
                        _sgr_state_to_sequence)
from .escape_sequences import (_SEQUENCE_CLASSIFY,
                               _HORIZONTAL_CURSOR_MOVEMENT,
                               INDETERMINATE_EFFECT_SEQUENCE)


class _ClipContext(NamedTuple):
    """Immutable parameters for a clip operation."""

    text: str
    start: int
    end: int
    fillchar: str
    tabsize: int
    ambiguous_width: int
    control_codes: Literal['parse', 'strict', 'ignore']
    strict: bool
    propagate_sgr: bool


class _HyperlinkAction(enum.Enum):
    """Outcome of processing an OSC 8 hyperlink unit."""

    NO_CLOSE = enum.auto()   # open sequence without matching close
    EMPTY = enum.auto()       # hyperlink with no visible inner text
    OUTSIDE = enum.auto()     # hyperlink entirely outside the clip window
    VISIBLE = enum.auto()     # hyperlink overlaps the clip window


class _HyperlinkResult(NamedTuple):
    """
    Result of processing an OSC 8 hyperlink.

    Only the fields relevant to each action are populated.
    """

    action: _HyperlinkAction
    close_end: int = 0
    inner_width: int = 0
    open_seq: str = ''
    clipped_inner: str = ''
    close_seq: str = ''
    clipped_width: int = 0
    hl_col_end: int = 0


def _apply_sgr_wrap(result: str, sgr_at_clip_start: Optional[_SGRState]) -> str:
    """
    Apply SGR prefix/suffix around *result*.

    If an SGR state was captured at the first visible character, prefix the result with the
    corresponding SGR sequence and suffix with a reset if any styles are active.
    """
    if sgr_at_clip_start is not None:
        if prefix := _sgr_state_to_sequence(sgr_at_clip_start):
            result = prefix + result
        if _sgr_state_is_active(sgr_at_clip_start):
            result += '\x1b[0m'
    return result


def _process_hyperlink(
    ctx: _ClipContext,
    params: HyperlinkParams,
    match_end: int,
    col: int,
) -> _HyperlinkResult:
    """
    Process an OSC 8 hyperlink unit.

    Finds the matching close sequence, measures the inner text width, and determines whether the
    hyperlink is empty, outside the clip window, or visible (requiring inner-text clipping).
    """
    close_start, close_end = Hyperlink.find_close(ctx.text, match_end)
    if (close_start, close_end) == (-1, -1):
        return _HyperlinkResult(_HyperlinkAction.NO_CLOSE)
    inner_text = ctx.text[match_end:close_start]
    inner_width = width(
        inner_text, control_codes=ctx.control_codes,
        tabsize=ctx.tabsize, ambiguous_width=ctx.ambiguous_width,
    )

    if inner_width == 0:
        return _HyperlinkResult(_HyperlinkAction.EMPTY, close_end=close_end)

    hl_col_end = col + inner_width

    if hl_col_end <= ctx.start or col >= ctx.end:
        return _HyperlinkResult(_HyperlinkAction.OUTSIDE, close_end=close_end,
                                inner_width=inner_width)

    inner_clip_start = max(0, ctx.start - col)
    inner_clip_end = ctx.end - col

    clipped_inner = clip(
        inner_text, inner_clip_start, inner_clip_end,
        fillchar=ctx.fillchar, tabsize=ctx.tabsize,
        ambiguous_width=ctx.ambiguous_width,
        propagate_sgr=False,
        control_codes=ctx.control_codes,
    )

    clipped_width = width(
        clipped_inner, control_codes=ctx.control_codes,
        tabsize=ctx.tabsize, ambiguous_width=ctx.ambiguous_width,
    )

    return _HyperlinkResult(
        _HyperlinkAction.VISIBLE,
        close_end=close_end,
        inner_width=inner_width,
        open_seq=params.make_open(),
        clipped_inner=clipped_inner,
        close_seq=params.make_close(),
        clipped_width=clipped_width,
        hl_col_end=hl_col_end,
    )


# pylint: disable=too-many-locals
def _reconstruct_painter(
    cells: dict[int, tuple[str, int]],
    sequences: list[tuple[int, int, str]],
    start: int,
    end: int,
    fillchar: str,
) -> str:
    """
    Reconstruct the output string from painter's algorithm state.

    Walks columns left-to-right, interleaving escape sequences and cell content, filling gaps with
    *fillchar*.
    """
    # Group and sort sequences by column, preserving insertion order within each.
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
        # Emit any sequences anchored at this column.
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

    # Emit sequences anchored beyond the visible region.
    for c in sorted(seqs_by_col.keys()):
        if c > col_limit:
            for _, seq_text in seqs_by_col[c]:
                parts.append(seq_text)

    return ''.join(parts)


# pylint: disable=too-complex,too-many-locals,too-many-branches,too-many-statements
def _clip_simple(ctx: _ClipContext) -> tuple[str, Optional[_SGRState]]:
    """
    Clip text without cursor movement (simple append-to-output path).

    Returns ``(result, sgr_at_clip_start)``.  The caller applies SGR wrapping.
    """
    # Bind hot-path attributes to locals (LOAD_FAST instead of LOAD_ATTR).
    _text = ctx.text
    _end = ctx.end
    _start = ctx.start
    _propg = ctx.propagate_sgr
    _ambw = ctx.ambiguous_width
    _fillchar = ctx.fillchar
    _tabsize = ctx.tabsize
    _strict = ctx.strict

    output: list[str] = []
    col = 0
    idx = 0
    sgr_at_clip_start = None
    sgr = _SGR_STATE_DEFAULT if _propg else None

    def _mark() -> None:
        nonlocal sgr_at_clip_start
        if _propg and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _emit_tab(col: int) -> int:
        """Expand tab, appending spaces to output list."""
        if _tabsize > 0:
            next_tab = col + (_tabsize - (col % _tabsize))
            while col < next_tab:
                if _start <= col < _end:
                    output.append(' ')
                    _mark()
                col += 1
        else:
            output.append('\t')
        return col

    def _handle_grapheme(grapheme: str, gw: int, col: int) -> None:
        """Emit grapheme to output list based on visibility."""
        if gw == 0:
            if _start <= col < _end:
                output.append(grapheme)
        elif col >= _start and col + gw <= _end:
            output.append(grapheme)
            _mark()
        elif col < _end and col + gw > _start:
            output.append(_fillchar * (min(_end, col + gw) - max(_start, col)))
            _mark()

    while idx < len(_text):
        char = _text[idx]

        # Early exit: past visible region.
        if col >= _end and char not in '\r\x08\t\x1b':
            if sgr_at_clip_start is not None:
                break
            if not _propg:
                next_esc = _text.find('\x1b', idx + 1)
                if next_esc == -1:
                    break
                idx = next_esc
                continue

        if char == '\x1b':
            m = _SEQUENCE_CLASSIFY.match(_text, idx)
            if not m:
                output.append(char)
                idx += 1
                continue

            # SGR: update state, do not emit.
            if m.group('sgr_params') is not None and _propg and sgr is not None:
                sgr = _sgr_state_update(sgr, m.group())
                idx = m.end()
                continue

            # OSC 8 hyperlink.
            if hl_state := HyperlinkParams.parse(m.group()):
                r = _process_hyperlink(ctx, hl_state, m.end(), col)
                if r.action is _HyperlinkAction.NO_CLOSE:
                    output.append(m.group())
                    idx = m.end()
                elif r.action is _HyperlinkAction.EMPTY:
                    idx = r.close_end
                elif r.action is _HyperlinkAction.OUTSIDE:
                    col += r.inner_width
                    idx = r.close_end
                else:
                    output.append(r.open_seq)
                    output.append(r.clipped_inner)
                    output.append(r.close_seq)
                    _mark()
                    col += r.inner_width
                    idx = r.close_end
                continue

            # Indeterminate-effect sequences: raise in strict mode.
            seq = m.group()
            if _strict and INDETERMINATE_EFFECT_SEQUENCE.match(seq):
                raise ValueError(
                    f"Indeterminate cursor sequence at position {idx}, "
                    f"{seq!r}"
                )

            # Any other recognized sequence: preserve as-is.
            output.append(seq)
            idx = m.end()
            continue

        if char == '\t':
            col = _emit_tab(col)
            idx += 1
            continue

        grapheme = next(iter_graphemes(_text, start=idx))
        grapheme_w = width(grapheme, ambiguous_width=_ambw)
        _handle_grapheme(grapheme, grapheme_w, col)
        col += grapheme_w
        idx += len(grapheme)

    return ''.join(output), sgr_at_clip_start


# pylint: disable=too-complex,too-many-locals,too-many-branches,too-many-statements
def _clip_painter(ctx: _ClipContext) -> tuple[str, Optional[_SGRState]]:
    """
    Clip text with cursor movement (painter's algorithm path).

    Returns ``(result, sgr_at_clip_start)``.  The caller applies SGR wrapping.
    """
    # Bind hot-path attributes to locals (LOAD_FAST instead of LOAD_ATTR).
    _text = ctx.text
    _end = ctx.end
    _start = ctx.start
    _propg = ctx.propagate_sgr
    _ambw = ctx.ambiguous_width
    _fillchar = ctx.fillchar
    _tabsize = ctx.tabsize
    _strict = ctx.strict

    cells: dict[int, tuple[str, int]] = {}
    hyperlink_cells: set[int] = set()
    sequences: list[tuple[int, int, str]] = []
    seq_order = 0

    col = 0
    idx = 0
    sgr_at_clip_start = None
    sgr = _SGR_STATE_DEFAULT if _propg else None

    def _mark() -> None:
        nonlocal sgr_at_clip_start
        if _propg and sgr_at_clip_start is None:
            sgr_at_clip_start = sgr

    def _write_cells(s: str, w: int, write_col: int,
                     is_hyperlink: bool = False) -> None:
        """Write *w* cells of text *s* at *write_col*, handling wide-char splitting."""
        for offset in range(w):
            src_col = write_col + offset
            if src_col > 0 and cells.get(src_col - 1, ('', 0))[1] == 2:
                cells[src_col - 1] = (_fillchar, 1)
                hyperlink_cells.discard(src_col - 1)
            if cells.get(src_col, ('', 0))[1] == 2:
                cells[src_col + 1] = (_fillchar, 1)
                hyperlink_cells.discard(src_col + 1)
            cells.pop(src_col, None)
            hyperlink_cells.discard(src_col)
        cells[write_col] = (s, w)
        if is_hyperlink:
            for offset in range(w):
                hyperlink_cells.add(write_col + offset)
        _mark()

    def _append_seq(seq: str, at_col: Optional[int] = None) -> None:
        """Append a zero-width escape sequence anchored at the current column."""
        nonlocal seq_order
        c = col if at_col is None else at_col
        sequences.append((c, seq_order, seq))
        seq_order += 1
        _mark()

    def _emit_tab(col: int) -> int:
        """Expand tab for painter-path."""
        if _tabsize > 0:
            next_tab = col + (_tabsize - (col % _tabsize))
            while col < next_tab:
                if _start <= col < _end:
                    _write_cells(' ', 1, col)
                col += 1
        else:
            _append_seq('\t')
        return col

    def _handle_grapheme(grapheme: str, gw: int, col: int) -> None:
        """Emit grapheme to painter-path based on visibility."""
        if gw == 0:
            if _start <= col < _end:
                _append_seq(grapheme)
        elif col >= _start and col + gw <= _end:
            _write_cells(grapheme, gw, col)
        elif col < _end and col + gw > _start:
            clip_start = max(_start, col)
            for offset in range(min(_end, col + gw) - clip_start):
                _write_cells(_fillchar, 1, clip_start + offset)

    while idx < len(_text):
        char = _text[idx]

        # Early exit: past visible region, SGR captured, no escape ahead.
        # Note: unlike _clip_simple, we cannot skip past non-escape chars when
        # propagate_sgr is False, because cursor movements (\r, \x08, CSI C/D)
        # depend on accurate column tracking and may move back into the visible region.
        if col >= _end and sgr_at_clip_start is not None and char != '\x1b':
            break

        if char == '\x1b':
            m = _SEQUENCE_CLASSIFY.match(_text, idx)
            if not m:
                _append_seq(char)
                idx += 1
                continue

            # SGR: update state, do not emit.
            if m.group('sgr_params') is not None and _propg and sgr is not None:
                sgr = _sgr_state_update(sgr, m.group())
                idx = m.end()
                continue

            # OSC 8 hyperlink.
            if hl_state := HyperlinkParams.parse(m.group()):
                r = _process_hyperlink(ctx, hl_state, m.end(), col)
                if r.action is _HyperlinkAction.NO_CLOSE:
                    _append_seq(m.group())
                    idx = m.end()
                elif r.action is _HyperlinkAction.EMPTY:
                    idx = r.close_end
                elif r.action is _HyperlinkAction.OUTSIDE:
                    col += r.inner_width
                    idx = r.close_end
                else:
                    _append_seq(r.open_seq)
                    _write_cells(r.clipped_inner, r.clipped_width, col,
                                 is_hyperlink=True)
                    col += r.clipped_width
                    _append_seq(r.close_seq, at_col=col)
                    col = r.hl_col_end
                    idx = r.close_end
                continue

            # Indeterminate-effect sequences: raise in strict mode.
            seq = m.group()
            if _strict and INDETERMINATE_EFFECT_SEQUENCE.match(seq):
                raise ValueError(
                    f"Indeterminate cursor sequence at position {idx}, "
                    f"{seq!r}"
                )

            # Horizontal Position Absolute (CSI n G).
            if (hpa_n := m.group('hpa_n')) is not None:
                col = int(hpa_n) - 1 if hpa_n else 0
                idx = m.end()
                continue

            # Cursor Forward (CSI n C).
            if (cforward_n := m.group('cforward_n')) is not None:
                n_forward = int(cforward_n) if cforward_n else 1
                move_end = col + n_forward
                if col < _end and move_end > _start:
                    for i in range(max(col, _start), min(move_end, _end)):
                        _write_cells(_fillchar, 1, i)
                col = move_end
                idx = m.end()
                continue

            # Cursor Backward (CSI n D).
            if (cbackward_n := m.group('cbackward_n')) is not None:
                n_backward = int(cbackward_n) if cbackward_n else 1
                if _strict and n_backward > col:
                    raise ValueError(
                        f"Cursor left movement at position {idx} would move "
                        f"{n_backward} cells left from column {col}, "
                        f"exceeding string start"
                    )
                col = max(0, col - n_backward)
                idx = m.end()
                continue

            # Any other recognized sequence: preserve as-is.
            _append_seq(m.group())
            idx = m.end()
            continue

        # Carriage return.
        if char == '\r':
            col = 0
            idx += 1
            continue

        # Backspace.
        if char == '\x08':
            if col > 0:
                col -= 1
            idx += 1
            continue

        # Tab expansion.
        if char == '\t':
            col = _emit_tab(col)
            idx += 1
            continue

        # Grapheme cluster.
        grapheme = next(iter_graphemes(_text, start=idx))
        grapheme_w = width(grapheme, ambiguous_width=_ambw)
        _handle_grapheme(grapheme, grapheme_w, col)
        col += grapheme_w
        idx += len(grapheme)

    result = _reconstruct_painter(
        cells, sequences, _start, _end, _fillchar,
    )
    return result, sgr_at_clip_start


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
    they have zero display width. If a wide character (width 2) is split at
    either boundary, it is replaced with ``fillchar``.

    TAB characters (``\t``) are expanded to spaces up to the next tab stop,
    controlled by the ``tabsize`` parameter. When cursor movement is detected,
    a "painter's algorithm" is used, cursor movements actively change the write
    position, allowing cursor-left and carriage return to overwrite previously
    written cells. It is assumed that ``text`` begins at column 0.

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
          hyperlink text.  Cursor overwrite is always allowed, with best effort
          results; indeterminate sequences (home, clear, reset, etc.) are
          preserved as zero-width.
        - ``'strict'``: Like ``parse``, but raises :exc:`ValueError` on
          sequences with indeterminate effects (cursor home, clear screen,
          reset, vertical movement, etc.) matching :func:`width` behavior.
          Also raises on out-of-bounds horizontal cursor movement.
        - ``'ignore'``: All control characters are treated as zero-width.
          Cursor movement is not tracked (fastest path).

    :returns: Substring of ``text`` spanning display columns ``(start, end)``,
        with all terminal sequences preserved and wide characters at boundaries
        replaced with ``fillchar``.

    :raises ValueError: If ``control_codes='strict'`` and an indeterminate-effect
        sequence or out-of-bounds cursor movement is encountered.

    SGR (terminal styling) sequences are propagated by default. The result
    begins with any active style and ends with a reset::

        >>> clip('\x1b[1;34mHello world\x1b[0m', 6, 11)
        '\x1b[1;34mworld\x1b[0m'

    Set ``propagate_sgr=False`` to disable this behavior.

    .. versionadded:: 0.3.0

    .. versionchanged:: 0.5.0
       Added ``propagate_sgr`` parameter (default True).

    .. versionchanged:: 0.7.0
       Added ``control_codes`` parameter (default 'parse').
       OSC 8 hyperlink-aware clipping.

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

    # Fast path: printable ASCII only.
    if text.isascii() and text.isprintable():
        return text[start:end]

    # No escape sequences => no SGR tracking needed.
    has_esc = '\x1b' in text
    if propagate_sgr and not has_esc:
        propagate_sgr = False

    # Use painter's algorithm only when cursor movement can overwrite cells.
    fn_clip = _clip_painter if (
        control_codes != 'ignore' and
        ('\x08' in text or '\r' in text or
         (has_esc and bool(_HORIZONTAL_CURSOR_MOVEMENT.search(text))))
    ) else _clip_simple

    ctx = _ClipContext(
        text=text,
        start=start,
        end=end,
        fillchar=fillchar,
        tabsize=tabsize,
        ambiguous_width=ambiguous_width,
        control_codes=control_codes,
        strict=(control_codes == 'strict'),
        propagate_sgr=propagate_sgr,
    )

    return _apply_sgr_wrap(*fn_clip(ctx))
