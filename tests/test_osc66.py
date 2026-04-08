"""Tests for OSC 66 (Kitty Text Sizing Protocol) support."""
# 3rd party
import pytest

# local
import wcwidth
from wcwidth.osc66 import (
    OSC66Metadata,
    parse_osc66_metadata,
    make_osc66_metadata,
    parse_osc66_sequence,
    osc66_width,
    make_osc66_sequence,
    osc66_wrap,
    osc66_scale,
    _replace_osc66_with_padding,
)


PARSE_METADATA_CASES = [
    ('', OSC66Metadata()),
    ('s=2', OSC66Metadata(scale=2)),
    ('w=3', OSC66Metadata(width=3)),
    ('s=2:w=3', OSC66Metadata(scale=2, width=3)),
    ('s=2:w=3:n=1:d=2:v=1:h=2',
     OSC66Metadata(scale=2, width=3, numerator=1, denominator=2,
                   vertical_align=1, horizontal_align=2)),
    ('n=5:d=10', OSC66Metadata(numerator=5, denominator=10)),
    ('v=0:h=0', OSC66Metadata()),
    ('s=1:w=0', OSC66Metadata()),
]


@pytest.mark.parametrize('raw,expected', PARSE_METADATA_CASES)
def test_parse_osc66_metadata(raw, expected):
    assert parse_osc66_metadata(raw) == expected


PARSE_METADATA_CLAMP_CASES = [
    ('s=0', OSC66Metadata(scale=1)),
    ('s=9', OSC66Metadata(scale=7)),
    ('w=8', OSC66Metadata(width=7)),
    ('n=20', OSC66Metadata(numerator=15)),
    ('d=99', OSC66Metadata(denominator=15)),
    ('v=5', OSC66Metadata(vertical_align=2)),
    ('h=3', OSC66Metadata(horizontal_align=2)),
    ('w=-1', OSC66Metadata(width=0)),
]


@pytest.mark.parametrize('raw,expected', PARSE_METADATA_CLAMP_CASES)
def test_parse_osc66_metadata_clamp(raw, expected):
    assert parse_osc66_metadata(raw) == expected


PARSE_METADATA_EDGE_CASES = [
    ('unknown=5', OSC66Metadata()),
    ('s=2:unknown=5:w=3', OSC66Metadata(scale=2, width=3)),
    ('s=abc', OSC66Metadata()),
    ('s=', OSC66Metadata()),
    ('noequalssign', OSC66Metadata()),
    ('s=2:w=3:', OSC66Metadata(scale=2, width=3)),
    (':s=2', OSC66Metadata(scale=2)),
]


@pytest.mark.parametrize('raw,expected', PARSE_METADATA_EDGE_CASES)
def test_parse_osc66_metadata_edge(raw, expected):
    assert parse_osc66_metadata(raw) == expected


MAKE_METADATA_CASES = [
    (OSC66Metadata(), ''),
    (OSC66Metadata(scale=2), 's=2'),
    (OSC66Metadata(width=3), 'w=3'),
    (OSC66Metadata(scale=2, width=3), 's=2:w=3'),
    (OSC66Metadata(scale=2, width=3, numerator=1, denominator=2,
                   vertical_align=1, horizontal_align=2),
     's=2:w=3:n=1:d=2:v=1:h=2'),
]


@pytest.mark.parametrize('meta,expected', MAKE_METADATA_CASES)
def test_make_osc66_metadata(meta, expected):
    assert make_osc66_metadata(meta) == expected


METADATA_ROUNDTRIP_CASES = [
    OSC66Metadata(),
    OSC66Metadata(scale=3),
    OSC66Metadata(scale=2, width=5),
    OSC66Metadata(scale=7, width=7, numerator=15, denominator=15,
                  vertical_align=2, horizontal_align=2),
    OSC66Metadata(numerator=1, denominator=2),
]


@pytest.mark.parametrize('meta', METADATA_ROUNDTRIP_CASES)
def test_metadata_roundtrip(meta):
    assert parse_osc66_metadata(make_osc66_metadata(meta)) == meta


PARSE_SEQUENCE_CASES = [
    ('\x1b]66;s=2;hello\x07',
     (OSC66Metadata(scale=2), 'hello', '\x07')),
    ('\x1b]66;s=2;hello\x1b\\',
     (OSC66Metadata(scale=2), 'hello', '\x1b\\')),
    ('\x1b]66;;text\x07',
     (OSC66Metadata(), 'text', '\x07')),
    ('\x1b]66;s=3:w=2;\x07',
     (OSC66Metadata(scale=3, width=2), '', '\x07')),
    ('\x1b]66;w=5;AB\x07',
     (OSC66Metadata(width=5), 'AB', '\x07')),
]


@pytest.mark.parametrize('seq,expected', PARSE_SEQUENCE_CASES)
def test_parse_osc66_sequence(seq, expected):
    assert parse_osc66_sequence(seq) == expected


PARSE_SEQUENCE_NONE_CASES = [
    '\x1b[31m',
    '\x1b]0;title\x07',
    '\x1b]65;s=2;text\x07',
    'plain text',
    '',
    '\x1b]66;missing_second_semi\x07',
]


@pytest.mark.parametrize('seq', PARSE_SEQUENCE_NONE_CASES)
def test_parse_osc66_sequence_none(seq):
    assert parse_osc66_sequence(seq) is None


OSC66_WIDTH_CASES = [
    (OSC66Metadata(scale=2, width=3), 'anything', 6),
    (OSC66Metadata(scale=1, width=5), '', 5),
    (OSC66Metadata(scale=3, width=1), 'x', 3),
    (OSC66Metadata(scale=1, width=0), 'AB', 2),
    (OSC66Metadata(scale=2, width=0), 'AB', 4),
    (OSC66Metadata(scale=1, width=0), '\u4e2d', 2),
    (OSC66Metadata(scale=2, width=0), '\u4e2d', 4),
    (OSC66Metadata(scale=1, width=0), '', 0),
    (OSC66Metadata(scale=3, width=0), '', 0),
]


@pytest.mark.parametrize('meta,inner,expected', OSC66_WIDTH_CASES)
def test_osc66_width(meta, inner, expected):
    assert osc66_width(meta, inner) == expected


MAKE_SEQUENCE_CASES = [
    ('hi', OSC66Metadata(scale=2, width=1), '\x07',
     '\x1b]66;s=2:w=1;hi\x07'),
    ('AB', OSC66Metadata(scale=2, width=2), '\x1b\\',
     '\x1b]66;s=2:w=2;AB\x1b\\'),
    ('x', OSC66Metadata(), '\x07',
     '\x1b]66;;x\x07'),
    ('', OSC66Metadata(scale=3, width=2), '\x07',
     '\x1b]66;s=3:w=2;\x07'),
]


@pytest.mark.parametrize('text,meta,term,expected', MAKE_SEQUENCE_CASES)
def test_make_osc66_sequence(text, meta, term, expected):
    assert make_osc66_sequence(text, meta, term) == expected


def test_make_osc66_sequence_payload_limit():
    text = 'x' * 4097
    with pytest.raises(ValueError, match='4096'):
        make_osc66_sequence(text, OSC66Metadata())


WRAP_CASES = [
    (dict(text='AB', scale=2, width=2),
     '\x1b]66;s=2:w=2;AB\x07'),
    (dict(text='AB', scale=2, width=2, terminator='\x1b\\'),
     '\x1b]66;s=2:w=2;AB\x1b\\'),
    (dict(text='x', scale=1),
     '\x1b]66;;x\x07'),
    (dict(text='hi', scale=3, width=1, numerator=1, denominator=2,
          vertical_align=1, horizontal_align=2),
     '\x1b]66;s=3:w=1:n=1:d=2:v=1:h=2;hi\x07'),
]


@pytest.mark.parametrize('kwargs,expected', WRAP_CASES)
def test_osc66_wrap(kwargs, expected):
    assert osc66_wrap(**kwargs) == expected


SCALE_CASES = [
    ('AB', 2, '\x1b]66;s=2:w=2;AB\x07'),
    ('\u4e2d', 2, '\x1b]66;s=2:w=2;\u4e2d\x07'),
    ('x', 3, '\x1b]66;s=3:w=1;x\x07'),
    ('hello', 1, '\x1b]66;w=5;hello\x07'),
]


@pytest.mark.parametrize('text,scale,expected', SCALE_CASES)
def test_osc66_scale(text, scale, expected):
    assert osc66_scale(text, scale) == expected


def test_osc66_scale_st_terminator():
    result = osc66_scale('AB', 2, terminator='\x1b\\')
    assert result == '\x1b]66;s=2:w=2;AB\x1b\\'


# --- Integration tests: width() ---

WIDTH_PARSE_CASES = [
    ('\x1b]66;s=2:w=3;anything\x07', 6),
    ('\x1b]66;w=3;x\x07', 3),
    ('\x1b]66;s=1:w=0;AB\x07', 2),
    ('\x1b]66;s=2:w=0;AB\x07', 4),
    ('\x1b]66;s=2:w=0;\u4e2d\x07', 4),
    ('\x1b]66;s=1:w=0;\x07', 0),
    ('abc\x1b]66;w=3;x\x07def', 9),
    ('\x1b]66;w=2;A\x07\x1b]66;w=3;B\x07', 5),
    ('\x1b]66;s=2:w=3;text\x1b\\', 6),
    ('\x1b[31m\x1b]66;w=2;AB\x07\x1b[0m', 2),
]


@pytest.mark.parametrize('text,expected', WIDTH_PARSE_CASES)
def test_width_osc66_parse(text, expected):
    assert wcwidth.width(text) == expected


@pytest.mark.parametrize('text,expected', WIDTH_PARSE_CASES)
def test_width_osc66_ignore(text, expected):
    assert wcwidth.width(text, control_codes='ignore') == expected


@pytest.mark.parametrize('text,expected', WIDTH_PARSE_CASES)
def test_width_osc66_strict(text, expected):
    assert wcwidth.width(text, control_codes='strict') == expected


# --- Integration tests: strip_sequences() ---

STRIP_OSC66_CASES = [
    ('\x1b]66;s=2;hello\x07', 'hello'),
    ('\x1b]66;s=2;hello\x1b\\', 'hello'),
    ('\x1b]66;;text\x07', 'text'),
    ('\x1b]66;s=3:w=2;\x07', ''),
    ('abc\x1b]66;w=2;XY\x07def', 'abcXYdef'),
    ('\x1b[31m\x1b]66;s=2;red\x07\x1b[0m', 'red'),
    ('\x1b]66;w=1;A\x07\x1b]66;w=1;B\x07', 'AB'),
]


@pytest.mark.parametrize('text,expected', STRIP_OSC66_CASES)
def test_strip_sequences_osc66(text, expected):
    assert wcwidth.strip_sequences(text) == expected


# --- Integration tests: iter_sequences() ---

def test_iter_sequences_osc66():
    text = 'abc\x1b]66;s=2;hello\x07def'
    segments = list(wcwidth.iter_sequences(text))
    assert segments == [
        ('abc', False),
        ('\x1b]66;s=2;hello\x07', True),
        ('def', False),
    ]


def test_iter_sequences_osc66_st():
    text = '\x1b]66;w=2;AB\x1b\\'
    segments = list(wcwidth.iter_sequences(text))
    assert segments == [('\x1b]66;w=2;AB\x1b\\', True)]


# --- Integration tests: clip() ---

CLIP_OSC66_CASES = [
    ('\x1b]66;w=3;ABC\x07', 0, 3, '\x1b]66;w=3;ABC\x07'),
    ('\x1b]66;w=3;ABC\x07', 0, 2, '  '),
    ('\x1b]66;w=3;ABC\x07', 1, 3, '  '),
    ('ab\x1b]66;w=2;XY\x07cd', 0, 6, 'ab\x1b]66;w=2;XY\x07cd'),
    ('ab\x1b]66;w=2;XY\x07cd', 0, 3, 'ab '),
    ('ab\x1b]66;w=2;XY\x07cd', 4, 6, 'cd'),
]


@pytest.mark.parametrize('text,start,end,expected', CLIP_OSC66_CASES)
def test_clip_osc66(text, start, end, expected):
    assert wcwidth.clip(text, start, end) == expected


# --- Internal helper ---

REPLACE_PADDING_CASES = [
    ('\x1b]66;w=3;x\x07', '   '),
    ('\x1b]66;s=2:w=2;AB\x07', '    '),
    ('abc\x1b]66;w=1;x\x07def', 'abc def'),
    ('no osc66 here', 'no osc66 here'),
]


@pytest.mark.parametrize('text,expected', REPLACE_PADDING_CASES)
def test_replace_osc66_with_padding(text, expected):
    assert _replace_osc66_with_padding(text) == expected
