=======
History
=======
0.8.4 *unreleased* ('master' branch, only)
  * **Bugfix** `clip()`_ hangs with OSC 8 hyperlinks in some conditions, `PR #252`_.
  * **Bugfix** width of ITU T.416 colon-format SGR color parameters, `PR #239`_.
  * **Bugfix** width of OSC 66 text sizing sequences without a text field, `PR #246`_.
  * **Changed** `iter_graphemes()`_ clustering rule GB9c for Unicode 18.0, `PR #238`_.
  * **Changed** ``ambiguous_width`` argument are now clamped to allowed range (1, 2), `PR #246`_.
  * **Changed** `wrap()`_ now raises ``ValueError`` for a width of zero or less, matching stdlib
    ``textwrap``.  Previously ``wrap('女', 0)`` returned ``['女']``, `PR #246`_.
  * **Changed** `clip()`_ arguments ``start=0`` and ``end=-1`` become optional, `PR #250`_.
  * **Updated** tables for Unicode version 18.0, `PR #238`_.

0.8.3 *2026-08-28*
  * **Bugfix** Do not hang on `wrap()`_ calls of width 1 with text containing OSC8 hyperlinks and
    wide characters, `PR #231`_.
  * **Bugfix** `clip()`_ with ``propagate_sgr=True``, should match behavior of `propagate_sgr()`_,
    `PR #235`_.

0.8.2 *2026-06-29*
  * **Bugfix** Do not raise IndexError when legacy POSIX ``n`` argument to `wcswidth()`_ or
    `wcstwidth()`_ exceeds the given string length. `PR #230`_

0.8.1 *2026-06-08*
  * **Improved** `wcstwidth()`_ with new ``zeroer``, ``narrow_wider``, and ``narrow_zeroer``
    Corrections_. `PR #226`_

0.8.0 *2026-06-05*
  * **New** support for Variation Selector 15 Emojis as narrow, `Issue #211`_.
  * **New** argument, ``term_program`` for `wcstwidth()`_, `width()`_, `clip()`_, `wrap()`_,
    `ljust()`_, `rjust()`_, and `center()`_.  ``False`` disables Corrections_; ``True``
    auto-detects by ``TERM_PROGRAM`` or ``TERM``; string values accept canonical names matching
    `list_term_programs()`_.  `wcstwidth()`_ defaults to ``True``; all other functions
    default to ``False``.
  * **Improved** performance on Python 3.15 using standard library iter_graphemes() `PR #206`_.
  * **Improved** memory usage and import time for Python 3.15 using lazy imports `PR #221`_.
  * **Bugfix** Invisible_Stacker viramas now form conjuncts (Burmese, Khmer, etc.) and
    change some Virama width calculations to match `jacobsandlund/uucode`_ (ghostty) `PR #223`_.
  * **Updated** graphemes width maximum now 2, matching Ghostty, foot, and Windows Terminal `PR
    #224`_.

0.7.0 *2026-05-02*
  * **New** support for `kitty text sizing protocol`_ (OSC 66) in `width()`_ and `clip()`_.
  * **New** `clip()`_ parameter ``control_codes='parse'``, ``'ignore'``, and ``'strict'``. `clip()`_
    is now able to clip OSC 8 hyperlinks and OSC 66 text sizing sequences.
  * **Improved** `clip()`_ and `width()`_ to support horizontal cursor sequences (``cub``, ``cuf``,
    ``hpa``). Cursor-left (``cub``) or backspace (``\b``) now overwrites text.  ``column_address``
    (``hpa``) and carriage return (``\r``) are now parsed, and more values conditionally raise
    ``ValueError`` when ``control_codes='strict'``.

0.6.0 *2026-02-06*
  * **New** Parameters ``expand_tabs``, ``replace_whitespace``, ``fix_sentence_endings``,
    ``drop_whitespace``, ``max_lines``, and ``placeholder`` for `wrap()`_, completing stdlib
    `textwrap.wrap()`_ compatibility.

0.5.3 *2026-01-30*
  * **Bugfix** Brahmic using Virama conjunct formation. `Issue #155`_, `PR #204`_.

0.5.2 *2026-01-29*
  * **Bugfix** Measurement of category ``Mc`` (`Spacing Combining Mark`_), approx.  443, has a more
    nuanced specification_, and may be categorized as either zero or wide. `PR #200`_.
  * **Bugfix** Measurement of "standalone" modifiers and regional indicators, `PR #202`_.
  * **Updated** Data files used in some automatic tests are no longer distributed. `PR #199`_

0.5.1 *2026-01-27*
  * **Updated** generated zero and wide code tables to length of 1 to complete the previously
    announced removal of historical wide and zero tables. `PR #196`_.

0.5.0 *2026-01-26*
  * **Drop Support** of many historical versions of wide and zero unicode tables.  Only the latest
    Unicode version (17.0.0) is now shipped. The related ``unicode_version='auto'`` keyword of the
    `wcwidth()`_ family of functions are ignored. `list_versions()`_ always returns a tuple of only
    a single element of the only unicode version supported. `PR #195`_.
  * **Performance** improvement of most common call without version or ambiguous_width specified by
    20%. `PR #195`_.
  * **New** Function `propagate_sgr()`_ for applying SGR state propagation to a list of lines.
    `PR #194`_.
  * **Improved** `wrap()`_ and `clip()`_ with ``propagate_sgr=True``. `PR #194`_.
  * **Bugfix** `clip()`_ zero-width characters at clipping boundaries. `PR #194`_.
  * **Bugfix** OSC Hyperlinks when broken mid-text by `wrap()`_. `PR #193`_.

0.4.0 *2026-01-25*
  * **New** Functions `iter_graphemes_reverse()`_, `grapheme_boundary_before()`_. `PR #192`_.
  * **Bugfix** OSC Hyperlinks should not be broken by `wrap()`_. `PR #191`_.

0.3.5 *2026-01-24*
  * **Bugfix** packaging of 0.3.4 contains a failing test.

0.3.4 *2026-01-24*
  * **Bugfix** `center()`_ should match the eccentric `parity padding`_.
    of `str.center()`_. `PR #188`_.

0.3.3 *2026-01-24*
  * **Performance** improvement in `width()`_. `PR #185`_.
  * **Bugfix** missing ``py.typed``, ``Typing :: Typed``. `PR #184`_.

0.3.2 *2026-01-23*
  * **Updated** type hinting for full ``mympy --strict`` compliance. `PR #183`_.

0.3.1 *2026-01-22*
  * **Performance** improvement up to 30% in `width()_`. `PR #181`_.

0.3.0 *2026-01-21*
  * **Drop Support** for Python 3.6 and 3.7. `PR #156`_.
  * **New** Function `iter_graphemes()`_. `PR #165`_.
  * **New** Functions `width()`_ and `iter_sequences()`_. `PR #166`_.
  * **New** Functions `ljust()`_, `rjust()`_, `center()`_. `PR #168`_.
  * **New** Function `wrap()`_. `PR #169`_.
  * **Performance** improvement in `wcswidth()`_. `PR #171`_.
  * **New** argument ``ambiguous_width`` to all functions. `PR #172`_.
  * **New** Functions `clip()`_ and `strip_sequences()`_. `PR #173`_.
  * **Bugfix** Characters with ``Default_Ignorable_Code_Point`` property now
    return width 0. `PR #174`_.
  * **Bugfix** Characters with ``Prepended_Concatenation_Mark`` property now
    return width 1. `PR #175`_.

0.2.14 *2025-09-22*
  * **Drop Support** for Python 2.7 and 3.5. `PR #117`_.
  * **Update** tables to include Unicode Specifications 16.0.0 and 17.0.0.
    `PR #146`_.
  * **Bugfix** U+00AD SOFT HYPHEN should measure as 1, versions 0.2.9 through
    0.2.13 measured as 0. `PR #149`_.

0.2.13 *2024-01-06*
  * **Bugfix** zero-width support for Hangul Jamo (Korean)

0.2.12 *2023-11-21*
  * **Bugfix** Re-release to remove `.pyi` files misplaced in wheel `Issue #101`_.

0.2.11 *2023-11-20*
  * **Updated** Include tests files in the source distribution (`PR #98`_, `PR #100`_).

0.2.10 *2023-11-13*
  * **Bugfix** accounting of some kinds of emoji sequences using U+FE0F
    Variation Selector 16 (`PR #97`_).
  * **Updated** specification_.

0.2.9 *2023-10-30*
  * **Bugfix** zero-width characters used in Emoji ZWJ sequences, Balinese,
    Jamo, Devanagari, Tamil, Kannada and others (`PR #91`_).
  * **Updated** to include specification_ of character measurements.

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
    API Documentation is published to readthedocs.io.
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

.. _`Spacing Combining Mark`: https://www.unicode.org/versions/latest/ch04.pdf#G134153
.. _`specification`: https://wcwidth.readthedocs.io/en/latest/specs.html
.. _`prospector`: https://github.com/landscapeio/prospector
.. _`combining`: https://en.wikipedia.org/wiki/Combining_character
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
.. _`PR #117`: https://github.com/jquast/wcwidth/pull/117
.. _`PR #146`: https://github.com/jquast/wcwidth/pull/146
.. _`PR #149`: https://github.com/jquast/wcwidth/pull/149
.. _`PR #156`: https://github.com/jquast/wcwidth/pull/156
.. _`PR #165`: https://github.com/jquast/wcwidth/pull/165
.. _`PR #166`: https://github.com/jquast/wcwidth/pull/166
.. _`PR #168`: https://github.com/jquast/wcwidth/pull/168
.. _`PR #169`: https://github.com/jquast/wcwidth/pull/169
.. _`PR #171`: https://github.com/jquast/wcwidth/pull/171
.. _`PR #172`: https://github.com/jquast/wcwidth/pull/172
.. _`PR #173`: https://github.com/jquast/wcwidth/pull/173
.. _`PR #174`: https://github.com/jquast/wcwidth/pull/174
.. _`PR #175`: https://github.com/jquast/wcwidth/pull/175
.. _`PR #181`: https://github.com/jquast/wcwidth/pull/181
.. _`PR #183`: https://github.com/jquast/wcwidth/pull/183
.. _`PR #184`: https://github.com/jquast/wcwidth/pull/184
.. _`PR #185`: https://github.com/jquast/wcwidth/pull/185
.. _`PR #188`: https://github.com/jquast/wcwidth/pull/188
.. _`PR #191`: https://github.com/jquast/wcwidth/pull/191
.. _`PR #192`: https://github.com/jquast/wcwidth/pull/192
.. _`PR #193`: https://github.com/jquast/wcwidth/pull/193
.. _`PR #194`: https://github.com/jquast/wcwidth/pull/194
.. _`PR #195`: https://github.com/jquast/wcwidth/pull/195
.. _`PR #196`: https://github.com/jquast/wcwidth/pull/196
.. _`PR #199`: https://github.com/jquast/wcwidth/pull/199
.. _`PR #200`: https://github.com/jquast/wcwidth/pull/200
.. _`PR #202`: https://github.com/jquast/wcwidth/pull/202
.. _`PR #204`: https://github.com/jquast/wcwidth/pull/204
.. _`PR #206`: https://github.com/jquast/wcwidth/pull/206
.. _`PR #221`: https://github.com/jquast/wcwidth/pull/221
.. _`PR #223`: https://github.com/jquast/wcwidth/pull/223
.. _`PR #224`: https://github.com/jquast/wcwidth/pull/224
.. _`PR #226`: https://github.com/jquast/wcwidth/pull/226
.. _`PR #230`: https://github.com/jquast/wcwidth/pull/230
.. _`PR #231`: https://github.com/jquast/wcwidth/pull/231
.. _`PR #235`: https://github.com/jquast/wcwidth/pull/235
.. _`PR #238`: https://github.com/jquast/wcwidth/pull/238
.. _`PR #239`: https://github.com/jquast/wcwidth/pull/239
.. _`PR #246`: https://github.com/jquast/wcwidth/pull/246
.. _`PR #250`: https://github.com/jquast/wcwidth/pull/250
.. _`PR #252`: https://github.com/jquast/wcwidth/pull/252
.. _`Issue #101`: https://github.com/jquast/wcwidth/issues/101
.. _`Issue #155`: https://github.com/jquast/wcwidth/issues/155
.. _`Issue #211`: https://github.com/jquast/wcwidth/issues/211
.. _`Issue #242`: https://github.com/jquast/wcwidth/issues/242
.. _`jquast/ucs-detect`: https://github.com/jquast/ucs-detect
.. _`Avram Lubkin`: https://github.com/avylove
.. _`jacobsandlund/uucode`: https://github.com/jacobsandlund/uucode
.. _`textwrap.wrap()`: https://docs.python.org/3/library/textwrap.html#textwrap.wrap
.. _`str.center()`: https://docs.python.org/3/library/stdtypes.html#str.center
.. _`wcwidth()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.wcwidth
.. _`wcswidth()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.wcswidth
.. _`wcstwidth()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.wcstwidth
.. _`width()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.width
.. _`iter_graphemes()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.iter_graphemes
.. _`iter_graphemes_reverse()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.iter_graphemes_reverse
.. _`grapheme_boundary_before()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.grapheme_boundary_before
.. _`ljust()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.ljust
.. _`rjust()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.rjust
.. _`center()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.center
.. _`wrap()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.wrap
.. _`clip()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.clip
.. _`strip_sequences()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.strip_sequences
.. _`propagate_sgr()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.propagate_sgr
.. _`iter_sequences()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.iter_sequences
.. _`list_versions()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.list_versions
.. _`list_term_programs()`: https://wcwidth.readthedocs.io/en/latest/api.html#wcwidth.list_term_programs
.. _`parity padding`: https://jazcap53.github.io/pythons-eccentric-strcenter.html
.. _`kitty text sizing protocol`: https://sw.kovidgoyal.net/kitty/text-sizing-protocol/
.. _Corrections: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections
.. _libwcwidth: https://wcwidth.readthedocs.io/en/latest/libwcwidth.html
