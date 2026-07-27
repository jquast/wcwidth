==========
libwcwidth
==========

A portable C11 library mainly for CLI/TUI programs that carefully produce output for Terminals.

This is a companion library of the Python `wcwidth`_ package.

The Python documentation_ closely matches this C library, except that the C API provides
UTF-8 and codepoint array interfaces.

.. _wcwidth: https://github.com/jquast/wcwidth
.. _documentation: https://wcwidth.readthedocs.io/

The lowest-level functions are derived from POSIX.1-2001 and POSIX.1-2008 `wcwidth(3)`_ and
`wcswidth(3)`_, which this library implements as `wcwidth_u32()`_ and `wcswidth_u32()`_.  These
functions return -1 when C0 and C1 control codes are present.

`width_u8()`_ is a higher-level wrapper of `wcswidth_u8()`_ that also measures terminal control
sequences, like colors, bold, tabstops, horizontal cursor movement, OSC 8 hyperlinks and others.

`wcstwidth_u8()`_ provides terminal-specific corrections, for accurate width measurement by
latest terminal program described, described in the Python Corrections_ documentation.

.. _Corrections: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections

Quick Start
-----------

Build static library::

    make

Build example programs::

    make examples

Tests::

    make test

Format::

    make format

Link with your own project::

    gcc -Ilibwcwidth/include myapp.c -Llibwcwidth/build -lwcwidth

Example Programs
----------------

Three small CLI utilities demonstrate use of this library.

**textwrap** -- Unicode, CJK, emoji, and terminal sequence-aware text wrapping::

    $ textwrap 42 README.rst
    ==========
    libwcwidth
    ==========

    A portable C11 library mainly for CLI/TUI
    programs that carefully produce output
    for Terminals.

    ...

Uses environment value, ``$COLUMNS``, if no width argument is given.  Use ``-v`` to append a red
carriage-return marker.

**width** -- report the display width of each line::

    $ width README.rst
    80
    39
    0
    67
    ...

    $ echo 'コンニチハ' | width
    10

    $ width -v <<< "café résumé"
    11:café résumé

**align** -- demonstrate left, right, and center alignment::

    $ echo "hello" | align 40
    hello                                         hello                    hello

API
---

TODO Sphinx documentation for the C API (will be) published at `libwcwidth.readthedocs.org`_.

The C API mirrors the Python API.  For detailed semantics of each function, see
the Python documentation_ for now. TODO: C API documentation will soon be published!

.. _libwcwidth.readthedocs.org: https://libwcwidth.readthedocs.org/

The ``control_codes`` parameter is the ``wcwidth_control_mode_t`` enum:

====================================  ================================================
Python                                C
====================================  ================================================
``control_codes='parse'``             ``WCWIDTH_PARSE``
``control_codes='strict'``            ``WCWIDTH_STRICT``
``control_codes='ignore'``            ``WCWIDTH_IGNORE``
====================================  ================================================

``WCWIDTH_STRICT`` returns ``-1`` and sets ``*error`` on failure.  Pass
``NULL`` for ``error`` if the specific cause isn't needed:

.. code-block:: c

    int err = 0;
    int w = width_u8("\n", 1, WCWIDTH_STRICT, &WCWIDTH_WIDTH_OPTS_DEFAULT, &err);
    if (w < 0) {
        /* err is set to an error code */
    }

Allocation: `ljust_u8()`_, `rjust_u8()`_, `center_u8()`_, `clip_u8()`_,
`wrap_u8()`_, and `wrap_u8_text()`_ return ``malloc``\ 'd strings the caller must ``free``.

For example::

    char *out = NULL;
    size_t out_len = 0;
    wcwidth_wrap_opts_t opts = WCWIDTH_WRAP_OPTS_DEFAULT;
    opts.width = 72;

    if (wrap_u8_text(text, text_len, &opts, &out, &out_len) == 0) {
        fwrite(out, 1, out_len, stdout);
        free(out);
    }

Supported Terminals
-------------------

TODO: use code generation (".. BEGIN_LIST_TERM_PROGRAMS")

The following canonical terminal names are accepted by ``term_program``::

    alacritty bobcat contour extraterm foot ghostty hyper iterm2 kitty
    konsole mintty mlterm pterm putty rio st tabby terminology vscode
    vte warp wezterm xterm

For the most accurate corrections, query the terminal's software version via
XTVERSION_ (``CSI > q``) and pass the canonical name.

.. _XTVERSION: https://wcwidth.readthedocs.io/en/latest/introduction.html#corrections

Unicode Version
---------------

TODO: use code generation!

Tables generated from Unicode |unicode_version|.

.. |unicode_version| replace:: 17.0.0

