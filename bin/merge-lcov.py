#!/usr/bin/env python
"""
Merge duplicate LCOV branch records and normalize source paths.

The C test suite and the Python extension build the same sources twice,
gcovr emits separate branch records for each, this merges them.
"""
from __future__ import annotations

# std imports
import re
import argparse

_SF_PATTERN = re.compile(r'(?m)^SF:.*?(?=libwcwidth/)')


def merge(path: str) -> None:
    with open(path, encoding='utf-8') as lcov:
        lines = _SF_PATTERN.sub('SF:', lcov.read()).splitlines()

    merged: list[str] = []
    seen: dict[tuple[str | None, str, str], int] = {}
    source = None

    for line in lines:
        if line.startswith('SF:'):
            source = line[3:].strip()
        elif line.startswith('BRDA:'):
            line_number, _, branch, taken = line[5:].split(',')
            key = (source, line_number, branch)
            count = -1 if taken == '-' else int(taken)
            if key in seen:
                index = seen[key]
                previous = merged[index].rsplit(',', 1)[1]
                if previous == '-' or count > int(previous):
                    merged[index] = f'BRDA:{line_number},0,{branch},{taken if count >= 0 else "-"}'
                continue
            seen[key] = len(merged)
            merged.append(f'BRDA:{line_number},0,{branch},{taken}')
            continue
        merged.append(line)

    with open(path, 'w', encoding='utf-8') as lcov:
        lcov.write('\n'.join(merged) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lcov', help='LCOV tracefile to rewrite in place')
    merge(parser.parse_args().lcov)


if __name__ == '__main__':
    main()
