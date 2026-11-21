"""Tests for bin/check-release.py, the pre-upload release gate."""

# std imports
import json
import subprocess
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
    ('wcwidth-0.9.0-cp314-cp314t-win_amd64.whl', ('cp314t', 'win_amd64')),
    # a PEP 427 build tag sits between the version and the python tag
    ('wcwidth-0.9.0-1-cp310-abi3-win32.whl', ('cp310', 'win32')),
])
def test_wheel_tags(name, expected):
    """The python tag is the third-from-last field, or the ABI tag when free-threaded."""
    assert check_release.wheel_tags(name) == expected


@pytest.mark.parametrize('identifier,wheel', [
    # identifier shapes cibuildwheel prints for [tool.cibuildwheel] build = "cp310-* cp314t-* cp315t-*"
    (('cp310', 'manylinux_x86_64'),
     'wcwidth-0.9.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'),
    (('cp310', 'macosx_arm64'), 'wcwidth-0.9.0-cp310-abi3-macosx_11_0_arm64.whl'),
    (('cp310', 'win_amd64'), 'wcwidth-0.9.0-cp310-abi3-win_amd64.whl'),
    (('cp314t', 'manylinux_x86_64'),
     'wcwidth-0.9.0-cp314-cp314t-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'),
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


class _Clock:
    """Fake time module for wait_for_run."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[int] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: int) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _gh_list(payload: list[dict[str, object]], returncode: int = 0
             ) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=json.dumps(payload), stderr='')


def _fake_run(responses):
    """Return a run() fake that answers git with a sha and gh with *responses*."""
    def fake_run(*args):
        if args[:2] == ('git', 'rev-parse'):
            return subprocess.CompletedProcess(args, 0, stdout='deadbeef\n', stderr='')
        return _gh_list(responses.pop(0))
    return fake_run


def test_wait_for_run_retries_until_run_appears(monkeypatch):
    """A tag-push run GitHub has not registered yet is polled, not failed."""
    responses = [[], [{'databaseId': 7, 'conclusion': 'success', 'status': 'completed'}]]
    monkeypatch.setattr(check_release, 'run', _fake_run(responses))
    clock = _Clock()
    monkeypatch.setattr(check_release, 'time', clock)
    check_release.FAILURES.clear()

    assert check_release.wait_for_run('0.9.0') == '7'
    assert clock.sleeps == [check_release.POLL_INTERVAL]
    assert not check_release.FAILURES


def test_wait_for_run_waits_for_in_progress(monkeypatch):
    """An unfinished run is polled until it succeeds."""
    responses = [
        [{'databaseId': 7, 'conclusion': None, 'status': 'in_progress'}],
        [{'databaseId': 7, 'conclusion': 'success', 'status': 'completed'}],
    ]
    monkeypatch.setattr(check_release, 'run', _fake_run(responses))
    clock = _Clock()
    monkeypatch.setattr(check_release, 'time', clock)
    check_release.FAILURES.clear()

    assert check_release.wait_for_run('0.9.0') == '7'
    assert clock.sleeps == [check_release.POLL_INTERVAL]
    assert not check_release.FAILURES


def test_wait_for_run_fails_fast_on_completed_failure(monkeypatch):
    """A completed run with a failure conclusion is not polled to the timeout."""
    responses = [[{'databaseId': 7, 'conclusion': 'failure', 'status': 'completed'}]]
    monkeypatch.setattr(check_release, 'run', _fake_run(responses))
    clock = _Clock()
    monkeypatch.setattr(check_release, 'time', clock)
    check_release.FAILURES.clear()

    assert check_release.wait_for_run('0.9.0') is None
    assert not clock.sleeps
    assert any("concluded 'failure'" in message for message in check_release.FAILURES)


def test_wait_for_run_times_out(monkeypatch):
    """A run still queued at the deadline is a failure."""
    monkeypatch.setattr(check_release, 'POLL_TIMEOUT', 60)
    responses = [[{'databaseId': 7, 'conclusion': None, 'status': 'queued'}]] * 3
    monkeypatch.setattr(check_release, 'run', _fake_run(responses))
    clock = _Clock()
    monkeypatch.setattr(check_release, 'time', clock)
    check_release.FAILURES.clear()

    assert check_release.wait_for_run('0.9.0') is None
    assert clock.sleeps == [check_release.POLL_INTERVAL] * 2
    assert any('did not succeed' in message for message in check_release.FAILURES)
