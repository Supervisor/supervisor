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

import sys
import xmlrpclib
from supervisor.xmlrpc import SupervisorTransport

def getRPCInterface(env):
    # dumbass ServerProxy won't allow us to pass in a non-HTTP url,
    # so we fake the url we pass into it and always use the transport's
    # 'serverurl' to figure out what to attach to
    u = env.get('SUPERVISOR_USERNAME', '')
    p = env.get('SUPERVISOR_PASSWORD', '')
    return xmlrpclib.ServerProxy(
        'http://127.0.0.1',
        transport = SupervisorTransport(u, p, env['SUPERVISOR_SERVER_URL'])
        )

def write_stderr(msg):
    sys.stderr.write(msg)
    sys.stderr.flush()

def write_stdout(msg):
    sys.stdout.write(msg)
    sys.stdout.flush()

def get_headers(line):
    return dict([ x.split(':') for x in line.split() ])
