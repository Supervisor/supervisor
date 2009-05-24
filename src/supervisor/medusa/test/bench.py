# -*- Mode: Python -*-

# benchmark a single channel, pipelined

request = 'GET /index.html HTTP/1.0\r\nConnection: Keep-Alive\r\n\r\n'
last_request = 'GET /index.html HTTP/1.0\r\nConnection: close\r\n\r\n'

import socket
import time

class timer:
    def __init__ (self):
        self.start = time.time()
    def end (self):
        return time.time() - self.start

def bench (host, port=80, n=100):
    s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
    s.connect ((host, port))
    t = timer()
    s.send ((request * n) + last_request)
    while 1:
        d = s.recv(65536)
        if not d:
            break
    total = t.end()
    print 'time: %.2f seconds  (%.2f hits/sec)' % (total, n/total)

if __name__ == '__main__':
    import sys
    import string
    if len(sys.argv) < 3:
        print 'usage: %s <host> <port> <count>' % (sys.argv[0])
    else:
        bench (sys.argv[1], string.atoi (sys.argv[2]), string.atoi (sys.argv[3]))
