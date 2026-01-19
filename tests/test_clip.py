"""Tests for clip() and strip_sequences() functions."""
import pytest
from wcwidth import clip, strip_sequences, width


class TestStripSequences:
    """Tests for strip_sequences function."""

    @pytest.mark.parametrize('text,expected', [
        # empty and plain
        ('', ''),
        ('hello', 'hello'),
        ('hello world', 'hello world'),
        # SGR sequences
        ('\x1b[31m', ''),
        ('\x1b[0m', ''),
        ('\x1b[m', ''),
        ('\x1b[31mred\x1b[0m', 'red'),
        ('\x1b[1m\x1b[31mbold red\x1b[0m', 'bold red'),
        ('\x1b[1m\x1b[31m\x1b[4m', ''),
        ('\x1b[1mbold\x1b[0m \x1b[3mitalic\x1b[0m', 'bold italic'),
        # OSC sequences
        ('\x1b]0;title\x07', ''),
        ('\x1b]0;title\x07text', 'text'),
        ('\x1b]8;;https://example.com\x07link\x1b]8;;\x07', 'link'),
        # CJK and emoji
        ('\x1b[31m中文\x1b[0m', '中文'),
        (f'\x1b[1m\U0001F468\u200D\U0001F469\u200D\U0001F467\x1b[0m',
         '\U0001F468\u200D\U0001F469\u200D\U0001F467'),
        # lone/incomplete escape
        ('\x1b', ''),
        ('a\x1bb', 'ab'),
        ('\x1b[', ''),
        ('text\x1b[more', 'textore'),
    ])
    def test_strip(self, text, expected):
        assert strip_sequences(text) == expected


class TestClipBasic:
    """Basic clip functionality tests."""

    @pytest.mark.parametrize('text,start,end,expected', [
        # empty and boundary cases
        ('', 0, 5, ''),
        ('', 0, 0, ''),
        ('hello', 0, 0, ''),
        ('hello', 5, 5, ''),
        ('hello', 5, 3, ''),
        ('hello', -5, 3, 'hel'),
        # simple ASCII
        ('hello', 0, 5, 'hello'),
        ('hello', 0, 3, 'hel'),
        ('hello', 2, 5, 'llo'),
        ('hello', 1, 4, 'ell'),
        ('hello world', 0, 5, 'hello'),
        ('hello world', 6, 11, 'world'),
        ('hello world', 0, 11, 'hello world'),
        # beyond text bounds
        ('hi', 0, 100, 'hi'),
        ('hi', 100, 200, ''),
    ])
    def test_basic(self, text, start, end, expected):
        assert clip(text, start, end) == expected


class TestClipCJK:
    """Tests for clip with CJK (wide) characters."""

    @pytest.mark.parametrize('text,start,end,expected', [
        # exact boundaries
        ('中文字', 0, 6, '中文字'),
        ('中文字', 0, 4, '中文'),
        ('中文字', 0, 2, '中'),
        ('中文字', 2, 4, '文'),
        # split at boundaries
        ('中文字', 0, 3, '中 '),
        ('中文字', 1, 6, ' 文字'),
        ('中文字', 1, 5, ' 文 '),
        # mixed ASCII/CJK
        ('A中B', 0, 4, 'A中B'),
        ('A中B', 0, 3, 'A中'),
        ('A中B', 1, 4, '中B'),
        ('A中B', 1, 3, '中'),
        ('A中B', 2, 4, ' B'),
        # single wide char
        ('中', 0, 2, '中'),
        ('中', 0, 1, ' '),
        ('中', 1, 2, ' '),
    ])
    def test_cjk(self, text, start, end, expected):
        assert clip(text, start, end) == expected

    def test_custom_fillchar(self):
        assert clip('中文字', 1, 5, fillchar='.') == '.文.'
        assert clip('中文', 1, 3, fillchar='\u00b7') == '\u00b7\u00b7'

    @pytest.mark.parametrize('text,start,end,expected_width', [
        ('中文字', 0, 6, 6),
        ('中文字', 0, 3, 3),
        ('中文字', 1, 6, 5),
        ('中文字', 1, 5, 4),
    ])
    def test_width_consistency(self, text, start, end, expected_width):
        assert width(clip(text, start, end)) == expected_width


class TestClipSequences:
    """Tests for clip with terminal escape sequences."""

    def test_preserve_sgr(self):
        result = clip('\x1b[31mred\x1b[0m', 0, 3)
        assert result == '\x1b[31mred\x1b[0m'
        assert strip_sequences(result) == 'red'

    def test_sequences_before_start(self):
        result = clip('\x1b[31mred text\x1b[0m', 4, 8)
        assert '\x1b[31m' in result and 'text' in result and '\x1b[0m' in result

    def test_sequences_after_end(self):
        assert clip('hello\x1b[31m world\x1b[0m', 0, 5) == 'hello\x1b[31m\x1b[0m'

    def test_multiple_sequences(self):
        result = clip('\x1b[1m\x1b[31mbold red\x1b[0m', 0, 4)
        assert all(s in result for s in ['\x1b[1m', '\x1b[31m', 'bold', '\x1b[0m'])

    def test_sequence_only(self):
        assert clip('\x1b[31m\x1b[0m', 0, 10) == '\x1b[31m\x1b[0m'

    def test_osc_hyperlink(self):
        result = clip('\x1b]8;;https://example.com\x07link\x1b]8;;\x07', 0, 4)
        assert 'link' in result and '\x1b]8;;' in result

    def test_cjk_with_sequences(self):
        result = clip('\x1b[31m中文\x1b[0m', 0, 3)
        assert result == '\x1b[31m中 \x1b[0m'

    def test_sequence_between_chars(self):
        result = clip('a\x1b[31mb\x1b[0mc', 1, 2)
        assert 'b' in result and '\x1b[31m' in result

    def test_lone_esc(self):
        result = clip('a\x1bb', 0, 2)
        assert 'a' in result and 'b' in result and '\x1b' in result


class TestClipEmoji:
    """Tests for clip with emoji characters."""

    @pytest.mark.parametrize('emoji,full_width', [
        ('\U0001F600', 2),                                    # simple emoji
        ('\U0001F468\u200D\U0001F469\u200D\U0001F467', 2),    # ZWJ family
        ('\u2764\uFE0F', 2),                                  # VS16 heart
        ('\U0001F1FA\U0001F1F8', 2),                          # flag
    ])
    def test_emoji_clip(self, emoji, full_width):
        assert clip(emoji, 0, full_width) == emoji
        assert clip(emoji, 0, 1) == ' '
        assert width(emoji) == full_width

    def test_emoji_with_sequences(self):
        result = clip('\x1b[1m\U0001F600\x1b[0m', 0, 2)
        assert '\U0001F600' in result and '\x1b[1m' in result


class TestClipCombining:
    """Tests for clip with combining characters."""

    def test_combining_accent(self):
        assert clip('cafe\u0301', 0, 4) == 'cafe\u0301'
        assert clip('cafe\u0301', 0, 3) == 'caf'

    def test_multiple_combining(self):
        assert clip('e\u0301\u0327', 0, 1) == 'e\u0301\u0327'


class TestClipAmbiguous:
    """Tests for clip with ambiguous width characters."""

    def test_ambiguous_width_1(self):
        result = clip('\u00b1test', 0, 3, ambiguous_width=1)
        assert result == '\u00b1te'

    def test_ambiguous_width_2(self):
        result = clip('\u00b1test', 0, 3, ambiguous_width=2)
        assert result == '\u00b1t'


class TestClipTabExpansion:
    """Tests for clip() TAB expansion."""

    @pytest.mark.parametrize('text,start,end,tabsize,expected', [
        ('a\tb', 0, 10, 8, 'a       b'),
        ('a\tb', 0, 4, 8, 'a   '),
        ('a\tb', 0, 10, 4, 'a   b'),
        ('a\tb', 4, 10, 8, '    b'),
        ('a\tb\tc', 0, 20, 4, 'a   b   c'),
        ('中\tb', 0, 10, 4, '中  b'),
        ('a\tb', 0, 5, 0, 'a\tb'),  # tabsize=0 preserves tab
    ])
    def test_tab_expansion(self, text, start, end, tabsize, expected):
        assert clip(text, start, end, tabsize=tabsize) == expected

    def test_tab_with_sequences(self):
        result = clip('\x1b[31mab\tc\x1b[0m', 0, 12, tabsize=4)
        assert '\x1b[31m' in result and '\x1b[0m' in result


# Control chars passed through as zero-width (not processed)
@pytest.mark.parametrize('text,start,end,expected', [
    ('abc\bde', 0, 5, 'abc\bde'),      # backspace
    ('ab\acd', 0, 4, 'ab\acd'),        # bell
    ('ab\x00cd', 0, 4, 'ab\x00cd'),    # NUL
    ('abc\rde', 0, 5, 'abc\rde'),      # carriage return
    ('\a\b\rHello', 0, 5, '\a\b\rHello'),
    ('ab\x01\x02cd', 0, 4, 'ab\x01\x02cd'),
])
def test_control_chars_zero_width(text, start, end, expected):
    assert clip(text, start, end) == expected


# Cursor sequences passed through as zero-width (not processed)
@pytest.mark.parametrize('text,start,end,expected', [
    ('ab\x1b[5Ccd', 0, 4, 'ab\x1b[5Ccd'),      # cursor right 5
    ('abcde\x1b[2Df', 0, 6, 'abcde\x1b[2Df'),  # cursor left 2
    ('ab\x1b[10Ccd', 0, 4, 'ab\x1b[10Ccd'),    # cursor right 10
    ('ab\x1b[Ccd', 0, 4, 'ab\x1b[Ccd'),        # cursor right (no param)
])
def test_cursor_sequences_zero_width(text, start, end, expected):
    assert clip(text, start, end) == expected
