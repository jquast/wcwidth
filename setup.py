"""
Optional CPython extension for wcwidth.

The extension is declared here with the classic ``ext_modules`` API (rather
than declaratively in ``pyproject.toml``) because the declarative form
``[[tool.setuptools.ext-modules]]`` requires setuptools >= 77, and setuptools
dropped Python 3.8 support in 77 -- this package supports 3.8 and newer.  The
classic API works on every setuptools version that reads ``pyproject.toml``.

This file also holds the parts that cannot be expressed declaratively at all:
the C standard flag for the current compiler, and the graceful fallback when
the extension cannot be built (no C compiler, unsupported platform, PyPy, or
``WCWIDTH_PYTHON=1``) -- the build continues and the Python
implementation is used instead.

The optional-extension-with-Python-fallback pattern is long-established:

- distutils' ``build_ext`` has built-in support: extensions marked
  ``optional=True`` have compile failures caught and reported as warnings
  (``distutils.command.build_ext``), so a failed compile never fails the
  install.  ``websockets`` builds its optional C ``speedups`` extension this
  way (https://github.com/python-websockets/websockets).
- ``MarkupSafe`` (Pallets) overrides ``build_ext`` to catch compile errors
  and continue without the extension
  (https://github.com/pallets/markupsafe/blob/main/setup.py).
- ``PyYAML`` builds its optional ``_yaml`` (libyaml) extension the same way,
  warning "Error compiling module, falling back to pure Python"
  (https://github.com/yaml/pyyaml/blob/main/setup.py).
"""
from __future__ import annotations

import os
import platform
import sys

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext as _build_ext
from setuptools.errors import CCompilerError, CompileError, LinkError
from distutils.errors import (  # pylint: disable=deprecated-module
    DistutilsExecError,
    DistutilsPlatformError,
)

# C11 features (designated initializers, stdbool) require an explicit standard
# flag on both MSVC and POSIX compilers.
if sys.platform == "win32":
    _C_STANDARD_FLAG = "/std:c11"
else:
    _C_STANDARD_FLAG = "-std=c11"

# Keep this source list in parity with libwcwidth/CMakeLists.txt's
# LIBWCWIDTH_SOURCES; the Makefile globs src/*.c itself.
_EXT_SOURCES = [
    "wcwidth/_wcwidth_c.c",
    "libwcwidth/src/bisearch.c",
    "libwcwidth/src/wcwidth.c",
    "libwcwidth/src/wcswidth.c",
    "libwcwidth/src/wcstwidth.c",
    "libwcwidth/src/width.c",
    "libwcwidth/src/textwrap.c",
    "libwcwidth/src/clip.c",
    "libwcwidth/src/align.c",
    "libwcwidth/src/grapheme.c",
    "libwcwidth/src/escape.c",
    "libwcwidth/src/sgr.c",
    "libwcwidth/src/hyperlink.c",
    "libwcwidth/src/text_sizing.c",
    "libwcwidth/src/terminal_override.c",
    "libwcwidth/src/utf8.c",
    "libwcwidth/src/tables/table_wide.c",
    "libwcwidth/src/tables/table_zero.c",
    "libwcwidth/src/tables/table_ambiguous.c",
    "libwcwidth/src/tables/table_grapheme.c",
    "libwcwidth/src/tables/table_mc.c",
    "libwcwidth/src/tables/table_vs15.c",
    "libwcwidth/src/tables/table_vs16.c",
    "libwcwidth/src/tables/table_terminal_overrides.c",
    "libwcwidth/src/tables/table_term_programs.c",
]

_EXT_MODULES = [
    Extension(
        "wcwidth._wcwidth_c",
        sources=_EXT_SOURCES,
        include_dirs=["libwcwidth/include"],
    ),
]


class optional_build_ext(_build_ext):
    """
    build_ext that tolerates C compilation failure.

    When the extension cannot be compiled or linked, emit a warning and
    continue without it; ``wcwidth/__init__.py`` falls back to the
    Python implementation at import time.
    """

    def finalize_options(self) -> None:
        super().finalize_options()
        for ext in self.extensions:
            ext.extra_compile_args = (ext.extra_compile_args or []) + [_C_STANDARD_FLAG]

    def run(self) -> None:
        if not self.extensions:
            return
        if os.environ.get("WCWIDTH_PYTHON", "") or platform.python_implementation() != "CPython":
            self.warn(
                "Skipping optional C extension 'wcwidth._wcwidth_c'; "
                "the Python implementation will be used."
            )
            return
        try:
            super().run()
        except (CompileError, LinkError, CCompilerError,
                DistutilsExecError, DistutilsPlatformError, OSError) as exc:
            self.warn(
                "The C extension 'wcwidth._wcwidth_c' could not be built: "
                f"{exc}; the Python implementation will be used instead."
            )


setup(
    cmdclass={"build_ext": optional_build_ext},
    ext_modules=_EXT_MODULES,
)
