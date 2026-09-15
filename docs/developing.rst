==========
Developing
==========

Install wcwidth in editable mode::

   pip install -e .

Execute all code generation, autoformatters, linters and unit tests using tox::

   tox

Or execute individual tasks, see ``tox -lv`` for all available targets::

   tox -e pylint,py36,py314

To run tests with detailed coverage reporting showing missing lines::

   tox -epy314 -- --cov-report=term-missing

Updating Unicode Version
------------------------

Regenerate python code tables from latest Unicode Specification data files::

   tox -e update

The script is located at ``bin/update-tables.py``, requires Python 3.9 or later.

Building Documentation
----------------------

This project is using `sphinx`_ 4.5 to build documentation::

   tox -e sphinx

The output will be in ``docs/_build/html/``.

Updating Requirements
---------------------

This project is using `pip-tools`_ to manage requirements.

To upgrade requirements for updating unicode version, run::

   tox -e update_requirements_update

To upgrade requirements for testing, run::

   tox -e update_requirements38,update_requirements39

To upgrade requirements for building documentation, run::

   tox -e update_requirements_docs

.. _`pip-tools`: https://pip-tools.readthedocs.io/
.. _`sphinx`: https://www.sphinx-doc.org/
