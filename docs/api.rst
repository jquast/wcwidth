==========
Public API
==========

This package follows SEMVER_ rules.  Therefore, for the functions of the below
list, you may safely use version dependency definition ``wcwidth<2`` in your
requirements.txt or equivalent. Their signatures will never change.

.. autofunction:: wcwidth.wcwidth

.. autofunction:: wcwidth.wcswidth

.. autofunction:: wcwidth.list_versions

.. _SEMVER: https://semver.org

===========
Private API
===========

These functions should only be used for wcwidth development, and not used by
dependent packages except with care and by use of frozen version dependency,
as these functions may change names, signatures, or disappear entirely at any
time in the future, and not reflected by SEMVER_ rules!

If stable public API for any of the given functions is needed, please suggest a
Pull Request!

.. autofunction:: wcwidth._bisearch

.. autofunction:: wcwidth._wcversion_value

.. autofunction:: wcwidth._wcmatch_version
