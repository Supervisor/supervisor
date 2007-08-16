##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

__revision__ = '$Id$'

from ez_setup import use_setuptools
use_setuptools()

import os
import sys
import string

version, extra = string.split(sys.version, ' ', 1)
maj, minor = string.split(version, '.', 1)

if not maj[0] >= '2' and minor[0] >= '3':
    msg = ("supervisor requires Python 2.3 or better, you are attempting to "
           "install it using version %s.  Please install with a "
           "supported version" % version)

from setuptools import setup, find_packages
here = os.path.abspath(os.path.normpath(os.path.dirname(__file__)))

DESC = """\
Supervisor is a client/server system that allows its users to
control a number of processes on UNIX-like operating systems. """

CLASSIFIERS = [
    'Development Status :: 5 - Production/Stable',
    'Environment :: No Input/Output (Daemon)',
    'Intended Audience :: System Administrators',
    'License :: OSI Approved :: Zope Public License',
    'Natural Language :: English',
    'Operating System :: POSIX',
    'Topic :: System :: Boot',
    'Topic :: System :: Systems Administration',
    ]

version_txt = os.path.join(here, 'src/supervisor/version.txt')
supervisor_version = open(version_txt).read().strip()

dist = setup(
    name = 'supervisor',
    version = supervisor_version,
    license = 'ZPL 2.1/others (see LICENSES.txt)',
    url = 'http://www.plope.com/software/supervisor2/',
    description = "A system for controlling process state under UNIX",
    long_description= DESC,
    classifiers = CLASSIFIERS,
    author = "Chris McDonough",
    author_email = "chrism@plope.com",
    maintainer = "Chris McDonough",
    maintainer_email = "chrism@plope.com",
    package_dir = {'':'src'},
    packages = find_packages(os.path.join(here, 'src')),
    scripts=['src/supervisor/supervisord', 'src/supervisor/supervisorctl'],
    install_requires = ['medusa >= 0.5.4', 'meld3 >= 0.6',
                        'elementtree >= 1.2.6'],
    include_package_data = True,
    zip_safe = False,
    namespace_packages = ['supervisor'],
    test_suite = "supervisor.tests",
    )
