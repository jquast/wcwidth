#!/usr/bin/env python3
# std imports
import os
import sys
import json

json_version = os.path.join(
    os.path.dirname(__file__), os.path.pardir, 'wcwidth', 'version.json')


def main(bump_arg):
    assert bump_arg in ('--minor', '--major', '--release'), bump_arg

    with open(json_version, 'r') as fin:
        data = json.load(fin)

    release, major, minor = map(int, data['package'].split('.'))
    release = release + 1 if bump_arg == '--release' else release
    major = major + 1 if bump_arg == '--major' else major
    minor = minor + 1 if bump_arg == '--minor' else minor
    new_version = '.'.join(map(str, [release, major, minor]))
    data['package'] = new_version

    with open(json_version, 'w') as fout:
        json.dump(data, fout)


if __name__ == '__main__':
    main(sys.argv[1])
