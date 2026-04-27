"""Tests for Text Sizing Protocol (OSC 66) support."""
# 3rd party
import pytest

# local
import wcwidth
from wcwidth.text_sizing import TextSizing, TextSizingParams
from wcwidth.escape_sequences import TEXT_SIZING_PATTERN

CONTROL_CODES_PARAMS_CASES = [
    ('x=2', "", "Unknown text sizing field 'x' in "),
    ('s=3:x=3', "s=3", "Unknown text sizing field 'x' in "),
    ('s=2:x=3:w=9', "s=2:w=7", "Unknown text sizing field 'x' in "),
    ('xyz=2', "", "Unknown text sizing field 'xyz' in "),
    ('xxx', "", "Expected '=' in text sizing parameter"),
    ('s=xxx', "", "Illegal text sizing value 'xxx' in "),
    ('s=-99', "", "Out of bounds text sizing value '-99' in "),
    ('s=99', "s=7", "Out of bounds text sizing value '99' in "),
    ('w=-1', "", "Out of bounds text sizing value '-1' in "),
    ('w=8', "w=7", "Out of bounds text sizing value '8' in "),
    ('n=20', "n=15", "Out of bounds text sizing value '20' in "),
    ('d=99', "d=15", "Out of bounds text sizing value '99' in "),
    ('v=5', "v=2", "Out of bounds text sizing value '5' in "),
    ('h=3', "h=2", "Out of bounds text sizing value '3' in "),
]


@pytest.mark.parametrize('given_params,expected_remainder,expected_exc,', CONTROL_CODES_PARAMS_CASES)
def test_text_sizing_params_control_codes(given_params, expected_remainder, expected_exc):
    """Verify control_codes='strict' and 'parse' behavior in TextSizingParams.from_params()."""
    # assert control_codes='strict' raises expected exception,
    with pytest.raises(ValueError) as exc_info:
        TextSizingParams.from_params(given_params, control_codes='strict')
    assert exc_info.value.args[0].startswith(expected_exc)

    # when 'parse' (default), any illegal argument or value is filtered, excluded, or clipped
    params = TextSizingParams.from_params(given_params)
    assert params.make_sequence() == expected_remainder


@pytest.mark.parametrize('given_params,expected_remainder,expected_exc,', CONTROL_CODES_PARAMS_CASES)
def test_text_sizing_width_control_codes(given_params, expected_remainder, expected_exc):
    """Verify control_codes='strict' with invalid OSC 66 sequences in wciwdth.width()."""
    seq1 = '\x1b]66;' + given_params + ';ABC' + '\x07'
    seq2 = '\x1b]66;' + given_params + ';ABC' + '\x1b\\'
    for seq in (seq1, seq2):
        with pytest.raises(ValueError) as exc_info:
            wcwidth.width(seq, control_codes='strict')
        assert exc_info.value.args[0].startswith(expected_exc)


@pytest.mark.parametrize('params,text,expected_width', [
    # cases of static width=N values,
    (TextSizingParams(scale=2, width=3), 'anything', 6),
    (TextSizingParams(scale=1, width=5), '', 5),
    (TextSizingParams(scale=3, width=1), 'x', 3),
    # and automatic width (width=0) values,
    (TextSizingParams(scale=1), 'AB', 2),
    (TextSizingParams(scale=2), 'AB', 4),
    (TextSizingParams(scale=1), '中', 2),
    (TextSizingParams(scale=2), '中', 4),
    (TextSizingParams(scale=1), '', 0),
    (TextSizingParams(scale=3), '', 0),
])
def test_text_sizing_width(params, text, expected_width):
    """Verify width using with both kinds of terminator."""
    assert TextSizing(params, text, terminator='\x07').display_width() == expected_width
    assert TextSizing(params, text, terminator='\x1b\\').display_width() == expected_width
    seq1 = TextSizing(params, text, terminator='\x07').make_sequence()
    seq2 = TextSizing(params, text, terminator='\x1b\\').make_sequence()
    assert wcwidth.width(seq1) == expected_width
    assert wcwidth.width(seq2) == expected_width


#    ('abc\x1b]66;w=3;x\x07def', 'x', 'w=3', 7),
#    ('\x1b[31m\x1b]66;w=2;AB\x07\x1b[0m', 2),
@pytest.mark.parametrize('given_sequence,expected_text,expected_params,expected_width', [
    ('\x1b]66;s=2:w=2;AB\x07', 'AB', 's=2:w=2', 4),
    ('\x1b]66;s=2:w=2;\u4e2d\x07', '\u4e2d', 's=2:w=2', 4),
    ('\x1b]66;s=3:w=1;x\x07', 'x', 's=3:w=1', 3),
    ('\x1b]66;w=5;hello\x07', 'hello', 'w=5', 5),
    ('\x1b]66;s=2:w=3;anything\x07', 'anything', 's=2:w=3', 6),
    ('\x1b]66;w=3;x\x07', 'x', 'w=3', 3),
    ('\x1b]66;s=1;AB\x07', 'AB', '', 2),
    ('\x1b]66;s=2;AB\x07', 'AB', 's=2', 4),
    ('\x1b]66;s=2;中\x07', '中', 's=2', 4),
    ('\x1b]66;s=2;\x07', '', 's=2', 0),
    ('\x1b]66;s=1:w=1;\x07', '', 'w=1', 1),
    ('\x1b]66;w=2;A\x07', 'A', 'w=2', 2),
    ('\x1b]66;s=2:w=3;text\x1b\\', 'text', 's=2:w=3', 6),
])
def test_text_sizing_scale_width(given_sequence, expected_text, expected_params, expected_width):
    ts_match = TEXT_SIZING_PATTERN.match(given_sequence)
    assert ts_match is not None
    text_size = TextSizing.from_match(ts_match)
    assert text_size.params.make_sequence() == expected_params
    assert text_size.text == expected_text
    assert wcwidth.width(given_sequence, control_codes='parse') == expected_width
    assert wcwidth.width(given_sequence, control_codes='strict') == expected_width
    assert wcwidth.width(given_sequence, control_codes='ignore') == wcwidth.wcswidth(expected_text)


WIDTH_PARSE_IGNORED_CASES = [
    # when control_codes='ignore', only the 'inner text' width is naturally
    # measured, its
]


@pytest.mark.parametrize('text,expected', WIDTH_PARSE_IGNORED_CASES)
def test_width_text_sizing_ignored(text, expected):
    assert wcwidth.width(text, control_codes='ignore') == expected


WIDTH_PARSE_CASES = [
    ('\x1b]66;s=2:w=3;anything\x07', 6),
    ('\x1b]66;w=3;x\x07', 3),
    ('\x1b]66;s=1:w=0;AB\x07', 2),
    ('\x1b]66;s=2:w=0;AB\x07', 4),
    ('\x1b]66;s=2:w=0;\u4e2d\x07', 4),  # '中'
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
def test_width_text_sizing_strict(text, expected):
    assert wcwidth.width(text, control_codes='strict') == expected


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


# ___REPLACE_PADDING_CASES = [
#    ('\x1b]66;w=3;x\x07', '   '),
#    ('\x1b]66;s=2:w=2;AB\x07', '    '),
#    ('abc\x1b]66;w=1;x\x07def', 'abc def'),
#    ('no text sizing here', 'no text sizing here'),
# ]
#
#
#
#
#
# CONTROL_CODES_WIDTH_CASES = [
#    ('hi', dict(scale=2, width=1), '\x07',
#     '\x1b]66;s=2:w=1;hi\x07'),
#    ('AB', dict(scale=2, width=2), '\x1b\\',
#     '\x1b]66;s=2:w=2;AB\x1b\\'),
#    ('x', {}, '\x07',
#     '\x1b]66;;x\x07'),
#    ('', dict(scale=3, width=2), '\x07',
#     '\x1b]66;s=3:w=2;\x07'),
#        ]
# MAKE_SEQUENCE_CASES = [

#
# WRAP_CASES = [
#    (TextSizingParams(scale=2, width=2),
#     '\x1b]66;s=2:w=2;ABC\x1b\\'),
#    (TextSizingParams(scale=2, width=2),
#     '\x1b]66;s=2:w=2;ABC\x1b\\'),
#    (TextSizingParams(scale=1),
#     '\x1b]66;;ABC\x1b\\'),
#    (TextSizingParams(scale=3, width=1, numerator=1, denominator=2,
#                      vertical_align=1, horizontal_align=2),
#     '\x1b]66;s=3:w=1:n=1:d=2:v=1:h=2;ABC\x1b\\'),
# ]
#
# @pytest.mark.parametrize('params,expected', WRAP_CASES)
# def test_wrap(params, expected):
#    text = 'ABC'
#    terminator = '\x1b\\'
#    assert TextSizing(params, text, terminator).make_sequence() == expected
#
# def test_scale_st_terminator():
#    text, scale = 'AB', 2
#    inner_w = wcwidth.wcswidth(text)
#    result = _build_seq(text,
#                        TextSizingParams(scale=scale, width=max(0, inner_w)),
#                        terminator='\x1b\\')
#    assert result == '\x1b]66;s=2:w=2;AB\x1b\\'
#
#
# @pytest.mark.parametrize('text,kwargs,term,expected', MAKE_SEQUENCE_CASES)
# def test_make_sequence(text, kwargs, term, expected):
#    assert TextSizing(text, terminator=term, **kwargs) == expected
#
#
# @pytest.mark.parametrize('raw,expected', PARSE_PARAMS_EDGE_CASES)
# def test_parse_text_sizing_params_edge(raw, expected):
#    assert _parse_text_sizing_params(raw) == expected
#
#
# PARAMS_ROUNDTRIP_CASES = [
#    TextSizingParams(),
#    TextSizingParams(scale=3),
#    TextSizingParams(scale=2, width=5),
#    TextSizingParams(scale=7, width=7, numerator=15, denominator=15,
#                     vertical_align=2, horizontal_align=2),
#    TextSizingParams(numerator=1, denominator=2),
# ]
#
# @pytest.mark.parametrize('params', PARAMS_ROUNDTRIP_CASES)
# def test_params_roundtrip(params):
#    text_size = TextSizing(params, "abc", terminator="\x07")
#    #assert _parse_text_sizing_params(_make_params_str(params)) == params

# PARSE_PARAMS_CASES = [
#    ('', TextSizingParams()),
#    ('s=2', TextSizingParams(scale=2)),
#    ('w=3', TextSizingParams(width=3)),
#    ('s=2:w=3', TextSizingParams(scale=2, width=3)),
#    ('s=2:w=3:n=1:d=2:v=1:h=2',
#     TextSizingParams(scale=2, width=3, numerator=1, denominator=2,
#                      vertical_align=1, horizontal_align=2)),
#    ('n=5:d=10', TextSizingParams(numerator=5, denominator=10)),
#    ('v=0:h=0', TextSizingParams()),
#    ('s=1:w=0', TextSizingParams()),
# ]

# PARSE_SEQUENCE_CASES = [
#    ('\x1b]66;s=2;hello\x07',
#     (TextSizingParams(scale=2), 'hello', '\x07')),
#    ('\x1b]66;s=99;hello\x07',
#     (TextSizingParams(scale=TextSizingParams.FIELD_MAPPING['s'].high), 'hello', '\x07')),
#    ('\x1b]66;s=-99;hello\x07',
#     (TextSizingParams(scale=TextSizingParams.FIELD_MAPPING['s'].low), 'hello', '\x07')),
#    ('\x1b]66;s=2;hello\x1b\\',
#     (TextSizingParams(scale=2), 'hello', '\x1b\\')),
#    ('\x1b]66;;text\x07',
#     (TextSizingParams(), 'text', '\x07')),
#    ('\x1b]66;s=3:w=2;\x07',
#     (TextSizingParams(scale=3, width=2), '', '\x07')),
#    ('\x1b]66;w=5;AB\x07',
#     (TextSizingParams(width=5), 'AB', '\x07')),
#    ('\x1b]66;s=7;' + ('X' * 30) + '\x07',
#     (TextSizingParams(scale=7), 'X' * 30, '\x07')),
# ]

#
# @pytest.mark.parametrize('seq,expected', PARSE_SEQUENCE_CASES)
# def test_parse_text_sizing(seq, expected):
#    assert parse_text_sizing(seq) == expected


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
