.. _Specification:

=============
Specification
=============

This document defines how the wcwidth library measures the printable width
of characters of a string.

Width of -1
-----------

The following have a column width of -1 for function :func:`wcwidth.wcwidth`

- C0 control characters (U+001 through U+01F).
- C1 control characters and DEL (U+07F through U+0A0).

If any character in sequence contains C0 or C1 control characters, the final
return value of of :func:`wcwidth.wcswidth` is -1.

Width of 0
----------

Any characters defined by category codes in DerivedGeneralCategory txt files:

- 'Me': Enclosing Combining Mark, aprox. 13 characters.
- 'Mn': Nonspacing Combining Mark, aprox. 1,839 characters.
- 'Mc': Spacing Mark, aprox. 443 characters.
- 'Cf': Format control character, aprox. 161 characters.
- 'Zl': U+2028 LINE SEPARATOR only
- 'Zp': U+2029 PARAGRAPH SEPARATOR only
- 'Sk': Modifier Symbol, aprox. 4 characters of only those where phrase
  ``'EMOJI MODIFIER'`` is present in comment of unicode data file.

The NULL character (``U+0000``).

Any character following a ZWJ (``U+200D``) when in sequence by
function :func:`wcwidth.wcswidth`.

Width of 1
----------

String characters are measured width of 1 when they are not
measured as `Width of 0`_ or `Width of 2`.

Width of 2
----------

Any character defined by East Asian Fullwidth (``F``) or Wide (``W``)
properties in EastAsianWidth txt files, except those that are defined by the
Category codes of Nonspacing Mark (``Mn``) and Spacing Mark (``Mc``).

Any characters of Modifier Symbol category, ``'Sk'`` where ``'FULLWIDTH'`` is
present in comment of unicode data file, aprox. 3 characters.

Any character in sequence with U+FE0F (Variation Selector 16) defined by
Emoji Variation Sequences txt as ``emoji style``.

