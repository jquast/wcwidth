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


class SequenceTextWrapper(textwrap.TextWrapper):
    """
    Sequence-aware text wrapper extending :class:`textwrap.TextWrapper`.

    This wrapper properly handles terminal escape sequences and Unicode grapheme clusters when
    calculating text width for wrapping.

    This implementation is based on the SequenceTextWrapper from the 'blessed' library, with
    contributions from Avram Lubkin and grayjk.

    The key difference from the blessed implementation is the addition of grapheme cluster support
    via :func:`~.iter_graphemes`, providing width calculation for ZWJ emoji sequences, VS-16 emojis
    and variations, regional indicator flags, and combining characters.
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
        Sequence-aware variant of :meth:`textwrap.TextWrapper._split`.

        This method ensures that terminal escape sequences don't interfere
        with the text splitting logic, particularly for hyphen-based word
        breaking. It builds a position mapping from stripped text to original
        text, calls the parent's _split on stripped text, then maps chunks back.
        """
        # Build a mapping from stripped text positions to original text positions
        # and extract the stripped (sequence-free) text
        stripped_to_original: List[int] = []
        stripped_text = ''
        original_pos = 0

        for segment, is_seq in iter_sequences(text):
            if not is_seq:
                # This is regular text, not a sequence
                for char in segment:
                    stripped_to_original.append(original_pos)
                    stripped_text += char
                    original_pos += 1
            else:
                # This is an escape sequence, skip it in stripped text
                original_pos += len(segment)

        # Add sentinel for end position
        stripped_to_original.append(original_pos)

        # Use parent's _split on the stripped text
        stripped_chunks = textwrap.TextWrapper._split(self, stripped_text)

        # Map the chunks back to the original text with sequences
        result: List[str] = []
        stripped_pos = 0

        for chunk in stripped_chunks:
            chunk_len = len(chunk)

            # Find the start and end positions in the original text
            start_orig = stripped_to_original[stripped_pos]
            end_orig = stripped_to_original[stripped_pos + chunk_len]

            # Extract the corresponding portion from the original text
            result.append(text[start_orig:end_orig])
            stripped_pos += chunk_len

        return result

    def _wrap_chunks(self, chunks: List[str]) -> List[str]:
        """
        Wrap chunks into lines using sequence-aware width.

        Override TextWrapper._wrap_chunks to use _width instead of len.
        Follows stdlib's algorithm: greedily fill lines, handle long words.
        """
        if not chunks:
            return []

        lines = []
        is_first_line = True

        # Arrange in reverse order so items can be efficiently popped
        chunks = list(reversed(chunks))

        while chunks:
            current_line: List[str] = []
            current_width = 0

            # Get the indent and available width for current line
            indent = self.initial_indent if is_first_line else self.subsequent_indent
            line_width = self.width - self._width(indent)

            # Drop leading whitespace (except at very start)
            # Use _strip_sequences to properly detect whitespace in sequenced text
            if self.drop_whitespace and lines and not self._strip_sequences(chunks[-1]).strip():
                del chunks[-1]

            # Greedily add chunks that fit
            while chunks:
                chunk = chunks[-1]
                chunk_width = self._width(chunk)

                if current_width + chunk_width <= line_width:
                    current_line.append(chunks.pop())
                    current_width += chunk_width
                else:
                    break

            # Handle chunk that's too long for any line
            if chunks and self._width(chunks[-1]) > line_width:
                self._handle_long_word(
                    chunks, current_line, current_width, line_width
                )
                current_width = self._width(''.join(current_line))

            # Drop trailing whitespace
            # Use _strip_sequences to properly detect whitespace in sequenced text
            if (self.drop_whitespace and current_line and
                    not self._strip_sequences(current_line[-1]).strip()):
                current_width -= self._width(current_line[-1])
                del current_line[-1]

            if current_line:
                lines.append(indent + ''.join(current_line))
                is_first_line = False

        return lines

    def _handle_long_word(self, reversed_chunks: List[str],
                          cur_line: List[str], cur_len: int,
                          width: int) -> None:
        """
        Sequence-aware :meth:`textwrap.TextWrapper._handle_long_word`.

        This method ensures that word boundaries are not broken mid-sequence,
        and respects grapheme cluster boundaries when breaking long words.
        """
        if width < 1:
            space_left = 1
        else:
            space_left = width - cur_len

        if self.break_long_words:
            chunk = reversed_chunks[-1]
            break_at_hyphen = False
            hyphen_end = 0

            # Handle break_on_hyphens: find last hyphen within space_left
            if self.break_on_hyphens:
                # Strip sequences to find hyphen in logical text
                stripped = self._strip_sequences(chunk)
                if len(stripped) > space_left:
                    # Find last hyphen in the portion that fits
                    hyphen_pos = stripped.rfind('-', 0, space_left)
                    if hyphen_pos > 0 and any(c != '-' for c in stripped[:hyphen_pos]):
                        # Map back to original position including sequences
                        hyphen_end = self._map_stripped_pos_to_original(chunk, hyphen_pos + 1)
                        break_at_hyphen = True

            # For sequence-aware breaking, we need to break at grapheme boundaries
            if self.break_on_graphemes:
                if break_at_hyphen:
                    # Use the hyphen break position
                    actual_end = hyphen_end
                else:
                    # Find the break position respecting graphemes and sequences
                    actual_end = self._find_break_position(chunk, space_left)
                    # If no progress possible (e.g., wide char exceeds line width),
                    # force at least one grapheme to avoid infinite loop
                    if actual_end == 0:
                        actual_end = self._find_first_grapheme_end(chunk)
                cur_line.append(chunk[:actual_end])
                reversed_chunks[-1] = chunk[actual_end:]
            else:
                end = hyphen_end if break_at_hyphen else space_left
                cur_line.append(chunk[:end])
                reversed_chunks[-1] = chunk[end:]

        elif not cur_line:
            cur_line.append(reversed_chunks.pop())

    def _map_stripped_pos_to_original(self, text: str, stripped_pos: int) -> int:
        """Map a position in stripped text back to original text position."""
        stripped_idx = 0
        original_idx = 0

        for segment, is_seq in iter_sequences(text):
            if is_seq:
                original_idx += len(segment)
            else:
                for _ in segment:
                    if stripped_idx >= stripped_pos:
                        return original_idx
                    stripped_idx += 1
                    original_idx += 1

        return original_idx

    def _find_break_position(self, text: str, max_width: int) -> int:
        """Find string index in text that fits within max_width cells."""
        idx = 0
        width_so_far = 0

        while idx < len(text):
            char = text[idx]

            # Skip escape sequences (they don't add width)
            if char == '\x1b':
                match = TERM_SEQ_PATTERN.match(text, idx)
                if match:
                    idx = match.end()
                    continue

            # Get grapheme
            grapheme = next(iter_graphemes(text[idx:]))

            grapheme_width = self._width(grapheme)
            if width_so_far + grapheme_width > max_width:
                break

            width_so_far += grapheme_width
            idx += len(grapheme)

        return idx

    def _find_first_grapheme_end(self, text: str) -> int:
        """Find the end position of the first grapheme (skipping leading sequences)."""
        idx = 0
        while idx < len(text):
            char = text[idx]

            # Skip escape sequences
            if char == '\x1b':
                match = TERM_SEQ_PATTERN.match(text, idx)
                if match:
                    idx = match.end()
                    continue

            # Found first non-sequence character, get its grapheme
            grapheme = next(iter_graphemes(text[idx:]))
            return idx + len(grapheme)

        return len(text)

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
