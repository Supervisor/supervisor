#!/usr/bin/env python

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

# A sample supervisor event listener which demonstrates how to accept
# event notifications from supervisor and how to respond properly,
# exiting after each event is accepted and processed

import sys

def write_stdout(s):
    sys.stdout.write(s)
    sys.stdout.flush()

def write_stderr(s):
    sys.stderr.write(s)
    sys.stderr.flush()

def main():
    write_stdout('READY\n') # transition from ACKNOWLEDGED to READY
    line = sys.stdin.readline()  # read a line from stdin from supervisord
    write_stderr(line) # print it out to stderr (testing only)
    ver, event, serial, length = line.split(' ', 3) # split into tokens
    data = sys.stdin.read(int(length)) # read the event payload
    write_stderr(data) # print the event payload to stderr (testing only)
    write_stdout('OK\n') # transition from READY to ACKNOWLEDGED
    # exit, if the eventlistener process config has autorestart=true,
    # it will be restarted by supervisord.

if __name__ == '__main__':
    main()
    
