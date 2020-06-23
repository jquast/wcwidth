#!/usr/bin/env python
"""
Update the python Unicode tables for wcwidth.

https://github.com/jquast/wcwidth
"""
from __future__ import print_function

# std imports
import os
import re
import glob
import json
import codecs
import string
import urllib
import datetime
import collections
import unicodedata

try:
    # py2
    from urllib2 import urlopen
except ImportError:
    # py3
    from urllib.request import urlopen

URL_UNICODE_DERIVED_AGE = 'http://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt'
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


# use chr() for py3.x,
# unichr() for py2.x
try:
    _ = unichr(0)
except NameError as err:
    if err.args[0] == "name 'unichr' is not defined":
        # pylint: disable=C0103,W0622
        #         Invalid constant name "unichr" (col 8)
        #         Redefining built-in 'unichr' (col 8)
        unichr = chr
    else:
        raise


TableDef = collections.namedtuple('table', ['version', 'date', 'values'])


def main():
    """Update east-asian, combining and zero width tables."""
    versions = get_unicode_versions()
    do_east_asian(versions)
    do_zero_width(versions)
    do_rst_file_update()
    do_unicode_versions(versions)


def get_unicode_versions():
    """Fetch, determine, and return Unicode Versions for processing."""
    fname = os.path.join(PATH_DATA, 'DerivedAge.txt')
    do_retrieve(url=URL_UNICODE_DERIVED_AGE, fname=fname)
    pattern = re.compile(r'#.*assigned in Unicode ([0-9.]+)')
    versions = []
    for line in open(fname, 'r'):
        if match := re.match(pattern, line):
            version = match.group(1)
            if version not in EXCLUDE_VERSIONS:
                versions.append(version)
    versions.sort(key=lambda ver: list(map(int, ver.split('.'))))
    return versions


def do_rst_file_update():
    """Patch unicode_versions.rst to reflect the data files used in release."""

    # read in,
    data_in = codecs.open(FILE_RST, 'r', 'utf8').read()

    # search for beginning and end positions,
    pos_begin = data_in.find(FILE_PATCH_FROM)
    assert pos_begin != -1, (pos_begin, FILE_PATCH_FROM)
    pos_begin += len(FILE_PATCH_FROM)
    data_out = data_in[:pos_begin] + '\n\n'

    # find all filenames with a version number in it,
    # sort filenames by name, then dotted number, ascending
    glob_pattern = os.path.join(PATH_DATA, '*[0-9]*.txt')
    filenames = glob.glob(glob_pattern)
    filenames.sort(key=lambda ver: [ver.split(
        '-')[0]] + list(map(int, ver.split('-')[-1][:-4].split('.'))))

    # copy file description as-is, formatted
    for fpath in filenames:
        if description := describe_file_header(fpath):
            data_out += f'\n{description}'

    # write.
    print(f"patching {FILE_RST} ..")
    codecs.open(
        FILE_RST, 'w', 'utf8').write(data_out)


def do_east_asian(versions):
    """Fetch and update east-asian tables."""
    table = {}
    for version in versions:
        fin = os.path.join(PATH_DATA, 'EastAsianWidth-{version}.txt')
        fout = os.path.join(PATH_CODE, 'table_wide.py')
        url = ('http://www.unicode.org/Public/{version}/'
               'ucd/EastAsianWidth.txt')
        try:
            do_retrieve(url=url.format(version=version),
                        fname=fin.format(version=version))
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
        else:
            table[version] = parse_east_asian(
                fname=fin.format(version=version),
                properties=(u'W', u'F',))
    do_write_table(fname=fout, variable='WIDE_EASTASIAN', table=table)


def do_zero_width(versions):
    """Fetch and update zero width tables."""
    table = {}
    fout = os.path.join(PATH_CODE, 'table_zero.py')
    for version in versions:
        fin = os.path.join(PATH_DATA, 'DerivedGeneralCategory-{version}.txt')
        url = ('http://www.unicode.org/Public/{version}/ucd/extracted/'
               'DerivedGeneralCategory.txt')
        try:
            do_retrieve(url=url.format(version=version),
                        fname=fin.format(version=version))
        except urllib.error.HTTPError as err:
            if err.code != 404:
                raise
        else:
            table[version] = parse_category(
                fname=fin.format(version=version),
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
                resp = urlopen(url)
                fout.write(resp.read())
        except BaseException:
            print('failed')
            os.unlink(fname)
            raise
        print(f"{fname} saved.")
    return fname


def describe_file_header(fpath):
    header_2 = [line.lstrip('# ').rstrip() for line in
                codecs.open(fpath, 'r', 'utf8').readlines()[:2]]
    # fmt:
    #
    # ``EastAsianWidth-8.0.0.txt``
    #   *2015-02-10, 21:00:00 GMT [KW, LI]*
    fmt = '``{0}``\n  *{1}*\n'
    if len(header_2) == 0:
        return ''
    assert len(header_2) == 2, (fpath, header_2)
    return fmt.format(*header_2)


def parse_east_asian(fname, properties=(u'W', u'F',)):
    """Parse unicode east-asian width tables."""
    print(f'parsing {fname}: ', end='', flush=True)
    version, date, values = None, None, []
    for line in open(fname, 'rb'):
        uline = line.decode('utf-8')
        if version is None:
            version = uline.split(None, 1)[1].rstrip()
            continue
        if date is None:
            date = uline.split(':', 1)[1].rstrip()
            continue
        if uline.startswith('#') or not uline.lstrip():
            continue
        addrs, details = uline.split(';', 1)
        if any(details.startswith(property)
               for property in properties):
            start, stop = addrs, addrs
            if '..' in addrs:
                start, stop = addrs.split('..')
            values.extend(range(int(start, 16), int(stop, 16) + 1))
    print('ok')
    return TableDef(version, date, values)


def parse_category(fname, categories):
    """Parse unicode category tables."""
    print(f'parsing {fname}: ', end='', flush=True)
    version, date, values = None, None, []
    for line in open(fname, 'rb'):
        uline = line.decode('utf-8')
        if version is None:
            version = uline.split(None, 1)[1].rstrip()
            continue
        if date is None:
            date = uline.split(':', 1)[1].rstrip()
            continue
        if uline.startswith('#') or not uline.lstrip():
            continue
        addrs, details = uline.split(';', 1)
        addrs, details = addrs.rstrip(), details.lstrip()
        if any(details.startswith(f'{value} #')
               for value in categories):
            start, stop = addrs, addrs
            if '..' in addrs:
                start, stop = addrs.split('..')
            values.extend(range(int(start, 16), int(stop, 16) + 1))
    print('ok')
    return TableDef(version, date, sorted(values))


def do_write_table(fname, variable, table):
    """Write combining tables to filesystem as python code."""
    # pylint: disable=R0914
    #         Too many local variables (19/15) (col 4)
    utc_now = datetime.datetime.utcnow()
    indent = ' ' * 8
    with open(fname, 'w') as fout:
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
                ucs_start, ucs_end = unichr(start), unichr(end)
                hex_start, hex_end = (f'0x{start:05x}', f'0x{end:05x}')
                try:
                    name_start = string.capwords(unicodedata.name(ucs_start))
                except ValueError:
                    name_start = u'(nil)'
                try:
                    name_end = string.capwords(unicodedata.name(ucs_end))
                except ValueError:
                    name_end = u'(nil)'
                fout.write(f'\n{indent}')
                comment_startpart = name_start[:24].rstrip()
                comment_endpart = name_end[:24].rstrip()
                fout.write(f'({hex_start}, {hex_end},),')
                fout.write(f'  # {comment_startpart:24s}..{comment_endpart}')
            fout.write(f'\n{indent[:-4]}),\n')
        fout.write('}\n')
    print("complete.")


def do_unicode_versions(versions):
    """Write unicode_versions.py function list_versions()."""
    fname = os.path.join(PATH_CODE, 'unicode_versions.py')
    print(f"writing {fname} ... ", end='')

    utc_now = datetime.datetime.utcnow()
    version_tuples_str = '\n        '.join(
        f'"{ver}",' for ver in versions)
    with open(fname, 'w') as fp:
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
