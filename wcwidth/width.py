"""This is a high-level width() supporting terminal output."""

from typing import Literal

# local
from .wcwidth import wcwidth
from .bisearch import bisearch
from .wcswidth import wcswidth
from ._constants import (_EMOJI_ZWJ_SET,
                         _ISC_VIRAMA_SET,
                         _CATEGORY_MC_TABLE,
                         _FITZPATRICK_RANGE,
                         _REGIONAL_INDICATOR_SET)
from .table_vs16 import VS16_NARROW_TO_WIDE
from .text_sizing import TextSizing, TextSizingParams
from .control_codes import ILLEGAL_CTRL, VERTICAL_CTRL, HORIZONTAL_CTRL, ZERO_WIDTH_CTRL
from .table_grapheme import ISC_CONSONANT
from .escape_sequences import _SEQUENCE_CLASSIFY, INDETERMINATE_EFFECT_SEQUENCE, strip_sequences

# In 'parse' mode, strings longer than this are checked for cursor-movement
# controls (BS, TAB, CR, cursor sequences); when absent, mode downgrades to
# 'ignore' to skip character-by-character parsing. The detection scan cost is
# negligible for long strings but wasted on short ones like labels or headings.
_WIDTH_FAST_PATH_MIN_LEN = 20

# Translation table to strip C0/C1 control characters for fast 'ignore' mode.
_CONTROL_CHAR_TABLE = str.maketrans('', '', (
    ''.join(chr(c) for c in range(0x00, 0x20)) +   # C0: NUL through US (including tab)
    '\x7f' +                                       # DEL
    ''.join(chr(c) for c in range(0x80, 0xa0))     # C1: U+0080-U+009F
))


def _width_ignored_codes(text: str, ambiguous_width: int = 1) -> int:
    """
    Fast path for width() with control_codes='ignore'.

    Strips escape sequences and control characters, then measures remaining text.
    """
    return wcswidth(
        strip_sequences(text).translate(_CONTROL_CHAR_TABLE),
        ambiguous_width=ambiguous_width
    )


def width(
    text: str,
    *,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    tabsize: int = 8,
    ambiguous_width: int = 1,
) -> int:
    r"""
    Return printable width of text containing many kinds of control codes and sequences.

    Unlike :func:`wcswidth`, this function handles most control characters and many popular terminal
    output sequences.  Never returns -1.

    :param text: String to measure.
    :param control_codes: How to handle control characters and sequences:

        - ``'parse'`` (default): Track horizontal cursor movement like BS ``\b``, CR ``\r``, TAB
          ``\t``, cursor left and right movement sequences.  Vertical movement (LF, VT, FF) and
          indeterminate terminal sequences are zero-width. OSC 66 Kitty Text Sizing protocol, OSC 8
          Hyperlink, and many other kinds of output sequences are parsed for displayed measurements.
        - ``'strict'``: Like parse, but raises :exc:`ValueError` on control characters with
          indeterminate results of the screen or cursor, like clear or vertical movement. Generally,
          these should be handled with a virtual terminal emulator (like 'pyte').
        - ``'ignore'``: All C0 and C1 control characters and escape sequences are measured as
          width 0. This is the fastest measurement for text already filtered or known not to contain
          any kinds of control codes or sequences. TAB ``\t`` is zero-width; to ensure
          tab expansion, pre-process text using :func:`str.expandtabs`.

    :param tabsize: Tab stop width for ``'parse'`` and ``'strict'`` modes. Default is 8.
        Must be positive. Has no effect when ``control_codes='ignore'``.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: Maximum cursor position reached, "extent", accounting for cursor movement sequences
        present in ``text`` according to given parameters.  This represents the rightmost column the
        cursor reaches.  Always a non-negative integer.

    :raises ValueError: If ``control_codes='strict'`` and control characters with indeterminate
        effects, such as vertical movement or clear sequences are encountered, or on unexpected
        C0 or C1 control code. Also raised when ``control_codes`` is not one of the valid values.

    .. versionadded:: 0.3.0

    Examples::

        >>> width('hello')
        5
        >>> width('コンニチハ')
        10
        >>> width('\x1b[31mred\x1b[0m')
        3
        >>> width('\x1b[31mred\x1b[0m', control_codes='ignore')  # same result (ignored)
        3
        >>> width('123\b4')     # backspace overwrites previous cell (outputs '124')
        3
        >>> width('abc\t')      # tab caused cursor to move to column 8
        8
        >>> width('1\x1b[10C')  # '1' + cursor right 10, cursor ends on column 11
        11
        >>> width('1\x1b[10C', control_codes='ignore')   # faster but wrong in this case
        1
    """
    # pylint: disable=too-complex,too-many-branches,too-many-statements,too-many-locals
    # This could be broken into sub-functions (#1, #3, and #6 especially), but for reduced overhead
    # in consideration of this function a likely "hot path", they are inline, breaking many pylint
    # complexity rules.

    # Fast path for ASCII printable (no tabs, escapes, or control chars)
    if text.isascii() and text.isprintable():
        return len(text)

    # Fast parse: if no horizontal cursor movements are possible, switch to 'ignore' mode.
    # Only check longer strings - the detection overhead hurts short string performance.
    if control_codes == 'parse' and len(text) > _WIDTH_FAST_PATH_MIN_LEN:
        # Check for cursor-affecting control characters
        if '\b' not in text and '\t' not in text and '\r' not in text:
            # Check for escape sequences that can't be ignored, if present
            if '\x1b' not in text or not _SEQUENCE_CLASSIFY.search(text):
                control_codes = 'ignore'

    # Fast path for ignore mode, useful if you know the text is already free of control codes
    if control_codes == 'ignore':
        return _width_ignored_codes(text, ambiguous_width)

    strict = control_codes == 'strict'
    # Track absolute positions: tab stops need modulo on absolute column, CR resets to 0.
    # Initialize max_extent to 0 so backward movement (CR, BS) won't yield negative width.
    current_col = 0
    max_extent = 0
    idx = 0
    last_measured_idx = -2  # Track index of last measured char for VS16; -2 can never match idx-1
    last_measured_ucs = -1  # Codepoint of last measured char (for deferred emoji check)
    last_was_virama = False  # Virama conjunct formation state
    conjunct_pending = False  # Deferred +1 for bare conjuncts (no trailing Mc)
    text_len = len(text)

    # Select wcwidth call pattern for best lru_cache performance:
    # - ambiguous_width=1 (default): single-arg calls share cache with direct wcwidth() calls
    # - ambiguous_width=2: full positional args needed (results differ, separate cache is correct)
    _wcwidth = wcwidth if ambiguous_width == 1 else lambda c: wcwidth(c, 'auto', ambiguous_width)

    while idx < text_len:
        char = text[idx]

        # 1. ESC sequences
        if char == '\x1b':
            m = _SEQUENCE_CLASSIFY.match(text, idx)
            if not m:
                # 1a. Errant ESC or unknown sequence: only the first character is zero-width
                idx += 1
            else:
                seq = m.group()
                if strict and INDETERMINATE_EFFECT_SEQUENCE.match(seq):
                    raise ValueError(f"Indeterminate cursor sequence at position {idx}, {seq!r}")

                # 2b. cursor forward, backward, and OSC 66 text sizing width
                if (cforward_n := m.group('cforward_n')) is not None:
                    current_col += int(cforward_n) if cforward_n else 1
                elif (cbackward_n := m.group('cbackward_n')) is not None:
                    current_col = max(0, current_col - (int(cbackward_n) if cbackward_n else 1))
                elif (ts_meta := m.group('ts_meta')) is not None:
                    ts_text = m.group('ts_text')
                    ts_term = m.group('ts_term')
                    assert ts_text is not None and ts_term is not None
                    text_size = TextSizing(
                        TextSizingParams.from_params(ts_meta, control_codes=control_codes),
                        ts_text, ts_term)
                    current_col += text_size.display_width(ambiguous_width)
                # 2c. SGR and other zero-width sequences -- no column advance
                idx = m.end()
            max_extent = max(max_extent, current_col)
            continue

        # 2. Vertical or Illegal control characters zero width or error when 'strict'
        if char in ILLEGAL_CTRL:
            if strict:
                raise ValueError(f"Illegal control character {ord(char):#x} at position {idx}")
            idx += 1
            continue

        if char in VERTICAL_CTRL:
            if strict:
                raise ValueError(f"Vertical movement character {ord(char):#x} at position {idx}")
            idx += 1
            continue

        # 3. Horizontal movement characters
        if char in HORIZONTAL_CTRL:
            if char == '\x09' and tabsize > 0:  # Tab
                current_col += tabsize - (current_col % tabsize)
            elif char == '\x08':  # Backspace
                if current_col > 0:
                    current_col -= 1
            elif char == '\x0d':  # Carriage return
                current_col = 0
            max_extent = max(max_extent, current_col)
            idx += 1
            continue

        # 4. Zero-Width Joiner (ZWJ)
        if char == '\u200D':
            if last_was_virama:
                # ZWJ after virama requests explicit half-form rendering but
                # does not change cell count — consume ZWJ only, let the next
                # consonant be handled by the virama conjunct rule.
                idx += 1
            elif idx + 1 < text_len:
                # Emoji ZWJ: skip next character unconditionally.
                idx += 2
                last_was_virama = False
            else:
                idx += 1
                last_was_virama = False
            continue

        # 5. Other zero-width characters (control chars)
        if char in ZERO_WIDTH_CTRL:
            idx += 1
            continue

        ucs = ord(char)

        # 6. VS16: converts preceding narrow character to wide
        if ucs == 0xFE0F:
            if last_measured_idx == idx - 1:
                if bisearch(ord(text[last_measured_idx]), VS16_NARROW_TO_WIDE["9.0.0"]):
                    current_col += 1
                    max_extent = max(max_extent, current_col)
            # VS16 preserves emoji context: last_measured_ucs stays as the base
            idx += 1
            continue

        # 6b. Regional Indicator & Fitzpatrick: both above BMP (U+1F1E6+)
        if ucs > 0xFFFF:
            if ucs in _REGIONAL_INDICATOR_SET:
                # Lazy RI pairing: count preceding consecutive RIs
                ri_before = 0
                j = idx - 1
                while j >= 0 and ord(text[j]) in _REGIONAL_INDICATOR_SET:
                    ri_before += 1
                    j -= 1
                if ri_before % 2 == 1:
                    last_measured_ucs = ucs
                    idx += 1
                    continue
            # 6c. Fitzpatrick modifier: zero-width when following emoji base
            elif (_FITZPATRICK_RANGE[0] <= ucs <= _FITZPATRICK_RANGE[1]
                  and last_measured_ucs in _EMOJI_ZWJ_SET):
                idx += 1
                continue

        # 7. Virama conjunct formation: consonant following virama contributes 0 width.
        # See https://www.unicode.org/reports/tr44/#Indic_Syllabic_Category
        if last_was_virama and bisearch(ucs, ISC_CONSONANT):
            last_measured_idx = idx
            last_measured_ucs = ucs
            last_was_virama = False
            conjunct_pending = True
            idx += 1
            continue

        # 8. Normal characters: measure with wcwidth
        w = _wcwidth(char)
        if w > 0:
            if conjunct_pending:
                current_col += 1
                conjunct_pending = False
            current_col += w
            max_extent = max(max_extent, current_col)
            last_measured_idx = idx
            last_measured_ucs = ucs
            last_was_virama = False
        elif last_measured_idx >= 0 and bisearch(ucs, _CATEGORY_MC_TABLE):
            # Spacing Combining Mark (Mc) following a base character adds 1
            current_col += 1
            max_extent = max(max_extent, current_col)
            last_measured_idx = -2
            last_was_virama = False
            conjunct_pending = False
        else:
            last_was_virama = ucs in _ISC_VIRAMA_SET
        idx += 1

    if conjunct_pending:
        current_col += 1
        max_extent = max(max_extent, current_col)
    return max_extent
