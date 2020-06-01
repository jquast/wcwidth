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
for Unicode vesion 5.0.0, and were not WIDE values for the
previous version (4.1.0).
"""
import json

# List new WIDE characters at each unicode version.
#
def main():
    from wcwidth import WIDE_EASTASIAN, _bisearch
    next_version_values, next_version = [], ''
    results = {}
    for version, table in reversed(WIDE_EASTASIAN.items()):
        for value_pair in next_version_values:
            for value in range(*value_pair):
                if not _bisearch(value, table):
                    results[version] = results.get(version, []) + [value]
        next_version_values = table
        next_version = version
    print(json.dumps(results, indent=4))


if __name__ == '__main__':
    main()
