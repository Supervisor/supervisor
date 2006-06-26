#! /usr/local/bin/python
# -*- Mode: Python -*-
#
#       Author: Sam Rushing <rushing@nightmare.com>
#       Copyright 1996-2000 by Sam Rushing
#                                                All Rights Reserved.
#

RCS_ID =  '$Id$'

# python modules
import os
import re
import socket
import string
import sys
import time

# async modules
import asyncore
import asynchat

# medusa modules
import http_date
import producers
import status_handler
import logger

VERSION_STRING = string.split(RCS_ID)[2]

from counter import counter
from urllib import unquote, splitquery

# ===========================================================================
#                                                       Request Object
# ===========================================================================

class http_request:

    # default reply code
    reply_code = 200

    request_counter = counter()

    # Whether to automatically use chunked encoding when
    #
    #   HTTP version is 1.1
    #   Content-Length is not set
    #   Chunked encoding is not already in effect
    #
    # If your clients are having trouble, you might want to disable this.
    use_chunked = 1

    # by default, this request object ignores user data.
    collector = None

    def __init__ (self, *args):
        # unpack information about the request
        (self.channel, self.request,
         self.command, self.uri, self.version,
         self.header) = args

        self.outgoing = []
        self.reply_headers = {
                'Server'        : 'Medusa/%s' % VERSION_STRING,
                'Date'          : http_date.build_http_date (time.time())
                }
        self.request_number = http_request.request_counter.increment()
        self._split_uri = None
        self._header_cache = {}

    # --------------------------------------------------
    # reply header management
    # --------------------------------------------------
    def __setitem__ (self, key, value):
        self.reply_headers[key] = value

    def __getitem__ (self, key):
        return self.reply_headers[key]

    def has_key (self, key):
        return self.reply_headers.has_key (key)

    def build_reply_header (self):
        return string.join (
                [self.response(self.reply_code)] + map (
                        lambda x: '%s: %s' % x,
                        self.reply_headers.items()
                        ),
                '\r\n'
                ) + '\r\n\r\n'

    # --------------------------------------------------
    # split a uri
    # --------------------------------------------------

    # <path>;<params>?<query>#<fragment>
    path_regex = re.compile (
    #      path      params    query   fragment
            r'([^;?#]*)(;[^?#]*)?(\?[^#]*)?(#.*)?'
            )

    def split_uri (self):
        if self._split_uri is None:
            m = self.path_regex.match (self.uri)
            if m.end() != len(self.uri):
                raise ValueError, "Broken URI"
            else:
                self._split_uri = m.groups()
        return self._split_uri

    def get_header_with_regex (self, head_reg, group):
        for line in self.header:
            m = head_reg.match (line)
            if m.end() == len(line):
                return m.group (group)
        return ''

    def get_header (self, header):
        header = string.lower (header)
        hc = self._header_cache
        if not hc.has_key (header):
            h = header + ': '
            hl = len(h)
            for line in self.header:
                if string.lower (line[:hl]) == h:
                    r = line[hl:]
                    hc[header] = r
                    return r
            hc[header] = None
            return None
        else:
            return hc[header]

    # --------------------------------------------------
    # user data
    # --------------------------------------------------

    def collect_incoming_data (self, data):
        if self.collector:
            self.collector.collect_incoming_data (data)
        else:
            self.log_info(
                    'Dropping %d bytes of incoming request data' % len(data),
                    'warning'
                    )

    def found_terminator (self):
        if self.collector:
            self.collector.found_terminator()
        else:
            self.log_info (
                    'Unexpected end-of-record for incoming request',
                    'warning'
                    )

    def push (self, thing):
        if type(thing) == type(''):
            self.outgoing.append(producers.simple_producer (thing))
        else:
            self.outgoing.append(thing)

    def response (self, code=200):
        message = self.responses[code]
        self.reply_code = code
        return 'HTTP/%s %d %s' % (self.version, code, message)

    def error (self, code):
        self.reply_code = code
        message = self.responses[code]
        s = self.DEFAULT_ERROR_MESSAGE % {
                'code': code,
                'message': message,
                }
        self['Content-Length'] = len(s)
        self['Content-Type'] = 'text/html'
        # make an error reply
        self.push (s)
        self.done()

    # can also be used for empty replies
    reply_now = error

    def done (self):
        "finalize this transaction - send output to the http channel"

        # ----------------------------------------
        # persistent connection management
        # ----------------------------------------

        #  --- BUCKLE UP! ----

        connection = string.lower (get_header (CONNECTION, self.header))

        close_it = 0
        wrap_in_chunking = 0

        if self.version == '1.0':
            if connection == 'keep-alive':
                if not self.has_key ('Content-Length'):
                    close_it = 1
                else:
                    self['Connection'] = 'Keep-Alive'
            else:
                close_it = 1
        elif self.version == '1.1':
            if connection == 'close':
                close_it = 1
            elif not self.has_key ('Content-Length'):
                if self.has_key ('Transfer-Encoding'):
                    if not self['Transfer-Encoding'] == 'chunked':
                        close_it = 1
                elif self.use_chunked:
                    self['Transfer-Encoding'] = 'chunked'
                    wrap_in_chunking = 1
                else:
                    close_it = 1
        elif self.version is None:
            # Although we don't *really* support http/0.9 (because we'd have to
            # use \r\n as a terminator, and it would just yuck up a lot of stuff)
            # it's very common for developers to not want to type a version number
            # when using telnet to debug a server.
            close_it = 1

        outgoing_header = producers.simple_producer (self.build_reply_header())

        if close_it:
            self['Connection'] = 'close'

        if wrap_in_chunking:
            outgoing_producer = producers.chunked_producer (
                    producers.composite_producer (self.outgoing)
                    )
            # prepend the header
            outgoing_producer = producers.composite_producer(
                [outgoing_header, outgoing_producer]
                )
        else:
            # prepend the header
            self.outgoing.insert(0, outgoing_header)
            outgoing_producer = producers.composite_producer (self.outgoing)

        # apply a few final transformations to the output
        self.channel.push_with_producer (
                # globbing gives us large packets
                producers.globbing_producer (
                        # hooking lets us log the number of bytes sent
                        producers.hooked_producer (
                                outgoing_producer,
                                self.log
                                )
                        )
                )

        self.channel.current_request = None

        if close_it:
            self.channel.close_when_done()

    def log_date_string (self, when):
        gmt = time.gmtime(when)
        if time.daylight and gmt[8]:
            tz = time.altzone
        else:
            tz = time.timezone
        if tz > 0:
            neg = 1
        else:
            neg = 0
            tz = -tz
        h, rem = divmod (tz, 3600)
        m, rem = divmod (rem, 60)
        if neg:
            offset = '-%02d%02d' % (h, m)
        else:
            offset = '+%02d%02d' % (h, m)

        return time.strftime ( '%d/%b/%Y:%H:%M:%S ', gmt) + offset

    def log (self, bytes):
        self.channel.server.logger.log (
                self.channel.addr[0],
                '%d - - [%s] "%s" %d %d\n' % (
                        self.channel.addr[1],
                        self.log_date_string (time.time()),
                        self.request,
                        self.reply_code,
                        bytes
                        )
                )

    responses = {
            100: "Continue",
            101: "Switching Protocols",
            200: "OK",
            201: "Created",
            202: "Accepted",
            203: "Non-Authoritative Information",
            204: "No Content",
            205: "Reset Content",
            206: "Partial Content",
            300: "Multiple Choices",
            301: "Moved Permanently",
            302: "Moved Temporarily",
            303: "See Other",
            304: "Not Modified",
            305: "Use Proxy",
            400: "Bad Request",
            401: "Unauthorized",
            402: "Payment Required",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            406: "Not Acceptable",
            407: "Proxy Authentication Required",
            408: "Request Time-out",
            409: "Conflict",
            410: "Gone",
            411: "Length Required",
            412: "Precondition Failed",
            413: "Request Entity Too Large",
            414: "Request-URI Too Large",
            415: "Unsupported Media Type",
            500: "Internal Server Error",
            501: "Not Implemented",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Time-out",
            505: "HTTP Version not supported"
            }

    # Default error message
    DEFAULT_ERROR_MESSAGE = string.join (
            ['<head>',
             '<title>Error response</title>',
             '</head>',
             '<body>',
             '<h1>Error response</h1>',
             '<p>Error code %(code)d.',
             '<p>Message: %(message)s.',
             '</body>',
             ''
             ],
            '\r\n'
            )


# ===========================================================================
#                                                HTTP Channel Object
# ===========================================================================

class http_channel (asynchat.async_chat):

    # use a larger default output buffer
    ac_out_buffer_size = 1<<16

    current_request = None
    channel_counter = counter()

    def __init__ (self, server, conn, addr):
        self.channel_number = http_channel.channel_counter.increment()
        self.request_counter = counter()
        asynchat.async_chat.__init__ (self, conn)
        self.server = server
        self.addr = addr
        self.set_terminator ('\r\n\r\n')
        self.in_buffer = ''
        self.creation_time = int (time.time())
        self.check_maintenance()

    def __repr__ (self):
        ar = asynchat.async_chat.__repr__(self)[1:-1]
        return '<%s channel#: %s requests:%s>' % (
                ar,
                self.channel_number,
                self.request_counter
                )

    # Channel Counter, Maintenance Interval...
    maintenance_interval = 500

    def check_maintenance (self):
        if not self.channel_number % self.maintenance_interval:
            self.maintenance()

    def maintenance (self):
        self.kill_zombies()

    # 30-minute zombie timeout.  status_handler also knows how to kill zombies.
    zombie_timeout = 30 * 60

    def kill_zombies (self):
        now = int (time.time())
        for channel in asyncore.socket_map.values():
            if channel.__class__ == self.__class__:
                if (now - channel.creation_time) > channel.zombie_timeout:
                    channel.close()

    # --------------------------------------------------
    # send/recv overrides, good place for instrumentation.
    # --------------------------------------------------

    # this information needs to get into the request object,
    # so that it may log correctly.
    def send (self, data):
        result = asynchat.async_chat.send (self, data)
        self.server.bytes_out.increment (len(data))
        return result

    def recv (self, buffer_size):
        try:
            result = asynchat.async_chat.recv (self, buffer_size)
            self.server.bytes_in.increment (len(result))
            return result
        except MemoryError:
            # --- Save a Trip to Your Service Provider ---
            # It's possible for a process to eat up all the memory of
            # the machine, and put it in an extremely wedged state,
            # where medusa keeps running and can't be shut down.  This
            # is where MemoryError tends to get thrown, though of
            # course it could get thrown elsewhere.
            sys.exit ("Out of Memory!")

    def handle_error (self):
        t, v = sys.exc_info()[:2]
        if t is SystemExit:
            raise t, v
        else:
            asynchat.async_chat.handle_error (self)

    def log (self, *args):
        pass

    # --------------------------------------------------
    # async_chat methods
    # --------------------------------------------------

    def collect_incoming_data (self, data):
        if self.current_request:
            # we are receiving data (probably POST data) for a request
            self.current_request.collect_incoming_data (data)
        else:
            # we are receiving header (request) data
            self.in_buffer = self.in_buffer + data

    def found_terminator (self):
        if self.current_request:
            self.current_request.found_terminator()
        else:
            header = self.in_buffer
            self.in_buffer = ''
            lines = string.split (header, '\r\n')

            # --------------------------------------------------
            # crack the request header
            # --------------------------------------------------

            while lines and not lines[0]:
                # as per the suggestion of http-1.1 section 4.1, (and
                # Eric Parker <eparker@zyvex.com>), ignore a leading
                # blank lines (buggy browsers tack it onto the end of
                # POST requests)
                lines = lines[1:]

            if not lines:
                self.close_when_done()
                return

            request = lines[0]

            command, uri, version = crack_request (request)
            header = join_headers (lines[1:])

            # unquote path if necessary (thanks to Skip Montanaro for pointing
            # out that we must unquote in piecemeal fashion).
            rpath, rquery = splitquery(uri)
            if '%' in rpath:
                if rquery:
                    uri = unquote (rpath) + '?' + rquery
                else:
                    uri = unquote (rpath)

            r = http_request (self, request, command, uri, version, header)
            self.request_counter.increment()
            self.server.total_requests.increment()

            if command is None:
                self.log_info ('Bad HTTP request: %s' % repr(request), 'error')
                r.error (400)
                return

            # --------------------------------------------------
            # handler selection and dispatch
            # --------------------------------------------------
            for h in self.server.handlers:
                if h.match (r):
                    try:
                        self.current_request = r
                        # This isn't used anywhere.
                        # r.handler = h # CYCLE
                        h.handle_request (r)
                    except:
                        self.server.exceptions.increment()
                        (file, fun, line), t, v, tbinfo = asyncore.compact_traceback()
                        self.log_info(
                                        'Server Error: %s, %s: file: %s line: %s' % (t,v,file,line),
                                        'error')
                        try:
                            r.error (500)
                        except:
                            pass
                    return

            # no handlers, so complain
            r.error (404)

    def writable_for_proxy (self):
        # this version of writable supports the idea of a 'stalled' producer
        # [i.e., it's not ready to produce any output yet] This is needed by
        # the proxy, which will be waiting for the magic combination of
        # 1) hostname resolved
        # 2) connection made
        # 3) data available.
        if self.ac_out_buffer:
            return 1
        elif len(self.producer_fifo):
            p = self.producer_fifo.first()
            if hasattr (p, 'stalled'):
                return not p.stalled()
            else:
                return 1

# ===========================================================================
#                                                HTTP Server Object
# ===========================================================================

class http_server (asyncore.dispatcher):

    SERVER_IDENT = 'HTTP Server (V%s)' % VERSION_STRING

    channel_class = http_channel

    def __init__ (self, ip, port, resolver=None, logger_object=None):
        self.ip = ip
        self.port = port
        asyncore.dispatcher.__init__ (self)
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)

        self.handlers = []

        if not logger_object:
            logger_object = logger.file_logger (sys.stdout)

        self.set_reuse_addr()
        self.bind ((ip, port))

        # lower this to 5 if your OS complains
        self.listen (1024)

        host, port = self.socket.getsockname()
        if not ip:
            self.log_info('Computing default hostname', 'warning')
            ip = socket.gethostbyname (socket.gethostname())
        try:
            self.server_name = socket.gethostbyaddr (ip)[0]
        except socket.error:
            self.log_info('Cannot do reverse lookup', 'warning')
            self.server_name = ip       # use the IP address as the "hostname"

        self.server_port = port
        self.total_clients = counter()
        self.total_requests = counter()
        self.exceptions = counter()
        self.bytes_out = counter()
        self.bytes_in  = counter()

        if not logger_object:
            logger_object = logger.file_logger (sys.stdout)

        if resolver:
            self.logger = logger.resolving_logger (resolver, logger_object)
        else:
            self.logger = logger.unresolving_logger (logger_object)

        self.log_info (
                'Medusa (V%s) started at %s'
                '\n\tHostname: %s'
                '\n\tPort:%d'
                '\n' % (
                        VERSION_STRING,
                        time.ctime(time.time()),
                        self.server_name,
                        port,
                        )
                )

    def writable (self):
        return 0

    def handle_read (self):
        pass

    def readable (self):
        return self.accepting

    def handle_connect (self):
        pass

    def handle_accept (self):
        self.total_clients.increment()
        try:
            conn, addr = self.accept()
        except socket.error:
            # linux: on rare occasions we get a bogus socket back from
            # accept.  socketmodule.c:makesockaddr complains that the
            # address family is unknown.  We don't want the whole server
            # to shut down because of this.
            self.log_info ('warning: server accept() threw an exception', 'warning')
            return
        except TypeError:
            # unpack non-sequence.  this can happen when a read event
            # fires on a listening socket, but when we call accept()
            # we get EWOULDBLOCK, so dispatcher.accept() returns None.
            # Seen on FreeBSD3.
            self.log_info ('warning: server accept() threw EWOULDBLOCK', 'warning')
            return

        self.channel_class (self, conn, addr)

    def install_handler (self, handler, back=0):
        if back:
            self.handlers.append (handler)
        else:
            self.handlers.insert (0, handler)

    def remove_handler (self, handler):
        self.handlers.remove (handler)

    def status (self):
        def nice_bytes (n):
            return string.join (status_handler.english_bytes (n))

        handler_stats = filter (None, map (maybe_status, self.handlers))

        if self.total_clients:
            ratio = self.total_requests.as_long() / float(self.total_clients.as_long())
        else:
            ratio = 0.0

        return producers.composite_producer (
                [producers.lines_producer (
                        ['<h2>%s</h2>'                                                  % self.SERVER_IDENT,
                        '<br>Listening on: <b>Host:</b> %s'             % self.server_name,
                        '<b>Port:</b> %d'                                               % self.port,
                         '<p><ul>'
                         '<li>Total <b>Clients:</b> %s'                 % self.total_clients,
                         '<b>Requests:</b> %s'                                  % self.total_requests,
                         '<b>Requests/Client:</b> %.1f'                 % (ratio),
                         '<li>Total <b>Bytes In:</b> %s'        % (nice_bytes (self.bytes_in.as_long())),
                         '<b>Bytes Out:</b> %s'                         % (nice_bytes (self.bytes_out.as_long())),
                         '<li>Total <b>Exceptions:</b> %s'              % self.exceptions,
                         '</ul><p>'
                         '<b>Extension List</b><ul>',
                         ])] + handler_stats + [producers.simple_producer('</ul>')]
                )

def maybe_status (thing):
    if hasattr (thing, 'status'):
        return thing.status()
    else:
        return None

CONNECTION = re.compile ('Connection: (.*)', re.IGNORECASE)

# merge multi-line headers
# [486dx2: ~500/sec]
def join_headers (headers):
    r = []
    for i in range(len(headers)):
        if headers[i][0] in ' \t':
            r[-1] = r[-1] + headers[i][1:]
        else:
            r.append (headers[i])
    return r

def get_header (head_reg, lines, group=1):
    for line in lines:
        m = head_reg.match (line)
        if m and m.end() == len(line):
            return m.group (group)
    return ''

def get_header_match (head_reg, lines):
    for line in lines:
        m = head_reg.match (line)
        if m and m.end() == len(line):
            return m
    return ''

REQUEST = re.compile ('([^ ]+) ([^ ]+)(( HTTP/([0-9.]+))$|$)')

def crack_request (r):
    m = REQUEST.match (r)
    if m and m.end() == len(r):
        if m.group(3):
            version = m.group(5)
        else:
            version = None
        return m.group(1), m.group(2), version
    else:
        return None, None, None

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print 'usage: %s <root> <port>' % (sys.argv[0])
    else:
        import monitor
        import filesys
        import default_handler
        import status_handler
        import ftp_server
        import chat_server
        import resolver
        import logger
        rs = resolver.caching_resolver ('127.0.0.1')
        lg = logger.file_logger (sys.stdout)
        ms = monitor.secure_monitor_server ('fnord', '127.0.0.1', 9999)
        fs = filesys.os_filesystem (sys.argv[1])
        dh = default_handler.default_handler (fs)
        hs = http_server ('', string.atoi (sys.argv[2]), rs, lg)
        hs.install_handler (dh)
        ftp = ftp_server.ftp_server (
                ftp_server.dummy_authorizer(sys.argv[1]),
                port=8021,
                resolver=rs,
                logger_object=lg
                )
        cs = chat_server.chat_server ('', 7777)
        sh = status_handler.status_extension([hs,ms,ftp,cs,rs])
        hs.install_handler (sh)
        if ('-p' in sys.argv):
            def profile_loop ():
                try:
                    asyncore.loop()
                except KeyboardInterrupt:
                    pass
            import profile
            profile.run ('profile_loop()', 'profile.out')
        else:
            asyncore.loop()
