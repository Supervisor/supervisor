#!/usr/bin/env python -u

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

# An event listener that listens for process communications events
# from osx_mon_eventgen.py and kills processes that are using "too
# much memory" (based on maxbytes value passed in).
#
# This process is meant to be put into a supervisor config like this one
# (along with the generator):
#
# [eventlistener:memlistener]
# command=python osx_memmon_listener.py 200MB
# events=PROCESS_COMMUNICATION
#
# [program:monitor]
# command=python osx_memmon_eventgen.py 5
# stdout_capture_maxbytes=1MB

autostart=true              ; start at supervisord start (default: true)
autorestart=false            ; retstart at unexpected quit (default: true)
stdout_capture_maxbytes=1MB

import sys
import os
from supervisor import childutils
from supervisor import datatypes

from StringIO import StringIO
try:
    import xml.etree.ElementTree as etree
except ImportError:
    import elementtree.ElementTree as etree

def main(maxkb):
    rpc = childutils.getRPCInterface(os.environ)
    while 1:
        childutils.protocol.ready()
        line = sys.stdin.readline()
        headers = childutils.get_headers(line)
        payload = sys.stdin.read(int(headers['len']))
        if headers['eventname'].startswith('PROCESS_COMMUNICATION'):
            pheaders, pdata = childutils.eventdata(payload)
            procname, groupname = pheaders['processname'], pheaders['groupname']
            if groupname == 'monitor':
                for event, elem in etree.iterparse(StringIO(pdata)):
                    if elem.tag == 'process':
                        rss = int(elem.find('rss').text)
                        name = elem.attrib['name']
                        if  rss > maxkb:
                            rpc.supervisor.stopProcess(name)
                            rpc.supervisor.startProcess(name)
        childutils.protocol.ok()

if __name__ == '__main__':
    maxbytes = datatypes.byte_size(sys.argv[1])
    maxkb = maxbytes / 1024
    main(maxkb)
    
