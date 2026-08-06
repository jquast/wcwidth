"""
Optional CPython extension for wcwidth.

The extension declaration lives declaratively in ``pyproject.toml`` under
``[tool.setuptools.ext-modules]``.  This file exists only for the parts that
cannot be expressed declaratively: the C standard flag for the current
compiler, and the graceful fallback when the extension cannot be built (no C
compiler, unsupported platform, PyPy, or ``WCWIDTH_PURE_PYTHON=1``) -- the
build continues and the pure-Python implementation is used instead.

The optional-extension-with-pure-fallback pattern is long-established:

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

There is no declarative form in any build backend for "optional extension
that may fail to compile", which is why the imperative bits live here.
"""
from __future__ import annotations

import os
import platform
import sys

from setuptools import setup
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


class optional_build_ext(_build_ext):
    """
    build_ext that tolerates C compilation failure.

    When the extension cannot be compiled or linked, emit a warning and
    continue without it; ``wcwidth/__init__.py`` falls back to the
    pure-Python implementation at import time.
    """

    def finalize_options(self) -> None:
        super().finalize_options()
        for ext in self.extensions:
            ext.extra_compile_args = (ext.extra_compile_args or []) + [_C_STANDARD_FLAG]

    def run(self) -> None:
        if not self.extensions:
            return
        if os.environ.get("WCWIDTH_PURE_PYTHON", "") or platform.python_implementation() != "CPython":
            self.warn(
                "Skipping optional C extension 'wcwidth._wcwidth_c'; "
                "the pure-Python implementation will be used."
            )
            return
        try:
            super().run()
        except (CompileError, LinkError, CCompilerError,
                DistutilsExecError, DistutilsPlatformError, OSError) as exc:
            self.warn(
                "The C extension 'wcwidth._wcwidth_c' could not be built: "
                f"{exc}; the pure-Python implementation will be used instead."
            )


setup(cmdclass={"build_ext": optional_build_ext})
