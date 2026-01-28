.. _Specification:

=============
Specification
=============

This document defines how the wcwidth library measures the printable width
of characters of a string.

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

- 'Me': Enclosing Combining Mark, aprox. 13 characters.
- 'Mn': Nonspacing Combining Mark, aprox. 1,839 characters.
- 'Cf': Format control characters excluding `U+00AD`_ SOFT HYPHEN and
  `Prepended_Concatenation_Mark`_ characters, aprox. 147 characters.
- 'Zl': `U+2028`_ LINE SEPARATOR only
- 'Zp': `U+2029`_ PARAGRAPH SEPARATOR only
- 'Sk': Modifier Symbol, aprox. 4 characters of only those where phrase
  ``'EMOJI MODIFIER'`` is present in comment of unicode data file.

The NULL character (`U+0000`_).

Any character following ZWJ (`U+200D`_) when in sequence by
function :func:`wcwidth.wcswidth`.

Hangul Jamo Jungseong and "Extended-B" code blocks, `U+1160`_ through
`U+11FF`_ and `U+D7B0`_ through U+D7FF.


Width of 1
----------

String characters are measured width of 1 when they are not
measured as `Width of 0`_ or `Width of 2`_.

This includes characters of category ``Mc`` (`Spacing Combining Mark`_), aprox. 443
characters, which have positive advance width per the `Unicode specification`_.

Width of 2
----------

Any character defined by `East Asian`_ Fullwidth (``F``) or Wide (``W``)
properties in `EastAsianWidth.txt`_ files, except those that are defined by the
Category code of `Nonspacing Mark`_ (``Mn``).

Any characters of Modifier Symbol category, ``'Sk'`` where ``'FULLWIDTH'`` is
present in comment of unicode data file, aprox. 3 characters.

Any character in sequence with `U+FE0F`_ (Variation Selector 16) defined by
`emoji-variation-sequences.txt`_ as ``emoji style``.


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
.. _`Spacing Combining Mark`: https://www.unicode.org/versions/latest/ch04.pdf#G134153
.. _`Unicode specification`: https://www.unicode.org/versions/latest/
.. _`East Asian`: https://www.unicode.org/reports/tr11/
.. _`Nonspacing Mark`: https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-5/#G1095
