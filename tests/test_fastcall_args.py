"""
Argument handling of the METH_FASTCALL C binding.

Every parameter is accepted positionally and by keyword, and a call that cannot be parsed raises.
Keyword names are matched by length, not by walking the parameter list, so these spellings guard the
hand-written parser that replaces PyArg_ParseTupleAndKeywords() on the fast path.
"""

# 3rd party
import pytest

# Only the C binding has a hand-written parser; skip when the extension is not built.
_wcwidth_c = pytest.importorskip('wcwidth._wcwidth_c')

# Spellings of each call that must all give the same result: positional, keyword, and mixed.
# Within one group the values are held constant, so only the spelling varies.
SPELLINGS = [
    (_wcwidth_c.width, [
        (('abc',), {}),
        ((), {'text': 'abc'}),
        (('abc',), {'control_codes': 'parse'}),
        (('abc',), {'control_codes': 'ignore', 'tabsize': 4}),
        (('abc',), {'ambiguous_width': 1, 'term_program': False}),
        (('abc',), {'control_codes': 'parse', 'tabsize': 8, 'ambiguous_width': 1,
                    'term_program': False}),
    ]),
    (_wcwidth_c.ljust, [
        (('abc', 10), {}),
        ((), {'text': 'abc', 'dest_width': 10}),
        (('abc', 10, ' '), {}),
        (('abc', 10), {'fillchar': ' '}),
        (('abc', 10, ' '), {'ambiguous_width': 1, 'term_program': False}),
        (('abc', 10), {'control_codes': 'parse', 'ambiguous_width': 1, 'term_program': False}),
    ]),
    (_wcwidth_c.wcswidth, [
        (('abc', 2), {}),
        (('abc',), {'n': 2}),
        (('abc', 2, 'auto', 1), {}),
        (('abc', 2), {'unicode_version': 'auto', 'ambiguous_width': 1}),
        (('abc',), {'n': 2, 'unicode_version': 'auto', 'ambiguous_width': 1}),
    ]),
    (_wcwidth_c.wcstwidth, [
        (('abc', 2), {}),
        (('abc',), {'n': 2}),
        (('abc', 2, 'auto', 1, 'xterm'), {}),
        (('abc', 2), {'term_program': 'xterm'}),
        (('abc', 2), {'unicode_version': 'auto', 'ambiguous_width': 1, 'term_program': 'xterm'}),
    ]),
    (_wcwidth_c.wcwidth, [
        (('a',), {}),
        ((), {'wc': 'a'}),
        (('a', 'auto', 1), {}),
        (('a',), {'ambiguous_width': 1}),
        (('a', 'auto'), {'ambiguous_width': 1}),
    ]),
    (_wcwidth_c.clip, [
        (('abc', 0, 2), {}),
        ((), {'text': 'abc', 'start': 0, 'end': 2}),
        (('abc', 0, 2), {'fillchar': '.'}),
        (('abc', 0, 2), {'tabsize': 4, 'control_codes': 'parse', 'propagate_sgr': False}),
    ]),
    (_wcwidth_c.strip_sequences, [
        (('abc',), {}),
        ((), {'text': 'abc'}),
    ]),
    (_wcwidth_c.propagate_sgr, [
        ((['a', 'b'],), {}),
        ((), {'lines': ['a', 'b']}),
    ]),
    (lambda *args, **kwargs: list(_wcwidth_c.iter_graphemes(*args, **kwargs)), [
        (('ab',), {}),
        ((), {'unistr': 'ab'}),
        (('ab', 0, 2), {}),
        (('ab',), {'start': 0, 'end': 2}),
    ]),
]

# Calls the parser must reject.  Only the exception type is asserted: the message text is
# CPython's wording for the generic cases and varies between versions.
REJECTED = [
    (_wcwidth_c.width, (), {}),                                  # text is required
    (_wcwidth_c.width, (1,), {}),                                # text must be str
    (_wcwidth_c.width, ('a', 'b'), {}),                          # one positional at most
    (_wcwidth_c.width, ('a',), {'text': 'b'}),                   # given twice
    (_wcwidth_c.width, ('a',), {'nope': 1}),                     # unknown keyword
    (_wcwidth_c.width, ('a',), {'tabsize': 'x'}),                # not an int
    (_wcwidth_c.width, ('a',), {'tabsize': 2 ** 70}),            # out of int range
    (_wcwidth_c.width, ('a',), {'ambiguous_width': 'x'}),
    (_wcwidth_c.ljust, ('a',), {'text': 'b'}),                   # given twice
    (_wcwidth_c.ljust, ('a', 'x'), {}),                          # dest_width must be an int
    (_wcwidth_c.ljust, ('a', 5, '.', 'x'), {}),                  # three positional at most
    (_wcwidth_c.wcswidth, ('a',), {'nope': 1}),
    (_wcwidth_c.wcwidth, ('a',), {'term_program': 'xterm'}),     # not a parameter
    (_wcwidth_c.wcwidth, ('a', 'auto', 1, 2), {}),               # three positional at most
    (_wcwidth_c.clip, ('a', 0, 2, '.'), {}),                     # fillchar is keyword-only
    (_wcwidth_c.strip_sequences, ('a', 'b'), {}),
    (_wcwidth_c.propagate_sgr, ('a', 'b'), {}),
    (lambda *args, **kwargs: list(_wcwidth_c.iter_graphemes(*args, **kwargs)),
     ('a', 1, 2, 3), {}),
]

GROUP_IDS = ["width", "ljust", "wcswidth", "wcstwidth", "wcwidth", "clip",
             "strip_sequences", "propagate_sgr", "iter_graphemes"]


@pytest.mark.parametrize("func, calls", SPELLINGS, ids=GROUP_IDS)
def test_argument_spellings_agree(func, calls):
    """Positional, keyword, and mixed spellings of one call agree."""
    results = [func(*args, **kwargs) for args, kwargs in calls]
    assert results == [results[0]] * len(results)


@pytest.mark.parametrize("func, args, kwargs", REJECTED,
                         ids=[f"{i}" for i in range(len(REJECTED))])
def test_rejected_calls_raise(func, args, kwargs):
    """A call the fast parser cannot accept raises instead of falling through."""
    with pytest.raises((TypeError, OverflowError)):
        func(*args, **kwargs)
