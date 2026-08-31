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

Every string function takes an explicit length, and every one of them reads exactly that many
units:

``_u32`` functions
    count codepoints in the array,
``_u8`` functions
    count bytes.

There is no "measure it for me" sentinel.  A library that accepts one has to call ``strlen(3)``
on your behalf, which means trusting that a NUL exists inside the buffer -- when it does not, the
scan runs off the end of the allocation, and the bug surfaces far from the call that caused it.
Passing the length you already know is both faster and impossible to get wrong in that way.  When
the text really is a NUL-terminated C string, write ``strlen(text)`` at the call site, where the
assumption is visible.

Because the length is authoritative, a NUL is an ordinary zero-width character rather than a
terminator: text may contain NULs anywhere, they measure as zero-width, and they survive into the
output of the transforms, whose ``*out_len`` reports the true byte length.

Alternate encodings
~~~~~~~~~~~~~~~~~~~

This library is UTF-8 centric.  Every ``_u8`` function takes and returns UTF-8 bytes; every
``_u32`` function takes and returns a ``uint32_t`` codepoint array.  The two families mirror
each other: use ``_u8`` when your text is UTF-8, ``_u32`` when you hold decoded codepoints.
The measurement functions (``wcswidth_u32()``, ``wcstwidth_u32()``, ``width_u32()``) are
encoding-neutral either way -- a width number is a width number.

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
  ``wcwidth_encode_u32()`` and ``wcwidth_decode_u32()`` move between the two
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
    if (cd == (iconv_t) -1)
        return -1;
    in = utf8;
    outp = buf;
    in_left = utf8_len;
    out_left = utf8_len;  /* reserve the final byte of buf for the NUL */
    if (iconv(cd, &in, &in_left, &outp, &out_left) == (size_t) -1)
        ; /* EILSEQ: this codepoint has no CP437 form -- substitute or fail */
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

``width_u32()`` and ``width_u8()`` parse the sequences that move the cursor
within a line or change how much room text occupies: SGR, horizontal cursor
movement (CUF, CUB, HPA), and OSC 66 text sizing.  That is the whole of it --
this is not a general terminal emulator.  Every other recognized sequence is
counted as zero-width, and sequences whose effect on the column cannot be
known from the text alone -- screen clears, scrolls, vertical movement -- are
reported as indeterminate, which is what ``WCWIDTH_STRICT`` turns into an
error.  ``wcswidth_*()`` and ``wcstwidth_*()`` parse nothing at all: matching
their Python counterparts, they take no ``wcwidth_control_mode_t`` and return
-1 for any escape sequence.

The text transforms are simpler than the Python ones:

* OSC 8 hyperlinks are not implemented at all.  Python parses them, clips
  them as semantic units, and continues them across wrapped lines with a
  synthesized ``id=`` parameter; the C11 library treats an OSC 8 sequence as
  an ordinary zero-width OSC, so it measures correctly but is never
  rewritten.  A ``clip_u8()`` window that begins or ends inside a hyperlink
  therefore yields an unbalanced pair -- clipping ``[0, 2)`` keeps the opener
  but drops the closer, leaving the link open across whatever is printed
  next -- and ``wrap_u8()`` does not re-open the link on each line.  Callers
  that transform hyperlinked text must re-emit the opener and terminator
  themselves.
* ``clip_u8()`` does not parse horizontal cursor movement (the Python
  ``overtyping`` painter's algorithm has no C11 counterpart) or OSC 66 text
  sizing; every sequence other than SGR is passed through as zero-width.
* ``wrap_u8()`` and ``wrap_u8_text()`` fit line width using ``width_u8()``,
  but split words on the ASCII space alone, where Python's ``wrap()`` splits
  on any run of whitespace.  Python's ``break_on_hyphens``,
  ``fix_sentence_endings``, and ``propagate_sgr`` have no counterpart here, so
  ``wcwidth_wrap_opts_t`` does not offer them: a hyphenated word is broken
  mid-word rather than at the hyphen, a sentence-ending period is not widened
  to two spaces, and SGR state is not re-opened on each wrapped line, so
  colour set before a break does not survive it.

``ljust_u8()``, ``rjust_u8()``, and ``center_u8()`` have nothing to list here:
they delegate measurement to ``width_u8()`` and produce the same output as the
Python ``ljust()``, ``rjust()``, and ``center()``.

Malformed escape sequences
~~~~~~~~~~~~~~~~~~~~~~~~~~

A sequence that is *well formed* -- one a conforming program would actually
emit -- measures the same here as in Python.  A sequence that is malformed may
not: an unterminated CSI or OSC, a lone ESC at the end of a buffer, or an
introducer followed by a byte the standard does not allow there can differ by
a cell or two, and ``wcwidth_escape_strip()`` may keep bytes that Python's
``strip_sequences()`` drops, or the reverse.  Feeding random escape soup to
both, roughly 2% of inputs measure differently.

The cause is that Python recognizes sequences with a regular expression while
this library uses a hand-written scanner, and the two do not agree on where a
malformed sequence ends.  How narrow that is worth stating: for a character-set
designation ``ESC (``, every one of the 79 final bytes ECMA-48 permits
(``0x30``-``0x7e``, which is every real designation -- ``ESC ( B`` for US
ASCII, ``ESC ( 0`` for DEC line drawing, and the rest) measures identically in
both, as does every intermediate byte.  Of the 33 C0 controls, which the
standard does not permit in that position at all, exactly one differs:

.. code-block:: c

    width_u8("X\x1b(\nY", 5, WCWIDTH_PARSE, &opts, NULL);   /* 2; Python says 3 */

Python's pattern is ``\x1b[()].`` and ``.`` does not match a newline, so it
leaves those three bytes as literal text; this library consumes them as a
sequence.  A real terminal does neither -- ECMA-48 executes a C0 control
encountered inside an escape sequence and keeps waiting for the final byte, so
xterm moves the cursor down a line and the sequence stays open.

The disagreement is the same under ``WCWIDTH_IGNORE``, which strips control
codes but still has to decide where each sequence ends.

Neither answer is more useful than the other, since neither is what a terminal
would do, and terminals differ among themselves on malformed input.  If your
text is arbitrary bytes rather than sequences you emitted yourself, do not
depend on the two implementations agreeing.  ``WCWIDTH_STRICT`` is the
exception: it refuses indeterminate input rather than guessing a width for it,
and over the same random-escape corpus the C and Python implementations
returned identical results -- the same widths, and the same errors with the
same messages -- for every input.

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
.. _XTVERSION: https://vtdn.dev/docs/dcs/xtversion/
.. _`C11 API`: https://wcwidth.readthedocs.io/en/latest/api_c.html
.. _clang-format: https://clang.llvm.org/docs/ClangFormat.html
.. _`wcwidth(3)`: https://man7.org/linux/man-pages/man3/wcwidth.3.html
.. _`wcswidth(3)`: https://man7.org/linux/man-pages/man3/wcswidth.3.html
