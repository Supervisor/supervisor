#!/usr/bin/env python

# A sample long-running supervisor event listener which demonstrates
# how to accept event notifications from supervisor and how to respond
# properly.  It is the same as the sample_eventlistener.py script
# except it exits after each request (presumably to be restarted by
# supervisor).  This demonstration does *not* use the
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
    write_stdout('READY\n') # transition from ACKNOWLEDGED to READY
    line = sys.stdin.readline()  # read a line from stdin from supervisord
    write_stderr(line) # print it out to stderr (testing only)
    headers = dict([ x.split(':') for x in line.split() ])
    data = sys.stdin.read(int(headers['len'])) # read the event payload
    write_stderr(data) # print the event payload to stderr (testing only)
    write_stdout('RESULT 2\nOK') # transition from READY to ACKNOWLEDGED
    # exit, if the eventlistener process config has autorestart=true,
    # it will be restarted by supervisord.

if __name__ == '__main__':
    main()
    
