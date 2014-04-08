#!/usr/bin/env python
from setuptools import setup
import os

here = os.path.dirname(__file__)

setup(
    name='wcwidth',
    version='0.0.1',
    description="A python-pure interface to wcwidth() and wcswidth()",
    long_description=open(os.path.join(here, 'README.rst')).read(),
    author='Jeff Quast',
    author_email='contact@jeffquast.com',
    license='MIT',
    packages=['wcwidth', ],
    url='https://github.com/jquast/wcwidth',
    include_package_data=True,
    # test_suite='tests',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Internationalization',
        'Topic :: Software Development :: Localization',
        'Topic :: Terminals',
        'Topic :: Text Processing :: General',
        ],
    keywords=['terminal', 'emulator', 'wcwidth', 'wcswidth', 'cjk',
              'combining', 'ambiguous', 'xterm', 'console', 'keyboard', ],
)
