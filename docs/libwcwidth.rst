==========
libwcwidth
==========

A portable C11 library, mainly for CLI/TUI programs that carefully produce output for Terminals.

This project is derived from the Python `wcwidth`_ project.

The Python documentation_ closely matches this C library, except that the C API provides UTF-8 and
codepoint array interfaces.

The lowest-level functions are derived from POSIX.1-2001 and POSIX.1-2008 `wcwidth(3)`_ and
`wcswidth(3)`_, which this library implements as `wcwidth_u32()`_ and `wcswidth_u32()`_.  These
functions return -1 when C0 and C1 control codes other than NUL are present; NUL measures as
zero-width.  They do not parse terminal escape sequences: any escape sequence contains control
codes, so these functions return -1 for it.

`wcwidth_width_u8()`_ is a higher-level wrapper of `wcswidth_u8()`_ that also measures terminal
control sequences, like colors, bold, tabstops, and horizontal cursor movement.

`wcstwidth_u8()`_ applies corrections for a specific terminal program and version, as described
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

Memory ownership
~~~~~~~~~~~~~~~~

The text transforms allocate their result and return ``NULL`` on failure, be certain to ``free()``
on success:

.. code-block:: c

    wcwidth_clip_opts_t opts = WCWIDTH_CLIP_OPTS_DEFAULT;
    char *out;

    opts.v_end = 3;
    out = wcwidth_clip_u8("中文字", 9, WCWIDTH_PARSE, &opts, NULL, NULL);
    if (out == NULL)
        return -1;
    /* ... use out ... */
    free(out);

`wcwidth_encode_u32()`_ and `wcwidth_decode_u32()`_ instead return the caller's scratch buffer
if the result fits, allocating only when it does not.  ``free()`` these with the condition that
the result is at a new address:

.. code-block:: c

    char stack[64], *utf8 = wcwidth_encode_u32(cps, n, stack, sizeof(stack), &utf8_len);

    if (utf8 == NULL)
        return -1;
    /* ... use utf8, utf8_len ... */
    if (utf8 != stack)
        free(utf8);

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
throughout, or use the ``_u32`` forms and re-encode the result.  `wcwidth_encode_u32()`_ and
`wcwidth_decode_u32()`_ convert between the two representations:

.. code-block:: c

    /* CP437 "caf\x82" decoded to codepoints by the caller. */
    uint32_t cps[] = {'c', 'a', 'f', 0xE9};   /* 0x82 in CP437 is U+00E9 */
    char stack[64], *utf8;
    size_t out_len, utf8_len;
    wcwidth_align_opts_t opts = WCWIDTH_ALIGN_OPTS_DEFAULT;
    uint32_t *out;

    opts.dest_width = 5;
    out = wcwidth_ljust_u32(cps, 4, WCWIDTH_PARSE, &opts, &out_len, NULL);
    if (out == NULL)
        return -1;

    /* out is {c, a, f, U+00E9, ' '}; encode for the caller's iconv(3) or ICU. */
    utf8 = wcwidth_encode_u32(out, out_len, stack, sizeof(stack), &utf8_len);
    if (utf8 == NULL) {
        free(out);
        return -1;
    }

    /* ... hand utf8/utf8_len to iconv(3) or ICU ... */

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
2 under either setting.  A single codepoint needs no ``_u8`` variant; use `wcswidth_u8()`_ to
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

Terminal-aware variants of `wcswidth_u32()`_ and `wcswidth_u8()`_; the ``term_program``
argument applies terminal-specific corrections:

.. code-block:: c

    wcswidth_u8("☰", 3, 1)               /* U+2630, wide */  2
    wcstwidth_u8("☰", 3, 1, "vte")                            1

wcwidth_width_u32() and wcwidth_width_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Measure the visible width of text including terminal control sequences: colors, bold, tabstops,
horizontal cursor movement, and OSC 66 Text Sizing.  `wcwidth_width_u32()`_ encodes
its codepoints to UTF-8 and measures as `wcwidth_width_u8()`_:

.. code-block:: c

    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;

    wcwidth_width_u8("\x1b[31mWARN\x1b[0m", 13, WCWIDTH_PARSE, &opts, NULL);  /* 4 */
    opts.tabsize = 4;
    wcwidth_width_u8("\t", 1, WCWIDTH_PARSE, &opts, NULL);                   /* 4 */
    wcwidth_width_u8("\x1b[H\x1b[2J", 7, WCWIDTH_PARSE, &opts, NULL);        /* 0 */
    wcwidth_width_u8("hello\x1b[5Dworld", 14, WCWIDTH_IGNORE, &opts, NULL);  /* 10 */
    wcwidth_width_u8("\x1b]66;w=2;XY\x07", 12, WCWIDTH_PARSE, &opts, NULL);  /* 2 */

The ``wcwidth_control_mode_t`` mode selects how control characters and sequences are treated:
``WCWIDTH_PARSE`` tracks horizontal cursor movement (the default), ``WCWIDTH_STRICT`` returns
``-1`` and sets ``*error`` for indeterminate sequences, and ``WCWIDTH_IGNORE`` strips all control
codes:

.. code-block:: c

    int err = 0;
    int w = wcwidth_width_u8("\n", 1, WCWIDTH_STRICT, &WCWIDTH_WIDTH_OPTS_DEFAULT, &err);
    if (w < 0) {
        /* err is WCWIDTH_ERROR_VERTICAL_CTRL */
    }

wcwidth_ljust_u8(), wcwidth_rjust_u8(), and wcwidth_center_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Justify UTF-8 text to ``opts.dest_width`` display cells, filling with a UTF-8 byte string.  Each
returns a ``malloc``\ 'd NUL-terminated string the caller must ``free``:

.. code-block:: c

    wcwidth_align_opts_t opts = WCWIDTH_ALIGN_OPTS_DEFAULT;
    char *out;

    opts.fillchar = "*";
    opts.dest_width = 11;

    out = wcwidth_ljust_u8("コンニチハ", 15, WCWIDTH_PARSE, &opts, NULL, NULL);
    /* "コンニチハ*" */
    free(out);

    out = wcwidth_rjust_u8("コンニチハ", 15, WCWIDTH_PARSE, &opts, NULL, NULL);
    /* "*コンニチハ" */
    free(out);

    opts.dest_width = 6;
    out = wcwidth_center_u8("cafe\xcc\x81", 6, WCWIDTH_PARSE, &opts, NULL, NULL);
    /* "*café*" */
    free(out);

wcwidth_clip_u8()
~~~~~~~~~~~~~~~~~

Clip text to the visible column range ``[opts.v_start, opts.v_end)``, filling partially visible
graphemes with a fill string.  Returns a ``malloc``\ 'd NUL-terminated string the caller must
``free``:

.. code-block:: c

    wcwidth_clip_opts_t opts = WCWIDTH_CLIP_OPTS_DEFAULT;
    char *out;

    opts.v_end = 3;
    out = wcwidth_clip_u8("中文字", 9, WCWIDTH_PARSE, &opts, NULL, NULL);
    /* "中 " */
    free(out);

    opts.v_start = 1;
    opts.v_end = 5;
    opts.fillchar = ".";
    out = wcwidth_clip_u8("中文字", 9, WCWIDTH_PARSE, &opts, NULL, NULL);
    /* ".文." */
    free(out);

Leave ``opts.v_end`` at its ``SIZE_MAX`` default to clip from ``v_start`` through the final column
of *text*, without measuring it first -- the counterpart of the ``-1`` default of Python's `clip()`_:

.. code-block:: c

    opts = WCWIDTH_CLIP_OPTS_DEFAULT;
    opts.v_start = 6;   /* v_end stays SIZE_MAX: through the final column */
    out = wcwidth_clip_u8("\x1b[1;34mHello world\x1b[0m", 22, WCWIDTH_PARSE, &opts, NULL, NULL);
    /* "\x1b[1;34mworld\x1b[0m" */
    free(out);

Some sequences are unsupported, and `wcwidth_clip_u8()`_ returns ``NULL`` with ``*error`` set to
``WCWIDTH_ERROR_UNSUPPORTED`` rather than answering differently from Python's `clip()`_:

* **Horizontal cursor movement** -- BS, CR, and CSI ending in ``C`` (CUF), ``D`` (CUB) or ``G``
  (HPA).  There is no counterpart to the ``overtyping`` option of Python's `clip()`_.
* **OSC 8 hyperlinks** and **OSC 66 text sizing** -- measured, but never rewritten, so a window
  cutting through one would leave an unbalanced pair or an unclipped sequence.

.. code-block:: c

    int error;

    opts = WCWIDTH_CLIP_OPTS_DEFAULT;
    opts.v_end = 3;
    out = wcwidth_clip_u8("abcdef\x1b[3Dxy", 12, WCWIDTH_PARSE, &opts, NULL, &error);
    /* NULL, error == WCWIDTH_ERROR_UNSUPPORTED */

Movement is reported wherever it appears, because a CUB or HPA right of the window still rewinds
into it.  The OSC sequences are reported only when the clip reaches one: the scan stops at the
first ordinary character past ``v_end``, and nothing beyond that can change the result.

`wcwidth_clip_u32()`_ is the codepoint-array form, returning a ``malloc``\ 'd array of ``*out_len``
codepoints.

wcwidth_wrap_u8() and wcwidth_wrap_u8_text()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wrap UTF-8 text into lines of at most ``opts.width`` display cells.  `wcwidth_wrap_u8()`_ collapses
all whitespace, including newlines; `wcwidth_wrap_u8_text()`_ preserves input newlines as paragraph
breaks.  Both emit a single ``malloc``\ 'd buffer of newline-separated lines:

.. code-block:: c

    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    char *out;
    size_t out_len;

    opts.width = 5;
    wcwidth_wrap_u8("hello world", 11, &opts, &out, &out_len);    /* "hello\nworld" */
    free(out);

    opts.width = 4;
    wcwidth_wrap_u8("コンニチハ", 15, &opts, &out, &out_len);       /* "コン\nニチ\nハ" */
    free(out);

When the placeholder does not fit within the given width (``max_lines`` truncation),
`wcwidth_wrap_u8()`_ returns ``-2`` rather than ``-1``, so callers can raise a tailored error.
`wcwidth_wrap_lines_u8()`_ additionally reports each line's start offset in the output buffer, which
matters when a line contains ``'\n'`` from the placeholder itself:

.. code-block:: c

    size_t *offsets, count;
    wcwidth_wrap_lines_u8("one two", 7, &opts, &out, &out_len, &offsets, &count);
    /* out is "one\ntwo", offsets = {0, 4} */
    free(offsets);
    free(out);

OSC 66 text sizing is atomic to the word splitter: a sequence and its display text are one
unbreakable unit, so a line is never broken inside one, even at a space or hyphen in the display
text.  Python's `wrap()`_ behaves the same way.  `wcwidth_wrap_u32()`_ and `wcwidth_wrap_u32_text()`_ are the
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
an ``out_cap`` of 0, then allocate and fill.  `wcwidth_escape_strip_u32()`_ is the
codepoint-array form, and allocates its result instead.

Differences from the Python package
-----------------------------------

`wcwidth_width_u32()`_ and `wcwidth_width_u8()`_ parse only the sequences that move the cursor
within a line or change how much room text occupies: SGR, horizontal cursor movement (CUF, CUB,
HPA), and OSC 66 text sizing.  Every other recognized sequence is zero-width.  Screen clears,
scrolls and vertical movement are indeterminate -- their column effect depends on terminal state
the text does not carry -- so ``WCWIDTH_STRICT`` reports them as an error and the other modes
count them as zero-width.

``wcswidth_*()`` and ``wcstwidth_*()`` take no ``wcwidth_control_mode_t`` and return -1 for any
escape sequence, matching their Python counterparts.  `wcwidth_ljust_u8()`_, `wcwidth_rjust_u8()`_
and `wcwidth_center_u8()`_ match the Python functions exactly.

The text transforms are simpler:

* `wcwidth_clip_u8()`_ rejects the unsupported sequences described above; every other sequence but
  SGR is zero-width, preserved where it appeared rather than clipped as a unit.  It otherwise
  matches Python's `clip()`_, SGR included.
* `wcwidth_wrap_u8()`_ treats an OSC 8 hyperlink as an ordinary zero-width OSC, so the link is not
  re-opened on each line; callers must re-emit the opener and terminator themselves.
* `wcwidth_wrap_u8()`_ and `wcwidth_wrap_u8_text()`_ split words on the ASCII space alone, where
  Python's `wrap()`_ splits on any whitespace run.  ``wcwidth_wrap_opts_t`` offers no
  ``break_on_hyphens``, ``fix_sentence_endings`` or ``propagate_sgr``: hyphenated words break
  mid-word, sentence-ending periods are not widened, and SGR state does not survive a line break.

Malformed escape sequences
~~~~~~~~~~~~~~~~~~~~~~~~~~

Python recognizes sequences by regular expression and this library by hand-written scanner, and
the two agree on every well-formed sequence and nearly every malformed one.  Over 200,000 random
escape soups, two measured differently and `wcwidth_escape_strip()`_ matched `strip_sequences()`_
everywhere.  Both exceptions are a CSI carrying a private parameter byte before a cursor final,
such as ``ESC [ > D``, which this library resolves as CUB where Python counts it zero-width.  A
real terminal does neither reliably, so do not depend on the two agreeing when the text is
arbitrary bytes.

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

Tables generated from Unicode |unicode_version|.

.. |unicode_version| replace:: 18.0.0

.. _`wcwidth_center_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_center_u8
.. _`clip()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.clip
.. _`wcwidth_clip_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_clip_u32
.. _`wcwidth_clip_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_clip_u8
.. _`wcwidth_ljust_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_ljust_u8
.. _`wcwidth_rjust_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_rjust_u8
.. _`strip_sequences()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.strip_sequences
.. _`wcstwidth_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcstwidth_u8
.. _`wcswidth_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcswidth_u32
.. _`wcswidth_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcswidth_u8
.. _`wcwidth_decode_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_decode_u32
.. _`wcwidth_encode_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_encode_u32
.. _`wcwidth_escape_strip()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_escape_strip
.. _`wcwidth_escape_strip_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_escape_strip_u32
.. _`wcwidth_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_u32
.. _`wcwidth_wrap_lines_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_wrap_lines_u8
.. _`wcwidth_width_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_width_u32
.. _`wcwidth_width_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_width_u8
.. _`wrap()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.wrap
.. _`wcwidth_wrap_u32()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_wrap_u32
.. _`wcwidth_wrap_u32_text()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_wrap_u32_text
.. _`wcwidth_wrap_u8()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_wrap_u8
.. _`wcwidth_wrap_u8_text()`: https://wcwidth.readthedocs.io/en/latest/api_c.html#c.wcwidth_wrap_u8_text
.. _wcwidth: https://github.com/jquast/wcwidth
.. _documentation: https://wcwidth.readthedocs.io/
.. _Corrections: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections
.. _XTVERSION: https://vtdn.dev/docs/dcs/xtversion/
.. _`C11 API`: https://wcwidth.readthedocs.io/en/latest/api_c.html
.. _clang-format: https://clang.llvm.org/docs/ClangFormat.html
.. _`wcwidth(3)`: https://man7.org/linux/man-pages/man3/wcwidth.3.html
.. _`wcswidth(3)`: https://man7.org/linux/man-pages/man3/wcswidth.3.html
