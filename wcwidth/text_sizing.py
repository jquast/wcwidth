r"""
Text Sizing Protocol (OSC 66) parsing and measurement.

The `Kitty Text Sizing Protocol`_ allows applications to explicitly tell
terminals how many cells text occupies, using the escape sequence::

    ESC ] 66 ; metadata ; text BEL/ST

Metadata is colon-separated ``key=value`` pairs:

- ``s``: scale (1--7, default 1)
- ``w``: width in cells (0--7, default 0; 0 means auto-calculate from inner text)
- ``n``: fractional numerator (0--15, default 0)
- ``d``: fractional denominator (0--15, default 0)
- ``v``: vertical alignment (0--2, default 0: top, 1: bottom, 2: center)
- ``h``: horizontal alignment (0--2, default 0: left, 1: right, 2: center)

Width calculation: if ``w > 0``, the sequence occupies ``s * w`` cells.
If ``w == 0``, the sequence occupies ``s * inner_text_width`` cells.

.. _`Kitty Text Sizing Protocol`: https://sw.kovidgoyal.net/kitty/text-sizing-protocol/

.. versionadded:: 0.6.0
"""
from __future__ import annotations

from typing import NamedTuple

from .escape_sequences import TEXT_SIZING_PATTERN

# Metadata key → (NamedTuple field, min, max, default)
_META_FIELDS = {
    's': ('scale', 1, 7, 1),
    'w': ('width', 0, 7, 0),
    'n': ('numerator', 0, 15, 0),
    'd': ('denominator', 0, 15, 0),
    'v': ('vertical_align', 0, 2, 0),
    'h': ('horizontal_align', 0, 2, 0),
}

class TextSizingParams(NamedTuple):
    """Parsed parameters from a text sizing escape sequence (OSC 66).

    :param scale: Scale factor (1--7). Text occupies ``scale`` rows tall
        and ``scale * width`` columns wide.
    :param width: Width in cells (0--7). When 0, width is auto-calculated
        from the inner text.
    :param numerator: Fractional scaling numerator (0--15).
    :param denominator: Fractional scaling denominator (0--15).
    :param vertical_align: Vertical alignment (0=top, 1=bottom, 2=center).
    :param horizontal_align: Horizontal alignment (0=left, 1=right, 2=center).
    """

    scale: int = 1
    width: int = 0
    numerator: int = 0
    denominator: int = 0
    vertical_align: int = 0
    horizontal_align: int = 0


def parse_text_sizing_params(raw: str) -> TextSizingParams:
    """Parse colon-separated ``key=value`` metadata string.

    :param raw: Metadata string, e.g. ``'s=2:w=3'``.
    :returns: Parsed parameters with values clamped to valid ranges.
        Unknown keys are ignored. Non-integer values use defaults.

    Example::

        >>> parse_text_sizing_params('s=2:w=3')
        TextSizingParams(scale=2, width=3, numerator=0, denominator=0, vertical_align=0, horizontal_align=0)
        >>> parse_text_sizing_params('')
        TextSizingParams(scale=1, width=0, numerator=0, denominator=0, vertical_align=0, horizontal_align=0)
    """
    kwargs: dict[str, int] = {}
    if not raw:
        return TextSizingParams()
    for part in raw.split(':'):
        if '=' not in part:
            continue
        key, _, val_str = part.partition('=')
        if key not in _META_FIELDS:
            continue
        field, lo, hi, default = _META_FIELDS[key]
        try:
            kwargs[field] = max(lo, min(hi, int(val_str)))
        except (ValueError, OverflowError):
            kwargs[field] = default
    return TextSizingParams(**kwargs)


def parse_text_sizing(seq: str) -> tuple[TextSizingParams, str, str] | None:
    """Parse a complete text sizing escape sequence (OSC 66).

    :param seq: Full escape sequence string.
    :returns: Tuple of ``(params, inner_text, terminator)`` or ``None``
        if the string is not a valid text sizing sequence.

    Example::

        >>> parse_text_sizing('\x1b]66;s=2;hello\x07')
        (TextSizingParams(scale=2, ...), 'hello', '\x07')
        >>> parse_text_sizing('\x1b[31m') is None
        True
    """
    match = TEXT_SIZING_PATTERN.fullmatch(seq)
    if not match:
        return None
    return (
        parse_text_sizing_params(match.group(1)),
        match.group(2),
        match.group(3),
    )


def text_sizing_width(
    params: TextSizingParams,
    inner_text: str,
    ambiguous_width: int = 1,
) -> int:
    """Calculate the display width of a text sizing sequence.

    :param params: Parsed parameters.
    :param inner_text: The text payload of the sequence.
    :param ambiguous_width: Width for East Asian Ambiguous characters.
    :returns: Display width in terminal cells.

    When ``params.width > 0``, returns ``params.scale * params.width``.
    When ``params.width == 0``, returns ``params.scale * measured_inner_width``.
    """
    if params.width > 0:
        return params.scale * params.width
    # Lazy import to avoid circular dependency (wcwidth -> text_sizing -> wcwidth)
    from .wcwidth import wcswidth  # pylint: disable=import-outside-toplevel
    inner_w = wcswidth(inner_text, ambiguous_width=ambiguous_width)
    return params.scale * max(0, inner_w)


def _replace_text_sizing_with_padding(
    text: str,
    ambiguous_width: int = 1,
) -> str:
    """Replace each text sizing sequence with spaces matching its declared width.

    Used internally by ``_width_ignored_codes`` to account for text sizing
    width before stripping other sequences.
    """
    def _replacer(match: 're.Match[str]') -> str:
        params = parse_text_sizing_params(match.group(1))
        inner_text = match.group(2)
        w = text_sizing_width(params, inner_text, ambiguous_width)
        return ' ' * w

    return TEXT_SIZING_PATTERN.sub(_replacer, text)
