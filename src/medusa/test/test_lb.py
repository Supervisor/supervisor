# -*- Mode: Python -*-

# Get a lower bound for Medusa performance with a simple async
# client/server benchmark built on the async lib.  The idea is to test
# all the underlying machinery [select, asyncore, asynchat, etc...] in
# a context where there is virtually no processing of the data.

import socket
import select
import sys

# ==================================================
# server
# ==================================================

from medusa import asyncore_25 as asyncore
from medusa import asynchat_25 as asynchat

class test_channel (asynchat.async_chat):

    ac_in_buffer_size = 16384
    ac_out_buffer_size = 16384

    total_in = 0

    def __init__ (self, conn, addr):
        asynchat.async_chat.__init__ (self, conn)
        self.set_terminator ('\r\n\r\n')
        self.buffer = ''

    def collect_incoming_data (self, data):
        self.buffer = self.buffer + data
        test_channel.total_in = test_channel.total_in + len(data)

    def found_terminator (self):
        # we've gotten the data, now send it back
        data = self.buffer
        self.buffer = ''
        self.push (data+'\r\n\r\n')

    def handle_close (self):
        sys.stdout.write ('.'); sys.stdout.flush()
        self.close()

    def log (self, *args):
        pass

class test_server (asyncore.dispatcher):
    def __init__ (self, addr):

        if type(addr) == type(''):
            f = socket.AF_UNIX
        else:
            f = socket.AF_INET

        self.create_socket (f, socket.SOCK_STREAM)
        self.bind (addr)
        self.listen (5)
        print 'server started on',addr

    def handle_accept (self):
        conn, addr = self.accept()
        test_channel (conn, addr)

# ==================================================
# client
# ==================================================

# pretty much the same behavior, except that we kick
# off the exchange and decide when to quit

class test_client (test_channel):

    def __init__ (self, addr, packet, number):
        if type(addr) == type(''):
            f = socket.AF_UNIX
        else:
            f = socket.AF_INET

        asynchat.async_chat.__init__ (self)
        self.create_socket (f, socket.SOCK_STREAM)
        self.set_terminator ('\r\n\r\n')
        self.buffer = ''
        self.connect (addr)
        self.push (packet + '\r\n\r\n')
        self.number = number
        self.count = 0

    def handle_connect (self):
        pass

    def found_terminator (self):
        self.count = self.count + 1
        if self.count == self.number:
            sys.stdout.write('.'); sys.stdout.flush()
            self.close()
        else:
            test_channel.found_terminator (self)

import time

class timer:
    def __init__ (self):
        self.start = time.time()

    def end (self):
        return time.time() - self.start

if __name__ == '__main__':
    import string

    if '--poll' in sys.argv:
        sys.argv.remove ('--poll')
        use_poll=1
    else:
        use_poll=0

    if len(sys.argv) == 1:
        print 'usage: %s\n' \
        '  (as a server) [--poll] -s <ip> <port>\n' \
        '  (as a client) [--poll] -c <ip> <port> <packet-size> <num-packets> <num-connections>\n' % sys.argv[0]
        sys.exit(0)
    if sys.argv[1] == '-s':
        s = test_server ((sys.argv[2], string.atoi (sys.argv[3])))
        asyncore.loop(use_poll=use_poll)
    elif sys.argv[1] == '-c':
        # create the packet
        packet = string.atoi(sys.argv[4]) * 'B'
        host = sys.argv[2]
        port = string.atoi (sys.argv[3])
        num_packets = string.atoi (sys.argv[5])
        num_conns = string.atoi (sys.argv[6])

        t = timer()
        for i in range (num_conns):
            test_client ((host,port), packet, num_packets)
        asyncore.loop(use_poll=use_poll)
        total_time = t.end()

        # ok, now do some numbers
        bytes = test_client.total_in
        num_trans = num_packets * num_conns
        total_bytes = num_trans * len(packet)
        throughput = float (total_bytes) / total_time
        trans_per_sec = num_trans / total_time

        sys.stderr.write ('total time: %.2f\n' % total_time)
        sys.stderr.write ( 'number of transactions: %d\n' % num_trans)
        sys.stderr.write ( 'total bytes sent: %d\n' % total_bytes)
        sys.stderr.write ( 'total throughput (bytes/sec): %.2f\n' % throughput)
        sys.stderr.write ( ' [note, throughput is this amount in each direction]\n')
        sys.stderr.write ( 'transactions/second: %.2f\n' % trans_per_sec)

        sys.stdout.write (
                string.join (
                        map (str, (num_conns, num_packets, len(packet), throughput, trans_per_sec)),
                        ','
                        ) + '\n'
                )
