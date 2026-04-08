r"""
OSC 66 (Kitty Text Sizing Protocol) parsing and generation.

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

from .escape_sequences import OSC66_PATTERN

_MAX_TEXT_PAYLOAD = 4096

# Metadata key → (NamedTuple field, min, max, default)
_META_FIELDS = {
    's': ('scale', 1, 7, 1),
    'w': ('width', 0, 7, 0),
    'n': ('numerator', 0, 15, 0),
    'd': ('denominator', 0, 15, 0),
    'v': ('vertical_align', 0, 2, 0),
    'h': ('horizontal_align', 0, 2, 0),
}

# Reverse map: field name → short key
_FIELD_TO_KEY = {field: key for key, (field, _, _, _) in _META_FIELDS.items()}


class OSC66Metadata(NamedTuple):
    """Parsed metadata from an OSC 66 escape sequence.

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


def parse_osc66_metadata(raw: str) -> OSC66Metadata:
    """Parse colon-separated ``key=value`` metadata string.

    :param raw: Metadata string, e.g. ``'s=2:w=3'``.
    :returns: Parsed metadata with values clamped to valid ranges.
        Unknown keys are ignored. Non-integer values use defaults.

    Example::

        >>> parse_osc66_metadata('s=2:w=3')
        OSC66Metadata(scale=2, width=3, numerator=0, denominator=0, vertical_align=0, horizontal_align=0)
        >>> parse_osc66_metadata('')
        OSC66Metadata(scale=1, width=0, numerator=0, denominator=0, vertical_align=0, horizontal_align=0)
    """
    kwargs: dict[str, int] = {}
    if not raw:
        return OSC66Metadata()
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
    return OSC66Metadata(**kwargs)


def make_osc66_metadata(meta: OSC66Metadata) -> str:
    """Serialize metadata, omitting fields at their default values.

    :param meta: Metadata to serialize.
    :returns: Colon-separated ``key=value`` string.

    Example::

        >>> make_osc66_metadata(OSC66Metadata(scale=2, width=3))
        's=2:w=3'
        >>> make_osc66_metadata(OSC66Metadata())
        ''
    """
    parts = []
    defaults = OSC66Metadata()
    for field, key in _FIELD_TO_KEY.items():
        val = getattr(meta, field)
        if val != getattr(defaults, field):
            parts.append(f'{key}={val}')
    return ':'.join(parts)


def parse_osc66_sequence(seq: str) -> tuple[OSC66Metadata, str, str] | None:
    """Parse a complete OSC 66 escape sequence.

    :param seq: Full escape sequence string.
    :returns: Tuple of ``(metadata, inner_text, terminator)`` or ``None``
        if the string is not a valid OSC 66 sequence.

    Example::

        >>> parse_osc66_sequence('\x1b]66;s=2;hello\x07')
        (OSC66Metadata(scale=2, ...), 'hello', '\x07')
        >>> parse_osc66_sequence('\x1b[31m') is None
        True
    """
    match = OSC66_PATTERN.fullmatch(seq)
    if not match:
        return None
    return (
        parse_osc66_metadata(match.group(1)),
        match.group(2),
        match.group(3),
    )


def osc66_width(
    meta: OSC66Metadata,
    inner_text: str,
    ambiguous_width: int = 1,
) -> int:
    """Calculate the display width of an OSC 66 sequence.

    :param meta: Parsed metadata.
    :param inner_text: The text payload of the OSC 66 sequence.
    :param ambiguous_width: Width for East Asian Ambiguous characters.
    :returns: Display width in terminal cells.

    When ``meta.width > 0``, returns ``meta.scale * meta.width``.
    When ``meta.width == 0``, returns ``meta.scale * measured_inner_width``.
    """
    if meta.width > 0:
        return meta.scale * meta.width
    # Lazy import to avoid circular dependency (wcwidth -> osc66 -> wcwidth)
    from .wcwidth import wcswidth  # pylint: disable=import-outside-toplevel
    inner_w = wcswidth(inner_text, ambiguous_width=ambiguous_width)
    return meta.scale * max(0, inner_w)


def make_osc66_sequence(
    text: str,
    meta: OSC66Metadata,
    terminator: str = '\x07',
) -> str:
    r"""Build a complete OSC 66 escape sequence.

    :param text: Text payload.
    :param meta: Metadata to encode.
    :param terminator: Sequence terminator, ``'\x07'`` (BEL) or
        ``'\x1b\\'`` (ST). Default is BEL.
    :returns: Complete escape sequence string.
    :raises ValueError: If text exceeds 4096 bytes when UTF-8 encoded.

    Example::

        >>> make_osc66_sequence('hi', OSC66Metadata(scale=2, width=1))
        '\x1b]66;s=2:w=1;hi\x07'
    """
    if len(text.encode('utf-8')) > _MAX_TEXT_PAYLOAD:
        raise ValueError(
            f"OSC 66 text payload exceeds {_MAX_TEXT_PAYLOAD} byte limit"
        )
    metadata_str = make_osc66_metadata(meta)
    return f'\x1b]66;{metadata_str};{text}{terminator}'


def osc66_wrap(
    text: str,
    *,
    scale: int = 1,
    width: int = 0,
    numerator: int = 0,
    denominator: int = 0,
    vertical_align: int = 0,
    horizontal_align: int = 0,
    terminator: str = '\x07',
) -> str:
    r"""Wrap text in an OSC 66 escape sequence with full control over metadata.

    :param text: Text payload.
    :param scale: Scale factor (1--7).
    :param width: Width in cells (0--7). 0 means auto-calculate.
    :param numerator: Fractional scaling numerator (0--15).
    :param denominator: Fractional scaling denominator (0--15).
    :param vertical_align: Vertical alignment (0=top, 1=bottom, 2=center).
    :param horizontal_align: Horizontal alignment (0=left, 1=right, 2=center).
    :param terminator: ``'\x07'`` (BEL) or ``'\x1b\\'`` (ST).
    :returns: Complete OSC 66 escape sequence.
    :raises ValueError: If text exceeds 4096 bytes.

    Example::

        >>> osc66_wrap('AB', scale=2, width=2)
        '\x1b]66;s=2:w=2;AB\x07'
    """
    meta = OSC66Metadata(
        scale=scale,
        width=width,
        numerator=numerator,
        denominator=denominator,
        vertical_align=vertical_align,
        horizontal_align=horizontal_align,
    )
    return make_osc66_sequence(text, meta, terminator)


def osc66_scale(
    text: str,
    scale: int,
    *,
    terminator: str = '\x07',
    ambiguous_width: int = 1,
) -> str:
    r"""Wrap text in an OSC 66 sequence, auto-calculating width from inner text.

    This is the most common use case: scale text to ``scale`` times its
    natural width, with the ``w`` parameter set automatically.

    :param text: Text payload.
    :param scale: Scale factor (1--7).
    :param terminator: ``'\x07'`` (BEL) or ``'\x1b\\'`` (ST).
    :param ambiguous_width: Width for East Asian Ambiguous characters.
    :returns: Complete OSC 66 escape sequence with auto-calculated ``w``.
    :raises ValueError: If text exceeds 4096 bytes.

    Example::

        >>> osc66_scale('AB', 2)
        '\x1b]66;s=2:w=2;AB\x07'
    """
    from .wcwidth import wcswidth  # pylint: disable=import-outside-toplevel
    inner_w = wcswidth(text, ambiguous_width=ambiguous_width)
    meta = OSC66Metadata(scale=scale, width=max(0, inner_w))
    return make_osc66_sequence(text, meta, terminator)


def _replace_osc66_with_padding(
    text: str,
    ambiguous_width: int = 1,
) -> str:
    """Replace each OSC 66 sequence with spaces matching its declared width.

    Used internally by ``_width_ignored_codes`` to account for OSC 66
    width before stripping other sequences.
    """
    def _replacer(match: 're.Match[str]') -> str:
        meta = parse_osc66_metadata(match.group(1))
        inner_text = match.group(2)
        w = osc66_width(meta, inner_text, ambiguous_width)
        return ' ' * w

    return OSC66_PATTERN.sub(_replacer, text)
