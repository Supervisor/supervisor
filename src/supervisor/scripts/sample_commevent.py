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

# An example process which emits a stdout process communication event every
# second (or every number of seconds specified as a single argument).

import sys
import time

def write_stdout(s):
    sys.stdout.write(s)
    sys.stdout.flush()

def main(sleep):
    while 1:
        write_stdout('<!--XSUPERVISOR:BEGIN-->')
        write_stdout('the data')
        write_stdout('<!--XSUPERVISOR:END-->')
        time.sleep(sleep)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(float(sys.argv[1]))
    else:
        main(1)

