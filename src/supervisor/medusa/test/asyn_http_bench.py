#! /usr/local/bin/python1.4
# -*- Mode: Python -*-

import asyncore
import socket
import string
import sys

def blurt (thing):
    sys.stdout.write (thing)
    sys.stdout.flush ()

total_sessions = 0

class http_client (asyncore.dispatcher_with_send):
    def __init__ (self, host='127.0.0.1', port=80, uri='/', num=10):
        asyncore.dispatcher_with_send.__init__ (self)
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.port = port
        self.uri = uri
        self.num = num
        self.bytes = 0
        self.connect ((host, port))

    def log (self, *info):
        pass

    def handle_connect (self):
        self.connected = 1
#               blurt ('o')
        self.send ('GET %s HTTP/1.0\r\n\r\n' % self.uri)

    def handle_read (self):
#               blurt ('.')
        d = self.recv (8192)
        self.bytes = self.bytes + len(d)

    def handle_close (self):
        global total_sessions
#               blurt ('(%d)' % (self.bytes))
        self.close()
        total_sessions = total_sessions + 1
        if self.num:
            http_client (self.host, self.port, self.uri, self.num-1)

import time
class timer:
    def __init__ (self):
        self.start = time.time()
    def end (self):
        return time.time() - self.start

from asyncore import socket_map, poll

MAX = 0

def loop (timeout=30.0):
    global MAX
    while socket_map:
        if len(socket_map) > MAX:
            MAX = len(socket_map)
        poll (timeout)

if __name__ == '__main__':
    if len(sys.argv) < 6:
        print 'usage: %s <host> <port> <uri> <hits> <num_clients>' % sys.argv[0]
    else:
        [host, port, uri, hits, num] = sys.argv[1:]
        hits = string.atoi (hits)
        num = string.atoi (num)
        port = string.atoi (port)
        t = timer()
        clients = map (lambda x: http_client (host, port, uri, hits-1), range(num))
        #import profile
        #profile.run ('loop')
        loop()
        total_time = t.end()
        print (
                '\n%d clients\n%d hits/client\n'
                'total_hits:%d\n%.3f seconds\ntotal hits/sec:%.3f' % (
                        num,
                        hits,
                        total_sessions,
                        total_time,
                        total_sessions / total_time
                        )
                )
        print 'Max. number of concurrent sessions: %d' % (MAX)


# linux 2.x, talking to medusa
# 50 clients
# 1000 hits/client
# total_hits:50000
# 2255.858 seconds
# total hits/sec:22.165
# Max. number of concurrent sessions: 50
