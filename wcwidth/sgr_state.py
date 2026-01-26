"""
SGR (Select Graphic Rendition) state tracking for terminal escape sequences.

This module provides functions for tracking and propagating terminal styling (bold, italic, colors,
etc.) across wrapped or clipped text lines.
"""
from __future__ import annotations

# std imports
import re

from typing import TYPE_CHECKING, Iterator, NamedTuple

if TYPE_CHECKING:
    from typing import Sequence

# SGR sequence pattern: CSI followed by semicolon-separated numbers ending with 'm'
_SGR_PATTERN = re.compile(r'\x1b\[([\d;]*)m')

# Fast path: quick check if any SGR sequence exists
_SGR_QUICK_CHECK = re.compile(r'\x1b\[[\d;]*m')

# Reset sequence
_SGR_RESET = '\x1b[0m'


class _SGRState(NamedTuple):
    """
    Track active SGR terminal attributes by category (immutable).

    :param bold: Bold attribute (SGR 1).
    :param dim: Dim/faint attribute (SGR 2).
    :param italic: Italic attribute (SGR 3).
    :param underline: Underline attribute (SGR 4).
    :param blink: Blink attribute (SGR 5).
    :param inverse: Inverse/reverse attribute (SGR 7).
    :param hidden: Hidden/invisible attribute (SGR 8).
    :param strikethrough: Strikethrough attribute (SGR 9).
    :param foreground: Foreground color as tuple of SGR params, or None for default.
    :param background: Background color as tuple of SGR params, or None for default.
    """
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    inverse: bool = False
    hidden: bool = False
    strikethrough: bool = False
    foreground: tuple[int, ...] | None = None
    background: tuple[int, ...] | None = None


# Default state with no attributes set
_SGR_STATE_DEFAULT = _SGRState()


def _sgr_state_is_active(state: _SGRState) -> bool:
    """
    Return True if any attributes are set.

    :param state: The SGR state to check.
    :returns: True if any attribute differs from default.
    """
    return (state.bold or state.dim or state.italic or state.underline
            or state.blink or state.inverse or state.hidden or state.strikethrough
            or state.foreground is not None or state.background is not None)


def _sgr_state_to_sequence(state: _SGRState) -> str:
    """
    Generate minimal SGR sequence to restore this state from reset.

    :param state: The SGR state to convert.
    :returns: SGR escape sequence string, or empty string if no attributes set.
    """
    if not _sgr_state_is_active(state):
        return ''

    # Map boolean attributes to their SGR codes
    bool_attrs = [
        (state.bold, '1'), (state.dim, '2'), (state.italic, '3'),
        (state.underline, '4'), (state.blink, '5'), (state.inverse, '7'),
        (state.hidden, '8'), (state.strikethrough, '9'),
    ]
    params = [code for active, code in bool_attrs if active]

    # Add color params (already formatted as tuples)
    if state.foreground is not None:
        params.append(';'.join(str(p) for p in state.foreground))
    if state.background is not None:
        params.append(';'.join(str(p) for p in state.background))

    return f'\x1b[{";".join(params)}m'


def _parse_sgr_params(sequence: str) -> list[int]:
    r"""
    Parse SGR sequence and return list of parameter values.

    Handles compound sequences like ``\x1b[1;31;4m`` -> [1, 31, 4].
    Empty params (e.g., ``\x1b[m``) are treated as [0] (reset).

    :param sequence: SGR escape sequence string.
    :returns: List of integer parameters.
    """
    match = _SGR_PATTERN.match(sequence)
    if not match:
        return []
    params_str = match.group(1)
    if not params_str:
        return [0]  # \x1b[m is equivalent to \x1b[0m
    result = []
    for param in params_str.split(';'):
        result.append(int(param) if param else 0)
    return result


# SGR code lookup tables
_SGR_ATTR_ON = {1: 'bold', 2: 'dim', 3: 'italic', 4: 'underline',
                5: 'blink', 7: 'inverse', 8: 'hidden', 9: 'strikethrough'}
_SGR_ATTR_OFF = {23: 'italic', 24: 'underline', 25: 'blink',
                 27: 'inverse', 28: 'hidden', 29: 'strikethrough'}


def _parse_extended_color(params: Iterator[int], base: int) -> tuple[int, ...] | None:
    """
    Parse extended color (256-color or RGB) from parameter iterator.

    :param params: Iterator of remaining SGR parameters.
    :param base: Base code (38 for foreground, 48 for background).
    :returns: Color tuple like (38, 5, N) or (38, 2, R, G, B), or None if malformed.
    """
    try:
        mode = next(params)
        if mode == 5:  # 256-color
            return (base, 5, next(params))
        if mode == 2:  # RGB
            return (base, 2, next(params), next(params), next(params))
    except StopIteration:
        pass
    return None


def _sgr_state_update(state: _SGRState, sequence: str) -> _SGRState:
    """
    Parse SGR sequence and return new state with updates applied.

    :param state: Current SGR state.
    :param sequence: SGR escape sequence string.
    :returns: New SGRState with updates applied.
    """
    params = iter(_parse_sgr_params(sequence))
    for p in params:
        if p == 0:
            state = _SGR_STATE_DEFAULT
        elif p == 22:  # resets both bold and dim
            state = state._replace(bold=False, dim=False)
        elif p in _SGR_ATTR_ON:
            state = state._replace(**{_SGR_ATTR_ON[p]: True})
        elif p in _SGR_ATTR_OFF:
            state = state._replace(**{_SGR_ATTR_OFF[p]: False})
        elif 30 <= p <= 37 or 90 <= p <= 97:
            state = state._replace(foreground=(p,))
        elif 40 <= p <= 47 or 100 <= p <= 107:
            state = state._replace(background=(p,))
        elif p == 39:
            state = state._replace(foreground=None)
        elif p == 49:
            state = state._replace(background=None)
        elif p == 38:
            if color := _parse_extended_color(params, 38):
                state = state._replace(foreground=color)
        elif p == 48:
            if color := _parse_extended_color(params, 48):
                state = state._replace(background=color)
    return state


def propagate_sgr(lines: Sequence[str]) -> list[str]:
    r"""
    Propagate SGR codes across wrapped lines.

    When text with SGR styling is wrapped across multiple lines, each line
    needs to be self-contained for proper display. This function:

    - Ends each line with ``\x1b[0m`` if styles are active (prevents bleeding)
    - Starts each subsequent line with the active style restored

    Fast path: If no SGR sequences exist in any line, returns input unchanged.

    :param lines: List of text lines, possibly containing SGR sequences.
    :returns: List of lines with SGR codes propagated.

    Example::

        >>> propagate_sgr(['\x1b[31mhello', 'world\x1b[0m'])
        ['\x1b[31mhello\x1b[0m', '\x1b[31mworld\x1b[0m']
    """
    if not lines:
        return list(lines)

    # Fast path: check if any line contains SGR sequences
    if not any(_SGR_QUICK_CHECK.search(line) for line in lines):
        return list(lines)

    result: list[str] = []
    state = _SGR_STATE_DEFAULT

    for line in lines:
        # Prefix with restoration sequence if state is active
        prefix = _sgr_state_to_sequence(state)

        # Update state by processing all SGR sequences in this line
        for match in _SGR_PATTERN.finditer(line):
            state = _sgr_state_update(state, match.group())

        # Build output line
        output_line = prefix + line if prefix else line
        if _sgr_state_is_active(state):
            output_line = output_line + _SGR_RESET

        result.append(output_line)

    return result
