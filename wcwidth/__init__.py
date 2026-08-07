"""
Python 'wcwidth' module.

https://github.com/jquast/wcwidth
"""

__lazy_modules__ = [
    "wcwidth._clip",
    "wcwidth._wcswidth",
    "wcwidth._wcwidth",
    "wcwidth._width",
    "wcwidth.align",
    "wcwidth.bisearch",
    "wcwidth.escape_sequences",
    "wcwidth.grapheme",
    "wcwidth.hyperlink",
    "wcwidth.sgr_state",
    "wcwidth.table_ambiguous",
    "wcwidth.table_vs16",
    "wcwidth.table_wide",
    "wcwidth.table_zero",
    "wcwidth.text_sizing",
    "wcwidth.textwrap",
    "wcwidth.unicode_versions",
]

# std imports
import os
from functools import lru_cache

# local
# re-export common and outermost functions & definitions, even a few private
# ones, some for convenience, others for legacy, only the items in __all__ are
# documented as public API
from .bisearch import bisearch as _bisearch
from .grapheme import iter_graphemes, iter_graphemes_reverse, grapheme_boundary_before
from .textwrap import SequenceTextWrapper
from .hyperlink import Hyperlink, HyperlinkParams
from ._constants import list_term_programs
from .table_vs16 import VS16_NARROW_TO_WIDE
from .table_wide import WIDE_EASTASIAN
from .table_zero import ZERO_WIDTH
from .text_sizing import TextSizing, TextSizingParams
from .table_ambiguous import AMBIGUOUS_EASTASIAN
from .escape_sequences import iter_sequences
from .unicode_versions import list_versions
from ._clip import clip
from .textwrap import wrap

# Import optional C extension 'wcwidth._wcwidth_c', a wrapper around the
# portable C11 libwcwidth library.  When it is unavailable (compilation
# failure, unsupported platform, or WCWIDTH_PURE_PYTHON=1), the pure-Python
# implementation below is used as a drop-in replacement.
HAS_C_EXTENSION = False
if not os.environ.get('WCWIDTH_PURE_PYTHON', ''):
    try:
        # local
        # import ... as _wcwidth_c: binds only the submodule name, so mypy
        # does not see 'wcwidth' redefined by the later function imports.
        # The import statement (unlike 'from . import _wcwidth_c') always
        # consults sys.modules, so a poisoned/broken submodule raises here
        # even on reload -- see test_import_error_fallback.
        import wcwidth._wcwidth_c as _wcwidth_c  # noqa: F401  pylint:disable=unused-import
    except ImportError:  # pragma: no cover - exercised by test_c_extension.py
        pass
    else:
        HAS_C_EXTENSION = True

if HAS_C_EXTENSION:
    from ._wcwidth_c import (ljust,
                             rjust,
                             width,
                             center,
                             wcwidth as _c_wcwidth,
                             wcswidth,
                             wcstwidth,
                             propagate_sgr,
                             strip_sequences)
    wcwidth = lru_cache(maxsize=1024)(_c_wcwidth)
else:
    from .align import ljust, rjust, center
    from ._width import width
    from ._wcswidth import wcswidth, wcstwidth
    from ._wcwidth import wcwidth
    from .escape_sequences import strip_sequences
    from .sgr_state import propagate_sgr

# NOTE: this sort order is important for legacy import API compatibility before release 0.7.0
#
# On Python < 3.15 the legacy submodule is eagerly pre-imported for backward compatibility
# (populates sys.modules['wcwidth.wcwidth']).  On 3.15+ __lazy_modules__ handles all submodules; the
# legacy shim loads on-demand via file discovery when ``from wcwidth.wcwidth import ...`` is used.
if __import__('sys').version_info < (3, 15):
    # Pre-import the legacy submodule so that sys.modules['wcwidth.wcwidth'] is populated during
    # package initialization.  Without this, a later downstream dependent ``import wcwidth.wcwidth``
    # triggers on-disk file discovery which rebinds wcwidth.wcwidth from the function to the module
    # object.
    #
    # this is just a lot of carefulness for the original release that contained all functions in a
    # single 'wcwidth.py' file. Even though we always exposed our API at the top-level the preferred
    # 'from wcwidth import wcswidth', it was always possible to import them more directly,
    # 'from wcwidth.wcwidth import wcswidth'
    # -- and we make a lot of effort to allow any such import statements to continue to function.
    from . import wcwidth as _wcwidth_module  # isort:skip

from ._wcwidth import _wcmatch_version, _wcversion_value  # isort:skip  # pylint: disable=wrong-import-position


# The __all__ attribute defines the items exported from statement,
# 'from wcwidth import *', but also to say, "This is the public API".
__all__ = ('wcwidth', 'wcswidth', 'wcstwidth', 'width', 'iter_sequences', 'iter_graphemes',
           'iter_graphemes_reverse', 'grapheme_boundary_before',
           'ljust', 'rjust', 'center', 'wrap', 'clip', 'strip_sequences',
           'list_versions', 'list_term_programs', 'propagate_sgr',
           'Hyperlink', 'HyperlinkParams', 'TextSizing', 'TextSizingParams')

# Version is stamped by code generation (bin/update-tables.py) from pyproject.toml.
__version__ = '0.9.0'
