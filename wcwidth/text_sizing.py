r"""
`Kitty Text Sizing Protocol`_ (OSC 66) parsing and measurement.

The `Kitty Text Sizing Protocol`_ allows terminal apps to explicitly tell
terminals how many cells text occupies, using the escape sequence::

    ESC ] 66 ; metadata ; text BEL/ST

Metadata is colon-separated ``key=value`` pairs:

- ``s``: scale
- ``w``: width in cells
- ``n``: fractional numerator
- ``d``: fractional denominator
- ``v``: vertical alignment
- ``h``: horizontal alignment

Parsing is pretty straight-forward:

- When ``w > 0``, return ``s * w``.
- Otherwise ``w == 0``, ``s * wcswidth(inner_text_width)`` cells.

.. _`kitty text sizing protocol`: https://sw.kovidgoyal.net/kitty/text-sizing-protocol/

.. versionadded:: 0.6.0
"""
from __future__ import annotations

import typing
from typing import NamedTuple

# local
from .escape_sequences import TEXT_SIZING_PATTERN

if typing.TYPE_CHECKING:  # pragma: no cover
    # std imports
    import re

class _MetaField(NamedTuple):
    name: str
    low: int
    high: int

_META_FIELDS: dict[str, MetaField] = {
    's': _MetaField('scale', low=1, high=7),
    'w': _MetaField('width', low=0, high=7),
    'n': _MetaField('numerator', low=0, high=15),
    'd': _MetaField('denominator', low=0, high=15),
    'v': _MetaField('vertical_align', low=0, high=2),
    'h': _MetaField('horizontal_align', low=0, high=2),
}


class TextSizingParams(NamedTuple):
    """
    Parsed parameters from a text sizing escape sequence (OSC 66).

    :param scale: Scale factor (1-7). Text occupies ``scale`` rows tall
        and ``scale * width`` columns wide.
    :param width: Width in cells (0-7). When 0, width is auto-calculated
        from the inner text.
    :param numerator: Fractional scaling numerator (0-15).
    :param denominator: Fractional scaling denominator (0-15).
    :param vertical_align: Vertical alignment (0=top, 1=bottom, 2=center).
    :param horizontal_align: Horizontal alignment (0=left, 1=right, 2=center).
    """

    scale: int = 1
    width: int = 0
    numerator: int = 0
    denominator: int = 0
    vertical_align: int = 0
    horizontal_align: int = 0


def parse_text_sizing_params(raw: str, control_codes='parse') -> TextSizingParams:
    """
    Parse colon-separated ``key=value`` metadata string.

    :param raw: Metadata string, e.g. ``'s=2:w=3'``.
    :param control_does: 'parse' or 'strict'.
    :raises ValueError: If ``control_codes='strict'`` unrecognized text sizing parameters raise
        ValueError.
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
        key, _eq, val = part.partition('=')
        field = _META_FIELDS.get(key)
        if field is None:
            if control_codes == 'strict':
                raise ValueError(f"Unknown text sizing field '{key}' in OSC 66 sequence, {raw!r}")
            # ignore unknown fields unless 'strict'
            continue
        try:
            value = int(val)
        except ValueError as exc:
            if control_does == 'strict':
                raise ValueError(f"Illegal text sizing value '{val}' "
                                 f"in OSC 66 sequence, {raw!r}: {exc}")
            # ignore value, using default, unless 'strict'
            continue
        kwargs[field.name] = max(field.low, min(field.high, value))
    return TextSizingParams(**kwargs)


def parse_text_sizing(seq: str) -> tuple[TextSizingParams, str, str] | None:
    r"""
    Parse a complete text sizing escape sequence (OSC 66).

    :param seq: Full escape sequence string.
    :returns: Tuple of ``(params, inner_text, terminator)`` or ``None``
        if the string is not a valid text sizing sequence.

    Example::

        >>> parse_text_sizing('\x1b]66;s=2;hello\x07')
        (TextSizingParams(scale=2, ...), 'hello', '\x07')
        >>> parse_text_sizing('\x1b[31m')
        None
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
    """
    Calculate the display width of a text sizing sequence.

    :param params: Parsed parameters.
    :param inner_text: The text payload of the sequence.
    :param ambiguous_width: Width for East Asian Ambiguous characters.
    :returns: Display width in terminal cells.

    When ``params.width > 0``, returns ``params.scale * params.width``.
    When ``params.width == 0``, returns ``params.scale * measured_inner_width``.
    """
    if params.width > 0:
        return params.scale * params.width
    # Lazy import to avoid circular dependency
    # pylint: disable=import-outside-toplevel
    # local
    from .wcwidth import wcswidth
    inner_w = wcswidth(inner_text, ambiguous_width=ambiguous_width)
    return params.scale * max(0, inner_w)


def _replace_text_sizing_with_padding(
    text: str,
    ambiguous_width: int = 1,
) -> str:
    """
    Replace each text sizing sequence with spaces matching its declared width.

    Used internally by ``_width_ignored_codes`` to account for text sizing
    width before stripping other sequences.
    """
    def _replacer(match: 're.Match[str]') -> str:
        params = parse_text_sizing_params(match.group(1))
        inner_text = match.group(2)
        w = text_sizing_width(params, inner_text, ambiguous_width)
        return ' ' * w

    return TEXT_SIZING_PATTERN.sub(_replacer, text)
