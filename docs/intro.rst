|pypi_downloads| |codecov| |license|

================
What is wcwidth?
================

**wcwidth** is a Python package intended for CLI programs that produce output
for terminals or terminal emulators. The functions within this package
implement the C functions, `wcwidth(3)`_ and `wcswidth(3)`_, which were defined
in the POSIX.1-2001 and POSIX.1-2008 standards. These functions return the
number of cells a unicode string is expected to occupy on the screen.

Most unicode characters have a printable length that's equal to the number of
cells that character occupies on the screen (i.e. 1 character = 1 cell).
However, there are certain categories of characters that occupy 2 cells
(full-width), and others that occupy 0 cells (zero-width).


Example
-------

To demonstrate, let's assign a string of Japanese unicode characters to the
variable ``text``.::

    >>> text = u'コンニチハ'

When we use the ``len`` from the standard Python library to check the length
of our ``text`` variable, it returns the *string length* (5 characters)
rather than the *printable length* (10 cells) of our unicode string. This
difference produces unintended results when we attempt to align the output
from our ``text`` variable within the terminal (example output shown below
using the ``rjust`` function from the standard Python library).::

    >>> print(len(text))
    5

    >>> from wcwidth import wcswidth
    >>> print(wcswidth(text))
    10

    >>> print(text.rjust(20, '_'))
    _______________コンニチハ

We can solve this problem by implementing our own ``wc_rjust`` function.::

   >>> def wc_rjust(text, length, padding=' '):
   ...    from wcwidth import wcswidth
   ...    return padding * max(0, (length - wcswidth(text))) + text
   ...

We can see that the new ``wc_rjust`` function produces the expected output
within the terminal, thanks to ``wcwidth``::

   >>> print(wc_rjust('コンニチハ', 20, '_'))
   __________コンニチハ




===============
Getting Started
===============

The source code for this package is currently hosted on GitHub at: 
https://github.com/jquast/wcwidth

Binary installers for the latest released version are available at:
https://pypi.org/project/wcwidth/

The complete API documentation for this package can be referenced at:
https://wcwidth.readthedocs.org


Installation
------------

The stable version of this package is maintained on PyPI and can be installed
using the following ``pip`` command:::

    pip install wcwidth


Unicode Version Config
----------------------

The unicode version used for your terminal can be set using the 
``UNICODE_VERSION`` environment variable.

Simply export the ``UNICODE_VERSION`` environment variable using the following
shell command (with variable set to the desired version number):::

    $ export UNICODE_VERSION=13.0

If the ``UNICODE_VERSION`` environment variable is missing or unspecified, the
latest version is used. If your terminal or terminal emulator does not export
this variable, you can utilize the `jquast/ucs-detect`_ utility to
automatically detect and export it to your shell.


wcwidth, wcswidth
-----------------
Use function ``wcwidth()`` to determine the length of a *single unicode
character*, and ``wcswidth()`` to determine the length of many, a *string
of unicode characters*.

Briefly, return values of function ``wcwidth()`` are:::

    -1
      --  Indeterminate (not printable).

    0
      --  Does not advance the cursor, such as NULL or Combining.

    2
      --  Characters of category East Asian Wide (W) or East Asian
          Full-width (F) which are displayed using two terminal cells.

    1
      --  All others.

Function ``wcswidth()`` simply returns the sum of all values for each character
within the string, or ``-1`` if there are any indeterminate (non-printable)
characters within the string.




==================================
Helpful Resources for Contributors
==================================

Updating source code
--------------------

Make changes locally by installing ``wcwidth`` in editable mode with ``pip``::

   pip install -e .


Executing unit tests
--------------------

This project uses tox_ for unit testing. To run all of the unit tests, execute
the following command within the project directory.::

   tox -e py36,py37,py38,py39,py310,py311,py312


Updating Unicode Data
----------------------

Execute the following command to regenerate the Python code tables from the
latest Unicode specification data files:::

   tox -e update

The script that performs the update is ``bin/update-tables.py`` and requires
Python 3.9 or later. It is recommended but not necessary to run this script
with the latest stable version of Python, because that version will have the
latest ``unicodedata`` for generating comments.


Building Documentation
----------------------

This project is using `sphinx`_ 4.5 to build documentation::

   tox -e sphinx

The output files will be generated in the ``docs/_build/html/`` directory of
this repository.


Updating Requirements
---------------------

This project is using `pip-tools`_ to manage requirements.

To update the requirements for updating unicode data, run::

   tox -e update_requirements_update

To update the requirements for testing, run::

   tox -e update_requirements37,update_requirements39

To update the requirements for building documentation, run::

   tox -e update_requirements_docs


Utilities
---------

Supplemental tools for browsing and testing terminals for wide unicode
characters can be found in the `bin/`_ directory of this project's source
code. 

Before attempting to use any of the tools within that directory, you must
first execute the following ``pip`` command from this project's root
directory:::

    pip install -r requirements-develop.txt
    
As an example, the following command will open an interactive browser for
testing::

  python ./bin/wcwidth-browser.py




====
Uses
====

This library is used in:

- `jquast/blessed`_: a thin, practical wrapper around terminal capabilities in
  Python.

- `prompt-toolkit/python-prompt-toolkit`_: a Library for building powerful
  interactive command lines in Python.

- `dbcli/pgcli`_: Postgres CLI with autocompletion and syntax highlighting.

- `thomasballinger/curtsies`_: a Curses-like terminal wrapper with a display
  based on compositing 2d arrays of text.

- `selectel/pyte`_: Simple VTXXX-compatible linux terminal emulator.

- `astanin/python-tabulate`_: Pretty-print tabular data in Python, a library
  and a command-line utility.

- `rspeer/python-ftfy`_: Fixes mojibake and other glitches in Unicode
  text.

- `nbedos/termtosvg`_: Terminal recorder that renders sessions as SVG
  animations.

- `peterbrittain/asciimatics`_: Package to help people create full-screen text
  UIs.

- `python-cmd2/cmd2`_: A tool for building interactive command line apps

- `stratis-storage/stratis-cli`_: CLI for the Stratis project

- `ihabunek/toot`_: A Mastodon CLI/TUI client

- `saulpw/visidata`_: Terminal spreadsheet multitool for discovering and
  arranging data

===============
Other Languages
===============

- `timoxley/wcwidth`_: JavaScript
- `janlelis/unicode-display_width`_: Ruby
- `alecrabbit/php-wcwidth`_: PHP
- `Text::CharWidth`_: Perl
- `bluebear94/Terminal-WCWidth`_: Perl 6
- `mattn/go-runewidth`_: Go
- `grepsuzette/wcwidth`_: Haxe
- `aperezdc/lua-wcwidth`_: Lua
- `joachimschmidt557/zig-wcwidth`_: Zig
- `fumiyas/wcwidth-cjk`_: `LD_PRELOAD` override
- `joshuarubin/wcwidth9`_: Unicode version 9 in C

=======
History
=======

Unreleased
  * **Updated** tables to include Unicode Specification 16.0.0 and 17.0.0.

0.2.13 *2024-01-06*
  * **Bugfix** zero-width support for Hangul Jamo (Korean)

0.2.12 *2023-11-21*
  * re-release to remove .pyi file misplaced in wheel files `Issue #101`_.

0.2.11 *2023-11-20*
  * Include tests files in the source distribution (`PR #98`_, `PR #100`_).

0.2.10 *2023-11-13*
  * **Bugfix** accounting of some kinds of emoji sequences using U+FE0F
    Variation Selector 16 (`PR #97`_).
  * **Updated** `Specification <Specification_from_pypi_>`_.

0.2.9 *2023-10-30*
  * **Bugfix** zero-width characters used in Emoji ZWJ sequences, Balinese,
    Jamo, Devanagari, Tamil, Kannada and others (`PR #91`_).
  * **Updated** to include `Specification <Specification_from_pypi_>`_ of
    character measurements.

0.2.8 *2023-09-30*
  * Include requirements files in the source distribution (`PR #82`_).

0.2.7 *2023-09-28*
  * **Updated** tables to include Unicode Specification 15.1.0.
  * Include ``bin``, ``docs``, and ``tox.ini`` in the source distribution

0.2.6 *2023-01-14*
  * **Updated** tables to include Unicode Specification 14.0.0 and 15.0.0.
  * **Changed** developer tools to use pip-compile, and to use jinja2 templates
    for code generation in `bin/update-tables.py` to prepare for possible
    compiler optimization release.

0.2.1 .. 0.2.5 *2020-06-23*
  * **Repository** changes to update tests and packaging issues, and
    begin tagging repository with matching release versions.

0.2.0 *2020-06-01*
  * **Enhancement**: Unicode version may be selected by exporting the
    Environment variable ``UNICODE_VERSION``, such as ``13.0``, or ``6.3.0``.
    See the `jquast/ucs-detect`_ CLI utility for automatic detection.
  * **Enhancement**:
    API Documentation is published to readthedocs.org.
  * **Updated** tables for *all* Unicode Specifications with files
    published in a programmatically consumable format, versions 4.1.0
    through 13.0

0.1.9 *2020-03-22*
  * **Performance** optimization by `Avram Lubkin`_, `PR #35`_.
  * **Updated** tables to Unicode Specification 13.0.0.

0.1.8 *2020-01-01*
  * **Updated** tables to Unicode Specification 12.0.0. (`PR #30`_).

0.1.7 *2016-07-01*
  * **Updated** tables to Unicode Specification 9.0.0. (`PR #18`_).

0.1.6 *2016-01-08 Production/Stable*
  * ``LICENSE`` file now included with distribution.

0.1.5 *2015-09-13 Alpha*
  * **Bugfix**:
    Resolution of "combining_ character width" issue, most especially
    those that previously returned -1 now often (correctly) return 0.
    resolved by `Philip Craig`_ via `PR #11`_.
  * **Deprecated**:
    The module path ``wcwidth.table_comb`` is no longer available,
    it has been superseded by module path ``wcwidth.table_zero``.

0.1.4 *2014-11-20 Pre-Alpha*
  * **Feature**: ``wcswidth()`` now determines printable length
    for (most) combining_ characters.  The developer's tool
    `bin/wcwidth-browser.py`_ is improved to display combining_
    characters when provided the ``--combining`` option
    (`Thomas Ballinger`_ and `Leta Montopoli`_ `PR #5`_).
  * **Feature**: added static analysis (prospector_) to testing
    framework.

0.1.3 *2014-10-29 Pre-Alpha*
  * **Bugfix**: 2nd parameter of wcswidth was not honored.
    (`Thomas Ballinger`_, `PR #4`_).

0.1.2 *2014-10-28 Pre-Alpha*
  * **Updated** tables to Unicode Specification 7.0.0.
    (`Thomas Ballinger`_, `PR #3`_).

0.1.1 *2014-05-14 Pre-Alpha*
  * Initial release to pypi, Based on Unicode Specification 6.3.0

This code was originally derived directly from C code of the same name,
whose latest version is available at
https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c::

 * Markus Kuhn -- 2007-05-26 (Unicode 5.0)
 *
 * Permission to use, copy, modify, and distribute this software
 * for any purpose and without fee is hereby granted. The author
 * disclaims all warranties with regard to this software.

.. _`Specification_from_pypi`: https://wcwidth.readthedocs.io/en/latest/specs.html
.. _`tox`: https://tox.wiki/en/latest/
.. _`prospector`: https://github.com/landscapeio/prospector
.. _`combining`: https://en.wikipedia.org/wiki/Combining_character
.. _`bin/`: https://github.com/jquast/wcwidth/tree/master/bin
.. _`bin/wcwidth-browser.py`: https://github.com/jquast/wcwidth/blob/master/bin/wcwidth-browser.py
.. _`Thomas Ballinger`: https://github.com/thomasballinger
.. _`Leta Montopoli`: https://github.com/lmontopo
.. _`Philip Craig`: https://github.com/philipc
.. _`PR #3`: https://github.com/jquast/wcwidth/pull/3
.. _`PR #4`: https://github.com/jquast/wcwidth/pull/4
.. _`PR #5`: https://github.com/jquast/wcwidth/pull/5
.. _`PR #11`: https://github.com/jquast/wcwidth/pull/11
.. _`PR #18`: https://github.com/jquast/wcwidth/pull/18
.. _`PR #30`: https://github.com/jquast/wcwidth/pull/30
.. _`PR #35`: https://github.com/jquast/wcwidth/pull/35
.. _`PR #82`: https://github.com/jquast/wcwidth/pull/82
.. _`PR #91`: https://github.com/jquast/wcwidth/pull/91
.. _`PR #97`: https://github.com/jquast/wcwidth/pull/97
.. _`PR #98`: https://github.com/jquast/wcwidth/pull/98
.. _`PR #100`: https://github.com/jquast/wcwidth/pull/100
.. _`Issue #101`: https://github.com/jquast/wcwidth/issues/101
.. _`jquast/blessed`: https://github.com/jquast/blessed
.. _`selectel/pyte`: https://github.com/selectel/pyte
.. _`thomasballinger/curtsies`: https://github.com/thomasballinger/curtsies
.. _`dbcli/pgcli`: https://github.com/dbcli/pgcli
.. _`prompt-toolkit/python-prompt-toolkit`: https://github.com/prompt-toolkit/python-prompt-toolkit
.. _`timoxley/wcwidth`: https://github.com/timoxley/wcwidth
.. _`wcwidth(3)`:  https://man7.org/linux/man-pages/man3/wcwidth.3.html
.. _`wcswidth(3)`: https://man7.org/linux/man-pages/man3/wcswidth.3.html
.. _`astanin/python-tabulate`: https://github.com/astanin/python-tabulate
.. _`janlelis/unicode-display_width`: https://github.com/janlelis/unicode-display_width
.. _`rspeer/python-ftfy`: https://github.com/rspeer/python-ftfy
.. _`alecrabbit/php-wcwidth`: https://github.com/alecrabbit/php-wcwidth
.. _`Text::CharWidth`: https://metacpan.org/pod/Text::CharWidth
.. _`bluebear94/Terminal-WCWidth`: https://github.com/bluebear94/Terminal-WCWidth
.. _`mattn/go-runewidth`: https://github.com/mattn/go-runewidth
.. _`grepsuzette/wcwidth`: https://github.com/grepsuzette/wcwidth
.. _`jquast/ucs-detect`: https://github.com/jquast/ucs-detect
.. _`Avram Lubkin`: https://github.com/avylove
.. _`nbedos/termtosvg`: https://github.com/nbedos/termtosvg
.. _`peterbrittain/asciimatics`: https://github.com/peterbrittain/asciimatics
.. _`aperezdc/lua-wcwidth`: https://github.com/aperezdc/lua-wcwidth
.. _`joachimschmidt557/zig-wcwidth`: https://github.com/joachimschmidt557/zig-wcwidth
.. _`fumiyas/wcwidth-cjk`: https://github.com/fumiyas/wcwidth-cjk
.. _`joshuarubin/wcwidth9`: https://github.com/joshuarubin/wcwidth9
.. _`python-cmd2/cmd2`: https://github.com/python-cmd2/cmd2
.. _`stratis-storage/stratis-cli`: https://github.com/stratis-storage/stratis-cli
.. _`ihabunek/toot`: https://github.com/ihabunek/toot
.. _`saulpw/visidata`: https://github.com/saulpw/visidata
.. _`pip-tools`: https://pip-tools.readthedocs.io/
.. _`sphinx`: https://www.sphinx-doc.org/
.. |pypi_downloads| image:: https://img.shields.io/pypi/dm/wcwidth.svg?logo=pypi
    :alt: Downloads
    :target: https://pypi.org/project/wcwidth/
.. |codecov| image:: https://codecov.io/gh/jquast/wcwidth/branch/master/graph/badge.svg
    :alt: codecov.io Code Coverage
    :target: https://app.codecov.io/gh/jquast/wcwidth/
.. |license| image:: https://img.shields.io/pypi/l/wcwidth.svg
    :target: https://pypi.org/project/wcwidth/
    :alt: MIT License
