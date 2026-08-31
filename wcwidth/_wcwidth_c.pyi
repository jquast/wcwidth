"""Type stub for the optional C extension ``wcwidth._wcwidth_c``.

Mirrors the signatures of the Python implementations in wcwidth/; the
runtime behavior is identical.  When this module is not built, the package
falls back to the Python implementation.
"""

# pylint: disable=unused-argument,missing-function-docstring

from typing import Union, Literal, Optional, Sequence

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
