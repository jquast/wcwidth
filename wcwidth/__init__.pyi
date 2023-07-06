from typing import Optional, Tuple


def wcwidth(wc: str, unicode_version: str = ...) -> int:
    ...


def wcswidth(pwcs: str, n: Optional[int] = None, unicode_version: str = ...):
    ...


def list_versions() -> Tuple[str]:
    ...


__version__: str = ...
