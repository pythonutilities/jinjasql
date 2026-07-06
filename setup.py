#!/usr/bin/env python
import os
import re

from setuptools import setup

# Read the version from jinjasql/__init__.py, so that it is
# maintained in exactly one place. We can't import jinjasql here,
# because during installation Jinja2 isn't installed as yet.
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, 'jinjasql', '__init__.py')) as f:
    __version__ = re.search(r"__version__\s*=\s*'([^']+)'", f.read()).group(1)

with open(os.path.join(here, 'README.md')) as f:
    long_description = f.read()

sdict = {
    'name': 'jinjasql2',
    'version': __version__,
    'description': 'Generate SQL Queries and Corresponding Bind Parameters using a Jinja2 Template',
    'long_description': long_description,
    'long_description_content_type': 'text/markdown',
    'url': 'https://github.com/pythonutilities/jinjasql',
    'author': 'Sridhar, Thomas Ashish Cherian, Sripathi Krishnan',
    'author_email': 'crsridhar23@gmail.com',
    'maintainer': 'Sridhar, Thomas Ashish Cherian',
    'maintainer_email': 'crsridhar23@gmail.com',
    'keywords': ['Jinja2', 'SQL', 'Python', 'Template'],
    'license': 'MIT',
    'packages': ['jinjasql'],
    'python_requires': '>=3.8',
    'install_requires': ['Jinja2>=3.1.6'],
    'classifiers': [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
}

setup(**sdict)
