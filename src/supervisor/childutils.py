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
import time
import xmlrpclib
from supervisor.xmlrpc import SupervisorTransport
from supervisor.events import ProcessCommunicationEvent
from supervisor.dispatchers import PEventListenerDispatcher

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

def get_asctime():
    now = time.time()
    msecs = (now - long(now)) * 1000
    part1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    asctime = '%s,%03d' % (part1, msecs)
    return asctime

def send_proc_comm(msg, write=write_stdout):
    write(ProcessCommunicationEvent.BEGIN_TOKEN)
    write(msg)
    write(ProcessCommunicationEvent.END_TOKEN)

def send_proc_comm_stdout(msg):
    return send_proc_comm(msg, write_stdout)

def send_proc_comm_stderr(msg):
    return send_proc_comm(msg, write_stderr)

def eventdata(payload):
    headerinfo, data = payload.split('\n')
    headers = get_headers(headerinfo)
    return headers, data

class EventListenerProtocol:
    def ready(self):
        write_stdout(PEventListenerDispatcher.READY_FOR_EVENTS_TOKEN)
    def ok(self, *ignored):
        write_stdout(PEventListenerDispatcher.EVENT_PROCESSED_TOKEN)
    def fail(self, *ignored):
        write_stdout(PEventListenerDispatcher.EVENT_REJECTED_TOKEN)

protocol = EventListenerProtocol()
