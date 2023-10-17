#!/usr/bin/env python
"""
Update the Unicode code tables for wcwidth.  This is code generation using jinja2.

This should be executed through tox,

    $ tox -e update

If data files were previously downloaded, but will refresh by last-modified
check using HEAD request from unicode.org URLs, unless --no-check-last-modified
is used:

    $ tox -e update -- --check-last-modified

https://github.com/jquast/wcwidth
"""
from __future__ import annotations

# std imports
import os
import re
import sys
import string
import logging
import datetime
import functools
import collections
import unicodedata
from pathlib import Path
from dataclasses import field, fields, dataclass

from typing import Any, Mapping, Iterable, Iterator, Sequence, Container, Collection

# 3rd party
import jinja2
import requests
import urllib3.util
import dateutil.parser
from typing_extensions import Self

URL_UNICODE_DERIVED_AGE = 'https://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt'
URL_EASTASIAN_WIDTH = 'https://www.unicode.org/Public/{version}/ucd/EastAsianWidth.txt'
URL_DERIVED_CATEGORY = 'https://www.unicode.org/Public/{version}/ucd/extracted/DerivedGeneralCategory.txt'
URL_EMOJI_ZWJ_SEQUENCES = 'https://unicode.org/Public/emoji/{version}/emoji-zwj-sequences.txt'
EXCLUDE_VERSIONS = ['2.0.0', '2.1.2', '3.0.0', '3.1.0', '3.2.0', '4.0.0']

PATH_UP = os.path.relpath(os.path.join(os.path.dirname(__file__), os.path.pardir))
PATH_DATA = os.path.join(PATH_UP, 'data')
# "wcwidth/bin/update-tables.py", even on Windows
# not really a path, if the git repo isn't named "wcwidth"
THIS_FILEPATH = ('wcwidth/' +
                 Path(__file__).resolve().relative_to(Path(PATH_UP).resolve()).as_posix())

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(PATH_UP, 'code_templates')),
    keep_trailing_newline=True)
UTC_NOW = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

CONNECT_TIMEOUT = int(os.environ.get('CONNECT_TIMEOUT', '10'))
FETCH_BLOCKSIZE = int(os.environ.get('FETCH_BLOCKSIZE', '4096'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '6'))
BACKOFF_FACTOR = float(os.environ.get('BACKOFF_FACTOR', '0.1'))

logger = logging.getLogger(__name__)


@dataclass(order=True, frozen=True)
class UnicodeVersion:
    """A class for comparing 2 and 3-digit versions used in unicode data files"""
    major: int
    minor: int
    micro: int = None

    @classmethod
    def parse(cls, version_str: str) -> UnicodeVersion:
        """
        Parse version strings used by unicode data files.

        >>> UnicodeVersion.parse("14.0.0")
        UnicodeVersion(major=14, minor=0, micro=0)

        >>> UnicodeVersion.parse("15.1")
        UnicodeVersion(major=15, minor=1, micro=None)
        """
        versions = list(map(int, version_str.split(".")[:3]))
        while len(versions) < 3:
            versions.append(None)
        return cls(*versions)

    def __str__(self) -> str:
        """
        >>> str(UnicodeVersion(12, 1, 0))
        '12.1.0'
        >>> str(UnicodeVersion(15, 1, None))
        '15.1'

        """
        maybe_micro = ''
        if self.micro is not None:
            maybe_micro = f'.{self.micro}'
        return f'{self.major}.{self.minor}{maybe_micro}'

    @property
    def major_minor(self) -> str:
        """
        >>> UnicodeVersion(11, 0, 0).major_minor
        '11.0'
        """
        return f'{self.major}.{self.minor}'


@dataclass(frozen=True)
class TableEntry:
    """An entry of a unicode table."""
    code_range: tuple[int, int] | None
    properties: tuple[str, ...]
    comment: str

    def filter_by_category(entry, category_codes, wide):
        if entry.code_range is None:
            return False
        elif entry.properties[0] == 'Sk':
            if 'EMOJI MODIFIER' in entry.comment:
                # These codepoints are fullwidth when used without emoji, 0-width with.
                # Generate code that expects the best case, that is always combined
                return wide == 0
            elif 'FULLWIDTH' in entry.comment:
                # Some 'Sk' categories are fullwidth,
                return wide == 2
            else:
                # the rest are narrow
                return wide == 1
        if entry.properties[0] in ('W', 'F'):
            return wide == 2
        # TODO I think 'Cf' has some mixed cases ..
        if entry.properties[0] in ('Me', 'Mn', 'Cf', 'Zl', 'Zp'):
            return wide == 0
        return wide == 1


    @staticmethod
    def parse_category_values(category_codes: str,
                            table_iter: Iterator[TableEntry],
                            wide: int) -> set[tuple[int, int]]:
        """
        Parse value ranges of unicode data files, by given category and width
        """
        return {
            (entry.code_range[0], entry.code_range[1] - 1)
            for entry in table_iter
            if entry.filter_by_category(category_codes, wide)}



@dataclass(frozen=True)
class SequenceEntry:
    """An entry of a unicode sequence."""
    code_seq: str | None
    description: str
    comment: str

@dataclass
class TableDef:
    filename: str
    date: str
    value_ranges: set[tuple[int, int]]

    def optimized_values(self) -> list[tuple[int, int]]:
        """
        Given unsorted ranges of (start, end), 'value_ranges', compress into
        a sorted ascending list of non-overlapping, merged ranges.
        """
        result = []
        for start, end in sorted(self.value_ranges):
            if result and result[-1][1] + 1 == start:
                result[-1] = (result[-1][0], end)
            else:
                result.append((start, end))
        return result


    @property
    def hex_range_descriptions(self) -> list[tuple[str, str, str]]:
        """Convert integers into string table of (hex_start, hex_end, txt_description)."""
        pytable_values: list[tuple[str, str, str]] = []
        for start, end in self.optimized_values():
            hex_start, hex_end = f'0x{start:05x}', f'0x{end:05x}'
            ucs_start, ucs_end = chr(start), chr(end)
            name_start = name_ucs(ucs_start) or '(nil)'
            name_end = name_ucs(ucs_end) or '(nil)'
            if name_start != name_end:
                txt_description = f'{name_start[:24].rstrip():24s}..{name_end[:24].rstrip()}'
            else:
                txt_description = f'{name_start[:48]}'
            pytable_values.append((hex_start, hex_end, txt_description))
        return pytable_values


@dataclass
class SequenceDef:
    filename: str
    date: str
    sequences: dict[int, list[tuple[str, str]]]


@dataclass(frozen=True)
class RenderContext:
    def to_dict(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name)
                for field in fields(self)}


@dataclass(frozen=True)
class UnicodeVersionPyRenderCtx(RenderContext):
    versions: Collection[UnicodeVersion]


@dataclass(frozen=True)
class UnicodeVersionRstRenderCtx(RenderContext):
    source_headers: Sequence[tuple[str, str]]


@dataclass(frozen=True)
class UnicodeTableRenderCtx(RenderContext):
    variable_name: str
    table: Mapping[UnicodeVersion, TableDef]


@dataclass
class RenderDefinition:
    """Base class, do not instantiate it directly."""
    jinja_filename: str
    output_filename: str
    render_context: RenderContext

    _template: jinja2.Template = field(init=False, repr=False)
    _render_context: dict[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._template = JINJA_ENV.get_template(self.jinja_filename)
        self._render_context = {
            'utc_now': UTC_NOW,
            'this_filepath': THIS_FILEPATH,
            **self.render_context.to_dict(),
        }

    def render(self) -> str:
        """just like jinja2.Template.render."""
        return self._template.render(self._render_context)

    def generate(self) -> Iterator[str]:
        """just like jinja2.Template.generate."""
        return self._template.generate(self._render_context)


@dataclass
class UnicodeVersionPyRenderDef(RenderDefinition):
    render_context: UnicodeVersionPyRenderCtx

    @classmethod
    def new(cls, context: UnicodeVersionPyRenderCtx) -> Self:
        return cls(
            jinja_filename='unicode_versions.py.j2',
            output_filename=os.path.join(PATH_UP, 'wcwidth', 'unicode_versions.py'),
            render_context=context,
        )


@dataclass
class UnicodeVersionRstRenderDef(RenderDefinition):
    render_context: UnicodeVersionRstRenderCtx

    @classmethod
    def new(cls, context: UnicodeVersionRstRenderCtx) -> Self:
        return cls(
            jinja_filename='unicode_version.rst.j2',
            output_filename=os.path.join(PATH_UP, 'docs', 'unicode_version.rst'),
            render_context=context,
        )


@dataclass
class UnicodeTableRenderDef(RenderDefinition):
    render_context: UnicodeTableRenderCtx

    @classmethod
    def new(cls, filename: str, context: UnicodeTableRenderCtx) -> Self:
        _, ext = os.path.splitext(filename)
        if ext == '.py':
            jinja_filename = 'python_table.py.j2'
        elif ext == '.c':
            # TODO
            jinja_filename = 'c_table.c.j2'
        else:
            raise ValueError('filename must be a Python or a C file')

        return cls(
            jinja_filename=jinja_filename,
            output_filename=os.path.join(PATH_UP, 'wcwidth', filename),
            render_context=context,
        )

@dataclass
class UnicodeSequenceRenderDef(RenderDefinition):
    render_context: UnicodeTableRenderCtx

    @classmethod
    def new(cls, filename: str, context: UnicodeTableRenderCtx) -> Self:
        _, ext = os.path.splitext(filename)
        if ext == '.py':
            jinja_filename = 'emoji_zwj_sequences.py.j2'
        else:
            raise ValueError('filename must be Python')

        return cls(
            jinja_filename=jinja_filename,
            output_filename=os.path.join(PATH_UP, 'wcwidth', filename),
            render_context=context,
        )


@functools.cache
def fetch_unicode_versions() -> list[UnicodeVersion]:
    """Fetch, determine, and return Unicode Versions for processing."""
    fname = os.path.join(PATH_DATA, URL_UNICODE_DERIVED_AGE.rsplit('/', 1)[-1])
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

def fetch_zwj_versions() -> list[UnicodeVersion]:
    """Determine Unicode Versions with Emoji Zero Width Join character support."""
    # From Unicode® Technical Standard #51
    #
    # > Starting with Version 11.0 of this specification, the repertoire of
    # > emoji characters is synchronized with the Unicode Standard, and has the
    # > same version numbering system. For details, see Section 1.5.2, Versioning.
    #
    # http://www.unicode.org/reports/tr51/#Versioning
    #
    fname = os.path.join(PATH_DATA, URL_EMOJI_ZWJ_SEQUENCES.rsplit('/', 1)[-1])
    filename, ext = os.path.splitext(fname)
    fname = filename + '-latest' + ext
    do_retrieve(url=URL_EMOJI_ZWJ_SEQUENCES.format(version='latest'), fname=fname)
    pattern = re.compile(r'.*# E([0-9.]+)')
    versions = set()
    with open(fname, encoding='utf-8') as f:
        for line in f:
            if match := re.match(pattern, line):
                version = match.group(1)
                versions.add(UnicodeVersion.parse(version))
    return sorted(versions)

def fetch_source_headers() -> UnicodeVersionRstRenderCtx:
    # find all filenames with a version number in it,
    # sort filenames by name, then dotted number, ascending
    pattern = re.compile(
        r'^(DerivedGeneralCategory|EastAsianWidth)-(\d+)\.(\d+)\.(\d+)\.txt$')
    filename_matches = []
    for fname in os.listdir(PATH_DATA):
        if match := re.search(pattern, fname):
            filename_matches.append(match)

    filename_matches.sort(key=lambda m: (
        m.group(1),
        int(m.group(2)),
        int(m.group(3)),
        int(m.group(4)),
    ))
    filenames = [os.path.join(PATH_DATA, match.string)
                 for match in filename_matches]

    headers: list[tuple[str, str]] = []
    for filename in filenames:
        header_description = cite_source_description(filename)
        headers.append(header_description)
    return UnicodeVersionRstRenderCtx(headers)


def fetch_table_wide_data() -> UnicodeTableRenderCtx:
    """Fetch and update east-asian tables."""
    table: dict[UnicodeVersion, TableDef] = {}
    for version in fetch_unicode_versions():
        # parse typical 'wide' characters by categories 'W' and 'F',
        fname_eaw = os.path.join(PATH_DATA, f'EastAsianWidth-{version}.txt')
        do_retrieve(url=URL_EASTASIAN_WIDTH.format(version=version), fname=fname_eaw)
        table[version] = parse_category(fname=fname_eaw, category_codes=('W', 'F'), wide=2)

        # join with some atypical 'wide' characters found in category 'Sk'
        fname_dgc = os.path.join(PATH_DATA, f'DerivedGeneralCategory-{version}.txt')
        do_retrieve(url=URL_UNICODE_DERIVED_AGE.format(version=version), fname=fname_dgc)
        table[version].value_ranges.update(parse_category(fname=fname_dgc, category_codes=('Sk',), wide=2).value_ranges)
    return UnicodeTableRenderCtx('WIDE_EASTASIAN', table)


def fetch_table_zero_data() -> UnicodeTableRenderCtx:
    """Fetch and update zero width tables."""
    table: dict[UnicodeVersion, TableDef] = {}
    for version in fetch_unicode_versions():
        # Determine values of zero-width character lookup table by the following category codes
        fname_dgc = os.path.join(PATH_DATA, f'DerivedGeneralCategory-{version}.txt')
        do_retrieve(url=URL_DERIVED_CATEGORY.format(version=version), fname=fname_dgc)
        table[version] = parse_category(fname=fname_dgc, category_codes=('Me', 'Mn', 'Cf', 'Zl', 'Zp', 'Sk'), wide=0)

        # Look for the few zero-width characters mislabelled as W in eastasian width files.
        fname_eaw = os.path.join(PATH_DATA, f'EastAsianWidth-{version}.txt')
        do_retrieve(url=URL_EASTASIAN_WIDTH.format(version=version), fname=fname_eaw)
        table[version].value_ranges.update(parse_category(fname=fname_eaw, category_codes=('N','W'), wide=0).value_ranges)

        # And, include NULL
        table[version].value_ranges.add((0, 0))
    return UnicodeTableRenderCtx('ZERO_WIDTH', table)


def fetch_emoji_zero_data() -> UnicodeTableRenderCtx:
    """Fetch the latest emoji zero width joiner (ZWJ)."""
    table: dict[UnicodeVersion, SequenceDef] = {}
    for version in fetch_zwj_versions():
        fname = os.path.join(PATH_DATA, f'emoji-zwj-sequences-{version}.txt')
        do_retrieve(url=URL_EMOJI_ZWJ_SEQUENCES.format(version=version), fname=fname)
        table[version] = parse_zwj(fname=fname, version=version)
    return UnicodeTableRenderCtx('EMOJI_ZWJ_SEQUENCES', table)


def cite_source_description(filename: str) -> tuple[str, str]:
    """Return unicode.org source data file's own description as citation."""
    with open(filename, encoding='utf-8') as f:
        entry_iter = parse_unicode_table(f)
        fname = next(entry_iter).comment.strip()
        date = next(entry_iter).comment.strip()

    return fname, date


def make_table(value_ranges: Collection[int]) -> list[tuple[int, int]]:
    """
    Return a tuple of (start, end) lookup pairs for given sequence of sorted values.

    >>> make_table([0,1,2,5,6,7,9])
    [(0, 2), (5, 7), (9, 9)]
    """
    table: list[tuple[int, int]] = []
    values_iter = iter(values_range)
    start = end = next(values_iter)
    table.append((start, end))

    for value in values_iter:
        start, end = table.pop()
        if end == value - 1:
            # continuation of existing range
            table.append((start, value,))
        else:
            # insert back previous range,
            table.append((start, end,))
            # and start a new one
            table.append((value, value,))
    return table

def name_ucs(ucs: str) -> str:
    try:
        return string.capwords(unicodedata.name(ucs))
    except ValueError:
        return None


def parse_unicode_table(file: Iterable[str]) -> Iterator[TableEntry]:
    """
    Parse unicode tables.

    See details: https://www.unicode.org/reports/tr44/#Format_Conventions
    """
    for line in file:
        data, _, comment = line.partition('#')
        data_fields: Iterator[str] = (field.strip() for field in data.split(';'))
        code_points_str, *properties = data_fields

        if not code_points_str:
            yield TableEntry(None, tuple(properties), comment)
            continue

        if '..' in code_points_str:
            start, end = code_points_str.split('..')
        else:
            start = end = code_points_str
        code_range = (int(start, base=16), int(end, base=16) + 1)

        yield TableEntry(code_range, tuple(properties), comment)


def parse_category(fname: str, category_codes: Container[str], wide: int) -> TableDef:
    """Parse value ranges of unicode data files, by given categories into string tables."""
    print(f'parsing {fname}: ', end='', flush=True)

    with open(fname, encoding='utf-8') as f:
        table_iter = parse_unicode_table(f)

        # pull "version string" from first line of source file
        version = next(table_iter).comment.strip()
        # and "date string" from second line
        date = next(table_iter).comment.split(':', 1)[1].strip()
        value_ranges = TableEntry.parse_category_values(category_codes, table_iter, wide)
    print('ok')
    return TableDef(version, date, value_ranges)


def parse_zwj_file(file: Iterable[str]) -> Iterator[SequenceEntry]:
    """
    Parse Emoji ZWJ Sequences

    Format:
        code_point(s) ; type_field ; description # comments
    """
    for line in file:
        data, _, comment = line.partition('#')
        data_fields: Iterator[str] = (field.strip() for field in data.split(';'))
        code_points_str, *type_description = data_fields
        description = ''
        if len(type_description) > 1:
            description = type_description[1]

        if not code_points_str:
            # ignore comments or empty lines, except for 'Date:' -- a marker
            # found across all releases so far.
            if 'Date:' in comment:
                yield SequenceEntry(None, None, comment)
            continue

        hex_values = tuple(f'0x{int(code_point, 16):05x}'
                           for code_point in code_points_str.split())
        yield SequenceEntry(hex_values, description, comment)


def parse_zwj(fname: str, version: str) -> SequenceDef:
    print(f'parsing {fname}: ', end='', flush=True)
    with open(fname, encoding='utf-8') as f:
        table_iter = parse_zwj_file(f)
        date = next(table_iter).comment.split(':', 1)[1].strip()
        # sequences are keyed by length
        sequences = collections.defaultdict(list)
        for entry in table_iter:
            if entry.code_seq is not None:
                sequences[len(entry.code_seq)].append((entry.code_seq, entry.description))
    sorted_sequences = collections.OrderedDict([(k, v) for k, v in sorted(sequences.items())])
    print('ok')
    return SequenceDef(fname, date, sorted_sequences)


@functools.cache
def get_http_session() -> requests.Session:
    session = requests.Session()
    retries = urllib3.util.Retry(total=MAX_RETRIES,
                                 backoff_factor=BACKOFF_FACTOR,
                                 status_forcelist=[500, 502, 503, 504])
    session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
    return session


def is_url_newer(url: str, fname: str) -> bool:
    if not os.path.exists(fname):
        return True
    if '--no-check-last-modified' not in sys.argv[1:]:
        session = get_http_session()
        resp = session.head(url, timeout=CONNECT_TIMEOUT)
        resp.raise_for_status()
        remote_url_dt = dateutil.parser.parse(resp.headers['Last-Modified']).astimezone()
        local_file_dt = datetime.datetime.fromtimestamp(os.path.getmtime(fname)).astimezone()
        return remote_url_dt > local_file_dt
    return False


def do_retrieve(url: str, fname: str) -> None:
    """Retrieve given url to target filepath fname."""
    folder = os.path.dirname(fname)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)
    if not is_url_newer(url, fname):
        return
    session = get_http_session()
    resp = session.get(url, timeout=CONNECT_TIMEOUT)
    resp.raise_for_status()
    print(f"saving {fname}: ", end='', flush=True)
    with open(fname, 'wb') as fout:
        for chunk in resp.iter_content(FETCH_BLOCKSIZE):
            fout.write(chunk)
    print('ok')


def main() -> None:
    """Update east-asian, combining and zero width tables."""
    if "--debug" in sys.argv[1:]:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.WARNING
    logging.basicConfig(stream=sys.stderr, level=loglevel)

    # This defines which jinja source templates map to which output filenames,
    # and what function defines the source data. We hope to add more source
    # language options using jinja2 templates, with minimal modification of the
    # code.
    def get_codegen_definitions() -> Iterator[RenderDefinition]:
        yield UnicodeVersionPyRenderDef.new(
            UnicodeVersionPyRenderCtx(fetch_unicode_versions())
        )
        yield UnicodeVersionRstRenderDef.new(fetch_source_headers())
        yield UnicodeTableRenderDef.new('table_wide.py', fetch_table_wide_data())
        yield UnicodeTableRenderDef.new('table_zero.py', fetch_table_zero_data())
        yield UnicodeSequenceRenderDef.new('emoji_zwj_sequences.py', fetch_emoji_zero_data())

    for render_def in get_codegen_definitions():
        with open(render_def.output_filename, 'w', encoding='utf-8', newline='\n') as fout:
            print(f'write {render_def.output_filename}: ', flush=True, end='')
            for data in render_def.generate():
                fout.write(data)
            print('ok')

if __name__ == '__main__':
    main()


# TODO https://unicode.org/L2/L2002/02368-default-ignorable.html, parse??
