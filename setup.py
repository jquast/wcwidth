#!/usr/bin/env python
from __future__ import print_function
import os
import setuptools
import setuptools.command.develop
import setuptools.command.test

here = os.path.dirname(__file__)

# use chr() for py3.x,
# unichr() for py2.x
try:
    _ = unichr(0)
except NameError as err:
    if err.args[0] == "name 'unichr' is not defined":
        unichr = chr
    else:
        raise


class SetupUpdate(setuptools.Command):
    description = "Fetch and update unicode code tables"
    user_options = []

    EAW_URL = 'http://www.unicode.org/Public/UNIDATA/EastAsianWidth.txt'
    EAW_IN = os.path.join(here, 'data', 'EastAsianWidth.txt')
    EAW_OUT = os.path.join(here, 'wcwidth', 'table_wide.py')

    UCD_URL = ('http://www.unicode.org/Public/UNIDATA/extracted/'
               'DerivedCombiningClass.txt')
    UCD_IN = os.path.join(here, 'data', 'DerivedCombiningClass.txt')
    CMB_OUT = os.path.join(here, 'wcwidth', 'table_comb.py')

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        assert os.getenv('VIRTUAL_ENV'), 'You should be in a virtualenv'
        self.do_east_asian_width()
        self.do_combining()

    def do_east_asian_width(self):
        self._do_retrieve(self.EAW_URL, self.EAW_IN)
        (version, date, values) = self._do_east_asian_width_parse(self.EAW_IN)
        table = self._make_table(values)
        self._do_write(self.EAW_OUT, 'WIDE_EASTASIAN', version, date, table)

    def do_combining(self):
        self._do_retrieve(self.UCD_URL, self.UCD_IN)
        (version, date, values) = self._do_combining_parse(self.UCD_IN)
        table = self._make_table(values)
        self._do_write(self.CMB_OUT, 'NONZERO_COMBINING', version, date, table)

    @staticmethod
    def _make_table(values):
        import collections
        table = collections.deque()
        start, end = values[0], values[0]
        for n, value in enumerate(values):
            if n == 0:
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
        try:
            import requests
        except ImportError:
            print("Execute '{} develop' first.")
            exit(1)
        if not os.path.exists(os.path.dirname(fname)):
            print("{}/ created.")
            os.makedirs(os.path.dirname(fname))
        if not os.path.exists(fname):
            with open(fname, 'wb') as fp:
                req = requests.get(url)
                print("retrieving {}.".format(url))
                fp.write(req.content)
            print("{} saved.".format(fname))
        return fname

    @staticmethod
    def _do_east_asian_width_parse(fname,
                                   East_Asian_Width_properties=(u'W', u'F',)):
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
                   for property in East_Asian_Width_properties):
                start, stop = addrs, addrs
                if '..' in addrs:
                    start, stop = addrs.split('..')
                values.extend(range(int(start, 16), int(stop, 16) + 1))
        return version, date, sorted(values)

    @staticmethod
    def _do_combining_parse(fname, exclude_values=(0,)):
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
        print("writing {} ..".format(fname))
        import unicodedata
        import datetime
        import string
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        INDENT = 4
        with open(fname, 'w') as fp:
            fp.write("# Generated: {iso_utc}\n"
                     "# Source: {version}\n"
                     "# Date: {date}\n"
                     "{variable} = (".format(iso_utc=utc_now.isoformat(),
                                             version=version,
                                             date=date,
                                             variable=variable))
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
                fp.write('\n' + (' ' * INDENT))
                fp.write('({0}, {1},),'.format(hex_start, hex_end))
                fp.write('  # {0:24s}..{1}'.format(
                    name_start[:24].rstrip() or '(nil)',
                    name_end[:24].rstrip()))
            fp.write('\n)\n')
        print("complete.")


class SetupDevelop(setuptools.command.develop.develop):
    def run(self):
        assert os.getenv('VIRTUAL_ENV'), 'You should be in a virtualenv'
        setuptools.command.develop.develop.run(self)
        self.spawn(('pip', 'install', '-U', 'blessed', 'requests',))


class SetupTest(setuptools.command.test.test):
    def run(self):
        self.spawn(('tox',))


def main():
    setuptools.setup(
        name='wcwidth',
        version='0.1.0',
        description=("Measures number of Terminal column cells "
                     "of wide-character codes"),
        long_description=open(os.path.join(here, 'README.rst')).read(),
        author='Jeff Quast',
        author_email='contact@jeffquast.com',
        license='MIT',
        packages=['wcwidth', 'wcwidth.tests'],
        url='https://github.com/jquast/wcwidth',
        include_package_data=True,
        test_suite='wcwidth.tests',
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
