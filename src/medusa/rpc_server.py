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

# There are two RPC implementations here.

# The first ('rpc') attempts to be as transparent as possible, and
# passes along 'internal' methods like __getattr__, __getitem__, and
# __del__.  It is rather 'chatty', and may not be suitable for a
# high-performance system.

# The second ('fastrpc') is less flexible, but has much less overhead,
# and is easier to use from an asynchronous client.

import marshal
import socket
import string
import sys
import types

import asyncore
import asynchat

from producers import scanning_producer
from counter import counter

MY_NAME = string.split (socket.gethostname(), '.')[0]

# ===========================================================================
#                                                         RPC server
# ===========================================================================

# marshal is good for low-level data structures.
# but when passing an 'object' (any non-marshallable object)
# we really want to pass a 'reference', which will act on
# the other side as a proxy.  How transparent can we make this?

class rpc_channel (asynchat.async_chat):

    'Simple RPC server.'

    # a 'packet': NNNNNNNNmmmmmmmmmmmmmmmm
    # (hex length in 8 bytes, followed by marshal'd packet data)
    # same protocol used in both directions.

    STATE_LENGTH = 'length state'
    STATE_PACKET = 'packet state'

    ac_out_buffer_size = 65536

    request_counter = counter()
    exception_counter = counter()
    client_counter = counter()

    def __init__ (self, root, conn, addr):
        self.root = root
        self.addr = addr
        asynchat.async_chat.__init__ (self, conn)
        self.pstate = self.STATE_LENGTH
        self.set_terminator (8)
        self.buffer = []
        self.proxies = {}
        rid = id(root)
        self.new_reference (root)
        p = marshal.dumps ((rid,))
        # send root oid to the other side
        self.push ('%08x%s' % (len(p), p))
        self.client_counter.increment()

    def new_reference (self, object):
        oid = id(object)
        ignore, refcnt = self.proxies.get (oid, (None, 0))
        self.proxies[oid] = (object, refcnt + 1)

    def forget_reference (self, oid):
        object, refcnt = self.proxies.get (oid, (None, 0))
        if refcnt > 1:
            self.proxies[oid] = (object, refcnt - 1)
        else:
            del self.proxies[oid]

    def log (self, *ignore):
        pass

    def collect_incoming_data (self, data):
        self.buffer.append (data)

    def found_terminator (self):
        self.buffer, data = [], string.join (self.buffer, '')

        if self.pstate is self.STATE_LENGTH:
            packet_length = string.atoi (data, 16)
            self.set_terminator (packet_length)
            self.pstate = self.STATE_PACKET
        else:

            self.set_terminator (8)
            self.pstate = self.STATE_LENGTH

            oid, kind, arg = marshal.loads (data)

            obj, refcnt = self.proxies[oid]
            e = None
            reply_kind = 2

            try:
                if kind == 0:
                    # __call__
                    result = apply (obj, arg)
                elif kind == 1:
                    # __getattr__
                    result = getattr (obj, arg)
                elif kind == 2:
                    # __setattr__
                    key, value = arg
                    setattr (obj, key, value)
                    result = None
                elif kind == 3:
                    # __repr__
                    result = repr(obj)
                elif kind == 4:
                    # __del__
                    self.forget_reference (oid)
                    result = None
                elif kind == 5:
                    # __getitem__
                    result = obj[arg]
                elif kind == 6:
                    # __setitem__
                    (key, value) = arg
                    obj[key] = value
                    result = None
                elif kind == 7:
                    # __len__
                    result = len(obj)

            except:
                reply_kind = 1
                (file,fun,line), t, v, tbinfo = asyncore.compact_traceback()
                result = '%s:%s:%s:%s (%s:%s)' % (MY_NAME, file, fun, line, t, str(v))
                self.log_info (result, 'error')
                self.exception_counter.increment()

            self.request_counter.increment()

            # optimize a common case
            if type(result) is types.InstanceType:
                can_marshal = 0
            else:
                can_marshal = 1

            try:
                rb = marshal.dumps ((reply_kind, result))
            except ValueError:
                can_marshal = 0

            if not can_marshal:
                # unmarshallable object, return a reference
                rid = id(result)
                self.new_reference (result)
                rb = marshal.dumps ((0, rid))

            self.push_with_producer (
                    scanning_producer (
                            ('%08x' % len(rb)) + rb,
                            buffer_size = 65536
                            )
                    )

class rpc_server_root:
    pass

class rpc_server (asyncore.dispatcher):

    def __init__ (self, root, address = ('', 8746)):
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind (address)
        self.listen (128)
        self.root = root

    def handle_accept (self):
        conn, addr = self.accept()
        rpc_channel (self.root, conn, addr)


# ===========================================================================
#                                                  Fast RPC server
# ===========================================================================

# no proxies, request consists
# of a 'chain' of getattrs terminated by a __call__.

# Protocol:
# <path>.<to>.<object> ( <param1>, <param2>, ... )
# => ( <value1>, <value2>, ... )
#
#
# (<path>, <params>)
# path: tuple of strings
# params: tuple of objects

class fastrpc_channel (asynchat.async_chat):

    'Simple RPC server'

    # a 'packet': NNNNNNNNmmmmmmmmmmmmmmmm
    # (hex length in 8 bytes, followed by marshal'd packet data)
    # same protocol used in both directions.

    # A request consists of (<path-tuple>, <args-tuple>)
    # where <path-tuple> is a list of strings (eqv to string.split ('a.b.c', '.'))

    STATE_LENGTH = 'length state'
    STATE_PACKET = 'packet state'

    def __init__ (self, root, conn, addr):
        self.root = root
        self.addr = addr
        asynchat.async_chat.__init__ (self, conn)
        self.pstate = self.STATE_LENGTH
        self.set_terminator (8)
        self.buffer = []

    def log (*ignore):
        pass

    def collect_incoming_data (self, data):
        self.buffer.append (data)

    def found_terminator (self):
        self.buffer, data = [], string.join (self.buffer, '')

        if self.pstate is self.STATE_LENGTH:
            packet_length = string.atoi (data, 16)
            self.set_terminator (packet_length)
            self.pstate = self.STATE_PACKET
        else:
            self.set_terminator (8)
            self.pstate = self.STATE_LENGTH
            (path, params) = marshal.loads (data)
            o = self.root

            e = None

            try:
                for p in path:
                    o = getattr (o, p)
                result = apply (o, params)
            except:
                e = repr (asyncore.compact_traceback())
                result = None

            rb = marshal.dumps ((e,result))
            self.push (('%08x' % len(rb)) + rb)

class fastrpc_server (asyncore.dispatcher):

    def __init__ (self, root, address = ('', 8748)):
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind (address)
        self.listen (128)
        self.root = root

    def handle_accept (self):
        conn, addr = self.accept()
        fastrpc_channel (self.root, conn, addr)

# ===========================================================================

if __name__ == '__main__':

    class thing:
        def __del__ (self):
            print 'a thing has gone away %08x' % id(self)

    class sample_calc:

        def product (self, *values):
            return reduce (lambda a,b: a*b, values, 1)

        def sum (self, *values):
            return reduce (lambda a,b: a+b, values, 0)

        def eval (self, string):
            return eval (string)

        def make_a_thing (self):
            return thing()

    if '-f' in sys.argv:
        server_class = fastrpc_server
        address = ('', 8748)
    else:
        server_class = rpc_server
        address = ('', 8746)

    root = rpc_server_root()
    root.calc = sample_calc()
    root.sys = sys
    rs = server_class (root, address)
    asyncore.loop()
