"""
Optional CPython extension for wcwidth.

Holds what pyproject.toml cannot express: the C standard flag, and continuing
the build when the extension will not compile (no compiler, or PyPy) so that
the Python implementation is used instead.  WCWIDTH_NO_EXTENSION=1 skips it
outright, which is how the py3-none-any wheel is built.
"""
from __future__ import annotations

import os
import platform
import re
import sys
import sysconfig

import setuptools
from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext as _build_ext

try:
    from setuptools.errors import CCompilerError, CompileError, LinkError
except ImportError:  # setuptools < 59 keeps these in distutils
    from distutils.errors import (  # pylint: disable=deprecated-module
        CCompilerError,
        CompileError,
        LinkError,
    )
from distutils.errors import (  # pylint: disable=deprecated-module
    DistutilsExecError,
    DistutilsPlatformError,
)

_PEP621_SETUPTOOLS = (61, 0)
_setuptools_version = tuple(int(part) for part in
                            re.findall(r'\d+', setuptools.__version__)[:2])


def _version_from_source() -> str:
    """Read __version__ out of wcwidth/__init__.py without importing it."""
    init = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wcwidth', '__init__.py')
    with open(init, encoding='utf-8') as fp:
        match = re.search(r"^__version__ = '([^']+)'", fp.read(), re.M)
    if match is None:
        raise SystemExit('cannot determine version from wcwidth/__init__.py')
    return match.group(1)


# Below 61, setuptools ignores [project] and would build UNKNOWN 0.0.0; pip
# applies the requires floor only when it builds in isolation.  Supply just
# enough to name the package -- the rest of the metadata is lost, which beats
# not building.
if _setuptools_version < _PEP621_SETUPTOOLS:
    _FALLBACK_METADATA = {
        'name': 'wcwidth',
        'version': _version_from_source(),
        'packages': find_packages(include=['wcwidth', 'wcwidth.*']),
        'package_data': {'wcwidth': ['py.typed', '*.pyi']},
        'python_requires': '>=3.9',
    }
else:
    _FALLBACK_METADATA = {}

# C11 needs an explicit standard flag on both MSVC and POSIX compilers.
if sys.platform == "win32":
    _C_STANDARD_FLAG = "/std:c11"
else:
    _C_STANDARD_FLAG = "-std=c11"

# Keep in parity with LIBWCWIDTH_SOURCES in libwcwidth/CMakeLists.txt.
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
    "libwcwidth/src/tables/table_gcb_class.c",
]

# Stable ABI (abi3): one cp310 wheel covers every GIL-enabled interpreter from
# 3.10 up.  A 3.9 interpreter installs the pure Python py3-none-any wheel.
PY_LIMITED_API = "0x030A0000"
ABI3_TAG = "cp310"

# Only a 3.10 or newer build can compile against that API.  A free-threaded
# build cannot use the stable ABI at all: Py_LIMITED_API below 3.13 drops the
# Py_mod_gil declaration it requires.
USE_LIMITED_API = (not sysconfig.get_config_var("Py_GIL_DISABLED")
                   and sys.version_info >= (3, 10))

# Build-time only, and distinct from the WCWIDTH_PYTHON runtime selector: that
# one is read at import and works whether or not the extension exists, so it has
# no business here.  Declaring no extension, rather than one that is skipped
# later, is what makes bdist_wheel tag the result py3-none-any -- setuptools
# decides purity from ext_modules, not from whether anything was built.
if os.environ.get("WCWIDTH_NO_EXTENSION", ""):
    _EXT_MODULES: list[Extension] = []
else:
    _EXT_MODULES = [
        Extension(
            "wcwidth._wcwidth_c",
            sources=_EXT_SOURCES,
            include_dirs=["libwcwidth/include"],
            define_macros=[("Py_LIMITED_API", PY_LIMITED_API)] if USE_LIMITED_API else [],
            py_limited_api=USE_LIMITED_API,
        ),
    ]

# Claim the abi3 tag only when an extension is built; the WCWIDTH_NO_EXTENSION
# wheel stays py3-none-any and a 3.9 build stays version specific.
WHEEL_OPTIONS = ({"bdist_wheel": {"py_limited_api": ABI3_TAG}}
                 if _EXT_MODULES and USE_LIMITED_API else {})


class optional_build_ext(_build_ext):
    """build_ext that warns and continues when the C extension will not build."""

    def finalize_options(self) -> None:
        super().finalize_options()
        for ext in self.extensions:
            ext.extra_compile_args = (ext.extra_compile_args or []) + [_C_STANDARD_FLAG]

    def run(self) -> None:
        if not self.extensions:
            return
        if platform.python_implementation() != "CPython":
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
    options=WHEEL_OPTIONS,
    **_FALLBACK_METADATA,
)
