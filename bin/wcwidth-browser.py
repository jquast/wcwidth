#!/usr/bin/env python
"""
A terminal browser, similar to less(1) for testing printable width of unicode.

This displays the full range of unicode points for 1 or 2-character wide
ideograms, with pipes ('|') that should always align for any terminal that
supports utf-8.

Usage:
  ./bin/wcwidth-browser.py [--wide=<n>]
                           [--alignment=<str>]
                           [--combining]
                           [--help]

Options:
  --wide=<int>        Browser 1 or 2 character-wide cells.
  --alignment=<str>   Chose left or right alignment. [default: left]
  --combining         Use combining character generator. [default: 2]
  --help              Display usage
"""
# pylint: disable=C0103,W0622
#         Invalid constant name "echo"
#         Invalid constant name "flushout" (col 4)
#         Invalid constant name "unichr" (col 8)
#         Invalid constant name "xrange" (col 8)
#         Invalid module name "wcwidth-browser"
#
#         Redefining built-in 'unichr' (col 8)
#         Redefining built-in 'xrange' (col 8)
#
# std imports
from __future__ import print_function
from __future__ import division
from functools import partial
import unicodedata
import string
import signal

# local
from wcwidth.wcwidth import wcwidth, ZERO_WIDTH

# 3rd-party
from blessed import Terminal
from docopt import docopt

# BEGIN, python 2.6 through 3.4 compatibilities,

#: print function alias, does not end with line terminator.
echo = partial(print, end='')

try:
    flushout = partial(print, end='', flush=True)
    flushout('')
except TypeError as err:
    # pylint: disable=W0704
    #         Except doesn't do anything (col 15)

    assert "'flush' is an invalid keyword argument" in err.args[0]

    def flushout():
        """flush any buffered output on standard out when called."""
        import sys
        # pylint: disable=E0602
        #         Undefined variable 'BrokenPipeError' (col 15)
        try:
            sys.stdout.flush()
        except BrokenPipeError:  # noqa
            pass


try:
    _ = unichr(0)
except NameError as err:
    if err.args[0] == "name 'unichr' is not defined":
        unichr = chr
    else:
        raise

try:
    _ = xrange(0)
except NameError as err:
    if err.args[0] == "name 'xrange' is not defined":
        xrange = range
    else:
        raise

# END, python 2.6 - 3.3 compatibilities

# some poor python builds (apple, etc.) are narrow, presumably
# for smaller memory footprint of character strings.
try:
    _ = unichr(0x10000)
    LIMIT_UCS = 0x3fffd
except ValueError as err:
    assert 'narrow Python build' in err.args[0], err.args
    LIMIT_UCS = 0x10000

#: printable length of highest unicode character
UCS_PRINTLEN = len('{value:0x}'.format(value=LIMIT_UCS))


class WcWideCharacterGenerator(object):

    """Generator yields unicode characters of the given ``width``."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)

    def __init__(self, width=2):
        """
        Class constructor.

        :param width: generate characters of given width.
        :type width: int
        """
        self.characters = (unichr(idx)
                           for idx in xrange(LIMIT_UCS)
                           if wcwidth(unichr(idx)) == width)

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
                continue
            return (ucs, name)

    # python 2.6 - 3.3 compatibility
    next = __next__


class WcCombinedCharacterGenerator(object):

    """Generator yields unicode characters with combining."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)

    def __init__(self, width=1):
        """
        Class constructor.

        :param width: generate characters of given width.
        :type width: int
        """
        self.characters = []
        letters_o = (u'o' * width)
        for boundaries in ZERO_WIDTH:
            for val in [_val for _val in
                        range(boundaries[0], boundaries[1] + 1)
                        if _val <= LIMIT_UCS]:
                self.characters.append(letters_o[:1] +
                                       unichr(val) +
                                       letters_o[wcwidth(unichr(val))+1:])
        self.characters.reverse()

    def __iter__(self):
        """Special method called by iter()."""
        return self

    def __next__(self):
        """Special method called by next()."""
        while True:
            if not self.characters:
                raise StopIteration
            ucs = self.characters.pop()
            try:
                name = string.capwords(unicodedata.name(ucs[1]))
            except ValueError:
                continue
            return (ucs, name)

    # python 2.6 - 3.3 compatibility
    next = __next__


class Style(object):

    """Styling decorator class instance for terminal output."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)
    attr_major = lambda self, text: text
    attr_minor = lambda self, text: text
    delimiter = u'|'
    continuation = u' $'
    header_hint = u'-'
    header_fill = u'='
    name_len = 10
    alignment = 'right'

    def __init__(self, **kwargs):
        """
        Class constructor.

        Any given keyword arguments are assigned to the class attribute
        of the same name.
        """
        for key, val in kwargs.items():
            setattr(self, key, val)


class Screen(object):

    """Represents terminal style, data dimensions, and drawables."""

    intro_msg_fmt = u'Delimiters ({delim}) should align.'

    def __init__(self, term, style, wide=2):
        """Class constructor."""
        self.term = term
        self.style = style
        self.wide = wide

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
                    len(u' '),
                    UCS_PRINTLEN + 2,
                    len(u' '),
                    self.style.name_len,))

    @property
    def head_item(self):
        """Text of a single column heading."""
        delimiter = self.style.attr_minor(self.style.delimiter)
        hint = self.style.header_hint * self.wide
        heading = (u'{delimiter}{hint}{delimiter}'
                   .format(delimiter=delimiter, hint=hint))
        alignment = lambda *args: (
            self.term.rjust(*args) if self.style.alignment == 'right' else
            self.term.ljust(*args))
        txt = alignment(heading, self.hint_width, self.style.header_fill)
        return self.style.attr_major(txt)

    @property
    def msg_intro(self):
        """Introductory message disabled above heading."""
        delim = self.style.attr_minor(self.style.delimiter)
        txt = self.intro_msg_fmt.format(delim=delim).rstrip()
        return self.term.center(txt)

    @property
    def row_ends(self):
        """Bottom of page."""
        return self.term.height - 1

    @property
    def num_columns(self):
        """Number of columns displayed."""
        if self.term.is_a_tty:
            return self.term.width // self.hint_width
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
        return self.num_rows * self.num_columns


class Pager(object):

    """A less(1)-like browser for browsing unicode characters."""

    #: screen state for next draw method(s).
    STATE_CLEAN, STATE_DIRTY, STATE_REFRESH = 0, 1, 2

    def __init__(self, term, screen, character_factory):
        """
        Class constructor.

        :param term: blessed Terminal class instance.
        :type term: blessed.Terminal
        :param screen: Screen class instance.
        :type screen: Screen
        :param character_factory: Character factory generator.
        :type character_factory: callable returning iterable.
        """
        self.term = term
        self.screen = screen
        self.character_factory = character_factory
        self.character_generator = self.character_factory(self.screen.wide)
        self.dirty = self.STATE_REFRESH
        self.last_page = 0
        self._page_data = list()

    def on_resize(self, *args):
        """Signal handler callback for SIGWINCH."""
        # pylint: disable=W0613
        #         Unused argument 'args'
        self.screen.style.name_len = min(self.screen.style.name_len,
                                         self.term.width - 15)
        assert self.term.width >= self.screen.hint_width, (
            'Screen to small {}, must be at least {}'.format(
                self.term.width, self.screen.hint_width))
        self._set_lastpage()
        self.dirty = self.STATE_REFRESH

    def _set_lastpage(self):
        """Calculate value of class attribute ``last_page``."""
        self.last_page = (len(self._page_data) - 1) // self.screen.page_size

    def display_initialize(self):
        """Display 'please wait' message, and narrow build warning."""
        echo(self.term.home + self.term.clear)
        echo(self.term.move_y(self.term.height // 2))
        echo(self.term.center('Initializing page data ...').rstrip())
        flushout()

        if LIMIT_UCS == 0x10000:
            echo('\n\n')
            echo(self.term.blink_red(self.term.center(
                'narrow Python build: upperbound value is {n}.'
                .format(n=LIMIT_UCS)).rstrip()))
            echo('\n\n')
            flushout()

    def initialize_page_data(self):
        """Initialize the page data for the given screen."""
        if self.term.is_a_tty:
            self.display_initialize()
        self.character_generator = self.character_factory(self.screen.wide)
        page_data = list()
        while True:
            try:
                page_data.append(next(self.character_generator))
            except StopIteration:
                break
        if LIMIT_UCS == 0x10000:
            echo(self.term.center('press any key.').rstrip())
            flushout()
            self.term.inkey(timeout=None)
        return page_data

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

    def _run_notty(self, writer):
        """Pager run method for terminals that are not a tty."""
        page_idx = page_offset = 0
        while True:
            npage_idx, _ = self.draw(writer, page_idx + 1, page_offset)
            if npage_idx == self.last_page:
                # page displayed was last page, quit.
                break
            page_idx = npage_idx
            self.dirty = self.STATE_DIRTY
        return

    def _run_tty(self, writer, reader):
        """Pager run method for terminals that are a tty."""
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
            if not self.dirty:
                self.dirty = nxt != page_idx or noff != page_offset
            page_idx, page_offset = nxt, noff
            if page_idx == -1:
                return

    def run(self, writer, reader):
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
        self._page_data = self.initialize_page_data()
        self._set_lastpage()
        if not self.term.is_a_tty:
            self._run_notty(writer)
        else:
            self._run_tty(writer, reader)

    def process_keystroke(self, inp, idx, offset):
        """
        Process keystroke ``inp``, adjusting screen parameters.

        :param inp: return value of Terminal.inkey().
        :type inp: blessed.keyboard.Keystroke
        :param idx: page index.
        :type idx: int
        :param offset: scrolling region offset of current page.
        :type offset: int
        :returns: tuple of next (idx, offset).
        :rtype: (int, int)
        """
        if inp.lower() in (u'q', u'Q'):
            # exit
            return (-1, -1)
        self._process_keystroke_commands(inp)
        idx, offset = self._process_keystroke_movement(inp, idx, offset)
        return idx, offset

    def _process_keystroke_commands(self, inp):
        """Process keystrokes that issue commands (side effects)."""
        if inp in (u'1', u'2'):
            # chose 1 or 2-character wide
            if int(inp) != self.screen.wide:
                self.screen.wide = int(inp)
                self.on_resize(None, None)
        elif inp in (u'_', u'-'):
            # adjust name length -2
            nlen = max(1, self.screen.style.name_len - 2)
            if nlen != self.screen.style.name_len:
                self.screen.style.name_len = nlen
                self.on_resize(None, None)
        elif inp in (u'+', u'='):
            # adjust name length +2
            nlen = min(self.term.width - 8, self.screen.style.name_len + 2)
            if nlen != self.screen.style.name_len:
                self.screen.style.name_len = nlen
                self.on_resize(None, None)
        elif inp == u'2' and self.screen.wide != 2:
            # change 2 or 1-cell wide view
            self.screen.wide = 2
            self.on_resize(None, None)

    def _process_keystroke_movement(self, inp, idx, offset):
        """Process keystrokes that adjust index and offset."""
        term = self.term
        if inp in (u'y', u'k') or inp.code in (term.KEY_UP,):
            # scroll backward 1 line
            idx, offset = (idx, offset - self.screen.num_columns)
        elif inp in (u'e', u'j') or inp.code in (term.KEY_ENTER,
                                                 term.KEY_DOWN,):
            # scroll forward 1 line
            idx, offset = (idx, offset + self.screen.num_columns)
        elif inp in (u'f', u' ') or inp.code in (term.KEY_PGDOWN,):
            # scroll forward 1 page
            idx, offset = (idx + 1, offset)
        elif inp == u'b' or inp.code in (term.KEY_PGUP,):
            # scroll backward 1 page
            idx, offset = (max(0, idx - 1), offset)
        elif inp.code in (term.KEY_SDOWN,):
            # scroll forward 10 pages
            idx, offset = (max(0, idx + 10), offset)
        elif inp.code in (term.KEY_SUP,):
            # scroll forward 10 pages
            idx, offset = (max(0, idx - 10), offset)
        elif inp.code == term.KEY_HOME:
            # top
            idx, offset = (0, 0)
        elif inp.code == term.KEY_END:
            # bottom
            idx, offset = (self.last_page, 0)
        return idx, offset

    def draw(self, writer, idx, offset):
        """
        Draw the current page view to ``writer``.

        :param writer: callable writes to output stream, receiving unicode.
        :type writer: callable
        :param idx: current page index.
        :type idx: int
        :param offset: scrolling region offset of current page.
        :type offset: int
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

        :param writer: callable writes to output stream, receiving unicode.
        :returns: True if class attribute ``dirty`` is ``STATE_REFRESH``.
        """
        if self.dirty == self.STATE_REFRESH:
            writer(u''.join(
                (self.term.home, self.term.clear,
                 self.screen.msg_intro, '\n',
                 self.screen.header, '\n',)))
            return True

    def draw_status(self, writer, idx):
        """
        Conditionally draw status bar when output terminal is a tty.

        :param writer: callable writes to output stream, receiving unicode.
        :param idx: current page position index.
        :type idx: int
        """
        if self.term.is_a_tty:
            writer(self.term.hide_cursor())
            style = self.screen.style
            writer(self.term.move(self.term.height - 1))
            if idx == self.last_page:
                last_end = u'(END)'
            else:
                last_end = u'/{0}'.format(self.last_page)
            txt = (u'Page {idx}{last_end} - '
                   u'{q} to quit, [keys: {keyset}]'
                   .format(idx=style.attr_minor(u'{0}'.format(idx)),
                           last_end=style.attr_major(last_end),
                           keyset=style.attr_major('kjfb12-='),
                           q=style.attr_minor(u'q')))
            writer(self.term.center(txt).rstrip())

    def page_view(self, data):
        """
        Generator yields text to be displayed for the current unicode pageview.

        :param data: The current page's data as tuple of ``(ucs, name)``.
        :rtype: generator
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
                    val = u''.join((val, clear_eol, u'\n'))
                else:
                    val = u''.join((val.rstrip(), u'\n'))
            yield val

        if self.term.is_a_tty:
            yield u''.join((clear_eol, u'\n', clear_eos))

    def text_entry(self, ucs, name):
        """
        Display a single column segment row describing ``(ucs, name)``.

        :param ucs: target unicode point character string.
        :param name: name of unicode point.
        :rtype: unicode
        """
        style = self.screen.style
        if len(name) > style.name_len:
            idx = max(0, style.name_len - len(style.continuation))
            name = u''.join((name[:idx], style.continuation if idx else u''))
        if style.alignment == 'right':
            fmt = u' '.join(('0x{val:0>{ucs_printlen}x}',
                             '{name:<{name_len}s}',
                             '{delimiter}{ucs}{delimiter}'
                             ))
        else:
            fmt = u' '.join(('{delimiter}{ucs}{delimiter}',
                             '0x{val:0>{ucs_printlen}x}',
                             '{name:<{name_len}s}'))
        delimiter = style.attr_minor(style.delimiter)
        if len(ucs) != 1:
            # determine display of combining characters
            val = ord(ucs[1])
            # a combining character displayed of any fg color
            # will reset the foreground character of the cell
            # combined with (iTerm2, OSX).
            disp_ucs = style.attr_major(ucs[0:2])
            if len(ucs) > 2:
                disp_ucs += ucs[2]
        else:
            # non-combining
            val = ord(ucs)
            disp_ucs = style.attr_major(ucs)

        return fmt.format(name_len=style.name_len,
                          ucs_printlen=UCS_PRINTLEN,
                          delimiter=delimiter,
                          name=name,
                          ucs=disp_ucs,
                          val=val)


def validate_args(opts):
    """Validate and return options provided by docopt parsing."""
    if opts['--wide'] is None:
        opts['--wide'] = 2
    else:
        assert opts['--wide'] in ("1", "2"), opts['--wide']
    if opts['--alignment'] is None:
        opts['--alignment'] = 'left'
    else:
        assert opts['--alignment'] in ('left', 'right'), opts['--alignment']
    opts['--wide'] = int(opts['--wide'])
    opts['character_factory'] = WcWideCharacterGenerator
    if opts['--combining']:
        opts['character_factory'] = WcCombinedCharacterGenerator
    return opts


def main(opts):
    """Program entry point."""
    term = Terminal()
    style = Style()

    # if the terminal supports colors, use a Style instance with some
    # standout colors (magenta, cyan).
    if term.number_of_colors:
        style = Style(attr_major=term.magenta,
                      attr_minor=term.bright_cyan,
                      alignment=opts['--alignment'])
    style.name_len = term.width - 15

    screen = Screen(term, style, wide=opts['--wide'])
    pager = Pager(term, screen, opts['character_factory'])

    with term.location(), term.cbreak(), \
            term.fullscreen(), term.hidden_cursor():
        pager.run(writer=echo, reader=term.inkey)
    return 0

if __name__ == '__main__':
    exit(main(validate_args(docopt(__doc__))))
