"""Tests for setup.py's optional C extension build command."""

# std imports
import importlib.util
from pathlib import Path
from unittest import mock

# 3rd party
import pytest

# cibuildwheel creates its wheel-test virtualenv with --no-setuptools, and this module tests the
# packaging source rather than the wheel built there, so it is skipped in that lane.
setuptools = pytest.importorskip('setuptools')

_SETUP_PY = Path(__file__).resolve().parent.parent / 'setup.py'
_EXTENSION = setuptools.Extension('wcwidth._wcwidth_c', sources=['wcwidth/_wcwidth_c.c'])


def _load_setup(monkeypatch, release_build=False, no_extension=False):
    """Load setup.py, which reads its environment as it is imported."""
    # clear both: cibuildwheel runs this suite in a container with CIBUILDWHEEL set
    for name, enabled in {'CIBUILDWHEEL': release_build,
                          'WCWIDTH_NO_EXTENSION': no_extension}.items():
        if enabled:
            monkeypatch.setenv(name, '1')
        else:
            monkeypatch.delenv(name, raising=False)
    spec = importlib.util.spec_from_file_location('wcwidth_setup', _SETUP_PY)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(setuptools, 'setup'):
        spec.loader.exec_module(module)
    return module


def _run_build_ext(module, monkeypatch, extensions, implementation='CPython'):
    """Run the command once, with compilation replaced by a failure."""
    distribution = setuptools.Distribution({'name': 'wcwidth', 'ext_modules': extensions})
    command = module.optional_build_ext(distribution)
    command.initialize_options()
    command.finalize_options()

    def boom(self):
        raise module.CompileError('gcc: command not found')

    monkeypatch.setattr(module._build_ext, 'run', boom)
    monkeypatch.setattr(module.platform, 'python_implementation', lambda: implementation)
    warned = []
    monkeypatch.setattr(command, 'warn', warned.append)
    command.run()
    return warned


@pytest.mark.parametrize('release_build', [False, True])
def test_compile_failure(release_build, monkeypatch):
    """A failed compile warns, or raises when CIBUILDWHEEL is set."""
    module = _load_setup(monkeypatch, release_build=release_build)

    if release_build:
        with pytest.raises(module.DistutilsPlatformError, match='CIBUILDWHEEL'):
            _run_build_ext(module, monkeypatch, [_EXTENSION])
    else:
        warned = _run_build_ext(module, monkeypatch, [_EXTENSION])

        assert len(warned) == 1
        assert 'wcwidth._wcwidth_c' in warned[0]


@pytest.mark.parametrize('release_build', [False, True])
def test_no_cpython(release_build, monkeypatch):
    """A non-CPython build warns, or raises when CIBUILDWHEEL is set."""
    module = _load_setup(monkeypatch, release_build=release_build)

    if release_build:
        with pytest.raises(module.DistutilsPlatformError, match='PyPy'):
            _run_build_ext(module, monkeypatch, [_EXTENSION], implementation='PyPy')
    else:
        warned = _run_build_ext(module, monkeypatch, [_EXTENSION], implementation='PyPy')

        assert len(warned) == 1
        assert 'PyPy' in warned[0]


def test_no_extension_declared(monkeypatch):
    """WCWIDTH_NO_EXTENSION declares no extension, so a release build still succeeds."""
    module = _load_setup(monkeypatch, release_build=True, no_extension=True)

    assert module._EXT_MODULES == []
    assert module.WHEEL_OPTIONS == {}

    assert not _run_build_ext(module, monkeypatch, [])
