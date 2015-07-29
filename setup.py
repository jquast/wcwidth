#!/usr/bin/env python
"""
Setup module for wcwidth.

https://github.com/jquast/wcwidth

You may execute setup.py with special arguments:

- ``develop``: Ensures virtualenv and installs development tools.
- ``update``: Updates unicode reference files of the project to latest.
- ``test``: Executes test runner (tox)
"""

from __future__ import print_function
import os
import setuptools
import setuptools.command.develop
import setuptools.command.test

HERE = os.path.dirname(__file__)

# use chr() for py3.x,
# unichr() for py2.x
try:
    _ = unichr(0)
except NameError as err:
    if err.args[0] == "name 'unichr' is not defined":
        # pylint: disable=C0103,W0622
        #         Invalid constant name "unichr" (col 8)
        #         Redefining built-in 'unichr' (col 8)
        unichr = chr
    else:
        raise


class SetupUpdate(setuptools.Command):

    """ 'setup.py update' fetches and updates local unicode code tables. """

    # pylint: disable=R0904
    #         Too many public methods (43/20)
    description = "Fetch and update unicode code tables"
    user_options = []

    EAW_URL = 'http://www.unicode.org/Public/UNIDATA/EastAsianWidth.txt'
    EAW_IN = os.path.join(HERE, 'data', 'EastAsianWidth.txt')
    EAW_OUT = os.path.join(HERE, 'wcwidth', 'table_wide.py')

    UCD_URL = ('http://www.unicode.org/Public/UNIDATA/extracted/'
               'DerivedCombiningClass.txt')
    UCD_IN = os.path.join(HERE, 'data', 'DerivedCombiningClass.txt')
    CMB_OUT = os.path.join(HERE, 'wcwidth', 'table_comb.py')

    def initialize_options(self):
        """Override builtin method: no options are available."""
        pass

    def finalize_options(self):
        """Override builtin method: no options are available."""
        pass

    def run(self):
        """Execute command: update east-asian and combining tables."""
        assert os.getenv('VIRTUAL_ENV'), 'You should be in a virtualenv'
        self.do_east_asian_width()
        self.do_combining()

    def do_east_asian_width(self):
        """Fetch and update east-asian tables."""
        self._do_retrieve(self.EAW_URL, self.EAW_IN)
        (version, date, values) = self._do_east_asian_width_parse(self.EAW_IN)
        table = self._make_table(values)
        self._do_write(self.EAW_OUT, 'WIDE_EASTASIAN', version, date, table)

    def do_combining(self):
        """Fetch and update combining tables."""
        self._do_retrieve(self.UCD_URL, self.UCD_IN)
        (version, date, values) = self._do_combining_parse(self.UCD_IN)
        table = self._make_table(values)
        self._do_write(self.CMB_OUT, 'NONZERO_COMBINING', version, date, table)

    @staticmethod
    def _make_table(values):
        """Return a tuple of lookup tables for given values."""
        import collections
        table = collections.deque()
        start, end = values[0], values[0]
        for num, value in enumerate(values):
            if num == 0:
                table.append((value, value,))
                continue
            start, end = table.pop()
            if end == value - 1:
                table.append((start, value,))
            else:
                table.append((start, end,))
                table.append((value, value,))
        return tuple(table)

    @staticmethod
    def _do_retrieve(url, fname):
        """Retrieve given url to target filepath fname."""
        try:
            import requests
        except ImportError:
            print("Execute '{} develop' first.".format(__file__))
            exit(1)
        folder = os.path.dirname(fname)
        if not os.path.exists(folder):
            os.makedirs(folder)
            print("{}/ created.".format(folder))
        if not os.path.exists(fname):
            with open(fname, 'wb') as fout:
                req = requests.get(url)
                print("retrieving {}.".format(url))
                fout.write(req.content)
            print("{} saved.".format(fname))
        return fname

    @staticmethod
    def _do_east_asian_width_parse(fname,
                                   east_asian_width_properties=(u'W', u'F',)):
        """Parse unicode east-asian width tables."""
        version, date, values = None, None, []
        print("parsing {} ..".format(fname))
        for line in open(fname, 'rb'):
            uline = line.decode('ascii')
            if version is None:
                version = uline.split(None, 1)[1].rstrip()
                continue
            elif date is None:
                date = uline.split(':', 1)[1].rstrip()
                continue
            if uline.startswith('#') or not uline.lstrip():
                continue
            addrs, details = uline.split(';', 1)
            if any(details.startswith(property)
                   for property in east_asian_width_properties):
                start, stop = addrs, addrs
                if '..' in addrs:
                    start, stop = addrs.split('..')
                values.extend(range(int(start, 16), int(stop, 16) + 1))
        return version, date, sorted(values)

    @staticmethod
    def _do_combining_parse(fname, exclude_values=(0,)):
        """Parse unicode combining tables."""
        version, date, values = None, None, []
        print("parsing {} ..".format(fname))
        for line in open(fname, 'rb'):
            uline = line.decode('ascii')
            if version is None:
                version = uline.split(None, 1)[1].rstrip()
                continue
            elif date is None:
                date = uline.split(':', 1)[1].rstrip()
                continue
            if uline.startswith('#') or not uline.lstrip():
                continue
            addrs, details = uline.split(';', 1)
            addrs, details = addrs.rstrip(), details.lstrip()
            if not any(details.startswith('{} #'.format(value))
                       for value in exclude_values):
                start, stop = addrs, addrs
                if '..' in addrs:
                    start, stop = addrs.split('..')
                values.extend(range(int(start, 16), int(stop, 16) + 1))
        return version, date, sorted(values)

    @staticmethod
    def _do_write(fname, variable, version, date, table):
        """Write combining tables to filesystem as python code."""
        # pylint: disable=R0914
        #         Too many local variables (19/15) (col 4)
        print("writing {} ..".format(fname))
        import unicodedata
        import datetime
        import string
        utc_now = datetime.datetime.utcnow()
        indent = 4
        with open(fname, 'w') as fout:
            fout.write(
                '"""{variable_proper} table. Created by setup.py."""\n'
                "# Generated: {iso_utc}\n"
                "# Source: {version}\n"
                "# Date: {date}\n"
                "{variable} = (".format(iso_utc=utc_now.isoformat(),
                                        version=version,
                                        date=date,
                                        variable=variable,
                                        variable_proper=variable.title()))
            for start, end in table:
                ucs_start, ucs_end = unichr(start), unichr(end)
                hex_start, hex_end = ('0x{0:04x}'.format(start),
                                      '0x{0:04x}'.format(end))
                try:
                    name_start = string.capwords(unicodedata.name(ucs_start))
                except ValueError:
                    name_start = u''
                try:
                    name_end = string.capwords(unicodedata.name(ucs_end))
                except ValueError:
                    name_end = u''
                fout.write('\n' + (' ' * indent))
                fout.write('{0}, {1},'.format(hex_start, hex_end))
                fout.write('  # {0:24s}..{1}'.format(
                    name_start[:24].rstrip() or '(nil)',
                    name_end[:24].rstrip()))
            fout.write('\n)\n')
        print("complete.")


class SetupDevelop(setuptools.command.develop.develop):

    """'setup.py develop' is augmented to install development tools."""

    # pylint: disable=R0904
    #         Too many public methods (43/20)

    def run(self):
        """Execute command pip for development requirements."""
        # pylint: disable=E1101
        # Instance of 'SetupDevelop' has no 'spawn' member (col 8)
        assert os.getenv('VIRTUAL_ENV'), 'You should be in a virtualenv'
        setuptools.command.develop.develop.run(self)
        self.spawn(('pip', 'install', '-U',
                    'blessed', 'requests', 'tox', 'docopt',))


class SetupTest(setuptools.command.test.test):

    """'setup.py test' is an alias to execute tox."""

    def run(self):
        """ Execute command: tox. """
        # pylint: disable=E1101
        # Instance of 'SetupTest' has no 'spawn' member (col 8)
        self.spawn(('tox',))


def main():
    """Setup.py entry point."""
    import codecs
    setuptools.setup(
        name='wcwidth',
        version='0.1.4',
        description=("Measures number of Terminal column cells "
                     "of wide-character codes"),
        long_description=codecs.open(
            os.path.join(HERE, 'README.rst'), 'r', 'utf8').read(),
        author='Jeff Quast',
        author_email='contact@jeffquast.com',
        license='MIT',
        packages=['wcwidth', 'wcwidth.tests'],
        url='https://github.com/jquast/wcwidth',
        include_package_data=True,
        test_suite='wcwidth.tests',
        zip_safe=True,
        classifiers=[
            'Intended Audience :: Developers',
            'Natural Language :: English',
            'Development Status :: 2 - Pre-Alpha',
            'Environment :: Console',
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
            'Topic :: Software Development :: Libraries',
            'Topic :: Software Development :: Localization',
            'Topic :: Software Development :: Internationalization',
            'Topic :: Terminals'
            ],
        keywords=['terminal', 'emulator', 'wcwidth', 'wcswidth', 'cjk',
                  'combining', 'xterm', 'console', ],
        cmdclass={'develop': SetupDevelop,
                  'update': SetupUpdate,
                  'test': SetupTest},
    )

if __name__ == '__main__':
    main()
