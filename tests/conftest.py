"""Pytest configuration and fixtures."""

# std imports
import os

# 3rd party
import pytest

# local
from wcwidth._constants import resolve_terminal


@pytest.fixture(autouse=True)
def _verify_extension_mode():
    """Assert the loaded implementation matches the WCWIDTH_PURE_PYTHON env var.

    In extension mode the C extension must be active; in pure-Python mode it
    must not be, so a silently-failed C build is caught in CI.
    """
    import wcwidth

    if os.environ.get('WCWIDTH_PURE_PYTHON', ''):
        assert not wcwidth.HAS_C_EXTENSION, "C extension loaded in pure-Python mode"
    else:
        assert wcwidth.HAS_C_EXTENSION, "C extension not loaded in extension mode"


@pytest.fixture(autouse=True)
def _clear_resolve_terminal_cache():
    """Clear resolve_terminal cache and unset TERM/TERM_PROGRAM before each test."""
    saved_term = os.environ.pop('TERM', None)
    saved_tprog = os.environ.pop('TERM_PROGRAM', None)
    resolve_terminal.cache_clear()
    yield
    resolve_terminal.cache_clear()
    if saved_term is not None:
        os.environ['TERM'] = saved_term
    if saved_tprog is not None:
        os.environ['TERM_PROGRAM'] = saved_tprog


try:
    # 3rd party
    from pytest_codspeed import BenchmarkFixture  # noqa: F401  pylint:disable=unused-import
except ImportError:
    # Provide a no-op benchmark fixture when pytest-codspeed is not installed
    @pytest.fixture
    def benchmark():
        """No-op benchmark fixture for environments without pytest-codspeed."""

        def _passthrough(func, *args, **kwargs):
            return func(*args, **kwargs)
        return _passthrough
