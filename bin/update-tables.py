#!/usr/bin/env python
"""
Update the python Unicode tables for wcwidth.

This should be executed through tox,

    $ tox -e update

Use argument --check-last-modified if data files were previously downloaded,
but will refresh by last-modified check using HEAD request from unicode.org
URLs.

    $ tox -e update -- --check-last-modified

https://github.com/jquast/wcwidth
"""


from __future__ import annotations

# std imports
import os
import re
import sys
import glob
import string
import logging
import datetime
import functools
import collections
import unicodedata
from dataclasses import dataclass

# 3rd party
import jinja2
import requests
import tenacity
import dateutil.parser


URL_UNICODE_DERIVED_AGE = 'https://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt'
URL_EASTASIAN_WIDTH = 'https://www.unicode.org/Public/{version}/ucd/EastAsianWidth.txt'
URL_DERIVED_CATEGORY = 'https://www.unicode.org/Public/{version}/ucd/extracted/DerivedGeneralCategory.txt'
EXCLUDE_VERSIONS = ['2.0.0', '2.1.2', '3.0.0', '3.1.0', '3.2.0', '4.0.0']

PATH_UP = os.path.relpath(os.path.join(os.path.dirname(__file__), os.path.pardir))
PATH_DATA = os.path.join(PATH_UP, 'data')
THIS_FILEPATH = os.path.relpath(__file__, os.path.join(
    PATH_UP, os.path.pardir))  # "wcwidth/bin/update-tables.py"

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(PATH_UP, 'code_templates')),
    keep_trailing_newline=True)
UTC_NOW = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

CONNECT_TIMEOUT = int(os.environ.get('CONNECT_TIMEOUT', '10'))
FETCH_BLOCKSIZE = int(os.environ.get('FETCH_BLOCKSIZE', '4096'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '10'))

logger = logging.getLogger(__name__)


@dataclass(order=True, frozen=True)
class UnicodeVersion:
    """A class for camparable unicode version"""
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


TableDef = collections.namedtuple('table', ['version', 'date', 'values'])
RenderDefinition = collections.namedtuple(
    'render', ['jinja_filename', 'output_filename', 'fn_data'])


@functools.cache
def fetch_unicode_versions() -> list[UnicodeVersion]:
    """Fetch, determine, and return Unicode Versions for processing."""
    fname = os.path.join(PATH_DATA, os.path.basename(URL_UNICODE_DERIVED_AGE))
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


def fetch_source_headers():
    glob_pattern = os.path.join(PATH_DATA, '*[0-9]*.txt')
    filenames = glob.glob(glob_pattern)
    filenames.sort(key=lambda filename: make_sortable_source_name(filename))
    headers = []
    for filename in filenames:
        if header_description := cite_source_description(filename):
            headers.append(header_description)
    return {'source_headers': headers}


def fetch_table_wide_data() -> dict:
    """Fetch and update east-asian tables."""
    table = {}
    for version in fetch_unicode_versions():
        fname = os.path.join(PATH_DATA, f'EastAsianWidth-{version}.txt')
        do_retrieve(url=URL_EASTASIAN_WIDTH.format(version=version), fname=fname)
        table[version] = parse_category(fname=fname, category_codes=('W', 'F',))
    return {'table': table, 'variable_name': 'WIDE_EASTASIAN'}


def fetch_table_zero_data() -> dict:
    """Fetch and update zero width tables."""
    table = {}
    for version in fetch_unicode_versions():
        fname = os.path.join(PATH_DATA, f'DerivedGeneralCategory-{version}.txt')
        do_retrieve(url=URL_DERIVED_CATEGORY.format(version=version), fname=fname)
        # TODO: test whether all of category, 'Cf' should be 'zero
        #       width', or, just the subset 2060..2064, see open issue
        #       https://github.com/jquast/wcwidth/issues/26
        table[version] = parse_category(fname=fname, category_codes=('Me', 'Mn',))
    return {'table': table, 'variable_name': 'ZERO_WIDTH'}


def render_template(jinja_filename, utc_now=UTC_NOW, this_filepath=THIS_FILEPATH, **kwargs):
    return JINJA_ENV.get_template(jinja_filename).render(
        utc_now=utc_now,
        this_filepath=THIS_FILEPATH,
        **kwargs)


def cite_source_description(filename):
    """Return unicode.org source data file's own description as citation."""
    header_twolines = [
        line.lstrip('# ').rstrip()
        for line in open(filename, encoding='utf-8')
        .readlines()[:2]
    ]
    if len(header_twolines) == 2:
        return header_twolines


def make_sortable_source_name(filename):
    # make a sortable filename of unicode text file,
    #
    # >>> make_sorted_name("DerivedGeneralCategory-5.0.0.txt")
    # ('DerivedGeneralCategory', 5, 0, 0)
    basename, remaining = filename.split('-', 1)
    version_numbers, _extension = os.path.splitext(remaining)
    return (basename, *list(map(int, version_numbers.split('.'))))


def make_table(values):
    """Return a tuple of lookup tables for given values."""
    start, end = values[0], values[0]
    table = collections.deque()
    table.append((start, end))
    for value in values[1:]:
        start, end = table.pop()
        if end == value - 1:
            # continuation of existing range
            table.append((start, value,))
        else:
            # put back existing range,
            table.append((start, end,))
            # and start a new one
            table.append((value, value,))
    return tuple(table)


def convert_values_to_string_table(values):
    """Convert integers into string table of (hex_start, hex_end, txt_description)."""
    pytable_values = []
    for start, end in values:
        hex_start, hex_end = (f'0x{start:05x}', f'0x{end:05x}')
        ucs_start, ucs_end = chr(start), chr(end)
        name_start, name_end = '(nil)', '(nil)'
        try:
            name_start = string.capwords(unicodedata.name(ucs_start))
        except ValueError:
            pass
        try:
            name_end = string.capwords(unicodedata.name(ucs_end))
        except ValueError:
            pass
        if name_start != name_end:
            txt_description = f'{name_start[:24].rstrip():24s}..{name_end[:24].rstrip()}'
        else:
            txt_description = f'{name_start[:48]}'
        pytable_values.append((hex_start, hex_end, txt_description))
    return pytable_values


def parse_category(fname: str, category_codes=('Me', 'Mn',)) -> TableDef:
    """Parse value ranges of unicode data files, by given categories into string tables."""
    print(f'parsing {fname}: ', end='', flush=True)
    version = None
    date = None
    values: set[int] = set()
    with open(fname, encoding='utf-8') as f:
        for line in f:
            if version is None:
                # pull "version string" from first line of source file
                version = line.split(None, 1)[1].rstrip()
                continue
            if date is None:
                # and "date string" from second line
                date = line.split(':', 1)[1].rstrip()
                continue
            if line.startswith('#') or not line.lstrip():
                # ignore any further comments or empty lines
                continue
            addrs, details = line.split(';', 1)
            addrs, details = addrs.rstrip(), details.lstrip()
            if any(details.startswith(f'{category_code}')
                   for category_code in category_codes):
                if '..' in addrs:
                    start, stop = addrs.split('..')
                else:
                    start, stop = addrs, addrs
                values.update(range(int(start, 16), int(stop, 16) + 1))
    txt_values = convert_values_to_string_table(make_table(sorted(values)))
    print('ok')
    return TableDef(version, date, txt_values)


def is_url_newer(url, fname):
    if not os.path.exists(fname):
        return True
    if '--check-last-modified' in sys.argv[1:]:
        resp = requests.head(url, timeout=CONNECT_TIMEOUT)
        resp.raise_for_status()
        remote_url_dt = dateutil.parser.parse(resp.headers['Last-Modified']).astimezone()
        local_file_dt = datetime.datetime.fromtimestamp(os.path.getmtime(fname)).astimezone()
        return remote_url_dt > local_file_dt
    return False


@tenacity.retry(reraise=True, wait=tenacity.wait_none(),
                retry=tenacity.retry_if_exception_type(requests.exceptions.RequestException),
                stop=tenacity.stop_after_attempt(MAX_RETRIES),
                before_sleep=tenacity.before_sleep_log(logger, logging.DEBUG))
def do_retrieve(url, fname):
    """Retrieve given url to target filepath fname."""
    folder = os.path.dirname(fname)
    if not os.path.exists(folder):
        os.makedirs(folder)
    if not is_url_newer(url, fname):
        return
    resp = requests.get(url, timeout=CONNECT_TIMEOUT)
    resp.raise_for_status()
    print(f"saving {fname}: ", end='', flush=True)
    with open(fname, 'wb') as fout:
        for chunk in resp.iter_content(FETCH_BLOCKSIZE):
            fout.write(chunk)
            print('.', end='', flush=True)
    print('ok')


def main() -> None:
    """Update east-asian, combining and zero width tables."""
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    # This defines which jinja source templates map to which output filenames,
    # and what function defines the source data. We hope to add more source
    # language options using jinja2 templates, with minimal modification of the
    # code.
    CODEGEN_DEFINITIONS = [
        RenderDefinition(
            jinja_filename='unicode_versions.py.j2',
            output_filename=os.path.join(PATH_UP, 'wcwidth', 'unicode_versions.py'),
            fn_data=lambda: {'versions': fetch_unicode_versions()}),
        RenderDefinition(
            jinja_filename='unicode_version.rst.j2',
            output_filename=os.path.join(PATH_UP, 'docs', 'unicode_version.rst'),
            fn_data=fetch_source_headers),
        RenderDefinition(
            jinja_filename='python_table.py.j2',
            output_filename=os.path.join(PATH_UP, 'wcwidth', 'table_wide.py'),
            fn_data=fetch_table_wide_data),
        RenderDefinition(
            jinja_filename='python_table.py.j2',
            output_filename=os.path.join(PATH_UP, 'wcwidth', 'table_zero.py'),
            fn_data=fetch_table_zero_data)
    ]
    for render_def in CODEGEN_DEFINITIONS:
        with open(render_def.output_filename, 'w', encoding='utf-8') as fout:
            data = render_def.fn_data()
            print(f'write {render_def.output_filename}: ', flush=True, end='')
            fout.write(render_template(render_def.jinja_filename, **data))
            print('ok')


if __name__ == '__main__':
    main()
