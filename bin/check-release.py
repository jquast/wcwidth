#!/usr/bin/env python3
from __future__ import annotations

# std imports
import os
import re
import sys
import json
import argparse
import subprocess

import typing

PATH_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = 'wheels.yml'
VERSION_FILES = (('wcwidth/__init__.py', r"^__version__ = '([^']+)'"),
                 ('pyproject.toml', r'^version = "([^"]+)"'))
FAILURES: list[str] = []


def ok(message: str) -> None:
    print(f'  ok    {message}')


def fail(message: str) -> None:
    FAILURES.append(message)
    print(f'  FAIL  {message}')


def note(message: str) -> None:
    print(f'        {message}')


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False, cwd=PATH_REPO)


def check_tag() -> typing.Optional[str]:
    proc = run('git', 'describe', '--exact-match', '--tags', 'HEAD')
    if proc.returncode != 0:
        fail('HEAD is not a tag')
        return None
    ok(f'HEAD is tag {proc.stdout.strip()}')
    return proc.stdout.strip()


def check_branch() -> None:
    head = run('git', 'rev-parse', 'HEAD').stdout.strip()
    proc = run('git', 'rev-parse', 'master')
    if proc.returncode != 0:
        fail('no local master branch')
        return
    local = proc.stdout.strip()
    if head == local:
        ok('HEAD is the tip of master')
    else:
        fail(f'HEAD {head[:12]} is not the tip of master {local[:12]}')

    if run('git', 'fetch', '--quiet', 'origin', 'master').returncode != 0:
        fail('git fetch origin master failed')
        return
    proc = run('git', 'rev-parse', 'origin/master')
    if proc.returncode != 0:
        fail('no origin/master to compare against')
    elif local == proc.stdout.strip():
        ok('master matches origin/master')
    else:
        fail(f'master {local[:12]} differs from origin/master {proc.stdout.strip()[:12]}')


def check_clean_tree() -> None:
    proc = run('git', 'status', '--porcelain', '--untracked-files=no')
    dirty = [line for line in proc.stdout.splitlines() if line.strip()]
    if dirty:
        fail(f'{len(dirty)} uncommitted change(s), e.g. {dirty[0].strip()}')
    else:
        ok('working tree is clean')


def package_version() -> typing.Optional[str]:
    found = {}
    for relpath, pattern in VERSION_FILES:
        with open(os.path.join(PATH_REPO, relpath), encoding='utf-8') as fp:
            match = re.search(pattern, fp.read(), re.M)
        if match is None:
            fail(f'no version found in {relpath}')
            return None
        found[relpath] = match.group(1)
    if len(set(found.values())) != 1:
        fail(f'version disagrees between files: {found}')
        return None
    version = found[VERSION_FILES[0][0]]
    ok(f'version {version} agrees in {" and ".join(found)}')
    return version


def check_tag_matches_version(tag: str, version: str) -> None:
    if tag.lstrip('v') == version:
        ok(f'tag {tag} matches version {version}')
    else:
        fail(f'tag {tag} does not match version {version}')


def expected_wheels() -> typing.Optional[list[tuple[str, str]]]:
    expected = []
    for platform in ('linux', 'macos', 'windows'):
        proc = run(sys.executable, '-m', 'cibuildwheel',
                   '--print-build-identifiers', '--platform', platform)
        if proc.returncode != 0:
            fail(f'cannot list {platform} build identifiers; is cibuildwheel installed?')
            return None
        for identifier in proc.stdout.split():
            # cibuildwheel prints '{python tag}-{platform}', e.g. 'cp310-manylinux_x86_64'.
            python_tag, _, plat = identifier.partition('-')
            expected.append((python_tag, plat))
    ok(f'{len(expected)} binary wheels expected by [tool.cibuildwheel]')
    return expected


def collect(dest: str) -> tuple[list[str], list[str]]:
    wheels, sdists = [], []
    for _root, _dirs, files in os.walk(dest):
        wheels += [name for name in files if name.endswith('.whl')]
        sdists += [name for name in files if name.endswith('.tar.gz')]
    return wheels, sdists


def obtain_artifacts(tag: typing.Optional[str], dest: str) -> None:
    wheels, sdists = collect(dest)
    if wheels or sdists:
        note(f'{len(wheels) + len(sdists)} artifacts already in {dest}, delete it to refetch')
        return
    if tag is None:
        note(f'no tag, so nothing fetched into {dest}')
        return

    proc = run('gh', 'run', 'list', '--workflow', WORKFLOW, '--branch', tag,
               '--limit', '1', '--json', 'databaseId,conclusion')
    if proc.returncode != 0:
        fail(f'gh run list failed: {proc.stderr.strip()}')
        return
    runs = json.loads(proc.stdout or '[]')
    if not runs:
        fail(f'no {WORKFLOW} run found for {tag}')
        return

    run_id, conclusion = str(runs[0]['databaseId']), runs[0]['conclusion']
    if conclusion != 'success':
        fail(f'{WORKFLOW} run {run_id} concluded {conclusion!r}')
    else:
        ok(f'{WORKFLOW} run {run_id} succeeded')

    os.makedirs(dest, exist_ok=True)
    proc = run('gh', 'run', 'download', run_id, '--dir', dest)
    if proc.returncode != 0:
        fail(f'gh run download {run_id} failed: {proc.stderr.strip()}')
    else:
        ok(f'artifacts downloaded to {dest}')


def wheel_tags(name: str) -> tuple[str, str]:
    """
    Return the (python tag, platform tag) of a wheel filename.

    The last three fields are the python, ABI and platform tags (PEP 427); the ABI tag is skipped
    because an abi3 wheel carries 'abi3' there, a value no cibuildwheel identifier repeats.

    A free-threaded wheel reads 'cp314-cp314t', and cibuildwheel prints 'cp314t' for it.
    """
    fields = name[:-len('.whl')].split('-')
    python_tag, abi_tag = fields[-3], fields[-2]
    if abi_tag == f'{python_tag}t':
        python_tag = abi_tag
    return python_tag, fields[-1]


def satisfied(identifier: tuple[str, str], have: set[tuple[str, str]]) -> bool:
    python_tag, plat = identifier
    family, _, arch = plat.partition('_')
    for got_python, got_plat in have:
        if got_python == python_tag and (got_plat == plat or
                                         (not plat.startswith('win') and
                                          got_plat.startswith(family) and got_plat.endswith(arch))):
            return True
    return False


def check_artifacts(dest: str, version: str,
                    expected: typing.Optional[list[tuple[str, str]]]) -> None:
    wheels, sdists = collect(dest)
    if not wheels and not sdists:
        fail(f'no artifacts found under {dest}')
        return

    if len(sdists) == 1:
        ok(f'sdist present: {sdists[0]}')
    else:
        fail(f'expected exactly 1 sdist, found {len(sdists)}')

    pure = [name for name in wheels if name.endswith('-py3-none-any.whl')]
    if len(pure) == 1:
        ok(f'universal wheel present: {pure[0]}')
    else:
        fail(f'expected exactly 1 py3-none-any wheel, found {len(pure)}')

    wrong = sorted({name for name in wheels if f'-{version}-' not in name})
    if wrong:
        fail(f'{len(wrong)} artifacts are not version {version}: {wrong[:3]}')
    else:
        ok(f'every artifact is version {version}')

    if expected is None:
        return
    have = {wheel_tags(name) for name in wheels if name not in pure}
    missing = [ident for ident in expected if not satisfied(ident, have)]
    if missing:
        fail(f'{len(missing)} expected wheels missing, e.g. {missing[:4]}')
    else:
        ok(f'all {len(expected)} expected binary wheels present')


def main() -> int:
    parser = argparse.ArgumentParser(description='pre-upload release checks')
    parser.add_argument('--dir', default=os.path.join(PATH_REPO, 'dist'),
                        help='where to download artifacts (default: dist/)')
    args = parser.parse_args()

    tag = check_tag()
    check_branch()
    check_clean_tree()
    version = package_version()
    if tag and version:
        check_tag_matches_version(tag, version)
    expected = expected_wheels()
    obtain_artifacts(tag, args.dir)
    if version:
        check_artifacts(args.dir, version, expected)

    print()
    print(f'{len(FAILURES)} check(s) failed; do not upload' if FAILURES else 'all checks passed')
    return 1 if FAILURES else 0


if __name__ == '__main__':
    sys.exit(main())
