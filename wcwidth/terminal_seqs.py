"""
Terminal sequence patterns and control character sets.

This module provides the constants and patterns used by the width() function
to handle terminal control characters and escape sequences.
"""
# std imports
import re

from ._generated_caps import INDETERMINATE_CAPS

# Illegal C0/C1 control characters.
# These raise ValueError in 'strict' mode.
ILLEGAL_CTRL = frozenset(
    chr(c) for c in (
        list(range(0x01, 0x07)) +    # SOH, STX, ETX (^C), EOT (^D), ENQ, ACK
        list(range(0x10, 0x1b)) +    # DLE through SUB (^Z)
        list(range(0x1c, 0x20)) +    # FS, GS, RS, US
        [0x7f] +                      # DEL
        list(range(0x80, 0xa0))       # C1 control characters
    )
)

# Vertical movement control characters.
# These raise ValueError in 'strict' mode (indeterminate horizontal position).
VERTICAL_CTRL = frozenset({
    '\x0a',  # LF (line feed)
    '\x0b',  # VT (vertical tab)
    '\x0c',  # FF (form feed)
})

# Horizontal movement control characters.
# These affect cursor position and are tracked in 'strict' and 'parse' modes.
HORIZONTAL_CTRL = frozenset({
    '\x08',  # BS (backspace) - cursor left 1
    '\x09',  # HT (horizontal tab) - advance to next tab stop
    '\x0d',  # CR (carriage return) - cursor to column 0
})

# Terminal-valid zero-width control characters.
# These are allowed in all modes (zero-width, no movement).
ZERO_WIDTH_CTRL = frozenset({
    '\x00',  # NUL
    '\x07',  # BEL (bell)
    '\x0e',  # SO (shift out)
    '\x0f',  # SI (shift in)
})

# All control characters that need special handling (not regular printable).
ALL_CTRL = ILLEGAL_CTRL | VERTICAL_CTRL | HORIZONTAL_CTRL | ZERO_WIDTH_CTRL | {'\x1b'}

# Pattern matches a majority of CSI, OSC, Fe sequences, Fp sequences, etc.
ZERO_WIDTH_PATTERN = re.compile(
    # CSI,
    # Parameter bytes (0-9:;<=>?)'
    # Intermediate bytes (' ' through '/')
    # Final bytes (@-~)'
    r'\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]|'
    # OSC (includes iTerm2 OSC 1337, Kitty OSC 99/5522/5113/21/22, etc.)
    # String content (until BEL or ESC)
    # String terminator (BEL or ST)
    r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|'
    # APC - Application Program Command (Kitty graphics protocol)
    r'\x1b_[^\x1b\x07]*(?:\x07|\x1b\\)|'
    # DCS - Device Control String (Sixel graphics, DECRQSS, tmux passthrough)
    r'\x1bP[^\x1b\x07]*(?:\x07|\x1b\\)|'
    # PM - Privacy Message (rare but valid ECMA-48)
    r'\x1b\^[^\x1b\x07]*(?:\x07|\x1b\\)|'
    # Character set designation
    r'\x1b[()].|'
    # Fe sequences (ESC + 0x40-0x5F)
    r'\x1b[\x40-\x5f]|'
    # Fp sequences: DECSC(7), DECRC(8), DECKPAM(=), DECKPNM(>), visual bell(g)
    r'\x1b[78=>g]'
)

# Pattern for cursor right movement: CSI [n] C
CURSOR_RIGHT_PATTERN = re.compile(r'\x1b\[(\d*)C')

# Pattern for cursor left movement: CSI [n] D
CURSOR_LEFT_PATTERN = re.compile(r'\x1b\[(\d*)D')

# Pattern for indeterminate sequences (raise in strict mode).
# These affect cursor position in ways that cannot be tracked horizontally.
INDETERMINATE_SEQ_PATTERN = re.compile(
    '|'.join(f'(?:{pattern})' for pattern in INDETERMINATE_CAPS.values())
)
