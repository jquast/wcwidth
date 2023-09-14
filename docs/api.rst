==========
Public API
==========

This package follows SEMVER_ rules for version, therefore, for all of the
given functions signatures, at example version 1.1.1, you may use version
dependency ``>=1.1.1,<2.0`` for forward compatibility of future wcwidth
versions.

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
time in the future, and not reflected by SEMVER rules.

If stable public API for any of the given functions is needed, please suggest a
Pull Request!

.. autofunction:: wcwidth._bisearch

.. autofunction:: wcwidth._wcversion_value

.. autofunction:: wcwidth._wcmatch_version
