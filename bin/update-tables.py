#!/usr/bin/env python
"""
Update the python Unicode tables for wcwidth.

https://github.com/jquast/wcwidth
"""

# TODO: when a unicode point was released: may be determined from
# http://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt

from __future__ import print_function
import setuptools.command.test
import collections
import setuptools
import json
import os

try:
    # py2
    from urllib2 import urlopen
except ImportError:
    # py3
    from urllib.request import urlopen

# local imports
import wcwidth

PATH_UP = os.path.relpath(
    os.path.join(os.path.dirname(__file__), os.path.pardir))

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


# note: when a unicode point was released: may be determined from
# http://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt

EAW_URL = ('http://www.unicode.org/Public/{version}/'
           'ucd/EastAsianWidth.txt')
EAW_IN = os.path.join(PATH_UP, 'data',
                      'EastAsianWidth-{version}.txt')
EAW_OUT = os.path.join(PATH_UP, 'wcwidth', 'table_wide.py')

UCD_URL = ('http://www.unicode.org/Public/{version}/ucd/extracted/'
           'DerivedGeneralCategory.txt')
UCD_IN = os.path.join(PATH_UP, 'data',
                      'DerivedGeneralCategory-{version}.txt')
ZERO_OUT = os.path.join(PATH_UP, 'wcwidth', 'table_zero.py')

FILE_RST = os.path.join(PATH_UP, 'docs/unicode_version.rst')
FILE_PATCH_FROM = "release files:"
FILE_PATCH_TO = "======="


TableDef = collections.namedtuple('table', ['version', 'date', 'values'])

def main():
    """Update east-asian, combining and zero width tables."""
    versions = get_unicode_versions()
    do_east_asian(versions)
    do_zero_width(versions)
    do_rst_file_update()
    do_version_json(versions)

def get_unicode_versions():
    # TODO: Dynamically try for the future somehows..
    return ['4.1.0',
            '5.0.0',
            '5.1.0',
            '5.2.0',
            '6.0.0',
            '6.1.0',
            '6.2.0',
            '6.3.0',
            '7.0.0',
            '8.0.0',
            '9.0.0']

def do_rst_file_update():
    """Patch unicode_versions.rst to reflect the data files used in release."""
    import codecs
    import glob

    # read in,
    data_in = codecs.open(FILE_RST, 'r', 'utf8').read()

    # search for beginning and end positions,
    pos_begin = data_in.find(FILE_PATCH_FROM)
    assert pos_begin != -1, (pos_begin, FILE_PATCH_FROM)
    pos_begin += len(FILE_PATCH_FROM)

    glob_pattern = os.path.join(PATH_UP, 'data', '*.txt')
    file_descriptions = [
        describe_file_header(fpath)
        for fpath in sorted(glob.glob(glob_pattern))]

    # patch,
    data_out = (
        data_in[:pos_begin] +
        '\n\n' +
        '\n'.join(file_descriptions) +
        '\n'
    )

    # write.
    print("patching {} ..".format(FILE_RST))
    codecs.open(
        FILE_RST, 'w', 'utf8').write(data_out)

def do_east_asian(versions):
    """Fetch and update east-asian tables."""
    for version in versions:
        fin = os.path.join(PATH_UP, 'data', 'EastAsianWidth-{version}.txt')
        fout = os.path.join(PATH_UP, 'wcwidth', 'table_wide.py')
        url = ('http://www.unicode.org/Public/{version}/'
                   'ucd/EastAsianWidth.txt')
        do_retrieve(url=url.format(version=version),
                    fname=fin.format(version=version))
    table = {
        version: parse_east_asian(fname=fin.format(version=version),
                                  properties=(u'W', u'F',))
        for version in versions
    }
    do_write_table(fname=fout, variable='WIDE_EASTASIAN', table=table)

def do_zero_width(versions):
    """Fetch and update zero width tables."""
    for version in versions:
        fin = os.path.join(PATH_UP, 'data', 'DerivedGeneralCategory-{version}.txt')
        fout = os.path.join(PATH_UP, 'wcwidth', 'table_zero.py')
        url = ('http://www.unicode.org/Public/{version}/ucd/extracted/'
                   'DerivedGeneralCategory.txt')
        do_retrieve(url=url.format(version=version),
                     fname=fin.format(version=version))
    table = {
        version: parse_category(fname=fin.format(version=version),
                                categories=('Me', 'Mn',))
        for version in versions
    }
    do_write_table(fname=fout, variable='ZERO_WIDTH', table=table)

def make_table(values):
    """Return a tuple of lookup tables for given values."""
    import collections
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
        print("{}/ created.".format(folder))
    if not os.path.exists(fname):
        with open(fname, 'wb') as fout:
            print("retrieving {}.".format(url))
            resp = urlopen(url)
            fout.write(resp.read())
        print("{} saved.".format(fname))
    else:
        print("re-using artifact {}".format(fname))
    return fname

def describe_file_header(fpath):
    import codecs
    header_2 = [line.lstrip('# ').rstrip() for line in
                codecs.open(fpath, 'r', 'utf8').readlines()[:2]]
    # fmt:
    #
    # ``EastAsianWidth-8.0.0.txt``
    #   *2015-02-10, 21:00:00 GMT [KW, LI]*
    fmt = '``{0}``\n  *{1}*\n'
    assert len(header_2) == 2, (fpath, header_2)
    return (fmt.format(*header_2))

def parse_east_asian(fname, properties=(u'W', u'F',)):
    """Parse unicode east-asian width tables."""
    version, date, values = None, None, []
    print("parsing {} ..".format(fname))
    for line in open(fname, 'rb'):
        uline = line.decode('utf-8')
        if version is None:
            version = uline.split(None, 1)[1].rstrip()
            continue
        elif date is None:
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
    return TableDef(version, date, values)

def parse_category(fname, categories):
    """Parse unicode category tables."""
    version, date, values = None, None, []
    print("parsing {} ..".format(fname))
    for line in open(fname, 'rb'):
        uline = line.decode('utf-8')
        if version is None:
            version = uline.split(None, 1)[1].rstrip()
            continue
        elif date is None:
            date = uline.split(':', 1)[1].rstrip()
            continue
        if uline.startswith('#') or not uline.lstrip():
            continue
        addrs, details = uline.split(';', 1)
        addrs, details = addrs.rstrip(), details.lstrip()
        if any(details.startswith('{} #'.format(value))
               for value in categories):
            start, stop = addrs, addrs
            if '..' in addrs:
                start, stop = addrs.split('..')
            values.extend(range(int(start, 16), int(stop, 16) + 1))
    return TableDef(version, date, sorted(values))

def do_write_table(fname, variable, table):
    """Write combining tables to filesystem as python code."""
    # pylint: disable=R0914
    #         Too many local variables (19/15) (col 4)
    print("writing {} ..".format(fname))
    import unicodedata
    import datetime
    import string
    utc_now = datetime.datetime.utcnow()
    indent = 4
    with open(fname, 'w') as fout:
        fout.write(
            '"""{variable_proper} table. Created by setup.py."""\n'
            "# Generated: {iso_utc}\n"
            "{variable} = {{\n".format(
                iso_utc=utc_now.isoformat(),
                variable_proper=variable.title(),
                variable=variable))

        for version_key, version_table in sorted(table.items()):
            fout.write(
                "  '{version_key}': (\n"
                "    # Source: {version_table.version}\n"
                "    # Date: {version_table.date}\n"
                "    #".format(
                    version_key=version_key,
                    version_table=version_table))

            for start, end in make_table(version_table.values):
                ucs_start, ucs_end = unichr(start), unichr(end)
                hex_start, hex_end = ('0x{0:04x}'.format(start),
                                      '0x{0:04x}'.format(end))
                try:
                    name_start = string.capwords(unicodedata.name(ucs_start))
                except ValueError:
                    name_start = u''
                try:
                    name_end = string.capwords(unicodedata.name(ucs_end))
                except ValueError:
                    name_end = u''
                fout.write('\n' + (' ' * indent))
                fout.write('({0}, {1},),'.format(hex_start, hex_end))
                fout.write('  # {0:24s}..{1}'.format(
                    name_start[:24].rstrip() or '(nil)',
                    name_end[:24].rstrip()))
            fout.write('\n  ),\n')
        fout.write('}\n')
    print("complete.")

def do_version_json(versions):
    fname = os.path.join(PATH_UP, 'wcwidth', 'version.json')
    print("writing {}".format(fname))

    with open(fname, 'r') as fp:
        version_data = json.load(fp)

    version_data['tables'] = versions

    with open(fname, 'w') as fp:
        version_data = json.dump(version_data, fp)

if __name__ == '__main__':
    main()

