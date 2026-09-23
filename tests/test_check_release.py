"""Tests for bin/check-release.py, the pre-upload release gate."""

# std imports
import importlib.util
from pathlib import Path

# 3rd party
import pytest

# not importable as a module: the filename holds a hyphen
_SPEC = importlib.util.spec_from_file_location(
    'check_release', Path(__file__).resolve().parent.parent / 'bin' / 'check-release.py')
check_release = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_release)


def _dist_with(tmp_path, wheel):
    """Return a dist directory holding an sdist, the pure wheel, and *wheel*."""
    dist = tmp_path / 'dist'
    dist.mkdir()
    for name in ('wcwidth-0.9.0.tar.gz', 'wcwidth-0.9.0-py3-none-any.whl', wheel):
        (dist / name).touch()
    return dist


@pytest.mark.parametrize('name,expected', [
    ('wcwidth-0.9.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl',
     ('cp310', 'manylinux_2_17_x86_64.manylinux2014_x86_64')),
    ('wcwidth-0.9.0-cp314t-cp314t-win_amd64.whl', ('cp314t', 'win_amd64')),
    # a PEP 427 build tag sits between the version and the python tag
    ('wcwidth-0.9.0-1-cp310-abi3-win32.whl', ('cp310', 'win32')),
])
def test_wheel_tags(name, expected):
    """The python tag is read from the third-from-last field."""
    assert check_release.wheel_tags(name) == expected


@pytest.mark.parametrize('identifier,wheel', [
    # identifier shapes cibuildwheel prints for [tool.cibuildwheel] build = "cp310-* cp314t-*"
    (('cp310', 'manylinux_x86_64'),
     'wcwidth-0.9.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'),
    (('cp310', 'macosx_arm64'), 'wcwidth-0.9.0-cp310-abi3-macosx_11_0_arm64.whl'),
    (('cp310', 'win_amd64'), 'wcwidth-0.9.0-cp310-abi3-win_amd64.whl'),
    (('cp314t', 'manylinux_x86_64'),
     'wcwidth-0.9.0-cp314t-cp314t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'),
])
def test_check_artifacts_accepts_abi3_wheels(identifier, wheel, tmp_path):
    """An abi3 wheel satisfies its cibuildwheel identifier."""
    dist = _dist_with(tmp_path, wheel)

    check_release.FAILURES.clear()
    check_release.check_artifacts(str(dist), '0.9.0', [identifier])

    assert not check_release.FAILURES


def test_check_artifacts_reports_wrong_python_tag(tmp_path):
    """A cp311 wheel is reported missing for a cp310 identifier."""
    dist = _dist_with(tmp_path, 'wcwidth-0.9.0-cp311-cp311-manylinux_2_17_x86_64.whl')

    check_release.FAILURES.clear()
    check_release.check_artifacts(str(dist), '0.9.0', [('cp310', 'manylinux_x86_64')])

    assert any('expected wheels missing' in message for message in check_release.FAILURES)
