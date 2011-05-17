#!/usr/bin/env python -u
##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
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

# An event listener that listens for process communications events
# from loop_eventgen.py and uses RPC to write data to the event
# generator's stdin.

import os
from supervisor import childutils

def main():
    rpcinterface = childutils.getRPCInterface(os.environ)
    while 1:
        headers, payload = childutils.listener.wait()
        if headers['eventname'].startswith('PROCESS_COMMUNICATION'):
            pheaders, pdata = childutils.eventdata(payload)
            pname = '%s:%s' % (pheaders['processname'], pheaders['groupname'])
            rpcinterface.supervisor.sendProcessStdin(pname, 'Got it yo\n')
        childutils.listener.ok()

if __name__ == '__main__':
    main()
