Introduction
============

This API is mainly for Terminal Emulator implementors -- any python program
that attempts to determine the printable width of a string on a Terminal.

It is certainly possible to use your Operating System's ``wcwidth()`` and
``wcswidth()`` calls if it is POSIX-conforming, but this would not be possible
on non-POSIX platforms, such as Windows, or for alternative Python
implementations, such as jython.

Problem
-------

You may have noticed some characters of the Unicode specification,
especially Chinese, Japanese, and Korean -- collectively known as the
*CJK Unified Ideographs* consume more than 1 terminal cell.

In python, if you ask for the length of the string, ``u'コンニチハ'`` 
(Japanese: Hello), it is correctly determined to be a length of **5**.

However, if you were to print this to a Terminal Emulator, such as xterm,
urxvt, Terminal.app, or PuTTY, it would consume **10** columns, or *cells*,
two for each symbol.

Solution
--------

This API allows one to determine the printable length of a single cell, such
that::

        wcwidth(u'コ') == 2
        wcswidth(u'コンニチハ') == 10


Installation
============

Simply install from pip::

    pip install wcwidth

Use
===

xxx

References
==========

http://www.unicode.org/Public/UNIDATA/EastAsianWidth.txt

wcwidth.c
---------

This code is derived directly from C code of the same name, whose latest
version is available at: http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c
And is authored by Markus Kuhn -- 2007-05-26 (Unicode 5.0)

Any subsequent changes were done by directly testing against the various libc
implementations of POSIX-compliant Operating Systems, such as Mac OSX, Linux,
and OpenSolaris.

License
=======

The original license is as follows::

    Permission to use, copy, modify, and distribute this software
    for any purpose and without fee is hereby granted. The author
    disclaims all warranties with regard to this software.

No specific licensing is specified, and Mr. Kuhn resides in the UK which allows
some protection from Copyrighting, as a derivative from US Soil, an OSI-approved
license that appears most-alike has been chosen, the MIT license::

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
