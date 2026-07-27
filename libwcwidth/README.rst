==========
libwcwidth
==========

A portable C11 library mainly for CLI/TUI programs that carefully produce output for Terminals.

This is published as a companion of the Python `wcwidth`_ package.

.. _wcwidth: https://github.com/jquast/wcwidth

The lowest-level functions in this library are derived from POSIX.1-2001 and POSIX.1-2008
`wcwidth(3)`_ and `wcswidth(3)`_, which this library precisely copies by interface as `wcwidth()`_
and `wcswidth()`_.  These functions return -1 when C0 and C1 control codes are present.

An easy-to-use `width_u8()`_ and `width_u32()`_ function is provided as a wrapper of `wcswidth()`_,
that is also capable of measuring most terminal control codes and sequences, like colors, bold,
tabstops, and horizontal cursor movement.

TODO: keep migrating documentation ..:

.. ::

    `width()`_ argument ``term_program`` may provide more accurate terminal measurement Corrections_ as
    a wrapper of `wcstwidth()`_.

    Text-justification is solved by the sequence-aware functions `ljust()`_, `rjust()`_, `center()`_,
    and the grapheme-aware function `wrap()`_, serving as drop-in replacements to python standard
    functions.

    The `clip()`_ function extracts substrings by their displayed column positions, and
    `strip_sequences()`_ removes terminal escape sequences from text altogether.

    The iterator functions `iter_graphemes()`_ and `iter_sequences()`_ allow for careful navigation of
    grapheme and terminal control sequence boundaries as required by editors or REPLs with cursor
    control.  `iter_graphemes_reverse()`_ and `grapheme_boundary_before()`_ are necessary for backward
    cursor control over complex unicode.


Quick Start
-----------

Build static library::

    make

Run tests::

    make test

Format::

    make format

Link into your project::

    gcc -Ilibwcwidth/include myapp.c -Llibwcwidth/build -lwcwidth

Example Programs
----------------

Three small CLI utilities are included to demonstrate use of this library.

**textwrap**, unicode, CJK, emoji, terminal sequence-aware text wrapping tool.
TODO demonstrate terminal sequence support succiently?
::

    $ textwrap 42 README.rst
    A portable C11 library for measuring
    the display width of Unicode strings
    on terminal emulators.  This is a C11
    ...

TODO: support all of the textwrap options as CLI arguments

Uses ``$COLUMNS`` if no width argument is given.  Use ``-v`` to append a red
carriage-return marker.

**width**
TODO demonstrate CJK and emoji and such
::

    $ width README.rst
    80
    39
    0
    67
    ...

Use ``-v`` for rewrite to output with prefixed width::

    $ width -v <<< "café résumé"
    11:café résumé

**align**
TODO: just show align right of README?
demonstrate left, right, and center alignment
::

    $ echo "hello" | align 40
    hello                                         hello                    hello

API
---

TODO: Use sphinx apidocs, publish independently to libwcwidth.readthedocs.org,
cross-reference each other's documentation by external reference to and from python
wcwidth so that they don't build together.
