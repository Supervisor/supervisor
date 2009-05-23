# -*- Mode: Python -*-

import socket
import string
from medusa import asyncore_25 as asyncore
from medusa import asynchat_25 as asynchat

# get some performance figures for an HTTP/1.1 server.
# use pipelining.

class test_client (asynchat.async_chat):

    ac_in_buffer_size = 16384
    ac_out_buffer_size = 16384

    total_in = 0

    concurrent = 0
    max_concurrent = 0

    def __init__ (self, addr, chain):
        asynchat.async_chat.__init__ (self)
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)
        self.set_terminator ('\r\n\r\n')
        self.connect (addr)
        self.push (chain)

    def handle_connect (self):
        test_client.concurrent = test_client.concurrent + 1
        if (test_client.concurrent > test_client.max_concurrent):
            test_client.max_concurrent = test_client.concurrent

    def handle_expt (self):
        print 'unexpected FD_EXPT thrown.  closing()'
        self.close()

    def close (self):
        test_client.concurrent = test_client.concurrent - 1
        asynchat.async_chat.close(self)

    def collect_incoming_data (self, data):
        test_client.total_in = test_client.total_in + len(data)

    def found_terminator (self):
        pass

    def log (self, *args):
        pass


import time

class timer:
    def __init__ (self):
        self.start = time.time()

    def end (self):
        return time.time() - self.start

def build_request_chain (num, host, request_size):
    s = 'GET /test%d.html HTTP/1.1\r\nHost: %s\r\n\r\n' % (request_size, host)
    sl = [s] * (num-1)
    sl.append (
            'GET /test%d.html HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n' % (
                    request_size, host
                    )
            )
    return string.join (sl, '')

if __name__ == '__main__':
    import string
    import sys
    if len(sys.argv) != 6:
        print 'usage: %s <host> <port> <request-size> <num-requests> <num-connections>\n' % sys.argv[0]
    else:
        host = sys.argv[1]

        ip = socket.gethostbyname (host)

        [port, request_size, num_requests, num_conns] = map (
                string.atoi, sys.argv[2:]
                )

        chain = build_request_chain (num_requests, host, request_size)

        t = timer()
        for i in range (num_conns):
            test_client ((host,port), chain)
        asyncore.loop()
        total_time = t.end()

        # ok, now do some numbers
        total_bytes = test_client.total_in
        num_trans = num_requests * num_conns
        throughput = float (total_bytes) / total_time
        trans_per_sec = num_trans / total_time

        sys.stderr.write ('total time: %.2f\n' % total_time)
        sys.stderr.write ('number of transactions: %d\n' % num_trans)
        sys.stderr.write ('total bytes sent: %d\n' % total_bytes)
        sys.stderr.write ('total throughput (bytes/sec): %.2f\n' % throughput)
        sys.stderr.write ('transactions/second: %.2f\n' % trans_per_sec)
        sys.stderr.write ('max concurrent connections: %d\n' % test_client.max_concurrent)

        sys.stdout.write (
                string.join (
                        map (str, (num_conns, num_requests, request_size, throughput, trans_per_sec)),
                        ','
                        ) + '\n'
                )
