"""Tests for terminal-specific width overrides."""
# std imports
import os

# 3rd party
import pytest

# local
import wcwidth
from wcwidth._constants import _resolve_terminal, list_term_programs
from wcwidth.table_grapheme_overrides import get


def test_resolve_terminal_aliases():
    """_resolve_terminal maps known aliases to canonical names."""
    assert _resolve_terminal('kitty') == 'kitty'
    assert _resolve_terminal('vscode') == 'xterm.js'
    assert _resolve_terminal('xterm') == 'xterm'
    assert _resolve_terminal('urxvt') == 'rxvt-unicode'


def test_resolve_terminal_unknown():
    """_resolve_terminal returns None for unrecognized names and empty string."""
    assert _resolve_terminal('nonexistent') is None
    assert _resolve_terminal('') is None


def test_resolve_terminal_none():
    """_resolve_terminal reads TERM_PROGRAM env var, falling back to TERM."""
    saved_tprog = os.environ.get('TERM_PROGRAM')
    saved_term = os.environ.get('TERM')
    try:
        for var in ('TERM_PROGRAM', 'TERM'):
            os.environ.pop(var, None)
        assert _resolve_terminal(None) is None
        os.environ['TERM_PROGRAM'] = 'kitty'
        assert _resolve_terminal(None) == 'kitty'
    finally:
        for var, saved in (('TERM_PROGRAM', saved_tprog), ('TERM', saved_term)):
            if saved is not None:
                os.environ[var] = saved
            else:
                os.environ.pop(var, None)


def test_wcswidth_no_override():
    """Wcswidth works normally without term_program or with empty string."""
    assert wcwidth.wcswidth('hello') == 5
    assert wcwidth.wcswidth('hello', term_program='') == 5


def test_wcswidth_vte_wide_override():
    """VTE override narrows U+2630 from wcwidth=2 to terminal=1."""
    assert wcwidth.wcwidth('\u2630') == 2
    assert wcwidth.wcswidth('\u2630') == 2
    assert wcwidth.wcswidth('\u2630', term_program='VTE') == 1


def test_wcswidth_vte_wide_overrides_multiple():
    """Multiple trigram characters corrected by VTE override."""
    text = '\u2630\u2631\u2632\u2633\u2634\u2635\u2636\u2637'
    assert wcwidth.wcswidth(text) == 16
    assert wcwidth.wcswidth(text, term_program='VTE') == 8
    assert wcwidth.wcswidth(text, term_program='kitty') == 16


def test_wcswidth_vte_sri_override():
    """VTE override narrows standalone Regional Indicators from 2 to 1."""
    assert wcwidth.wcswidth('\U0001f1e6') == 2
    assert wcwidth.wcswidth('\U0001f1e6', term_program='VTE') == 1


def test_width_vte_wide_override():
    """Width() applies VTE override for U+2630."""
    assert wcwidth.width('\u2630', term_program='VTE') == 1
    assert wcwidth.width('\u2630', term_program='kitty') == 2


def test_width_vte_with_control_codes():
    """Width() with control codes applies terminal overrides."""
    text = '\x1b[31m\u2630\u2631\x1b[0m'
    result = wcwidth.width(text, term_program='VTE')
    assert result == 2


def test_width_ignore_mode_with_override():
    """Width() ignore mode applies terminal overrides."""
    text = '\u2630\u2631'
    result = wcwidth.width(text, control_codes='ignore', term_program='VTE')
    assert result == 2


def test_vs16_override_basic():
    """VS16 override is applied to heart emoji variation."""
    heart_vs16 = '\u2764\ufe0f'
    normal = wcwidth.wcswidth(heart_vs16)
    with_override = wcwidth.wcswidth(heart_vs16, term_program='VTE')
    assert normal in (1, 2)
    assert with_override in (1, 2)


def test_wcwidth_unchanged():
    """Wcwidth() does not accept term_program parameter."""
    assert wcwidth.wcwidth('\u2630') == 2
    with pytest.raises(TypeError):
        wcwidth.wcwidth('\u2630', term_program='VTE')  # type: ignore[call-arg]


def test_wcswidth_empty_term_program_disables():
    """Empty term_program disables override lookup."""
    assert wcwidth.wcswidth('\u2630', term_program='') == 2
    assert wcwidth.wcswidth('\u2630', term_program='VTE') == 1


def test_wcswidth_ascii_unchanged():
    """ASCII text is unaffected by terminal overrides."""
    assert wcwidth.wcswidth('hello world', term_program='VTE') == 11
    assert wcwidth.wcswidth('hello world', term_program='kitty') == 11


def test_vs15_standalone():
    """VS15 (U+FE0E) alone measures as width 0."""
    assert wcwidth.wcswidth('\ufe0e') == 0
    assert wcwidth.wcswidth('\ufe0e', term_program='VTE') == 0


def test_vs15_no_override():
    """VS15 after a character not in any override table has no effect."""
    base = '\u2630'
    assert wcwidth.wcswidth(base + '\ufe0e') == wcwidth.wcswidth(base)
    assert wcwidth.wcswidth(base + '\ufe0e', term_program='kitty') == wcwidth.wcswidth(base)


def test_vs15_wider_override_unchanged():
    """VS15 wider override does not add width when wcwidth already says 2."""
    assert wcwidth.wcswidth('\u231a') == 2
    assert wcwidth.wcswidth('\u231a\ufe0e') == 2
    assert wcwidth.wcswidth('\u231a\ufe0e', term_program='VTE') == 2


def test_width_vs15_override():
    """Width() with VS15 and terminal override."""
    assert wcwidth.width('\u231a\ufe0e', term_program='VTE') == 2
    assert wcwidth.width('\u2630\ufe0e', term_program='VTE') == 1


def test_grapheme_override_wcswidth_alacritty():
    """Wcswidth applies ZWJ grapheme override for alacritty."""
    family = '\U0001F468\u200D\U0001F466'
    assert wcwidth.wcswidth(family) == 2
    assert wcwidth.wcswidth(family, term_program='alacritty') == 4


def test_grapheme_override_wcswidth_no_term():
    """Wcswidth uses default width when no terminal is set."""
    family = '\U0001F468\u200D\U0001F466'
    assert wcwidth.wcswidth(family) == 2


def test_grapheme_override_wcswidth_disabled():
    """Wcswidth ignores overrides when term_program is empty string."""
    family = '\U0001F468\u200D\U0001F466'
    assert wcwidth.wcswidth(family, term_program='') == 2


def test_grapheme_override_wcswidth_unknown_term():
    """Wcswidth uses default width for unrecognized terminal."""
    family = '\U0001F468\u200D\U0001F466'
    assert wcwidth.wcswidth(family, term_program='nonexistent') == 2


def test_grapheme_override_multi_zwj_alacritty():
    """Wcswidth handles multi-ZWJ grapheme override."""
    family4 = '\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466'
    default = wcwidth.wcswidth(family4)
    override = wcwidth.wcswidth(family4, term_program='alacritty')
    assert default == 2
    assert override == 8


def test_grapheme_override_width_alacritty():
    """Width() applies ZWJ grapheme override."""
    family = '\U0001F468\u200D\U0001F466'
    assert wcwidth.width(family, term_program='alacritty') == 4


def test_grapheme_override_width_ignore_mode():
    """Width() ignore mode applies grapheme override."""
    family = '\U0001F468\u200D\U0001F466'
    result = wcwidth.width(family, control_codes='ignore', term_program='alacritty')
    assert result == 4


def test_grapheme_override_ascii_unchanged():
    """ASCII text is unaffected by grapheme overrides."""
    assert wcwidth.wcswidth('hello', term_program='alacritty') == 5
    assert wcwidth.width('hello', term_program='alacritty') == 5


def test_grapheme_override_zwj_at_end():
    """ZWJ at end of string does not trigger override scan."""
    text = '\U0001F468\u200D'
    assert wcwidth.wcswidth(text, term_program='alacritty') == 2


def test_grapheme_override_fitzpatrick():
    """Fitzpatrick modifier between base and ZWJ handled correctly."""
    text = '\u26F9\U0001F3FB\u200D\u2640\uFE0F'
    assert wcwidth.wcswidth(text, term_program='alacritty') == 4


def test_list_term_programs():
    """list_term_programs returns known terminals."""
    terms = list_term_programs()
    assert isinstance(terms, tuple)
    assert 'alacritty' in terms
    assert 'vte' in terms
    assert 'xterm.js' in terms
    assert 'nonexistent' not in terms


def test_grapheme_override_invalid_term_names():
    """Grapheme override get() rejects non-canonical names."""
    assert get(None) is None
    assert get('__init__') is None
    assert get('') is None
    assert get('../../etc') is None


def test_grapheme_override_zwj_no_extpict_base():
    """ZWJ after non-ExtPict base does not trigger override scan."""
    text = 'a\u200D\u200D'
    assert wcwidth.wcswidth(text, term_program='alacritty') == 1


@pytest.mark.parametrize('text,term,expected', [
    ('👨\u200d👦x', 'alacritty', 5),
    ('👨\u200da', 'alacritty', 2),
    ('👨\u200da', None, 2),
])
def test_grapheme_override_scanner_edges(text, term, expected):
    """Scanner edge cases for ZWJ chains."""
    assert wcwidth.wcswidth(text, term_program=term) == expected
