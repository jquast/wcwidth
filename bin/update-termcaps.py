#!/usr/bin/env python
"""
Update terminal capability patterns for wcwidth. This is code generation using jinja2.

Uses subprocesses because curses.setupterm() can only be called once per process.
See blessed/terminal.py lines 2751-2770 for details on this Python/curses limitation.

This is typically executed through tox,

$ tox -e update

https://github.com/jquast/wcwidth
"""
from __future__ import annotations

import datetime
import difflib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Iterator, List, Tuple

import jinja2

PATH_UP = os.path.relpath(os.path.join(os.path.dirname(__file__), os.path.pardir))
THIS_FILEPATH = ('wcwidth/' +
                 Path(__file__).resolve().relative_to(Path(PATH_UP).resolve()).as_posix())

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
# Format: 'name': ('terminfo_cap', {'nparams': N, 'match_grouped': bool, 'match_any': bool})

# Horizontal movement - tracked in 'parse' mode
HORIZONTAL_MOVEMENT_TERMINFO: Dict[str, Tuple[str, Dict[str, Any]]] = {
    'parm_right_cursor': ('cuf', {'nparams': 1, 'match_grouped': True}),
    'cursor_right': ('cuf1', {}),
    'parm_left_cursor': ('cub', {'nparams': 1, 'match_grouped': True}),
    'cursor_left': ('cub1', {}),
}

# Indeterminate/vertical - raise in 'strict' mode
INDETERMINATE_TERMINFO: Dict[str, Tuple[str, Dict[str, Any]]] = {
    'cursor_address': ('cup', {'nparams': 2, 'match_grouped': True}),
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

# Zero-width sequences from terminfo - no cursor movement
ZERO_WIDTH_TERMINFO: Dict[str, Tuple[str, Dict[str, Any]]] = {
    # Text attributes
    'enter_bold_mode': ('bold', {}),
    'enter_dim_mode': ('dim', {}),
    'enter_blink_mode': ('blink', {}),
    'enter_underline_mode': ('smul', {}),
    'exit_underline_mode': ('rmul', {}),
    'enter_standout_mode': ('smso', {}),
    'exit_standout_mode': ('rmso', {}),
    'enter_reverse_mode': ('rev', {}),
    'exit_attribute_mode': ('sgr0', {}),
    'enter_italics_mode': ('sitm', {}),
    'exit_italics_mode': ('ritm', {}),
    # Colors (using match_any because color numbers vary)
    'set_a_foreground': ('setaf', {'nparams': 1, 'match_any': True, 'numeric': 1}),
    'set_a_background': ('setab', {'nparams': 1, 'match_any': True, 'numeric': 1}),
    'orig_pair': ('op', {}),
    # Cursor visibility
    'cursor_invisible': ('civis', {}),
    'cursor_visible': ('cvvis', {}),
    'cursor_normal': ('cnorm', {}),
    # Cursor save (does not move cursor, only saves position)
    'save_cursor': ('sc', {}),
    # Character sets
    'enter_alt_charset_mode': ('smacs', {}),
    'exit_alt_charset_mode': ('rmacs', {}),
    # Misc
    'bell': ('bel', {}),
    'flash_screen': ('flash', {}),
    'keypad_xmit': ('smkx', {}),
    'keypad_local': ('rmkx', {}),
    # Tab control (from blessed)
    'clear_all_tabs': ('tbc', {}),
    'set_tab': ('hts', {}),
    # Insert mode (from blessed)
    'exit_insert_mode': ('rmir', {}),
}

@dataclass(frozen=True)
class RenderContext:
    """Base render context."""

    def to_dict(self) -> dict[str, Any]:
        return {fld.name: getattr(self, fld.name) for fld in fields(self)}


@dataclass(frozen=True)
class TerminalCapsRenderCtx(RenderContext):
    """Render context for terminal capabilities."""
    terminals: List[str]
    horizontal_caps: Dict[str, str]
    indeterminate_caps: Dict[str, str]
    zero_width_caps: Dict[str, str]


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


def fetch_terminal_caps_data() -> TerminalCapsRenderCtx:
    """Fetch and process terminal capability patterns from terminfo."""
    print('extracting terminal capabilities: ', end='', flush=True)

    # Extract from terminfo only - modern patterns are in terminal_seqs.py
    horizontal = extract_all_terminals(TERMINALS, HORIZONTAL_MOVEMENT_TERMINFO)
    indeterminate = extract_all_terminals(TERMINALS, INDETERMINATE_TERMINFO)
    zero_width = extract_all_terminals(TERMINALS, ZERO_WIDTH_TERMINFO)

    print('ok')

    # Convert patterns to repr() form for valid Python source
    def repr_values(d: Dict[str, str]) -> Dict[str, str]:
        return {k: repr(v) for k, v in d.items()}

    return TerminalCapsRenderCtx(
        terminals=TERMINALS,
        horizontal_caps=repr_values(horizontal),
        indeterminate_caps=repr_values(indeterminate),
        zero_width_caps=repr_values(zero_width),
    )


def replace_if_modified(new_filename: str, original_filename: str) -> bool:
    """Replace original file with new file only if there are significant changes.

    If only the 'This code generated' timestamp line differs, discard the new file.
    If there are other changes or the original doesn't exist, replace it.
    """
    if os.path.exists(original_filename):
        with open(original_filename, 'r', encoding='utf-8') as f1, \
                open(new_filename, 'r', encoding='utf-8') as f2:
            old_lines = f1.readlines()
            new_lines = f2.readlines()

        diff_lines = list(difflib.unified_diff(old_lines, new_lines,
                                               fromfile=original_filename,
                                               tofile=new_filename,
                                               lineterm=''))

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
            os.remove(new_filename)
            return False

    os.replace(new_filename, original_filename)
    return True


def main() -> None:
    """Update terminal capability patterns."""
    context = fetch_terminal_caps_data()
    render_def = RenderDefinition(
        jinja_filename='terminal_caps.py.j2',
        output_filename=os.path.join(PATH_UP, 'wcwidth', '_generated_caps.py'),
        render_context=context,
    )

    new_filename = render_def.output_filename + '.new'
    with open(new_filename, 'w', encoding='utf-8', newline='\n') as fout:
        print(f'write {new_filename}: ', flush=True, end='')
        for data in render_def.generate():
            fout.write(data)

    if not replace_if_modified(new_filename, render_def.output_filename):
        print(f'discarded {new_filename} (timestamp-only change)')
    else:
        print('ok')


if __name__ == '__main__':
    main()
