# -*- Mode: Python -*-

#
#       Author: Sam Rushing <rushing@nightmare.com>
#

RCS_ID =  '$Id: resolver.py,v 1.4 2002/03/20 17:37:48 amk Exp $'


# Fast, low-overhead asynchronous name resolver.  uses 'pre-cooked'
# DNS requests, unpacks only as much as it needs of the reply.

# see rfc1035 for details

import string
import asyncore_25 as asyncore
import socket
import sys
import time
from counter import counter

VERSION = string.split(RCS_ID)[2]

# header
#                                    1  1  1  1  1  1
#      0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                      ID                       |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |QR|   Opcode  |AA|TC|RD|RA|   Z    |   RCODE   |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                    QDCOUNT                    |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                    ANCOUNT                    |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                    NSCOUNT                    |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                    ARCOUNT                    |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+


# question
#                                    1  1  1  1  1  1
#      0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                                               |
#    /                     QNAME                     /
#    /                                               /
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                     QTYPE                     |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                     QCLASS                    |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

# build a DNS address request, _quickly_
def fast_address_request (host, id=0):
    return (
            '%c%c' % (chr((id>>8)&0xff),chr(id&0xff))
            + '\001\000\000\001\000\000\000\000\000\000%s\000\000\001\000\001' % (
                    string.join (
                            map (
                                    lambda part: '%c%s' % (chr(len(part)),part),
                                    string.split (host, '.')
                                    ), ''
                            )
                    )
            )

def fast_ptr_request (host, id=0):
    return (
            '%c%c' % (chr((id>>8)&0xff),chr(id&0xff))
            + '\001\000\000\001\000\000\000\000\000\000%s\000\000\014\000\001' % (
                    string.join (
                            map (
                                    lambda part: '%c%s' % (chr(len(part)),part),
                                    string.split (host, '.')
                                    ), ''
                            )
                    )
            )

def unpack_name (r,pos):
    n = []
    while 1:
        ll = ord(r[pos])
        if (ll&0xc0):
            # compression
            pos = (ll&0x3f << 8) + (ord(r[pos+1]))
        elif ll == 0:
            break
        else:
            pos = pos + 1
            n.append (r[pos:pos+ll])
            pos = pos + ll
    return string.join (n,'.')

def skip_name (r,pos):
    s = pos
    while 1:
        ll = ord(r[pos])
        if (ll&0xc0):
            # compression
            return pos + 2
        elif ll == 0:
            pos = pos + 1
            break
        else:
            pos = pos + ll + 1
    return pos

def unpack_ttl (r,pos):
    return reduce (
            lambda x,y: (x<<8)|y,
            map (ord, r[pos:pos+4])
            )

# resource record
#                                    1  1  1  1  1  1
#      0  1  2  3  4  5  6  7  8  9  0  1  2  3  4  5
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                                               |
#    /                                               /
#    /                      NAME                     /
#    |                                               |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                      TYPE                     |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                     CLASS                     |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                      TTL                      |
#    |                                               |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+
#    |                   RDLENGTH                    |
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--|
#    /                     RDATA                     /
#    /                                               /
#    +--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+--+

def unpack_address_reply (r):
    ancount = (ord(r[6])<<8) + (ord(r[7]))
    # skip question, first name starts at 12,
    # this is followed by QTYPE and QCLASS
    pos = skip_name (r, 12) + 4
    if ancount:
        # we are looking very specifically for
        # an answer with TYPE=A, CLASS=IN (\000\001\000\001)
        for an in range(ancount):
            pos = skip_name (r, pos)
            if r[pos:pos+4] == '\000\001\000\001':
                return (
                        unpack_ttl (r,pos+4),
                        '%d.%d.%d.%d' % tuple(map(ord,r[pos+10:pos+14]))
                        )
            # skip over TYPE, CLASS, TTL, RDLENGTH, RDATA
            pos = pos + 8
            rdlength = (ord(r[pos])<<8) + (ord(r[pos+1]))
            pos = pos + 2 + rdlength
        return 0, None
    else:
        return 0, None

def unpack_ptr_reply (r):
    ancount = (ord(r[6])<<8) + (ord(r[7]))
    # skip question, first name starts at 12,
    # this is followed by QTYPE and QCLASS
    pos = skip_name (r, 12) + 4
    if ancount:
        # we are looking very specifically for
        # an answer with TYPE=PTR, CLASS=IN (\000\014\000\001)
        for an in range(ancount):
            pos = skip_name (r, pos)
            if r[pos:pos+4] == '\000\014\000\001':
                return (
                        unpack_ttl (r,pos+4),
                        unpack_name (r, pos+10)
                        )
            # skip over TYPE, CLASS, TTL, RDLENGTH, RDATA
            pos = pos + 8
            rdlength = (ord(r[pos])<<8) + (ord(r[pos+1]))
            pos = pos + 2 + rdlength
        return 0, None
    else:
        return 0, None


# This is a UDP (datagram) resolver.

#
# It may be useful to implement a TCP resolver.  This would presumably
# give us more reliable behavior when things get too busy.  A TCP
# client would have to manage the connection carefully, since the
# server is allowed to close it at will (the RFC recommends closing
# after 2 minutes of idle time).
#
# Note also that the TCP client will have to prepend each request
# with a 2-byte length indicator (see rfc1035).
#

class resolver (asyncore.dispatcher):
    id = counter()
    def __init__ (self, server='127.0.0.1'):
        asyncore.dispatcher.__init__ (self)
        self.create_socket (socket.AF_INET, socket.SOCK_DGRAM)
        self.server = server
        self.request_map = {}
        self.last_reap_time = int(time.time())      # reap every few minutes

    def writable (self):
        return 0

    def log (self, *args):
        pass

    def handle_close (self):
        self.log_info('closing!')
        self.close()

    def handle_error (self):      # don't close the connection on error
        (file,fun,line), t, v, tbinfo = asyncore.compact_traceback()
        self.log_info(
                        'Problem with DNS lookup (%s:%s %s)' % (t, v, tbinfo),
                        'error')

    def get_id (self):
        return (self.id.as_long() % (1<<16))

    def reap (self):          # find DNS requests that have timed out
        now = int(time.time())
        if now - self.last_reap_time > 180:        # reap every 3 minutes
            self.last_reap_time = now              # update before we forget
            for k,(host,unpack,callback,when) in self.request_map.items():
                if now - when > 180:               # over 3 minutes old
                    del self.request_map[k]
                    try:                           # same code as in handle_read
                        callback (host, 0, None)   # timeout val is (0,None)
                    except:
                        (file,fun,line), t, v, tbinfo = asyncore.compact_traceback()
                        self.log_info('%s %s %s' % (t,v,tbinfo), 'error')

    def resolve (self, host, callback):
        self.reap()                                # first, get rid of old guys
        self.socket.sendto (
                fast_address_request (host, self.get_id()),
                (self.server, 53)
                )
        self.request_map [self.get_id()] = (
                host, unpack_address_reply, callback, int(time.time()))
        self.id.increment()

    def resolve_ptr (self, host, callback):
        self.reap()                                # first, get rid of old guys
        ip = string.split (host, '.')
        ip.reverse()
        ip = string.join (ip, '.') + '.in-addr.arpa'
        self.socket.sendto (
                fast_ptr_request (ip, self.get_id()),
                (self.server, 53)
                )
        self.request_map [self.get_id()] = (
                host, unpack_ptr_reply, callback, int(time.time()))
        self.id.increment()

    def handle_read (self):
        reply, whence = self.socket.recvfrom (512)
        # for security reasons we may want to double-check
        # that <whence> is the server we sent the request to.
        id = (ord(reply[0])<<8) + ord(reply[1])
        if self.request_map.has_key (id):
            host, unpack, callback, when = self.request_map[id]
            del self.request_map[id]
            ttl, answer = unpack (reply)
            try:
                callback (host, ttl, answer)
            except:
                (file,fun,line), t, v, tbinfo = asyncore.compact_traceback()
                self.log_info('%s %s %s' % ( t,v,tbinfo), 'error')

class rbl (resolver):

    def resolve_maps (self, host, callback):
        ip = string.split (host, '.')
        ip.reverse()
        ip = string.join (ip, '.') + '.rbl.maps.vix.com'
        self.socket.sendto (
                fast_ptr_request (ip, self.get_id()),
                (self.server, 53)
                )
        self.request_map [self.get_id()] = host, self.check_reply, callback
        self.id.increment()

    def check_reply (self, r):
        # we only need to check RCODE.
        rcode = (ord(r[3])&0xf)
        self.log_info('MAPS RBL; RCODE =%02x\n %s' % (rcode, repr(r)))
        return 0, rcode # (ttl, answer)


class hooked_callback:
    def __init__ (self, hook, callback):
        self.hook, self.callback = hook, callback

    def __call__ (self, *args):
        apply (self.hook, args)
        apply (self.callback, args)

class caching_resolver (resolver):
    "Cache DNS queries.  Will need to honor the TTL value in the replies"

    def __init__ (*args):
        apply (resolver.__init__, args)
        self = args[0]
        self.cache = {}
        self.forward_requests = counter()
        self.reverse_requests = counter()
        self.cache_hits = counter()

    def resolve (self, host, callback):
        self.forward_requests.increment()
        if self.cache.has_key (host):
            when, ttl, answer = self.cache[host]
            # ignore TTL for now
            callback (host, ttl, answer)
            self.cache_hits.increment()
        else:
            resolver.resolve (
                    self,
                    host,
                    hooked_callback (
                            self.callback_hook,
                            callback
                            )
                    )

    def resolve_ptr (self, host, callback):
        self.reverse_requests.increment()
        if self.cache.has_key (host):
            when, ttl, answer = self.cache[host]
            # ignore TTL for now
            callback (host, ttl, answer)
            self.cache_hits.increment()
        else:
            resolver.resolve_ptr (
                    self,
                    host,
                    hooked_callback (
                            self.callback_hook,
                            callback
                            )
                    )

    def callback_hook (self, host, ttl, answer):
        self.cache[host] = time.time(), ttl, answer

    SERVER_IDENT = 'Caching DNS Resolver (V%s)' % VERSION

    def status (self):
        import producers
        return producers.simple_producer (
                '<h2>%s</h2>'                                   % self.SERVER_IDENT
                + '<br>Server: %s'                              % self.server
                + '<br>Cache Entries: %d'               % len(self.cache)
                + '<br>Outstanding Requests: %d' % len(self.request_map)
                + '<br>Forward Requests: %s'    % self.forward_requests
                + '<br>Reverse Requests: %s'    % self.reverse_requests
                + '<br>Cache Hits: %s'                  % self.cache_hits
                )

#test_reply = """\000\000\205\200\000\001\000\001\000\002\000\002\006squirl\011nightmare\003com\000\000\001\000\001\300\014\000\001\000\001\000\001Q\200\000\004\315\240\260\005\011nightmare\003com\000\000\002\000\001\000\001Q\200\000\002\300\014\3006\000\002\000\001\000\001Q\200\000\015\003ns1\003iag\003net\000\300\014\000\001\000\001\000\001Q\200\000\004\315\240\260\005\300]\000\001\000\001\000\000\350\227\000\004\314\033\322\005"""
# def test_unpacker ():
#       print unpack_address_reply (test_reply)
#
# import time
# class timer:
#       def __init__ (self):
#               self.start = time.time()
#       def end (self):
#               return time.time() - self.start
#
# # I get ~290 unpacks per second for the typical case, compared to ~48
# # using dnslib directly.  also, that latter number does not include
# # picking the actual data out.
#
# def benchmark_unpacker():
#
#       r = range(1000)
#       t = timer()
#       for i in r:
#               unpack_address_reply (test_reply)
#       print '%.2f unpacks per second' % (1000.0 / t.end())

if __name__ == '__main__':
    if len(sys.argv) == 1:
        print 'usage: %s [-r] [-s <server_IP>] host [host ...]' % sys.argv[0]
        sys.exit(0)
    elif ('-s' in sys.argv):
        i = sys.argv.index('-s')
        server = sys.argv[i+1]
        del sys.argv[i:i+2]
    else:
        server = '127.0.0.1'

    if ('-r' in sys.argv):
        reverse = 1
        i = sys.argv.index('-r')
        del sys.argv[i]
    else:
        reverse = 0

    if ('-m' in sys.argv):
        maps = 1
        sys.argv.remove ('-m')
    else:
        maps = 0

    if maps:
        r = rbl (server)
    else:
        r = caching_resolver(server)

    count = len(sys.argv) - 1

    def print_it (host, ttl, answer):
        global count
        print '%s: %s' % (host, answer)
        count = count - 1
        if not count:
            r.close()

    for host in sys.argv[1:]:
        if reverse:
            r.resolve_ptr (host, print_it)
        elif maps:
            r.resolve_maps (host, print_it)
        else:
            r.resolve (host, print_it)

    # hooked asyncore.loop()
    while asyncore.socket_map:
        asyncore.poll (30.0)
        print 'requests outstanding: %d' % len(r.request_map)
