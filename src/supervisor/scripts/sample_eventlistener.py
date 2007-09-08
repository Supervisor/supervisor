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

# A sample long-running supervisor event listener which demonstrates
# how to accept event notifications from supervisor and how to respond
# properly.  This demonstration does *not* use the
# supervisor.childutils module, which wraps the specifics of
# communications in higher-level API functions.  If your listeners are
# implemented using Python, it is recommended that you use the
# childutils module API instead of modeling your scripts on the
# lower-level protocol example below.

import sys

def write_stdout(s):
    sys.stdout.write(s)
    sys.stdout.flush()

def write_stderr(s):
    sys.stderr.write(s)
    sys.stderr.flush()

def main():
    while 1:
        write_stdout('READY\n') # transition from ACKNOWLEDGED to READY
        line = sys.stdin.readline()  # read header line from stdin 
        write_stderr(line) # print it out to stderr (testing only)
        headers = dict([ x.split(':') for x in line.split() ])
        data = sys.stdin.read(int(headers['len'])) # read the event payload
        write_stderr(data) # print the event payload to stderr (testing only)
        write_stdout('OK\n') # transition from READY to ACKNOWLEDGED

if __name__ == '__main__':
    main()
