==========
libwcwidth
==========

A portable C11 library, mainly for CLI/TUI programs that carefully produce output for Terminals.

This project is derived from the Python `wcwidth`_ project.

The Python documentation_ closely matches this C library, except that the C API provides UTF-8 and
codepoint array interfaces.

The lowest-level functions are derived from POSIX.1-2001 and POSIX.1-2008 `wcwidth(3)`_ and
`wcswidth(3)`_, which this library implements as :c:func:`wcwidth_u32` and
:c:func:`wcswidth_u32`.  These functions return -1 when C0 and C1 control codes are present.

:c:func:`width_u8` is a higher-level wrapper of :c:func:`wcswidth_u8` that also measures terminal
control sequences, like colors, bold, tabstops, horizontal cursor movement, OSC 8 hyperlinks and
others.

:c:func:`wcstwidth_u8` provides terminal-specific corrections, for accurate width measurement by
the latest terminal program described in the Python Corrections_ documentation.

Quick Start
-----------

From the ``libwcwidth/`` sub-folder, build a static library::

    make

Example programs::

    make examples

Tests::

    make test

Format::

    make format

For linking with your own project::

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
    hello                               hello        hello

Overview
--------

The full function reference is the :ref:`c-api` page, generated from the headers; this section
demonstrates each function by example.  Conceptual topics such as ambiguous width, terminal
corrections, and grapheme clustering are discussed in the Python documentation_.

String length conventions
~~~~~~~~~~~~~~~~~~~~~~~~~

Every string function takes a length argument, ``n``:

``_u32`` functions
    count codepoints in the array; the full array length must be passed,
``_u8`` functions
    count bytes; pass ``(size_t) -1`` to measure until the first NUL byte, or an explicit count
    to allow embedded NULs (which measure as zero-width).

Alternate encodings
~~~~~~~~~~~~~~~~~~~

This library is UTF-8 centric.  Every ``_u8`` function takes and returns UTF-8 bytes; every
``_u32`` function takes and returns a ``uint32_t`` codepoint array.  The two families mirror
each other: use ``_u8`` when your text is UTF-8, ``_u32`` when you hold decoded codepoints.
The measurement functions (:c:func:`wcswidth_u32`, :c:func:`wcstwidth_u32`,
:c:func:`width_u32`) are encoding-neutral either way -- a width number is a width number.

The text transforms (``ljust_u32``, ``rjust_u32``, ``center_u32``, ``clip_u32``, ``wrap_u32``,
``wrap_u32_text``, ``wcwidth_escape_strip_u32``) take and return codepoint arrays.  Auxiliary
strings -- the ``fillchar`` padding argument and the ``initial_indent``/``subsequent_indent``/
``placeholder`` wrap options -- are UTF-8 bytes in both families: they are short constants the
caller writes once, not the text being processed.

Text in another encoding (Latin-1, CP437, Shift-JIS, ...) is transcoded at the boundary; the
library itself never sees the legacy bytes.  Two shapes are common:

* Transcode the legacy bytes to UTF-8 once with iconv(3) or ICU, then use the ``_u8`` forms
  end-to-end -- the simplest path.
* When the program already holds decoded codepoints (its own tables, or a mixed-encoding
  pipeline), use the ``_u32`` forms and re-encode the result with iconv(3) or ICU.
  :c:func:`wcwidth_encode_u32` and :c:func:`wcwidth_decode_u32` move between the two
  representations when a caller needs both:

.. code-block:: c

    /* CP437 "caf\x82" decoded to codepoints by the caller (own tables,
     * or iconv to UTF-8 then wcwidth_decode_u32). */
    uint32_t cps[] = {'c', 'a', 'f', 0xE9};  /* 0x82 in CP437 is U+00E9 */
    size_t n = 4, out_len, utf8_len, in_left, out_left;
    uint32_t *out;
    char utf8_stack[64], *utf8, *in, *buf, *outp;
    iconv_t cd;

    out = ljust_u32(cps, n, 5, " ", 1, WCWIDTH_PARSE, 1, NULL, &out_len, NULL);
    /* out is a codepoint array: {c, a, f, U+00E9, ' '} (5 entries). */

    /* Re-encode to CP437 via iconv, with UTF-8 as the interchange form.
     * A manual byte cast only works when every codepoint happens to fit
     * the target encoding; iconv reports EILSEQ for the rest, so the
     * caller can substitute or fail deliberately. */
    utf8 = wcwidth_encode_u32(out, out_len, utf8_stack, sizeof(utf8_stack), &utf8_len);
    buf = malloc(utf8_len + 1);
    cd = iconv_open("CP437", "UTF-8");
    in = utf8;
    outp = buf;
    in_left = utf8_len;
    out_left = utf8_len + 1;
    iconv(cd, &in, &in_left, &outp, &out_left);
    iconv_close(cd);
    *outp = '\0'; /* buf is the CP437 result: "caf\x82 " */
    free(buf);
    if (utf8 != utf8_stack)
        free(utf8);
    free(out);

The library deliberately provides no legacy decoding: the codepoint-array interface keeps it
free of encoding tables, and every serious C project already has a transcoding pipeline.
ICU's ``ucnv_*`` API is the portable alternative to iconv(3).

wcwidth_u32()
~~~~~~~~~~~~~

Measure the width of a single codepoint; returns ``0`` for zero-width (combining marks, ZWJ,
NUL), ``2`` for wide East Asian characters, and ``-1`` for control codes:

.. code-block:: c

    wcwidth_u32(0x0301, 1)    /* combining acute accent */   0
    wcwidth_u32(0x2640, 1)    /* female sign, narrow */      1
    wcwidth_u32(0x2460, 2)    /* CIRCLED DIGIT ONE, wide */  2
    wcwidth_u32('\n', 1)      /* control code */            -1

``ambiguous_width`` (1 or 2) sets the width of East Asian Ambiguous characters.  A single
codepoint needs no ``_u8`` variant; use :c:func:`wcswidth_u8` to measure text.

wcswidth_u32() and wcswidth_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Measure a string of codepoints or UTF-8 bytes, treating grapheme clusters (ZWJ sequences,
variation selectors, virama conjuncts, regional indicator pairs) as single units; return ``-1``
when any control code is present:

.. code-block:: c

    uint32_t family[] = {0x1F468, 0x200D, 0x1F469, 0x200D, 0x1F467};
    wcswidth_u32(family, 5, 1)   /* man ZWJ woman ZWJ girl */  2
    wcswidth_u8("café", 5, 1)                                  4

wcstwidth_u32() and wcstwidth_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Terminal-aware variants of :c:func:`wcswidth_u32` and :c:func:`wcswidth_u8`; the ``term_program``
argument applies terminal-specific corrections:

.. code-block:: c

    wcswidth_u8("☰", 3, 1)               /* U+2630, wide */  2
    wcstwidth_u8("☰", 3, 1, "vte")                            1

width_u32() and width_u8()
~~~~~~~~~~~~~~~~~~~~~~~~~~

Measure the visible width of text including terminal control sequences: colors, bold, tabstops,
horizontal cursor movement, OSC 8 hyperlinks, and OSC 66 Text Sizing.  ``width_u32()`` encodes
its codepoints to UTF-8 and measures as :c:func:`width_u8`:

.. code-block:: c

    wcwidth_width_opts_t opts = WCWIDTH_WIDTH_OPTS_DEFAULT;

    width_u8("\x1b[31mWARN\x1b[0m", 13, WCWIDTH_PARSE, &opts, NULL);  /* 4 */
    opts.tabsize = 4;
    width_u8("\t", 1, WCWIDTH_PARSE, &opts, NULL);                   /* 4 */
    width_u8("\x1b[H\x1b[2J", 7, WCWIDTH_PARSE, &opts, NULL);        /* 0 */
    width_u8("hello\x1b[5Dworld", 15, WCWIDTH_IGNORE, &opts, NULL);  /* 10 */
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

    clip_u8("中文字", 9, 0, 3, WCWIDTH_PARSE, 8, 1, NULL, true, -1, " ", 1, NULL, NULL);
    /* "中 " */

    clip_u8("中文字", 9, 1, 5, WCWIDTH_PARSE, 8, 1, NULL, true, -1, ".", 1, NULL, NULL);
    /* ".文." */

wrap_u8() and wrap_u8_text()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Wrap UTF-8 text into lines of at most ``opts.width`` display cells.  ``wrap_u8()`` collapses all
whitespace, including newlines; ``wrap_u8_text()`` preserves input newlines as paragraph breaks.
Both emit a single ``malloc``\ 'd buffer of newline-separated lines:

.. code-block:: c

    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
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

wcwidth_escape_strip()
~~~~~~~~~~~~~~~~~~~~~~

Strip all terminal escape sequences from text, preserving OSC 66 display text:

.. code-block:: c

    char buf[64];
    size_t out_len = 0;
    wcwidth_escape_strip("\x1b[31mred\x1b[0m", 12, buf, sizeof buf, &out_len);
    /* buf is "red" */

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

.. |unicode_version| replace:: 17.0.0

.. _wcwidth: https://github.com/jquast/wcwidth
.. _documentation: https://wcwidth.readthedocs.io/
.. _Corrections: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections
.. _XTVERSION: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections
.. _`wcwidth(3)`: https://man7.org/linux/man-pages/man3/wcwidth.3.html
.. _`wcswidth(3)`: https://man7.org/linux/man-pages/man3/wcswidth.3.html
