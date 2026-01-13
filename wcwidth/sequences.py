"""
Sequence-aware text manipulation functions.

This module provides functions for manipulating text that may contain
terminal escape sequences, with proper handling of Unicode grapheme
clusters and character display widths.
"""
import math
import re
import textwrap
from typing import Iterator, List, Optional, Tuple

from .grapheme import iter_graphemes
from .terminal_seqs import (
    TERM_SEQ_PATTERN,
    SGR_PATTERN,
    CURSOR_RIGHT_PATTERN,
    CURSOR_LEFT_PATTERN,
    INDETERMINATE_SEQ_PATTERN,
    ILLEGAL_CTRL,
    VERTICAL_CTRL,
    HORIZONTAL_CTRL,
)
# Import width() as _width to avoid collision with 'width' parameter in function signatures
from .wcwidth import width as _width, wcwidth


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
            match = TERM_SEQ_PATTERN.match(text, idx)
            if match:
                yield (match.group(), True)
                idx = match.end()
                continue
        # Collect non-sequence characters into a single run
        start = idx
        while idx < text_len:
            if text[idx] == '\x1b' and TERM_SEQ_PATTERN.match(text, idx):
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


def _is_movement_sequence(seq: str) -> bool:
    """Check if sequence causes cursor movement."""
    return bool(
        CURSOR_RIGHT_PATTERN.match(seq) or
        CURSOR_LEFT_PATTERN.match(seq) or
        INDETERMINATE_SEQ_PATTERN.match(seq)
    )


def truncate(text: str, start: int, end: int,
             control_codes: str = 'parse',
             cutwide_padding: str = ' ') -> str:
    """
    Truncate text to display positions [start, end).

    :param text: String to truncate, may contain terminal sequences.
    :param start: Starting cell position (inclusive, 0-indexed).
    :param end: Ending cell position (exclusive).
    :param control_codes: How to handle control sequences:

        - ``'parse'``: Re-emit non-movement sequences outside the range.
        - ``'ignore'``: Strip all sequences.
        - ``'strict'``: Raise on problematic sequences.

    :param cutwide_padding: When a wide character is partially cut,
        use this character as padding. Empty string ``''`` to omit padding.
    :returns: Text truncated to the specified cell range.

    Wide characters (CJK, emoji) occupy 2 cells. If truncation cuts
    through a wide character, it is removed and replaced with
    ``cutwide_padding`` (if provided).

    Example::

        >>> truncate('abcde', 1, 4)
        'bcd'
        >>> truncate('a\u4e2d\u6587b', 1, 3)  # 中文 are wide chars
        '\u4e2d'
        >>> truncate('a\u4e2db', 2, 4)  # Cut through 中
        ' b'
    """
    if start < 0:
        raise ValueError(f"start must be non-negative, got {start}")
    if end < start:
        raise ValueError(f"end must be >= start, got start={start}, end={end}")

    prefix_seqs: List[str] = []
    result_chars: List[str] = []
    suffix_seqs: List[str] = []

    current_col = 0
    past_end = False

    idx = 0
    text_len = len(text)

    while idx < text_len:
        char = text[idx]

        # Check for escape sequence
        if char == '\x1b':
            match = TERM_SEQ_PATTERN.match(text, idx)
            if match:
                seq = match.group()
                idx = match.end()

                if control_codes == 'ignore':
                    continue
                if control_codes == 'strict' and INDETERMINATE_SEQ_PATTERN.match(seq):
                    raise ValueError(f"indeterminate cursor position: {seq!r}")

                # Categorize sequence by position
                is_movement = _is_movement_sequence(seq)
                if not is_movement:
                    if current_col < start:
                        prefix_seqs.append(seq)
                    elif past_end:
                        suffix_seqs.append(seq)
                    else:
                        result_chars.append(seq)
                continue

        # Check for control characters
        if char in ILLEGAL_CTRL:
            if control_codes == 'strict':
                raise ValueError(f"illegal control character: {ord(char):#x}")
            idx += 1
            continue
        if char in VERTICAL_CTRL:
            if control_codes == 'strict':
                raise ValueError(f"vertical control character: {ord(char):#x}")
            idx += 1
            continue

        # Handle regular character - get full grapheme from this position
        # For proper grapheme handling, we need to find the grapheme boundary
        remaining = text[idx:]
        grapheme = next(iter_graphemes(remaining), '')
        if not grapheme:  # pragma: no cover
            idx += 1
            continue

        # Use _width for proper ZWJ sequence handling
        grapheme_width = _width(grapheme, control_codes='ignore')

        char_start = current_col
        char_end = current_col + grapheme_width

        # Check if grapheme falls within [start, end)
        if char_end <= start:
            # Entirely before visible range
            pass
        elif char_start >= end:
            # Entirely after visible range
            past_end = True
        elif char_start < start:
            # Left edge cut through grapheme (wide char partially visible)
            if cutwide_padding:
                # Pad for the portion that would be visible
                visible_portion = char_end - start
                result_chars.append(cutwide_padding * visible_portion)
        elif char_end > end:
            # Right edge cut through grapheme (wide char partially visible)
            if cutwide_padding:
                # Pad for the portion that would be visible
                visible_portion = end - char_start
                result_chars.append(cutwide_padding * visible_portion)
            past_end = True
        else:
            # Fully within visible range
            result_chars.append(grapheme)

        current_col = char_end
        idx += len(grapheme)

    if control_codes == 'parse':
        return ''.join(prefix_seqs + result_chars + suffix_seqs)
    else:
        return ''.join(result_chars)


class SequenceTextWrapper(textwrap.TextWrapper):
    """
    Sequence-aware text wrapper extending :class:`textwrap.TextWrapper`.

    This wrapper properly handles terminal escape sequences and Unicode
    grapheme clusters when calculating text width for wrapping.
    """

    def __init__(self, width: int = 70,
                 control_codes: str = 'parse',
                 break_on_graphemes: bool = True,
                 tabstop: int = 8,
                 column: int = 0,
                 **kwargs):
        """
        Initialize the wrapper.

        :param width: Maximum line width in display cells.
        :param control_codes: How to handle control sequences.
        :param break_on_graphemes: If True, break words at grapheme
            boundaries when they exceed width.
        :param tabstop: Tab stop width for tab expansion.
        :param column: Starting column for width calculation.
        :param kwargs: Additional arguments passed to TextWrapper.
        """
        super().__init__(width=width, **kwargs)
        self.control_codes = control_codes
        self.break_on_graphemes = break_on_graphemes
        self.tabstop = tabstop
        self.column = column

    def _width(self, text: str) -> int:
        """Measure text width accounting for sequences."""
        return _width(text, control_codes=self.control_codes,
                            tabstop=self.tabstop, column=self.column)

    def _strip_sequences(self, text: str) -> str:
        """Strip all terminal sequences from text."""
        result = []
        for segment, is_seq in iter_sequences(text):
            if not is_seq:
                result.append(segment)
        return ''.join(result)

    def _split(self, text: str) -> List[str]:
        """
        Split text into chunks, preserving sequences.

        Override TextWrapper._split to handle sequences properly.
        """
        # Build mapping from stripped text positions to original positions
        stripped = []
        pos_map = []  # Maps stripped position to original position

        for segment, is_seq in iter_sequences(text):
            if is_seq:
                # Sequences get zero length in stripped, but we need to track them
                continue
            for char in segment:
                pos_map.append(len(''.join(stripped)))
                stripped.append(char)

        stripped_text = ''.join(stripped)

        # Use parent's _split on stripped text
        # But we need to preserve sequences, so we'll do a custom split
        # that maintains sequence associations

        # Split on whitespace while preserving sequences
        chunks = []
        current_chunk = []
        in_word = False

        for segment, is_seq in iter_sequences(text):
            if is_seq:
                current_chunk.append(segment)
            else:
                for char in segment:
                    if char.isspace():
                        if in_word:
                            # End of word
                            chunks.append(''.join(current_chunk))
                            current_chunk = [char]
                            in_word = False
                        else:
                            current_chunk.append(char)
                    else:
                        if not in_word and current_chunk:
                            # End of whitespace run
                            chunks.append(''.join(current_chunk))
                            current_chunk = []
                        current_chunk.append(char)
                        in_word = True

        if current_chunk:
            chunks.append(''.join(current_chunk))

        return chunks

    def _wrap_chunks(self, chunks: List[str]) -> List[str]:
        """
        Wrap chunks into lines using sequence-aware width.

        Override TextWrapper._wrap_chunks to use _width instead of len.
        """
        if not chunks:
            return []

        lines = []
        current_line = []
        current_width = 0
        is_first_line = True

        # Get the indent for current line
        def get_indent():
            return self.initial_indent if is_first_line else self.subsequent_indent

        # Calculate available width after indent
        def get_available_width():
            return self.width - self._width(get_indent())

        for chunk in chunks:
            chunk_width = self._width(chunk)
            stripped_chunk = chunk.strip()

            if not stripped_chunk:
                # Whitespace-only chunk
                if current_line:
                    # Add space between words if room
                    if current_width + chunk_width <= get_available_width():
                        current_line.append(chunk)
                        current_width += chunk_width
                continue

            # Check if chunk fits
            if current_width + chunk_width <= get_available_width():
                current_line.append(chunk)
                current_width += chunk_width
            elif not current_line:
                # First word on line and it's too long
                self._handle_long_word(chunk, lines, current_line, is_first_line)
                current_width = self._width(''.join(current_line))
            else:
                # Start new line
                lines.append(get_indent() + ''.join(current_line).rstrip())
                is_first_line = False
                current_line = [chunk]
                current_width = chunk_width

        if current_line:
            lines.append(get_indent() + ''.join(current_line).rstrip())

        return lines

    def _handle_long_word(self, word: str, lines: List[str],
                          current_line: List[str],
                          is_first_line: bool = True) -> None:
        """
        Handle a word that exceeds the line width.

        If break_on_graphemes is True, break the word at grapheme boundaries.
        """
        if not self.break_long_words:
            current_line.append(word)
            return

        def get_indent(first_line: bool) -> str:
            return self.initial_indent if first_line else self.subsequent_indent

        def get_available_width(first_line: bool) -> int:
            return self.width - self._width(get_indent(first_line))

        if self.break_on_graphemes:
            # Break at grapheme boundaries
            remaining = word
            line_chars = []
            line_width = 0
            first_line = is_first_line

            # Iterate through sequences and graphemes
            idx = 0
            word_len = len(remaining)

            while idx < word_len:
                char = remaining[idx]

                # Check for escape sequence
                if char == '\x1b':
                    match = TERM_SEQ_PATTERN.match(remaining, idx)
                    if match:
                        seq = match.group()
                        line_chars.append(seq)
                        idx = match.end()
                        continue

                # Get grapheme starting at this position
                grapheme = next(iter_graphemes(remaining[idx:]), '')
                if not grapheme:  # pragma: no cover
                    idx += 1
                    continue

                grapheme_width = self._width(grapheme)
                available = get_available_width(first_line and not lines)

                if line_width + grapheme_width > available and line_chars:
                    # Line is full, start new line
                    indent = get_indent(first_line and not lines)
                    if current_line:
                        lines.append(indent + ''.join(current_line))
                        current_line.clear()
                        first_line = False
                    else:
                        lines.append(indent + ''.join(line_chars))
                        first_line = False
                    line_chars = []
                    line_width = 0

                line_chars.append(grapheme)
                line_width += grapheme_width
                idx += len(grapheme)

            if line_chars:
                current_line.extend(line_chars)
        else:
            # Simple character-by-character break (original behavior)
            current_line.append(word)


def wrap(text: str, width: int,
         control_codes: str = 'parse',
         break_on_graphemes: bool = True,
         tabstop: int = 8,
         column: int = 0,
         initial_indent: str = '',
         subsequent_indent: str = '',
         break_long_words: bool = True,
         break_on_hyphens: bool = True) -> List[str]:
    """
    Wrap text to fit within given width.

    :param text: Text to wrap, may contain terminal sequences.
    :param width: Maximum line width in display cells.
    :param control_codes: How to handle control sequences.
    :param break_on_graphemes: If True, break words at grapheme
        boundaries when they exceed width.
    :param tabstop: Tab stop width for tab expansion.
    :param column: Starting column for first line.
    :param initial_indent: Prefix for first line.
    :param subsequent_indent: Prefix for subsequent lines.
    :param break_long_words: Break words that exceed width.
    :param break_on_hyphens: Break on hyphens in words.
    :returns: List of wrapped lines.

    Example::

        >>> wrap('hello world', 5)
        ['hello', 'world']
        >>> wrap('abcdefghij', 3, break_on_graphemes=True)
        ['abc', 'def', 'ghi', 'j']
    """
    wrapper = SequenceTextWrapper(
        width=width,
        control_codes=control_codes,
        break_on_graphemes=break_on_graphemes,
        tabstop=tabstop,
        column=column,
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        break_long_words=break_long_words,
        break_on_hyphens=break_on_hyphens,
    )
    return wrapper.wrap(text)
