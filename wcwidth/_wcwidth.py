"""This is a python implementation of wcwidth()."""

# std
# std imports
from functools import lru_cache

# local
from .bisearch import bisearch
from ._constants import _AMBIGUOUS_TABLE, _ZERO_WIDTH_TABLE, _WIDE_EASTASIAN_TABLE

# maxsize=1024: western scripts need ~64 unique codepoints per session, but
# CJK sessions may use ~2000 of ~3500 common hanzi/kanji. 1024 accommodates
# heavy CJK use. Performance floor at 32; bisearch is ~100ns per miss.


@lru_cache(maxsize=1024)
def wcwidth(wc: str, unicode_version: str = 'auto', ambiguous_width: int = 1) -> int:  # pylint: disable=unused-argument
    r"""
    Given one Unicode codepoint, return its printable length on a terminal.

    :param wc: A single Unicode character.
    :param unicode_version: Ignored. Retained for backwards compatibility.

        .. deprecated:: 0.3.0
           Only the latest Unicode version is now shipped.

    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts
        where ambiguous characters display as double-width. See
        :ref:`ambiguous_width` for details.
    :returns: The width, in cells, necessary to display the character of
        Unicode string character, ``wc``.  Returns 0 if the ``wc`` argument has
        no printable effect on a terminal (such as NUL '\0'), -1 if ``wc`` is
        not printable, or has an indeterminate effect on the terminal, such as
        a control character.  Otherwise, the number of column positions the
        character occupies on a graphic terminal (1 or 2) is returned.

    See :ref:`Specification` for details of cell measurement.
    """
    ucs = ord(wc) if wc else 0

    # small optimization: early return of 1 for printable ASCII, this provides
    # approximately 40% performance improvement for mostly-ascii documents, with
    # less than 1% impact to others.
    if 32 <= ucs < 0x7f:
        return 1

    # C0/C1 control characters are -1 for compatibility with POSIX-like calls
    if ucs and ucs < 32 or 0x07F <= ucs < 0x0A0:
        return -1

    # Zero width
    if bisearch(ucs, _ZERO_WIDTH_TABLE):
        return 0

    # Wide (F/W categories)
    if bisearch(ucs, _WIDE_EASTASIAN_TABLE):
        return 2

    # Ambiguous width (A category) - only when ambiguous_width=2
    if ambiguous_width == 2 and bisearch(ucs, _AMBIGUOUS_TABLE):
        return 2

    return 1
