"""
This is an implementation of wcwidth() and wcswidth().

Defined in IEEE Std 1002.1-2001.

https://github.com/jquast/wcwidth

from Markus Kuhn's C code at:

    http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c

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

Markus Kuhn -- 2007-05-26 (Unicode 5.0)

Permission to use, copy, modify, and distribute this software
for any purpose and without fee is hereby granted. The author
disclaims all warranties with regard to this software.

Latest version: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
"""
# std imports
from __future__ import division
import pkg_resources
import json

# local
from .table_wide import WIDE_EASTASIAN
from .table_zero import ZERO_WIDTH

_UNICODE_VERSIONS = None

def _bisearch(ucs, table):
    """
    Auxiliary function for binary search in interval table.

    :arg int ucs: Ordinal value of unicode character.
    :arg list table: List of starting and ending ranges of ordinal values,
        in form of ``[(start, end), ...]``.
    :rtype: int
    :returns: 1 if ordinal value ucs is found within lookup table, else 0.
    """
    lbound = 0
    ubound = len(table) - 1

    if ucs < table[0][0] or ucs > table[ubound][1]:
        return 0
    while ubound >= lbound:
        mid = (lbound + ubound) // 2
        if ucs > table[mid][1]:
            lbound = mid + 1
        elif ucs < table[mid][0]:
            ubound = mid - 1
        else:
            return 1

    return 0


def wcwidth(wc, unicode_version='latest'):
    r"""
    Given one Unicode character, return its printable length on a terminal.

    :param str wc: A single Unicode character.
    :param str unicode_version: A Unicode version number, such as
        ``'6.0.0'``, the list of available version levels may be
        listed by pairing function :func:`get_supported_unicode_versions`.
        Any version string may be specified without error -- the nearest
        matching version is selected.  When ``latest`` (default), the
        highest Unicode version level is used.
    :returns: The width, in cells, necessary to display the character of
        Unicode string character, ``wc``.  Returns 0 if the ``wc`` argument has
        no printable effect on a terminal (such as NUL '\0'), -1 if ``wc`` is
        not printable, or has an indeterminate effect on the terminal, such as
        a control character.  Otherwise, the number of column positions the
        character occupies on a graphic terminal (1 or 2) is returned.

    The following have a column width of -1:

        - C0 control characters (U+001 through U+01F).

        - C1 control characters and DEL (U+07F through U+0A0).

    The following have a column width of 0:

    - Non-spacing and enclosing combining characters (general
      category code Mn or Me in the Unicode database).

    - NULL (``U+0000``).

    - COMBINING GRAPHEME JOINER (``U+034F``).

    - ZERO WIDTH SPACE (``U+200B``) *through*
      RIGHT-TO-LEFT MARK (``U+200F``).

    - LINE SEPARATOR (``U+2028``) *and*
      PARAGRAPH SEPARATOR (``U+2029``).

    - LEFT-TO-RIGHT EMBEDDING (``U+202A``) *through*
      RIGHT-TO-LEFT OVERRIDE (``U+202E``).

    - WORD JOINER (``U+2060``) *through*
      INVISIBLE SEPARATOR (``U+2063``).

    The following have a column width of 1:

    - SOFT HYPHEN (``U+00AD``).

    - All remaining characters, including all printable ISO 8859-1
      and WGL4 characters, Unicode control characters, etc.

    The following have a column width of 2:

    - Spacing characters in the East Asian Wide (W) or East Asian
      Full-width (F) category as defined in Unicode Technical
      Report #11 have a column width of 2.

    - Some kinds of emjoi or symbols.
    """
    # pylint: disable=C0103
    #         Invalid argument name "wc"
    ucs = ord(wc)

    _unicode_version = match_version(unicode_version)

    # NOTE: created by hand, there isn't anything identifiable other than
    # general Cf category code to identify these, and some characters in Cf
    # category code are of non-zero width.
    #
    # pylint: disable=too-many-boolean-expressions
    #          Too many boolean expressions in if statement (7/5)
    if (ucs == 0 or
            ucs == 0x034F or
            0x200B <= ucs <= 0x200F or
            ucs == 0x2028 or
            ucs == 0x2029 or
            0x202A <= ucs <= 0x202E or
            0x2060 <= ucs <= 0x2063):
        return 0

    # C0/C1 control characters
    if ucs < 32 or 0x07F <= ucs < 0x0A0:
        return -1

    # combining characters with zero width
    if _bisearch(ucs, ZERO_WIDTH[_unicode_version]):
        return 0

    return 1 + _bisearch(ucs, WIDE_EASTASIAN[_unicode_version])


def wcswidth(pwcs, n=None, unicode_version='latest'):
    """
    Given a unicode string, return its printable length on a terminal.

    :param str pwcs: Measure width of given unicode string.
    :param int n: When ``n`` is None (default), return the length of the
        entire string, otherwise width the first ``n`` characters specified.
    :returns: The width, in cells, necessary to display the first ``n``
        characters of the unicode string ``pwcs``.  Returns ``-1`` if
        a non-printable character is encountered.
    """
    # pylint: disable=C0103
    #         Invalid argument name "n"

    end = len(pwcs) if n is None else n
    idx = slice(0, end)
    width = 0
    for char in pwcs[idx]:
        wcw = wcwidth(char, unicode_version=unicode_version)
        if wcw < 0:
            return -1
        else:
            width += wcw
    return width


def _validate_unicode_versions(unicode_versions):
    """
    Validate given unicode_versions array is ascending sorted order.
    """
    # On first table load, perform validation
    for cur_version in _UNICODE_VERSIONS[1:]:
        prev_idx = _UNICODE_VERSIONS.index(cur_version) - 1
        if prev_idx >= 0:
            prev_version = _UNICODE_VERSIONS[prev_idx]
            cmp_current = distutils.version.LooseVersion(cur_version)
            cmp_previous = distutils.version.LooseVersion(prev_version)
            assert cmp_current < cmp_previous, (
                "The unicode version strings specified in project file "
                "'version.json', key 'unicode' must be in ascending "
                "sorted order, failed validation at index {prev_idx}: "
                "{prev_version} < {cur_version}".format(
                    prev_idx=prev_idx,
                    prev_version=prev_version,
                    cur_version=cur_version))


def get_supported_unicode_versions():
    """
    Return Unicode version levels supported by this module release.

    Any of the version strings returned may be used as keyword argument
    ``unicode_version`` to the ``wcwidth()`` family of functions.

    :returns: Supported Unicode version numbers in ascending sorted order.
    :rtype: list[str]
    """
    # global cache to avoid excessive disk i/o
    global _UNICODE_VERSIONS
    if _UNICODE_VERSIONS is None:
        # load from 'version.json', use setuptools to access
        # resource string so that the package is zip/wheel-compatible.
        _UNICODE_VERSIONS = json.loads(
            pkg_resources.resource_string(
                'wcwidth', "version.json"
            ).decode('utf8'))['unicode']

        _validate_unicode_versions(_UNICODE_VERSIONS)
    return _UNICODE_VERSIONS


def match_version(given_version):
    """
    Return nearest matching supported Unicode version level for given version.

    If an exact match is not determined, the nearest version lowest version
    level is returned.  For example, given supported levels '4.1.0' and
    '5.0.0':

    >>> match_version('4.9.9')
    '4.1.0'

    :param str version: XXX
    :rtype: str
    """
    unicode_versions = get_supported_unicode_versions()
    if given_version == 'latest':
        return unicode_versions[-1]
    if given_version in unicode_versions:
        return given_version
    for match_version in unicode_versions:
        prev_version = unicode_versions.index(match_version) - 1
#        if prev_version >= 0:

#    for idx, match_version in enumerate(unicode_versions):
#
#        prev_idx = _UNICODE_VERSIONS.index(cur_version) - 1
#        if prev_idx >= 0:
#            prev_version = _UNICODE_VERSIONS[prev_idx]
#            cmp_current = distutils.version.LooseVersion(cur_version)
#            cmp_previous = distutils.version.LooseVersion(prev_version)
   
#   if match_version not in unicode_versions:
#       given_version = distutils.version.LooseVersion(version)
#       sorted_versions = sorted(
#           [distutils.version.LooseVersion(ver)
#            for ver in wcwidth.get_supported_unicode_versions()],
#           reverse=True)
#       for idx, match_version in sorted_versions:
#           if given_version < match_version:
#               if idx:
#                   return sorted_versions[idx - 1]
#               return sorted_versions[0]
