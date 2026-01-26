==========
Public API
==========

This package follows SEMVER_ rules.  Therefore, for the functions of the below
list, you may safely use version dependency definition ``wcwidth<1`` in your
requirements.txt or equivalent. Their signatures will never change.

.. autofunction:: wcwidth.wcwidth

.. autofunction:: wcwidth.wcswidth

.. autofunction:: wcwidth.width

.. autofunction:: wcwidth.iter_sequences

.. autofunction:: wcwidth.iter_graphemes

.. autofunction:: wcwidth.iter_graphemes_reverse

.. autofunction:: wcwidth.grapheme_boundary_before

.. autofunction:: wcwidth.ljust

.. autofunction:: wcwidth.rjust

.. autofunction:: wcwidth.center

.. autofunction:: wcwidth.wrap

.. autofunction:: wcwidth.clip

.. autofunction:: wcwidth.strip_sequences

.. autofunction:: wcwidth.propagate_sgr

.. autofunction:: wcwidth.list_versions

.. _SEMVER: https://semver.org
