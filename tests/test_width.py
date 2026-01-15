"""Tests for width() function."""
# 3rd party
import pytest

# local
import wcwidth

BASIC_WIDTH_CASES = [
    ('', 0, 'empty'),
    ('hello', 5, 'ASCII'),
    ('コンニチハ', 10, 'CJK'),
    ('cafe\u0301', 4, 'combining'),
    ('\U0001F468\u200d\U0001F469\u200d\U0001F467', 2, 'ZWJ'),
]


@pytest.mark.parametrize('text,expected,name', BASIC_WIDTH_CASES)
def test_width_basic(text, expected, name):
    """Basic width measurement tests."""
    assert wcwidth.width(text) == expected


IGNORE_MODE_CASES = [
    ('hello\x01world', 10, 'C0_control'),
    ('hello\x00world', 10, 'NUL'),
    ('abc\bd', 4, 'backspace'),
    ('abc\nxy', 5, 'LF'),
    ('\x1b[31mred\x1b[0m', 3, 'SGR_sequence'),
    ('hello\x80world', 10, 'C1_control'),
]


@pytest.mark.parametrize('text,expected,name', IGNORE_MODE_CASES)
def test_width_control_codes_ignore(text, expected, name):
    """Ignore mode strips control codes from width calculation."""
    assert wcwidth.width(text, control_codes="ignore") == expected


STRICT_RAISES_CASES = [
    ('hello\x01world', 'C0_control'),
    ('hello\x1aworld', 'ctrl_z'),
    ('hello\x7fworld', 'DEL'),
    ('hello\x80world', 'C1_control'),
    ('hello\nworld', 'LF'),
    ('hello\x1b[Hworld', 'cursor_home'),
    ('hello\x1b[Aworld', 'cursor_up'),
]


@pytest.mark.parametrize('text,name', STRICT_RAISES_CASES)
def test_width_control_codes_strict_raises(text, name):
    """Strict mode raises ValueError for illegal control codes."""
    with pytest.raises(ValueError):
        wcwidth.width(text, control_codes="strict")


STRICT_ALLOWED_CASES = [
    ('hello\x07world', 10, 'BEL'),
    ('hello\x00world', 10, 'NUL'),
    ('abc\bd', 3, 'backspace'),
    ('abc\rxy', 3, 'CR'),
    ('\x1b[31mred\x1b[0m', 3, 'SGR_sequence'),
    ('a\x1b[2Cb', 4, 'cursor_right'),
]


@pytest.mark.parametrize('text,expected,name', STRICT_ALLOWED_CASES)
def test_width_control_codes_strict_allowed(text, expected, name):
    """Strict mode allows certain control codes."""
    assert wcwidth.width(text, control_codes="strict") == expected


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


PARSE_MODE_CASES = [
    ('hello\x01world', 10, 'C0_control'),
    ('abc\bd', 3, 'backspace'),
    ('abc\rxy', 3, 'CR'),
    ('abc\nxy', 5, 'LF_vertical'),
    ('a\x1b[2Cb', 4, 'cursor_right'),
    ('abcd\x1b[2De', 4, 'cursor_left'),
    ('\x1b[31mred\x1b[0m', 3, 'SGR'),
    ('ab\x1b[Hcd', 4, 'indeterminate'),
]


@pytest.mark.parametrize('text,expected,name', PARSE_MODE_CASES)
def test_width_control_codes_parse(text, expected, name):
    """Parse mode (default) handles control codes."""
    assert wcwidth.width(text) == expected


TABSTOP_CASES = [
    ('\t', 8, 8, 0, 'default'),
    ('\t', 5, 8, 3, 'column_offset'),
    ('abc\t', 8, 8, 0, 'after_text'),
    ('ab\t', 4, 4, 0, 'tabstop_4'),
]


@pytest.mark.parametrize('text,expected,tabstop,column,name', TABSTOP_CASES)
def test_width_tabstop(text, expected, tabstop, column, name):
    """Tabstop parameter controls tab width calculation."""
    assert wcwidth.width(text, tabstop=tabstop, column=column) == expected


def test_width_tabstop_zero():
    """Tabs are zero-width with control_codes='ignore'."""
    assert wcwidth.width('\t', control_codes='ignore') == 0


def test_width_tabstop_zero_parse():
    """Tab with tabstop=0 in parse mode is zero-width."""
    assert wcwidth.width('ab\tc', tabstop=0) == 3


ESCAPE_SEQUENCE_CASES = [
    ('\x1b[m', 0, 'basic_SGR'),
    ('\x1b[38;2;255;0;0m', 0, 'RGB_SGR'),
    ('\x1b]8;;https://example.com\x07link\x1b]8;;\x07', 4, 'OSC_hyperlink'),
    ('\x1b]0;title\x07text', 4, 'OSC_title'),
    ('\x1b(B', 0, 'charset'),
    ('\x1b[', 0, 'incomplete_CSI'),
]


@pytest.mark.parametrize('text,expected,name', ESCAPE_SEQUENCE_CASES)
def test_width_escape_sequences(text, expected, name):
    """Escape sequences are parsed correctly."""
    assert wcwidth.width(text) == expected


EDGE_CASES = [
    ('\x1b[31m\x1b[0m', 0, 'only_escapes'),
    ('\x1b[31mhello\x1b[0m world', 11, 'mixed_content'),
    ('\x1b[31mコ\x1b[0m', 2, 'wide_with_escape'),
    ('\x1b', 0, 'lone_ESC'),
    ('\x1b!', 1, 'ESC_unrecognized'),
    ('*\x1b*', 2, 'lone_ESC_between_text'),
]


@pytest.mark.parametrize('text,expected,name', EDGE_CASES)
def test_width_edge_cases(text, expected, name):
    """Edge cases are handled correctly."""
    assert wcwidth.width(text) == expected


def test_width_invalid_control_codes():
    """Tests for invalid control_codes parameter."""
    with pytest.raises(ValueError):
        wcwidth.width("hello", control_codes="invalid")


def test_vs16_selector():
    """VS16 converts narrow character to wide (width 2)."""
    # Smiley face with VS16 should be width 2 (same as wcswidth)
    assert wcwidth.width("\u263A\uFE0F") == 2
    assert wcwidth.width("\u263A\uFE0F") == wcwidth.wcswidth("\u263A\uFE0F")
    # Heart with VS16
    assert wcwidth.width("\u2764\uFE0F") == 2
    # VS16 without valid preceding char is zero-width
    assert wcwidth.width("\uFE0F") == 0
    # Character not in VS16 table followed by VS16 stays narrow
    assert wcwidth.width("A\uFE0F") == 1


def test_backspace_at_column_zero():
    """Backspace at column 0 does not go negative."""
    assert wcwidth.width('\b') == 0
    assert wcwidth.width('\ba') == 1


def test_carriage_return_resets_column():
    """CR resets column, max extent is preserved."""
    assert wcwidth.width('abc\rd') == 3
    assert wcwidth.width('abc\rde') == 3


def test_iter_sequences_lone_esc():
    """Lone ESC is yielded as a sequence."""
    assert list(wcwidth.iter_sequences('\x1b')) == [('\x1b', True)]
    assert list(wcwidth.iter_sequences('*\x1b*')) == [('*', False), ('\x1b', True), ('*', False)]


def test_tab_ignore_with_tabstop():
    """Tabs are zero-width with control_codes='ignore', tabstop has no effect."""
    assert wcwidth.width("abc\t", control_codes="ignore", tabstop=8) == 3


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


INDETERMINATE_CAP_SAMPLES = [
    ('\x1b[1;1r', 'change_scroll_region'),
    ('\x1b[H\x1b[2J', 'clear_screen'),
    ('\x1b[K', 'clr_eol'),
    ('\x1b[1;1H', 'cursor_address'),
    ('\x1b[A', 'cursor_up'),
    ('\x1b[M', 'delete_line'),
    ('\x1b[?1049h', 'enter_fullscreen'),
    ('\x1b[1X', 'erase_chars'),
    ('\x1b[L', 'insert_line'),
    ('\x1b[1S', 'parm_index'),
    ('\x1b[1A', 'parm_up_cursor'),
    ('\x1b8', 'restore_cursor'),
    ('\x1b[1d', 'row_address'),
    ('\x1bD', 'scroll_forward'),
]


@pytest.mark.parametrize('seq,cap_name', INDETERMINATE_CAP_SAMPLES)
def test_indeterminate_caps_covered_by_term_seq_pattern(seq, cap_name):
    """Verify all INDETERMINATE_CAPS sequences are matched by ZERO_WIDTH_PATTERN."""
    # local
    from wcwidth.escape_sequences import ZERO_WIDTH_PATTERN
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
    assert wcwidth.width(seq, control_codes='strict') == expected_width
