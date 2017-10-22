"""
wcwidth module.

https://github.com/jquast/wcwidth
"""
# re-export all functions, even private ones, from top-level module
# path, to allow for 'from wcwidth import _private_func'.  Of course, user
# beware that any _private function may disappear or change signature at any
# future version.
from .wcwidth import (
    _bisearch,
    wcwidth,
    wcswidth,
    list_versions,
    _wcversion_value,
    _wcmatch_version,
    _get_package_version,
    _wcmatch_version,
)  # noqa

__all__ = ('wcwidth', 'wcswidth', 'list_versions')
__version__ = _get_package_version()
