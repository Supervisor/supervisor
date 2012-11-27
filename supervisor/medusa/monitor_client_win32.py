# -*- Mode: Python -*-

# monitor client, win32 version

# since we can't do select() on stdin/stdout, we simply
# use threads and blocking sockets.  <sigh>

import supervisor.medusa.text_socket as socket
import sys
import supervisor.medusa.thread as thread
from supervisor.py3compat import *

try:
    from md5 import md5
except ImportError:
    from hashlib import md5

def hex_digest (s):
    m = md5.md5()
    m.update (s)
    return ''.join([hex (ord (x))[2:] for x in list(m.digest())])

def reader (lock, sock, password):
    # first grab the timestamp
    ts = sock.recv (1024)[:-2]
    sock.send (hex_digest (ts+password) + '\r\n')
    while 1:
        d = sock.recv (1024)
        if not d:
            lock.release()
            print('Connection closed.  Hit <return> to exit')
            thread.exit()
        sys.stdout.write (d)
        sys.stdout.flush()

def writer (lock, sock, barrel="just kidding"):
    while lock.locked():
        sock.send (
                sys.stdin.readline()[:-1] + '\r\n'
                )

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print('Usage: %s host port')
        sys.exit(0)
    print_function('Enter Password: ',end='')
    p = raw_input()
    s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
    s.connect ((sys.argv[1], int(sys.argv[2])))
    l = thread.allocate_lock()
    l.acquire()
    thread.start_new_thread (reader, (l, s, p))
    writer (l, s)
