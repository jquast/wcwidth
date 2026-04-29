r"""
Terminal escape sequence patterns.

This module provides regex patterns for matching terminal escape sequences. All patterns match
sequences that begin with ESC (``\x1b``). Before calling re.match with these patterns, callers
should first check that the character at the current position is ESC for optimal performance.
"""

# std imports
import re

import typing

# Text Sizing Protocol (OSC 66) — has positive width, must be checked before ZERO_WIDTH_PATTERN.
# Groups: (1) metadata, (2) inner text, (3) terminator (BEL or ST).
# https://sw.kovidgoyal.net/kitty/text-sizing-protocol/
TEXT_SIZING_PATTERN = re.compile(
    r'\x1b\]66;([^;\x07\x1b]*);([^\x07\x1b]*)(\x07|\x1b\\)'
)

# Zero-width escape sequences (SGR, OSC, CSI, etc.). This table, like INDETERMINATE_EFFECT_SEQUENCE,
# originated from the 'blessed' library.
ZERO_WIDTH_PATTERN = re.compile(
    # CSI sequences
    r'\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]|'
    # OSC sequences, note that text sizing protocol (OSC 66) is special case in width() and clip(),
    # and contrary to the variable name, it is positive width.
    r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|'
    # APC sequences
    r'\x1b_[^\x1b\x07]*(?:\x07|\x1b\\)|'
    # DCS sequences
    r'\x1bP[^\x1b\x07]*(?:\x07|\x1b\\)|'
    # PM sequences
    r'\x1b\^[^\x1b\x07]*(?:\x07|\x1b\\)|'
    # Character set designation
    r'\x1b[()].|'
    # Fe sequences
    r'\x1b[\x40-\x5f]|'
    # Fp sequences
    r'\x1b[78=>g]'
)

# Cursor right movement: CSI [n] C, parameter may be parsed by width()
CURSOR_RIGHT_SEQUENCE = re.compile(r'\x1b\[(\d*)C')

# Cursor left movement: CSI [n] D, parameter may be parsed by width()
CURSOR_LEFT_SEQUENCE = re.compile(r'\x1b\[(\d*)D')

# Indeterminate effect sequences - raise ValueError in 'strict' mode. The effects of these sequences
# are likely to be undesirable, moving the cursor vertically or to any unknown position, and
# otherwise not managed by the 'width' method of this library.
#
# This table was created initially with code generation by extraction of termcap library with
# techniques used at 'blessed' library runtime for 'xterm', 'alacritty', 'kitty', ghostty',
# 'screen', 'tmux', and others. Then, these common capabilities were merged into the list below.
INDETERMINATE_EFFECT_SEQUENCE = re.compile(
    '|'.join(f'(?:{_pattern})' for _pattern in (
        r'\x1b\[\d+;\d+r',           # change_scroll_region
        r'\x1b\[\d*K',               # erase_in_line (clr_eol, clr_bol)
        r'\x1b\[\d*J',               # erase_in_display (clr_eos, erase_display)
        r'\x1b\[\d*G',               # column_address
        r'\x1b\[\d+;\d+H',           # cursor_address
        r'\x1b\[\d*H',               # cursor_home
        r'\x1b\[\d*A',               # cursor_up
        r'\x1b\[\d*B',               # cursor_down
        r'\x1b\[\d*P',               # delete_character
        r'\x1b\[\d*M',               # delete_line
        r'\x1b\[\d*L',               # insert_line
        r'\x1b\[\d*@',               # insert_character
        r'\x1b\[\d+X',               # erase_chars
        r'\x1b\[\d*S',               # scroll_up (parm_index)
        r'\x1b\[\d*T',               # scroll_down (parm_rindex)
        r'\x1b\[\d*d',               # row_address
        r'\x1b\[\?1049[hl]',         # alternate screen buffer
        r'\x1b\[\?47[hl]',           # alternate screen (legacy)
        r'\x1b8',                    # restore_cursor
        r'\x1bD',                    # scroll_forward (index)
        r'\x1bM',                    # scroll_reverse (reverse index)
    ))
)


def iter_sequences(text: str) -> typing.Iterator[typing.Tuple[str, bool]]:
    r"""
    Iterate through text, yielding segments with sequence identification.

    This generator yields tuples of ``(segment, is_sequence)`` for each part
    of the input text, where ``is_sequence`` is ``True`` if the segment is
    a recognized terminal escape sequence.

    :param text: String to iterate through.
    :returns: Iterator of (segment, is_sequence) tuples.

    .. versionadded:: 0.3.0

    Example::

        >>> list(iter_sequences('hello'))
        [('hello', False)]
        >>> list(iter_sequences('\x1b[31mred'))
        [('\x1b[31m', True), ('red', False)]
        >>> list(iter_sequences('\x1b[1m\x1b[31m'))
        [('\x1b[1m', True), ('\x1b[31m', True)]
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


def strip_sequences(text: str) -> str:
    r"""
    Return text with all terminal escape sequences removed.

    For sequences containing printable text, OSC 66 (Text sizing protocol) and OSC 8 (hyperlink),
    the inner text is preserved.

    Unknown or incomplete ESC sequences are preserved.

    :param text: String that may contain terminal escape sequences.
    :returns: The input text with all escape sequences stripped.

    .. versionadded:: 0.3.0

    Example::

        >>> strip_sequences('\x1b[31mred\x1b[0m')
        'red'
        >>> strip_sequences('hello')
        'hello'
        >>> strip_sequences('\x1b[1m\x1b[31mbold red\x1b[0m text')
        'bold red text'
        >>> strip_sequences('\x1b]66;s=2;hello\x07')
        'hello'
        >>> strip_sequences('\x1b]8;id=34;https://example.com\x1b\\[view]\x1b]8;;\x1b\\')
        '[view]'
    """
    if '\x1b]66;' in text:
        text = TEXT_SIZING_PATTERN.sub(r'\2', text)
    return ZERO_WIDTH_PATTERN.sub('', text)
