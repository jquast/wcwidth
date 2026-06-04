"""Shared data tables and constants for wcwidth.py, _wcwidth.py, and _wcswidth.py."""

# local
from .table_mc import CATEGORY_MC
from .table_wide import WIDE_EASTASIAN
from .table_zero import ZERO_WIDTH
from .table_grapheme import (ISC_VIRAMA,
                             EXTENDED_PICTOGRAPHIC,
                             ISC_INVISIBLE_STACKER,
                             GRAPHEME_REGIONAL_INDICATOR)
from .table_ambiguous import AMBIGUOUS_EASTASIAN
from .unicode_versions import list_versions

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
)

_REGIONAL_INDICATOR_SET = frozenset(
    range(GRAPHEME_REGIONAL_INDICATOR[0][0], GRAPHEME_REGIONAL_INDICATOR[0][1] + 1)
)
_ISC_VIRAMA_SET = frozenset(
    cp for lo, hi in (*ISC_VIRAMA, *ISC_INVISIBLE_STACKER)
    for cp in range(lo, hi + 1)
)
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
