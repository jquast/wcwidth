"""
This is a python implementation of wcwidth() and wcswidth().

https://github.com/jquast/wcwidth

Derived from Markus Kuhn's C code,

This is an implementation of wcwidth() and wcswidth() (defined in
IEEE Std 1002.1-2001) for Unicode.

http://www.opengroup.org/onlinepubs/007904975/functions/wcwidth.html
http://www.opengroup.org/onlinepubs/007904975/functions/wcswidth.html

In fixed-width output devices, Latin characters all occupy a single
"cell" position of equal width, whereas ideographic CJK characters
occupy two such cells. Interoperability between terminal-line
applications and (teletype-style) character terminals using the
UTF-8 encoding requires agreement on which character should advance
the cursor by how many cell positions. No established formal
standards exist at present on which Unicode character shall occupy
how many cell positions on character terminals. These routines are
a first attempt of defining such behavior based on simple rules
applied to data provided by the Unicode Consortium.

For some graphical characters, the Unicode standard explicitly
defines a character-cell width via the definition of the East Asian
FullWidth (F), Wide (W), Half-width (H), and Narrow (Na) classes.
In all these cases, there is no ambiguity about which width a
terminal shall use. For characters in the East Asian Ambiguous (A)
class, the width choice depends purely on a preference of backward
compatibility with either historic CJK or Western practice.
Choosing single-width for these characters is easy to justify as
the appropriate long-term solution, as the CJK practice of
displaying these characters as double-width comes from historic
implementation simplicity (8-bit encoded characters were displayed
single-width and 16-bit ones double-width, even for Greek,
Cyrillic, etc.) and not any typographic considerations.

Much less clear is the choice of width for the Not East Asian
(Neutral) class. Existing practice does not dictate a width for any
of these characters. It would nevertheless make sense
typographically to allocate two character cells to characters such
as for instance EM SPACE or VOLUME INTEGRAL, which cannot be
represented adequately with a single-width glyph. The following
routines at present merely assign a single-cell width to all
neutral characters, in the interest of simplicity. This is not
entirely satisfactory and should be reconsidered before
establishing a formal standard in this area. At the moment, the
decision which Not East Asian (Neutral) characters should be
represented by double-width glyphs cannot yet be answered by
applying a simple rule from the Unicode database content. Setting
up a proper standard for the behavior of UTF-8 character terminals
will require a careful analysis not only of each Unicode character,
but also of each presentation form, something the author of these
routines has avoided to do so far.

http://www.unicode.org/unicode/reports/tr11/

Latest version: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
"""

from __future__ import annotations

# std imports
from functools import lru_cache

from typing import Literal

# local
from ._width import width
from ._wcwidth import wcwidth
from ._constants import _LATEST_VERSION


@lru_cache(maxsize=128)
def _wcversion_value(ver_string: str) -> tuple[int, ...]:  # pragma: no cover
    """
    Integer-mapped value of given dotted version string.

    .. deprecated:: 0.3.0

        This function is no longer used internally by wcwidth but is retained
        for API compatibility with external tools.

    :param ver_string: Unicode version string, of form ``n.n.n``.
    :returns: tuple of digit tuples, ``tuple(int, [...])``.
    """
    retval = tuple(map(int, (ver_string.split('.'))))
    return retval


@lru_cache(maxsize=8)
def _wcmatch_version(given_version: str) -> str:  # pylint: disable=unused-argument
    """
    Return the supported Unicode version level.

    .. deprecated:: 0.3.0
        This function now always returns the latest version.

        This function is no longer used internally by wcwidth but is retained
        for API compatibility with external tools.

    :param given_version: Ignored. Any value is accepted for compatibility.
    :returns: The latest unicode version string.
    """
    return _LATEST_VERSION


def ljust(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    ambiguous_width: int = 1,
) -> str:
    r"""
    Return text left-justified in a string of given display width.

    :param text: String to justify, may contain terminal sequences.
    :param dest_width: Total display width of result in terminal cells.
    :param fillchar: Single character for padding (default space). Must have
        display width of 1 (not wide, not zero-width, not combining). Unicode
        characters like ``'·'`` are acceptable. The width is not validated.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: Text padded on the right to reach ``dest_width``.

    .. versionadded:: 0.3.0

    Example::

        >>> wcwidth.ljust('hi', 5)
        'hi   '
        >>> wcwidth.ljust('\x1b[31mhi\x1b[0m', 5)
        '\x1b[31mhi\x1b[0m   '
        >>> wcwidth.ljust('\U0001F468\u200D\U0001F469\u200D\U0001F467', 6)
        '👨‍👩‍👧    '
    """
    if text.isascii() and text.isprintable():
        text_width = len(text)
    else:
        text_width = width(text, control_codes=control_codes, ambiguous_width=ambiguous_width)
    padding_cells = max(0, dest_width - text_width)
    return text + fillchar * padding_cells


def rjust(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    ambiguous_width: int = 1,
) -> str:
    r"""
    Return text right-justified in a string of given display width.

    :param text: String to justify, may contain terminal sequences.
    :param dest_width: Total display width of result in terminal cells.
    :param fillchar: Single character for padding (default space). Must have
        display width of 1 (not wide, not zero-width, not combining). Unicode
        characters like ``'·'`` are acceptable. The width is not validated.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: Text padded on the left to reach ``dest_width``.

    .. versionadded:: 0.3.0

    Example::

        >>> wcwidth.rjust('hi', 5)
        '   hi'
        >>> wcwidth.rjust('\x1b[31mhi\x1b[0m', 5)
        '   \x1b[31mhi\x1b[0m'
        >>> wcwidth.rjust('\U0001F468\u200D\U0001F469\u200D\U0001F467', 6)
        '    👨‍👩‍👧'
    """
    if text.isascii() and text.isprintable():
        text_width = len(text)
    else:
        text_width = width(text, control_codes=control_codes, ambiguous_width=ambiguous_width)
    padding_cells = max(0, dest_width - text_width)
    return fillchar * padding_cells + text


def center(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: Literal['parse', 'strict', 'ignore'] = 'parse',
    ambiguous_width: int = 1,
) -> str:
    r"""
    Return text centered in a string of given display width.

    :param text: String to center, may contain terminal sequences.
    :param dest_width: Total display width of result in terminal cells.
    :param fillchar: Single character for padding (default space). Must have
        display width of 1 (not wide, not zero-width, not combining). Unicode
        characters like ``'·'`` are acceptable. The width is not validated.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: Text padded on both sides to reach ``dest_width``.

    For odd-width padding, the extra cell goes on the right (matching
    Python's :meth:`str.center` behavior).

    .. versionadded:: 0.3.0

    Example::

        >>> wcwidth.center('hi', 6)
        '  hi  '
        >>> wcwidth.center('\x1b[31mhi\x1b[0m', 6)
        '  \x1b[31mhi\x1b[0m  '
        >>> wcwidth.center('\U0001F468\u200D\U0001F469\u200D\U0001F467', 6)
        '  👨‍👩‍👧  '
    """
    if text.isascii() and text.isprintable():
        text_width = len(text)
    else:
        text_width = width(text, control_codes=control_codes, ambiguous_width=ambiguous_width)
    total_padding = max(0, dest_width - text_width)
    # matching https://jazcap53.github.io/pythons-eccentric-strcenter.html
    left_pad = total_padding // 2 + (total_padding & dest_width & 1)
    right_pad = total_padding - left_pad
    return fillchar * left_pad + text + fillchar * right_pad

