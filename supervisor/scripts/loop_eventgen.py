#!/usr/bin/env python

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
        childutils.pcomm.stdout('the_data')
        sys.stdin.readline()
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


