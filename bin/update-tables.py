#!/usr/bin/env python
"""
Update the python Unicode tables for wcwidth.

https://github.com/jquast/wcwidth
"""
# std imports
import os
import re
import glob
import codecs
import string
import urllib
import datetime
import collections
import unicodedata
from urllib.request import urlopen

# third party
import jinja2

URL_UNICODE_DERIVED_AGE = 'http://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt'
EXCLUDE_VERSIONS = ['2.0.0', '2.1.2', '3.0.0', '3.1.0', '3.2.0', '4.0.0']
PATH_UP = os.path.relpath(
    os.path.join(
        os.path.dirname(__file__),
        os.path.pardir))
PATH_DATA = os.path.join(PATH_UP, 'data')
THIS_FILEPATH = os.path.relpath(__file__, os.path.join(PATH_UP, os.path.pardir))  # "wcwidth/bin/update-tables.py"
JINJA_ENV = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.path.join(PATH_UP, 'code_templates')),
            keep_trailing_newline=True)

TableDef = collections.namedtuple('table', ['version', 'date', 'values'])
RenderDef = collections.namedtuple('render', ['jinja_filename', 'output_filename', 'fn_data'])


# version codes are used by most templates
# TODO: memoize
def fetch_unicode_versions():
    """Fetch, determine, and return Unicode Versions for processing."""

    fname = os.path.join(PATH_DATA, os.path.basename(URL_UNICODE_DERIVED_AGE))
    do_retrieve(url=URL_UNICODE_DERIVED_AGE, fname=fname)
    pattern = re.compile(r'#.*assigned in Unicode ([0-9.]+)')
    versions = []
    for line in open(fname, 'r'):
        if match := re.match(pattern, line):
            version = match.group(1)
            if version not in EXCLUDE_VERSIONS:
                versions.append(version)
    versions.sort(key=lambda ver: list(map(int, ver.split('.'))))
    return {'versions': versions}


def fetch_source_headers():
    glob_pattern = os.path.join(PATH_DATA, '*[0-9]*.txt')
    filenames = glob.glob(glob_pattern)
    filenames.sort(key=lambda filename: make_sortable_source_name(filename))
    headers = []
    for filename in filenames:
        if header_description := fetch_source_description(filename):
            headers.append(header_description)
    return {'source_headers': headers}


CODEGEN_DEFINITIONS = [
    RenderDef(jinja_filename='unicode_versions.py.j2',
              output_filename=os.path.join(PATH_UP, 'code', 'unicode_versions.py'),
              fn_data=fetch_unicode_versions),
    RenderDef(jinja_filename='unicode_version.rst.j2',
              output_filename=os.path.join(PATH_UP, 'docs', 'unicode_version.rst'),
              fn_data=fetch_source_headers)
    RenderDef(jinja_filename='table_wide.py.j2',
              output_filename=os.path.join(PATH_UP, 'code', 'table_wide.py'),
              fn_data=fetch_table_wide_data),
#    RenderDef(jinja_filename='table_zero.py.j2',
#              output_filename=os.path.join(PATH_CODE, f'table_zero.py'),
#              fn_data=fetch_table_zero_data)
]


def main():
    """Update east-asian, combining and zero width tables."""
    for render_def in CODEGEN_DEFINITIONS:
        with open(render_def.output_filename, 'w') as fout:
            fout.write(render_template(render_def.jinja_filename, **render_def.fn_data()))

def render_template(jinja_filename, utc_now=UTC_NOW, this_filepath=THIS_FILEPATH, **kwargs):
    return JINJA_ENV.get_template(jinja_filename).render(
        utc_now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        this_filepath=THIS_FILEPATH,
        **kwargs)

#    do_rst_file_update()
    #render_unicode_versions(versions)
    #render_table_wide(versions)
    #render_table_wide(versions)

# functions for rendering unicode_version.rst
#

def make_sortable_source_name(filename):
    # make a sortable filename of unicode text file,
    #
    # >>> make_sorted_name("DerivedGeneralCategory-5.0.0.txt")
    # ('DerivedGeneralCategory', 5, 0, 0)
    basename, remaining = filename.split('-', 1)
    version_numbers, _extension = os.path.splitext(remaining)
    return (basename, *list(map(int, version_numbers.split('.'))))

def fetch_source_description(filename):
    # read first two lines, strip leading #
    header_twolines = [
        line.lstrip('# ').rstrip()
        for line in codecs.open(filename, 'r', 'utf8')
        .readlines()[:2]
    ]
    if len(header_twolines) == 2:
        return header_twolines

def fetch_table_wide_data():
    """Fetch and update east-asian tables."""
    table = {}
    for version in fetch_unicode_versions():
        fin = os.path.join(PATH_DATA, 'EastAsianWidth-{version}.txt')
        #fout = os.path.join(PATH_CODE, 'table_wide.py')
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
    return {
        'table': table,
        'variable': 'WIDE_EASTASIAN',
    }


def fetch_table_zero_data():
    """Fetch and update zero width tables."""
    table = {}
    #fout = os.path.join(PATH_CODE, 'table_zero.py')
    for version in fetch_unicode_versions():
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
                # todo: test whether all of category, 'Cf' should be excluded,
                # or, just a subset, see issue about 2060..2064 range
                # https://github.com/jquast/wcwidth/issues/26
                categories=('Me', 'Mn',))
    return table



# todo translate before jinja
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



#def do_unicode_versions(versions, lang):
#    """Write unicode_versions.py function list_versions()."""
#    jinja_filename = 
#    output_filename = 
#    with open(output_filename, 'w') as fout:
#        fout.write(
#
#
#
#    do_unicode_versions(versions, lang='py')
#    val = fetch_east_asian_table(versions, lang='py')
#    assert False, val
#    assert False
#    #do_write_table(fname=fout, variable='WIDE_EASTASIAN', table=table, lang=lang)
#    fetch_zero_width_table(versions, lang='py')
#    #do_write_table(fname=fout, variable='ZERO_WIDTH', table=table, lang=lang)


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


def do_write_table(fname, variable, table, lang):
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
                ucs_start, ucs_end = chr(start), chr(end)
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


if __name__ == '__main__':
    main()
