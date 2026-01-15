"""Tests for width() function."""
# 3rd party
import pytest

# local
import wcwidth


def test_width_basic():
    """Basic width measurement tests."""
    # empty string
    assert wcwidth.width("") == 0
    # ASCII string
    assert wcwidth.width("hello") == 5
    # wide characters (CJK)
    assert wcwidth.width("コンニチハ") == 10
    # combining characters
    assert wcwidth.width("cafe\u0301") == 4
    # ZWJ sequence
    assert wcwidth.width("\U0001F468\u200d\U0001F469\u200d\U0001F467") == 2


def test_width_control_codes_ignore():
    """Tests for control_codes='ignore'."""
    # illegal control code is stripped (\x01)
    assert wcwidth.width("hello\x01world", control_codes="ignore") == 10
    # BEL is stripped
    assert wcwidth.width("hello\x07world", control_codes="ignore") == 10
    # NUL is stripped
    assert wcwidth.width("hello\x00world", control_codes="ignore") == 10
    # backspace is stripped
    assert wcwidth.width("abc\bd", control_codes="ignore") == 4
    # CR is stripped
    assert wcwidth.width("abc\rxy", control_codes="ignore") == 5
    # LF is stripped
    assert wcwidth.width("abc\nxy", control_codes="ignore") == 5
    # escape sequence is stripped
    assert wcwidth.width("\x1b[31mred\x1b[0m", control_codes="ignore") == 3
    # C1 control is stripped
    assert wcwidth.width("hello\x80world", control_codes="ignore") == 10
    # DEL is stripped
    assert wcwidth.width("hello\x7fworld", control_codes="ignore") == 10
    # tab stripped when tabstop=None
    assert wcwidth.width("\t", control_codes="ignore", tabstop=None) == 0


def test_width_control_codes_strict():
    """Tests for control_codes='strict'."""
    # illegal control code raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x01world", control_codes="strict")
    # Ctrl-C raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x03world", control_codes="strict")
    # Ctrl-D raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x04world", control_codes="strict")
    # Ctrl-Z raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x1aworld", control_codes="strict")
    # DEL raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x7fworld", control_codes="strict")
    # C1 control raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x80world", control_codes="strict")
    # LF raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\nworld", control_codes="strict")
    # VT raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x0bworld", control_codes="strict")
    # FF raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x0cworld", control_codes="strict")
    # cursor home raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x1b[Hworld", control_codes="strict")
    # clear screen raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x1b[2Jworld", control_codes="strict")
    # cursor up raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x1b[Aworld", control_codes="strict")
    # cursor down raises
    with pytest.raises(ValueError):
        wcwidth.width("hello\x1b[Bworld", control_codes="strict")
    # BEL is allowed
    assert wcwidth.width("hello\x07world", control_codes="strict") == 10
    # NUL is allowed
    assert wcwidth.width("hello\x00world", control_codes="strict") == 10
    # backspace tracks movement
    assert wcwidth.width("abc\bd", control_codes="strict") == 3
    # CR tracks movement
    assert wcwidth.width("abc\rxy", control_codes="strict") == 3
    # escape sequence is allowed
    assert wcwidth.width("\x1b[31mred\x1b[0m", control_codes="strict") == 3
    # cursor right is allowed
    assert wcwidth.width("a\x1b[2Cb", control_codes="strict") == 4
    # cursor left is allowed
    assert wcwidth.width("abcd\x1b[2De", control_codes="strict") == 4


STRICT_INDETERMINATE_SEQUENCES = [
    ('\x1b[?1049h', 'enter_fullscreen'),
    ('\x1b[?1049l', 'exit_fullscreen'),
    ('\x1bD', 'scroll_forward'),
    ('\x1bM', 'scroll_reverse'),
    ('\x1b8', 'restore_cursor'),
    ('\x1b[1P', 'parm_dch'),
    ('\x1b[1M', 'parm_delete_line'),
    ('\x1b[1L', 'parm_insert_line'),
    ('\x1b[1X', 'erase_chars'),
    ('\x1b[1S', 'parm_index'),
    ('\x1b[1T', 'parm_rindex'),
]


@pytest.mark.parametrize('seq,cap_name', STRICT_INDETERMINATE_SEQUENCES)
def test_width_strict_indeterminate_raises(seq, cap_name):
    with pytest.raises(ValueError):
        wcwidth.width(f"hello{seq}world", control_codes="strict")


def test_width_control_codes_parse():
    """Tests for control_codes='parse' (default)."""
    # illegal control code has zero width
    assert wcwidth.width("hello\x01world") == 10
    # backspace moves cursor
    assert wcwidth.width("abc\bd") == 3
    # backspace-space-backspace erase pattern
    assert wcwidth.width("abc\b \b") == 3
    # backspace at column zero
    assert wcwidth.width("\ba") == 1
    # CR resets column
    assert wcwidth.width("abc\rxy") == 3
    # LF has zero width
    assert wcwidth.width("abc\nxy") == 5
    # cursor right sequence
    assert wcwidth.width("a\x1b[2Cb") == 4
    # cursor right default (no param)
    assert wcwidth.width("a\x1b[Cb") == 3
    # cursor left sequence
    assert wcwidth.width("abcd\x1b[2De") == 4
    # cursor left default (no param)
    assert wcwidth.width("abc\x1b[Dd") == 3
    # cursor left past column zero
    assert wcwidth.width("a\x1b[10Db") == 1
    # SGR has no movement
    assert wcwidth.width("\x1b[31mred\x1b[0m") == 3
    # indeterminate sequence has zero width
    assert wcwidth.width("ab\x1b[Hcd") == 4
    # C1 control has zero width
    assert wcwidth.width("hello\x80world") == 10
    # DEL has zero width
    assert wcwidth.width("hello\x7fworld") == 10


def test_width_tabstop():
    """Tests for tabstop parameter (default is 8)."""
    # tab with default tabstop
    assert wcwidth.width("\t") == 8
    # tab at column zero
    assert wcwidth.width("\t", tabstop=8, column=0) == 8
    # tab at column three
    assert wcwidth.width("\t", tabstop=8, column=3) == 5
    # tab after text
    assert wcwidth.width("abc\t", tabstop=8) == 8
    # tab with tabstop=None
    assert wcwidth.width("\t", tabstop=None) == 0
    # tab with tabstop=4
    assert wcwidth.width("ab\t", tabstop=4) == 4
    # multiple tabs
    assert wcwidth.width("\t\t", tabstop=8) == 16
    # tab with column offset
    assert wcwidth.width("ab\t", tabstop=8, column=2) == 6


def test_width_escape_sequences():
    """Tests for escape sequence handling."""
    # basic SGR
    assert wcwidth.width("\x1b[m") == 0
    # SGR with params
    assert wcwidth.width("\x1b[1;31m") == 0
    # 256-color SGR
    assert wcwidth.width("\x1b[38;5;196m") == 0
    # RGB SGR
    assert wcwidth.width("\x1b[38;2;255;0;0m") == 0
    # OSC hyperlink
    assert wcwidth.width("\x1b]8;;https://example.com\x07link\x1b]8;;\x07") == 4
    # OSC title
    assert wcwidth.width("\x1b]0;title\x07text") == 4
    # charset designation
    assert wcwidth.width("\x1b(B") == 0
    # lone escape
    assert wcwidth.width("\x1b") == 0
    # incomplete CSI
    assert wcwidth.width("\x1b[") == 0


def test_width_edge_cases():
    """Edge case tests."""
    # only control chars with ignore
    assert wcwidth.width("\x01\x02\x03", control_codes="ignore") == 0
    # only escape sequences
    assert wcwidth.width("\x1b[31m\x1b[0m") == 0
    # mixed content
    assert wcwidth.width("\x1b[31mhello\x1b[0m world") == 11
    # wide char with escape
    assert wcwidth.width("\x1b[31mコ\x1b[0m") == 2
    # combining char with escape
    assert wcwidth.width("\x1b[31mcafe\u0301\x1b[0m") == 4


def test_width_invalid_control_codes():
    """Tests for invalid control_codes parameter."""
    with pytest.raises(ValueError):
        wcwidth.width("hello", control_codes="invalid")


def test_width_measure():
    """Tests for measure parameter."""
    # extent is default
    assert wcwidth.width("A\x1b[10C") == 11
    # explicit extent
    assert wcwidth.width("A\x1b[10C", measure="extent") == 11
    # printable simple
    assert wcwidth.width("hello", measure="printable") == 5
    # printable with cursor right
    assert wcwidth.width("A\x1b[10C", measure="printable") == 1
    # printable with cursor right and char
    assert wcwidth.width("A\x1b[10CA", measure="printable") == 2
    # printable with cursor right no leading char
    assert wcwidth.width("\x1b[10CA", measure="printable") == 1
    # printable with cursor left
    assert wcwidth.width("abcd\x1b[2De", measure="printable") == 5
    # printable with backspace
    assert wcwidth.width("abc\bd", measure="printable") == 4
    # printable with CR
    assert wcwidth.width("abc\rxy", measure="printable") == 5
    # printable with wide chars
    assert wcwidth.width("コンニチハ", measure="printable") == 10
    # printable with escape sequence
    assert wcwidth.width("\x1b[31mred\x1b[0m", measure="printable") == 3
    # invalid measure value
    with pytest.raises(ValueError):
        wcwidth.width("hello", measure="invalid")


def test_vs16_selector():
    """Test VS16 emoji selector."""
    assert wcwidth.width("\u263A\uFE0F") == 1


def test_tab_ignore_with_tabstop():
    """Test tab with ignore mode and tabstop."""
    assert wcwidth.width("abc\t", control_codes="ignore", tabstop=8) == 8


def test_cursor_right_unparameterized():
    """Test unparameterized cursor_right sequence is handled correctly."""
    seq = '\x1b[C'
    # sequence is recognized as a sequence
    segments = list(wcwidth.iter_sequences(seq))
    assert segments == [(seq, True)]
    # sequence alone moves cursor right by 1 (default), extent is 1
    assert wcwidth.width(seq) == 1
    # cursor moves right by 1: 'a'(1) + right(1) + 'b'(1) = 3
    assert wcwidth.width('a' + seq + 'b') == 3
    # strict mode allows cursor_right
    assert wcwidth.width('a' + seq + 'b', control_codes='strict') == 3
    # printable counts only printed characters
    assert wcwidth.width('a' + seq + 'b', measure='printable') == 2


INDETERMINATE_CAP_SAMPLES = [
    ('\x1b[1;1r', 'change_scroll_region'),
    ('\x1b[H\x1b[2J', 'clear_screen'),
    ('\x1b[1K', 'clr_bol'),
    ('\x1b[K', 'clr_eol'),
    ('\x1b[J', 'clr_eos'),
    ('\x1b[1G', 'column_address'),
    ('\x1b[1;1H', 'cursor_address'),
    ('\x1b[B', 'cursor_down'),
    ('\x1b[H', 'cursor_home'),
    ('\x1b[A', 'cursor_up'),
    ('\x1b[P', 'delete_character'),
    ('\x1b[M', 'delete_line'),
    ('\x1b[?1049h', 'enter_fullscreen'),
    ('\x1b[1X', 'erase_chars'),
    ('\x1b[J', 'erase_display'),
    ('\x1b[?1049l', 'exit_fullscreen'),
    ('\x1b[L', 'insert_line'),
    ('\x1b[1P', 'parm_dch'),
    ('\x1b[1M', 'parm_delete_line'),
    ('\x1b[1B', 'parm_down_cursor'),
    ('\x1b[1@', 'parm_ich'),
    ('\x1b[1S', 'parm_index'),
    ('\x1b[1L', 'parm_insert_line'),
    ('\x1b[1T', 'parm_rindex'),
    ('\x1b[1A', 'parm_up_cursor'),
    ('\x1b8', 'restore_cursor'),
    ('\x1b[1d', 'row_address'),
    ('\x1bD', 'scroll_forward'),
    ('\x1bM', 'scroll_reverse'),
]


@pytest.mark.parametrize('seq,cap_name', INDETERMINATE_CAP_SAMPLES)
def test_indeterminate_caps_covered_by_term_seq_pattern(seq, cap_name):
    """Verify all INDETERMINATE_CAPS sequences are matched by ZERO_WIDTH_PATTERN."""
    from wcwidth.sequences import ZERO_WIDTH_PATTERN
    assert ZERO_WIDTH_PATTERN.match(seq)
    assert wcwidth.width(seq) == 0


ZERO_WIDTH_CAP_SAMPLES = [
    ('\x1b[3g', 'clear_all_tabs'),
    ('\x1b[?25l', 'cursor_invisible'),
    ('\x1b[?25h', 'cursor_normal'),
    ('\x1b[?12;25h', 'cursor_visible'),
    ('\x1b(0', 'enter_alt_charset_mode'),
    ('\x1b[5m', 'enter_blink_mode'),
    ('\x1b[1m', 'enter_bold_mode'),
    ('\x1b[2m', 'enter_dim_mode'),
    ('\x1b[3m', 'enter_italics_mode'),
    ('\x1b[7m', 'enter_reverse_mode'),
    ('\x1b[3m', 'enter_standout_mode'),
    ('\x1b[4m', 'enter_underline_mode'),
    ('\x1b(B', 'exit_alt_charset_mode'),
    ('\x1b[m', 'exit_attribute_mode'),
    ('\x1b[4l', 'exit_insert_mode'),
    ('\x1b[23m', 'exit_italics_mode'),
    ('\x1b[27m', 'exit_standout_mode'),
    ('\x1b[24m', 'exit_underline_mode'),
    ('\x1b[?5h\x1b[?5l', 'flash_screen_csi'),
    ('\x1bg', 'flash_screen_visual_bell'),
    ('\x1b>', 'keypad_local'),
    ('\x1b=', 'keypad_xmit'),
    ('\x1b[39;49m', 'orig_pair'),
    ('\x1b7', 'save_cursor'),
    ('\x1bH', 'set_tab'),
]


@pytest.mark.parametrize('seq,cap_name', ZERO_WIDTH_CAP_SAMPLES)
def test_zero_width_sequences_matched_by_pattern(seq, cap_name):
    """Verify zero-width terminfo sequences are matched by ZERO_WIDTH_PATTERN."""
    for part, is_seq in wcwidth.iter_sequences(seq):
        assert is_seq, f"{cap_name}: {repr(part)} not matched as sequence"
    assert wcwidth.width(seq) == 0


MODERN_TERMINAL_SEQUENCES = [
    ('\x1b_Gf=100,i=1;base64data\x1b\\hello', 5, 'kitty_graphics_with_text'),
    ('\x1b_Ga=d\x07', 0, 'kitty_graphics_delete'),
    ('\x1bP0;1;0q#0~-\x1b\\test', 4, 'sixel_graphics_with_text'),
    ('\x1bP$q"p\x1b\\', 0, 'decrqss_query'),
    ('\x1b^private\x1b\\text', 4, 'pm_with_text'),
    ('\x1b]1337;SetMark\x07test', 4, 'iterm2_setmark'),
    ('\x1b]1337;File=inline=1:base64\x07img', 3, 'iterm2_inline_image'),
    ('\x1b]1337;CursorShape=1\x07', 0, 'iterm2_cursor_shape'),
    ('\x1b]1337;CurrentDir=/home\x07', 0, 'iterm2_currentdir'),
    ('\x1b]133;A\x07$ ', 2, 'shell_prompt_start'),
    ('\x1b]133;B\x07ls', 2, 'shell_command_start'),
    ('\x1b]133;C\x07', 0, 'shell_command_executed'),
    ('\x1b]133;D;0\x07', 0, 'shell_command_finished'),
    ('\x1b]99;i=1:d=0;Hello\x1b\\', 0, 'kitty_notification'),
    ('\x1b]5522;type=read\x07', 0, 'kitty_clipboard_read'),
    ('\x1b]22;pointer\x07', 0, 'kitty_pointer_shape'),
    ('\x1b]21;fg=?\x07', 0, 'kitty_color_query'),
    ('\x1b]30001\x1b\\', 0, 'kitty_color_push'),
    ('\x1b]30101\x1b\\', 0, 'kitty_color_pop'),
]


@pytest.mark.parametrize('seq,expected_width,name', MODERN_TERMINAL_SEQUENCES)
def test_modern_sequences(seq, expected_width, name):
    """Modern terminal sequences are recognized as zero-width."""
    assert wcwidth.width(seq) == expected_width


MODERN_SEQUENCES_STRICT = [
    '\x1b_Gf=100;data\x1b\\',
    '\x1bP0q~-\x1b\\',
    '\x1b]1337;SetMark\x07',
    '\x1b]133;A\x07',
]


@pytest.mark.parametrize('seq', MODERN_SEQUENCES_STRICT)
def test_modern_sequences_strict_mode(seq):
    """Modern sequences do not raise in strict mode."""
    assert wcwidth.width(seq, control_codes='strict') == 0
