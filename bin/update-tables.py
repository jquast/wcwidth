#!/usr/bin/env python
"""
Update the Unicode code tables for wcwidth.  This is code generation using jinja2.

This is typically executed through tox,

$ tox -e update

https://github.com/jquast/wcwidth
"""
from __future__ import annotations

# std imports
import io
import os
import re
import string
import difflib
import zipfile
import argparse
import datetime
import functools
import unicodedata
from pathlib import Path
from dataclasses import field, fields, dataclass

from typing import Any, Mapping, Iterable, Iterator, Sequence, Collection

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
READ_TIMEOUT = int(os.environ.get('READ_TIMEOUT', '30'))
FETCH_BLOCKSIZE = int(os.environ.get('FETCH_BLOCKSIZE', '4096'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '10'))
BACKOFF_FACTOR = float(os.environ.get('BACKOFF_FACTOR', '1.0'))

# Global flag set by main() from --check-last-modified CLI argument.
# When True, perform HTTP HEAD requests to check if remote files are newer.
# Default is False because Unicode data files rarely change once published.
CHECK_LAST_MODIFIED = False

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

HEX_STR_VS16 = 'FE0F'
# Grapheme Break Property values from UAX #29
GRAPHEME_BREAK_PROPERTIES = (
    'CR', 'LF', 'Control', 'Extend', 'ZWJ', 'Regional_Indicator',
    'Prepend', 'SpacingMark', 'L', 'V', 'T', 'LV', 'LVT'
)
INCB_VALUES = ('Linker', 'Consonant', 'Extend')


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
    """A class for comparable unicode version."""
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
                # Standalone Fitzpatrick modifiers display as wide (2 cells).
                # Zero-width when following an emoji base is handled contextually
                # in wcswidth() and width().
                return wide == 2
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


@dataclass(frozen=True)
class GraphemeTableRenderCtx(RenderContext):
    """Render context for grapheme tables (latest version only)."""
    unicode_version: str
    tables: Mapping[str, TableDef]


@dataclass
class GraphemeTableRenderDef(RenderDefinition):
    render_context: GraphemeTableRenderCtx

    @classmethod
    def new(cls, context: GraphemeTableRenderCtx) -> Self:
        return cls(
            jinja_filename='grapheme_table.py.j2',
            output_filename=os.path.join(PATH_UP, 'wcwidth', 'table_grapheme.py'),
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
    """Fetch east-asian tables for the latest Unicode version only."""
    table: dict[UnicodeVersion, TableDef] = {}
    version = fetch_unicode_versions()[-1]  # Only latest version

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

    # Subtract Default_Ignorable_Code_Point characters (they should be zero-width).
    # Exception: U+115F HANGUL CHOSEONG FILLER remains wide for jamo composition.
    # See https://github.com/jquast/wcwidth/issues/118
    default_ignorable = parse_derived_core_property(
        fname=UnicodeDataFile.DerivedCoreProperties(version),
        property_name='Default_Ignorable_Code_Point')
    default_ignorable.discard(0x115F)  # Keep HANGUL CHOSEONG FILLER as wide
    table[version].values = table[version].values.difference(default_ignorable)

    # finally, join with atypical 'wide' characters defined by category 'Sk',
    fname = UnicodeDataFile.DerivedGeneralCategory(version)
    table[version].values.update(parse_category(fname=fname, wide=2).values)

    # Add Regional Indicator symbols (U+1F1E6..U+1F1FF). Though classified as
    # Neutral in EastAsianWidth.txt, terminals universally render these as
    # double-width. Pairing (flag emoji) is handled contextually in wcswidth()
    # and width().
    table[version].values.update(range(0x1F1E6, 0x1F1FF + 1))

    return UnicodeTableRenderCtx('WIDE_EASTASIAN', table)


def fetch_table_zero_data() -> UnicodeTableRenderCtx:
    """
    Fetch zero width tables for the latest Unicode version only.

    See also: https://unicode.org/L2/L2002/02368-default-ignorable.html
    """
    table: dict[UnicodeVersion, TableDef] = {}
    version = fetch_unicode_versions()[-1]  # Only latest version

    # Determine values of zero-width character lookup table by the following category codes
    fname = UnicodeDataFile.DerivedGeneralCategory(version)
    table[version] = parse_category(fname=fname, wide=0)

    # Include NULL
    table[version].values.add(0)

    # Add Hangul Jamo Vowels and Hangul Trailing Consonants
    table[version].values.update(HANGUL_JAMO_ZEROWIDTH)

    # Add Default_Ignorable_Code_Point characters
    # Per Unicode Standard (https://www.unicode.org/faq/unsup_char.html):
    # "All default-ignorable characters should be rendered as completely invisible
    # (and non advancing, i.e. 'zero width'), if not explicitly supported in rendering."
    #
    # See also:
    # - https://www.unicode.org/reports/tr44/#Default_Ignorable_Code_Point
    # - https://github.com/jquast/wcwidth/issues/118
    table[version].values.update(parse_derived_core_property(
        fname=UnicodeDataFile.DerivedCoreProperties(version),
        property_name='Default_Ignorable_Code_Point'))

    # Remove U+115F HANGUL CHOSEONG FILLER from zero-width table.
    # Although it has Default_Ignorable_Code_Point property, it should remain
    # width 2 because it combines with other Hangul Jamo to form width-2
    # syllable blocks.
    table[version].values.discard(0x115F)

    # Remove u+00AD categoryCode=Cf name="SOFT HYPHEN",
    # > https://www.unicode.org/faq/casemap_charprop.html
    #
    # > Q: Unicode now treats the SOFT HYPHEN as format control (Cf)
    # > character when formerly it was a punctuation character (Pd).
    # > Doesn't this break ISO 8859-1 compatibility?
    #
    # > [..] In a terminal emulation environment, particularly in
    # > ISO-8859-1 contexts, one could display the SOFT HYPHEN as a hyphen
    # > in all circumstances.
    #
    # This value was wrongly measured as a width of '0' in this wcwidth
    # versions 0.2.9 - 0.2.13. Fixed in 0.2.14
    table[version].values.discard(0x00AD)  # SOFT HYPHEN

    # Remove Prepended_Concatenation_Mark characters from zero-width.
    # Per Unicode Standard Annex #44, these format characters (General_Category=Cf) have
    # mandatory visible display and should NOT be treated as invisible.
    # See https://github.com/jquast/wcwidth/issues/119
    table[version].values = table[version].values.difference(
        parse_derived_core_property(
            fname=UnicodeDataFile.PropList(version),
            property_name='Prepended_Concatenation_Mark'))

    # Remove Emoji Modifier Fitzpatrick types (U+1F3FB..U+1F3FF) from zero-width.
    # Standalone they display as wide (2 cells); they are only zero-width when
    # following an emoji base character in sequence, handled contextually in
    # wcswidth() and width().
    table[version].values -= set(range(0x1F3FB, 0x1F3FF + 1))

    return UnicodeTableRenderCtx('ZERO_WIDTH', table)


def fetch_table_category_mc_data() -> UnicodeTableRenderCtx:
    """
    Fetch Spacing Combining Mark (Mc) character table for the latest Unicode version.

    Characters with General_Category=Mc are combining marks that typically occupy a cell width when
    following a base character, but should be zero-width when standalone. This table is used for
    context-aware width measurement.
    """
    table: dict[UnicodeVersion, TableDef] = {}
    version = fetch_unicode_versions()[-1]

    fname = UnicodeDataFile.DerivedGeneralCategory(version)
    print(f'parsing {fname}, category=Mc: ', end='', flush=True)

    with open(fname, encoding='utf-8') as f:
        table_iter = parse_unicode_table(f)
        file_version = next(table_iter).comment.strip()
        date = next(table_iter).comment.split(':', 1)[1].strip()
        values = {n
                  for entry in table_iter
                  if entry.code_range is not None and entry.properties[0] == 'Mc'
                  for n in range(entry.code_range[0], entry.code_range[1])}
    print('ok')
    table[version] = TableDef(file_version, date, values)
    return UnicodeTableRenderCtx('CATEGORY_MC', table)


def fetch_table_ambiguous_data() -> UnicodeTableRenderCtx:
    """
    Fetch east-asian ambiguous character table for the latest Unicode version.

    East Asian Ambiguous (A) characters can display as either 1 cell (narrow) or 2 cells (wide)
    depending on the terminal's configuration. This table allows users to opt-in to treating these
    characters as wide by passing ambiguous_width=2 to wcwidth/wcswidth.
    """
    table: dict[UnicodeVersion, TableDef] = {}
    version = fetch_unicode_versions()[-1]
    # parse 'ambiguous' characters by category 'A'
    table[version] = parse_category_ambiguous(
        fname=UnicodeDataFile.EastAsianWidth(version)
    )
    # Subtract zero-width characters (they should remain zero-width
    # regardless of ambiguous_width setting)
    table[version].values = table[version].values.difference(
        parse_category(
            fname=UnicodeDataFile.DerivedGeneralCategory(version),
            wide=0
        ).values
    )
    return UnicodeTableRenderCtx('AMBIGUOUS_EASTASIAN', table)


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

    For that reason, and that **these values are not expected to change**,
    If they do, a noticeable change would occur in `wcwidth/table_vs16.py`
    falsely labeled under version 9.0 but is prevented by assertion.

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
    table[unicode_version] = parse_vs_data(fname=UnicodeDataFile.EmojiVariationSequences(unicode_latest),
                                           ubound_unicode_version=unicode_version,
                                           hex_str_vs=HEX_STR_VS16)

    # parse and join the final emoji release 12.0 of the earlier "type"
    table[unicode_version].values.update(
        parse_vs_data(fname=UnicodeDataFile.LegacyEmojiVariationSequences(),
                      ubound_unicode_version=unicode_version,
                      hex_str_vs=HEX_STR_VS16).values)

    # perform culling on any values that are already understood as 'wide'
    # without the variation-16 selector (use latest wide table)
    wide_table = wide_tables[unicode_latest].as_value_ranges()
    table[unicode_version].values = {
        ucs for ucs in table[unicode_version].values
        if not _bisearch(ucs, wide_table)
    }

    return UnicodeTableRenderCtx('VS16_NARROW_TO_WIDE', table)


def parse_vs_data(fname: str, ubound_unicode_version: UnicodeVersion, hex_str_vs: str):
    with open(fname, encoding='utf-8') as fin:
        table_iter = parse_vs_table(fin, hex_str_vs)
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


def parse_vs_table(fp: Iterable[str], hex_str_vs: str = 'FE0F') -> Iterator[TableEntry]:
    """Parse emoji-variation-sequences.txt for codepoints that precede `hex_str_vs`."""
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
        if len(code_points) == 2 and code_points[1] == hex_str_vs:
            # yield a single "code range" entry for a single value that precedes hex_str_vs
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


@functools.cache
def parse_category_ambiguous(fname: str) -> TableDef:
    """Parse EastAsianWidth.txt for 'A' (Ambiguous) category."""
    print(f'parsing {fname}, category=A: ', end='', flush=True)

    with open(fname, encoding='utf-8') as f:
        table_iter = parse_unicode_table(f)

        # pull "version string" from first line of source file
        version = next(table_iter).comment.strip()
        # and "date string" from second line
        date = next(table_iter).comment.split(':', 1)[1].strip()
        values = {
            n
            for entry in table_iter
            if entry.code_range is not None and entry.properties[0] == 'A'
            for n in range(entry.code_range[0], entry.code_range[1])
        }
    print('ok')
    return TableDef(version, date, values)


def parse_grapheme_break_properties(fname: str) -> dict[str, TableDef]:
    """Parse GraphemeBreakProperty.txt for grapheme break properties needing tables."""
    print(f'parsing {fname}: ', end='', flush=True)
    values_by_prop: dict[str, set[int]] = {prop: set() for prop in GRAPHEME_BREAK_PROPERTIES}

    with open(fname, encoding='utf-8') as f:
        table_iter = parse_unicode_table(f)
        version = next(table_iter).comment.strip()
        date = next(table_iter).comment.split(':', 1)[1].strip()

        for entry in table_iter:
            if entry.code_range is None:
                continue
            if entry.properties and entry.properties[0] in values_by_prop:
                values_by_prop[entry.properties[0]].update(
                    range(entry.code_range[0], entry.code_range[1])
                )

    print('ok')
    return {
        f'GRAPHEME_{prop.upper()}': TableDef(version, date, values)
        for prop, values in values_by_prop.items()
    }


def parse_extended_pictographic(fname: str) -> TableDef:
    """Parse emoji-data.txt for Extended_Pictographic property."""
    print(f'parsing {fname} for Extended_Pictographic: ', end='', flush=True)
    values: set[int] = set()

    with open(fname, encoding='utf-8') as f:
        table_iter = parse_unicode_table(f)
        # pull "version string" from first line of source file
        version = next(table_iter).comment.strip()
        # and "date string" from second line
        date = next(table_iter).comment.split(':', 1)[1].strip()

        for entry in table_iter:
            if entry.code_range is None:
                continue
            if entry.properties and entry.properties[0] == 'Extended_Pictographic':
                values.update(range(entry.code_range[0], entry.code_range[1]))

    print('ok')
    return TableDef(version, date, values)


def parse_indic_conjunct_breaks(fname: str) -> dict[str, TableDef]:
    """Parse DerivedCoreProperties.txt for all Indic_Conjunct_Break properties."""
    print(f'parsing {fname} for InCB: ', end='', flush=True)
    values_by_incb: dict[str, set[int]] = {val: set() for val in INCB_VALUES}

    with open(fname, encoding='utf-8') as f:
        for line in f:
            data, _, comment = line.partition('#')
            data = data.strip()
            if not data:
                continue

            parts = [p.strip() for p in data.split(';')]
            if len(parts) < 3:
                continue

            code_points_str, prop_name, prop_value = parts[0], parts[1], parts[2]

            if prop_name == 'InCB' and prop_value in values_by_incb:
                if '..' in code_points_str:
                    start, end = code_points_str.split('..')
                    values_by_incb[prop_value].update(
                        range(int(start, 16), int(end, 16) + 1)
                    )
                else:
                    values_by_incb[prop_value].add(int(code_points_str, 16))

    print('ok')
    return {
        f'INCB_{val.upper()}': TableDef('DerivedCoreProperties', 'see file', values)
        for val, values in values_by_incb.items()
    }


ISC_VALUES = ('Consonant',)


def parse_indic_syllabic_category(fname: str) -> dict[str, TableDef]:
    """
    Parse IndicSyllabicCategory.txt for Consonant property.

    See https://www.unicode.org/reports/tr44/#Indic_Syllabic_Category
    """
    print(f'parsing {fname} for ISC: ', end='', flush=True)
    values_by_isc: dict[str, set[int]] = {val: set() for val in ISC_VALUES}

    with open(fname, encoding='utf-8') as f:
        for line in f:
            data, _, comment = line.partition('#')
            data = data.strip()
            if not data:
                continue

            parts = [p.strip() for p in data.split(';')]
            if len(parts) < 2:
                continue

            code_points_str, prop_value = parts[0], parts[1]

            if prop_value in values_by_isc:
                if '..' in code_points_str:
                    start, end = code_points_str.split('..')
                    values_by_isc[prop_value].update(
                        range(int(start, 16), int(end, 16) + 1)
                    )
                else:
                    values_by_isc[prop_value].add(int(code_points_str, 16))

    print('ok')
    return {
        f'ISC_{val.upper()}': TableDef('IndicSyllabicCategory', 'see file', values)
        for val, values in values_by_isc.items()
    }


def parse_derived_core_property(fname: str, property_name: str) -> set[int]:
    """Parse DerivedCoreProperties.txt for a specific property."""
    print(f'parsing {fname} for {property_name}: ', end='', flush=True)
    values: set[int] = set()

    with open(fname, encoding='utf-8') as f:
        for line in f:
            data, _, comment = line.partition('#')
            data = data.strip()
            if not data:
                continue

            parts = [p.strip() for p in data.split(';')]
            if len(parts) < 2:
                continue

            code_points_str, prop_name = parts[0], parts[1]

            if prop_name == property_name:
                if '..' in code_points_str:
                    start, end = code_points_str.split('..')
                    values.update(range(int(start, 16), int(end, 16) + 1))
                else:
                    values.add(int(code_points_str, 16))

    print('ok')
    return values


def fetch_table_grapheme_data() -> GraphemeTableRenderCtx:
    """Fetch grapheme break property tables for the latest Unicode version only."""
    latest_version = fetch_unicode_versions()[-1]

    # makes a table definition for each break property
    tables = parse_grapheme_break_properties(
        UnicodeDataFile.GraphemeBreakProperty(latest_version)
    )
    tables['EXTENDED_PICTOGRAPHIC'] = parse_extended_pictographic(
        UnicodeDataFile.EmojiData(latest_version)
    )
    tables.update(parse_indic_conjunct_breaks(
        UnicodeDataFile.DerivedCoreProperties(latest_version)
    ))
    tables.update(parse_indic_syllabic_category(
        UnicodeDataFile.IndicSyllabicCategory(latest_version)
    ))

    return GraphemeTableRenderCtx(str(latest_version), tables)


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
    URL_GRAPHEME_BREAK = 'https://www.unicode.org/Public/{version}/ucd/auxiliary/GraphemeBreakProperty.txt'
    URL_EMOJI_DATA = 'https://www.unicode.org/Public/{version}/ucd/emoji/emoji-data.txt'
    URL_DERIVED_CORE_PROPS = 'https://www.unicode.org/Public/{version}/ucd/DerivedCoreProperties.txt'
    URL_PROP_LIST = 'https://www.unicode.org/Public/{version}/ucd/PropList.txt'
    URL_GRAPHEME_BREAK_TEST = 'https://www.unicode.org/Public/{version}/ucd/auxiliary/GraphemeBreakTest.txt'
    URL_INDIC_SYLLABIC_CATEGORY = 'https://www.unicode.org/Public/{version}/ucd/IndicSyllabicCategory.txt'
    URL_UDHR_ZIP = 'http://efele.net/udhr/assemblies/udhr_txt.zip'

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
        # ZWJ sequences are only at /Public/emoji/{version}/, use 'latest' for tests
        fname = os.path.join(PATH_TESTS, 'emoji-zwj-sequences.txt')
        cls.do_retrieve(url=cls.URL_EMOJI_ZWJ.format(version='latest'), fname=fname)
        return fname

    @classmethod
    def GraphemeBreakProperty(cls, version: str) -> str:
        fname = os.path.join(PATH_DATA, f'GraphemeBreakProperty-{version}.txt')
        cls.do_retrieve(url=cls.URL_GRAPHEME_BREAK.format(version=version), fname=fname)
        return fname

    @classmethod
    def EmojiData(cls, version: UnicodeVersion) -> str:
        """Fetch emoji-data.txt for Extended_Pictographic property."""
        fname = os.path.join(PATH_DATA, f'emoji-data-{version}.txt')
        cls.do_retrieve(url=cls.URL_EMOJI_DATA.format(version=version), fname=fname)
        return fname

    @classmethod
    def DerivedCoreProperties(cls, version: str) -> str:
        fname = os.path.join(PATH_DATA, f'DerivedCoreProperties-{version}.txt')
        cls.do_retrieve(url=cls.URL_DERIVED_CORE_PROPS.format(version=version), fname=fname)
        return fname

    @classmethod
    def PropList(cls, version: str) -> str:
        fname = os.path.join(PATH_DATA, f'PropList-{version}.txt')
        cls.do_retrieve(url=cls.URL_PROP_LIST.format(version=version), fname=fname)
        return fname

    @classmethod
    def IndicSyllabicCategory(cls, version: str) -> str:
        fname = os.path.join(PATH_DATA, f'IndicSyllabicCategory-{version}.txt')
        cls.do_retrieve(url=cls.URL_INDIC_SYLLABIC_CATEGORY.format(version=version), fname=fname)
        return fname

    @classmethod
    def TestGraphemeBreakTest(cls) -> str:
        version = fetch_unicode_versions()[-1]
        fname = os.path.join(PATH_TESTS, 'GraphemeBreakTest.txt')
        cls.do_retrieve(url=cls.URL_GRAPHEME_BREAK_TEST.format(version=version), fname=fname)
        return fname

    @classmethod
    def UDHRCombined(cls) -> str:
        """
        Fetch UDHR zip, extract and combine all translations into a single file.

        Downloads http://efele.net/udhr/assemblies/udhr_txt.zip, extracts the text files,
        and combines them with '--' separator between translations.
        """
        fname = os.path.join(PATH_TESTS, 'udhr_combined.txt')
        cls.do_retrieve_udhr_combined(url=cls.URL_UDHR_ZIP, fname=fname)
        return fname

    @staticmethod
    def do_retrieve_udhr_combined(url: str, fname: str) -> None:
        """Fetch UDHR zip file, extract, and combine all translations."""
        if not UnicodeDataFile.is_url_newer(url, fname):
            return

        session = UnicodeDataFile.get_http_session()
        print(f"fetching {url}: ", end='', flush=True)
        resp = session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        resp.raise_for_status()
        print('ok')

        print(f"extracting and combining to {fname}: ", end='', flush=True)
        combined_content = []
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            txt_files = sorted([n for n in zf.namelist() if n.endswith('.txt')])
            for txt_name in txt_files:
                with zf.open(txt_name) as f:
                    content = f.read().decode('utf-8').rstrip()
                    combined_content.append(f'----\n\n{content}\n')

        folder = os.path.dirname(fname)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        with open(fname, 'w', encoding='utf-8', newline='\n') as fout:
            fout.writelines(combined_content)
        print('ok')

    @staticmethod
    def do_retrieve(url: str, fname: str) -> None:
        """Retrieve given url to target filepath fname."""
        folder = os.path.dirname(fname)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        if not UnicodeDataFile.is_url_newer(url, fname):
            return
        session = UnicodeDataFile.get_http_session()
        resp = session.get(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
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
        if CHECK_LAST_MODIFIED:
            session = UnicodeDataFile.get_http_session()
            resp = session.head(url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
            resp.raise_for_status()
            remote_url_dt = dateutil.parser.parse(resp.headers['Last-Modified']).astimezone()
            local_file_dt = datetime.datetime.fromtimestamp(os.path.getmtime(fname)).astimezone()
            return remote_url_dt > local_file_dt
        return False

    @functools.cache
    def get_http_session() -> requests.Session:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'wcwidth-update-tables/1.0 (https://github.com/jquast/wcwidth)'
        })
        retries = urllib3.util.Retry(
            total=MAX_RETRIES,
            connect=MAX_RETRIES,
            read=MAX_RETRIES,
            backoff_factor=BACKOFF_FACTOR,
            backoff_jitter=BACKOFF_FACTOR,
            status_forcelist=[408, 429, 500, 502, 503, 504, 520],
            allowed_methods=['HEAD', 'GET'],
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retries)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
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


def replace_if_modified(new_filename: str, original_filename: str) -> None:
    """
    Replace original file with new file only if there are significant changes.

    If only the 'This code generated' timestamp line differs, discard the new file. If there are
    other changes or the original doesn't exist, replace it.
    """
    if os.path.exists(original_filename):
        with open(original_filename, encoding='utf-8') as f1, \
                open(new_filename, encoding='utf-8') as f2:
            old_lines = f1.readlines()
            new_lines = f2.readlines()

        # Generate diff
        diff_lines = list(difflib.unified_diff(old_lines, new_lines,
                                               fromfile=original_filename,
                                               tofile=new_filename,
                                               lineterm=''))

        # Check if only the 'This code generated' line is different
        significant_changes = False
        for line in diff_lines:
            if (line.startswith(('@@', '---', '+++')) or
                    (line.startswith(('-', '+')) and 'This code generated' in line)):
                continue
            else:
                significant_changes = line.startswith(('-', '+'))
            if significant_changes:
                break

        if not significant_changes:
            # only the code-generated timestamp changed, remove the .new file
            os.remove(new_filename)
            return False
    # Significant changes found, replace the original
    os.replace(new_filename, original_filename)
    return True


def fetch_all_emoji_files() -> None:
    """
    Fetch emoji variation sequences and ZWJ sequences for all versions.

    URL locations:
    - Variation sequences (5.0-12.1): /Public/emoji/{version}/
    - Variation sequences (13.0+): /Public/{version}/ucd/emoji/
    - ZWJ sequences (ALL versions): /Public/emoji/{version}/

    Note: ZWJ files never moved to /Public/{version}/ucd/emoji/ - they remain
    at /Public/emoji/{version}/ for all emoji versions.
    """
    unicode_versions = fetch_unicode_versions()

    # Legacy variation sequences (before 13.0, at /Public/emoji/{version}/)
    legacy_variation_versions = ['5.0', '11.0', '12.0', '12.1']

    for emoji_version in legacy_variation_versions:
        fname = os.path.join(PATH_DATA, f'emoji-variation-sequences-emoji-{emoji_version}.txt')
        UnicodeDataFile.do_retrieve(
            url=UnicodeDataFile.URL_LEGACY_VARIATION.format(version=emoji_version),
            fname=fname)

    # ZWJ sequences are ALL at /Public/emoji/{version}/ (they didn't move)
    all_zwj_versions = ['5.0', '11.0', '12.0', '12.1', '13.0', '13.1',
                        '14.0', '15.0', '15.1', '16.0']

    for emoji_version in all_zwj_versions:
        fname = os.path.join(PATH_DATA, f'emoji-zwj-sequences-emoji-{emoji_version}.txt')
        UnicodeDataFile.do_retrieve(
            url=UnicodeDataFile.URL_EMOJI_ZWJ.format(version=emoji_version),
            fname=fname)

    # Starting with Unicode 13.0.0, variation sequences moved to /Public/{version}/ucd/emoji/
    for version in unicode_versions:
        if version >= UnicodeVersion.parse('13.0.0'):
            fname = os.path.join(PATH_DATA, f'emoji-variation-sequences-{version}.txt')
            UnicodeDataFile.do_retrieve(
                url=UnicodeDataFile.URL_EMOJI_VARIATION.format(version=version),
                fname=fname)


def parse_args() -> dict[str, Any]:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Update Unicode code tables for wcwidth using jinja2 code generation.',
        epilog='https://github.com/jquast/wcwidth'
    )
    parser.add_argument(
        '--only-fetch',
        action='store_true',
        help='Only fetch data files without processing or code generation'
    )
    parser.add_argument(
        '--fetch-all-versions',
        action='store_true',
        help='Fetch emoji variation sequences and ZWJ sequences for all Unicode versions '
             '(for archival/testing purposes)'
    )
    parser.add_argument(
        '--check-last-modified',
        action='store_true',
        help='Check if remote files are newer than local files (rarely needed)'
    )
    return vars(parser.parse_args())


def fetch_all_data_files(fetch_all_versions: bool = False) -> None:
    """
    Fetch all required Unicode data files.

    Fetches data files for code generation and test files. Files are only downloaded if they don't
    exist locally or if CHECK_LAST_MODIFIED is True and the remote file is newer.
    """
    # Fetch DerivedAge first to determine available Unicode versions
    UnicodeDataFile.DerivedAge()
    version = fetch_unicode_versions()[-1]

    # Fetch data files required for code generation
    UnicodeDataFile.EastAsianWidth(version)
    UnicodeDataFile.DerivedGeneralCategory(version)
    UnicodeDataFile.EmojiVariationSequences(version)
    UnicodeDataFile.LegacyEmojiVariationSequences()
    UnicodeDataFile.GraphemeBreakProperty(version)
    UnicodeDataFile.EmojiData(version)
    UnicodeDataFile.DerivedCoreProperties(version)
    UnicodeDataFile.PropList(version)
    UnicodeDataFile.IndicSyllabicCategory(version)

    # Fetch test data files
    UnicodeDataFile.TestEmojiVariationSequences()
    UnicodeDataFile.TestEmojiZWJSequences()
    UnicodeDataFile.TestGraphemeBreakTest()
    UnicodeDataFile.UDHRCombined()

    # Fetch all legacy emoji files if requested
    if fetch_all_versions:
        fetch_all_emoji_files()


def main(only_fetch: bool = False, fetch_all_versions: bool = False,
         check_last_modified: bool = False) -> None:
    """Update east-asian, combining and zero width tables."""
    # Set global flag for HTTP requests to check Last-Modified headers
    global CHECK_LAST_MODIFIED
    CHECK_LAST_MODIFIED = check_last_modified

    # Always fetch data files first
    fetch_all_data_files(fetch_all_versions)

    # Exit early if only fetching was requested
    if only_fetch:
        print('Fetch complete (--only-fetch mode, skipping code generation)')
        return

    # This defines which jinja source templates map to which output filenames,
    # and what function defines the source data. We hope to add more source
    # language options using jinja2 templates, with minimal modification of the
    # code.
    def get_codegen_definitions() -> Iterator[RenderDefinition]:
        yield UnicodeVersionPyRenderDef.new(
            UnicodeVersionPyRenderCtx([fetch_unicode_versions()[-1]])  # Only latest
        )
        yield UnicodeTableRenderDef.new('table_vs16.py', fetch_table_vs16_data())
        yield UnicodeTableRenderDef.new('table_wide.py', fetch_table_wide_data())
        yield UnicodeTableRenderDef.new('table_zero.py', fetch_table_zero_data())
        yield UnicodeTableRenderDef.new('table_mc.py', fetch_table_category_mc_data())
        yield UnicodeTableRenderDef.new('table_ambiguous.py', fetch_table_ambiguous_data())
        yield GraphemeTableRenderDef.new(fetch_table_grapheme_data())
        yield UnicodeVersionRstRenderDef.new(fetch_source_headers())

    for render_def in get_codegen_definitions():
        new_filename = render_def.output_filename + '.new'
        with open(new_filename, 'w', encoding='utf-8', newline='\n') as fout:
            print(f'write {new_filename}: ', flush=True, end='')
            for data in render_def.generate():
                fout.write(data)

        if not replace_if_modified(new_filename, render_def.output_filename):
            print(f'discarded {new_filename} (timestamp-only change)')
        else:
            assert render_def.output_filename != 'table_vs16.py', ('table_vs16 not expected to change!')
            print('ok')


if __name__ == '__main__':
    main(**parse_args())
