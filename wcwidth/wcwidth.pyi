from typing import Optional


def wcwidth(wc: str, unicode_version: str = ...) -> int:
    ...


def wcswidth(pwcs: str, n: Optional[int] = None, unicode_version: str = ...):
    ...


def _bisearch(ucs: int, table: list[tuple[int, int]]) -> int:
    ...


def _wcversion_value(ver_string: str) -> tuple[int, ...]:
    ...


def _wcmatch_version(given_version: str) -> str:
    ...
