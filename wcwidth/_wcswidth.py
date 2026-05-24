"""This is a python implementation of wcswidth()."""

from __future__ import annotations

from typing import Optional

# local
from ._wcwidth import wcwidth
from .bisearch import bisearch
from ._constants import (_EMOJI_ZWJ_SET,
                         _ISC_VIRAMA_SET,
                         _CATEGORY_MC_TABLE,
                         _FITZPATRICK_RANGE,
                         _REGIONAL_INDICATOR_SET,
                         _resolve_terminal,
                         _get_term_overrides)
from .table_vs16 import VS16_NARROW_TO_WIDE
from .table_grapheme import ISC_CONSONANT, GRAPHEME_EXTEND
from . import table_grapheme_overrides


def _scan_zwj_cluster_end(text: str, start: int, end: int) -> int:
    """
    Scan forward from *start* (base character) to end of a ZWJ grapheme cluster.

    Follows the UAX #29 GB11 pattern (ExtPict Extend* ZWJ x ExtPict) chained repeatedly until no
    more ZWJ joins are found.
    """
    idx = start + 1
    # Skip Extend characters (Fitzpatrick modifiers, etc.) before first ZWJ
    while idx < end and bisearch(ord(text[idx]), GRAPHEME_EXTEND):
        idx += 1
    # Follow ZWJ chains
    while idx < end:
        if ord(text[idx]) != 0x200D:
            break
        idx += 1
        # GB11: \p{ExtPict} Extend* ZWJ × \p{ExtPict}
        # Extend modifiers (VS16, Fitzpatrick skin tones, etc.) attach to
        # the ExtPict *before* the ZWJ, not after it.  After ZWJ the next
        # codepoint is always an ExtPict directly — no Extend skip needed.
        if idx < end and ord(text[idx]) in _EMOJI_ZWJ_SET:
            idx += 1
            # Skip trailing Extend (VS16, etc.) after ExtPict before next ZWJ
            while idx < end and bisearch(ord(text[idx]), GRAPHEME_EXTEND):
                idx += 1
            continue
        break
    return idx


def wcswidth(
    pwcs: str,
    n: Optional[int] = None,
    unicode_version: str = 'auto',
    ambiguous_width: int = 1,
    term_program: Optional[str] = None,
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
    :param term_program: Terminal software identifier for table correction.  When ``None``
        (default), the ``TERM_PROGRAM`` environment variable is used when set. Accepts a
        canonical terminal name, ``TERM_PROGRAM`` value, or ``XTVERSION`` query result.
        Set to ``""`` to disable override lookup entirely.
    :returns: The width, in cells, needed to display the first ``n`` characters
        of the unicode string ``pwcs``.  Returns ``-1`` for C0 and C1 control
        characters!

    .. _`Unicode Standard Annex #29`: https://www.unicode.org/reports/tr29/
    """
    # pylint: disable=unused-argument,too-many-locals,too-many-statements
    # pylint: disable=too-complex,too-many-branches,duplicate-code
    # This function intentionally keeps all logic inline for performance.

    # Fast path: pure ASCII printable strings are always width == length
    if n is None and pwcs.isascii() and pwcs.isprintable():
        return len(pwcs)

    # Resolve terminal software for override lookup
    term_canonical = _resolve_terminal(term_program)
    overrides = _get_term_overrides(term_canonical) if term_canonical else None
    if overrides is not None:
        _narrower, _wider, _vs16_narrower, _vs16_wider, _vs15_narrower, _vs15_wider = overrides
    else:
        _narrower = _wider = _vs16_narrower = _vs16_wider = ()
        _vs15_narrower = _vs15_wider = ()

    # Load grapheme overrides (multi-codepoint ZWJ sequences) for this terminal
    _grapheme_overrides = table_grapheme_overrides.get(term_canonical) if term_canonical else None

    # Select wcwidth call pattern for best lru_cache performance
    _wcwidth = wcwidth if ambiguous_width == 1 else lambda c: wcwidth(c, 'auto', ambiguous_width)

    end = len(pwcs) if n is None else n
    total_width = 0
    idx = 0

    # grapheme-clustering state
    last_measured_idx = -2
    last_measured_ucs = -1
    last_measured_w = 0
    last_was_virama = False
    conjunct_pending = False

    while idx < end:
        char = pwcs[idx]
        ucs = ord(char)

        # ZWJ (U+200D)
        if ucs == 0x200D:
            if last_was_virama:
                idx += 1
            elif idx + 1 < end:
                # Check for terminal grapheme override when base char is ExtPict/RI
                if (_grapheme_overrides is not None
                        and last_measured_idx >= 0
                        and last_measured_ucs in _EMOJI_ZWJ_SET):
                    cluster_end = _scan_zwj_cluster_end(pwcs, last_measured_idx, end)
                    cluster = pwcs[last_measured_idx:cluster_end]
                    override_w = _grapheme_overrides.get(cluster)
                    if override_w is not None:
                        total_width += (override_w - last_measured_w)
                        last_measured_idx = -2
                        last_measured_ucs = -1
                        last_measured_w = 0
                        last_was_virama = False
                        idx = cluster_end
                        continue
                last_was_virama = False
                idx += 2
            else:
                last_was_virama = False
                idx += 1
            continue

        # VS16 (U+FE0F): converts preceding narrow character to wide.
        if ucs == 0xFE0F and last_measured_idx >= 0:
            base_ucs = ord(pwcs[last_measured_idx])
            vs16_wide = bisearch(base_ucs, VS16_NARROW_TO_WIDE['9.0.0'])
            if _vs16_narrower and bisearch(base_ucs, _vs16_narrower):
                vs16_wide = False
            if _vs16_wider and bisearch(base_ucs, _vs16_wider):
                vs16_wide = True
            if vs16_wide:
                total_width += 1
            last_measured_idx = -2  # prevent double application
            idx += 1
            continue

        # VS15 (U+FE0E): text variation selector, requests narrow presentation.
        if ucs == 0xFE0E and last_measured_idx >= 0:
            base_ucs = ord(pwcs[last_measured_idx])
            if _vs15_narrower and bisearch(base_ucs, _vs15_narrower):
                if last_measured_w == 2:
                    total_width -= 1
            elif _vs15_wider and bisearch(base_ucs, _vs15_wider):
                if last_measured_w == 1:
                    total_width += 1
            last_measured_idx = -2
            idx += 1
            continue

        # Regional Indicator & Fitzpatrick (both above BMP)
        if ucs > 0xFFFF:
            if ucs in _REGIONAL_INDICATOR_SET:
                ri_before = 0
                j = idx - 1
                while j >= 0 and ord(pwcs[j]) in _REGIONAL_INDICATOR_SET:
                    ri_before += 1
                    j -= 1
                if ri_before % 2 == 1:
                    last_measured_ucs = ucs
                    idx += 1
                    continue
            elif (_FITZPATRICK_RANGE[0] <= ucs <= _FITZPATRICK_RANGE[1]
                  and last_measured_ucs in _EMOJI_ZWJ_SET):
                idx += 1
                continue

        # Virama conjunct formation
        if last_was_virama and bisearch(ucs, ISC_CONSONANT):
            last_measured_idx = idx
            last_measured_ucs = ucs
            last_was_virama = False
            conjunct_pending = True
            idx += 1
            continue

        # Normal character: measure with wcwidth
        w = _wcwidth(char)
        if w < 0:
            # C0/C1 control character
            return -1
        # Apply single-codepoint terminal overrides (pre-merged tuples)
        if w == 2 and _narrower and bisearch(ucs, _narrower):
            w = 1
        elif w == 1 and _wider and bisearch(ucs, _wider):
            w = 2
        if w > 0:
            if conjunct_pending:
                total_width += 1
                conjunct_pending = False
            total_width += w
            last_measured_idx = idx
            last_measured_ucs = ucs
            last_measured_w = w
            last_was_virama = False
        elif last_measured_idx >= 0 and bisearch(ucs, _CATEGORY_MC_TABLE):
            # Spacing Combining Mark (Mc) following a base character adds 1
            total_width += 1
            last_measured_idx = -2
            last_was_virama = False
            conjunct_pending = False
        else:
            last_was_virama = ucs in _ISC_VIRAMA_SET
        idx += 1

    if conjunct_pending:
        total_width += 1
    return total_width
