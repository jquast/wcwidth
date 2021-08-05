"""
wcwidth module.

https://github.com/jquast/wcwidth
"""
# re-export all functions & definitions, even private ones, from top-level
# module path, to allow for 'from wcwidth import _private_func' if necessary.
# Of course, user beware that any _private function may disappear or change
# signature at any future version. This is also a bit odd in that.
#
# This effort flattens the statement, 'from wcwidth.wcwidth import wcwidth' into
# 'from wcwidth import wcwidth'.

# local
from .wcwidth import (
    width,
    wcwidth,
    wcswidth,
    list_versions,
    _wwidth,
    _bisearch,
    _wcmatch_version,
    _wcversion_value,
    _fetch_zero_width_emoji_patterns,
    ZERO_WIDTH,
    WIDE_EASTASIAN,
    EMOJI_ZERO_WIDTH_SEQUENCES)

# The __all__ attribute defines the items exported from statement, 'from wcwidth
# import *', but also to say, "This is the public API".  I don't ever suggest to
# use the "*" character, I just like to codify what part of the API is public.
__all__ = ('width', 'wcwidth', 'wcswidth', 'list_versions')
__version__ = '0.2.5'
