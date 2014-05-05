.. image:: https://img.shields.io/travis/jquast/wcwidth.svg
    :alt: Travis Continous Integration

.. image:: https://img.shields.io/coveralls/jquast/wcwidth.svg
    :alt: Coveralls Code Coverage

.. image:: https://img.shields.io/pypi/v/wcwidth.svg
    :alt: Latest Version

.. image:: https://pypip.in/license/wcwidth/badge.svg
    :alt: License

.. image:: https://img.shields.io/pypi/dm/wcwidth.svg
    :alt: Downloads


============
Introduction
============

This API is mainly for Terminal Emulator implementors -- any python program
that attempts to determine the printable width of a string on a Terminal.

It is certainly possible to use your Operating System's ``wcwidth()`` and
``wcswidth()`` calls if it is POSIX-conforming, but this would not be possible
on non-POSIX platforms, such as Windows, or for alternative Python
implementations, such as jython.

Furthermore, testing (`wcwidth-libc-comparator.py`_) has shown that libc
wcwidth() is particularly out of date on most operating systems, reporting -1
for a great many characters that are actually a displayable width of 1 or 2.

Problem
-------

You may have noticed some characters especially Chinese, Japanese, and
Korean (collectively known as the *CJK Unified Ideographs*) consume more
than 1 terminal cell.

In python, if you ask for the length of the string, ``u'コンニチハ'``
(Japanese: Hello), it is correctly determined to be a length of **5**.

However, if you were to print this to a Terminal Emulator, such as xterm,
urxvt, Terminal.app, or PuTTY, it would consume **10** *cells* (columns) --
two for each symbol.

On an 80-wide terminal, the following would wrap along the margin, instead
of displaying it right-aligned as desired::

    >>> text = u'コンニチハ'
    >>> print(text.rjust(80))
                                                                                 コン
    ニチハ

Solution
--------

This API allows one to determine the printable length of these strings,
that the length of ``wcwidth(u'コ')`` is reported as ``2``, and
``wcswidth(u'コンニチハ')`` as ``10``.

This allows one to determine the printable effects of displaying *CJK*
characters on a terminal emulator.

Installation
------------

The stable version of this package is maintained on pypi, install using pip::

    pip install wcwidth

wcwidth, wcswidth
-----------------
Use ``wcwidth`` to determine the length of a single character,
and ``wcswidth`` to determine the length of a string of characters.

To Display ``u'コンニチハ'`` right-adjusted on screen of 80 columns::

    >>> from wcwidth import wcswidth
    >>> text = u'コンニチハ'
    >>> print(u' ' * (80 - wcswidth(text)) + text)
                                                                           コンニチハ


Values
------

See the docstring for ``wcwidth()``, general overview of return values:

   - ``-1``: indeterminate, such as combining_ characters.

   - ``0``: do not advance the cursor, such as NULL.

   - ``2``: East_Asian_Width property values W and F (Wide and Full-width).

   - ``1``: all others.

``wcswidth()`` simply returns the sum of all values along a string, or
``-1`` if it has occurred for any value returned by ``wcwidth()``.

==========
Developing
==========

Updating Tables
---------------

The command ``python setup.py update`` will fetch the following resources:

    - http://www.unicode.org/Public/UNIDATA/EastAsianWidth.txt
    - http://www.unicode.org/Public/UNIDATA/extracted/DerivedCombiningClass.txt

Generating the table files `wcwidth/table_wide.py`_ and `wcwidth/table_comb.py`_.

wcwidth.c
---------

This code was originally derived directly from C code of the same name,
whose latest version is available at: `wcwidth.c`_ And is authored by
Markus Kuhn -- 2007-05-26 (Unicode 5.0)

Any subsequent changes were done by directly testing against the various libc
implementations of POSIX-compliant Operating Systems, such as Mac OSX, Linux,
and OpenSolaris.

Examples
--------

This library is used in `jquast/blessed`_ so that strings containing both
terminal sequences and CJK characters may be word-wrapped or right-adjusted
on a terminal.

Additional tools for displaying and testing wcwidth is found in the ``bin/``
folder of this project (github link: `wcwidth/bin`_). They are not
distributed as a script or part of the module.

Todo
----

It is my wish that `combining`_ characters are understood. Currently,
any string containing combining characters will always return ``-1``.


License
-------

The original license is as follows::

    Permission to use, copy, modify, and distribute this software
    for any purpose and without fee is hereby granted. The author
    disclaims all warranties with regard to this software.

No specific licensing is specified, and Mr. Kuhn resides in the UK which allows
some protection from Copyrighting. As this derivative is based on US Soil,
an OSI-approved license that appears most-alike has been chosen, the MIT license::

    The MIT License (MIT)

    Copyright (c) 2014 <contact@jeffquast.com>

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.

.. _`jquast/blessed`: https://github.com/jquast/blessed
.. _`wcwidth/bin`: https://github.com/jquast/wcwidth/tree/master/bin
.. _`wcwidth-libc-comparator.py`: https://github.com/jquast/wcwidth/tree/master/bin/wcwidth-libc-comparator.py
.. _`wcwidth/table_wide.py`: https://github.com/jquast/wcwidth/tree/master/wcwidth/table_wide.py
.. _`wcwidth/table_comb.py`: https://github.com/jquast/wcwidth/tree/master/wcwidth/table_comb.py
.. _`combining`: https://en.wikipedia.org/wiki/Combining_character
.. _`wcwidth.c`: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
