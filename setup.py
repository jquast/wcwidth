#!/usr/bin/env python
"""
Setup module for wcwidth.

https://github.com/jquast/wcwidth

You may execute setup.py with special arguments:

- ``update``: Updates unicode reference files of the project to latest.
- ``test``: Executes test runner (tox)
"""

from __future__ import print_function
import os
import setuptools
import setuptools.command.test
try:
    # py2
    from urllib2 import urlopen
except ImportError:
    # py3
    from urllib.request import urlopen

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

    EAW_URL = ('http://www.unicode.org/Public/UNIDATA/'
               'EastAsianWidth.txt')
    UCD_URL = ('http://www.unicode.org/Public/UNIDATA/extracted/'
               'DerivedGeneralCategory.txt')

    EAW_IN = os.path.join(HERE, 'data', 'EastAsianWidth.txt')
    UCD_IN = os.path.join(HERE, 'data', 'DerivedGeneralCategory.txt')

    EAW_OUT = os.path.join(HERE, 'wcwidth', 'table_wide.py')
    ZERO_OUT = os.path.join(HERE, 'wcwidth', 'table_zero.py')

    README_RST = os.path.join(HERE, 'README.RST')
    README_PATCH_FROM = "the Unicode Standard release files:"
    README_PATCH_TO = "Installation"

    def initialize_options(self):
        """Override builtin method: no options are available."""
        pass

    def finalize_options(self):
        """Override builtin method: no options are available."""
        pass

    def run(self):
        """Update east-asian, combining and zero width tables."""
        self._do_east_asian()
        self._do_zero_width()
        self._do_readme_update()

    def _do_readme_update(self):
        """Patch README.rst to reflect the data files used in release."""
        import codecs
        import glob

        # read in,
        data_in = codecs.open(
            os.path.join(HERE, 'README.rst'), 'r', 'utf8').read()

        # search for beginning and end positions,
        pos_begin = data_in.find(self.README_PATCH_FROM)
        assert pos_begin != -1, (pos_begin, self.README_PATCH_FROM)
        pos_begin += len(self.README_PATCH_FROM)

        pos_end = data_in.find(self.README_PATCH_TO)
        assert pos_end != -1, (pos_end, self.README_PATCH_TO)

        glob_pattern = os.path.join(HERE, 'data', '*.txt')
        file_descriptions = [
            self._describe_file_header(fpath)
            for fpath in glob.glob(glob_pattern)]

        # patch,
        data_out = (
            data_in[:pos_begin] +
            '\n\n' +
            '\n'.join(file_descriptions) +
            '\n\n' +
            data_in[pos_end:]
        )

        # write.
        print("patching {} ..".format(self.README_RST))
        codecs.open(
            self.README_RST, 'w', 'utf8').write(data_out)

    def _do_east_asian(self):
        """Fetch and update east-asian tables."""
        self._do_retrieve(self.EAW_URL, self.EAW_IN)
        (version, date, values) = self._parse_east_asian(
            fname=self.EAW_IN,
            properties=(u'W', u'F',)
        )
        table = self._make_table(values)
        self._do_write(self.EAW_OUT, 'WIDE_EASTASIAN', version, date, table)

    def _do_zero_width(self):
        """Fetch and update zero width tables."""
        self._do_retrieve(self.UCD_URL, self.UCD_IN)
        (version, date, values) = self._parse_category(
            fname=self.UCD_IN,
            categories=('Me', 'Mn',)
        )
        table = self._make_table(values)
        self._do_write(self.ZERO_OUT, 'ZERO_WIDTH', version, date, table)

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
        folder = os.path.dirname(fname)
        if not os.path.exists(folder):
            os.makedirs(folder)
            print("{}/ created.".format(folder))
        if not os.path.exists(fname):
            with open(fname, 'wb') as fout:
                print("retrieving {}.".format(url))
                resp = urlopen(url)
                fout.write(resp.read())
            print("{} saved.".format(fname))
        else:
            print("re-using artifact {}".format(fname))
        return fname

    @staticmethod
    def _describe_file_header(fpath):
        import codecs
        header_3 = [line.lstrip('# ').rstrip() for line in
                    codecs.open(fpath, 'r', 'utf8').readlines()[:3]]
        return ('``{0}``\n'   # ``EastAsianWidth-8.0.0.txt``
                '  *{1}*\n'   #   *2015-02-10, 21:00:00 GMT [KW, LI]*
                '  {2}\n'       #   (c) 2016 Unicode(R), Inc.
                .format(*header_3))

    @staticmethod
    def _parse_east_asian(fname, properties=(u'W', u'F',)):
        """Parse unicode east-asian width tables."""
        version, date, values = None, None, []
        print("parsing {} ..".format(fname))
        for line in open(fname, 'rb'):
            uline = line.decode('utf-8')
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
                   for property in properties):
                start, stop = addrs, addrs
                if '..' in addrs:
                    start, stop = addrs.split('..')
                values.extend(range(int(start, 16), int(stop, 16) + 1))
        return version, date, sorted(values)

    @staticmethod
    def _parse_category(fname, categories):
        """Parse unicode category tables."""
        version, date, values = None, None, []
        print("parsing {} ..".format(fname))
        for line in open(fname, 'rb'):
            uline = line.decode('utf-8')
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
            if any(details.startswith('{} #'.format(value))
                   for value in categories):
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
                fout.write('({0}, {1},),'.format(hex_start, hex_end))
                fout.write('  # {0:24s}..{1}'.format(
                    name_start[:24].rstrip() or '(nil)',
                    name_end[:24].rstrip()))
            fout.write('\n)\n')
        print("complete.")


def main():
    """Setup.py entry point."""
    import codecs
    setuptools.setup(
        name='wcwidth',
        version='0.1.9',
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
            'Development Status :: 3 - Alpha',
            'Environment :: Console',
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.4',
            'Programming Language :: Python :: 3.5',
            'Topic :: Software Development :: Libraries',
            'Topic :: Software Development :: Localization',
            'Topic :: Software Development :: Internationalization',
            'Topic :: Terminals'
            ],
        keywords=['terminal', 'emulator', 'wcwidth', 'wcswidth', 'cjk',
                  'combining', 'xterm', 'console', ],
        cmdclass={'update': SetupUpdate},
    )

if __name__ == '__main__':
    main()
