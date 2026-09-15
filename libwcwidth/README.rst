==========
libwcwidth
==========

A portable C11 library for measuring the displayed width of Unicode strings in a terminal,
derived from the Python wcwidth_ project.

**This library is a release candidate.**  It rides along in the wcwidth git tags so that it can
be used and reported on, but its API is not yet frozen: function signatures, header layout, and
the contents of ``wcwidth_config.h`` may change before 1.0.

Building
--------

With ``make``, which also builds the examples::

    make
    make test

Or with CMake::

    cmake -B build-cmake .
    cmake --build build-cmake
    ctest --test-dir build-cmake

Both produce a static ``libwcwidth.a``; the headers are in ``include/wcwidth/``.

Documentation
-------------

The full API reference and usage guide are published with the Python project:

- https://wcwidth.readthedocs.io/en/latest/libwcwidth.html
- https://wcwidth.readthedocs.io/en/latest/api_c.html

License
-------

MIT, see the LICENSE file in this directory.

.. _wcwidth: https://github.com/jquast/wcwidth
