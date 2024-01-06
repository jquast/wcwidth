#!/usr/bin/env python
"""
Update the Unicode code tables for wcwidth.  This is code generation using jinja2.

This is typically executed through tox,

$ tox -e update

https://github.com/jquast/wcwidth
"""
from __future__ import annotations

# std imports
import os
import re
import sys
import string
import datetime
import functools
import unicodedata
from pathlib import Path
from dataclasses import field, fields, dataclass

from typing import Any, Mapping, Iterable, Iterator, Sequence, Container, Collection

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self

# 3rd party
import jinja2
import requests
import urllib3.util
import dateutil.parser

EXCLUDE_VERSIONS = ['2.0.0', '2.1.2', '3.0.0', '3.1.0', '3.2.0', '4.0.0']

PATH_UP = os.path.relpath(os.path.join(os.path.dirname(__file__), os.path.pardir))
PATH_DATA = os.path.join(PATH_UP, 'data')
PATH_TESTS = os.path.join(PATH_UP, 'tests')
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

# Hangul Jamo is a decomposed form of Hangul Syllables, see
# see https://www.unicode.org/faq/korean.html#3
#     https://github.com/ridiculousfish/widecharwidth/pull/17
#     https://github.com/jquast/ucs-detect/issues/9
#     https://devblogs.microsoft.com/oldnewthing/20201009-00/?p=104351
# "Conjoining Jamo are divided into three classes: L, V, T (Leading
#  consonant, Vowel, Trailing consonant). A Hangul Syllable consists of
#  <LV> or <LVT> sequences."
HANGUL_JAMO_ZEROWIDTH = (
    *range(0x1160, 0x1200),  # Hangul Jungseong Filler .. Hangul Jongseong Ssangnieun
    *range(0xD7B0, 0xD800),  # Hangul Jungseong O-Yeo  .. Undefined Character of Hangul Jamo Extended-B
)


def _bisearch(ucs, table):
    """A copy of wcwwidth._bisearch, to prevent having issues when depending on code that imports
    our generated code."""
    lbound = 0
    ubound = len(table) - 1

    if ucs < table[0][0] or ucs > table[ubound][1]:
        return 0
    while ubound >= lbound:
        mid = (lbound + ubound) // 2
        if ucs > table[mid][1]:
            lbound = mid + 1
        elif ucs < table[mid][0]:
            ubound = mid - 1
        else:
            return 1

    return 0


@dataclass(order=True, frozen=True)
class UnicodeVersion:
    """A class for camparable unicode version."""
    major: int
    minor: int
    micro: int | None

    @classmethod
    def parse(cls, version_str: str) -> UnicodeVersion:
        """
        Parse a version string.

        >>> UnicodeVersion.parse("14.0.0")
        UnicodeVersion(major=14, minor=0, micro=0)
        """
        ver_ints = tuple(map(int, version_str.split(".")[:3]))
        return cls(major=ver_ints[0], minor=ver_ints[1],
                   micro=ver_ints[2] if len(ver_ints) > 2 else None)

    def __str__(self) -> str:
        """
        >>> str(UnicodeVersion(12, 1, 0))
        '12.1.0'
        """
        maybe_micro = ''
        if self.micro is not None:
            maybe_micro = f'.{self.micro}'
        return f'{self.major}.{self.minor}{maybe_micro}'


@dataclass(frozen=True)
class TableEntry:
    """An entry of a unicode table."""
    code_range: tuple[int, int] | None
    properties: tuple[str, ...]
    comment: str

    def filter_by_category_width(self, wide: int) -> bool:
        """
        Return whether entry matches displayed width.

        Parses both DerivedGeneralCategory.txt and EastAsianWidth.txt
        """
        if self.code_range is None:
            return False
        elif self.properties[0] == 'Sk':
            if 'EMOJI MODIFIER' in self.comment:
                # These codepoints are fullwidth when used without emoji, 0-width with.
                # Generate code that expects the best case, that is always combined
                return wide == 0
            elif 'FULLWIDTH' in self.comment:
                # Some codepoints in 'Sk' categories are fullwidth(!)
                # at this time just 3, FULLWIDTH: CIRCUMFLEX ACCENT, GRAVE ACCENT, and MACRON
                return wide == 2
            else:
                # the rest are narrow
                return wide == 1
        # Me Enclosing Mark
        # Mn Nonspacing Mark
        # Cf Format
        # Zl Line Separator
        # Zp Paragraph Separator
        if self.properties[0] in ('Me', 'Mn', 'Mc', 'Cf', 'Zl', 'Zp'):
            return wide == 0
        # F  Fullwidth
        # W  Wide
        if self.properties[0] in ('W', 'F'):
            return wide == 2
        return wide == 1

    @staticmethod
    def parse_width_category_values(table_iter: Iterator[TableEntry],
                                    wide: int) -> set[tuple[int, int]]:
        """Parse value ranges of unicode data files, by given category and width."""
        return {n
                for entry in table_iter
                if entry.filter_by_category_width(wide)
                for n in list(range(entry.code_range[0], entry.code_range[1]))}


@dataclass
class TableDef:
    filename: str
    date: str
    values: set[int]

    def as_value_ranges(self) -> list[tuple[int, int]]:
        """Return a list of tuple of (start, end) ranges for given set of 'values'."""
        table: list[tuple[int, int]] = []
        values_iter = iter(sorted(self.values))
        start = end = next(values_iter)
        table.append((start, end))

        for value in values_iter:
            # remove last-most entry for comparison,
            start, end = table.pop()
            if end == value - 1:
                # continuation of existing range, rewrite
                table.append((start, value,))
            else:
                # non-continuation: insert back previous range,
                table.append((start, end,))
                # and start a new one
                table.append((value, value,))
        return table

    @property
    def hex_range_descriptions(self) -> list[tuple[str, str, str]]:
        """Convert integers into string table of (hex_start, hex_end, txt_description)."""
        pytable_values: list[tuple[str, str, str]] = []
        for start, end in self.as_value_ranges():
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
        """Just like jinja2.Template.render."""
        return self._template.render(self._render_context)

    def generate(self) -> Iterator[str]:
        """Just like jinja2.Template.generate."""
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


@functools.cache
def fetch_unicode_versions() -> list[UnicodeVersion]:
    """Fetch, determine, and return Unicode Versions for processing."""
    pattern = re.compile(r'#.*assigned in Unicode ([0-9.]+)')
    versions: list[UnicodeVersion] = []
    with open(UnicodeDataFile.DerivedAge(), encoding='utf-8') as f:
        for line in f:
            if match := re.match(pattern, line):
                version = match.group(1)
                if version not in EXCLUDE_VERSIONS:
                    versions.append(UnicodeVersion.parse(version))
    versions.sort()
    return versions


def fetch_source_headers() -> UnicodeVersionRstRenderCtx:
    headers: list[tuple[str, str]] = []
    for filename in UnicodeDataFile.filenames():
        header_description = cite_source_description(filename)
        headers.append(header_description)
    return UnicodeVersionRstRenderCtx(headers)


def fetch_table_wide_data() -> UnicodeTableRenderCtx:
    """Fetch east-asian tables."""
    table: dict[UnicodeVersion, TableDef] = {}
    for version in fetch_unicode_versions():
        # parse typical 'wide' characters by categories 'W' and 'F',
        table[version] = parse_category(fname=UnicodeDataFile.EastAsianWidth(version),
                                        wide=2)

        # subtract(!) wide characters that were defined above as 'W' category in EastAsianWidth,
        # but also zero-width category 'Mn' or 'Mc' in DerivedGeneralCategory!
        table[version].values = table[version].values.difference(parse_category(
            fname=UnicodeDataFile.DerivedGeneralCategory(version),
            wide=0).values)

        # Also subtract Hangul Jamo Vowels and Hangul Trailing Consonants
        table[version].values = table[version].values.difference(HANGUL_JAMO_ZEROWIDTH)

        # finally, join with atypical 'wide' characters defined by category 'Sk',
        table[version].values.update(parse_category(fname=UnicodeDataFile.DerivedGeneralCategory(version),
                                                    wide=2).values)
    return UnicodeTableRenderCtx('WIDE_EASTASIAN', table)


def fetch_table_zero_data() -> UnicodeTableRenderCtx:
    """
    Fetch zero width tables.

    See also: https://unicode.org/L2/L2002/02368-default-ignorable.html
    """
    table: dict[UnicodeVersion, TableDef] = {}
    for version in fetch_unicode_versions():
        # Determine values of zero-width character lookup table by the following category codes
        table[version] = parse_category(fname=UnicodeDataFile.DerivedGeneralCategory(version),
                                        wide=0)

        # Include NULL
        table[version].values.add(0)

        # Add Hangul Jamo Vowels and Hangul Trailing Consonants
        table[version].values.update(HANGUL_JAMO_ZEROWIDTH)
    return UnicodeTableRenderCtx('ZERO_WIDTH', table)


def fetch_table_vs16_data() -> UnicodeTableRenderCtx:
    """
    Fetch and create a "narrow to wide variation-16" lookup table.

    Characters in this table are all narrow, but when combined with a variation
    selector-16 (\uFE0F), they become wide, for the given versions of unicode.

    UNICODE_VERSION=9.0.0 or greater is required to enable detection of the effect
    of *any* 'variation selector-16' narrow emoji becoming wide. Just two total
    files are parsed to create ONE unicode version table supporting all
    Unicode versions 9.0.0 and later.

    Because of the ambiguity of versions in these early emoji data files, which
    match unicode releases 8, 9, and 10, these specifications were mostly
    implemented only in Terminals supporting Unicode 9.0 or later.

    For that reason, and that these values are not expected to change,
    only this single shared table is exported.


    One example, where v3.2 became v1.1 ("-" 12.0, "+" 15.1)::

         -2620 FE0F  ; Basic_Emoji  ; skull and crossbones        #  3.2  [1] (☠️)
         +2620 FE0F  ; emoji style; # (1.1) SKULL AND CROSSBONES

    Or another discrepancy, published in unicode 12.0 as emoji version 5.2, but
    missing entirely in the emoji-variation-sequences.txt published with unicode
    version 15.1::

        26F3 FE0E  ; text style;  # (5.2) FLAG IN HOLE

    while some terminals display \\u0036\\uFE0F as a wide number one (kitty),
    others display as ascii 1 with a no-effect zero-width (iTerm2) and others
    have a strange narrow font corruption, I think it is fair to call these
    ambiguous, no doubt in part because of these issues, see related
    'ucs-detect' project.

    Note that version 3.2 became 1.1, which would change unicode release of 9.0
    to version 8.0.
    """
    table: dict[UnicodeVersion, TableDef] = {}
    unicode_latest = fetch_unicode_versions()[-1]

    wide_tables = fetch_table_wide_data().table
    unicode_version = UnicodeVersion.parse('9.0.0')

    # parse table formatted by the latest emoji release (developed with
    # 15.1.0) and parse a single file for all individual releases
    table[unicode_version] = parse_vs16_data(fname=UnicodeDataFile.EmojiVariationSequences(unicode_latest),
                                             ubound_unicode_version=unicode_version)

    # parse and join the final emoji release 12.0 of the earlier "type"
    table[unicode_version].values.update(
        parse_vs16_data(fname=UnicodeDataFile.LegacyEmojiVariationSequences(),
                        ubound_unicode_version=unicode_version).values)

    # perform culling on any values that are already understood as 'wide'
    # without the variation-16 selector
    wide_table = wide_tables[unicode_version].as_value_ranges()
    table[unicode_version].values = {
        ucs for ucs in table[unicode_version].values
        if not _bisearch(ucs, wide_table)
    }

    return UnicodeTableRenderCtx('VS16_NARROW_TO_WIDE', table)


def parse_vs16_data(fname: str, ubound_unicode_version: UnicodeVersion):
    with open(fname, encoding='utf-8') as fin:
        table_iter = parse_vs16_table(fin)
        # pull "date string"
        date = next(table_iter).comment.split(':', 1)[1].strip()
        # pull values only matching this unicode version and lower
        values = {entry.code_range[0] for entry in table_iter}
    return TableDef(ubound_unicode_version, date, values)


def cite_source_description(filename: str) -> tuple[str, str]:
    """Return unicode.org source data file's own description as citation."""
    with open(filename, encoding='utf-8') as f:
        entry_iter = parse_unicode_table(f)
        fname = next(entry_iter).comment.strip()
        # use local name w/version in place of 'emoji-variation-sequences.txt'
        if fname == 'emoji-variation-sequences.txt':
            fname = os.path.basename(filename)
        date = next(entry_iter).comment.strip()

    return fname, date


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


def parse_vs16_table(fp: Iterable[str]) -> Iterator[TableEntry]:
    """Parse emoji-variation-sequences.txt for codepoints that preceed 0xFE0F."""
    hex_str_vs16 = 'FE0F'
    for line in fp:
        data, _, comment = line.partition('#')
        data_fields: Iterator[str] = (field.strip() for field in data.split(';'))
        code_points_str, *properties = data_fields

        if not code_points_str:
            if 'Date' in comment:
                # yield 'Data'
                yield TableEntry(None, tuple(properties), comment)
            continue
        code_points = code_points_str.split()
        if len(code_points) == 2 and code_points[1] == hex_str_vs16:
            # yeild a single "code range" entry for a single value that preceeds FE0F
            yield TableEntry((int(code_points[0], 16), int(code_points[0], 16)), tuple(properties), comment)


@functools.cache
def parse_category(fname: str, wide: int) -> TableDef:
    """Parse value ranges of unicode data files, by given categories into string tables."""
    print(f'parsing {fname}, wide={wide}: ', end='', flush=True)

    with open(fname, encoding='utf-8') as f:
        table_iter = parse_unicode_table(f)

        # pull "version string" from first line of source file
        version = next(table_iter).comment.strip()
        # and "date string" from second line
        date = next(table_iter).comment.split(':', 1)[1].strip()
        values = TableEntry.parse_width_category_values(table_iter, wide)
    print('ok')
    return TableDef(version, date, values)


class UnicodeDataFile:
    """
    Helper class for fetching Unicode Data Files.

    Methods like 'DerivedAge' return a local filename, but have the side-effect of fetching those
    files from unicode.org first, if not existing or out-of-date.

    Because file modification times are used, for local files of TestEmojiZWJSequences and
    TestEmojiVariationSequences, these files should be forcefully re-fetched CLI argument '--no-
    check-last-modified'.
    """
    URL_DERIVED_AGE = 'https://www.unicode.org/Public/UCD/latest/ucd/DerivedAge.txt'
    URL_EASTASIAN_WIDTH = 'https://www.unicode.org/Public/{version}/ucd/EastAsianWidth.txt'
    URL_DERIVED_CATEGORY = 'https://www.unicode.org/Public/{version}/ucd/extracted/DerivedGeneralCategory.txt'
    URL_EMOJI_VARIATION = 'https://unicode.org/Public/{version}/ucd/emoji/emoji-variation-sequences.txt'
    URL_LEGACY_VARIATION = 'https://unicode.org/Public/emoji/{version}/emoji-variation-sequences.txt'
    URL_EMOJI_ZWJ = 'https://unicode.org/Public/emoji/{version}/emoji-zwj-sequences.txt'

    @classmethod
    def DerivedAge(cls) -> str:
        fname = os.path.join(PATH_DATA, 'DerivedAge.txt')
        cls.do_retrieve(url=cls.URL_DERIVED_AGE, fname=fname)
        return fname

    @classmethod
    def EastAsianWidth(cls, version: str) -> str:
        fname = os.path.join(PATH_DATA, f'EastAsianWidth-{version}.txt')
        cls.do_retrieve(url=cls.URL_EASTASIAN_WIDTH.format(version=version), fname=fname)
        return fname

    @classmethod
    def DerivedGeneralCategory(cls, version: str) -> str:
        fname = os.path.join(PATH_DATA, f'DerivedGeneralCategory-{version}.txt')
        cls.do_retrieve(url=cls.URL_DERIVED_CATEGORY.format(version=version), fname=fname)
        return fname

    @classmethod
    def EmojiVariationSequences(cls, version: str) -> str:
        fname = os.path.join(PATH_DATA, f'emoji-variation-sequences-{version}.txt')
        cls.do_retrieve(url=cls.URL_EMOJI_VARIATION.format(version=version), fname=fname)
        return fname

    @classmethod
    def LegacyEmojiVariationSequences(cls) -> str:
        version = "12.0"
        fname = os.path.join(PATH_DATA, f'emoji-variation-sequences-{version}.0.txt')
        cls.do_retrieve(url=cls.URL_LEGACY_VARIATION.format(version=version), fname=fname)
        return fname

    @classmethod
    def TestEmojiVariationSequences(cls) -> str:
        version = fetch_unicode_versions()[-1]
        fname = os.path.join(PATH_TESTS, 'emoji-variation-sequences.txt')
        cls.do_retrieve(url=cls.URL_EMOJI_VARIATION.format(version=version), fname=fname)
        return fname

    @classmethod
    def TestEmojiZWJSequences(cls) -> str:
        version = fetch_unicode_versions()[-1]
        fname = os.path.join(PATH_TESTS, 'emoji-zwj-sequences.txt')
        cls.do_retrieve(url=cls.URL_EMOJI_ZWJ.format(version=f"{version.major}.{version.minor}"), fname=fname)
        return fname

    @staticmethod
    def do_retrieve(url: str, fname: str) -> None:
        """Retrieve given url to target filepath fname."""
        folder = os.path.dirname(fname)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        if not UnicodeDataFile.is_url_newer(url, fname):
            return
        session = UnicodeDataFile.get_http_session()
        resp = session.get(url, timeout=CONNECT_TIMEOUT)
        resp.raise_for_status()
        print(f"saving {fname}: ", end='', flush=True)
        with open(fname, 'wb') as fout:
            for chunk in resp.iter_content(FETCH_BLOCKSIZE):
                fout.write(chunk)
        print('ok')

    @staticmethod
    def is_url_newer(url: str, fname: str) -> bool:
        if not os.path.exists(fname):
            return True
        if '--no-check-last-modified' not in sys.argv[1:]:
            session = UnicodeDataFile.get_http_session()
            resp = session.head(url, timeout=CONNECT_TIMEOUT)
            resp.raise_for_status()
            remote_url_dt = dateutil.parser.parse(resp.headers['Last-Modified']).astimezone()
            local_file_dt = datetime.datetime.fromtimestamp(os.path.getmtime(fname)).astimezone()
            return remote_url_dt > local_file_dt
        return False

    @functools.cache
    def get_http_session() -> requests.Session:
        session = requests.Session()
        retries = urllib3.util.Retry(total=MAX_RETRIES,
                                     backoff_factor=BACKOFF_FACTOR,
                                     status_forcelist=[500, 502, 503, 504])
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
        return session

    @staticmethod
    def filenames() -> list[str]:
        """Return list of UnicodeData files stored in PATH_DATA, sorted by version number."""
        pattern = re.compile(
            r'^(emoji-variation-sequences|DerivedGeneralCategory|EastAsianWidth)-(\d+)\.(\d+)\.(\d+).txt$')
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
        return [os.path.join(PATH_DATA, match.string) for match in filename_matches]


def main() -> None:
    """Update east-asian, combining and zero width tables."""
    # This defines which jinja source templates map to which output filenames,
    # and what function defines the source data. We hope to add more source
    # language options using jinja2 templates, with minimal modification of the
    # code.
    def get_codegen_definitions() -> Iterator[RenderDefinition]:
        yield UnicodeVersionPyRenderDef.new(
            UnicodeVersionPyRenderCtx(fetch_unicode_versions())
        )
        yield UnicodeTableRenderDef.new('table_vs16.py', fetch_table_vs16_data())
        yield UnicodeTableRenderDef.new('table_wide.py', fetch_table_wide_data())
        yield UnicodeTableRenderDef.new('table_zero.py', fetch_table_zero_data())
        yield UnicodeVersionRstRenderDef.new(fetch_source_headers())

    for render_def in get_codegen_definitions():
        with open(render_def.output_filename, 'w', encoding='utf-8', newline='\n') as fout:
            print(f'write {render_def.output_filename}: ', flush=True, end='')
            for data in render_def.generate():
                fout.write(data)
            print('ok')

    # fetch latest test data files
    UnicodeDataFile.TestEmojiVariationSequences()
    UnicodeDataFile.TestEmojiZWJSequences()


if __name__ == '__main__':
    main()
