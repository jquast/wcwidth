"""
wcwidth module.

https://github.com/jquast/wcwidth
"""
# re-export all functions, even private ones, from top-level module
# path, to allow for 'from wcwidth import _private_func'.  Of course, user
# beware that any _private function may disappear or change signature at any
# future version.

# local
from .wcwidth import (wcwidth,
                      wcswidth,
                      _bisearch,
                      ZERO_WIDTH,
                      list_versions,
                      WIDE_EASTASIAN,
                      _wcmatch_version,
                      _wcversion_value,
                      _get_package_version,
                      )

# The __all__ attribute defines the items exported from statement,
# 'from wcwidth import *', but also to say, "This is the public API".
__all__ = ('wcwidth', 'wcswidth', 'list_versions')
__version__ = _get_package_version()
