==========
libwcwidth
==========

A portable C11 library, mainly for CLI/TUI programs that carefully produce output for Terminals.

This project is derived from the Python `wcwidth`_ project.

The Python documentation_ closely matches this C library, except that the C API provides UTF-8 and
codepoint array interfaces.

The lowest-level functions are derived from POSIX.1-2001 and POSIX.1-2008 `wcwidth(3)`_ and
`wcswidth(3)`_, which this library implements as ``wcwidth_u32()`` and ``wcswidth_u32()``.  These
functions return -1 when C0 and C1 control codes other than NUL are present; NUL measures as
zero-width.  They do not parse terminal escape sequences: any escape sequence contains control
codes, so these functions return -1 for it.

``width_u8()`` is a higher-level wrapper of ``wcswidth_u8()`` that also measures terminal control
sequences, like colors, bold, tabstops, and horizontal cursor movement.

``wcstwidth_u8()`` applies corrections for a specific terminal program and version, as described
in the Python Corrections_ documentation.

Quick Start
-----------

All commands below are run from the ``libwcwidth/`` sub-folder.  Build a static library,
``build/libwcwidth.a``::

    make

Example programs::

    make examples

Tests::

    make test

Format (requires clang-format_)::

    make format

CMake is also supported, and is preferred for embedding this library in a larger build::

    cmake -B build-cmake && cmake --build build-cmake

For linking with your own project, from the repository root::

    gcc -Ilibwcwidth/include myapp.c -Llibwcwidth/build -lwcwidth

Example Programs
----------------

Three small CLI utilities demonstrate use of this library.

**textwrap** -- Unicode, CJK, emoji, and terminal sequence-aware text wrapping::

    $ textwrap 42 README.rst
    ==========
    libwcwidth
    ==========

    A portable C11 library, mainly for CLI/TUI
    programs that carefully produce output for
    Terminals.

    ...

Uses environment value, ``$COLUMNS``, if no width argument is given.  Use ``-v`` to append a red
carriage-return marker.

**width** -- report the display width of each line::

    $ width README.rst
    10
    10
    10
    0
    96
    ...

    $ echo 'コンニチハ' | width
    10

    $ width -v <<< "café résumé"
    11:café résumé

**align** -- demonstrate left, right, and center alignment::

    $ echo "hello" | align 20
    hello                                hello         hello

Overview
--------

The full function reference is the `C11 API`_ page, generated from the headers; this section
demonstrates each function by example.  Conceptual topics such as ambiguous width, terminal
corrections, and grapheme clustering are discussed in the Python documentation_.

String length conventions
~~~~~~~~~~~~~~~~~~~~~~~~~

Every string function takes an explicit length and reads exactly that many units:

``_u32`` functions
    count codepoints in the array,
``_u8`` functions
    count bytes.

There is no NUL-terminated sentinel form; pass ``strlen(text)`` when the text is a C string.  The
length is authoritative, so a NUL is an ordinary zero-width character rather than a terminator: it
may appear anywhere, and survives into transform output, whose ``*out_len`` is the true length.

Alternate encodings
~~~~~~~~~~~~~~~~~~~

Use ``_u8`` when your text is UTF-8 and ``_u32`` when you hold decoded codepoints; the two
families mirror each other.  Auxiliary strings are UTF-8 in *both* families -- the ``fillchar``
padding argument and the ``initial_indent``/``subsequent_indent``/``placeholder`` wrap options --
since they are short constants, not the text being processed.

Other encodings (Latin-1, CP437, Shift-JIS, ...) are transcoded by the caller; the library carries
no encoding tables.  Either transcode to UTF-8 once with iconv(3) or ICU and use the ``_u8`` forms
throughout, or use the ``_u32`` forms and re-encode the result.  ``wcwidth_encode_u32()`` and
``wcwidth_decode_u32()`` convert between the two representations:

.. code-block:: c

    /* CP437 "caf\x82" decoded to codepoints by the caller. */
    uint32_t cps[] = {'c', 'a', 'f', 0xE9};   /* 0x82 in CP437 is U+00E9 */
    char stack[64], *utf8;
    size_t out_len, utf8_len;
    uint32_t *out;

    out = ljust_u32(cps, 4, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, &out_len, NULL);
    /* out is {c, a, f, U+00E9, ' '}; encode for the caller's iconv(3) or ICU. */
    utf8 = wcwidth_encode_u32(out, out_len, stack, sizeof(stack), &utf8_len);

    if (utf8 != stack)
        free(utf8);
    free(out);

Re-encoding to a legacy charset is the caller's iconv(3) or ICU (``ucnv_*``) call; a byte cast
works only when every codepoint fits the target, where iconv reports ``EILSEQ`` instead.

wcwidth_u32()
~~~~~~~~~~~~~

Measure the width of a single codepoint; returns ``0`` for zero-width (combining marks, ZWJ,
NUL), ``2`` for wide East Asian characters, and ``-1`` for control codes:

.. code-block:: c

    wcwidth_u32(0x0301, 1)  /* combining acute accent */       0
    wcwidth_u32(0x2630, 1)  /* TRIGRAM FOR HEAVEN, wide */     2
    wcwidth_u32(0x2640, 1)  /* female sign, ambiguous */       1
    wcwidth_u32(0x2640, 2)  /* the same, ambiguous_width=2 */  2
    wcwidth_u32('\n', 1)    /* control code */                -1

``ambiguous_width`` (1 or 2) sets the width of East Asian Ambiguous characters, and only of those:
U+2640 above is Ambiguous, so it answers to the second argument, while U+2630 is Wide and measures
2 under either setting.  A single codepoint needs no ``_u8`` variant; use ``wcswidth_u8()`` to
measure text.

wcswidth_u32() and wcswidth_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Measure a string of codepoints or UTF-8 bytes, treating grapheme clusters (ZWJ sequences,
variation selectors, virama conjuncts, regional indicator pairs) as single units; return ``-1``
when any control code other than NUL is present:

.. code-block:: c

    uint32_t family[] = {0x1F468, 0x200D, 0x1F469, 0x200D, 0x1F467};
    wcswidth_u32(family, 5, 1)   /* man ZWJ woman ZWJ girl */  2
    wcswidth_u8("café", 5, 1)                                  4

wcstwidth_u32() and wcstwidth_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Terminal-aware variants of ``wcswidth_u32()`` and ``wcswidth_u8()``; the ``term_program``
argument applies terminal-specific corrections:

.. code-block:: c

    wcswidth_u8("☰", 3, 1)               /* U+2630, wide */  2
    wcstwidth_u8("☰", 3, 1, "vte")                            1

width_u32() and width_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~

Measure the visible width of text including terminal control sequences: colors, bold, tabstops,
horizontal cursor movement, and OSC 66 Text Sizing.  ``width_u32()`` encodes
its codepoints to UTF-8 and measures as ``width_u8()``:

.. code-block:: c

    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;

    width_u8("\x1b[31mWARN\x1b[0m", 13, WCWIDTH_PARSE, &opts, NULL);  /* 4 */
    opts.tabsize = 4;
    width_u8("\t", 1, WCWIDTH_PARSE, &opts, NULL);                   /* 4 */
    width_u8("\x1b[H\x1b[2J", 7, WCWIDTH_PARSE, &opts, NULL);        /* 0 */
    width_u8("hello\x1b[5Dworld", 14, WCWIDTH_IGNORE, &opts, NULL);  /* 10 */
    width_u8("\x1b]66;w=2;XY\x07", 12, WCWIDTH_PARSE, &opts, NULL);  /* 2 */

The ``wcwidth_control_mode_t`` mode selects how control characters and sequences are treated:
``WCWIDTH_PARSE`` tracks horizontal cursor movement (the default), ``WCWIDTH_STRICT`` returns
``-1`` and sets ``*error`` for indeterminate sequences, and ``WCWIDTH_IGNORE`` strips all control
codes:

.. code-block:: c

    int err = 0;
    int w = width_u8("\n", 1, WCWIDTH_STRICT, &WCWIDTH_WIDTH_OPTS_DEFAULT, &err);
    if (w < 0) {
        /* err is WCWIDTH_ERROR_VERTICAL_CTRL */
    }

ljust_u8(), rjust_u8(), and center_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Justify UTF-8 text to a display width, filling with a UTF-8 byte string.  Each returns a
``malloc``\ 'd NUL-terminated string the caller must ``free``:

.. code-block:: c

    ljust_u8("コンニチハ", 15, 11, "*", 1, WCWIDTH_PARSE, 1, NULL, NULL, NULL);
    /* "コンニチハ*" */
    rjust_u8("コンニチハ", 15, 11, "*", 1, WCWIDTH_PARSE, 1, NULL, NULL, NULL);
    /* "*コンニチハ" */
    center_u8("cafe\xcc\x81", 6, 6, "*", 1, WCWIDTH_PARSE, 1, NULL, NULL, NULL);
    /* "*café*" */

clip_u8()
~~~~~~~~~

Clip text to a visible column range ``[v_start, v_end)``, filling partially visible graphemes
with a fill string.  Returns a ``malloc``\ 'd NUL-terminated string the caller must ``free``:

.. code-block:: c

    clip_u8("中文字", 9, 0, 3, WCWIDTH_PARSE, 8, 1, NULL, true, " ", 1, NULL, NULL);
    /* "中 " */

    clip_u8("中文字", 9, 1, 5, WCWIDTH_PARSE, 8, 1, NULL, true, ".", 1, NULL, NULL);
    /* ".文." */

``clip_u32()`` is the codepoint-array form, returning a ``malloc``\ 'd array of ``*out_len``
codepoints.

wrap_u8() and wrap_u8_text()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wrap UTF-8 text into lines of at most ``opts.width`` display cells.  ``wrap_u8()`` collapses all
whitespace, including newlines; ``wrap_u8_text()`` preserves input newlines as paragraph breaks.
Both emit a single ``malloc``\ 'd buffer of newline-separated lines:

.. code-block:: c

    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out;
    size_t out_len;

    opts.width = 5;
    wrap_u8("hello world", 11, &opts, &out, &out_len);    /* "hello\nworld" */
    opts.width = 4;
    wrap_u8("コンニチハ", 15, &opts, &out, &out_len);       /* "コン\nニチ\nハ" */

When the placeholder does not fit within the given width (``max_lines`` truncation), ``wrap_u8()``
returns ``-2`` rather than ``-1``, so callers can raise a tailored error.  ``wcwidth_wrap_lines_u8()``
additionally reports each line's start offset in the output buffer, which matters when a line
contains ``'\n'`` from the placeholder itself:

.. code-block:: c

    size_t *offsets, count;
    wcwidth_wrap_lines_u8("one two", 7, &opts, &out, &out_len, &offsets, &count);
    /* out is "one\ntwo", offsets = {0, 4} */

OSC 66 text sizing is atomic to the word splitter: a sequence and its display text are one
unbreakable unit, so a line is never broken inside one, even at a space or hyphen in the display
text.  Python's ``wrap()`` behaves the same way.  ``wrap_u32()`` and ``wrap_u32_text()`` are the
codepoint-array forms.

wcwidth_escape_strip()
~~~~~~~~~~~~~~~~~~~~~~

Strip all terminal escape sequences from text, preserving OSC 66 display text.  The result is
written to a caller-supplied buffer and is always NUL-terminated:

.. code-block:: c

    char buf[64];
    size_t out_len = 0;
    size_t needed = wcwidth_escape_strip("\x1b[31mred\x1b[0m", 12, buf, sizeof buf, &out_len);
    /* buf is "red", out_len is 3 */

The return value is the byte length the stripped text needs, excluding the terminator, so the
buffer must hold ``needed + 1`` bytes; the output was truncated whenever the return value is
greater than or equal to ``out_cap``.  A caller sizing its own buffer can measure first by passing
an ``out_cap`` of 0, then allocate and fill.  ``wcwidth_escape_strip_u32()`` is the
codepoint-array form, and allocates its result instead.

Differences from the Python package
-----------------------------------

``width_u32()`` and ``width_u8()`` parse only the sequences that move the cursor within a line or
change how much room text occupies: SGR, horizontal cursor movement (CUF, CUB, HPA), and OSC 66 text
sizing.  This is not a terminal emulator.  Every other recognized sequence counts as zero-width, and
sequences whose column effect cannot be known from the text alone -- screen clears, scrolls,
vertical movement -- are indeterminate, which ``WCWIDTH_STRICT`` turns into an error.
``wcswidth_*()`` and ``wcstwidth_*()`` parse nothing: like their Python counterparts they take no
``wcwidth_control_mode_t`` and return -1 for any escape sequence.

The text transforms are simpler than the Python ones:

* OSC 8 hyperlinks are not implemented; an OSC 8 sequence is treated as an ordinary zero-width OSC.
  It measures correctly but is never rewritten, so a ``clip_u8()`` window starting or ending inside
  a hyperlink yields an unbalanced pair, and ``wrap_u8()`` does not re-open the link on each line.
  Callers must re-emit the opener and terminator themselves.
* ``clip_u8()`` does not parse horizontal cursor movement (there is no counterpart to Python's
  ``overtyping``) or OSC 66 text sizing; every sequence but SGR passes through as zero-width.
* ``wrap_u8()`` and ``wrap_u8_text()`` split words on the ASCII space alone, where Python's
  ``wrap()`` splits on any whitespace run.  ``wcwidth_wrap_opts_t`` offers no
  ``break_on_hyphens``, ``fix_sentence_endings`` or ``propagate_sgr``: hyphenated words break
  mid-word, sentence-ending periods are not widened, and SGR state does not survive a line break.

``ljust_u8()``, ``rjust_u8()`` and ``center_u8()`` match the Python functions exactly.

Malformed escape sequences
~~~~~~~~~~~~~~~~~~~~~~~~~~

Well-formed sequences -- those a conforming program would emit -- measure the same here as in
Python.  Malformed ones may not: an unterminated CSI or OSC, a lone ESC at the end of a buffer, or
an introducer followed by a byte the standard disallows can differ by a cell or two, and
``wcwidth_escape_strip()`` may keep bytes that Python's ``strip_sequences()`` drops, or the
reverse.  Over random escape soup, roughly 2% of inputs measure differently.

Python recognizes sequences by regular expression and this library by hand-written scanner, and the
two disagree on where a malformed sequence ends.  The divergence is narrow: for a character-set
designation ``ESC (``, all 79 final bytes ECMA-48 permits measure identically, as does every
intermediate byte.  Only one of the 33 C0 controls -- which are not permitted there at all --
differs:

.. code-block:: c

    width_u8("X\x1b(\nY", 5, WCWIDTH_PARSE, &opts, NULL);   /* 2; Python says 3 */

Python's ``\x1b[()].`` does not match a newline and leaves the three bytes as text; this library
consumes them as a sequence.  A real terminal does neither.  ``WCWIDTH_IGNORE`` behaves the same,
since it too must decide where a sequence ends.

Neither answer is more correct, and terminals themselves differ on malformed input, so do not rely
on the two implementations agreeing when the text is arbitrary bytes.  ``WCWIDTH_STRICT`` is the
exception: it refuses indeterminate input rather than guessing, and over the same corpus C and
Python returned identical widths and identical error messages for every input.

Supported Terminals
-------------------

The ``term_program`` argument selects per-terminal corrections from generated override tables.
The following canonical names are recognized; common ``TERM``/``TERM_PROGRAM`` aliases such as
``vscode`` and ``xterm-kitty`` resolve to them:

.. BEGIN_LIST_TERM_PROGRAMS
.. code-block:: text

    absolutetelnet/ssh alacritty apple_terminal bobcat contour extraterm foot
    ghostty iterm2 kitty konsole mintty mlterm pterm rio st terminology urxvt
    vte warp wezterm xterm xterm.js

.. END_LIST_TERM_PROGRAMS

For the most accurate corrections, query the terminal's software version via XTVERSION_
(``CSI > q``) and pass the canonical name.  See the Python Corrections_ documentation for details.

Unicode Version
---------------

Tables generated from Unicode |unicode_version|, which is still a pre-release draft.  The
Python package ships Unicode 17.0.0 tables until that release lands; the two halves of
this project are deliberately out of step while the C11 library is a release candidate.

.. |unicode_version| replace:: 18.0.0

.. _wcwidth: https://github.com/jquast/wcwidth
.. _documentation: https://wcwidth.readthedocs.io/
.. _Corrections: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections
.. _XTVERSION: https://vtdn.dev/docs/dcs/xtversion/
.. _`C11 API`: https://wcwidth.readthedocs.io/en/latest/api_c.html
.. _clang-format: https://clang.llvm.org/docs/ClangFormat.html
.. _`wcwidth(3)`: https://man7.org/linux/man-pages/man3/wcwidth.3.html
.. _`wcswidth(3)`: https://man7.org/linux/man-pages/man3/wcswidth.3.html
