"""Tests for Text Sizing Protocol (OSC 66) support."""
# 3rd party
import pytest

# local
import wcwidth
from wcwidth.text_sizing import (
    TextSizingParams,
    parse_text_sizing_params,
    parse_text_sizing,
    text_sizing_width,
    _replace_text_sizing_with_padding,
)


# -- Test-only helpers for generating OSC 66 sequences --

_FIELD_TO_KEY = {
    'scale': 's', 'width': 'w', 'numerator': 'n',
    'denominator': 'd', 'vertical_align': 'v', 'horizontal_align': 'h',
}

_DEFAULTS = TextSizingParams()


def _make_params_str(params):
    """Serialize TextSizingParams to colon-separated key=value string."""
    parts = []
    for field, key in _FIELD_TO_KEY.items():
        val = getattr(params, field)
        if val != getattr(_DEFAULTS, field):
            parts.append(f'{key}={val}')
    return ':'.join(parts)


def _make_seq(text, params=None, terminator='\x07', **kwargs):
    """Build a complete OSC 66 escape sequence for testing."""
    if params is None:
        params = TextSizingParams(**kwargs)
    return f'\x1b]66;{_make_params_str(params)};{text}{terminator}'


PARSE_PARAMS_CASES = [
    ('', TextSizingParams()),
    ('s=2', TextSizingParams(scale=2)),
    ('w=3', TextSizingParams(width=3)),
    ('s=2:w=3', TextSizingParams(scale=2, width=3)),
    ('s=2:w=3:n=1:d=2:v=1:h=2',
     TextSizingParams(scale=2, width=3, numerator=1, denominator=2,
                      vertical_align=1, horizontal_align=2)),
    ('n=5:d=10', TextSizingParams(numerator=5, denominator=10)),
    ('v=0:h=0', TextSizingParams()),
    ('s=1:w=0', TextSizingParams()),
]


@pytest.mark.parametrize('raw,expected', PARSE_PARAMS_CASES)
def test_parse_text_sizing_params(raw, expected):
    assert parse_text_sizing_params(raw) == expected


PARSE_PARAMS_CLAMP_CASES = [
    ('s=0', TextSizingParams(scale=1)),
    ('s=9', TextSizingParams(scale=7)),
    ('w=8', TextSizingParams(width=7)),
    ('n=20', TextSizingParams(numerator=15)),
    ('d=99', TextSizingParams(denominator=15)),
    ('v=5', TextSizingParams(vertical_align=2)),
    ('h=3', TextSizingParams(horizontal_align=2)),
    ('w=-1', TextSizingParams(width=0)),
]


@pytest.mark.parametrize('raw,expected', PARSE_PARAMS_CLAMP_CASES)
def test_parse_text_sizing_params_clamp(raw, expected):
    assert parse_text_sizing_params(raw) == expected


PARSE_PARAMS_EDGE_CASES = [
    ('unknown=5', TextSizingParams()),
    ('s=2:unknown=5:w=3', TextSizingParams(scale=2, width=3)),
    ('s=abc', TextSizingParams()),
    ('s=', TextSizingParams()),
    ('noequalssign', TextSizingParams()),
    ('s=2:w=3:', TextSizingParams(scale=2, width=3)),
    (':s=2', TextSizingParams(scale=2)),
]


@pytest.mark.parametrize('raw,expected', PARSE_PARAMS_EDGE_CASES)
def test_parse_text_sizing_params_edge(raw, expected):
    assert parse_text_sizing_params(raw) == expected


PARAMS_ROUNDTRIP_CASES = [
    TextSizingParams(),
    TextSizingParams(scale=3),
    TextSizingParams(scale=2, width=5),
    TextSizingParams(scale=7, width=7, numerator=15, denominator=15,
                     vertical_align=2, horizontal_align=2),
    TextSizingParams(numerator=1, denominator=2),
]


@pytest.mark.parametrize('params', PARAMS_ROUNDTRIP_CASES)
def test_params_roundtrip(params):
    assert parse_text_sizing_params(_make_params_str(params)) == params


PARSE_SEQUENCE_CASES = [
    ('\x1b]66;s=2;hello\x07',
     (TextSizingParams(scale=2), 'hello', '\x07')),
    ('\x1b]66;s=2;hello\x1b\\',
     (TextSizingParams(scale=2), 'hello', '\x1b\\')),
    ('\x1b]66;;text\x07',
     (TextSizingParams(), 'text', '\x07')),
    ('\x1b]66;s=3:w=2;\x07',
     (TextSizingParams(scale=3, width=2), '', '\x07')),
    ('\x1b]66;w=5;AB\x07',
     (TextSizingParams(width=5), 'AB', '\x07')),
]


@pytest.mark.parametrize('seq,expected', PARSE_SEQUENCE_CASES)
def test_parse_text_sizing(seq, expected):
    assert parse_text_sizing(seq) == expected


PARSE_SEQUENCE_NONE_CASES = [
    '\x1b[31m',
    '\x1b]0;title\x07',
    '\x1b]65;s=2;text\x07',
    'plain text',
    '',
    '\x1b]66;missing_second_semi\x07',
]


@pytest.mark.parametrize('seq', PARSE_SEQUENCE_NONE_CASES)
def test_parse_text_sizing_none(seq):
    assert parse_text_sizing(seq) is None


TEXT_SIZING_WIDTH_CASES = [
    (TextSizingParams(scale=2, width=3), 'anything', 6),
    (TextSizingParams(scale=1, width=5), '', 5),
    (TextSizingParams(scale=3, width=1), 'x', 3),
    (TextSizingParams(scale=1, width=0), 'AB', 2),
    (TextSizingParams(scale=2, width=0), 'AB', 4),
    (TextSizingParams(scale=1, width=0), '\u4e2d', 2),
    (TextSizingParams(scale=2, width=0), '\u4e2d', 4),
    (TextSizingParams(scale=1, width=0), '', 0),
    (TextSizingParams(scale=3, width=0), '', 0),
]


@pytest.mark.parametrize('params,inner,expected', TEXT_SIZING_WIDTH_CASES)
def test_text_sizing_width(params, inner, expected):
    assert text_sizing_width(params, inner) == expected


MAKE_SEQUENCE_CASES = [
    ('hi', dict(scale=2, width=1), '\x07',
     '\x1b]66;s=2:w=1;hi\x07'),
    ('AB', dict(scale=2, width=2), '\x1b\\',
     '\x1b]66;s=2:w=2;AB\x1b\\'),
    ('x', {}, '\x07',
     '\x1b]66;;x\x07'),
    ('', dict(scale=3, width=2), '\x07',
     '\x1b]66;s=3:w=2;\x07'),
]


@pytest.mark.parametrize('text,kwargs,term,expected', MAKE_SEQUENCE_CASES)
def test_make_sequence(text, kwargs, term, expected):
    assert _make_seq(text, terminator=term, **kwargs) == expected


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
def test_wrap(kwargs, expected):
    text = kwargs.pop('text')
    terminator = kwargs.pop('terminator', '\x07')
    assert _make_seq(text, terminator=terminator, **kwargs) == expected


SCALE_CASES = [
    ('AB', 2, '\x1b]66;s=2:w=2;AB\x07'),
    ('\u4e2d', 2, '\x1b]66;s=2:w=2;\u4e2d\x07'),
    ('x', 3, '\x1b]66;s=3:w=1;x\x07'),
    ('hello', 1, '\x1b]66;w=5;hello\x07'),
]


@pytest.mark.parametrize('text,scale,expected', SCALE_CASES)
def test_scale(text, scale, expected):
    inner_w = wcwidth.wcswidth(text)
    assert _make_seq(text, scale=scale, width=max(0, inner_w)) == expected


def test_scale_st_terminator():
    text, scale = 'AB', 2
    inner_w = wcwidth.wcswidth(text)
    result = _make_seq(text, scale=scale, width=max(0, inner_w), terminator='\x1b\\')
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
def test_width_text_sizing_parse(text, expected):
    assert wcwidth.width(text) == expected


@pytest.mark.parametrize('text,expected', WIDTH_PARSE_CASES)
def test_width_text_sizing_ignore(text, expected):
    assert wcwidth.width(text, control_codes='ignore') == expected


@pytest.mark.parametrize('text,expected', WIDTH_PARSE_CASES)
def test_width_text_sizing_strict(text, expected):
    assert wcwidth.width(text, control_codes='strict') == expected


# --- Integration tests: strip_sequences() ---

STRIP_TEXT_SIZING_CASES = [
    ('\x1b]66;s=2;hello\x07', 'hello'),
    ('\x1b]66;s=2;hello\x1b\\', 'hello'),
    ('\x1b]66;;text\x07', 'text'),
    ('\x1b]66;s=3:w=2;\x07', ''),
    ('abc\x1b]66;w=2;XY\x07def', 'abcXYdef'),
    ('\x1b[31m\x1b]66;s=2;red\x07\x1b[0m', 'red'),
    ('\x1b]66;w=1;A\x07\x1b]66;w=1;B\x07', 'AB'),
]


@pytest.mark.parametrize('text,expected', STRIP_TEXT_SIZING_CASES)
def test_strip_sequences_text_sizing(text, expected):
    assert wcwidth.strip_sequences(text) == expected


# --- Integration tests: iter_sequences() ---

def test_iter_sequences_text_sizing():
    text = 'abc\x1b]66;s=2;hello\x07def'
    segments = list(wcwidth.iter_sequences(text))
    assert segments == [
        ('abc', False),
        ('\x1b]66;s=2;hello\x07', True),
        ('def', False),
    ]


def test_iter_sequences_text_sizing_st():
    text = '\x1b]66;w=2;AB\x1b\\'
    segments = list(wcwidth.iter_sequences(text))
    assert segments == [('\x1b]66;w=2;AB\x1b\\', True)]


# --- Integration tests: clip() ---

CLIP_TEXT_SIZING_CASES = [
    ('\x1b]66;w=3;ABC\x07', 0, 3, '\x1b]66;w=3;ABC\x07'),
    ('\x1b]66;w=3;ABC\x07', 0, 2, '  '),
    ('\x1b]66;w=3;ABC\x07', 1, 3, '  '),
    ('ab\x1b]66;w=2;XY\x07cd', 0, 6, 'ab\x1b]66;w=2;XY\x07cd'),
    ('ab\x1b]66;w=2;XY\x07cd', 0, 3, 'ab '),
    ('ab\x1b]66;w=2;XY\x07cd', 4, 6, 'cd'),
]


@pytest.mark.parametrize('text,start,end,expected', CLIP_TEXT_SIZING_CASES)
def test_clip_text_sizing(text, start, end, expected):
    assert wcwidth.clip(text, start, end) == expected


# --- Internal helper ---

REPLACE_PADDING_CASES = [
    ('\x1b]66;w=3;x\x07', '   '),
    ('\x1b]66;s=2:w=2;AB\x07', '    '),
    ('abc\x1b]66;w=1;x\x07def', 'abc def'),
    ('no text sizing here', 'no text sizing here'),
]


@pytest.mark.parametrize('text,expected', REPLACE_PADDING_CASES)
def test_replace_text_sizing_with_padding(text, expected):
    assert _replace_text_sizing_with_padding(text) == expected
