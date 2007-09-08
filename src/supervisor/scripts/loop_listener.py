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
# from loop_eventgen.py and uses RPC to write data to the event
# generator's stdin.

import sys
import os
from supervisor import childutils

def main():
    rpcinterface = childutils.getRPCInterface(os.environ)
    while 1:
        headers, payload = childutils.protocol.wait()
        if headers['eventname'].startswith('PROCESS_COMMUNICATION'):
            pheaderinfo, pdata = payload.split('\n')
            pheaders = childutils.get_headers(pheaderinfo)
            pname = '%s:%s' % (pheaders['processname'], pheaders['groupname'])
            rpcinterface.supervisor.sendProcessStdin(pname, 'Got it yo\n')
        childutils.protocol.ok()

if __name__ == '__main__':
    main()
