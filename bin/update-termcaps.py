#!/usr/bin/env python
"""
Code generation of terminal capability wcwidth.

This is code generation using jinja2.

Uses 'subprocesses', because curses.setupterm() can only be called once per process.  See bottom of
file 'blessed' project, file blessed/terminal.py for details on this Python/curses limitation.

This code is almost entirely unnecessary -- modern terminals use "classical codes" for cursor
movement/indeterminate movements precisely for its high compatibility with legacy terminal
applications.

Would somebody someday invent a new terminal type that is popularly used with a new capability for
"cursor up"?

Probably not.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import jinja2

PATH_UP = os.path.relpath(os.path.join(os.path.dirname(__file__), os.path.pardir))
THIS_FILEPATH = ('wcwidth/' + Path(__file__).resolve().relative_to(Path(PATH_UP).resolve()).as_posix())

JINJA_ENV = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(PATH_UP, 'code_templates')),
    keep_trailing_newline=True)
UTC_NOW = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

# Terminal types to extract capabilities from
TERMINALS = [
    # xterm family
    'xterm', 'xterm-256color', 'xterm-direct',
    # Modern GPU-accelerated terminals
    'alacritty', 'alacritty-direct',
    'kitty', 'kitty-direct',
    'ghostty',
    # Multiplexers
    'tmux', 'tmux-256color',
    'screen', 'screen-256color',
    # Classic/legacy
    'linux', 'vt100', 'vt220',
    # Others
    'rxvt-unicode-256color',
    'konsole-256color',
]

# Capabilities to extract from terminfo, organized by semantic category.
# Format: 'name': ('terminfo_cap', {'nparams': N, 'match_any': bool})

# Indeterminate/vertical - raise in 'strict' mode
INDETERMINATE_TERMINFO: Dict[str, Tuple[str, Dict[str, Any]]] = {
    'cursor_address': ('cup', {'nparams': 2}),
    'cursor_home': ('home', {}),
    'parm_up_cursor': ('cuu', {'nparams': 1}),
    'cursor_up': ('cuu1', {}),
    'parm_down_cursor': ('cud', {'nparams': 1}),
    'cursor_down': ('cud1', {}),
    'column_address': ('hpa', {'nparams': 1}),
    'row_address': ('vpa', {'nparams': 1}),
    'clear_screen': ('clear', {}),
    'clr_eol': ('el', {}),
    'clr_bol': ('el1', {}),
    'clr_eos': ('ed', {}),
    'restore_cursor': ('rc', {}),
    'scroll_forward': ('ind', {}),
    'scroll_reverse': ('ri', {}),
    'change_scroll_region': ('csr', {'nparams': 2}),
    'enter_fullscreen': ('smcup', {}),
    'exit_fullscreen': ('rmcup', {}),
    # Character/line insert/delete (from blessed)
    'delete_character': ('dch1', {}),
    'delete_line': ('dl1', {}),
    'insert_line': ('il1', {}),
    'erase_chars': ('ech', {'nparams': 1}),
    'parm_dch': ('dch', {'nparams': 1}),
    'parm_delete_line': ('dl', {'nparams': 1}),
    'parm_ich': ('ich', {'nparams': 1}),
    'parm_insert_line': ('il', {'nparams': 1}),
    'parm_index': ('indn', {'nparams': 1}),
    'parm_rindex': ('rin', {'nparams': 1}),
}

# ANSI standard patterns not fully covered by terminfo.
# These are added to indeterminate caps after terminfo extraction.
# Terminfo cud1 is typically '\n', but ANSI CUD (CSI B) should also be caught.
# Terminfo clr_eos is '\x1b[J' only, but ANSI ED accepts parameters.
ANSI_INDETERMINATE_FALLBACKS: Dict[str, str] = {
    'cursor_down': r'\x1b\[\d*B',      # ANSI CUD - terminfo cud1 is \n
    'erase_display': r'\x1b\[\d*J',    # ANSI ED - terminfo ed is \x1b[J only
}

# Regex to match a single escape sequence (for splitting compound sequences).
# NOTE: This operates on escaped string patterns (e.g., '\\x1b') not raw bytes,
# so it cannot reuse ZERO_WIDTH_PATTERN from control_codes.py which matches actual bytes.
ESCAPE_SEQ_PATTERN = re.compile(
    r'\\x1b\\\[.*?[A-Za-z@`~]|'   # CSI: ESC [ ... final_byte
    r'\\x1b\][^\\]*(?:\\x07)?|'   # OSC: ESC ] ... BEL
    r'\\x1b.'                      # Fp/Fe: ESC + single char (7, 8, D, M, etc.)
)

# Safe sequences that should NOT be in INDETERMINATE_CAPS.
# These are zero-width and do not affect horizontal cursor position.
SAFE_PATTERNS = {
    r'\\x1b7',                     # DECSC - save cursor (doesn't move)
    r'\\x1b\\\[\d+;\d+;\d+t',      # Window title save/restore (22;0;0t, 23;0;0t)
    r'\\x1b\\\[r',                 # Reset scroll region (no params, doesn't move cursor)
}

def split_alternatives(pattern: str) -> List[str]:
    """
    Split a pattern like 'A|B|C' into ['A', 'B', 'C'].

    Handles nested groups, so '(?:X|Y)|Z' splits into ['(?:X|Y)', 'Z'].
    """
    alternatives = []
    current = []
    depth = 0

    for char in pattern:
        if char == '(' and depth >= 0:
            depth += 1
            current.append(char)
        elif char == ')' and depth > 0:
            depth -= 1
            current.append(char)
        elif char == '|' and depth == 0:
            alternatives.append(''.join(current))
            current = []
        else:
            current.append(char)

    if current:
        alternatives.append(''.join(current))

    return alternatives


def is_covered_by_concatenation(seq: str, patterns: Dict[str, str], exclude: str) -> bool:
    """Check if seq can be formed by concatenating matches from patterns."""
    if not seq:
        return True

    for name, pattern in patterns.items():
        if name == exclude:
            continue

        try:
            compiled = re.compile(pattern)
            match = compiled.match(seq)
            if match and match.group():
                remainder = seq[match.end():]
                if is_covered_by_concatenation(remainder, patterns, exclude):
                    return True
        except re.error:
            continue

    return False


def reduce_redundant_patterns(caps: Dict[str, str]) -> Dict[str, str]:
    """
    Remove compound patterns that are covered by concatenation of other patterns.

    For example, if clear_screen is '(?:\\x1b[H\\x1b[2J|\\x1b[H\\x1b[J)' and both
    alternatives can be formed by cursor_home + erase_display/clr_eos, then
    clear_screen is redundant and removed.
    """
    reduced = {}

    for name, pattern in caps.items():
        if not pattern.startswith('(?:'):
            reduced[name] = pattern
            continue

        inner = pattern[3:-1]
        alternatives = split_alternatives(inner)

        kept = []
        for alt in alternatives:
            if not is_covered_by_concatenation(alt, caps, name):
                kept.append(alt)

        if not kept:
            continue
        elif len(kept) == 1:
            reduced[name] = kept[0]
        else:
            reduced[name] = '(?:' + '|'.join(kept) + ')'

    return reduced


@dataclass(frozen=True)
class RenderContext:
    """Base render context."""

    def to_dict(self) -> dict[str, Any]:
        return {fld.name: getattr(self, fld.name) for fld in fields(self)}


@dataclass(frozen=True)
class TerminalCapsRenderCtx(RenderContext):
    """Render context for terminal capabilities."""
    terminals: List[str]
    indeterminate_caps: Dict[str, str]


@dataclass
class RenderDefinition:
    """Defines how to render a template to an output file."""
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
        return self._template.render(self._render_context)

    def generate(self) -> Iterator[str]:
        return self._template.generate(self._render_context)


SUBPROC_SCRIPT = os.path.join(os.path.dirname(__file__), 'update-termcaps-subproc.py')


def extract_single_terminal(term_name: str,
                            terminfo_caps: Dict[str, Tuple[str, Dict[str, Any]]]) -> Dict[str, str]:
    """
    Extract capabilities for ONE terminal in a SUBPROCESS.

    Must run in subprocess because setupterm() is once-per-process.
    """
    env = os.environ.copy()
    env['TERMCAPS_TERMINAL'] = term_name
    env['TERMCAPS_CAPS'] = json.dumps(terminfo_caps)

    try:
        result = subprocess.run(
            [sys.executable, SUBPROC_SCRIPT],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"Warning: {term_name}: timeout", file=sys.stderr)
        return {}

    if result.returncode != 0:
        print(f"Warning: {term_name}: {result.stderr.strip()}", file=sys.stderr)
        return {}

    try:
        data = json.loads(result.stdout)
        if 'error' in data:
            print(f"Warning: {term_name}: {data['error']}", file=sys.stderr)
            return {}
        return data
    except json.JSONDecodeError:
        print(f"Warning: {term_name}: invalid JSON output", file=sys.stderr)
        return {}


def extract_all_terminals(terminals: List[str],
                          terminfo_caps: Dict[str, Tuple[str, Dict[str, Any]]]) -> Dict[str, str]:
    """Extract capabilities from all terminals, merging unique patterns."""
    # Collect all unique patterns for each capability
    all_patterns: Dict[str, set] = {}

    for term in terminals:
        patterns = extract_single_terminal(term, terminfo_caps)
        for name, pattern in patterns.items():
            if name not in all_patterns:
                all_patterns[name] = set()
            all_patterns[name].add(pattern)

    # Merge multiple patterns with alternation
    merged: Dict[str, str] = {}
    for name, patterns in all_patterns.items():
        if len(patterns) == 1:
            merged[name] = patterns.pop()
        else:
            # Sort for deterministic output, join with alternation
            merged[name] = '(?:' + '|'.join(sorted(patterns)) + ')'

    return merged


def split_escape_sequences(pattern: str) -> List[str]:
    """
    Split a compound escape sequence pattern into individual sequences.

    For example, '\\x1b7\\x1b\\[\\?47h' -> ['\\x1b7', '\\x1b\\[\\?47h'].
    """
    sequences = ESCAPE_SEQ_PATTERN.findall(pattern)
    return sequences if sequences else [pattern]


def is_safe_pattern(pattern: str) -> bool:
    """Check if a pattern matches any of the safe (non-indeterminate) sequences."""
    for safe in SAFE_PATTERNS:
        if re.fullmatch(safe, pattern):
            return True
    return False


def split_and_filter_patterns(caps: Dict[str, str]) -> Dict[str, str]:
    """
    Split compound sequences and filter out "safe" patterns.

    For compound capabilities like enter_fullscreen that contain multiple
    escape sequences, split them into individual sequences and remove any
    that are safe (zero-width, no cursor movement).
    """
    result: Dict[str, str] = {}

    for name, pattern in caps.items():
        # First, handle alternation within the pattern
        alternatives = split_alternatives(pattern)

        kept_alternatives = []
        for alt in alternatives:
            # Split this alternative into individual escape sequences
            sequences = split_escape_sequences(alt)

            # Filter out safe sequences
            indeterminate_seqs = [seq for seq in sequences if not is_safe_pattern(seq)]

            # If any indeterminate sequences remain, keep them
            if indeterminate_seqs:
                # Rejoin the sequences (they're individual patterns now)
                kept_alternatives.extend(indeterminate_seqs)

        if not kept_alternatives:
            # All sequences were safe, skip this capability entirely
            continue

        # Deduplicate and sort for deterministic output
        unique_patterns = sorted(set(kept_alternatives))

        if len(unique_patterns) == 1:
            result[name] = unique_patterns[0]
        else:
            result[name] = '|'.join(unique_patterns)

    return result


def fetch_terminal_caps_data() -> TerminalCapsRenderCtx:
    """Fetch and process terminal capability patterns from terminfo."""
    print('extracting terminal capabilities: ', end='', flush=True)
    indeterminate = extract_all_terminals(TERMINALS, INDETERMINATE_TERMINFO)
    print('ok')

    # Add ANSI fallback patterns not fully covered by terminfo
    for name, pattern in ANSI_INDETERMINATE_FALLBACKS.items():
        if name not in indeterminate:
            indeterminate[name] = pattern

    # Second pass: reduce redundant compound patterns
    print('reducing redundant patterns: ', end='', flush=True)
    indeterminate = reduce_redundant_patterns(indeterminate)
    print('ok')

    # Third pass: split compound sequences and filter out safe patterns
    print('splitting and filtering safe patterns: ', end='', flush=True)
    indeterminate = split_and_filter_patterns(indeterminate)
    print('ok')

    # Convert patterns to repr() form for valid Python source
    def repr_values(d: Dict[str, str]) -> Dict[str, str]:
        return {k: repr(v) for k, v in d.items()}

    return TerminalCapsRenderCtx(
        terminals=TERMINALS,
        indeterminate_caps=repr_values(indeterminate),
    )


def main() -> None:
    """Update terminal capability patterns."""
    context = fetch_terminal_caps_data()
    render_def = RenderDefinition(
        jinja_filename='indeterminate_seqs.py.j2',
        output_filename=os.path.join(PATH_UP, 'wcwidth', 'indeterminate_seqs.py'),
        render_context=context,
    )

    new_filename = render_def.output_filename + '.new'
    with open(new_filename, 'w', encoding='utf-8', newline='\n') as fout:
        print(f'write {render_def.output_filename}: ', flush=True, end='')
        for data in render_def.generate():
            fout.write(data)

    os.replace(new_filename, render_def.output_filename)
    print('ok')


if __name__ == '__main__':
    main()
