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

if sys.version_info[:2] < (2, 4) or sys.version_info[0] > 2:
    msg = ("Supervisor requires Python 2.4 or later but does not work on "
           "any version of Python 3.  You are using version %s.  Please "
           "install using a supported version." % sys.version)
    sys.stderr.write(msg)
    sys.exit(1)

if sys.version_info[:2] < (2, 5):
    # meld3 1.0.0 dropped python 2.4 support
    # meld3 requires elementree on python 2.4 only
    requires = ['meld3 >= 0.6.5 , < 1.0.0', 'elementtree']
else:
    requires = ['meld3 >= 0.6.5']

from setuptools import setup, find_packages
here = os.path.abspath(os.path.dirname(__file__))
try:
    README = open(os.path.join(here, 'README.rst')).read()
    CHANGES = open(os.path.join(here, 'CHANGES.txt')).read()
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
    "Programming Language :: Python :: 2.4",
    "Programming Language :: Python :: 2.5",
    "Programming Language :: Python :: 2.6",
    "Programming Language :: Python :: 2.7",
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
    extras_require={'iterparse': ['cElementTree >= 1.0.2']},
    tests_require=['mock >= 0.5.0'],
    include_package_data=True,
    zip_safe=False,
    namespace_packages=['supervisor'],
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
