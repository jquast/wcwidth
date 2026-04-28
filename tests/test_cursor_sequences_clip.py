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
])
def test_clip_cursor_sequences_expected_behaviour(text, start, end, expected):
    """
    Verify clip() output matches terminal-visible columns after cursor moves.

    These tests capture the desired semantics: cursor-right creates blank cells (fillchar) in
    the clipped output if the moved-to columns are within the clip window; cursor-left allows
    subsequent characters to overwrite previous content and the clip should reflect that.
    """
    assert clip(text, start, end) == expected
