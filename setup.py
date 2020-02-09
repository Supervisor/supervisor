##############################################################################
#
# Copyright (c) 2006-2015 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the BSD-like license at
# http://www.repoze.org/LICENSE.txt.  A copy of the license should accompany
# this distribution.  THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL
# EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND
# FITNESS FOR A PARTICULAR PURPOSE
#
##############################################################################

import os
import sys

py_version = sys.version_info[:2]

if py_version < (2, 7):
    raise RuntimeError('On Python 2, Supervisor requires Python 2.7 or later')
elif (3, 0) < py_version < (3, 4):
    raise RuntimeError('On Python 3, Supervisor requires Python 3.4 or later')

requires = []
tests_require = []
if py_version < (3, 3):
    tests_require.append('mock<4.0.0.dev0')

testing_extras = tests_require + [
    'pytest',
    'pytest-cov',
    ]

from setuptools import setup, find_packages
here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.rst')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()
except:
    README = """\
Supervisor is a client/server system that allows its users to
control a number of processes on UNIX-like operating systems. """
    CHANGES = ''

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: No Input/Output (Daemon)',
    'Intended Audience :: System Administrators',
    'Natural Language :: English',
    'Operating System :: POSIX',
    'Topic :: System :: Boot',
    'Topic :: System :: Monitoring',
    'Topic :: System :: Systems Administration',
    "Programming Language :: Python",
    "Programming Language :: Python :: 2",
    "Programming Language :: Python :: 2.7",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.4",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
]

version_txt = os.path.join(here, 'supervisor/version.txt')
supervisor_version = open(version_txt).read().strip()

dist = setup(
    name='supervisor',
    version=supervisor_version,
    license='BSD-derived (http://www.repoze.org/LICENSE.txt)',
    url='http://supervisord.org/',
    description="A system for controlling process state under UNIX",
    long_description=README + '\n\n' + CHANGES,
    classifiers=CLASSIFIERS,
    author="Chris McDonough",
    author_email="chrism@plope.com",
    packages=find_packages(),
    install_requires=requires,
    extras_require={
        'testing': testing_extras,
        },
    tests_require=tests_require,
    include_package_data=True,
    zip_safe=False,
    test_suite="supervisor.tests",
    entry_points={
        'console_scripts': [
            'supervisord = supervisor.supervisord:main',
            'supervisorctl = supervisor.supervisorctl:main',
            'echo_supervisord_conf = supervisor.confecho:main',
            'pidproxy = supervisor.pidproxy:main',
        ],
    },
)
