"""Pytest configuration and fixtures."""
import pytest


try:
    from pytest_codspeed import BenchmarkFixture  # noqa: F401
except ImportError:
    # Provide a no-op benchmark fixture when pytest-codspeed is not installed
    @pytest.fixture
    def benchmark():
        """No-op benchmark fixture for environments without pytest-codspeed."""
        def _passthrough(func, *args, **kwargs):
            return func(*args, **kwargs)
        return _passthrough
