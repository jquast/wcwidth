"""
Tests for clip() handling of cursor left/right sequences (CSI <n>C / CSI <n>D).

These tests codify expected visible results when cursor movement sequences affect horizontal
positions. They are intentionally specific and will drive future implementation changes in clip().
"""

# 3rd party
import pytest

# local
from wcwidth import clip


@pytest.mark.parametrize("text,start,end,expected", [
    # Cursor-right introduces a gap that should be filled with spaces
    ("hello\x1b[10Cworld", 0, 10, "hello" + " " * 5),
    # Clipping just the initial region ignores the later rightward write
    ("hello\x1b[10Cworld", 0, 5, "hello"),
    # Cursor-left overwrites previous characters
    ("hello\x1b[2DXY", 0, 5, "helXY"),
    ('ab\x1b[5Ccd', 0, 4, 'ab  '),
    ('abcde\x1b[2Df', 0, 6, 'abcf'),
    ('ab\x1b[10Ccd', 0, 4, 'ab  '),
    ('XY\x1b[Czy', 0, 4, 'XY z'),
    ('XY\x1b[Czy', 0, 5, 'XY zy'),
    ('XY\x1b[Czy', 1, 3, 'Y '),
    ('XY\x1b[Czy', 1, 4, 'Y z'),
    ('LOL\x1b[5Clol', 0, 12, 'LOL     lol'),
    ('LOL\x1b[5Clol', 1, 11, 'OL     lol'),
    ('LOL\x1b[5Clol', 2, 11, 'L     lol'),
    ('LOL\x1b[5Clol', 3, 11, '     lol'),
    ('LOL\x1b[5Clol', 4, 11, '    lol'),
    ('LOL\x1b[5Clol', 5, 11, '   lol'),
    ('LOL\x1b[5Clol', 6, 11, '  lol'),
    ('LOL\x1b[5Clol', 7, 11, ' lol'),
    ('LOL\x1b[5Clol', 8, 11, 'lol'),
    ('LOL\x1b[5Clol', 9, 11, 'ol'),

])
def test_clip_cursor_sequences_expected_behaviour(text, start, end, expected):
    """
    Verify clip() output matches terminal-visible columns after cursor moves.

    These tests capture the desired semantics: cursor-right creates blank cells (fillchar) in
    the clipped output if the moved-to columns are within the clip window; cursor-left allows
    subsequent characters to overwrite previous content and the clip should reflect that.
    """
    assert repr(clip(text, start, end)) == repr(expected)
