"""
This is a python implementation of wcwidth() and wcswidth().

https://github.com/jquast/wcwidth

from Markus Kuhn's C code, retrieved from:

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

Latest version: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
"""

# std imports
import os
import warnings
from functools import lru_cache

# local
from .bisearch import bisearch as _bisearch
from .table_vs16 import VS16_NARROW_TO_WIDE
from .table_wide import WIDE_EASTASIAN
from .table_zero import ZERO_WIDTH
from .control_codes import ILLEGAL_CTRL, VERTICAL_CTRL, HORIZONTAL_CTRL, ZERO_WIDTH_CTRL
from .escape_sequences import (ZERO_WIDTH_PATTERN,
                               CURSOR_LEFT_SEQUENCE,
                               CURSOR_RIGHT_SEQUENCE,
                               INDETERMINATE_EFFECT_SEQUENCE)
from .unicode_versions import list_versions

# Translation table to strip C0/C1 control characters for fast 'ignore' mode.
_CONTROL_CHAR_TABLE = str.maketrans('', '', (
    ''.join(chr(c) for c in range(0x00, 0x20)) +   # C0: NUL through US (including tab)
    '\x7f' +                                       # DEL
    ''.join(chr(c) for c in range(0x80, 0xa0))     # C1: U+0080-U+009F
))


@lru_cache(maxsize=1000)
def wcwidth(wc, unicode_version='auto'):
    r"""
    Given one Unicode codepoint, return its printable length on a terminal.

    :param str wc: A single Unicode character.
    :param str unicode_version: A Unicode version number, such as
        ``'6.0.0'``. A list of version levels suported by wcwidth
        is returned by :func:`list_versions`.

        Any version string may be specified without error -- the nearest
        matching version is selected.  When ``'auto'`` (default), the
        ``UNICODE_VERSION`` environment variable is used if set, otherwise
        the highest Unicode version level is used.

        .. deprecated:: 0.2.14

            This parameter is deprecated. Empirical data shows that Unicode
            support in terminals varies not only by unicode version, but
            by capabilities, Emojis, and specific language support.

            The default ``'auto'`` behavior is recommended for all use cases.

    :return: The width, in cells, necessary to display the character of
        Unicode string character, ``wc``.  Returns 0 if the ``wc`` argument has
        no printable effect on a terminal (such as NUL '\0'), -1 if ``wc`` is
        not printable, or has an indeterminate effect on the terminal, such as
        a control character.  Otherwise, the number of column positions the
        character occupies on a graphic terminal (1 or 2) is returned.
    :rtype: int

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

    _unicode_version = _wcmatch_version(unicode_version)

    # Zero width
    if _bisearch(ucs, ZERO_WIDTH[_unicode_version]):
        return 0

    # 1 or 2 width
    return 1 + _bisearch(ucs, WIDE_EASTASIAN[_unicode_version])


def wcswidth(pwcs, n=None, unicode_version='auto'):
    """
    Given a unicode string, return its printable length on a terminal.

    :param str pwcs: Measure width of given unicode string.
    :param int n: When ``n`` is None (default), return the length of the entire
        string, otherwise only the first ``n`` characters are measured. This
        argument exists only for compatibility with the C POSIX function
        signature. It is suggested instead to use python's string slicing
        capability, ``wcswidth(pwcs[:n])``
    :param str unicode_version: A Unicode version number, such as
        ``'6.0.0'``, or ``'auto'`` (default) which uses the
        ``UNICODE_VERSION`` environment variable if defined, or the latest
        available unicode version otherwise.

        .. deprecated:: 0.2.14

            This parameter is deprecated. Empirical data shows that Unicode
            support in terminals varies not only by unicode version, but
            by capabilities, Emojis, and specific language support.

            The default ``'auto'`` behavior is recommended for all use cases.

    :rtype: int
    :returns: The width, in cells, needed to display the first ``n`` characters
        of the unicode string ``pwcs``.  Returns ``-1`` for C0 and C1 control
        characters!

    See :ref:`Specification` for details of cell measurement.
    """
    # this 'n' argument is a holdover for POSIX function
    _unicode_version = None
    end = len(pwcs) if n is None else n
    total_width = 0
    idx = 0
    last_measured_char = None
    while idx < end:
        char = pwcs[idx]
        if char == '\u200D':
            # Zero Width Joiner, do not measure this or next character
            idx += 2
            continue
        if char == '\uFE0F' and last_measured_char:
            # on variation selector 16 (VS16) following another character,
            # conditionally add '1' to the measured width if that character is
            # known to be converted from narrow to wide by the VS16 character.
            if _unicode_version is None:
                _unicode_version = _wcversion_value(_wcmatch_version(unicode_version))
            if _unicode_version >= (9, 0, 0):
                total_width += _bisearch(ord(last_measured_char),
                                         VS16_NARROW_TO_WIDE["9.0.0"])
                last_measured_char = None
            idx += 1
            continue
        # measure character at current index
        wcw = wcwidth(char, unicode_version)
        if wcw < 0:
            # early return -1 on C0 and C1 control characters
            return wcw
        if wcw > 0:
            # track last character measured to contain a cell, so that
            # subsequent VS-16 modifiers may be understood
            last_measured_char = char
        total_width += wcw
        idx += 1
    return total_width


@lru_cache(maxsize=128)
def _wcversion_value(ver_string):
    """
    Integer-mapped value of given dotted version string.

    :param str ver_string: Unicode version string, of form ``n.n.n``.
    :rtype: tuple(int)
    :returns: tuple of digit tuples, ``tuple(int, [...])``.
    """
    retval = tuple(map(int, (ver_string.split('.'))))
    return retval


@lru_cache(maxsize=8)
def _wcmatch_version(given_version):
    """
    Return nearest matching supported Unicode version level.

    If an exact match is not determined, the nearest lowest version level is
    returned after a warning is emitted.  For example, given supported levels
    ``4.1.0`` and ``5.0.0``, and a version string of ``4.9.9``, then ``4.1.0``
    is selected and returned:

    >>> _wcmatch_version('4.9.9')
    '4.1.0'
    >>> _wcmatch_version('8.0')
    '8.0.0'
    >>> _wcmatch_version('1')
    '4.1.0'

    :param str given_version: given version for compare, may be ``auto``
        (default), to select Unicode Version from Environment Variable,
        ``UNICODE_VERSION``. If the environment variable is not set, then the
        latest is used.
    :rtype: str
    :returns: unicode string.
    """
    # Design note: the choice to return the same type that is given certainly
    # complicates it for python 2 str-type, but allows us to define an api that
    # uses 'string-type' for unicode version level definitions, so all of our
    # example code works with all versions of python.
    #
    # That, along with the string-to-numeric and comparisons of earliest,
    # latest, matching, or nearest, greatly complicates this function.
    # Performance is somewhat curbed by memoization.

    unicode_versions = list_versions()
    latest_version = unicode_versions[-1]

    if given_version == 'auto':
        given_version = os.environ.get(
            'UNICODE_VERSION',
            'latest')

    if given_version == 'latest':
        # default match, when given as 'latest', use the most latest unicode
        # version specification level supported.
        return latest_version

    if given_version in unicode_versions:
        # exact match, downstream has specified an explicit matching version
        # matching any value of list_versions().
        return given_version

    # The user's version is not supported by ours. We return the newest unicode
    # version level that we support below their given value.
    try:
        cmp_given = _wcversion_value(given_version)

    except ValueError:
        # submitted value raises ValueError in int(), warn and use latest.
        warnings.warn(f"UNICODE_VERSION value, {given_version!r}, is invalid. "
                      "Value should be in form of `integer[.]+', the latest "
                      f"supported unicode version {latest_version!r} has been "
                      "inferred.")
        return latest_version

    # given version is less than any available version, return earliest
    # version.
    earliest_version = unicode_versions[0]
    cmp_earliest_version = _wcversion_value(earliest_version)

    if cmp_given <= cmp_earliest_version:
        # this probably isn't what you wanted, the oldest wcwidth.c you will
        # find in the wild is likely version 5 or 6, which we both support,
        # but it's better than not saying anything at all.
        warnings.warn(f"UNICODE_VERSION value, {given_version!r}, is lower "
                      "than any available unicode version. Returning lowest "
                      f"version level, {earliest_version!r}")
        return earliest_version

    # create list of versions which are less than our equal to given version,
    # and return the tail value, which is the highest level we may support,
    # or the latest value we support, when completely unmatched or higher
    # than any supported version.
    #
    # function will never complete, always returns.
    for idx, unicode_version in enumerate(unicode_versions):
        # look ahead to next value
        try:
            cmp_next_version = _wcversion_value(unicode_versions[idx + 1])
        except IndexError:
            # at end of list, return latest version
            return latest_version

        # Maybe our given version has less parts, as in tuple(8, 0), than the
        # next compare version tuple(8, 0, 0). Test for an exact match by
        # comparison of only the leading dotted piece(s): (8, 0) == (8, 0).
        if cmp_given == cmp_next_version[:len(cmp_given)]:
            return unicode_versions[idx + 1]

        # Or, if any next value is greater than our given support level
        # version, return the current value in index.  Even though it must
        # be less than the given value, it's our closest possible match. That
        # is, 4.1 is returned for given 4.9.9, where 4.1 and 5.0 are available.
        if cmp_next_version > cmp_given:
            return unicode_version
    assert False, ("Code path unreachable", given_version, unicode_versions)  # pragma: no cover


def iter_sequences(text):
    """
    Iterate through text, yielding segments with sequence identification.

    This generator yields tuples of ``(segment, is_sequence)`` for each part
    of the input text, where ``is_sequence`` is ``True`` if the segment is
    a recognized terminal escape sequence.

    :param str text: String to iterate through.
    :rtype: Iterator[tuple[str, bool]]
    :returns: Iterator of (segment, is_sequence) tuples.

    .. versionadded:: 0.2.15

    Example::

        >>> list(iter_sequences('hello'))
        [('hello', False)]
        >>> list(iter_sequences('\\x1b[31mred'))
        [('\\x1b[31m', True), ('red', False)]
        >>> list(iter_sequences('\\x1b[1m\\x1b[31m'))
        [('\\x1b[1m', True), ('\\x1b[31m', True)]
    """
    idx = 0
    text_len = len(text)
    segment_start = 0

    while idx < text_len:
        char = text[idx]

        if char == '\x1b':
            # Yield any accumulated non-sequence text
            if idx > segment_start:
                yield (text[segment_start:idx], False)

            # Try to match an escape sequence
            match = ZERO_WIDTH_PATTERN.match(text, idx)
            if match:
                yield (match.group(), True)
                idx = match.end()
            else:
                # Lone ESC or unrecognized - yield as sequence anyway
                yield (char, True)
                idx += 1
            segment_start = idx
        else:
            idx += 1

    # Yield any remaining text
    if segment_start < text_len:
        yield (text[segment_start:], False)


def _width_ignored_codes(text):
    """
    Fast path for width() with control_codes='ignore'.

    Strips escape sequences and control characters, then measures remaining text.
    """
    return wcswidth(
        ''.join([seg for seg, is_seq in iter_sequences(text) if not is_seq])
        .translate(_CONTROL_CHAR_TABLE)
    )


def width(text, control_codes='parse', tabstop=8, column=0):
    """
    Return printable width of text containing many kinds of control codes and sequences.

    Unlike :func:`wcswidth`, this function handles most control characters and many popular terminal
    output sequences.  Never returns -1.

    :param str text: String to measure.
    :param str control_codes: How to handle control characters and sequences:

        - ``'parse'`` (default): Track horizontal cursor movement from BS ``\\b``, CR ``\\r``, TAB
          ``\\t``, and cursor left and right movement sequences.  Vertical movement (LF, VT, FF) and
          indeterminate sequences are zero-width. Never raises.
        - ``'strict'``: Like parse, but raises :exc:`ValueError` on control characters with
          indeterminate results of the screen or cursor, like clear or vertical movement. Generally,
          these should be handled with a virtual terminal emulator (like 'pyte').
        - ``'ignore'``: All C0 and C1 control characters and escape sequences are measured as
          width 0. This is the fastest measurement for text already filtered or known not to contain
          any kinds of control codes or sequences. TAB ``\\t`` is zero-width; for tab expansion,
          pre-process: ``text.replace('\\t', ' ' * 8)``.

    :param int tabstop: Tab stop width for ``'parse'`` and ``'strict'`` modes. Default is 8.
        Must be positive. Has no effect when ``control_codes='ignore'``.
    :param int column: Starting column position for tabstop and movement calculations. Has no effect
        when ``control_codes='ignore'``.
    :rtype: int
    :returns: Maximum cursor position reached, "extent", accounting for cursor movement sequences
        present in ``text`` according to given parameters.  This represents the rightmost column the
        cursor reaches.  Always a non-negative integer.

    :raises ValueError: If ``control_codes='strict'`` and control characters with indeterminate
        effects, such as vertical movement or clear sequences are encountered, or on unexpected
        C0 or C1 control code. Also raised when ``control_codes`` is not one of the valid values.

    .. versionadded:: 0.2.15

    Examples::

        >>> width('hello')
        5
        >>> width('コンニチハ')
        10
        >>> width('\\x1b[31mred\\x1b[0m')
        3
        >>> width('\\x1b[31mred\\x1b[0m', control_codes='ignore')  # same result (ignored)
        3
        >>> width('123\\b4')     # backspace overwrites previous cell (outputs '124')
        3
        >>> width('abc\\t')      # tab caused cursor to move to column 8
        8
        >>> width('1\\x1b[10C')  # '1' + cursor right 10, cursor ends on column 11
        11
        >>> width('1\\x1b[10C', control_codes='ignore')   # faster but wrong in this case
        1
    """
    # pylint: disable=too-complex,too-many-branches,too-many-statements
    # This could be broken into sub-functions (#1 and #3), but for reduced overhead considering this
    # function is a likely "hot path", they are inlined, breaking our many complexity rules.  Fear
    # not, there are many tests!
    if control_codes not in ('ignore', 'strict', 'parse'):
        raise ValueError(
            f"control_codes must be 'ignore', 'strict', or 'parse', "
            f"got {control_codes!r}"
        )

    # Fast path for ignore mode
    if control_codes == 'ignore':
        return _width_ignored_codes(text)

    strict = control_codes == 'strict'
    # Track absolute positions: tab stops need modulo on absolute column, CR resets to 0.
    # Initialize max_extent to column so backward movement (CR, BS) won't yield negative width.
    # Subtract column at return to convert absolute max position to relative width.
    current_col = column
    max_extent = column
    idx = 0

    while idx < len(text):
        char = text[idx]

        # 1. Handle ESC sequences
        if char == '\x1b':
            match = ZERO_WIDTH_PATTERN.match(text, idx)
            if match:
                seq = match.group()
                if strict and INDETERMINATE_EFFECT_SEQUENCE.match(seq):
                    raise ValueError(f"Indeterminate cursor sequence at position {idx}")
                # Apply cursor movement
                right = CURSOR_RIGHT_SEQUENCE.match(seq)
                if right:
                    current_col += int(right.group(1) or 1)
                else:
                    left = CURSOR_LEFT_SEQUENCE.match(seq)
                    if left:
                        current_col = max(0, current_col - int(left.group(1) or 1))
                idx = match.end()
            else:
                idx += 1
            max_extent = max(max_extent, current_col)
            continue

        # 2. Handle illegal and vertical control characters (zero width, error in strict)
        if char in ILLEGAL_CTRL:
            if strict:
                raise ValueError(f"Illegal control character {ord(char):#x} at position {idx}")
            idx += 1
            continue

        if char in VERTICAL_CTRL:
            if strict:
                raise ValueError(f"Vertical movement character {ord(char):#x} at position {idx}")
            idx += 1
            continue

        # 3. Handle horizontal movement characters
        if char in HORIZONTAL_CTRL:
            if char == '\x09' and tabstop > 0:  # Tab
                current_col += tabstop - (current_col % tabstop)
            elif char == '\x08':  # Backspace
                if current_col > 0:
                    current_col -= 1
            elif char == '\x0d':  # Carriage return
                current_col = 0
            max_extent = max(max_extent, current_col)
            idx += 1
            continue

        # 4. Handle ZWJ (skip this and next character)
        if char == '\u200D':
            idx += 2
            continue

        # 5. Handle other zero-width characters (control chars and VS-16)
        if char in ZERO_WIDTH_CTRL or char == '\uFE0F':
            idx += 1
            continue

        # 6. Normal characters: measure with wcwidth
        w = wcwidth(char)
        if w > 0:
            current_col += w
            max_extent = max(max_extent, current_col)
        idx += 1

    return max_extent - column


def ljust(text, dest_width, fillchar=' ', control_codes='parse'):
    """
    Return text left-justified in a string of given display width.

    :param str text: String to justify, may contain terminal sequences.
    :param int dest_width: Total display width of result in terminal cells.
    :param str fillchar: Character for padding (default space). May be multi-cell.
    :param str control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :returns: Text padded on the right to reach width.
    :rtype: str
    :raises ValueError: If fillchar has no positive display width.

    .. versionadded:: 0.2.15

    Example::

        >>> ljust('hi', 5)
        'hi   '
        >>> ljust('\\x1b[31mhi\\x1b[0m', 5)
        '\\x1b[31mhi\\x1b[0m   '
    """
    text_width = width(text, control_codes=control_codes)
    fillchar_width = width(fillchar, control_codes='ignore')
    if fillchar_width < 1:
        raise ValueError(f"fillchar must have positive display width, got '{fillchar}'")
    padding_cells = max(0, dest_width - text_width)
    fill_count = padding_cells // fillchar_width
    return text + fillchar * fill_count


def rjust(text, dest_width, fillchar=' ', control_codes='parse'):
    """
    Return text right-justified in a string of given display width.

    :param str text: String to justify, may contain terminal sequences.
    :param int dest_width: Total display width of result in terminal cells.
    :param str fillchar: Character for padding (default space). May be multi-cell.
    :param str control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :returns: Text padded on the left to reach width.
    :rtype: str
    :raises ValueError: If fillchar has no positive display width.

    .. versionadded:: 0.2.15

    Example::

        >>> rjust('hi', 5)
        '   hi'
        >>> rjust('\\x1b[31mhi\\x1b[0m', 5)
        '   \\x1b[31mhi\\x1b[0m'
    """
    text_width = width(text, control_codes=control_codes)
    fillchar_width = width(fillchar, control_codes='ignore')
    if fillchar_width < 1:
        raise ValueError(f"fillchar must have positive display width, got '{fillchar}'")
    padding_cells = max(0, dest_width - text_width)
    fill_count = padding_cells // fillchar_width
    return fillchar * fill_count + text


def center(text, dest_width, fillchar=' ', control_codes='parse'):
    """
    Return text centered in a string of given display width.

    :param str text: String to center, may contain terminal sequences.
    :param int dest_width: Total display width of result in terminal cells.
    :param str fillchar: Character for padding (default space). May be multi-cell.
    :param str control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :returns: Text padded on both sides to reach width.
    :rtype: str
    :raises ValueError: If fillchar has no positive display width.

    For odd-width padding, the extra cell goes on the right (matching
    Python's :meth:`str.center` behavior).

    .. versionadded:: 0.2.15

    Example::

        >>> center('hi', 6)
        '  hi  '
        >>> center('hi', 5)
        ' hi  '
    """
    text_width = width(text, control_codes=control_codes)
    fillchar_width = width(fillchar, control_codes='ignore')
    if fillchar_width < 1:
        raise ValueError(f"fillchar must have positive display width, got '{fillchar}'")
    total_padding = max(0, dest_width - text_width)
    left_cells = total_padding // 2
    right_cells = total_padding - left_cells
    left_count = left_cells // fillchar_width
    right_count = right_cells // fillchar_width
    return fillchar * left_count + text + fillchar * right_count
