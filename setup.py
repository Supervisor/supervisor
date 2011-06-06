##############################################################################
#
# Copyright (c) 2006-2011 Agendaless Consulting and Contributors.
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

if sys.version_info[:2] < (2, 3) or sys.version_info[0] > 2:
    msg = ("Supervisor requires Python 2.3 or later but does not work on "
           "any version of Python 3.  You are using version %s.  Please "
           "install using a supported version." % sys.version)
    sys.stderr.write(msg)
    sys.exit(1)

import urllib
import urllib2
if not hasattr(urllib2, 'splituser'):
    # setuptools wants to import this from urllib2 but it's not
    # in there in Python 2.3.3, so we just alias it.
    urllib2.splituser = urllib.splituser

requires = ['setuptools', 'meld3 >= 0.6.5']

if sys.version_info[:2] < (2, 5):
    # for meld3 (it's a distutils package)
    requires.append('elementtree')

from setuptools import setup, find_packages
here = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))

try:
    here = os.path.abspath(os.path.dirname(__file__))
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
    ]

version_txt = os.path.join(here, 'supervisor/version.txt')
supervisor_version = open(version_txt).read().strip()

dist = setup(
    name = 'supervisor',
    version = supervisor_version,
    license = 'BSD-derived (http://www.repoze.org/LICENSE.txt)',
    url = 'http://supervisord.org/',
    description = "A system for controlling process state under UNIX",
    long_description=README + '\n\n' +  CHANGES,
    classifiers = CLASSIFIERS,
    author = "Chris McDonough",
    author_email = "chrism@plope.com",
    maintainer = "Mike Naberezny",
    maintainer_email = "mike@naberezny.com",
    packages = find_packages(),
    install_requires = requires,
    extras_require = {'iterparse':['cElementTree >= 1.0.2']},
    tests_require = requires + ['mock >= 0.5.0'],
    include_package_data = True,
    zip_safe = False,
    namespace_packages = ['supervisor'],
    test_suite = "supervisor.tests",
    entry_points = {
     'supervisor_rpc':['main = supervisor.rpcinterface:make_main_rpcinterface'],
     'console_scripts': [
         'supervisord = supervisor.supervisord:main',
         'supervisorctl = supervisor.supervisorctl:main',
         'echo_supervisord_conf = supervisor.confecho:main',
         'pidproxy = supervisor.pidproxy:main',
         ],
      },
    )
