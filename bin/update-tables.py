#!/usr/bin/env python3
"""
Update the python Unicode tables for wcwidth.

https://github.com/jquast/wcwidth
"""


from __future__ import annotations

import os
import re
import string
import urllib
import datetime
import collections
import unicodedata
from urllib.request import urlopen
from dataclasses import dataclass

from typing import Any, Container, Collection, Mapping, Iterator, Iterable


URL_UNICODE_DERIVED_AGE = 'https://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt'
EXCLUDE_VERSIONS = ['2.0.0', '2.1.2', '3.0.0', '3.1.0', '3.2.0', '4.0.0']
PATH_UP = os.path.relpath(
    os.path.join(
        os.path.dirname(__file__),
        os.path.pardir))
PATH_DOCS = os.path.join(PATH_UP, 'docs')
PATH_DATA = os.path.join(PATH_UP, 'data')
PATH_CODE = os.path.join(PATH_UP, 'wcwidth')
FILE_RST = os.path.join(PATH_DOCS, 'unicode_version.rst')
FILE_PATCH_FROM = "release files:"
FILE_PATCH_TO = "======="


@dataclass(order=True, frozen=True)
class UnicodeVersion:
    major: int
    minor: int
    micro: int

    @classmethod
    def parse(cls, version_str: str) -> UnicodeVersion:
        """parse a version string
        >>> UnicodeVersion.parse("14.0.0")
        UnicodeVersion(major=14, minor=0, micro=0)
        """
        return cls(*map(int, version_str.split(".")[:3]))

    def __str__(self):
        """
        >>> str(UnicodeVersion(12, 1, 0))
        '12.1.0'
        """
        return f'{self.major}.{self.minor}.{self.micro}'


@dataclass(frozen=True)
class TableEntry:
    code_range: range
    properties: tuple[str, ...]
    comment: str


@dataclass
class TableDef:
    version: str  # source file name
    date: str
    values: list[int]


def main() -> None:
    """Update east-asian, combining and zero width tables."""
    versions = get_unicode_versions()
    do_east_asian(versions)
    do_zero_width(versions)
    do_rst_file_update()
    do_unicode_versions(versions)


def get_unicode_versions() -> list[UnicodeVersion]:
    """Fetch, determine, and return Unicode Versions for processing."""
    fname = os.path.join(PATH_DATA, 'DerivedAge.txt')
    do_retrieve(url=URL_UNICODE_DERIVED_AGE, fname=fname)
    pattern = re.compile(r'#.*assigned in Unicode ([0-9.]+)')
    versions: list[UnicodeVersion] = []
    with open(fname, encoding='utf-8') as f:
        for line in f:
            if match := re.match(pattern, line):
                version = match.group(1)
                if version not in EXCLUDE_VERSIONS:
                    versions.append(UnicodeVersion.parse(version))
    versions.sort()
    return versions


def do_rst_file_update():
    """Patch unicode_versions.rst to reflect the data files used in release."""

    # read in,
    with open(FILE_RST, encoding='utf-8') as f:
        data_in = f.read()

    # search for beginning and end positions,
    pos_begin = data_in.find(FILE_PATCH_FROM)
    assert pos_begin != -1, (pos_begin, FILE_PATCH_FROM)
    pos_begin += len(FILE_PATCH_FROM)
    data_out_list = [data_in[:pos_begin], '\n\n']

    # find all filenames with a version number in it,
    # sort filenames by name, then dotted number, ascending
    pattern = re.compile(
        r'^(DerivedGeneralCategory|EastAsianWidth)-(\d+)\.(\d+)\.(\d+)\.txt$')
    filename_matches = []
    for fname in os.listdir(PATH_DATA):
        if match := re.search(pattern, fname):
            filename_matches.append(match)

    filename_matches.sort(key = lambda m: (
        m.group(1),
        int(m.group(2)),
        int(m.group(3)),
        int(m.group(4)),
    ))
    filenames = [match.string for match in filename_matches]

    # copy file description as-is, formatted
    for fpath in filenames:
        if description := describe_file_header(fpath):
            data_out_list.append(f'\n{description}')

    # write.
    print(f"patching {FILE_RST} ..")
    data_out = "".join(data_out_list)
    with open(FILE_RST, 'w', encoding='utf-8') as f:
        f.write(data_out)


def do_east_asian(versions: Collection[UnicodeVersion]):
    """Fetch and update east-asian tables."""
    table: dict[UnicodeVersion, TableDef] = {}
    fout = os.path.join(PATH_CODE, 'table_wide.py')
    for version in versions:
        fin = os.path.join(PATH_DATA, f'EastAsianWidth-{version}.txt')
        url = f'https://www.unicode.org/Public/{version}/ucd/EastAsianWidth.txt'
        try:
            do_retrieve(url=url, fname=fin)
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
        else:
            table[version] = parse_east_asian(
                fname=fin,
                properties=('W', 'F',))
    do_write_table(fname=fout, variable='WIDE_EASTASIAN', table=table)


def do_zero_width(versions: Collection[UnicodeVersion]):
    """Fetch and update zero width tables."""
    table: dict[UnicodeVersion, TableDef] = {}
    fout = os.path.join(PATH_CODE, 'table_zero.py')
    for version in versions:
        fin = os.path.join(PATH_DATA, f'DerivedGeneralCategory-{version}.txt')
        url = (f'https://www.unicode.org/Public/{version}/ucd/extracted/'
                'DerivedGeneralCategory.txt')
        try:
            do_retrieve(url=url, fname=fin)
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
        else:
            table[version] = parse_category(
                fname=fin,
                categories=('Me', 'Mn',))
    do_write_table(fname=fout, variable='ZERO_WIDTH', table=table)


def make_table(values):
    """Return a tuple of lookup tables for given values."""
    table = collections.deque()
    start, end = values[0], values[0]
    for num, value in enumerate(values):
        if num == 0:
            table.append((value, value,))
            continue
        start, end = table.pop()
        if end == value - 1:
            table.append((start, value,))
        else:
            table.append((start, end,))
            table.append((value, value,))
    return tuple(table)


def do_retrieve(url, fname):
    """Retrieve given url to target filepath fname."""
    folder = os.path.dirname(fname)
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"{folder}{os.path.sep} created.")
    if not os.path.exists(fname):
        try:
            with open(fname, 'wb') as fout:
                print(f"retrieving {url}: ", end='', flush=True)
                with urlopen(url) as resp:
                    fout.write(resp.read())
        except BaseException:
            print('failed')
            os.unlink(fname)
            raise
        print(f"{fname} saved.")
    return fname


def describe_file_header(fpath):
    with open(fpath, encoding='utf-8') as f:
        header_2 = [line.lstrip('# ').rstrip() for _, line in zip(range(2), f)]
    # fmt:
    #
    # ``EastAsianWidth-8.0.0.txt``
    #   *Date: 2015-02-10, 21:00:00 GMT [KW, LI]*
    fmt = '``{0}``\n  *{1}*\n'
    if len(header_2) == 0:
        return ''
    assert len(header_2) == 2, (fpath, header_2)
    return fmt.format(*header_2)


def parse_unicode_table(file: Iterable[str]) -> Iterator[TableEntry]:
    """Parse unicode tables.
    See details: https://www.unicode.org/reports/tr44/#Format_Conventions
    """
    for line in file:
        data, _, comment = line.partition('#')
        data_fields: Iterator[str] = (field.strip() for field in data.split(';'))
        code_points_str, *properties = data_fields

        if '..' in code_points_str:
            start, end = code_points_str.split('..')
        else:
            start = end = code_points_str
        code_range = range(int(start, base=16),
                           int(end, base=16) + 1)

        yield TableEntry(code_range, tuple(properties), comment)


def parse_file_select_by_first_property(
    fname: str,
    properties: Container
) -> TableDef:
    print(f'parsing {fname}: ', end='', flush=True)

    with open(fname, encoding='utf-8') as f:
        table_iter = parse_unicode_table(f)
        version = next(table_iter).comment.strip()
        date = next(table_iter).comment.split(':', 1)[1].strip()
        values: list[int] = []

        for entry in table_iter:
            if entry.properties[0] in properties:
                values.extend(entry.code_range)

    values.sort()
    print('ok')
    return TableDef(version, date, values)


def parse_east_asian(fname: str, properties: Container) -> TableDef:
    """Parse unicode east-asian width tables."""
    return parse_file_select_by_first_property(fname, properties)


def parse_category(fname: str, categories: Container) -> TableDef:
    """Parse unicode category tables."""
    return parse_file_select_by_first_property(fname, categories)


def do_write_table(
    fname: str,
    variable: str,
    table: Mapping[UnicodeVersion, TableDef]
) -> None:
    """Write combining tables to filesystem as python code."""
    # pylint: disable=R0914
    #         Too many local variables (19/15) (col 4)
    utc_now = datetime.datetime.utcnow()
    indent = ' ' * 8
    with open(fname, 'w', encoding='utf-8') as fout:
        print(f"writing {fname} ... ", end='')
        fout.write(
            f'"""{variable.title()} table, created by bin/update-tables.py."""\n'
            f"# Generated: {utc_now.isoformat()}\n"
            f"{variable} = {{\n")

        for version_key, version_table in table.items():
            if not version_table.values:
                continue
            fout.write(
                f"{indent[:-4]}'{version_key}': (\n"
                f"{indent}# Source: {version_table.version}\n"
                f"{indent}# Date: {version_table.date}\n"
                f"{indent}#")

            for start, end in make_table(version_table.values):
                ucs_start, ucs_end = chr(start), chr(end)
                hex_start, hex_end = (f'0x{start:05x}', f'0x{end:05x}')
                try:
                    name_start = string.capwords(unicodedata.name(ucs_start))
                except ValueError:
                    name_start = '(nil)'
                try:
                    name_end = string.capwords(unicodedata.name(ucs_end))
                except ValueError:
                    name_end = '(nil)'
                fout.write(f'\n{indent}')
                comment_startpart = name_start[:24].rstrip()
                comment_endpart = name_end[:24].rstrip()
                fout.write(f'({hex_start}, {hex_end},),')
                fout.write(f'  # {comment_startpart:24s}..{comment_endpart}')
            fout.write(f'\n{indent[:-4]}),\n')
        fout.write('}\n')
    print("complete.")


def do_unicode_versions(versions: Collection[UnicodeVersion]):
    """Write unicode_versions.py function list_versions()."""
    fname = os.path.join(PATH_CODE, 'unicode_versions.py')
    print(f"writing {fname} ... ", end='')

    utc_now = datetime.datetime.utcnow()
    version_tuples_str = '\n        '.join(
        f'"{ver}",' for ver in versions)

    with open(fname, 'w', encoding='utf-8') as fp:
        fp.write(f"""\"\"\"
Exports function list_versions() for unicode version level support.

This code generated by {__file__} on {utc_now}.
\"\"\"


def list_versions():
    \"\"\"
    Return Unicode version levels supported by this module release.

    Any of the version strings returned may be used as keyword argument
    ``unicode_version`` to the ``wcwidth()`` family of functions.

    :returns: Supported Unicode version numbers in ascending sorted order.
    :rtype: list[str]
    \"\"\"
    return (
        {version_tuples_str}
    )
""")
        print('done.')


if __name__ == '__main__':
    main()
