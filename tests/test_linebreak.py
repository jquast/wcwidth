"""Tests for UAX #14 line breaking (LineBreakTest.txt)."""

# std imports
import os
import re

# 3rd party
import pytest

# local
from wcwidth import linebreak, list_versions
from wcwidth.linebreak import (LINEBREAK_UNICODE_VERSION,
                               LineBreak,
                               linebreak_class,
                               iter_line_breaks)

TEST_FILE = os.path.join(os.path.dirname(__file__), 'LineBreakTest.txt')


def parse_line_break_test_line(line):
    """Parse one LineBreakTest.txt line into text and expected break positions."""
    data, _, _ = line.partition('#')
    tokens = data.split()
    cps = []
    expected = set()
    pending_break = False
    for token in tokens:
        if token == '\u00f7':
            pending_break = True
        elif token == '\u00d7':
            pending_break = False
        else:
            if pending_break:
                expected.add(len(cps))
            cps.append(int(token, 16))
    if pending_break:
        expected.add(len(cps))
    return ''.join(chr(cp) for cp in cps), expected


def read_line_break_test_version():
    """Return the Unicode version named by the LineBreakTest.txt header."""
    with open(TEST_FILE, encoding='utf-8') as test_file:
        header = test_file.readline()
    match = re.match(r'#\s*LineBreakTest-(\d+\.\d+\.\d+)\.txt', header)
    assert match is not None, (
        f'Cannot determine Unicode version from {TEST_FILE!r}, '
        f'first line is {header.strip()!r}')
    return match.group(1)


def read_line_break_test():
    """Read and parse LineBreakTest.txt."""
    if not os.path.exists(TEST_FILE):
        return []
    cases = []
    with open(TEST_FILE, encoding='utf-8') as test_file:
        for line_num, line in enumerate(test_file, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            text, expected = parse_line_break_test_line(line)
            cases.append(pytest.param(text, expected, id=f'line{line_num}'))
    return cases


@pytest.mark.skipif(not os.path.exists(TEST_FILE),
                    reason='LineBreakTest.txt is missing; run bin/update-tables.py')
def test_line_break_test_fixture_version():
    """LineBreakTest.txt must match the Unicode version of our tables."""
    fixture_version = read_line_break_test_version()
    table_version = list_versions()[-1]
    assert fixture_version == table_version, (
        f'tests/LineBreakTest.txt is Unicode {fixture_version} but the '
        f'shipped tables are Unicode {table_version}. Re-run '
        f'bin/update-tables.py so both sides agree; otherwise the failures '
        f'below are version skew, not bugs.')


@pytest.mark.parametrize('char,expected', [
    ('\u200b', LineBreak.ZW),
    ('\u2060', LineBreak.WJ),
    ('\ufeff', LineBreak.WJ),
    ('\u00a0', LineBreak.GL),
    ('\u202f', LineBreak.GL),
    ('\u2007', LineBreak.GL),
    ('\u00ad', LineBreak.HH),
    ('\u1680', LineBreak.BA),
    ('\u3000', LineBreak.BA),
    ('\u2000', LineBreak.BA),
    ('\u200a', LineBreak.BA),
    ('\u002d', LineBreak.HY),
    ('\u0020', LineBreak.SP),
])
def test_linebreak_class(char, expected):
    assert linebreak_class(ord(char)) == expected


def test_linebreak_class_out_of_range():
    assert linebreak_class(0x110000) == LineBreak.XX
    assert linebreak_class(0xFFFFFFFF) == LineBreak.XX


def test_break_positions_empty():
    assert not list(linebreak._break_positions('', True))


def test_iter_line_breaks_rule_contexts():
    pi_qu, pf_qu, ea = '\u00ab', '\u00bb', '\u3009'
    dot, vi, vf = '\u25cc', '\u1b44', '\u1bf2'
    preceders = ['\x0b', '\r', '\n', '\x85', ' ', '\u200b']
    quoted_preceders = ['(', '"', '\xa0']
    cases = []

    for prior in preceders:
        cases.append((prior + pi_qu + 'a', [1, 3]))
        cases.append((prior + pi_qu + ' a', [1, 4]))
    for prior in quoted_preceders:
        cases.append((prior + pi_qu + 'a', [3]))
        cases.append((prior + pi_qu + ' a', [4]))
    cases.append(('a' + pi_qu + 'a', [3]))
    cases.append(('a' + pi_qu + ' a', [3, 4]))
    cases.append((pi_qu + 'a', [2]))

    for suffix in [' ', '\xa0', '\u2060', '}', '"', ')', '!', ',', '/',
                   '\x0b', '\r', '\n', '\x85', '\u200b']:
        cases.append(('a' + pf_qu + suffix, [3]))
    cases.append(('a' + pf_qu, [2]))

    cases.extend([
        (ea + '"', [2]),
        ('"' + ea, [2]),
        (ea + '"' + ea, [3]),
        (ea + '"' + 'a', [3]),
        ('"' + ea + ea, [3]),
        ('"' + ea + 'a', [2, 3]),
    ])

    for prior in ['\x0b', '\r', '\n', '\x85', ' ', '\u200b', '\ufffc']:
        cases.append((prior + '-a', [1, 3]))
    cases.append(('\xa0-a', [3]))

    cases.extend([
        ('%(' + '0', [3]),
        ('%(' + ',0', [4]),
        ('%(' + ',a', [1, 4]),
        ('%(' + ',', [1, 3]),
        ('0,}%', [4]),
        ('0,)%', [4]),
        ('a,}%', [3, 4]),
    ])

    cases.extend([
        ('\U00011003' + dot, [2]),
        (dot + vf, [2]),
        (dot + vi, [2]),
        (vi + dot + dot, [1, 3]),
        (dot + dot + vf, [3]),
        (dot + vi + dot, [3]),
        (dot + vi + 'a', [2, 3]),
        ('a' + vi + dot, [1, 2, 3]),
    ])

    for text, expected in cases:
        assert [item.index for item in iter_line_breaks(text)] == expected


@pytest.mark.parametrize('text,expected', [
    ('', []),
    ('abc', [3]),
    ('a\u200bb', [2, 3]),
    ('a\u2060b', [3]),
    ('a\ufeffb', [3]),
    ('a\u00a0b', [3]),
    ('a\u202fb', [3]),
    ('a\u2007b', [3]),
    ('a\u3000b', [2, 3]),
    ('a\u1680b', [2, 3]),
    ('a\u2000b', [2, 3]),
    ('a\u200ab', [2, 3]),
    ('a-b', [2, 3]),
    ('a b', [2, 3]),
])
def test_iter_line_breaks(text, expected):
    assert [break_opportunity.index for break_opportunity in iter_line_breaks(text)] == expected


@pytest.mark.parametrize('text,expected', [
    ('a-b', [3]),
    ('a\u00adb', [3]),
    ('a\u2010b', [3]),
])
def test_iter_line_breaks_without_hyphens(text, expected):
    assert [break_opportunity.index
            for break_opportunity in iter_line_breaks(text, hyphens=False)] == expected


@pytest.mark.parametrize('text,expected', [
    ('a\nb', [(2, True), (3, False)]),
    ('a\r\nb', [(3, True), (4, False)]),
    ('a\rb', [(2, True), (3, False)]),
    ('a\x85b', [(2, True), (3, False)]),
    ('a\u2028b', [(2, True), (3, False)]),
    ('a\u2029b', [(2, True), (3, False)]),
])
def test_iter_line_breaks_mandatory(text, expected):
    assert [(break_opportunity.index, break_opportunity.mandatory)
            for break_opportunity in iter_line_breaks(text)] == expected


def test_iter_line_breaks_regional_indicators():
    """Regional indicator runs break only between pairs, following LB30a."""
    text = '\U0001f1fa\U0001f1f8' * 500
    assert [item.index for item in iter_line_breaks(text)] == list(range(2, 1001, 2))


@pytest.mark.parametrize('text,expected', [
    ('aa', [2]),
    ('\x00%', [2]),
    ('( a', [3]),
    ('\u2018 b', [3]),
    ('a\u2018 b', [3, 4]),
    ('\u4e2d\u4e2d', [1, 2]),
    ('\u4e2d\u200d\u4e2d', [3]),
])
def test_iter_line_breaks_rule_shortcuts(text, expected):
    """Short-circuited class pairs agree with the full rule chain."""
    assert [item.index for item in iter_line_breaks(text)] == expected


def test_linebreak_unicode_version_stable():
    """The generated table version matches the reported constant."""
    assert LINEBREAK_UNICODE_VERSION == list_versions()[-1]


@pytest.mark.skipif(not os.path.exists(TEST_FILE),
                    reason='LineBreakTest.txt is missing; run bin/update-tables.py')
@pytest.mark.parametrize(('text', 'expected'), read_line_break_test())
def test_unicode_line_break_test(text, expected):
    """Validate against official Unicode LineBreakTest.txt."""
    assert {break_opportunity.index for break_opportunity in iter_line_breaks(text)} == expected


def test_c_extension_matches_python(monkeypatch):
    """The C extension and the Python fallback produce identical break opportunities."""
    extension = pytest.importorskip('wcwidth._wcwidth_c')
    text = ('The quick brown fox jumps over the lazy dog.\n'
            '日本語のテキストは、単語の間に空白を置かない。'
            'foo\u200bbar foo\u00a0bar \U0001f1fa\U0001f1f8 cafe\u0301')
    with_hyphens = extension.line_breaks(text)
    without_hyphens = extension.line_breaks(text, hyphens=False)
    monkeypatch.setattr(linebreak, '_C_LINE_BREAKS', None)
    assert [(item.index, item.mandatory)
            for item in linebreak.iter_line_breaks(text)] == with_hyphens
    assert [(item.index, item.mandatory)
            for item in linebreak.iter_line_breaks(text, hyphens=False)] == without_hyphens
