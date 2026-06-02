"""Tests for terminal-specific width overrides."""
# std imports
import os

# 3rd party
import pytest

# local
import wcwidth
import wcwidth.table_grapheme_overrides as grapheme_overrides
from wcwidth._constants import _merge_ranges, resolve_terminal, list_term_programs
from wcwidth.table_overrides import VS15_OVERRIDES


def test_resolve_terminal_aliases():
    """resolve_terminal maps known aliases to canonical names."""
    assert resolve_terminal('kitty') == 'kitty'
    assert resolve_terminal('vscode') == 'xterm.js'
    assert resolve_terminal('urxvt') == 'urxvt'


def test_resolve_terminal_unknown():
    """resolve_terminal returns None for unrecognized names and empty string."""
    assert resolve_terminal('nonexistent') is None
    assert resolve_terminal('') is None


def test_resolve_terminal_none():
    """resolve_terminal reads TERM_PROGRAM env var, falling back to TERM."""
    saved_tprog = os.environ.get('TERM_PROGRAM')
    saved_term = os.environ.get('TERM')
    try:
        for var in ('TERM_PROGRAM', 'TERM'):
            os.environ.pop(var, None)
        resolve_terminal.cache_clear()
        assert resolve_terminal(None) is None
        os.environ['TERM_PROGRAM'] = 'kitty'
        resolve_terminal.cache_clear()
        assert resolve_terminal(None) == 'kitty'
    finally:
        for var, saved in (('TERM_PROGRAM', saved_tprog), ('TERM', saved_term)):
            if saved is not None:
                os.environ[var] = saved
            else:
                os.environ.pop(var, None)
        resolve_terminal.cache_clear()


def test_wcswidth_no_override():
    """Wcswidth works normally without term_program or with empty string."""
    assert wcwidth.wcswidth('hello') == 5
    assert wcwidth.wcswidth('hello', term_program='') == 5


@pytest.mark.parametrize('char,expected_default,expected_vte', [
    ('\u2630', 2, 1),
    ('\U0001f1e6', 2, 1),
])
def test_wcswidth_vte_override(char, expected_default, expected_vte):
    """VTE override narrows wide characters."""
    assert wcwidth.wcswidth(char) == expected_default
    assert wcwidth.wcswidth(char, term_program='VTE') == expected_vte


@pytest.mark.parametrize('text,kwargs,expected', [
    ('\u2630', {'term_program': 'VTE'}, 1),
    ('\u2630', {'term_program': 'kitty'}, 2),
    ('\x1b[31m\u2630\u2631\x1b[0m', {'term_program': 'VTE'}, 2),
    ('\u2630\u2631', {'control_codes': 'ignore', 'term_program': 'VTE'}, 2),
])
def test_width_vte_override(text, kwargs, expected):
    """Width() applies VTE overrides with and without control codes."""
    assert wcwidth.width(text, **kwargs) == expected


def test_vs16_override_basic():
    """VS16 override is applied to heart emoji variation."""
    heart_vs16 = '\u2764\ufe0f'
    assert wcwidth.wcswidth(heart_vs16) == 2
    assert wcwidth.wcswidth(heart_vs16, term_program='VTE') == 1
    assert wcwidth.width(heart_vs16, term_program='VTE') == 1


def test_vs16_wider_override_libvterm():
    """Libvterm has VS16 wider overrides -- exercises _vs16_wider bisearch path."""
    assert wcwidth.wcswidth('\u23ed\ufe0f', term_program='libvterm') == 2
    assert wcwidth.width('\u23ed\ufe0f', term_program='libvterm') == 2


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
    """VS15 narrows by default; VTE wider override restores width 2."""
    assert wcwidth.wcswidth('\u231a') == 2
    assert wcwidth.wcswidth('\u231a\ufe0e') == 1
    assert wcwidth.wcswidth('\u231a\ufe0e', term_program='VTE') == 2
    assert wcwidth.width('\u231a\ufe0e') == 1
    assert wcwidth.width('\u231a\ufe0e', term_program='VTE') == 2


def test_grapheme_override_zwj_not_in_table():
    """ZWJ cluster not in override table falls through without error."""
    assert wcwidth.wcswidth('😀\u200d😀', term_program='VTE') == 2
    assert wcwidth.width('😀\u200d😀', term_program='VTE') == 2


def test_width_vs15_override():
    """Width() with VS15 and terminal override."""
    assert wcwidth.width('\u231a\ufe0e', term_program='VTE') == 2
    assert wcwidth.width('\u2630\ufe0e', term_program='VTE') == 1


@pytest.mark.parametrize('term_program,expected', [
    (None, 2),
    ('', 2),
    ('nonexistent', 2),
    ('alacritty', 4),
])
def test_grapheme_override_wcswidth_family(term_program, expected):
    """Wcswidth ZWJ grapheme override applied only for recognized terminals with overrides."""
    family = '\U0001F468\u200D\U0001F466'
    assert wcwidth.wcswidth(family, term_program=term_program) == expected


def test_grapheme_override_multi_zwj_alacritty():
    """Wcswidth handles multi-ZWJ grapheme override."""
    family4 = '\U0001F468\u200D\U0001F469\u200D\U0001F467\u200D\U0001F466'
    default = wcwidth.wcswidth(family4)
    override = wcwidth.wcswidth(family4, term_program='alacritty')
    assert default == 2
    assert override == 8


@pytest.mark.parametrize('func,kwargs', [
    (wcwidth.width, {'term_program': 'alacritty'}),
    (wcwidth.width, {'control_codes': 'ignore', 'term_program': 'alacritty'}),
])
def test_grapheme_override_width_alacritty(func, kwargs):
    """Width() applies ZWJ grapheme override for alacritty."""
    family = '\U0001F468\u200D\U0001F466'
    assert func(family, **kwargs) == 4


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
    """Grapheme override get() returns empty dict for invalid names."""
    assert grapheme_overrides.get(None) == {}
    assert grapheme_overrides.get('__init__') == {}
    assert grapheme_overrides.get('') == {}
    assert grapheme_overrides.get('../../etc') == {}


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


def test_grapheme_override_missing_module():
    """
    Returns None when registry hash points to missing _known_ module.

    This can occur during a program re-install when the registry and _known_* files are out of sync
    (filesystem vs. in-memory copy differ). The ImportError is caught so measurement can continue
    gracefully without per-terminal grapheme overrides.
    """
    saved = grapheme_overrides._REGISTRY.get('putty')
    try:
        grapheme_overrides._REGISTRY['putty'] = 'deadbeef'
        grapheme_overrides.get.cache_clear()
        assert grapheme_overrides.get('putty') == {}
    finally:
        grapheme_overrides._REGISTRY['putty'] = saved
        grapheme_overrides.get.cache_clear()


def test_no_terminal_has_vs15_narrower_overrides():
    """No terminal narrows VS15."""

    # VS15 (text presentation) narrows a wide character to width 1. There is no width below 1 !
    narrower_terminals = {
        term: data['narrower']
        for term, data in VS15_OVERRIDES.items()
        if data.get('narrower')
    }
    assert not narrower_terminals, (
        f'Unexpected: terminal(s) with VS15 narrower overrides detected: '
        f'{sorted(narrower_terminals)}.\n'
        f'VS15 cannot narrow a character below width 1. '
        f'This may indicate a ucs-detect measurement error or an unexpected terminal behavior.'
    )


def test_list_term_programs_includes_xterm():
    """Xterm is a recognized terminal program for explicit use."""
    assert 'xterm' in list_term_programs()


def test_resolve_terminal_xterm_explicit():
    """resolve_terminal returns 'xterm' when passed explicitly."""
    assert resolve_terminal('xterm') == 'xterm'


@pytest.mark.parametrize('env_var', ['TERM', 'TERM_PROGRAM'])
def test_resolve_terminal_xterm_not_auto_detected(env_var):
    """resolve_terminal returns None for xterm via auto-detection from env."""
    os.environ[env_var] = 'xterm'
    resolve_terminal.cache_clear()
    assert resolve_terminal(None) is None


@pytest.mark.parametrize('func,text,expected_default,expected_xterm', [
    (wcwidth.wcswidth, '\U0001f1e6', 2, 1),
    (wcwidth.width, '\U0001f1e6', 2, 1),
    (wcwidth.wcswidth, '\u231a\ufe0e', 1, 2),
    (wcwidth.width, '\u231a\ufe0e', 1, 2),
])
def test_xterm_overrides_applied(func, text, expected_default, expected_xterm):
    """Xterm overrides are applied when term_program='xterm' is explicit."""
    assert func(text) == expected_default
    assert func(text, term_program='xterm') == expected_xterm


@pytest.mark.parametrize('func', [wcwidth.wcswidth, wcwidth.width])
def test_zwj_fallthrough_resets_base_for_vs16(func):
    """VS16 after ZWJ-skipped char does not connect to stale base (before fix, VS16 narrowed the
    watch)."""
    assert func('\u231a\u200d\u23f0\ufe0f') == 2


@pytest.mark.parametrize('func', [wcwidth.wcswidth, wcwidth.width])
def test_zwj_fallthrough_resets_base_for_vs15(func):
    """VS15 after ZWJ-skipped char does not connect to stale base (before fix, VS15 narrowed the
    watch)."""
    assert func('\u231a\u200d\u23f0\ufe0e') == 2


@pytest.mark.parametrize('func,text,dest_width,expected', [
    (wcwidth.ljust, '\u2630', 4, '\u2630   '),
    (wcwidth.rjust, '\u2630', 4, '   \u2630'),
    (wcwidth.center, '\u2630', 5, '  \u2630  '),
])
def test_align_term_program_vte(func, text, dest_width, expected):
    """Ljust/rjust/center pass term_program through to width()."""
    assert func(text, dest_width, term_program='VTE') == expected


def test_clip_term_program_vte():
    """Clip() passes term_program through to width()."""
    result = wcwidth.clip('\u2630\u2631', 0, 1, term_program='VTE')
    assert result == '\u2630'


def test_wrap_term_program_vte():
    """Wrap() passes term_program through to width()."""
    result = wcwidth.wrap('\u2630\u2631', width=2, term_program='VTE')
    assert result == ['\u2630\u2631']


@pytest.mark.parametrize('termenv,expected', [
    ({'TERM': 'xterm-kitty'}, 'kitty'),
    ({'TERM_PROGRAM': '', 'TERM': 'xterm-kitty'}, 'kitty'),
])
def test_resolve_terminal_from_env(termenv, expected):
    """resolve_terminal reads TERM when TERM_PROGRAM is unset or empty."""
    for var in ('TERM_PROGRAM', 'TERM'):
        os.environ.pop(var, None)
    os.environ.update(termenv)
    resolve_terminal.cache_clear()
    assert resolve_terminal(None) == expected


@pytest.mark.parametrize('args,expected', [
    ((), ()),
    ((((1, 5),),), ((1, 5),)),
    ((((1, 3),), ((6, 8),)), ((1, 3), (6, 8))),
    ((((1, 5),), ((4, 8),)), ((1, 8),)),
])
def test_merge_ranges(args, expected):
    """_merge_ranges merges sorted range tuples."""
    assert _merge_ranges(*args) == expected


def test_sfz_override_foot():
    """Foot narrows Fitzpatrick modifiers."""
    assert wcwidth.wcswidth('\U0001F3FB') == 2
    assert wcwidth.wcswidth('\U0001F3FB', term_program='foot') == 1


@pytest.mark.parametrize('value,expected', [
    ('  KITTY  ', 'kitty'),
    ('   ', None),
])
def test_resolve_terminal_strips_whitespace(value, expected):
    """resolve_terminal strips, lowercases, and returns None for whitespace-only."""
    assert resolve_terminal(value) == expected
