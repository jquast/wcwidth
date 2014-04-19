#!/usr/bin/env python
from setuptools import setup
import os

here = os.path.dirname(__file__)

setup(
    name='wcwidth',
    version='0.0.1',
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
        'Topic :: Text Processing :: General',
        ],
    keywords=['terminal', 'emulator', 'wcwidth', 'wcswidth', 'cjk',
              'combining', 'ambiguous', 'xterm', 'console', ]
)
