==========
Developing
==========

Install wcwidth in editable mode::

   pip install -e .

Execute all code generation, autoformatters, linters and unit tests using tox::

   tox

Or execute individual tasks, see ``tox -lv`` for all available targets::

   tox -e pylint,py39,py314

To run tests with detailed coverage reporting showing missing lines::

   tox -epy314 -- --cov-report=term-missing

Updating Unicode Version
------------------------

Regenerate python code tables from latest Unicode Specification data files::

   tox -e update

The script is located at ``bin/update-tables.py``, requires Python 3.9 or later.  While a
Unicode version is still pre-release, pass its version to ``--draft``, so that the draft
data files are fetched::

   tox -e update -- --draft=18.0

The terminal Corrections_ tables are generated from the ``ucs-detect`` git submodule, which
is not distributed in the sdist because of its size.  Fetch it first::

   git submodule update --init ucs-detect

Building Documentation
----------------------

This project uses `sphinx`_::

   tox -e sphinx

The output will be in ``docs/_build/html/``, to review::

    open docs/_build/html/index.html

Updating Requirements
---------------------

This project is using `pip-tools`_ to manage requirements.

To upgrade requirements for updating unicode tables, run::

   tox -e update_requirements_update

To upgrade requirements for testing, run::

   tox -e update_requirements38,update_requirements39

To upgrade requirements for building documentation, run::

   tox -e update_requirements_docs

.. _`pip-tools`: https://pip-tools.readthedocs.io/
.. _`sphinx`: https://www.sphinx-doc.org/

.. _Corrections: https://wcwidth.readthedocs.io/en/latest/intro.html#corrections

