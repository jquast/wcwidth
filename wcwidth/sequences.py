"""
Sequence-aware text manipulation functions.

This module provides functions for manipulating text that may contain
terminal escape sequences, with proper handling of Unicode grapheme
clusters and character display widths.
"""
from typing import Iterator, Tuple

from .escape_sequences import ZERO_WIDTH_PATTERN
# Import width() as _width to avoid collision with 'width' parameter in function signatures
from .wcwidth import width as _width


def iter_sequences(text: str) -> Iterator[Tuple[str, bool]]:
    """
    Iterate over text, yielding (segment, is_sequence) tuples.

    :param text: String that may contain terminal escape sequences.
    :yields: Tuples of ``(segment_text, is_sequence)`` where ``is_sequence``
        is ``True`` for escape sequences, ``False`` for plain text runs.

    This function separates terminal escape sequences from printable text,
    yielding whole runs of non-sequence content for efficiency.

    Example::

        >>> list(iter_sequences('\\x1b[31mred\\x1b[0m'))
        [('\\x1b[31m', True), ('red', False), ('\\x1b[0m', True)]
    """
    idx = 0
    text_len = len(text)
    while idx < text_len:
        char = text[idx]
        if char == '\x1b':
            match = ZERO_WIDTH_PATTERN.match(text, idx)
            if match:
                yield (match.group(), True)
                idx = match.end()
                continue
        # Collect non-sequence characters into a single run
        start = idx
        while idx < text_len:
            if text[idx] == '\x1b' and ZERO_WIDTH_PATTERN.match(text, idx):
                break
            idx += 1
        yield (text[start:idx], False)


def ljust(text: str, width: int, fillchar: str = ' ',
          control_codes: str = 'parse') -> str:
    """
    Return text left-justified in a string of given display width.

    :param text: String to justify, may contain terminal sequences.
    :param width: Total display width of result in terminal cells.
    :param fillchar: Character for padding (default space). May be multi-cell.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :returns: Text padded on the right to reach width.

    Example::

        >>> ljust('hi', 5)
        'hi   '
        >>> ljust('\\x1b[31mhi\\x1b[0m', 5)
        '\\x1b[31mhi\\x1b[0m   '
    """
    text_width = _width(text, control_codes=control_codes)
    fillchar_width = _width(fillchar, control_codes='ignore')
    if fillchar_width < 1:
        raise ValueError(f"fillchar must have positive display width, got '{fillchar}'")
    padding_cells = max(0, width - text_width)
    fill_count = padding_cells // fillchar_width
    return text + fillchar * fill_count


def rjust(text: str, width: int, fillchar: str = ' ',
          control_codes: str = 'parse') -> str:
    """
    Return text right-justified in a string of given display width.

    :param text: String to justify, may contain terminal sequences.
    :param width: Total display width of result in terminal cells.
    :param fillchar: Character for padding (default space). May be multi-cell.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :returns: Text padded on the left to reach width.

    Example::

        >>> rjust('hi', 5)
        '   hi'
        >>> rjust('\\x1b[31mhi\\x1b[0m', 5)
        '   \\x1b[31mhi\\x1b[0m'
    """
    text_width = _width(text, control_codes=control_codes)
    fillchar_width = _width(fillchar, control_codes='ignore')
    if fillchar_width < 1:
        raise ValueError(f"fillchar must have positive display width, got '{fillchar}'")
    padding_cells = max(0, width - text_width)
    fill_count = padding_cells // fillchar_width
    return fillchar * fill_count + text


def center(text: str, width: int, fillchar: str = ' ',
           control_codes: str = 'parse') -> str:
    """
    Return text centered in a string of given display width.

    :param text: String to center, may contain terminal sequences.
    :param width: Total display width of result in terminal cells.
    :param fillchar: Character for padding (default space). May be multi-cell.
    :param control_codes: How to handle control sequences when measuring.
        Passed to :func:`width` for measurement.
    :returns: Text padded on both sides to reach width.

    For odd-width padding, the extra cell goes on the right (matching
    Python's :meth:`str.center` behavior).

    Example::

        >>> center('hi', 6)
        '  hi  '
        >>> center('hi', 5)
        ' hi  '
    """
    text_width = _width(text, control_codes=control_codes)
    fillchar_width = _width(fillchar, control_codes='ignore')
    if fillchar_width < 1:
        raise ValueError(f"fillchar must have positive display width, got '{fillchar}'")
    total_padding = max(0, width - text_width)
    left_cells = total_padding // 2
    right_cells = total_padding - left_cells
    left_count = left_cells // fillchar_width
    right_count = right_cells // fillchar_width
    return fillchar * left_count + text + fillchar * right_count
