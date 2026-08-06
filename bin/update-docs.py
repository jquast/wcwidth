#!/usr/bin/env python
"""Regenerate the generated documentation files."""

from __future__ import annotations

# std imports
import os
import re
import glob
import textwrap
import importlib.util

from typing import Sequence

# Executed by tox,  $ tox -e update
#
# This script owns every generated documentation file:
#
#   docs/api_c.rst          C11 API reference, parsed from the headers.
#   docs/unicode_version.rst  Unicode release files page, from data file headers.
#   docs/libwcwidth.rst     canonical terminal names and Unicode version markers.
#   README.rst              list_term_programs() example (via docs/intro.rst).
#
# Headers are discovered by glob, so adding, renaming, or removing a header is
# reflected in docs/api_c.rst automatically.  Each header is parsed for comment
# blocks and declarations, and emitted as Sphinx C-domain directives, whose
# signatures are validated by Sphinx's own C parser at documentation build
# time.  The terminal name and Unicode version sections are refreshed from the
# generated Python tables.

PATH_UP = os.path.relpath(os.path.join(os.path.dirname(__file__), os.path.pardir))
PATH_HEADERS = os.path.join(PATH_UP, 'libwcwidth', 'include', 'wcwidth')
PATH_DATA = os.path.join(PATH_UP, 'data')
PATH_DOCS = os.path.join(PATH_UP, 'docs')
API_C_OUTPUT = os.path.join(PATH_DOCS, 'api_c.rst')
LIBWCWIDTH_DOC = os.path.join(PATH_DOCS, 'libwcwidth.rst')
README_DOC = os.path.join(PATH_UP, 'README.rst')

COMMENT_RE = re.compile(r'/\*(.*?)\*/', re.DOTALL)
MACRO_RE = re.compile(r'#define\s+(\w+)\s*(.*)$')
GUARD_IFNDEF_RE = re.compile(r'^\s*#\s*ifndef\s+(\w+)')
SKIP_LINE_RE = re.compile(r'^\s*#\s*(?:ifdef|endif|include)\b|^\s*extern\s+"C"\s*\{|^\s*\}\s*$')
ENUM_RE = re.compile(r'typedef\s+enum\s*\{(.*)\}\s*(\w+)\s*;', re.DOTALL)
STRUCT_RE = re.compile(r'typedef\s+struct\s*\{(.*)\}\s*(\w+)\s*;', re.DOTALL)
OPAQUE_RE = re.compile(r'typedef\s+struct\s+(\w+)\s+(\w+)\s*;')
FUNC_PTR_RE = re.compile(r'typedef\s+(.+?)\(\s*\*\s*(\w+)\s*\)\s*\(([^()]*)\)\s*;', re.DOTALL)
TYPEDEF_RE = re.compile(r'typedef\s+(.+?)\s+(\w+)\s*;', re.DOTALL)
FUNC_RE = re.compile(r'^(.*?)\b(\w+)\s*\(([^()]*)\)\s*;?$', re.DOTALL)
EXTERN_RE = re.compile(r'extern\s+(const\s+.+?)\s+(\w+)\s*(?:\[\s*\])?\s*;', re.DOTALL)
PARAM_RE = re.compile(r'^\*?(\w+)\*?:\s*(.*)$')

# Object names already emitted, across all headers: wcstwidth.h declares the
# same functions as wcwidth.h, and the tables.h interval arrays are data.
EMITTED: set[str] = set()

# Headers in documentation order, most important first; glob still discovers
# all headers, and any not listed here are appended alphabetically at the end.
HEADER_ORDER = [
    'wcwidth.h',
    'wcstwidth.h',
    'width.h',
    'textwrap.h',
    'align.h',
    'clip.h',
    'escape.h',
    'utf8.h',
    'grapheme.h',
    'hyperlink.h',
    'sgr.h',
    'text_sizing.h',
    'terminal_override.h',
    'tables.h',
    'wcwidth_config.h',
]


def load_module(name: str, path: str):
    """Import a single module file without importing its package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


TERM_TABLE = load_module('table_term_programs',
                         os.path.join(PATH_UP, 'wcwidth', 'table_term_programs.py'))
UNICODE_VERSIONS = load_module('unicode_versions',
                               os.path.join(PATH_UP, 'wcwidth', 'unicode_versions.py'))


def preprocess_header(text: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Strip include guards, includes, and extern "C" wrappers."""
    body_parts = []
    macros = []
    guard_names = set()
    offset = 0
    for line in text.splitlines(keepends=True):
        if m := GUARD_IFNDEF_RE.match(line):
            guard_names.add(m.group(1))
            continue
        if m := MACRO_RE.match(line):
            if m.group(1) not in guard_names:
                macros.append((offset, m.group(1), m.group(2).strip()))
            continue
        if SKIP_LINE_RE.match(line):
            continue
        body_parts.append(line)
        offset += len(line)
    return ''.join(body_parts), macros


def extract_comments(body: str) -> tuple[list[re.Match], str]:
    """Return comment matches and body with comments blanked out, positions preserved."""
    matches = list(COMMENT_RE.finditer(body))
    masked = COMMENT_RE.sub(lambda m: ' ' * (m.end() - m.start()), body)
    return matches, masked


def trim_span(masked: str, span: tuple[int, int]) -> tuple[int, int] | None:
    """Trim whitespace from a (start, end) span; None if it is empty."""
    start, end = span
    while start < end and masked[start].isspace():
        start += 1
    while end > start and masked[end - 1].isspace():
        end -= 1
    if start == end:
        return None
    return (start, end)


def split_statements(masked: str) -> list[tuple[int, int]]:
    """Split masked into (start, end) statement spans at top-level ';'."""
    stmts = []
    depth = 0
    start = 0
    for i, c in enumerate(masked):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == ';' and depth == 0:
            if span := trim_span(masked, (start, i + 1)):
                stmts.append(span)
            start = i + 1
    if span := trim_span(masked, (start, len(masked))):
        stmts.append(span)
    return stmts


def split_parts(masked: str) -> list[tuple[int, int]]:
    """Split masked into (start, end) spans at every ';'."""
    parts = []
    start = 0
    for i, c in enumerate(masked):
        if c == ';':
            parts.append((start, i + 1))
            start = i + 1
    if start < len(masked):
        parts.append((start, len(masked)))
    return parts


def clean_comment(comment: str) -> str:
    """Strip the leading '*' decoration from a header comment."""
    lines = []
    for raw in comment.splitlines():
        line = raw.strip()
        if line:
            line = re.sub(r'^\*+\s?', '', line)
        lines.append(line)
    return '\n'.join(lines).strip()


def escape_stars(text: str) -> str:
    """Escape asterisks that are not RST emphasis, e.g. the *error pointer."""
    return re.sub(r'(?<!\*)\*(?!\*)', r'\\*', text)


def description(comment: str | None,
                param_names: Sequence[str] = ()) -> tuple[list[str], list[tuple[str, str]]]:
    """Split a header comment into prose lines and :param: fields."""
    body = []
    fields: list[tuple[str, str]] = []
    current = None
    if comment:
        # A :param: field continues across following lines until a blank line
        # or the next parameter, so multi-line descriptions are not lost as prose.
        for raw in comment.splitlines():
            line = raw.strip()
            if not line or line == '*':
                if current is not None:
                    current = None
                else:
                    body.append('')
                continue
            line = re.sub(r'^\*+\s*', '', line)
            m = PARAM_RE.match(line)
            if m and m.group(1) in param_names:
                current = m.group(1)
                fields.append((current, escape_stars(m.group(2).strip())))
            elif current is not None and ':' not in line:
                name, desc = fields[-1]
                fields[-1] = (name, desc + ' ' + escape_stars(line))
            elif line in ('Parameters:', 'Arguments:'):
                continue
            else:
                body.append(escape_stars(line))
    return body, fields


def param_names(param_text: str) -> list[str]:
    """Return the parameter names of a function signature parameter list."""
    names = []
    for part in param_text.split(','):
        part = part.strip()
        if not part or part == 'void':
            continue
        names.append(part.split()[-1].lstrip('*'))
    return names


def render(kind: str, signature: str, comment: str | None,
           param_names: Sequence[str] = (),
           *, members: Sequence[tuple[str, str, str]] = (),
           note: str | None = None) -> list[str]:
    """Render a c-domain directive with its description, nested items, and note."""
    # The C domain does not join continuation lines, so signatures are kept on
    # one line; the generated file is exempt from doc8 line-length checks.
    body, fields = description(comment, param_names)
    lines = [f'.. {kind}:: {" ".join(signature.split())}']
    if body or fields:
        lines.append('')
        lines.extend('' if not line else f'   {line}' for line in body)
        lines.extend(f'   :param {name}: {desc}' for name, desc in fields)
    for mkind, name, doc in members:
        lines.append('')
        lines.append(f'   .. {mkind}:: {name}')
        if doc:
            lines.append('')
            lines.append('      ' + doc)
    if note:
        lines.append('')
        lines.append(f'   {note}')
    return lines


def enum_members(body: str) -> list[tuple[str, str]]:
    """Return (name, doc) pairs from an enum body."""
    # Comments sit after the ',' of the member they describe, so each comment is
    # paired with the member seen most recently before it.
    members: list[tuple[str, str]] = []
    name = ''
    for m in re.finditer(r'/\*(.*?)\*/|([A-Za-z_]\w*)', body, re.DOTALL):
        if m.group(1) is not None:
            if name and members[-1][0] == name and not members[-1][1]:
                members[-1] = (name, clean_comment(m.group(1)))
        else:
            name = m.group(2)
            members.append((name, ''))
    return members


def struct_members(body: str) -> list[tuple[str, str, str]]:
    """Return (type, name, doc) triples from a struct body."""
    # A comment on the same line as the previous ';' documents that member
    # (trailing); a comment on its own line documents the following declaration
    # (leading).  Members declared in a comma-separated list share the first
    # member's type.
    members: list[tuple[str, str, str]] = []
    comments, masked = extract_comments(body)
    ci = 0
    for start, end in split_parts(masked):
        decl = masked[start:end].strip()
        part_comments = []
        while ci < len(comments) and comments[ci].start() < end:
            part_comments.append(comments[ci])
            ci += 1
        if not decl:
            if members and part_comments:
                mtype, name, _ = members[-1]
                members[-1] = (mtype, name, clean_comment(part_comments[-1].group(1)))
            continue
        lead_doc = None
        for cm in part_comments:
            if '\n' not in masked[start:cm.start()] and members:
                mtype, name, _ = members[-1]
                members[-1] = (mtype, name, clean_comment(cm.group(1)))
            else:
                lead_doc = clean_comment(cm.group(1))
        mtype = None
        for member in decl.split(','):
            member = member.strip()
            if not member:
                continue
            tokens = member.split()
            if len(tokens) >= 2:
                mtype = ' '.join(tokens[:-1])
                name = tokens[-1]
            elif mtype is not None:
                name = tokens[0]
            else:
                continue
            members.append((mtype, name.rstrip(';'), ''))
        if lead_doc is not None and members:
            mtype, name, _ = members[-1]
            members[-1] = (mtype, name, lead_doc)
    return members


def classify(stmt: str) -> tuple[str, str, re.Match] | None:
    """Return (kind, name, match) for a statement, or None if not public API."""
    if m := ENUM_RE.match(stmt):
        return ('enum', m.group(2), m)
    if m := STRUCT_RE.match(stmt):
        return ('struct', m.group(2), m)
    if m := OPAQUE_RE.match(stmt):
        return ('type', m.group(2), m)
    if m := FUNC_PTR_RE.match(stmt):
        return ('type', m.group(2), m)
    if m := TYPEDEF_RE.match(stmt):
        return ('type', m.group(2), m)
    if m := FUNC_RE.match(stmt):
        return ('function', m.group(2), m)
    if m := EXTERN_RE.match(stmt):
        if 'wcwidth_interval_t' in m.group(1):
            return None
        return ('var', m.group(2), m)
    return None


def render_item(kind: str, name: str, payload: str,
                m: re.Match | None, comment: str | None) -> list[str]:
    """Render one classified statement or macro as c-domain directives."""
    if kind == 'macro':
        return render('c:macro', name, comment, note=f'Defined as ``{payload}``.')
    if kind == 'enum':
        members = [('c:enumerator', n, d) for n, d in enum_members(m.group(1))]
        return render('c:enum', m.group(2), comment, members=members)
    if kind == 'struct':
        members = [('c:member', f'{t} {n}', d) for t, n, d in struct_members(m.group(1))]
        return render('c:struct', m.group(2), comment, members=members)
    if kind == 'type':
        params = param_names(m.group(3)) if FUNC_PTR_RE.match(payload) else ()
        return render('c:type', name, comment, params)
    if kind == 'function':
        signature = ' '.join(payload.rstrip(';').split())
        return render('c:function', signature, comment, param_names(m.group(3)))
    return render('c:var', f'{m.group(1).strip()} {m.group(2)}', comment)


def header_intro(comments: list[re.Match], masked: str, first_start: int) -> tuple[str, int]:
    """Return the header's leading comment as (intro_text, comment index past it)."""
    if not comments or comments[0].end() > first_start:
        return '', 0
    if masked[comments[0].end():first_start].strip():
        return '', 0
    first = clean_comment(comments[0].group(1))
    if 'Copyright' in first:
        return '', 0
    return first, 1


def render_header_section(header: str, text: str) -> list[str]:
    """Render one header as a titled section of c-domain directives."""
    body, macros = preprocess_header(text)
    comments, masked = extract_comments(body)
    stmts = split_statements(masked)

    events = []
    for start, end in stmts:
        stmt = body[start:end].strip()
        info = classify(stmt)
        if info is None:
            continue
        kind, name, m = info
        if name not in EMITTED:
            events.append((start, end, kind, name, stmt, m))
    for pos, name, value in macros:
        if name not in EMITTED:
            events.append((pos, pos, 'macro', name, value, None))
    events.sort(key=lambda event: event[0])
    if not events:
        return []
    first = clean_comment(comments[0].group(1)) if comments else ''
    if 'Internal' in first or 'Generated by' in first:
        return []

    lines = [header, '-' * len(header), '']
    intro, comment_idx = header_intro(comments, masked, stmts[0][0] if stmts else events[0][0])
    if intro:
        lines.append(intro)
        lines.append('')

    lead = None
    prev_end = None
    for start, end, kind, name, payload, m in events:
        # A comment block documents the declaration that follows it; a blank
        # line between a comment and the declaration ends the association.
        if prev_end is not None and '\n\n' in body[prev_end:start]:
            lead = None
        while comment_idx < len(comments) and comments[comment_idx].end() <= start:
            if '\n\n' in body[comments[comment_idx].end():start]:
                comment_idx += 1
                continue
            lead = comments[comment_idx].group(1)
            comment_idx += 1
        lines.extend(render_item(kind, name, payload, m, lead))
        lines.append('')
        EMITTED.add(name)
        prev_end = end
    return lines


def header_files() -> list[str]:
    """Return the public header paths in documentation order."""
    # All headers are discovered by glob, so adding, renaming, or removing a
    # header is reflected automatically; known headers follow HEADER_ORDER and
    # any others are appended alphabetically at the end.
    found = set(glob.glob(os.path.join(PATH_HEADERS, '*.h')))
    ordered = []
    for name in HEADER_ORDER:
        path = os.path.join(PATH_HEADERS, name)
        if path in found:
            ordered.append(path)
    return ordered + sorted(found - set(ordered))


def render_api_doc() -> str:
    out = [
        f'.. Generated by wcwidth code generation (bin/{os.path.basename(__file__)}); do not edit.',
        '',
        '.. _c-api:',
        '',
        'C11 Public API',
        '==============',
        '',
        'This library is released together with the Python `wcwidth` package: any change',
        'to C11 ships with a PyPI release, and the same SEMVER_ rules apply.  The C11',
        'API is stable within a major version; function signatures do not change until',
        'a new major release.',
        '',
    ]
    for path in header_files():
        with open(path, encoding='utf-8') as fin:
            text = fin.read()
        section = render_header_section(os.path.basename(path), text)
        if section:
            out.extend(section)
            out.append('')
    out.append('.. _SEMVER: https://semver.org')
    return '\n'.join(out).rstrip() + '\n'


def update_doc(path: str, pattern: str, replacement: str) -> bool:
    """Replace one occurrence of pattern in *path*; True if it changed."""
    with open(path, encoding='utf-8') as fin:
        original = fin.read()
    modified = re.sub(pattern, replacement, original, count=1, flags=re.DOTALL)
    if modified == original:
        return False
    with open(path, 'w', encoding='utf-8', newline='\n') as fout:
        fout.write(modified)
    return True


def report(label: str, changed: bool) -> None:
    """Print whether the given docs section was updated."""
    print(f'{label}: {"updated" if changed else "up-to-date"}')


def write_if_changed(path: str, content: str, label: str) -> None:
    """Write *content* to *path* only if it differs, reporting the result."""
    try:
        with open(path, encoding='utf-8') as fin:
            original = fin.read()
    except FileNotFoundError:
        original = ''
    if content != original:
        new_path = path + '.new'
        with open(new_path, 'w', encoding='utf-8', newline='\n') as fout:
            fout.write(content)
        os.replace(new_path, path)
        print(f'{label}: updated')
    else:
        print(f'{label}: up-to-date')


def update_libwcwidth_term_programs() -> bool:
    """Refresh the canonical terminal name list in docs/libwcwidth.rst."""
    names = ' '.join(sorted(TERM_TABLE.KNOWN_TERMINALS))
    display = textwrap.fill(names, width=79, subsequent_indent='    ',
                            break_on_hyphens=False)
    pattern = r'\.\. BEGIN_LIST_TERM_PROGRAMS\n.*?\n\.\. END_LIST_TERM_PROGRAMS'
    replacement = (
        '.. BEGIN_LIST_TERM_PROGRAMS\n'
        '.. code-block:: text\n'
        '\n'
        f'    {display}\n'
        '\n'
        '.. END_LIST_TERM_PROGRAMS'
    )
    return update_doc(LIBWCWIDTH_DOC, pattern, replacement)


def update_libwcwidth_unicode_version() -> bool:
    """Refresh the Unicode version substitution in docs/libwcwidth.rst."""
    return update_doc(LIBWCWIDTH_DOC, r'\.\. \|unicode_version\| replace:: [0-9.]+',
                      f'.. |unicode_version| replace:: {UNICODE_VERSIONS.list_versions()[-1]}')


def update_readme_term_programs() -> bool:
    """Refresh the list_term_programs() example in README.rst."""
    names = sorted(TERM_TABLE.KNOWN_TERMINALS | TERM_TABLE.ALIASES.keys())
    display = textwrap.fill(repr(tuple(names)), width=79, subsequent_indent='     ',
                            break_on_hyphens=False)
    pattern = r'\.\. BEGIN_LIST_TERM_PROGRAMS\n.*?\n\.\. END_LIST_TERM_PROGRAMS'
    replacement = (
        '.. BEGIN_LIST_TERM_PROGRAMS\n'
        '.. code-block:: python\n'
        '\n'
        '    >>> wcwidth.list_term_programs()\n'
        f'    {display}\n'
        '\n'
        '.. END_LIST_TERM_PROGRAMS'
    )
    return update_doc(README_DOC, pattern, replacement)


def unicode_source_headers() -> list[tuple[str, str]]:
    """(file name, date) pairs for the Unicode release files page, version-sorted."""
    pattern = re.compile(
        r'^(emoji-variation-sequences|DerivedGeneralCategory|EastAsianWidth)-'
        r'(\d+)\.(\d+)\.(\d+).txt$')
    matches = []
    for fname in os.listdir(PATH_DATA):
        if m := re.match(pattern, fname):
            matches.append((m, fname))
    matches.sort(key=lambda pair: (pair[0].group(1), *map(int, pair[0].groups()[1:])))
    headers = []
    for m, fname in matches:
        with open(os.path.join(PATH_DATA, fname), encoding='utf-8') as fin:
            comments = [line.partition('#')[2].strip()
                        for line in fin if line.partition('#')[2].strip()]
        name = comments[0]
        if name == 'emoji-variation-sequences.txt':
            name = fname
        headers.append((name, comments[1]))
    return headers


def unicode_version_page() -> str:
    """Render docs/unicode_version.rst from the Unicode data file headers."""
    return (
        '=====================\n'
        'Unicode release files\n'
        '=====================\n'
        '\n'
        'This library aims to be forward-looking, portable, and most correct.\n'
        'The most current release of this API is based on the Unicode Standard\n'
        'release files:\n'
        '\n'
        '\n'
        + ''.join(f'``{name}``\n  *{date}*\n\n' for name, date in unicode_source_headers())
    )


def main() -> None:
    """Regenerate all generated documentation files."""
    write_if_changed(API_C_OUTPUT, render_api_doc(), 'docs/api_c.rst')
    write_if_changed(os.path.join(PATH_DOCS, 'unicode_version.rst'),
                     unicode_version_page(), 'docs/unicode_version.rst')
    report('docs/libwcwidth.rst: canonical terminal names',
           update_libwcwidth_term_programs())
    report('docs/libwcwidth.rst: Unicode version',
           update_libwcwidth_unicode_version())
    report('README.rst: list_term_programs() example',
           update_readme_term_programs())


if __name__ == '__main__':
    main()
