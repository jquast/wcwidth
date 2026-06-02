"""Shared data tables and constants for wcwidth.py, _wcwidth.py, and _wcswidth.py."""
from __future__ import annotations

# std imports
import os
from enum import IntEnum
from functools import lru_cache

from typing import Tuple, NamedTuple

# local
from .table_mc import CATEGORY_MC
from .table_wide import WIDE_EASTASIAN
from .table_zero import ZERO_WIDTH
from .table_grapheme import EXTENDED_PICTOGRAPHIC, GRAPHEME_REGIONAL_INDICATOR
from .table_ambiguous import AMBIGUOUS_EASTASIAN
from .unicode_versions import list_versions
from .table_term_programs import ALIASES, KNOWN_TERMINALS

_RangeTuple = Tuple[Tuple[int, int], ...]


class _GraphemeState(IntEnum):
    """Track VS/ZWJ clustering state for base character."""
    #: No base character established yet (initial state, or reset after cursor movement).
    NO_BASE = -1

    #: VS15 (U+FE0E) was applied: no further VS valid.
    VS15_APPLIED = -2

    #: VS16 (U+FE0F) was applied: blocks another VS16 but allows trailing VS15.
    VS16_APPLIED = -3

    #: ZWJ consumed, base char not VS16'd: VS16 may still connect across ZWJ.
    #: Example: ``"\\u263A\\u200Da\\uFE0F"`` (smiley + ZWJ + 'a' + VS16) = 2.
    ZWJ_SKIP_VS16_OPEN = -4

    #: ZWJ consumed, base char already VS16'd: block VS16 to prevent double-widen.
    #: Example: ``"\\u263A\\uFE0F\\u200Dx\\uFE0F"`` (smiley+VS16 + ZWJ + 'x' + VS16) = 2.
    ZWJ_SKIP_VS16_BLOCKED = -5


__all__ = (
    "_REGIONAL_INDICATOR_SET",
    "_ISC_VIRAMA_SET",
    "_LATEST_VERSION",
    "_CATEGORY_MC_TABLE",
    "_EMOJI_ZWJ_SET",
    "_FITZPATRICK_RANGE",
    "_ZERO_WIDTH_TABLE",
    "_WIDE_EASTASIAN_TABLE",
    "_AMBIGUOUS_TABLE",
    "resolve_terminal",
    "get_term_overrides",
    "list_term_programs",
)

_REGIONAL_INDICATOR_SET = frozenset(
    range(GRAPHEME_REGIONAL_INDICATOR[0][0], GRAPHEME_REGIONAL_INDICATOR[0][1] + 1)
)
_ISC_VIRAMA_SET = frozenset((
    0x094D,   # DEVANAGARI SIGN VIRAMA
    0x09CD,   # BENGALI SIGN VIRAMA
    0x0A4D,   # GURMUKHI SIGN VIRAMA
    0x0ACD,   # GUJARATI SIGN VIRAMA
    0x0B4D,   # ORIYA SIGN VIRAMA
    0x0BCD,   # TAMIL SIGN VIRAMA
    0x0C4D,   # TELUGU SIGN VIRAMA
    0x0CCD,   # KANNADA SIGN VIRAMA
    0x0D4D,   # MALAYALAM SIGN VIRAMA
    0x0DCA,   # SINHALA SIGN AL-LAKUNA
    0x1B44,   # BALINESE ADEG ADEG
    0xA806,   # SYLOTI NAGRI SIGN HASANTA
    0xA8C4,   # SAURASHTRA SIGN VIRAMA
    0xA9C0,   # JAVANESE PANGKON
    0x11046,  # BRAHMI VIRAMA
    0x110B9,  # KAITHI SIGN VIRAMA
    0x111C0,  # SHARADA SIGN VIRAMA
    0x11235,  # KHOJKI SIGN VIRAMA
    0x1134D,  # GRANTHA SIGN VIRAMA
    0x11442,  # NEWA SIGN VIRAMA
    0x114C2,  # TIRHUTA SIGN VIRAMA
    0x115BF,  # SIDDHAM SIGN VIRAMA
    0x1163F,  # MODI SIGN VIRAMA
    0x116B6,  # TAKRI SIGN VIRAMA
    0x11839,  # DOGRA SIGN VIRAMA
    0x119E0,  # NANDINAGARI SIGN VIRAMA
    0x11C3F,  # BHAIKSUKI SIGN VIRAMA
))
# pylint: disable=invalid-name
_LATEST_VERSION = list_versions()[-1]
_CATEGORY_MC_TABLE = CATEGORY_MC[_LATEST_VERSION]
_EMOJI_ZWJ_SET = frozenset(
    cp for lo, hi in EXTENDED_PICTOGRAPHIC for cp in range(lo, hi + 1)
) | _REGIONAL_INDICATOR_SET
_FITZPATRICK_RANGE = (0x1F3FB, 0x1F3FF)

_ZERO_WIDTH_TABLE = ZERO_WIDTH[_LATEST_VERSION]
_WIDE_EASTASIAN_TABLE = WIDE_EASTASIAN[_LATEST_VERSION]
_AMBIGUOUS_TABLE = AMBIGUOUS_EASTASIAN[_LATEST_VERSION]

# Canonical terminal names and TERM/TERM_PROGRAM aliases are imported
# from the generated table_term_programs module.


def list_term_programs() -> tuple[str, ...]:
    """
    Return all recognized values for the ``term_program`` argument.

    Includes canonical terminal names and their TERM/TERM_PROGRAM aliases.

    .. versionadded:: 0.8.0
    """
    return tuple(sorted(KNOWN_TERMINALS | ALIASES.keys()))


@lru_cache(maxsize=1)
def _load_single_cp_tables() -> dict[str, dict[str, dict[str, _RangeTuple]]]:
    """Lazy-load single-codepoint terminal override tables (excludes graphemes)."""
    # pylint: disable=import-outside-toplevel
    # local
    from .table_overrides import (SFZ_OVERRIDES,
                                  SRI_OVERRIDES,
                                  VS15_OVERRIDES,
                                  VS16_OVERRIDES,
                                  WIDE_OVERRIDES)

    # pylint: enable=import-outside-toplevel
    return {
        'wide': WIDE_OVERRIDES,
        'sri': SRI_OVERRIDES,
        'sfz': SFZ_OVERRIDES,
        'vs16': VS16_OVERRIDES,
        'vs15': VS15_OVERRIDES,
    }


def _merge_ranges(*tuples: _RangeTuple) -> _RangeTuple:
    """Merge multiple sorted range tuples into one sorted, non-overlapping tuple."""
    all_ranges: list[tuple[int, int]] = []
    for t in tuples:
        all_ranges.extend(t)
    if not all_ranges:
        return ()
    all_ranges.sort(key=lambda r: r[0])
    merged = [all_ranges[0]]
    for lo, hi in all_ranges[1:]:
        _, prev_hi = merged[-1]
        if lo <= prev_hi:
            merged[-1] = (merged[-1][0], max(prev_hi, hi))
        else:
            merged.append((lo, hi))
    return tuple(merged)


class TerminalOverrides(NamedTuple):
    """Pre-merged override range tuples for a single terminal."""

    narrower: _RangeTuple
    vs16_narrower: _RangeTuple
    vs16_wider: _RangeTuple
    vs15_wider: _RangeTuple

_EMPTY_OVERRIDES = TerminalOverrides((), (), (), ())


@lru_cache(maxsize=32)
def get_term_overrides(term_canonical: str | None) -> TerminalOverrides:
    """Return a TerminalOverrides, with all empty tuples when there are no overrides."""
    if term_canonical is None:
        return _EMPTY_OVERRIDES
    tables = _load_single_cp_tables()

    def _get(cat: str, direction: str) -> _RangeTuple:
        return tables[cat].get(term_canonical, {}).get(direction, ())

    narrower = _merge_ranges(
        _get('wide', 'narrower'),
        _get('sri', 'narrower'),
        _get('sfz', 'narrower'),
    )
    vs16_narrower = _get('vs16', 'narrower')
    vs16_wider = _get('vs16', 'wider')
    vs15_wider = _get('vs15', 'wider')
    # vs15_narrower is intentionally excluded, not possible by specification
    if not (narrower or vs16_narrower or vs16_wider or vs15_wider):
        return _EMPTY_OVERRIDES
    return TerminalOverrides(narrower, vs16_narrower, vs16_wider, vs15_wider)


@lru_cache(maxsize=32)
def resolve_terminal(term_program: str | None = None) -> str | None:
    """
    Resolve a terminal identifier to its canonical name.

    :param term_program: Terminal identifier string such as a TERM_PROGRAM value.
        If None, read the ``TERM_PROGRAM`` environment variable, falling back to ``TERM``.
    :returns: Canonical terminal name if recognized, ``None`` otherwise.

    The auto-detection path (``term_program=None``) reads environment variables at call time
    and caches the result.  The environment is assumed immutable for the process lifetime;
    callers that change ``TERM`` or ``TERM_PROGRAM`` mid-process must call
    :func:`resolve_terminal.cache_clear` afterward.
    """
    # Track whether the caller passed term_program explicitly.  Auto-detection
    # from environment must not match 'xterm' because its TERM value is shared
    # by many unrelated terminals with different unicode behaviours.
    explicit = term_program is not None
    if term_program is None:
        term_program = os.environ.get('TERM_PROGRAM', '')
        if not term_program:
            term_program = os.environ.get('TERM', '')
    if not term_program:
        return None
    key = term_program.strip().lower()
    canonical = ALIASES.get(key, key)
    if canonical not in KNOWN_TERMINALS:
        return None
    if canonical == 'xterm' and not explicit:
        return None
    return canonical
