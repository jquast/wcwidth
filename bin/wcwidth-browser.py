#!/usr/bin/env python
"""
A terminal browser and automatic testing tool for Zero, narrow, wide, and emoji ZWJ.

This displays the full range of unicode points for 1 or 2-character wide
ideograms, with pipes ('|') that should align for terminals that
supports utf-8.
"""
# pylint: disable=C0103,W0622
#         Invalid constant name "echo"
#         Invalid constant name "flushout" (col 4)
#         Invalid module name "wcwidth-browser"
from __future__ import division, print_function
import platform
import contextlib
import os

# std imports
import sys
import time
import signal
import string
import argparse
import functools
import unicodedata

# 3rd party
import blessed
import psutil
import yaml

# local
import wcwidth
from wcwidth import ZERO_WIDTH, wcwidth, list_versions, _wcmatch_version, EMOJI_ZWJ_SEQUENCES

#: print function alias, does not end with line terminator.
echo = functools.partial(print, end='')
flushout = functools.partial(print, end='', flush=True)

#: range of highest unicode character displayed for testing
LIMIT_UCS = 0x2ffff

#: printable length of highest unicode character description
UCS_PRINTLEN = len('{value:0x}'.format(value=LIMIT_UCS))

def readline(term, width):
    """A rudimentary readline implementation."""
    text = ''
    while True:
        inp = term.inkey()
        if inp.code == term.KEY_ENTER:
            break
        if inp.code == term.KEY_ESCAPE:
            text = ''
            break
        if not inp.is_sequence and len(text) < width:
            text += inp
            echo(inp)
            flushout()
        elif inp.code in (term.KEY_BACKSPACE, term.KEY_DELETE):
            if text:
                text = text[:-1]
                echo('\b \b')
            flushout()
    return text

def save_report(records, session_metadata):
    """
    save 'records' to yaml file in data/ folder.
    """
    records_filepath = os.path.join(
        os.path.dirname(__file__), os.pardir,
        'data', f'record-{int(time.time())}.yaml')
    with open(records_filepath, 'w') as fout:
        yaml.safe_dump({
            'session_metadata': session_metadata,
            'mismatch_records': records,
        }, fout)

@contextlib.contextmanager
def activate_terminal(term, automatic=False):
    if automatic:
        with term.location():
            yield
        return
    else:
        with term.fullscreen(), term.location(), term.cbreak(), term.hidden_cursor():
            yield

def fetch_terminal_metadata(term, unicode_version):
    """
    """
    parent_processes = psutil.Process(os.getpid()).parents()[:-1]
    return {
        # this is just to try to help identify the terminal software, xterm etc.
        # it can be hard to predict at what and how many layers our terminal process
        # is from ours.
        'parent_exes': [p.exe() for p in parent_processes],
        'terminal': {
            'width': term.width,
            'height': term.height,
        },
        'user_input': {},
        'unicode_version': _wcmatch_version(unicode_version),
        'python_version': platform.python_version(),
        'system': platform.system(),
        'date': time.strftime('%Y-%m-%d %H:%M:%S %z'),
    }


class WcWideCharacterGenerator(object):
    """Generator yields unicode characters of the given ``width``."""
    width = 2

    # pylint: disable=R0903
    #         Too few public methods (0/2)
    def __init__(self, unicode_version):
        """
        Class constructor.

        :param str unicode_version: Unicode Version for render.
        """
        self.characters = (
            chr(idx) for idx in range(LIMIT_UCS)
            if wcwidth(chr(idx), unicode_version=unicode_version) == self.width)

    def __iter__(self):
        """Special method called by iter()."""
        return self

    def __next__(self):
        """Special method called by next()."""
        while True:
            ucs = next(self.characters)
            try:
                name = string.capwords(unicodedata.name(ucs))
            except ValueError:
                # it isn't worth troubleshooting unnamed characters.
                continue
            return (ucs, name)

class WcNarrowCharacterGenerator(WcWideCharacterGenerator):
    """
    Generator yields a sequence for testing 1-width characters.
    """
    width = 1

class WcZeroCharacterGenerator(WcWideCharacterGenerator):
    """
    Generator yields a sequence for testing zero-width characters.
    
    TODO: Because of the nature of zero-width characters, they have special
    meaning in context of the characters that preceed or follow, but, our test
    makes no efforts to accomodate those at this time.
    """
    width = 0
    # TODO: properly co-joined combining characters !
    # by overriding next(), 

class WcEmojiZwjSequenceGenerator(object):
    """Generator yields "Recommended" Emoji ZWJ Sequences."""

    def __init__(self, unicode_version):
        """
        Class constructor.

        :param str unicode_version: Unicode version.
        """
        self.characters = []
        # find 'latest' by depending on dictionary key order (because we didn't
        # write a nice _wcmatch_version() for this single use case), but you are
        # free to specify an exact version ('v'), but when unmatched, the latest
        # is used.
        latest_str = list(EMOJI_ZWJ_SEQUENCES.keys())[-1]
        sequence_table = EMOJI_ZWJ_SEQUENCES[latest_str]
        if unicode_version in EMOJI_ZWJ_SEQUENCES:
            sequence_table = EMOJI_ZWJ_SEQUENCES[unicode_version]
        for sequence in sequence_table:
            self.characters.append(''.join(chr(val) for val in sequence))

    def __iter__(self):
        """Special method called by iter()."""
        return self

    def __next__(self):
        """
        Special method called by next().

        :return: unicode character and name, as tuple.
        :rtype: tuple[unicode, unicode]
        :raises StopIteration: no more characters
        """
        while True:
            if not self.characters:
                raise StopIteration
            seq = self.characters.pop()
            try:
                # TODO: shorten to 'ZWJ' ?
                name = ', '.join(string.capwords(unicodedata.name(ucs)) for ucs in seq)
            except ValueError:
                continue
            return (seq, name)


class Style(object):
    """Styling decorator class instance for terminal output."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)
    @staticmethod
    def attr_major(text):
        """non-stylized callable for "major" text, for non-ttys."""
        return text

    @staticmethod
    def attr_minor(text):
        """non-stylized callable for "minor" text, for non-ttys."""
        return text

    @staticmethod
    def attr_text(text):
        """non-stylized callable for "ucs" text."""
        return text

    delimiter = '|'
    continuation = ' $'
    header_hint = '-'
    header_fill = '='
    name_len = 10

    def __init__(self, **kwargs):
        """
        Class constructor.

        Any given keyword arguments are assigned to the class attribute of the same name.
        """
        for key, val in kwargs.items():
            setattr(self, key, val)


class Screen(object):
    """Represents terminal style, data dimensions, and drawables."""

    intro_msg_fmt = ('Delimiters ({delim}) should align, '
                     'unicode version is {version}.')

    def __init__(self, term, style, test_type='wide'):
        """Class constructor."""
        self.term = term
        self.style = style
        self.columns = 79 if not term.is_a_tty else term.width
        self.change_test_type(test_type)

    def change_test_type(self, test_type):
        self.test_type = test_type    
        self.wide = {
            'wide': 2,
            'narrow': 1,
            'zero': 0,
            'emoji-zwj': 2
        }[test_type]

    @property
    def header(self):
        """Text of joined segments producing full heading."""
        return self.head_item * self.num_columns

    @property
    def hint_width(self):
        """Width of a column segment."""
        return sum((len(self.style.delimiter),
                    self.wide,
                    len(self.style.delimiter),
                    len(' '),
                    self.style.name_len,))

    @property
    def head_item(self):
        """Text of a single column heading."""
        delimiter = self.style.attr_minor(self.style.delimiter)
        hint = self.style.header_hint * self.wide
        heading = ('{delimiter}{hint}{delimiter}'.format(delimiter=delimiter, hint=hint))

        txt = self.term.ljust(heading, self.hint_width, self.style.header_fill)
        return self.style.attr_major(txt)

    def msg_intro(self, version):
        """Introductory message disabled above heading."""
        return self.term.center(self.intro_msg_fmt.format(
            delim=self.style.attr_minor(self.style.delimiter),
            version=self.style.attr_minor(version))).rstrip()

    @property
    def row_ends(self):
        """Bottom of page."""
        return self.term.height - 1

    @property
    def num_columns(self):
        """Number of columns displayed."""
        if self.term.is_a_tty:
            return max(1, (self.term.width - 1) // self.hint_width)
        return 1

    @property
    def num_rows(self):
        """Number of rows displayed."""
        return self.row_ends - self.row_begins - 1

    @property
    def row_begins(self):
        """Top row displayed for content."""
        # pylint: disable=R0201
        # Method could be a function (col 4)
        return 2

    @property
    def page_size(self):
        """Number of unicode text displayed per page."""
        assert self.num_rows, self.num_rows
        assert self.num_columns, self.num_columns
        return self.num_rows * self.num_columns


class Pager(object):
    """A less(1)-like browser for browsing unicode characters."""
    # pylint: disable=too-many-instance-attributes

    #: screen state for next draw method(s).
    STATE_CLEAN, STATE_DIRTY, STATE_REFRESH = 0, 1, 2

    def __init__(self, term: blessed.Terminal, screen, test_type, unicode_version='auto'):
        """
        Class constructor.
        """
        self.term = term
        self.screen = screen
        self.unicode_version = unicode_version
        self.test_type = test_type
        self.dirty = self.STATE_REFRESH
        self.last_page = 0
        self._page_data = list()

    def on_resize(self, *args):
        """Signal handler callback for SIGWINCH."""
        # pylint: disable=W0613
        #         Unused argument 'args'
        self._set_lastpage()
        self.dirty = self.STATE_REFRESH

    def _set_lastpage(self):
        """Calculate value of class attribute ``last_page``."""
        self.last_page = (len(self._page_data) - 1) // self.screen.page_size

    def display_initialize(self):
        """Display 'please wait' message, and narrow build warning."""
        echo(self.term.home + self.term.clear)
        echo(self.term.move_y(self.term.height // 2))
        echo(self.term.center(self.term.black_on_cyan('Initializing page data ...')).rstrip())
        flushout()

    def initialize_page_data(self, test_type=None):
        """Initialize the page data for the given screen."""
        # pylint: disable=attribute-defined-outside-init
        if self.term.is_a_tty:
            self.display_initialize()
        self._page_data = list()
        self.test_type = test_type or self.test_type
        self.character_generator = {
            'zero': WcZeroCharacterGenerator,
            'narrow': WcNarrowCharacterGenerator,
            'wide': WcWideCharacterGenerator,
            'emoji-zwj': WcEmojiZwjSequenceGenerator,
        }[self.test_type](self.unicode_version)

        while True:
            try:
                self._page_data.append(next(self.character_generator))
            except StopIteration:
                break
        self._set_lastpage()

    def page_data(self, idx, offset):
        """
        Return character data for page of given index and offset.

        :param idx: page index.
        :type idx: int
        :param offset: scrolling region offset of current page.
        :type offset: int
        :returns: list of tuples in form of ``(ucs, name)``
        :rtype: list[(unicode, unicode)]
        """
        size = self.screen.page_size

        while offset < 0 and idx:
            offset += size
            idx -= 1
        offset = max(0, offset)

        while offset >= size:
            offset -= size
            idx += 1

        if idx == self.last_page:
            offset = 0
        idx = min(max(0, idx), self.last_page)

        start = (idx * self.screen.page_size) + offset
        end = start + self.screen.page_size
        return (idx, offset), self._page_data[start:end]

    def run_without_tty(self, writer):
        """Pager run method for terminals that are not a tty."""
        page_idx = page_offset = 0
        while True:
            npage_idx, _ = self.draw(writer, page_idx + 1, page_offset)
            if npage_idx == self.last_page:
                # page displayed was last page, quit.
                break
            page_idx = npage_idx
            self.dirty = self.STATE_DIRTY

    def run_automatic_test(self):
        """
        Automatic test method for terminals that are a tty and respond to cursor position sequence
        """
        writer = echo
        #reader = term.inkey

        # sequence clears to end-of-line
        clear_eol = self.term.clear_eol
        # sequence clears to end-of-screen
        clear_eos = self.term.clear_eos
        style_completed = Style(attr_major=self.term.bold_black,
                                attr_minor=self.term.bold_black,
                                attr_text=self.term.bold_black,
                                name_len=self.screen.style.name_len)
        style_failed = Style(attr_major=self.term.bright_red,
                             attr_minor=self.term.bright_red,
                             attr_text=self.term.bright_red,
                             name_len=self.screen.style.name_len)

        def measure_distance(ucs: str, name: str):
            y, x = self.term.get_location()
            writer(self.text_entry(ucs, name), end='')
            ny, nx = self.term.get_location()
            assert y == ny, ("y position is out of control on ucs value=", hex(ord(ucs)) if len(ucs) == 1 else repr(ucs))
            if y == ny:
                return nx - x

        def redraw_text_entry(ucs: str, name: str, style: Style):
            """Redraw over previously drawn entry with given blessed term_attr()"""
            writer('\b' * self.screen.hint_width)
            writer(self.text_entry(ucs, name, style=style), end='')
 
        records = list()
        stime = time.monotonic()
        session_metadata = fetch_terminal_metadata(self.term, unicode_version=self.unicode_version)
        session_metadata['user_input']['Terminal Software'] = input('Enter "Terminal Software": ')
        session_metadata['user_input']['Software version'] = input('Enter "Software Version": ')
        with self.term.cbreak():
            for test_type in ('narrow', 'wide', 'zero', 'emoji-zwj'):
                self.initialize_page_data(test_type)
                self.screen.change_test_type(test_type)
                page_idx = page_offset = idx = offset = 0
                self.term.move(self.screen.row_begins, 0)
                while True:
                    self.draw_heading(writer)
                    (idx, offset), data = self.page_data(idx, offset)
                    col = 0
                    for ucs, name in data:
                        try:
                            distance = measure_distance(ucs, name)
                            delta = self.screen.hint_width - distance
                        except AssertionError:
                            # drew past newline boundry, just re-execute the same test
                            try:
                                distance = measure_distance(ucs, name)
                                delta = self.screen.hint_width - distance
                            except AssertionError:
                                delta = 'Vertical Error'
                        if delta != 0:
                            # mark failed
                            records.append({'ucs': repr(ucs)[1:-1],
                                                    'named': name,
                                                    'delta': delta,
                                                    'test_type': test_type})
                            redraw_text_entry(ucs, name, style=style_failed)
                        else:
                            # mark completed
                            redraw_text_entry(ucs, name, style=style_completed)
                        col += 1
                        if col == self.screen.num_columns:
                            col = 0
                            writer(clear_eol + '\n')
                    writer(clear_eol)
                    self.draw_status(writer, idx, automatic=True)
                    if idx == self.last_page:
                        # page displayed was last page, quit.
                        break
                    idx += 1
        
        session_metadata['seconds_elapsed'] = time.monotonic() - stime
        # save 'records' to toml file in data/ folder
        save_report(records, session_metadata)


    def run_with_tty(self, writer, reader):
        """
        Pager run method for terminals that are a tty.

        When automatic_test is set, it is a filename for which a report
        output file of results of automatic test.
        """
        # allow window-change signal to reflow screen
        signal.signal(signal.SIGWINCH, self.on_resize)

        page_idx = page_offset = 0
        while True:
            if self.dirty:
                page_idx, page_offset = self.draw(writer,
                                                  page_idx,
                                                  page_offset)
                self.dirty = self.STATE_CLEAN
            inp = reader(timeout=0.25)
            if inp is not None:
                nxt, noff = self.process_keystroke(inp,
                                                   page_idx,
                                                   page_offset)
                if (-1, -1) == (nxt, noff):
                    # 'quit' semaphore
                    return
                if self.dirty:
                    continue
            if not self.dirty:
                self.dirty = nxt != page_idx or noff != page_offset
            assert nxt != -1, (page_idx, page_offset, nxt, noff)
            page_idx, page_offset = nxt, noff

    def run(self, writer, reader, automatic=False):
        """
        Pager entry point.

        In interactive mode (terminal is a tty), run until
        ``process_keystroke()`` detects quit keystroke ('q').  In
        non-interactive mode, exit after displaying all unicode points.

        :param writer: callable writes to output stream, receiving unicode.
        :type writer: callable
        :param reader: callable reads keystrokes from input stream, sending
                       instance of blessed.keyboard.Keystroke.
        :type reader: callable
        """
        if automatic:
            return self.run_automatic_test()
        self.initialize_page_data()
        if not self.term.is_a_tty:
            return self.run_without_tty(writer)
        self.run_with_tty(writer, reader)

    def process_keystroke(self, inp, idx, offset):
        """
        Process keystroke ``inp``, adjusting screen parameters.

        :param inp: return value of blessed.Terminal.inkey().
        :type inp: blessed.keyboard.Keystroke
        :param idx: page index.
        :type idx: int
        :param offset: scrolling region offset of current page.
        :type offset: int
        :returns: tuple of next (idx, offset).
        :rtype: (int, int)
        """
        if inp.lower() in ('q', 'Q'):
            # exit
            return (-1, -1)
        if self._process_keystroke_commands(inp):
            self.on_resize(None, None)
        idx, offset = self._process_keystroke_movement(inp, idx, offset)
        return idx, offset

    def _process_keystroke_commands(self, inp) -> bool:
        """Process keystrokes that issue commands (side effects).
        
        :param inp: return value of blessed.Terminal.inkey().
        :returns: True if command was processed and screen should be refreshed.
        """
        if inp == 'n':
            # switch-to narrow (1-cell) characters
            self.screen.wide = 1
            self.initialize_page_data('narrow')
        elif inp == 'w':
            # switch-to wide (2-cell) characters
            self.screen.wide = 2
            self.initialize_page_data('wide')
        elif inp == 'e':
            # switch to emoji zwj sequence test
            self.screen.wide = 11
            self.initialize_page_data('emoji-zwj')
        elif inp == 'z':
            # switch to zero-width characters
            self.screen.wide = 1
            self.initialize_page_data('zero')
        elif inp in ('_', '-', '+', '=') or inp.code in (self.term.KEY_LEFT,self.term.KEY_RIGHT):
            # adjust name length -2
            olen = self.screen.style.name_len
            if inp in ('_', '-') or inp.code in (self.term.KEY_LEFT,):
                nlen = max(9, self.screen.style.name_len - 2)
            else:
                nlen = min(self.term.width - self.screen.wide - 4, self.screen.style.name_len + 2)
            if nlen != olen:
                self.screen.style.name_len = nlen
        elif inp == 'v':
            # set "unicode_version"
            with self.term.location(x=0, y=self.term.height - 2):
                echo(self.term.clear_eos)
                input_selection_msg = (
                    "--> Enter unicode version [{versions}] ("
                    "current: {self.unicode_version}):".format(
                        versions=', '.join(list_versions()),
                        self=self))
                echo('\n'.join(self.term.wrap(input_selection_msg,
                                              subsequent_indent='    ')))
                echo(' ')
                flushout()
                inp = readline(self.term, width=max(map(len, list_versions())))
                if inp.strip() and inp != self.unicode_version:
                    # set new unicode version -- page data must be
                    # re-initialized. *Any* version is legal, underlying
                    # library performs best-match (with warnings)
                    self.unicode_version = _wcmatch_version(inp)
                    self.initialize_page_data()
        else:
            return False
        return True

    def _process_keystroke_movement(self, inp, idx, offset):
        """Process keystrokes that adjust index and offset."""
        term = self.term
        # a little vi-inspired.
        if inp in ('y', 'k') or inp.code in (term.KEY_UP,):
            # scroll backward 1 line
            offset -= self.screen.num_columns
        elif inp in ('e', 'j') or inp.code in (term.KEY_ENTER,
                                               term.KEY_DOWN,):
            # scroll forward 1 line
            offset = offset + self.screen.num_columns
        elif inp in ('f', ' ') or inp.code in (term.KEY_PGDOWN,):
            # scroll forward 1 page
            idx += 1
        elif inp == 'b' or inp.code in (term.KEY_PGUP,):
            # scroll backward 1 page
            idx = max(0, idx - 1)
        elif inp == 'F' or inp.code in (term.KEY_SDOWN,):
            # scroll forward 10 pages
            idx = max(0, idx + 10)
        elif inp == 'B' or inp.code in (term.KEY_SUP,):
            # scroll backward 10 pages
            idx = max(0, idx - 10)
        elif inp.code == term.KEY_HOME:
            # top
            idx, offset = (0, 0)
        elif inp == 'G' or inp.code == term.KEY_END:
            # bottom
            idx, offset = (self.last_page, 0)
        elif inp == '\x0c':  # ctrl-L
            self.dirty = True
        return idx, offset

    def draw(self, writer, idx, offset):
        """
        Draw the current page view to ``writer``.

        :param callable writer: callable writes to output stream, receiving unicode.
        :param int idx: current page index.
        :param int offset: scrolling region offset of current page.
        :returns: tuple of next (idx, offset).
        :rtype: (int, int)
        """
        # as our screen can be resized while we're mid-calculation,
        # our self.dirty flag can become re-toggled; because we are
        # not re-flowing our pagination, we must begin over again.
        while self.dirty:
            self.draw_heading(writer)
            self.dirty = self.STATE_CLEAN
            (idx, offset), data = self.page_data(idx, offset)
            for txt in self.page_view(data):
                writer(txt)
        self.draw_status(writer, idx)
        flushout()
        return idx, offset

    def draw_heading(self, writer):
        """
        Conditionally redraw screen when ``dirty`` attribute is valued REFRESH.

        When Pager attribute ``dirty`` is ``STATE_REFRESH``, cursor is moved
        to (0,0), screen is cleared, and heading is displayed.

        :param callable writer: callable writes to output stream, receiving unicode.
        :return: True if class attribute ``dirty`` is ``STATE_REFRESH``.
        :rtype: bool
        """
        if self.dirty == self.STATE_REFRESH:
            writer(''.join(
                (self.term.home,
                 self.screen.msg_intro(version=self.unicode_version), '\n',
                 self.screen.header, '\n',)))
            return True
        return False

    def draw_status(self, writer, idx, automatic=False, n_failed=0):
        """
        Conditionally draw status bar when output terminal is a tty.

        :param callable writer: callable writes to output stream, receiving unicode.
        :param int idx: current page position index.
        :type idx: int
        """
        if self.term.is_a_tty:
            style = self.screen.style
            writer(self.term.move(self.term.height - 1))
            if idx == self.last_page:
                last_end = '(END)'
            else:
                last_end = '/{0}'.format(self.last_page)
            maybe_keyset = '- {q} to quit, [keys: {keyset}]'.format(
                q=style.attr_minor('q'),
                keyset=style.attr_major('kjfbvc12-=')) if not automatic else ''
            maybe_errors = (' - {n_failed} errors'.format(n_failed=n_failed)
                                if n_failed and automatic else '')
            txt = ('Page {idx}{last_end}{maybe_keyset}{maybe_errors}'
                   .format(idx=style.attr_minor('{0}'.format(idx)),
                           last_end=style.attr_major(last_end),
                           maybe_keyset=maybe_keyset,
                           maybe_errors=maybe_errors))
            writer(self.term.center(txt).rstrip())

    def page_view(self, data):
        """
        Generator yields text to be displayed for the current unicode pageview.

        :param list[(unicode, unicode)] data: The current page's data as tuple
            of ``(ucs, name)``.
        :returns: generator for full-page text for display
        """
        if self.term.is_a_tty:
            yield self.term.move(self.screen.row_begins, 0)
        # sequence clears to end-of-line
        clear_eol = self.term.clear_eol
        # sequence clears to end-of-screen
        clear_eos = self.term.clear_eos

        # track our current column and row, where column is
        # the whole segment of unicode value text, and draw
        # only self.screen.num_columns before end-of-line.
        #
        # use clear_eol at end of each row to erase over any
        # "ghosted" text, and clear_eos at end of screen to
        # clear the same, especially for the final page which
        # is often short.
        col = 0
        for ucs, name in data:
            val = self.text_entry(ucs, name)
            col += 1
            if col == self.screen.num_columns:
                col = 0
                if self.term.is_a_tty:
                    val = ''.join((val, clear_eol, '\n'))
                else:
                    val = ''.join((val.rstrip(), '\n'))
            yield val

        if self.term.is_a_tty:
            yield ''.join((clear_eol, '\n', clear_eos))

    def text_entry(self, ucs, name, style=None):
        """
        Display a single column segment row describing ``(ucs, name)``.

        :param str ucs: target unicode point character string.
        :param str name: name of unicode point.
        :return: formatted text for display.
        :rtype: unicode
        """
        style = style or self.screen.style
        fmt = '{delimiter}{ucs}{delimiter}{name_val}'
        delimiter = style.attr_minor(style.delimiter)
        if len(ucs) > 1:
            # emoji zwj sequence
            val = ','.join([
                f'0x{ord(chr):0>{UCS_PRINTLEN}x}'
                for chr in ucs])
        else:
            # single char (zero, narrow, or wide)
            val = f'0x{ord(ucs[0]):0>{UCS_PRINTLEN}x}'

        name_val = val + ' ' + name
        name_len = len(name_val)
        if name_len > style.name_len:
            name_val = name_val[:style.name_len - len(style.continuation)] + style.continuation
        name_val = f' {name_val:<{style.name_len}s}'
        return fmt.format(name_len=style.name_len,
                          ucs_printlen=UCS_PRINTLEN,
                          delimiter=delimiter,
                          name_val=name_val,
                          ucs=ucs)


def main(test_type, unicode_version, automatic):
    """Program entry point."""
    term = blessed.Terminal()
    style = Style()

    # if the terminal supports colors, use a Style instance with some
    # standout colors (magenta, cyan).
    if term.number_of_colors:
        style = Style(attr_major=term.magenta,
                      attr_minor=term.bright_cyan)
    style.name_len = term.width // 4 if not automatic else 9
    screen = Screen(term=term, style=style, test_type=test_type)
    pager = Pager(term=term, screen=screen, test_type=test_type,
                  unicode_version=(unicode_version or 'auto'))
    with activate_terminal(term, automatic=automatic):
        pager.run(writer=echo, reader=term.inkey, automatic=automatic)
    return 0

def parse_args():
    """Parse command line arguments."""
    args = argparse.ArgumentParser()
    args.add_argument('--test-type', default='wide',
                      choices=('wide', 'narrow', 'zero', 'emoji-zwj'),
                      help='Character type for interactive viewing.')
    args.add_argument('--unicode-version', default='auto',
                      help='Unicode version for testing.')
    args.add_argument('--automatic', action='store_true',
                      help='Perform automatic testing.')
    return vars(args.parse_args())

if __name__ == '__main__':
    sys.exit(main(**parse_args()))
