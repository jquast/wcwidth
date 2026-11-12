"""
Line breaking following Unicode Standard Annex #14.

:func:`wcwidth.wrap` takes its break opportunities from here: U+200B ZERO WIDTH SPACE breaks,
U+00A0 NO-BREAK SPACE keeps its neighbours together, and U+2060 WORD JOINER suppresses breaks on
both sides.

https://www.unicode.org/reports/tr14/
"""

from __future__ import annotations

# std imports
import os
from functools import lru_cache
from dataclasses import dataclass

from typing import TYPE_CHECKING, Callable, Optional, NamedTuple

# local
from .bisearch import bisearch
from .table_linebreak import (LINEBREAK_PF_QU,
                              LINEBREAK_PI_QU,
                              LINEBREAK_SA_CM,
                              LINEBREAK_RANGES,
                              LINEBREAK_EAST_ASIAN,
                              LINEBREAK_EXT_PICT_CN,
                              LINEBREAK_UNICODE_VERSION,
                              LineBreak)

if TYPE_CHECKING:  # pragma: no cover
    # std imports
    from collections.abc import Iterable, Iterator

__all__ = ('BreakOpportunity', 'LineBreak', 'LINEBREAK_UNICODE_VERSION',
           'iter_line_breaks', 'linebreak_class')

_C_LINE_BREAKS: Optional[Callable[[str, bool], list[tuple[int, bool]]]] = None
if not os.environ.get('WCWIDTH_PYTHON', ''):
    try:
        # local
        from ._wcwidth_c import line_breaks as _C_LINE_BREAKS
    except ImportError:  # pragma: no cover
        pass

_HARD_BREAK = frozenset((LineBreak.BK, LineBreak.CR, LineBreak.LF, LineBreak.NL))
_NO_BASE = frozenset((LineBreak.BK, LineBreak.CR, LineBreak.LF, LineBreak.NL,
                      LineBreak.SP, LineBreak.ZW))
_HANGUL = frozenset((LineBreak.JL, LineBreak.JV, LineBreak.JT, LineBreak.H2, LineBreak.H3))
_DOTTED_CIRCLE = 0x25CC


@dataclass(frozen=True)
class BreakOpportunity:
    """A position where a line may break, and whether the break is mandatory."""

    index: int
    mandatory: bool


@lru_cache(maxsize=1024)
def linebreak_class(ucs: int) -> LineBreak:
    """
    Return the UAX #14 line breaking property of a codepoint from ``LineBreak.txt``.

    :func:`iter_line_breaks` applies the LB1 class resolution rules before using it.

    :param ucs: Codepoint ordinal.
    :returns: :class:`LineBreak` class value.
    """
    lo, hi = 0, len(LINEBREAK_RANGES) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end, cls = LINEBREAK_RANGES[mid]
        if ucs < start:
            hi = mid - 1
        elif ucs > end:
            lo = mid + 1
        else:
            return LineBreak(cls)
    return LineBreak.XX


def _resolved_class(ucs: int) -> LineBreak:
    """Apply LB1 resolution to a codepoint."""
    cls = linebreak_class(ucs)
    if cls in (LineBreak.AI, LineBreak.SG, LineBreak.XX):
        return LineBreak.AL
    if cls == LineBreak.CJ:
        return LineBreak.NS
    if cls == LineBreak.SA:
        return LineBreak.CM if bisearch(ucs, LINEBREAK_SA_CM) else LineBreak.AL
    return cls


_ASCII_CLASSES = tuple(_resolved_class(cp) for cp in range(128))


def _is_ea(ucs: int) -> bool:
    """Return True when East_Asian_Width is Fullwidth, Wide or Halfwidth."""
    return bool(bisearch(ucs, LINEBREAK_EAST_ASIAN))


def _is_pi_qu(ucs: int, cls: LineBreak) -> bool:
    return cls == LineBreak.QU and bool(bisearch(ucs, LINEBREAK_PI_QU))


def _is_pf_qu(ucs: int, cls: LineBreak) -> bool:
    return cls == LineBreak.QU and bool(bisearch(ucs, LINEBREAK_PF_QU))


def _is_ext_pict_cn(ucs: int) -> bool:
    return bool(bisearch(ucs, LINEBREAK_EXT_PICT_CN))


_LB15A_PRECEDERS = frozenset((LineBreak.BK, LineBreak.CR, LineBreak.LF, LineBreak.NL,
                              LineBreak.OP, LineBreak.QU, LineBreak.GL, LineBreak.SP,
                              LineBreak.ZW))


def _is_initial_quote(index: int, cps: list[int], clusters: list[LineBreak],
                      starts: list[int]) -> bool:
    """Return True when the cluster at index is a Pi quotation mark that begins a line."""
    if not _is_pi_qu(cps[starts[index]], clusters[index]):
        return False
    return index == 0 or clusters[index - 1] in _LB15A_PRECEDERS


class _Clusters(NamedTuple):
    """Codepoints grouped by LB9/LB10 combining sequences."""

    classes: list[LineBreak]
    clusters: list[LineBreak]
    starts: list[int]
    ends: list[int]


def _clusters(cps: list[int]) -> _Clusters:
    if not cps or (min(cps) >= 0x20 and max(cps) < 0x7f):
        # Every printable ASCII codepoint forms a cluster of its own.
        classes = [_ASCII_CLASSES[cp] for cp in cps]
        return _Clusters(classes, classes, list(range(len(cps))),
                         list(range(1, len(cps) + 1)))
    classes = [_resolved_class(cp) for cp in cps]
    clusters: list[LineBreak] = []
    starts: list[int] = []
    ends: list[int] = []
    n = len(cps)
    i = 0
    while i < n:
        cls = classes[i]
        if cls in (LineBreak.CM, LineBreak.ZWJ):
            # LB10: a combining mark with no usable base behaves as AL.
            clusters.append(LineBreak.AL)
        else:
            clusters.append(cls)
        starts.append(i)
        ends.append(i + 1)
        i += 1
        if clusters[-1] in _NO_BASE:
            continue
        while i < n and classes[i] in (LineBreak.CM, LineBreak.ZWJ):
            ends[-1] = i + 1
            i += 1
    return _Clusters(classes, clusters, starts, ends)


def _nu_before(idx: int, clusters: list[LineBreak]) -> int:
    """Return the index of NU in ``NU (SY|IS)*`` ending at idx, or -1."""
    while idx >= 0 and clusters[idx] in (LineBreak.SY, LineBreak.IS):
        idx -= 1
    return idx if idx >= 0 and clusters[idx] == LineBreak.NU else -1


def _is_dotted(index: int, cls: LineBreak, cps: list[int], starts: list[int]) -> bool:
    return cls in (LineBreak.AK, LineBreak.AS) or cps[starts[index]] == _DOTTED_CIRCLE


def _break_at(idx: int, cps: list[int], data: _Clusters, ri_run: int) -> tuple[bool, bool]:
    """Return (allowed, mandatory) for the boundary between cluster idx and idx+1."""
    # pylint: disable=too-many-branches,too-many-statements,too-many-return-statements
    # pylint: disable=too-complex,too-many-locals
    classes, clusters, starts, ends = data
    before = clusters[idx]
    after = clusters[idx + 1]
    count = len(clusters)

    # Short-circuits for the pairs that dominate running text, ahead of the full rule chain.
    if before == LineBreak.AL and after == LineBreak.AL:
        return False, False  # LB28
    if after == LineBreak.SP and before not in _HARD_BREAK:
        return False, False  # LB7, with LB4 and LB5 already excluded
    if before == LineBreak.SP and after == LineBreak.AL:
        look = idx - 1
        while look >= 0 and clusters[look] == LineBreak.SP:
            look -= 1
        if look >= 0 and (clusters[look] == LineBreak.OP
                          or _is_initial_quote(look, cps, clusters, starts)):
            return False, False  # LB14 and LB15a
        return True, False  # LB8 and LB18
    if (before == LineBreak.ID and after == LineBreak.ID
            and classes[ends[idx] - 1] != LineBreak.ZWJ):
        return True, False  # LB31, with LB8a excluded

    before_cp = cps[starts[idx]]
    after_cp = cps[starts[idx + 1]]

    # LB4, LB5: hard line breaks.
    if before == LineBreak.BK:
        return True, True
    if before == LineBreak.CR:
        return (False, False) if after == LineBreak.LF else (True, True)
    if before in (LineBreak.LF, LineBreak.NL):
        return True, True

    # LB6: do not break before hard line breaks.
    if after in _HARD_BREAK:
        return False, False

    # LB7: do not break before spaces or zero width space.
    if after in (LineBreak.SP, LineBreak.ZW):
        return False, False

    # LB8: ZW SP* divides.
    look = idx
    while look >= 0 and clusters[look] == LineBreak.SP:
        look -= 1
    if look >= 0 and clusters[look] == LineBreak.ZW:
        return True, False

    # LB8a: ZWJ does not break after.
    if classes[ends[idx] - 1] == LineBreak.ZWJ:
        return False, False

    # LB11: word joiner.
    if LineBreak.WJ in (before, after):
        return False, False

    # LB12: no break after glue.
    if before == LineBreak.GL:
        return False, False

    # LB12a: no break before glue, except after SP, HY or HH.
    if after == LineBreak.GL and before not in (LineBreak.SP, LineBreak.HY, LineBreak.HH):
        return False, False

    # LB13: no break before closing punctuation, exclamation, or solidus.
    if after in (LineBreak.CL, LineBreak.CP, LineBreak.EX, LineBreak.SY):
        return False, False

    # LB14: no break after OP, even after spaces.
    look = idx
    while look >= 0 and clusters[look] == LineBreak.SP:
        look -= 1
    if look >= 0 and clusters[look] == LineBreak.OP:
        return False, False

    # LB15a: no break after an initial quotation mark, even after spaces.
    look = idx
    while look >= 0 and clusters[look] == LineBreak.SP:
        look -= 1
    if look >= 0 and _is_initial_quote(look, cps, clusters, starts):
        return False, False

    # LB15b: no break before a final quotation mark in final position.
    if _is_pf_qu(after_cp, after):
        next_class = clusters[idx + 2] if idx + 2 < count else None
        if next_class in (None, LineBreak.SP, LineBreak.GL, LineBreak.WJ, LineBreak.CL,
                          LineBreak.QU, LineBreak.CP, LineBreak.EX, LineBreak.IS,
                          LineBreak.SY, LineBreak.BK, LineBreak.CR, LineBreak.LF,
                          LineBreak.NL, LineBreak.ZW):
            return False, False

    # LB15c: break before a decimal mark that follows a space.
    if before == LineBreak.SP and after == LineBreak.IS:
        if idx + 2 < count and clusters[idx + 2] == LineBreak.NU:
            return True, False

    # LB15d: otherwise no break before IS.
    if after == LineBreak.IS:
        return False, False

    # LB16: (CL|CP) SP* x NS.
    if after == LineBreak.NS:
        look = idx
        while look >= 0 and clusters[look] == LineBreak.SP:
            look -= 1
        if look >= 0 and clusters[look] in (LineBreak.CL, LineBreak.CP):
            return False, False

    # LB17: B2 SP* x B2.
    if after == LineBreak.B2:
        look = idx
        while look >= 0 and clusters[look] == LineBreak.SP:
            look -= 1
        if look >= 0 and clusters[look] == LineBreak.B2:
            return False, False

    # LB18: break after spaces.
    if before == LineBreak.SP:
        return True, False

    # LB19: unresolved quotation marks.
    if after == LineBreak.QU and not _is_pi_qu(after_cp, after):
        return False, False
    if before == LineBreak.QU and not _is_pf_qu(before_cp, before):
        return False, False

    # LB19a: East Asian quotation marks.
    if after == LineBreak.QU and not _is_ea(before_cp):
        return False, False
    if after == LineBreak.QU:
        next_cp = cps[starts[idx + 2]] if idx + 2 < count else None
        if next_cp is None or not _is_ea(next_cp):
            return False, False
    if before == LineBreak.QU and not _is_ea(after_cp):
        return False, False
    if before == LineBreak.QU:
        prior_cp = cps[starts[idx - 1]] if idx > 0 else None
        if prior_cp is None or not _is_ea(prior_cp):
            return False, False

    # LB20: break before and after unresolved CB.
    if LineBreak.CB in (after, before):
        return True, False

    # LB20a: no break after a word-initial hyphen.
    if before in (LineBreak.HY, LineBreak.HH) and after in (LineBreak.AL, LineBreak.HL):
        prior_class = clusters[idx - 1] if idx > 0 else None
        if prior_class in (None, LineBreak.BK, LineBreak.CR, LineBreak.LF, LineBreak.NL,
                           LineBreak.SP, LineBreak.ZW, LineBreak.CB, LineBreak.GL):
            return False, False

    # LB21: no break before BA, HH, HY, NS; no break after BB.
    if after in (LineBreak.BA, LineBreak.HH, LineBreak.HY, LineBreak.NS):
        return False, False
    if before == LineBreak.BB:
        return False, False

    # LB21a: Hebrew + hyphen + non-Hebrew.
    if (before in (LineBreak.HY, LineBreak.HH) and after != LineBreak.HL
            and idx > 0 and clusters[idx - 1] == LineBreak.HL):
        return False, False

    # LB21b: solidus before Hebrew.
    if before == LineBreak.SY and after == LineBreak.HL:
        return False, False

    # LB22: no break before ellipsis.
    if after == LineBreak.IN:
        return False, False

    # LB23: digits and letters.
    if ((before in (LineBreak.AL, LineBreak.HL) and after == LineBreak.NU)
            or (before == LineBreak.NU and after in (LineBreak.AL, LineBreak.HL))):
        return False, False

    # LB23a: numeric prefixes and ideographs.
    if ((before == LineBreak.PR and after in (LineBreak.ID, LineBreak.EB, LineBreak.EM))
            or (before in (LineBreak.ID, LineBreak.EB, LineBreak.EM)
                and after == LineBreak.PO)):
        return False, False

    # LB24: numeric prefixes and letters.
    if ((before in (LineBreak.PR, LineBreak.PO) and after in (LineBreak.AL, LineBreak.HL))
            or (before in (LineBreak.AL, LineBreak.HL)
                and after in (LineBreak.PR, LineBreak.PO))):
        return False, False

    # LB25: numbers.
    if after in (LineBreak.PO, LineBreak.PR):
        if _nu_before(idx, clusters) >= 0:
            return False, False
        if before in (LineBreak.CL, LineBreak.CP) and _nu_before(idx - 1, clusters) >= 0:
            return False, False
    if before in (LineBreak.PO, LineBreak.PR) and after == LineBreak.OP:
        nxt = clusters[idx + 2] if idx + 2 < count else None
        nxt2 = clusters[idx + 3] if idx + 3 < count else None
        if nxt == LineBreak.NU or (nxt == LineBreak.IS and nxt2 == LineBreak.NU):
            return False, False
    if before in (LineBreak.PO, LineBreak.PR) and after == LineBreak.NU:
        return False, False
    if before in (LineBreak.HY, LineBreak.IS) and after == LineBreak.NU:
        return False, False
    if after == LineBreak.NU and _nu_before(idx, clusters) >= 0:
        return False, False

    # LB26: Korean syllable blocks.
    if ((before == LineBreak.JL and after in (LineBreak.JL, LineBreak.JV,
                                              LineBreak.H2, LineBreak.H3))
            or (before in (LineBreak.JV, LineBreak.H2)
                and after in (LineBreak.JV, LineBreak.JT))
            or (before in (LineBreak.JT, LineBreak.H3) and after == LineBreak.JT)):
        return False, False

    # LB27: Korean syllable blocks behave as ID.
    if before in _HANGUL and after == LineBreak.PO:
        return False, False
    if before == LineBreak.PR and after in _HANGUL:
        return False, False

    # LB28: alphabetic letters.
    if before in (LineBreak.AL, LineBreak.HL) and after in (LineBreak.AL, LineBreak.HL):
        return False, False

    # LB28a: Brahmic orthographic syllables.
    if before == LineBreak.AP and _is_dotted(idx + 1, after, cps, starts):
        return False, False
    if _is_dotted(idx, before, cps, starts) and after in (LineBreak.VF, LineBreak.VI):
        return False, False
    if (before == LineBreak.VI and idx > 0
            and _is_dotted(idx - 1, clusters[idx - 1], cps, starts)
            and _is_dotted(idx + 1, after, cps, starts)):
        return False, False
    if (_is_dotted(idx, before, cps, starts)
            and _is_dotted(idx + 1, after, cps, starts)
            and idx + 2 < count and clusters[idx + 2] == LineBreak.VF):
        return False, False

    # LB29: numeric punctuation before letters.
    if before == LineBreak.IS and after in (LineBreak.AL, LineBreak.HL):
        return False, False

    # LB30: parentheses, excluding East Asian ones.
    if before in (LineBreak.AL, LineBreak.HL, LineBreak.NU) and after == LineBreak.OP:
        if not _is_ea(after_cp):
            return False, False
    if before == LineBreak.CP and after in (LineBreak.AL, LineBreak.HL, LineBreak.NU):
        if not _is_ea(before_cp):
            return False, False

    # LB30a: regional indicator pairs.
    if before == LineBreak.RI and after == LineBreak.RI:
        return ri_run % 2 == 0, False

    # LB30b: emoji base and modifier.
    if after == LineBreak.EM and (before == LineBreak.EB or _is_ext_pict_cn(before_cp)):
        return False, False

    # LB31: break everywhere else.
    return True, False


def iter_line_breaks(text: str, *, hyphens: bool = True) -> Iterator[BreakOpportunity]:
    r"""
    Iterate over UAX #14 line break opportunities.

    Each yielded index is a string position where a line may break.  Non-empty text yields its
    own length (LB3) and skips position 0 (LB2).

    :param text: Text to inspect.
    :param hyphens: When False, suppress optional breaks after U+002D HYPHEN-MINUS, U+2010 HYPHEN
        and U+00AD SOFT HYPHEN.  This preserves the ``break_on_hyphens`` option of
        :func:`wcwidth.wrap`.
    :yields: :class:`BreakOpportunity` values in ascending index order.

    Example::

        >>> [b.index for b in iter_line_breaks('a\u200bb')]
        [2, 3]
        >>> [b.index for b in iter_line_breaks('a\u00a0b')]
        [3]
    """
    if not text:
        return
    for index, mandatory in _break_positions(text, hyphens):
        yield BreakOpportunity(index, mandatory)


def _break_positions(text: str, hyphens: bool) -> Iterable[tuple[int, bool]]:
    """Return ``(index, mandatory)`` break opportunities, from C when available."""
    if not text:
        return ()
    if _C_LINE_BREAKS is not None:
        return _C_LINE_BREAKS(text, hyphens)
    return _python_break_positions(text, hyphens)


def _python_break_positions(text: str, hyphens: bool) -> Iterator[tuple[int, bool]]:
    cps = [ord(ch) for ch in text]
    data = _clusters(cps)
    count = len(data.clusters)
    ri_run = 0
    for idx in range(count - 1):
        ri_run = ri_run + 1 if data.clusters[idx] == LineBreak.RI else 0
        allowed, mandatory = _break_at(idx, cps, data, ri_run)
        if not allowed:
            continue
        if not hyphens and not mandatory and data.clusters[idx] in (LineBreak.HY, LineBreak.HH):
            continue
        yield data.ends[idx], mandatory
    yield len(text), False
