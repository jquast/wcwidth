.. image:: https://img.shields.io/travis/jquast/wcwidth.svg
    :target: https://travis-ci.org/jquast/wcwidth
    :alt: Travis Continous Integration

.. image:: https://img.shields.io/coveralls/jquast/wcwidth.svg
    :target: https://coveralls.io/r/jquast/wcwidth
    :alt: Coveralls Code Coverage

.. image:: https://img.shields.io/pypi/v/wcwidth.svg
    :target: https://pypi.python.org/pypi/wcwidth/
    :alt: Latest Version

.. image:: https://pypip.in/license/wcwidth/badge.svg
    :target: https://pypi.python.org/pypi/wcwidth/
    :alt: License

.. image:: https://pypip.in/wheel/wcwidth/badge.svg
    :alt: Wheel Status

.. image:: https://img.shields.io/pypi/dm/wcwidth.svg
    :target: https://pypi.python.org/pypi/wcwidth/
    :alt: Downloads


============
Introduction
============

This API is mainly for Terminal Emulator implementors, or those writing
programs that expect to interpreted by a terminal emulator and wish to
determine the printable width of a string on a Terminal.

Usually, the length of the string is equivalent to the number of cells
it occupies except that there are are also some categories of characters
which occupy 2 or even 0 cells.  POSIX-conforming systems provide
``wcwidth(3)`` and ``wcswidth(3)`` of which this module's interface mirrors
precisely.

This library aims to be forward-looking, portable, and most correct.  The most
current release of this API is based from Unicode Standard release files:

``EastAsianWidth-8.0.0.txt``
  *2015-02-10, 21:00:00 GMT [KW, LI]*

``DerivedGeneralCategory-8.0.0.txt``
  *2015-02-13, 13:47:11 GMT [MD]*

Installation
------------

The stable version of this package is maintained on pypi, install using pip::

    pip install wcwidth

wcwidth, wcswidth
-----------------
Use ``wcwidth`` to determine the length of a *single character*,
and ``wcswidth`` to determine the length of a *string of characters*.

To Display ``u'コンニチハ'`` right-adjusted on screen of 80 columns::

    >>> from wcwidth import wcswidth
    >>> text = u'コンニチハ'
    >>> print(u' ' * (80 - wcswidth(text)) + text)

Return Values
-------------

``-1``
  Indeterminate (not printable).

``0``
  Does not advance the cursor, such as NULL or Combining.

``2``
  Characters of category East Asian Wide (W) or East Asian
  Full-width (F) which are displayed using two terminal cells.

``1``
  All others.

``wcswidth()`` simply returns the sum of all values along a string, or
``-1`` in total if any part of the string results in -1.  A more exact
list of conditions and return values may be found in the docstring::

    $ pydoc wcwidth


Discrepancies
-------------

This library does its best to return the most appropriate return value for a
very particular terminal user interface where a monospaced fixed-cell
rendering is expected.  As the POSIX Terminal programming interfaces do not
provide any means to determine the unicode support level, we can only do our
best to return the *correct* result for the given codepoint, and not what any
terminal emulator particular does.

Python's determination of non-zero combining_ characters may also be based on
an older specification.

You may determine an exacting list of these discrepancies using the project
files `wcwidth-libc-comparator.py <https://github.com/jquast/wcwidth/tree/master/bin/wcwidth-libc-comparator.py>`_ and `wcwidth-combining-comparator.py <https://github.com/jquast/wcwidth/tree/master/bin/wcwidth-combining-comparator.py>`_.


==========
Developing
==========

Execute the command ``python setup.py develop`` to prepare an environment
for running tests (``python setup.py test``), updating tables (
``python setup.py update``) or using any of the scripts in the ``bin/``
sub-folder.  These files are only made available in the source repository.


Updating Tables
---------------

The command ``python setup.py update`` will fetch the following resources:

- http://www.unicode.org/Public/UNIDATA/EastAsianWidth.txt
- http://www.unicode.org/Public/UNIDATA/extracted/DerivedGeneralCategory.txt

And generates the table files:

- `wcwidth/table_wide.py <https://github.com/jquast/wcwidth/tree/master/wcwidth/table_wide.py>`_
- `wcwidth/table_zero.py <https://github.com/jquast/wcwidth/tree/master/wcwidth/table_zero.py>`_

wcwidth.c
---------

This code was originally derived directly from C code of the same name,
whose latest version is available at: `wcwidth.c
<http://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c>`_ And is authored by Markus
Kuhn -- 2007-05-26 (Unicode 5.0)

Examples
--------

This library is used in:

- `jquast/blessed`_, a simplified wrapper around curses.

- `jonathanslenders/python-prompt-toolkit`_, a Library for building powerful
  interactive command lines in Python.

Additional tools for displaying and testing wcwidth are found in the `bin/
<https://in.linkedin.com/in/chiragjog>`_ folder of this project. They are not
distributed as a script or part of the module.

.. _`jquast/blessed`: https://github.com/jquast/blessed
.. _`jonathanslenders/python-prompt-toolkit`: https://github.com/jonathanslenders/python-prompt-toolkit


License
-------

MIT license::

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

The original license is as follows::

    Permission to use, copy, modify, and distribute this software
    for any purpose and without fee is hereby granted. The author
    disclaims all warranties with regard to this software.

Mr. Kuhn resides in the UK which allows some protection from Copyright law.
As a US citizen, I feel compelled to chose an OSI-approved license to ensure
both my safety and yours, therefore the least-restrictive among them, the MIT
license was chosen.


Changes
-------

0.1.4 *2014-11-20 Pre-Alpha*
  * **Feature**: ``wcswidth()`` now determines printable length
    for (most) combining characters.  The developer's tool
    `bin/wcwidth-browser.py`_ is improved to display combining_
    characters when provided the ``--combining`` option
    (`Thomas Ballinger`_ and `Leta Montopoli`_ `PR #5`_).
  * added static analysis (prospector_) to testing framework.

0.1.3 *2014-10-29 Pre-Alpha*
  * **Bugfix**: 2nd parameter of wcswidth was not honored.
    (`Thomas Ballinger`_, `PR #4`).

0.1.2 *2014-10-28 Pre-Alpha*
  * **Updated** tables to Unicode Specification 7.0.0.
    (`Thomas Ballinger`_, `PR #3`).

0.1.1 *2014-05-14 Pre-Alpha*
  * Initial release to pypi, Based on Unicode Specification 6.3.0

.. _`prospector`: https://github.com/landscapeio/prospector
.. _`combining`: https://en.wikipedia.org/wiki/Combining_character
.. _`bin/wcwidth-browser.py`: https://github.com/jquast/wcwidth/tree/master/bin/wcwidth-browser.py
.. _`Thomas Ballinger`: https://github.com/thomasballinger
.. _`Leta Montopoli`: https://github.com/lmontopo
.. _`Philip Craig`: https://github.com/philipc
.. _`PR #3`: https://github.com/jquast/wcwidth/pull/3
.. _`PR #4`: https://github.com/jquast/wcwidth/pull/4
.. _`PR #5`: https://github.com/jquast/wcwidth/pull/5
.. _`PR #11`: https://github.com/jquast/wcwidth/pull/11
