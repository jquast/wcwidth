#!/usr/bin/env python
"""
Subprocess helper for update-termcaps.py.

Extracts terminal capabilities for a single terminal type.
Must run in subprocess because curses.setupterm() is once-per-process.

Environment variables:
    TERMCAPS_TERMINAL: Terminal name to extract capabilities from
    TERMCAPS_CAPS: JSON-encoded dict of capabilities to extract

Outputs JSON to stdout.
"""
from __future__ import annotations

import curses
import json
import os
import re
import sys


def strip_delay_markers(capability: str) -> str:
    """Strip terminfo delay markers like $<2>, $<50/>, $<5*> from capability string."""
    # Pattern matches $<number> with optional * and/or / modifiers
    return re.sub(r'\$<\d+[*/]*>', '', capability)


def is_raw_control_char(capability: str) -> bool:
    """Check if capability is a raw C0/C1 control character (not an escape sequence).

    These are handled separately in HORIZONTAL_CTRL, VERTICAL_CTRL, ZERO_WIDTH_CTRL
    and should not be in the generated escape sequence patterns.
    """
    if not capability:
        return True
    # Raw control chars are single bytes in C0 (0x00-0x1F) or DEL (0x7F) or C1 (0x80-0x9F)
    # Escape sequences start with ESC (\x1b) followed by more characters
    if len(capability) == 1:
        code = ord(capability)
        return code < 0x20 or code == 0x7F or 0x80 <= code < 0xA0
    # Multi-char starting with ESC is an escape sequence, not a raw control
    return False


def build_pattern(capability: str, nparams: int = 0, match_grouped: bool = False,
                  match_any: bool = False, numeric: int = 99) -> str:
    """Convert a terminfo capability string to a regex pattern."""
    # Strip delay markers before processing
    capability = strip_delay_markers(capability)

    if nparams == 0:
        return re.escape(capability)

    # tparm to get actual sequence with test values
    # Use widely spaced values to avoid collisions
    # Note: terminfo %i increments params by 1, so 87 might appear as 88
    test_values = [87 + i * 10 for i in range(nparams)]  # [87, 97, 107, ...]
    cap_bytes = capability.encode('latin1')
    try:
        output = curses.tparm(cap_bytes, *test_values).decode('latin1')
    except curses.error:
        return re.escape(capability)

    output = re.escape(output)
    pattern = r'(\d+)' if match_grouped else r'\d+'

    # Replace each test value with regex pattern
    # Check for value and value+1 (for %i increment)
    # Go in reverse order so larger numbers are replaced first
    for test_val in sorted(test_values, reverse=True):
        for num in [test_val + 1, test_val]:  # Check incremented value first
            if str(num) in output:
                if match_any:
                    output = re.sub(re.escape(str(num)), pattern, output)
                else:
                    output = output.replace(str(num), pattern, 1)
                break

    return output


def main() -> None:
    term_name = os.environ.get('TERMCAPS_TERMINAL')
    caps_json = os.environ.get('TERMCAPS_CAPS')

    if not term_name or not caps_json:
        print(json.dumps({'error': 'missing environment variables'}))
        sys.exit(1)

    try:
        terminfo_caps = json.loads(caps_json)
    except json.JSONDecodeError as e:
        print(json.dumps({'error': f'invalid JSON: {e}'}))
        sys.exit(1)

    try:
        curses.setupterm(term=term_name)
    except curses.error as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(0)

    patterns = {}
    for name, (attr, opts) in terminfo_caps.items():
        try:
            cap = curses.tigetstr(attr)
            if cap:
                decoded = cap.decode('latin1')
                # Strip delay markers first, then check if it's a raw control char
                decoded = strip_delay_markers(decoded)
                if is_raw_control_char(decoded):
                    # Skip raw control chars - handled separately in terminal_seqs.py
                    continue
                patterns[name] = build_pattern(decoded, **opts)
        except Exception:
            pass

    print(json.dumps(patterns))


if __name__ == '__main__':
    main()
