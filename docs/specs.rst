.. _Specification:

=============
Specification
=============

This document defines how this Python wcwidth library measures the printable width of characters of
a string. This is not meant to an official standard, but as a terse description of the lowest level
API functions :func:`wcwidth.wcwidth` and  :func:`wcwidth.wcswidth`.

The :func:`wcwidth.iter_graphemes` function is mainly specified by `Unicode Standard Annex #29`_.

Width of -1
-----------

The following have a column width of -1 for function :func:`wcwidth.wcwidth`

- ``C0`` control characters (`U+0001`_ through `U+001F`_).
- ``C1`` control characters and ``DEL`` (`U+007F`_ through `U+00A0`_).

If any character in sequence contains ``C0`` or ``C1`` control characters, the final
return value of of :func:`wcwidth.wcswidth` is -1.

Width of 0
----------

Any characters with the `Default_Ignorable_Code_Point`_ property in
`DerivedCoreProperties.txt`_ files, 4,174 characters, excluding `U+00AD`_ SOFT HYPHEN
(width 1) and `U+115F`_ HANGUL CHOSEONG FILLER (width 2).

Any characters defined by `General Category`_ codes in `DerivedGeneralCategory.txt`_ files:

- 'Me': `Enclosing Mark`_, aprox. 13 characters.
- 'Mn': `Nonspacing Mark`_, aprox. 1,839 characters.
- 'Cf': `Format`_ control characters excluding `U+00AD`_ SOFT HYPHEN and
  `Prepended_Concatenation_Mark`_ characters, aprox. 147 characters.
- 'Zl': `U+2028`_ LINE SEPARATOR only
- 'Zp': `U+2029`_ PARAGRAPH SEPARATOR only
- 'Sk': `Modifier Symbol`_, aprox. 1 character with ``'FULLWIDTH'`` in comment
  of `UnicodeData.txt`_ (see `Width of 2`_). `Emoji Modifier`_ Fitzpatrick
  symbols (`U+1F3FB`_ through `U+1F3FF`_) are zero-width only when following
  an emoji base character in sequence; see `Width of 2`_ for standalone.

The NULL character (`U+0000`_).

Any character following ZWJ (`U+200D`_) when preceded by an emoji
(`Extended_Pictographic`_ property) or `Regional Indicator`_ in sequence by
function :func:`wcwidth.wcswidth`. When ZWJ follows a non-emoji character
(including CJK), only the ZWJ itself is zero-width; the following character
is measured normally.

The second `Regional Indicator`_ symbol (`U+1F1E6`_ through `U+1F1FF`_) in a
consecutive pair, when measured in sequence by :func:`wcwidth.wcswidth` or
:func:`wcwidth.width`. The first indicator of the pair is `Width of 2`_.

`Hangul Jamo`_ Jungseong and "Extended-B" code blocks, `U+1160`_ through
`U+11FF`_ and `U+D7B0`_ through `U+D7FF`_.

Any characters of category ``Mc`` (`Spacing Combining Mark`_), aprox. 443
characters, for the single-character function :func:`wcwidth.wcwidth`.
When measured in sequence by :func:`wcwidth.wcswidth`, see `Width of 2`_.

Width of 1
----------

String characters are measured width of 1 when they are not
measured as `Width of 0`_ or `Width of 2`_.

Width of 2
----------

Any character defined by `East Asian`_ Fullwidth (``F``) or Wide (``W``)
properties in `EastAsianWidth.txt`_ files, except those that are defined by the
Category code of `Nonspacing Mark`_ (``Mn``).

`Regional Indicator`_ symbols (`U+1F1E6`_ through `U+1F1FF`_). Though
classified as Neutral in `EastAsianWidth.txt`_, terminals universally render
these as double-width. A consecutive pair of Regional Indicators forms a flag
emoji and is measured as width 2 total (first indicator is 2, second is 0).

`Emoji Modifier`_ Fitzpatrick symbols (`U+1F3FB`_ through `U+1F3FF`_) when
measured standalone (not following an emoji base character). When following
an emoji base, they combine with the base and add 0 to total width.

Any characters of `Modifier Symbol`_ category, ``'Sk'`` where ``'FULLWIDTH'`` is
present in comment of `UnicodeData.txt`_, aprox. 3 characters.

Any character in sequence with `U+FE0F`_ (Variation Selector 16) defined by
`emoji-variation-sequences.txt`_ as ``emoji style``.

Any character of non-zero width followed by an ``Mc`` (`Spacing Combining Mark`_)
character when measured in sequence by :func:`wcwidth.wcswidth` or
:func:`wcwidth.width`. The ``Mc`` character adds +1 to the total width,
reflecting its *positive advance width* as defined in `General Category`_
(Table 4-4). Zero-width combining marks (``Mn``) between the base character
and the ``Mc`` do not break the association — for example, a consonant followed
by a Nukta (``Mn``) and then a vowel sign (``Mc``) is measured as base + 1.

Virama Conjunct Formation
-------------------------

In `Brahmic scripts`_, a `Virama`_ (``Indic_Syllabic_Category=Virama`` in
`IndicSyllabicCategory.txt`_) between two consonants triggers `conjunct`_
formation: the font engine merges the consonants into a single ligature glyph.

- A ``Consonant`` immediately following a ``Virama`` contributes 0 width.
- The conjunct still occupies cells — the next visible advance settles it:

  - A following ``Mc`` (`Spacing Combining Mark`_, e.g. a vowel sign) counts as
    1 cell and closes the conjunct — no extra cell is added.
  - A following character with positive width (or end of string) adds 1 cell
    for the conjunct before counting its own width.

- Chains work the same way: C + virama + C + virama + C collapses each
  virama+consonant pair.
- ``Mn`` marks do not break conjunct context within the same `aksara`_.
- ZWJ (`U+200D`_) after a virama is consumed without breaking conjunct state,
  supporting explicit half-form requests (virama + ZWJ + consonant).

See also: `L2/2023/23107`_ "Proper Complex Script Support in Text Terminals".

.. _`U+0000`: https://codepoints.net/U+0000
.. _`U+0001`: https://codepoints.net/U+0001
.. _`U+001F`: https://codepoints.net/U+001F
.. _`U+007F`: https://codepoints.net/U+007F
.. _`U+00A0`: https://codepoints.net/U+00A0
.. _`U+00AD`: https://codepoints.net/U+00AD
.. _`U+1160`: https://codepoints.net/U+1160
.. _`U+11FF`: https://codepoints.net/U+11FF
.. _`U+200D`: https://codepoints.net/U+200D
.. _`U+2028`: https://codepoints.net/U+2028
.. _`U+2029`: https://codepoints.net/U+2029
.. _`U+D7B0`: https://codepoints.net/U+D7B0
.. _`U+FE0F`: https://codepoints.net/U+FE0F
.. _`U+115F`: https://codepoints.net/U+115F
.. _`DerivedGeneralCategory.txt`: https://www.unicode.org/Public/UCD/latest/ucd/extracted/DerivedGeneralCategory.txt
.. _`DerivedCoreProperties.txt`: https://www.unicode.org/Public/UCD/latest/ucd/DerivedCoreProperties.txt
.. _`EastAsianWidth.txt`: https://www.unicode.org/Public/UCD/latest/ucd/EastAsianWidth.txt
.. _`emoji-variation-sequences.txt`: https://www.unicode.org/Public/UCD/latest/ucd/emoji/emoji-variation-sequences.txt
.. _`Prepended_Concatenation_Mark`: https://www.unicode.org/reports/tr44/#Prepended_Concatenation_Mark
.. _`Default_Ignorable_Code_Point`: https://www.unicode.org/reports/tr44/#Default_Ignorable_Code_Point
.. _`General Category`: https://www.unicode.org/reports/tr44/#General_Category
.. _`Spacing Combining Mark`: https://www.unicode.org/versions/latest/core-spec/chapter-4/#G134153
.. _`Enclosing Mark`: https://www.unicode.org/versions/latest/core-spec/chapter-4/#G134153
.. _`Format`: https://www.unicode.org/versions/latest/core-spec/chapter-4/#G134153
.. _`Modifier Symbol`: https://www.unicode.org/versions/latest/core-spec/chapter-4/#G134153
.. _`Hangul Jamo`: https://www.unicode.org/charts/PDF/U1100.pdf
.. _`U+D7FF`: https://codepoints.net/U+D7FF
.. _`UnicodeData.txt`: https://www.unicode.org/Public/UCD/latest/ucd/UnicodeData.txt
.. _`East Asian`: https://www.unicode.org/reports/tr11/
.. _`U+1F1E6`: https://codepoints.net/U+1F1E6
.. _`U+1F1FF`: https://codepoints.net/U+1F1FF
.. _`U+1F3FB`: https://codepoints.net/U+1F3FB
.. _`U+1F3FF`: https://codepoints.net/U+1F3FF
.. _`Regional Indicator`: https://www.unicode.org/charts/PDF/U1F100.pdf
.. _`Emoji Modifier`: https://unicode.org/reports/tr51/#Emoji_Modifiers
.. _`Extended_Pictographic`: https://www.unicode.org/reports/tr51/#def_extended_pictographic
.. _`Nonspacing Mark`: https://www.unicode.org/versions/latest/core-spec/chapter-4/#G134153
.. _`IndicSyllabicCategory.txt`: https://www.unicode.org/Public/UCD/latest/ucd/IndicSyllabicCategory.txt
.. _`Indic_Syllabic_Category`: https://www.unicode.org/reports/tr44/#Indic_Syllabic_Category
.. _`Brahmic scripts`: https://en.wikipedia.org/wiki/Brahmic_scripts
.. _`Virama`: https://www.unicode.org/glossary/#virama
.. _`conjunct`: https://www.unicode.org/glossary/#consonant_conjunct
.. _`aksara`: https://www.unicode.org/glossary/#aksara
.. _`L2/2023/23107`: https://www.unicode.org/L2/L2023/23107-terminal-suppt.pdf
.. _`Unicode Standard Annex #29`: https://www.unicode.org/reports/tr29/
