#!/usr/bin/env python
"""
Setup module for wcwidth.

https://github.com/jquast/wcwidth
"""
# TODO: backward-compatible 'python setup.py update'?
#
import os
import setuptools

def _get_here(fname):
    return os.path.join(os.path.dirname(__file__), fname)


def _get_version(fname, key='package'):
    import json
    return json.load(open(fname, 'r'))[key]


def main():
    """Setup.py entry point."""
    import codecs
    setuptools.setup(
        name='wcwidth',
        version=_get_version(fname=_get_here(os.path.join('wcwidth', 'version.json'))),
        description=("Measures number of Terminal column cells "
                     "of wide-character codes"),
        long_description=codecs.open(_get_here('README.rst'), 'rb', 'utf8').read(),
        author='Jeff Quast',
        author_email='contact@jeffquast.com',
        license='MIT',
        packages=['wcwidth', 'wcwidth.tests'],
        url='https://github.com/jquast/wcwidth',
        #include_package_data=True,
        package_data={
            'wcwidth': ['*.json'],
            '': ['LICENSE.txt', '*.rst'],
        },
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
        # TODO
        # cmdclass={'update': SetupUpdate},
    )

if __name__ == '__main__':
    main()
