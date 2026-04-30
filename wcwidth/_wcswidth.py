"""This is a python implementation of wcswidth()."""

import typing

# local
from ._wcwidth import wcwidth
from .bisearch import bisearch
from ._constants import (_EMOJI_ZWJ_SET,
                         _ISC_VIRAMA_SET,
                         _CATEGORY_MC_TABLE,
                         _FITZPATRICK_RANGE,
                         _REGIONAL_INDICATOR_SET)
from .table_vs16 import VS16_NARROW_TO_WIDE
from .table_grapheme import ISC_CONSONANT


def wcswidth(
    pwcs: str,
    n: typing.Union[int, None] = None,
    unicode_version: str = 'auto',
    ambiguous_width: int = 1,
) -> int:
    """
    Given a unicode string, return its printable length on a terminal.

    See :ref:`Specification` for details of cell measurement.

    This implementation differs from Markus Khun's original POSIX C implementation, in that this
    ``wcswidth()`` processes graphemes strings yielded by :func:`wcwidth.iter_graphemes` defined by
    `Unicode Standard Annex #29`_. POSIX wcswidth(3) is not grapheme-aware and does not measure many
    kinds of Emojis or complex scripts correctly.

    :param pwcs: Measure width of given unicode string.
    :param n: When ``n`` is None (default), return the length of the entire
        string, otherwise only the first ``n`` characters are measured.

    :param unicode_version: Ignored. Retained for backwards compatibility.

        .. deprecated:: 0.3.0
           Only the latest Unicode version is now shipped.

    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: The width, in cells, needed to display the first ``n`` characters
        of the unicode string ``pwcs``.  Returns ``-1`` for C0 and C1 control
        characters!

    .. _`Unicode Standard Annex #29`: https://www.unicode.org/reports/tr29/
    """
    # pylint: disable=unused-argument,too-many-locals,too-many-statements
    # pylint: disable=too-complex,too-many-branches,duplicate-code
    # This function intentionally kept long without delegating functions to reduce function calls in
    # "hot path", the overhead per-character adds up.

    # Fast path: pure ASCII printable strings are always width == length
    if n is None and pwcs.isascii() and pwcs.isprintable():
        return len(pwcs)

    # Select wcwidth call pattern for best lru_cache performance:
    # - ambiguous_width=1 (default): single-arg calls share cache with direct wcwidth() calls
    # - ambiguous_width=2: full positional args needed (results differ, separate cache is correct)
    _wcwidth = wcwidth if ambiguous_width == 1 else lambda c: wcwidth(c, 'auto', ambiguous_width)

    end = len(pwcs) if n is None else n
    total_width = 0
    idx = 0
    last_measured_idx = -2  # Track index of last measured char for VS16
    last_measured_ucs = -1  # Codepoint of last measured char (for deferred emoji check)
    last_was_virama = False  # Virama conjunct formation state
    conjunct_pending = False  # Deferred +1 for bare conjuncts (no trailing Mc)
    while idx < end:
        char = pwcs[idx]
        ucs = ord(char)
        if ucs == 0x200D:
            if last_was_virama:
                # ZWJ after virama requests explicit half-form rendering but
                # does not change cell count -- consume ZWJ only, let the next
                # consonant be handled by the virama conjunct rule.
                idx += 1
            elif idx + 1 < end:
                # Emoji ZWJ: skip next character unconditionally.
                idx += 2
                last_was_virama = False
            else:
                idx += 1
                last_was_virama = False
            continue
        if ucs == 0xFE0F and last_measured_idx >= 0:
            # VS16 following a measured character: add 1 if that character is
            # known to be converted from narrow to wide by VS16.
            total_width += bisearch(ord(pwcs[last_measured_idx]), VS16_NARROW_TO_WIDE["9.0.0"])
            last_measured_idx = -2  # Prevent double application
            # VS16 preserves emoji context: last_measured_ucs stays as the base
            idx += 1
            continue
        # Regional Indicator & Fitzpatrick: both above BMP (U+1F1E6+)
        if ucs > 0xFFFF:
            if ucs in _REGIONAL_INDICATOR_SET:
                # Lazy RI pairing: count preceding consecutive RIs only when the last one is
                # received, because RI's are received so rarely its better than per-loop tracking of
                # 'last char was an RI'.
                ri_before = 0
                j = idx - 1
                while j >= 0 and ord(pwcs[j]) in _REGIONAL_INDICATOR_SET:
                    ri_before += 1
                    j -= 1
                if ri_before % 2 == 1:
                    # Second RI in pair: contributes 0 (pair = one 2-cell flag) using an even-or-odd
                    # check to determine, 'CAUS' would be two flags, but 'CAU' would be 1 flag
                    # and wide 'U'.
                    idx += 1
                    last_measured_ucs = ucs
                    continue
                # First or unpaired RI: measured normally (width 2 from table)
            # Fitzpatrick modifier: zero-width when following emoji base
            elif (_FITZPATRICK_RANGE[0] <= ucs <= _FITZPATRICK_RANGE[1]
                  and last_measured_ucs in _EMOJI_ZWJ_SET):
                idx += 1
                continue
        # Virama conjunct formation: consonant following virama contributes 0 width.
        # See https://www.unicode.org/reports/tr44/#Indic_Syllabic_Category
        if last_was_virama and bisearch(ucs, ISC_CONSONANT):
            last_measured_idx = idx
            last_measured_ucs = ucs
            last_was_virama = False
            conjunct_pending = True
            idx += 1
            continue
        wcw = _wcwidth(char)
        if wcw < 0:
            # early return -1 on C0 and C1 control characters
            return wcw
        if wcw > 0:
            if conjunct_pending:
                total_width += 1
                conjunct_pending = False
            last_measured_idx = idx
            last_measured_ucs = ucs
            last_was_virama = False
        elif last_measured_idx >= 0 and bisearch(ucs, _CATEGORY_MC_TABLE):
            # Spacing Combining Mark (Mc) following a base character adds 1
            wcw = 1
            last_measured_idx = -2
            last_was_virama = False
            conjunct_pending = False
        else:
            last_was_virama = ucs in _ISC_VIRAMA_SET
        total_width += wcw
        idx += 1
    if conjunct_pending:
        total_width += 1
    return total_width
