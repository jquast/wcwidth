"""This is a python implementation of wcswidth()."""

from __future__ import annotations

from typing import Callable, Optional

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


class GraphemeMeasurer:
    """
    Stateful measurer for grapheme-aware character width.

    Encapsulates the lookbehind state that must be threaded through
    sequential per-character measurements by :meth:`measure_at`.

    Callers that interleave escape sequences or control codes between
    characters should call :meth:`reset_adjacency` to prevent VS16
    from applying across the gap.
    """

    def __init__(self, text: str, end: int, wcwidth_fn: Callable[[str], int]) -> None:
        """Class initializer."""
        self._text = text
        self._end = end
        self._wcwidth_fn = wcwidth_fn
        self._last_measured_idx = -2
        self._last_measured_ucs = -1
        self._last_was_virama = False
        self.conjunct_pending = False

    # pylint: disable=too-complex,too-many-branches
    def measure_at(self, idx: int) -> tuple[int, int]:
        """
        Process character at ``text[idx]`` and return ``(next_idx, width)``.

        Handles ZWJ, VS16, Regional Indicators, Fitzpatrick modifiers, virama
        conjunct formation, Mc spacing marks, and standard ``wcwidth`` measurement.

        ``width`` is ``-1`` for C0/C1 control characters (caller must handle).
        Callers that never pass C0/C1 characters will always receive ``width >= 0``.
        """
        char = self._text[idx]
        ucs = ord(char)

        # ZWJ (U+200D)
        if ucs == 0x200D:
            if self._last_was_virama:
                return (idx + 1, 0)
            if idx + 1 < self._end:
                # Emoji ZWJ: skip next character unconditionally.
                # Preserve _last_measured_idx so VS16 checks the emoji base
                # (narrow bases get +1, wide bases are already 2 cells).
                self._last_was_virama = False
                return (idx + 2, 0)
            self._last_was_virama = False
            return (idx + 1, 0)

        # VS16 (U+FE0F): converts preceding narrow character to wide.
        if ucs == 0xFE0F and self._last_measured_idx >= 0:
            vs_width = bisearch(
                ord(self._text[self._last_measured_idx]),
                VS16_NARROW_TO_WIDE['9.0.0'],
            )
            # Prevent double application; preserve emoji context (_last_measured_ucs stays)
            self._last_measured_idx = -2
            return (idx + 1, vs_width)

        # Regional Indicator & Fitzpatrick (both above BMP)
        if ucs > 0xFFFF:
            if ucs in _REGIONAL_INDICATOR_SET:
                # Lazy RI pairing: count preceding consecutive RIs
                ri_before = 0
                j = idx - 1
                while j >= 0 and ord(self._text[j]) in _REGIONAL_INDICATOR_SET:
                    ri_before += 1
                    j -= 1
                if ri_before % 2 == 1:
                    # Second RI in pair: zero width (pair = one 2-cell flag)
                    self._last_measured_ucs = ucs
                    return (idx + 1, 0)
            # Fitzpatrick modifier: zero-width when following emoji base
            elif (_FITZPATRICK_RANGE[0] <= ucs <= _FITZPATRICK_RANGE[1]
                  and self._last_measured_ucs in _EMOJI_ZWJ_SET):
                return (idx + 1, 0)

        # Virama conjunct formation
        if self._last_was_virama and bisearch(ucs, ISC_CONSONANT):
            self._last_measured_idx = idx
            self._last_measured_ucs = ucs
            self._last_was_virama = False
            self.conjunct_pending = True
            return (idx + 1, 0)

        # Normal character: measure with wcwidth
        w = self._wcwidth_fn(char)
        if w < 0:
            # C0/C1 control character (returns -1: caller should handle!)
            return (idx + 1, -1)
        if w > 0:
            extra = 1 if self.conjunct_pending else 0
            self._last_measured_idx = idx
            self._last_measured_ucs = ucs
            self._last_was_virama = False
            self.conjunct_pending = False
            return (idx + 1, w + extra)
        if self._last_measured_idx >= 0 and bisearch(ucs, _CATEGORY_MC_TABLE):
            # Spacing Combining Mark (Mc) following a base character adds 1
            self._last_measured_idx = -2
            self._last_was_virama = False
            self.conjunct_pending = False
            return (idx + 1, 1)
        self._last_was_virama = ucs in _ISC_VIRAMA_SET
        return (idx + 1, 0)

    def reset_adjacency(self) -> None:
        """
        Break VS16/Fitzpatrick adjacency.

        Call after processing escape sequences or control codes to prevent VS16 and Fitzpatrick
        lookbehind from applying across the gap.
        """
        self._last_measured_idx = -2
        self._last_measured_ucs = -1


def wcswidth(
    pwcs: str,
    n: Optional[int] = None,
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

    # Select wcwidth call pattern for best lru_cache performance
    _wcwidth = wcwidth if ambiguous_width == 1 else lambda c: wcwidth(c, 'auto', ambiguous_width)

    end = len(pwcs) if n is None else n
    total_width = 0
    idx = 0
    measurer = GraphemeMeasurer(pwcs, end, _wcwidth)
    while idx < end:
        idx, w = measurer.measure_at(idx)
        if w < 0:
            return -1
        total_width += w
    if measurer.conjunct_pending:
        total_width += 1
    return total_width
