# -*- Mode: Python -*-

# no-holds barred, test a single channel's pipelining speed

import string
import socket

def build_request_chain (num, host, request_size):
    s = 'GET /test%d.html HTTP/1.1\r\nHost: %s\r\n\r\n' % (request_size, host)
    sl = [s] * (num-1)
    sl.append (
            'GET /test%d.html HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n' % (
                    request_size, host
                    )
            )
    return string.join (sl, '')

import time

class timer:
    def __init__ (self):
        self.start = time.time()

    def end (self):
        return time.time() - self.start

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 5:
        print 'usage: %s <host> <port> <request-size> <num-requests>' % (sys.argv[0])
    else:
        host = sys.argv[1]
        [port, request_size, num_requests] = map (
                string.atoi,
                sys.argv[2:]
                )
        chain = build_request_chain (num_requests, host, request_size)
        import socket
        s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        s.connect ((host,port))
        t = timer()
        s.send (chain)
        num_bytes = 0
        while 1:
            data = s.recv(16384)
            if not data:
                break
            else:
                num_bytes = num_bytes + len(data)
        total_time = t.end()
        print 'total bytes received: %d' % num_bytes
        print 'total time: %.2f sec' % (total_time)
        print 'transactions/sec: %.2f' % (num_requests/total_time)
