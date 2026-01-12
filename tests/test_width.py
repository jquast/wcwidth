"""Tests for width() function."""
import pytest

import wcwidth


class TestWidthBasic:
    """Basic width measurement tests."""

    def test_empty_string(self):
        assert wcwidth.width("") == 0

    def test_ascii_string(self):
        assert wcwidth.width("hello") == 5

    def test_wide_characters(self):
        assert wcwidth.width("コンニチハ") == 10

    def test_combining_characters(self):
        assert wcwidth.width("cafe\u0301") == 4

    def test_zwj_sequence(self):
        assert wcwidth.width("👨\u200d👩\u200d👧") == 2


class TestWidthControlCodesIgnore:
    """Tests for control_codes='ignore'."""

    def test_illegal_control_stripped(self):
        assert wcwidth.width("hello\x01world", control_codes="ignore") == 10

    def test_bell_stripped(self):
        assert wcwidth.width("hello\x07world", control_codes="ignore") == 10

    def test_nul_stripped(self):
        assert wcwidth.width("hello\x00world", control_codes="ignore") == 10

    def test_backspace_stripped(self):
        assert wcwidth.width("abc\bd", control_codes="ignore") == 4

    def test_cr_stripped(self):
        assert wcwidth.width("abc\rxy", control_codes="ignore") == 5

    def test_lf_stripped(self):
        assert wcwidth.width("abc\nxy", control_codes="ignore") == 5

    def test_escape_sequence_stripped(self):
        assert wcwidth.width("\x1b[31mred\x1b[0m", control_codes="ignore") == 3

    def test_c1_control_stripped(self):
        assert wcwidth.width("hello\x80world", control_codes="ignore") == 10

    def test_del_stripped(self):
        assert wcwidth.width("hello\x7fworld", control_codes="ignore") == 10

    def test_tab_stripped_no_tabstop(self):
        assert wcwidth.width("\t", control_codes="ignore", tabstop=None) == 0


class TestWidthControlCodesStrict:
    """Tests for control_codes='strict'."""

    def test_illegal_control_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x01world", control_codes="strict")

    def test_ctrl_c_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x03world", control_codes="strict")

    def test_ctrl_d_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x04world", control_codes="strict")

    def test_ctrl_z_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x1aworld", control_codes="strict")

    def test_del_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x7fworld", control_codes="strict")

    def test_c1_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x80world", control_codes="strict")

    def test_lf_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\nworld", control_codes="strict")

    def test_vt_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x0bworld", control_codes="strict")

    def test_ff_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x0cworld", control_codes="strict")

    def test_cursor_home_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x1b[Hworld", control_codes="strict")

    def test_clear_screen_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x1b[2Jworld", control_codes="strict")

    def test_cursor_up_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x1b[Aworld", control_codes="strict")

    def test_cursor_down_raises(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello\x1b[Bworld", control_codes="strict")

    def test_bell_allowed(self):
        assert wcwidth.width("hello\x07world", control_codes="strict") == 10

    def test_nul_allowed(self):
        assert wcwidth.width("hello\x00world", control_codes="strict") == 10

    def test_backspace_tracks_movement(self):
        assert wcwidth.width("abc\bd", control_codes="strict") == 3

    def test_cr_tracks_movement(self):
        assert wcwidth.width("abc\rxy", control_codes="strict") == 3

    def test_escape_sequence_allowed(self):
        assert wcwidth.width("\x1b[31mred\x1b[0m", control_codes="strict") == 3

    def test_cursor_right_allowed(self):
        assert wcwidth.width("a\x1b[2Cb", control_codes="strict") == 4

    def test_cursor_left_allowed(self):
        assert wcwidth.width("abcd\x1b[2De", control_codes="strict") == 4


class TestWidthControlCodesParse:
    """Tests for control_codes='parse' (default)."""

    def test_illegal_control_zero_width(self):
        assert wcwidth.width("hello\x01world") == 10

    def test_backspace_moves_cursor(self):
        assert wcwidth.width("abc\bd") == 3

    def test_backspace_erase_pattern(self):
        assert wcwidth.width("abc\b \b") == 3

    def test_backspace_at_column_zero(self):
        assert wcwidth.width("\ba") == 1

    def test_cr_resets_column(self):
        assert wcwidth.width("abc\rxy") == 3

    def test_lf_zero_width(self):
        assert wcwidth.width("abc\nxy") == 5

    def test_cursor_right_sequence(self):
        assert wcwidth.width("a\x1b[2Cb") == 4

    def test_cursor_right_default(self):
        assert wcwidth.width("a\x1b[Cb") == 3

    def test_cursor_left_sequence(self):
        assert wcwidth.width("abcd\x1b[2De") == 4

    def test_cursor_left_default(self):
        assert wcwidth.width("abc\x1b[Dd") == 3

    def test_cursor_left_past_zero(self):
        assert wcwidth.width("a\x1b[10Db") == 1

    def test_sgr_no_movement(self):
        assert wcwidth.width("\x1b[31mred\x1b[0m") == 3

    def test_indeterminate_seq_zero_width(self):
        assert wcwidth.width("ab\x1b[Hcd") == 4

    def test_c1_zero_width(self):
        assert wcwidth.width("hello\x80world") == 10

    def test_del_zero_width(self):
        assert wcwidth.width("hello\x7fworld") == 10


class TestWidthTabstop:
    """Tests for tabstop parameter (default is 8)."""

    def test_tab_default_tabstop(self):
        assert wcwidth.width("\t") == 8

    def test_tab_at_column_zero(self):
        assert wcwidth.width("\t", tabstop=8, column=0) == 8

    def test_tab_at_column_three(self):
        assert wcwidth.width("\t", tabstop=8, column=3) == 5

    def test_tab_after_text(self):
        assert wcwidth.width("abc\t", tabstop=8) == 8

    def test_tab_no_tabstop(self):
        assert wcwidth.width("\t", tabstop=None) == 0

    def test_tab_tabstop_four(self):
        assert wcwidth.width("ab\t", tabstop=4) == 4

    def test_multiple_tabs(self):
        assert wcwidth.width("\t\t", tabstop=8) == 16

    def test_tab_with_column_offset(self):
        assert wcwidth.width("ab\t", tabstop=8, column=2) == 6


class TestWidthEscapeSequences:
    """Tests for escape sequence handling."""

    def test_sgr_basic(self):
        assert wcwidth.width("\x1b[m") == 0

    def test_sgr_with_params(self):
        assert wcwidth.width("\x1b[1;31m") == 0

    def test_sgr_256_color(self):
        assert wcwidth.width("\x1b[38;5;196m") == 0

    def test_sgr_rgb(self):
        assert wcwidth.width("\x1b[38;2;255;0;0m") == 0

    def test_osc_hyperlink(self):
        assert wcwidth.width("\x1b]8;;https://example.com\x07link\x1b]8;;\x07") == 4

    def test_osc_title(self):
        assert wcwidth.width("\x1b]0;title\x07text") == 4

    def test_charset_designation(self):
        assert wcwidth.width("\x1b(B") == 0

    def test_lone_escape(self):
        assert wcwidth.width("\x1b") == 0

    def test_incomplete_csi(self):
        assert wcwidth.width("\x1b[") == 0


class TestWidthEdgeCases:
    """Edge case tests."""

    def test_only_control_chars_ignore(self):
        assert wcwidth.width("\x01\x02\x03", control_codes="ignore") == 0

    def test_only_escape_sequences(self):
        assert wcwidth.width("\x1b[31m\x1b[0m") == 0

    def test_mixed_content(self):
        result = wcwidth.width("\x1b[31mhello\x1b[0m world")
        assert result == 11

    def test_wide_char_with_escape(self):
        assert wcwidth.width("\x1b[31mコ\x1b[0m") == 2

    def test_combining_with_escape(self):
        assert wcwidth.width("\x1b[31mcafe\u0301\x1b[0m") == 4


class TestWidthInvalidControlCodes:
    """Tests for invalid control_codes parameter."""

    def test_invalid_control_codes_value(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello", control_codes="invalid")


class TestWidthMeasure:
    """Tests for measure parameter."""

    def test_measure_extent_default(self):
        assert wcwidth.width("A\x1b[10C") == 11

    def test_measure_extent_explicit(self):
        assert wcwidth.width("A\x1b[10C", measure="extent") == 11

    def test_measure_printable_simple(self):
        assert wcwidth.width("hello", measure="printable") == 5

    def test_measure_printable_cursor_right(self):
        assert wcwidth.width("A\x1b[10C", measure="printable") == 1

    def test_measure_printable_cursor_right_with_char(self):
        assert wcwidth.width("A\x1b[10CA", measure="printable") == 2

    def test_measure_printable_cursor_right_no_leading(self):
        assert wcwidth.width("\x1b[10CA", measure="printable") == 1

    def test_measure_printable_cursor_left(self):
        assert wcwidth.width("abcd\x1b[2De", measure="printable") == 5

    def test_measure_printable_backspace(self):
        assert wcwidth.width("abc\bd", measure="printable") == 4

    def test_measure_printable_cr(self):
        assert wcwidth.width("abc\rxy", measure="printable") == 5

    def test_measure_printable_wide_chars(self):
        assert wcwidth.width("コンニチハ", measure="printable") == 10

    def test_measure_printable_escape_sequence(self):
        assert wcwidth.width("\x1b[31mred\x1b[0m", measure="printable") == 3

    def test_measure_invalid(self):
        with pytest.raises(ValueError):
            wcwidth.width("hello", measure="invalid")
