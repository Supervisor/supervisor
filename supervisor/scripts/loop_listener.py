#!/usr/bin/env python -u

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
