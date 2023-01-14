#!/usr/bin/env python3
"""
Display new wide unicode point values, by version.

For example::

    "5.0.0": [
        12752,
        12753,
        12754,
        ...

Means that chr(12752) through chr(12754) are new WIDE values
for Unicode version 5.0.0, and were not WIDE values for the
previous version (4.1.0).
"""
# std imports
import sys
import json

# local
from wcwidth import WIDE_EASTASIAN, _bisearch


def main():
    """List new WIDE characters at each unicode version."""
    versions = list(WIDE_EASTASIAN.keys())
    results = {}
    for version in versions:
        prev_idx = versions.index(version) - 1
        if prev_idx == -1:
            continue
        previous_version = versions[prev_idx]
        previous_table = WIDE_EASTASIAN[previous_version]
        for value_pair in WIDE_EASTASIAN[version]:
            for value in range(*value_pair):
                if not _bisearch(value, previous_table):
                    results[version] = results.get(version, []) + [value]
                    if '--debug' in sys.argv:
                        print(f'version {version} has unicode character '
                              f'0x{value:05x} ({chr(value)}) but previous '
                              f'version, {previous_version} does not.',
                              file=sys.stderr)
    print(json.dumps(results, indent=4))


if __name__ == '__main__':
    main()
