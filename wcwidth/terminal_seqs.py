"""
Terminal sequence patterns and control character sets.

This module provides the constants and patterns used by the width() function
to handle terminal control characters and escape sequences.
"""
import re

from ._generated_caps import (
    HORIZONTAL_MOVEMENT_CAPS,
    INDETERMINATE_CAPS,
    ZERO_WIDTH_CAPS,
)

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

# Pattern to match terminal escape sequences.
# Matches CSI, OSC, Fe sequences, Fp sequences, and character set designations.
TERM_SEQ_PATTERN = re.compile(
    r'\x1b\['                               # CSI introducer
    r'[\x30-\x3f]*'                          # Parameter bytes (0-9:;<=>?)
    r'[\x20-\x2f]*'                          # Intermediate bytes (space through /)
    r'[\x40-\x7e]'                           # Final byte (@-~)
    r'|'
    r'\x1b\]'                                # OSC introducer
    r'[^\x07\x1b]*'                          # String content (until BEL or ESC)
    r'(?:\x07|\x1b\\)'                       # String terminator (BEL or ST)
    r'|'
    r'\x1b[()].'                             # Character set designation
    r'|'
    r'\x1b[\x40-\x5f]'                       # Fe sequences (ESC + 0x40-0x5F)
    r'|'
    r'\x1b[78=>]'                            # Fp sequences: DECSC(7), DECRC(8), DECKPAM(=), DECKPNM(>)
)

# Pattern for cursor right movement: CSI [n] C
CURSOR_RIGHT_PATTERN = re.compile(r'\x1b\[(\d*)C')

# Pattern for cursor left movement: CSI [n] D
CURSOR_LEFT_PATTERN = re.compile(r'\x1b\[(\d*)D')

# Pattern for SGR (Select Graphic Rendition) sequences: CSI ... m
# These affect styling only, no cursor movement.
SGR_PATTERN = re.compile(r'\x1b\[[\d;]*m')

# Pattern for indeterminate CSI sequences (raise in strict mode).
# These affect cursor position in ways that cannot be tracked horizontally:
# - H/f: Cursor position (absolute)
# - A/B: Cursor up/down (vertical)
# - J: Erase in display (clear screen)
# - K: Erase in line (may affect cursor)
# - S/T: Scroll up/down
# - s/u: Save/restore cursor position
# - G: Cursor horizontal absolute
# - d: Cursor vertical absolute
# - E/F: Cursor next/previous line
# - r: Set scrolling region
INDETERMINATE_SEQ_PATTERN = re.compile(
    r'\x1b\[[\d;]*[HfABJKSTsuGdEFr]'
)

# Compiled patterns from generated terminal capabilities.
# These are used to match specific terminfo-derived sequences.

# Pattern matching any horizontal movement sequence from terminfo.
GENERATED_HORIZONTAL_PATTERN = re.compile(
    '|'.join(f'(?:{pattern})' for pattern in HORIZONTAL_MOVEMENT_CAPS.values())
)

# Pattern matching any indeterminate sequence from terminfo.
GENERATED_INDETERMINATE_PATTERN = re.compile(
    '|'.join(f'(?:{pattern})' for pattern in INDETERMINATE_CAPS.values())
)

# Pattern matching any zero-width sequence from terminfo.
GENERATED_ZERO_WIDTH_PATTERN = re.compile(
    '|'.join(f'(?:{pattern})' for pattern in ZERO_WIDTH_CAPS.values())
)

# Combined pattern for all generated caps (for sequence detection).
GENERATED_ALL_CAPS_PATTERN = re.compile(
    '|'.join(
        f'(?:{pattern})'
        for caps in (HORIZONTAL_MOVEMENT_CAPS, INDETERMINATE_CAPS, ZERO_WIDTH_CAPS)
        for pattern in caps.values()
    )
)
