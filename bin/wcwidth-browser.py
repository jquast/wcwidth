#!/usr/bin/env python

# standard imports
from __future__ import print_function
from __future__ import division
from functools import partial
import unicodedata
import string
import signal

# local imports
from wcwidth import wcwidth

# 3rd party imports
from blessed import Terminal

# BEGIN, python 2.6 through 3.4 compatibilities,

echo = partial(print, end='')

try:
    flushout = partial(print, end='', flush=True)
    flushout('')
except TypeError as err:
    assert "'flush' is an invalid keyword argument" in err.args[0]

    def flushout():
        import sys
        try:
            sys.stdout.flush()
        except BrokenPipeError:
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
    import warnings
    import time
    warnings.warn('narrow Python build, only a small subset of '
                  'characters may be represented.')
    time.sleep(3)


class WcWideCharacterGenerator(object):
    " generates unicode characters of the presumed terminal width "
    def __init__(self, width=2):
        """
        ``cjk``
          Treat ambiguous-width characters as double-width
        """
        self.characters = (unichr(idx)
                           for idx in xrange(LIMIT_UCS)
                           if wcwidth(unichr(idx)) == width
                           )

    def __next__(self):
        while True:
            ucs = next(self.characters)
            try:
                name = string.capwords(unicodedata.name(ucs))
            except ValueError:
                continue
            return (ucs, name)

    # python 2.6 - 3.3 compatibility
    next = __next__


class Style(object):
    " decorator for screen output "
    heading = lambda self, text: text
    hint = lambda self, text: text
    delimiter = u'|'
    continuation = u' ..'
    header_hint = u'-'
    header_fill = u'='
    name_len = 25
    alignment = 'left'
    loading = ' ... loading ... '

    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)


class Screen(object):
    " represents terminal and data dimensions "
    intro_msg_fmt = (u'Characters {wide} terminal cells wide. '
                     u'Delimiters ({delim}) should align.')

    def __init__(self, term, style, wide=2, cjk=False):
        self.term = term
        self.style = style
        self.wide = wide

    @property
    def header(self):
        return self.head_item * self.num_columns

    @property
    def hint_width(self):
        return sum((len(self.style.delimiter),
                    self.wide,
                    len(self.style.delimiter),
                    len(u' '),
                    len(u'0xZZZZZ'),
                    len(u' '),
                    self.style.name_len,))

    @property
    def head_item(self):
        heading = (u'{delimiter}{hint}{delimiter}'
                   .format(delimiter=self.style.hint(self.style.delimiter),
                           hint=self.style.header_hint * self.wide))
        alignment = lambda *args: (
            self.term.rjust(*args) if self.style.alignment == 'right' else
            self.term.ljust(*args))
        txt = alignment(heading, self.hint_width, self.style.header_fill)
        return self.style.heading(txt)

    @property
    def msg_intro(self):
        delim = self.style.hint(self.style.delimiter)
        wide = self.style.heading('{}'.format(self.wide))
        return self.term.wrap(self.intro_msg_fmt.format(
            wide=wide, delim=delim))

    @property
    def row_ends(self):
        return self.term.height - 1

    @property
    def num_columns(self):
        if self.term.is_a_tty:
            return self.term.width // self.hint_width
        return 1

    @property
    def num_rows(self):
        return self.row_ends - self.row_begins - 1

    @property
    def row_begins(self):
        return len(self.msg_intro) + 1

    @property
    def page_size(self):
        return self.num_rows * self.num_columns


class Pager(object):
    " a specialized varient of less(1), you can pipe output to less, too. "
    def __init__(self, term, screen, character_factory):
        self.term = term
        self.screen = screen
        self.character_factory = character_factory
        self.character_generator = self.character_factory(self.screen.wide)
        self._page_data = dict()
        self.on_resize(None, None)
        self._idx = -1
        self._offset = 0

    def on_resize(self, sig, action):
        assert self.term.width >= self.screen.hint_width, (
            'Screen to small {}, must be at least {}'.format(
                self.term.width, self.screen.hint_width))
        self.dirty = 2
        self._page_data.clear()
        self.last_page = None
        self.character_generator = self.character_factory(self.screen.wide)

    def page_data(self, idx, offset):
        size = self.screen.page_size
        while offset < 0 and idx:
            offset += size
            idx -= 1
        offset = max(0, offset)
        while offset > size:
            offset -= size
            idx += 1
        if idx == self.last_page:
            offset = 0
        _idx = -1
        while _idx <= idx:
            # retrieve new page data
            _idx += 1
            if _idx not in self._page_data:
                pgdata = list()
                for count in xrange(size):
                    try:
                        pgdata.append(next(self.character_generator))
                    except StopIteration:
                        break
                self._page_data[_idx] = pgdata
                if not pgdata:
                    break

        last = max(self._page_data.keys())
        if len(self._page_data[last]) == 0:
            del self._page_data[last]
            last = max(self._page_data.keys())
        self.last_page = last

        nxt = max(0, min(idx, _idx, self.last_page or float('inf')))
        page_data = (self._page_data[nxt][offset:] +
                     self._page_data.get(nxt + 1, list())[:offset])
        return (nxt, offset), page_data

    def run(self, writer, reader):
        page_idx = page_offset = 0
        if not self.term.is_a_tty:
            while True:
                npage_idx, offset = self.draw(writer,
                                              page_idx + 1,
                                              page_offset)
                if npage_idx == page_idx:
                    break
                page_idx = npage_idx
                self.dirty = True
            return
        while True:
            if self.dirty:
                page_idx, page_offset = self.draw(writer,
                                                  page_idx,
                                                  page_offset)
                self.dirty = False
            nxt, noff = self.process_keystroke(reader(timeout=0.25),
                                               page_idx,
                                               page_offset)
            if not self.dirty:
                self.dirty = nxt != page_idx or noff != page_offset
            page_idx, page_offset = nxt, noff
            if page_idx == -1:
                return

    def process_keystroke(self, inp, idx, offset):
        term = self.term
        # exit
        if inp.lower() in (u'q', u'Q'):
            return (-1, -1)
        elif inp in (u'1', u'2'):
            if int(inp) != self.screen.wide:
                self.screen.wide = int(inp)
                self.on_resize(None, None)
        elif inp in (u'_', u'-'):
            # adjust name length -1
            nlen = max(1, self.screen.style.name_len - 2)
            if nlen != self.screen.style.name_len:
                self.screen.style.name_len = nlen
                self.on_resize(None, None)
        elif inp in (u'+', u'='):
            # adjust name length +1
            nlen = max(1, self.screen.style.name_len + 2)
            if nlen != self.screen.style.name_len:
                self.screen.style.name_len = nlen
                self.on_resize(None, None)
        elif inp == u'2' and self.wide != 2:
            # change 2 or 1-cell wide view
            self.screen.wide = 2
            self.on_resize(None, None)
        elif inp in (u'y', u'k') or inp.code in (term.KEY_UP,):
            # scroll backward 1 line
            return (idx, offset - self.screen.num_columns)
        elif inp in (u'e', u'j') or inp.code in (term.KEY_ENTER,
                                                 term.KEY_DOWN,):
            # scroll forward 1 line
            return (idx, offset + self.screen.num_columns)
        elif inp in (u'f', u' ') or inp.code in (term.KEY_PGDOWN,):
            # scroll forward 1 page
            return (idx + 1, offset)
        elif inp == u'b' or inp.code in (term.KEY_PGUP,):
            # scroll backward 1 page
            return (max(0, idx - 1), offset)
        elif inp.code in (term.KEY_SDOWN,):
            # scroll forward 10 pages
            return (max(0, idx + 10), offset)
        elif inp.code in (term.KEY_SUP,):
            # scroll forward 10 pages
            return (max(0, idx - 10), offset)
        elif inp.code == term.KEY_HOME:
            # top
            return (0, 0)
        elif inp.code == term.KEY_END:
            # bottom
            return (float('inf'), 0)
        # offset w/return
        return idx, offset

    def draw(self, writer, idx, offset):
        # as our screen can be resized while we're mid-calculation,
        # our self.dirty flag can become re-toggled; because we are
        # not reflowing our pagination, we must begin over again.
        while self.dirty:
            if not self.draw_heading(writer):
                self.draw_loading(writer, idx)
            self.dirty = False
            (idx, offset), data = self.page_data(idx, offset)
            for txt in self.page_view(data):
                writer(txt)
        self.draw_status(writer, idx)
        flushout()
        return idx, offset

    def draw_heading(self, writer):
        if self.dirty == 2:  # and self.term.is_a_tty:
            writer(self.term.clear)
            writer(self.term.move(0, 0))
            writer('\n'.join(self.screen.msg_intro))
            writer('\n')
            writer(self.screen.header)
            writer('\n')
            return True

    def draw_loading(self, writer, idx):
        if self.term.is_a_tty:
            if idx not in self._page_data:
                writer(u' ' + self.screen.style.loading)
            else:
                writer(u' +')
            flushout()

    def draw_status(self, writer, idx):
        if self.term.is_a_tty:
            writer(self.term.move(self.term.height - 1))
            end = u' (END)' if idx == self.last_page else u''
            writer('Page {idx}{end}. q to quit, [keys: kjfb12-=]'
                   .format(idx=idx, end=end))

    def page_view(self, data):
        if self.term.is_a_tty:
            yield self.term.move(self.screen.row_begins, 0)
        clear_eol = self.term.clear_eol
        clear_eos = self.term.clear_eos
        num_cols = self.screen.num_columns

        col = row = 0
        for ucs, name in data:
            val = self.text_entry(ucs, name)
            col += 1
            if col == num_cols:
                col = 0
                row += 1
                if self.term.is_a_tty:
                    val = u''.join((val, clear_eol, u'\n'))
                else:
                    val = u''.join((val.rstrip(), u'\n'))
            yield val
        if self.term.is_a_tty:
            yield u''.join((clear_eol, u'\n', clear_eos))

    def text_entry(self, ucs, name):
        style = self.screen.style
        if len(name) > style.name_len:
            idx = max(0, style.name_len - len(style.continuation))
            name = u''.join((name[:idx], style.continuation if idx else u''))
        if style.alignment == 'right':
            fmt = u' '.join(('{name:{name_len}s}',
                             '{delimiter}{ucs}{delimiter}'
                             '0x{value:x}'))
        else:
            fmt = u' '.join(('{delimiter}{ucs}{delimiter}',
                             '0x{value:x}',
                             '{name:{name_len}s}'))
        delimiter = style.hint(style.delimiter)
        return fmt.format(name_len=style.name_len,
                          delimiter=delimiter,
                          name=name, ucs=ucs,
                          value=ord(ucs))


def main():
    term = Terminal()
    style = Style(heading=term.magenta,
                  hint=term.bright_cyan,
                  delimiter=u'|',
                  ) if term.number_of_colors else Style()
    screen = Screen(term, style)
    character_factory = WcWideCharacterGenerator
    pager = Pager(term, screen, character_factory)
    if term.is_a_tty:
        signal.signal(signal.SIGWINCH, pager.on_resize)
    else:
        screen.style.name_len = 80 - 15
        pager.dirty = 2
    with term.location(), term.cbreak(), term.fullscreen():
        pager.run(writer=echo, reader=term.inkey)

if __name__ == '__main__':
    main()
