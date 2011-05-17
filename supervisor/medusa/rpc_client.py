# -*- Mode: Python -*-

# Copyright 1999, 2000 by eGroups, Inc.
#
#                         All Rights Reserved
#
# Permission to use, copy, modify, and distribute this software and
# its documentation for any purpose and without fee is hereby
# granted, provided that the above copyright notice appear in all
# copies and that both that copyright notice and this permission
# notice appear in supporting documentation, and that the name of
# eGroups not be used in advertising or publicity pertaining to
# distribution of the software without specific, written prior
# permission.
#
# EGROUPS DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN
# NO EVENT SHALL EGROUPS BE LIABLE FOR ANY SPECIAL, INDIRECT OR
# CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
# OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import marshal
import socket
import string
import exceptions
import string
import sys

#
# there are three clients in here.
#
# 1) rpc client
# 2) fastrpc client
# 3) async fastrpc client
#
# we hope that *whichever* choice you make, that you will enjoy the
# excellent hand-made construction, and return to do business with us
# again in the near future.
#

class RPC_Error (exceptions.StandardError):
    pass

# ===========================================================================
#                                                         RPC Client
# ===========================================================================

# request types:
# 0 call
# 1 getattr
# 2 setattr
# 3 repr
# 4 del


class rpc_proxy:

    DEBUG = 0

    def __init__ (self, conn, oid):
        # route around __setattr__
        self.__dict__['conn'] = conn
        self.__dict__['oid'] = oid

    # Warning: be VERY CAREFUL with attribute references, keep
    #             this __getattr__ in mind!

    def __getattr__ (self, attr):
        # __getattr__ and __call__
        if attr == '__call__':
            # 0 == __call__
            return self.__remote_call__
        elif attr == '__repr__':
            # 3 == __repr__
            return self.__remote_repr__
        elif attr == '__getitem__':
            return self.__remote_getitem__
        elif attr == '__setitem__':
            return self.__remote_setitem__
        elif attr == '__len__':
            return self.__remote_len__
        else:
            # 1 == __getattr__
            return self.__send_request__ (1, attr)

    def __setattr__ (self, attr, value):
        return self.__send_request__ (2, (attr, value))

    def __del__ (self):
        try:
            self.__send_request__ (4, None)
        except:
            import who_calls
            info = who_calls.compact_traceback()
            print info

    def __remote_repr__ (self):
        r = self.__send_request__ (3, None)
        return '<remote object [%s]>' % r[1:-1]

    def __remote_call__ (self, *args):
        return self.__send_request__ (0, args)

    def __remote_getitem__ (self, key):
        return self.__send_request__ (5, key)

    def __remote_setitem__ (self, key, value):
        return self.__send_request__ (6, (key, value))

    def __remote_len__ (self):
        return self.__send_request__ (7, None)

    _request_types_ = ['call', 'getattr', 'setattr', 'repr', 'del', 'getitem', 'setitem', 'len']

    def __send_request__ (self, *args):
        if self.DEBUG:
            kind = args[0]
            print (
                    'RPC: ==> %s:%08x:%s:%s' % (
                            self.conn.address,
                            self.oid,
                            self._request_types_[kind],
                            repr(args[1:])
                            )
                    )
        packet = marshal.dumps ((self.oid,)+args)
        # send request
        self.conn.send_packet (packet)
        # get response
        data = self.conn.receive_packet()
        # types of response:
        # 0: proxy
        # 1: error
        # 2: marshal'd data

        kind, value = marshal.loads (data)

        if kind == 0:
            # proxy (value == oid)
            if self.DEBUG:
                print 'RPC: <== proxy(%08x)' % (value)
            return rpc_proxy (self.conn, value)
        elif kind == 1:
            raise RPC_Error, value
        else:
            if self.DEBUG:
                print 'RPC: <== %s' % (repr(value))
            return value

class rpc_connection:

    cache = {}

    def __init__ (self, address):
        self.address = address
        self.connect ()

    def connect (self):
        s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        s.connect (self.address)
        self.socket = s

    def receive_packet (self):
        packet_len = string.atoi (self.socket.recv (8), 16)
        packet = []
        while packet_len:
            data = self.socket.recv (8192)
            packet.append (data)
            packet_len = packet_len - len(data)
        return string.join (packet, '')

    def send_packet (self, packet):
        self.socket.send ('%08x%s' % (len(packet), packet))

def rpc_connect (address = ('localhost', 8746)):
    if not rpc_connection.cache.has_key (address):
        conn = rpc_connection (address)
        # get oid of remote object
        data = conn.receive_packet()
        (oid,) = marshal.loads (data)
        rpc_connection.cache[address] = rpc_proxy (conn, oid)
    return rpc_connection.cache[address]

# ===========================================================================
#                       fastrpc client
# ===========================================================================

class fastrpc_proxy:

    def __init__ (self, conn, path=()):
        self.conn = conn
        self.path = path

    def __getattr__ (self, attr):
        if attr == '__call__':
            return self.__method_caller__
        else:
            return fastrpc_proxy (self.conn, self.path + (attr,))

    def __method_caller__ (self, *args):
        # send request
        packet = marshal.dumps ((self.path, args))
        self.conn.send_packet (packet)
        # get response
        data = self.conn.receive_packet()
        error, result = marshal.loads (data)
        if error is None:
            return result
        else:
            raise RPC_Error, error

    def __repr__ (self):
        return '<remote-method-%s at %x>' % (string.join (self.path, '.'), id (self))

def fastrpc_connect (address = ('localhost', 8748)):
    if not rpc_connection.cache.has_key (address):
        conn = rpc_connection (address)
        rpc_connection.cache[address] = fastrpc_proxy (conn)
    return rpc_connection.cache[address]

# ===========================================================================
#                                                async fastrpc client
# ===========================================================================

import asynchat_25 as asynchat

class async_fastrpc_client (asynchat.async_chat):

    STATE_LENGTH = 'length state'
    STATE_PACKET = 'packet state'

    def __init__ (self, address=('idb', 3001)):

        asynchat.async_chat.__init__ (self)

        if type(address) is type(''):
            family = socket.AF_UNIX
        else:
            family = socket.AF_INET

        self.create_socket (family, socket.SOCK_STREAM)
        self.address = address
        self.request_fifo = []
        self.buffer = []
        self.pstate = self.STATE_LENGTH
        self.set_terminator (8)
        self._connected = 0
        self.connect (self.address)

    def log (self, *args):
        pass

    def handle_connect (self):
        self._connected = 1

    def close (self):
        self._connected = 0
        self.flush_pending_requests ('lost connection to rpc server')
        asynchat.async_chat.close(self)

    def flush_pending_requests (self, why):
        f = self.request_fifo
        while len(f):
            callback = f.pop(0)
            callback (why, None)

    def collect_incoming_data (self, data):
        self.buffer.append (data)

    def found_terminator (self):
        self.buffer, data = [], string.join (self.buffer, '')

        if self.pstate is self.STATE_LENGTH:
            packet_length = string.atoi (data, 16)
            self.set_terminator (packet_length)
            self.pstate = self.STATE_PACKET
        else:
            # modified to fix socket leak in chat server, 2000-01-27, schiller@eGroups.net
            #self.set_terminator (8)
            #self.pstate = self.STATE_LENGTH
            error, result = marshal.loads (data)
            callback = self.request_fifo.pop(0)
            callback (error, result)
            self.close()    # for chat server

    def call_method (self, method, args, callback):
        if not self._connected:
            # might be a unix socket...
            family, type = self.family_and_type
            self.create_socket (family, type)
            self.connect (self.address)
        # push the request out the socket
        path = string.split (method, '.')
        packet = marshal.dumps ((path, args))
        self.push ('%08x%s' % (len(packet), packet))
        self.request_fifo.append(callback)


if __name__ == '__main__':
    if '-f' in sys.argv:
        connect = fastrpc_connect
    else:
        connect = rpc_connect

    print 'connecting...'
    c = connect()
    print 'calling <remote>.calc.sum (1,2,3)'
    print c.calc.sum (1,2,3)
    print 'calling <remote>.calc.nonexistent(), expect an exception!'
    print c.calc.nonexistent()
