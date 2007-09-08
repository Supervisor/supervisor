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

# A process which emits a process communications event on its stdout,
# and subsequently waits for a line to be sent back to its stdin by
# loop_listener.py.

import sys
import time
from supervisor import childutils

def main(max):
    start = time.time()
    report = open('/tmp/report', 'w')
    i = 0
    while 1:
        childutils.write_stdout('<!--XSUPERVISOR:BEGIN-->')
        childutils.write_stdout('the data')
        childutils.write_stdout('<!--XSUPERVISOR:END-->')
        data = sys.stdin.readline()
        report.write(str(i) + ' @ %s\n' % childutils.get_asctime())
        report.flush()
        i+=1
        if max and i >= max:
            end = time.time()
            report.write('%s per second\n' % (i / (end - start)))
            sys.exit(0)

if __name__ == '__main__':
    max = 0
    if len(sys.argv) > 1:
        max = int(sys.argv[1])
    main(max)
        

