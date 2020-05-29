#!/usr/bin/env python
"""
Setup.py distribution file for wcwidth.

https://github.com/jquast/wcwidth
"""
import codecs
import os
import setuptools

def _get_here(fname):
    return os.path.join(os.path.dirname(__file__), fname)

def _get_version(fname, key='package'):
    import json
    return json.load(open(fname, 'r'))[key]

class _SetupUpdate(setuptools.Command):
    # This is a compatibility, some downstream distributions might
    # still call "setup.py update".
    # 
    # New entry point is tox, 'tox -eupdate'.
    description = "Fetch and update unicode code tables"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import sys, subprocess
        retcode = subprocess.Popen([
            sys.executable,
            _get_here(os.path.join('bin', 'update-tables.py'))]).wait()
        assert retcode == 0, ('non-zero exit code', retcode)

def main():
    """Setup.py entry point."""
    setuptools.setup(
        name='wcwidth',
        version=_get_version(
            _get_here(os.path.join('wcwidth', 'version.json'))),
        description=(
            "Python library that measure the width of unicode "
            "strings rendered to a terminal"),
        long_description=codecs.open(
            _get_here('README.rst'), 'rb', 'utf8').read(),
        author='Jeff Quast',
        author_email='contact@jeffquast.com',
        license='MIT',
        packages=['wcwidth', 'wcwidth.tests'],
        url='https://github.com/jquast/wcwidth',
        package_data={
            'wcwidth': ['*.json'],
            '': ['LICENSE.txt', '*.rst'],
        },
        test_suite='wcwidth.tests',
        zip_safe=True,
        classifiers=[
            'Intended Audience :: Developers',
            'Natural Language :: English',
            'Development Status :: 5 - Production/Stable'
            'Environment :: Console',
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7',
            'Programming Language :: Python :: 3.8',
            'Topic :: Software Development :: Libraries',
            'Topic :: Software Development :: Localization',
            'Topic :: Software Development :: Internationalization',
            'Topic :: Terminals'
            ],
        keywords=[
            'cjk',
            'combining',
            'console',
            'eastasian',
            'emoji'
            'emulator',
            'terminal',
            'unicode',
            'wcswidth',
            'wcwidth',
            'xterm',
        ],
        cmdclass={'update': _SetupUpdate},
    )

if __name__ == '__main__':
    main()
