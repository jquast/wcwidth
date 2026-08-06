"""Type stub for the optional C extension ``wcwidth._wcwidth_c``.

Mirrors the signatures of the pure-Python implementations in wcwidth/; the
runtime behavior is identical.  When this module is not built, the package
falls back to the pure-Python implementation.
"""

# pylint: disable=unused-argument

# std imports
from typing import Literal, Optional, Sequence, Union

TermProgram = Union[bool, str]
ControlCodes = Literal['parse', 'strict', 'ignore']


def wcwidth(wc: str, unicode_version: str = 'auto', ambiguous_width: int = 1) -> int: ...
def wcswidth(
    pwcs: str,
    n: Optional[int] = None,
    unicode_version: str = 'auto',
    ambiguous_width: int = 1,
) -> int: ...
def wcstwidth(
    pwcs: str,
    n: Optional[int] = None,
    unicode_version: str = 'auto',
    ambiguous_width: int = 1,
    term_program: TermProgram = True,
) -> int: ...
def width(
    text: str,
    *,
    control_codes: ControlCodes = 'parse',
    tabsize: int = 8,
    ambiguous_width: int = 1,
    term_program: TermProgram = False,
) -> int: ...
def wrap(
    text: str,
    width: int = 70,
    *,
    control_codes: ControlCodes = 'parse',
    tabsize: int = 8,
    expand_tabs: bool = True,
    replace_whitespace: bool = True,
    ambiguous_width: int = 1,
    term_program: TermProgram = False,
    initial_indent: str = '',
    subsequent_indent: str = '',
    fix_sentence_endings: bool = False,
    break_long_words: bool = True,
    break_on_hyphens: bool = True,
    drop_whitespace: bool = True,
    max_lines: Optional[int] = None,
    placeholder: str = ' [...]',
    propagate_sgr: bool = True,
) -> list[str]: ...
def clip(
    text: str,
    start: int,
    end: int,
    *,
    fillchar: str = ' ',
    tabsize: int = 8,
    ambiguous_width: int = 1,
    propagate_sgr: bool = True,
    control_codes: ControlCodes = 'parse',
    overtyping: Optional[bool] = None,
    term_program: TermProgram = False,
) -> str: ...
def ljust(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: ControlCodes = 'parse',
    ambiguous_width: int = 1,
    term_program: TermProgram = False,
) -> str: ...
def rjust(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: ControlCodes = 'parse',
    ambiguous_width: int = 1,
    term_program: TermProgram = False,
) -> str: ...
def center(
    text: str,
    dest_width: int,
    fillchar: str = ' ',
    *,
    control_codes: ControlCodes = 'parse',
    ambiguous_width: int = 1,
    term_program: TermProgram = False,
) -> str: ...
def strip_sequences(text: str) -> str: ...
def propagate_sgr(lines: Sequence[str]) -> list[str]: ...
