"""Tests for SGR state tracking and propagation."""
from __future__ import annotations

import pytest

from wcwidth import wrap, clip


class TestWrapPropagatesSGR:
    """Tests for wrap() SGR propagation (enabled by default)."""

    def test_wrap_propagates_sgr_by_default(self):
        """wrap() should propagate SGR codes across lines by default."""
        result = wrap('\x1b[1;34mHello world\x1b[0m', width=6)
        assert result == ['\x1b[1;34mHello\x1b[0m', '\x1b[1;34mworld\x1b[0m']

    def test_wrap_propagates_bold(self):
        """wrap() propagates bold across lines."""
        result = wrap('\x1b[1mHello world\x1b[0m', width=6)
        assert result == ['\x1b[1mHello\x1b[0m', '\x1b[1mworld\x1b[0m']

    def test_wrap_propagates_foreground_color(self):
        """wrap() propagates foreground color."""
        result = wrap('\x1b[31mred text here\x1b[0m', width=5)
        assert result == ['\x1b[31mred\x1b[0m', '\x1b[31mtext\x1b[0m', '\x1b[31mhere\x1b[0m']

    def test_wrap_propagates_256_color(self):
        """wrap() propagates 256-color foreground."""
        result = wrap('\x1b[38;5;208morange text\x1b[0m', width=7)
        assert result == ['\x1b[38;5;208morange\x1b[0m', '\x1b[38;5;208mtext\x1b[0m']

    def test_wrap_propagates_rgb_color(self):
        """wrap() propagates RGB color."""
        result = wrap('\x1b[38;2;255;0;0mred text\x1b[0m', width=5)
        assert result == ['\x1b[38;2;255;0;0mred\x1b[0m', '\x1b[38;2;255;0;0mtext\x1b[0m']

    def test_wrap_propagates_multiple_attributes(self):
        """wrap() propagates multiple attributes combined."""
        result = wrap('\x1b[1;3;34mbold italic blue\x1b[0m', width=5)
        assert result[0] == '\x1b[1;3;34mbold\x1b[0m'
        assert result[1].startswith('\x1b[')
        assert result[1].endswith('\x1b[0m')

    def test_wrap_reset_clears_state(self):
        """Reset in middle of text clears propagation state."""
        result = wrap('\x1b[31mred\x1b[0m plain text', width=6)
        assert result == ['\x1b[31mred\x1b[0m', 'plain', 'text']

    def test_wrap_no_sgr_unchanged(self):
        """wrap() with no SGR sequences returns unchanged."""
        result = wrap('hello world', width=6)
        assert result == ['hello', 'world']

    def test_wrap_propagate_sgr_false(self):
        """wrap() with propagate_sgr=False returns old behavior."""
        result = wrap('\x1b[31mhello world\x1b[0m', width=6, propagate_sgr=False)
        assert result == ['\x1b[31mhello', 'world\x1b[0m']


class TestClipPropagatesSGR:
    """Tests for clip() SGR propagation (enabled by default)."""

    def test_clip_propagates_sgr_by_default(self):
        """clip() should restore SGR state at start and reset at end."""
        result = clip('\x1b[1;34mHello world\x1b[0m', 6, 11)
        assert result == '\x1b[1;34mworld\x1b[0m'

    def test_clip_propagates_bold(self):
        """clip() propagates bold."""
        result = clip('\x1b[1mHello world\x1b[0m', 6, 11)
        assert result == '\x1b[1mworld\x1b[0m'

    def test_clip_propagates_foreground_color(self):
        """clip() propagates foreground color."""
        result = clip('\x1b[31mHello world\x1b[0m', 6, 11)
        assert result == '\x1b[31mworld\x1b[0m'

    def test_clip_from_start(self):
        """clip() from start includes leading sequence."""
        result = clip('\x1b[31mHello\x1b[0m', 0, 5)
        assert result == '\x1b[31mHello\x1b[0m'

    def test_clip_no_active_style_at_position(self):
        """clip() after reset has no prefix."""
        result = clip('\x1b[31mred\x1b[0m plain', 4, 9)
        assert result == 'plain'

    def test_clip_no_sgr_unchanged(self):
        """clip() with no SGR sequences returns unchanged."""
        result = clip('Hello world', 6, 11)
        assert result == 'world'

    def test_clip_propagate_sgr_false(self):
        """clip() with propagate_sgr=False returns old behavior (all sequences included)."""
        result = clip('\x1b[1;34mHello world\x1b[0m', 6, 11, propagate_sgr=False)
        # Old behavior: all sequences are included (they're zero-width)
        assert result == '\x1b[1;34mworld\x1b[0m'


class TestSGRStateParsing:
    """Tests for _SGRState parsing functions."""

    def test_sgr_state_parse_bold(self):
        """_sgr_state_update parses bold."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[1m')
        assert state.bold is True

    def test_sgr_state_parse_italic(self):
        """_sgr_state_update parses italic."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[3m')
        assert state.italic is True

    def test_sgr_state_parse_underline(self):
        """_sgr_state_update parses underline."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[4m')
        assert state.underline is True

    def test_sgr_state_parse_inverse(self):
        """_sgr_state_update parses inverse."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[7m')
        assert state.inverse is True

    def test_sgr_state_parse_dim(self):
        """_sgr_state_update parses dim/faint (2)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[2m')
        assert state.dim is True

    def test_sgr_state_parse_blink(self):
        """_sgr_state_update parses blink (5)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[5m')
        assert state.blink is True

    def test_sgr_state_parse_hidden(self):
        """_sgr_state_update parses hidden/invisible (8)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[8m')
        assert state.hidden is True

    def test_sgr_state_parse_strikethrough(self):
        """_sgr_state_update parses strikethrough (9)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[9m')
        assert state.strikethrough is True

    def test_sgr_state_parse_foreground_basic(self):
        """_sgr_state_update parses basic foreground color."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[31m')
        assert state.foreground == (31,)

    def test_sgr_state_parse_background_basic(self):
        """_sgr_state_update parses basic background color."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[41m')
        assert state.background == (41,)

    def test_sgr_state_parse_foreground_256(self):
        """_sgr_state_update parses 256-color foreground."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[38;5;208m')
        assert state.foreground == (38, 5, 208)

    def test_sgr_state_parse_background_256(self):
        """_sgr_state_update parses 256-color background."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[48;5;208m')
        assert state.background == (48, 5, 208)

    def test_sgr_state_parse_foreground_rgb(self):
        """_sgr_state_update parses RGB foreground."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[38;2;255;128;0m')
        assert state.foreground == (38, 2, 255, 128, 0)

    def test_sgr_state_parse_background_rgb(self):
        """_sgr_state_update parses RGB background."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[48;2;255;128;0m')
        assert state.background == (48, 2, 255, 128, 0)

    def test_sgr_state_color_format_override(self):
        """Newer color replaces older regardless of format (basic/256/RGB)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        # 256-color then basic: basic wins
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[38;5;208m')
        assert state.foreground == (38, 5, 208)
        state = _sgr_state_update(state, '\x1b[31m')
        assert state.foreground == (31,)
        # basic then RGB: RGB wins
        state = _sgr_state_update(state, '\x1b[38;2;0;255;0m')
        assert state.foreground == (38, 2, 0, 255, 0)
        # RGB then 256-color: 256-color wins
        state = _sgr_state_update(state, '\x1b[38;5;99m')
        assert state.foreground == (38, 5, 99)

    def test_sgr_state_parse_compound(self):
        """_sgr_state_update parses compound sequence."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[1;34;3m')
        assert state.bold is True
        assert state.italic is True
        assert state.foreground == (34,)

    def test_sgr_state_parse_reset(self):
        """_sgr_state_update handles reset."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState, _SGR_STATE_DEFAULT
        state = _SGRState(bold=True, foreground=(31,))
        state = _sgr_state_update(state, '\x1b[0m')
        assert state == _SGR_STATE_DEFAULT

    def test_sgr_state_parse_empty_is_reset(self):
        """_sgr_state_update treats empty as reset."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState, _SGR_STATE_DEFAULT
        state = _SGRState(bold=True)
        state = _sgr_state_update(state, '\x1b[m')
        assert state == _SGR_STATE_DEFAULT

    def test_sgr_state_parse_bold_off(self):
        """_sgr_state_update parses bold off (22)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(bold=True)
        state = _sgr_state_update(state, '\x1b[22m')
        assert state.bold is False

    def test_sgr_state_parse_italic_off(self):
        """_sgr_state_update parses italic off (23)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(italic=True)
        state = _sgr_state_update(state, '\x1b[23m')
        assert state.italic is False

    def test_sgr_state_parse_underline_off(self):
        """_sgr_state_update parses underline off (24)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(underline=True)
        state = _sgr_state_update(state, '\x1b[24m')
        assert state.underline is False

    def test_sgr_state_parse_inverse_off(self):
        """_sgr_state_update parses inverse off (27)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(inverse=True)
        state = _sgr_state_update(state, '\x1b[27m')
        assert state.inverse is False

    def test_sgr_state_parse_blink_off(self):
        """_sgr_state_update parses blink off (25)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(blink=True)
        state = _sgr_state_update(state, '\x1b[25m')
        assert state.blink is False

    def test_sgr_state_parse_hidden_off(self):
        """_sgr_state_update parses hidden off (28)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(hidden=True)
        state = _sgr_state_update(state, '\x1b[28m')
        assert state.hidden is False

    def test_sgr_state_parse_strikethrough_off(self):
        """_sgr_state_update parses strikethrough off (29)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(strikethrough=True)
        state = _sgr_state_update(state, '\x1b[29m')
        assert state.strikethrough is False

    def test_sgr_state_22_resets_bold_and_dim(self):
        """Code 22 resets both bold and dim per xterm spec."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(bold=True, dim=True)
        state = _sgr_state_update(state, '\x1b[22m')
        assert state.bold is False
        assert state.dim is False

    def test_sgr_state_parse_foreground_default(self):
        """_sgr_state_update parses default foreground (39)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(foreground=(31,))
        state = _sgr_state_update(state, '\x1b[39m')
        assert state.foreground is None

    def test_sgr_state_parse_background_default(self):
        """_sgr_state_update parses default background (49)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState
        state = _SGRState(background=(41,))
        state = _sgr_state_update(state, '\x1b[49m')
        assert state.background is None

    def test_sgr_state_parse_bright_foreground(self):
        """_sgr_state_update parses bright foreground (90-97)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[91m')
        assert state.foreground == (91,)

    def test_sgr_state_parse_bright_background(self):
        """_sgr_state_update parses bright background (100-107)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[101m')
        assert state.background == (101,)


class TestSGRStateToSequence:
    """Tests for _sgr_state_to_sequence."""

    def test_sgr_state_to_sequence_empty(self):
        """Empty state produces no sequence."""
        from wcwidth.sgr_state import _sgr_state_to_sequence, _SGR_STATE_DEFAULT
        assert _sgr_state_to_sequence(_SGR_STATE_DEFAULT) == ''

    def test_sgr_state_to_sequence_bold(self):
        """Bold state produces bold sequence."""
        from wcwidth.sgr_state import _sgr_state_to_sequence, _SGRState
        state = _SGRState(bold=True)
        assert _sgr_state_to_sequence(state) == '\x1b[1m'

    def test_sgr_state_to_sequence_foreground(self):
        """Foreground color state produces color sequence."""
        from wcwidth.sgr_state import _sgr_state_to_sequence, _SGRState
        state = _SGRState(foreground=(31,))
        assert _sgr_state_to_sequence(state) == '\x1b[31m'

    def test_sgr_state_to_sequence_256_color(self):
        """256-color state produces extended sequence."""
        from wcwidth.sgr_state import _sgr_state_to_sequence, _SGRState
        state = _SGRState(foreground=(38, 5, 208))
        assert _sgr_state_to_sequence(state) == '\x1b[38;5;208m'

    def test_sgr_state_to_sequence_rgb_color(self):
        """RGB color state produces RGB sequence."""
        from wcwidth.sgr_state import _sgr_state_to_sequence, _SGRState
        state = _SGRState(foreground=(38, 2, 255, 128, 0))
        assert _sgr_state_to_sequence(state) == '\x1b[38;2;255;128;0m'

    def test_sgr_state_to_sequence_minimal(self):
        """Multiple attributes produce combined minimal sequence."""
        from wcwidth.sgr_state import _sgr_state_to_sequence, _SGRState
        state = _SGRState(bold=True, italic=True, foreground=(34,))
        seq = _sgr_state_to_sequence(state)
        assert seq == '\x1b[1;3;34m'

    def test_sgr_state_to_sequence_all_attributes(self):
        """All attributes produce combined sequence."""
        from wcwidth.sgr_state import _sgr_state_to_sequence, _SGRState
        state = _SGRState(
            bold=True,
            italic=True,
            underline=True,
            inverse=True,
            foreground=(31,),
            background=(44,)
        )
        seq = _sgr_state_to_sequence(state)
        assert '\x1b[' in seq
        assert 'm' in seq
        assert '1' in seq
        assert '3' in seq
        assert '4' in seq
        assert '7' in seq
        assert '31' in seq
        assert '44' in seq


class TestSGRStateIsActive:
    """Tests for _sgr_state_is_active."""

    def test_default_state_not_active(self):
        """Default state is not active."""
        from wcwidth.sgr_state import _sgr_state_is_active, _SGR_STATE_DEFAULT
        assert _sgr_state_is_active(_SGR_STATE_DEFAULT) is False

    def test_bold_state_is_active(self):
        """Bold state is active."""
        from wcwidth.sgr_state import _sgr_state_is_active, _SGRState
        assert _sgr_state_is_active(_SGRState(bold=True)) is True

    def test_foreground_state_is_active(self):
        """Foreground color state is active."""
        from wcwidth.sgr_state import _sgr_state_is_active, _SGRState
        assert _sgr_state_is_active(_SGRState(foreground=(31,))) is True


class TestPropagateSGRFunction:
    """Tests for propagate_sgr function directly."""

    def test_propagate_sgr_no_sequences(self):
        """propagate_sgr returns unchanged when no sequences."""
        from wcwidth.sgr_state import propagate_sgr
        lines = ['hello', 'world']
        result = propagate_sgr(lines)
        assert result == lines

    def test_propagate_sgr_single_line(self):
        """propagate_sgr handles single line."""
        from wcwidth.sgr_state import propagate_sgr
        lines = ['\x1b[31mhello\x1b[0m']
        result = propagate_sgr(lines)
        assert result == ['\x1b[31mhello\x1b[0m']

    def test_propagate_sgr_continues_style(self):
        """propagate_sgr continues style to next line."""
        from wcwidth.sgr_state import propagate_sgr
        lines = ['\x1b[31mhello', 'world\x1b[0m']
        result = propagate_sgr(lines)
        assert result == ['\x1b[31mhello\x1b[0m', '\x1b[31mworld\x1b[0m']

    def test_propagate_sgr_reset_clears(self):
        """propagate_sgr respects reset."""
        from wcwidth.sgr_state import propagate_sgr
        lines = ['\x1b[31mred\x1b[0m', 'plain']
        result = propagate_sgr(lines)
        assert result == ['\x1b[31mred\x1b[0m', 'plain']

    def test_propagate_sgr_empty_lines(self):
        """propagate_sgr handles empty lines correctly."""
        from wcwidth.sgr_state import propagate_sgr
        lines = ['\x1b[31mred', '', 'text\x1b[0m']
        result = propagate_sgr(lines)
        assert result[0] == '\x1b[31mred\x1b[0m'
        assert result[1] == '\x1b[31m\x1b[0m'
        assert result[2] == '\x1b[31mtext\x1b[0m'

    def test_propagate_sgr_empty_input(self):
        """propagate_sgr handles empty input."""
        from wcwidth.sgr_state import propagate_sgr
        assert propagate_sgr([]) == []


class TestSGREdgeCases:
    """Tests for edge cases in SGR parsing."""

    def test_malformed_256_color_missing_value(self):
        """Malformed 256-color sequence (missing value) is ignored."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[38;5m')
        assert state.foreground is None

    def test_malformed_rgb_missing_values(self):
        """Malformed RGB sequence (missing values) is ignored."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[38;2;255m')
        assert state.foreground is None

    def test_unknown_sgr_code_ignored(self):
        """Unknown SGR codes are ignored without error."""
        from wcwidth.sgr_state import _sgr_state_update, _SGR_STATE_DEFAULT
        state = _sgr_state_update(_SGR_STATE_DEFAULT, '\x1b[999m')
        assert state == _SGR_STATE_DEFAULT

    def test_empty_params_in_compound(self):
        """Empty params in compound sequence treated as 0 (reset)."""
        from wcwidth.sgr_state import _sgr_state_update, _SGRState, _SGR_STATE_DEFAULT
        state = _SGRState(bold=True)
        state = _sgr_state_update(state, '\x1b[;1m')
        assert state.bold is True

    def test_clip_sgr_only_no_visible_content(self):
        """clip() returns empty when only SGR sequences exist."""
        result = clip('\x1b[31m\x1b[0m', 0, 10)
        assert result == ''

    def test_clip_preserves_non_sgr_sequences(self):
        """clip() preserves non-SGR sequences (OSC, CSI cursor)."""
        result = clip('\x1b]8;;url\x07link\x1b]8;;\x07', 0, 4)
        assert '\x1b]8;;url\x07' in result
        assert '\x1b]8;;\x07' in result

    def test_wrap_preserves_non_sgr_sequences(self):
        """wrap() preserves non-SGR sequences."""
        result = wrap('\x1b]8;;url\x07long link text\x1b]8;;\x07', width=5)
        assert any('\x1b]8;;url\x07' in line for line in result)
