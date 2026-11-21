==========
Developing
==========

Install wcwidth in editable mode::

   pip install -e .

Execute all code generation, autoformatters, linters and unit tests using tox::

   tox

Or execute individual tasks, see ``tox -lv`` for all available targets::

   tox -e format,lint,py39,py314

To run tests with detailed coverage reporting showing missing lines::

   tox -epy314 -- --cov-report=term-missing

The C11 library's coverage is measured separately, since coverage.py cannot see compiled
code.  This merges two instrumented runs, the C11 test suite and the Python suite driving
the C extension, and writes ``coverage-c.lcov`` and ``htmlcov-c/index.html``::

   tox -e c_coverage

Code Generation
---------------

Terminal Corrections_ tables are generated from the ``ucs-detect`` git submodule, which is not
distributed in the sdist because of its size.  Fetch it first::

   git submodule update --init ucs-detect

Regenerate python code tables from latest Unicode Specification data files and apply formatting::

   tox -e update,format

The script is located at ``bin/update-tables.py``, requires Python 3.9 or later.  To prepare using
Unicode pre-release version, use ``--draft``, so that the draft data files are fetched::

   tox -e update -- --draft=18.0

Release
-------

Bump for the next version in ``pyproject.toml`` and "stamp" version into python and C11 project
using code generation::

    tox -e update,format

Create a ``git tag`` of the same version on master, then publish a GitHub Release for the tag.
wheels.yml_ builds all wheels using cibuildwheel_ on the tag push, and release.yml_ waits up to 45
minutes for that run, downloads its artifacts, runs the checks below, and uploads them with
`PyPI trusted publishing`_ from the ``pypi`` environment. Create the release right after the tag:
the tip-of-master check runs when the workflow starts, so a merge landing before that fails it.

The checks can also be run locally, and wait for the same run; they exit 0 only when every wheel
``[tool.cibuildwheel]`` expects is present::

   tox -e check_release

A wheels run that fails can be retried with "Re-run failed jobs" while the release waits, and the
successful re-run is picked up without publishing the release again.

Building Documentation
----------------------

This project uses `sphinx`_::

   tox -e sphinx

The output will be in ``docs/_build/html/``, to review::

    open docs/_build/html/index.html

Updating Requirements
---------------------

This project is using `pip-tools`_ to manage requirements. Note that this project requires
dependencies only for code generation and testing, the python wcwidth library published does not
have 3rd party dependencies.

To upgrade requirements for updating unicode tables, run::

   tox -e update_requirements_update

To upgrade testing requirements, run::

   tox -e update_requirements39

To upgrade requirements for building documentation, run::

   tox -e update_requirements_docs

.. _`pip-tools`: https://pip-tools.readthedocs.io/
.. _`sphinx`: https://www.sphinx-doc.org/

.. _Corrections: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections
.. _wheels.yml: https://github.com/jquast/wcwidth/blob/master/.github/workflows/wheels.yml
.. _release.yml: https://github.com/jquast/wcwidth/blob/master/.github/workflows/release.yml
.. _`PyPI trusted publishing`: https://docs.pypi.org/trusted-publishers/
.. _cibuildwheel: https://cibuildwheel.pypa.io/
