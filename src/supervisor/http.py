from medusa import http_date
from medusa import http_server
from medusa import producers
from medusa import filesys
import asyncore
import os
import stat
import time
import sys
import string
import socket
import errno
import pwd

NOT_DONE_YET = []

class deferring_chunked_producer:
    """A producer that implements the 'chunked' transfer coding for HTTP/1.1.
    Here is a sample usage:
            request['Transfer-Encoding'] = 'chunked'
            request.push (
                    producers.chunked_producer (your_producer)
                    )
            request.done()
    """

    def __init__ (self, producer, footers=None):
        self.producer = producer
        self.footers = footers
        self.delay = 0.1

    def more (self):
        if self.producer:
            data = self.producer.more()
            if data is NOT_DONE_YET:
                return NOT_DONE_YET
            elif data:
                return '%x\r\n%s\r\n' % (len(data), data)
            else:
                self.producer = None
                if self.footers:
                    return string.join (
                            ['0'] + self.footers,
                            '\r\n'
                            ) + '\r\n\r\n'
                else:
                    return '0\r\n\r\n'
        else:
            return ''

class deferring_composite_producer:
    "combine a fifo of producers into one"
    def __init__ (self, producers):
        self.producers = producers
        self.delay = 0.1

    def more (self):
        while len(self.producers):
            p = self.producers[0]
            d = p.more()
            if d is NOT_DONE_YET:
                return NOT_DONE_YET
            if d:
                return d
            else:
                self.producers.pop(0)
        else:
            return ''


class deferring_globbing_producer:
    """
    'glob' the output from a producer into a particular buffer size.
    helps reduce the number of calls to send().  [this appears to
    gain about 30% performance on requests to a single channel]
    """

    def __init__ (self, producer, buffer_size=1<<16):
        self.producer = producer
        self.buffer = ''
        self.buffer_size = buffer_size
        self.delay = 0.1

    def more (self):
        while len(self.buffer) < self.buffer_size:
            data = self.producer.more()
            if data is NOT_DONE_YET:
                return NOT_DONE_YET
            if data:
                self.buffer = self.buffer + data
            else:
                break
        r = self.buffer
        self.buffer = ''
        return r


class deferring_hooked_producer:
    """
    A producer that will call <function> when it empties,.
    with an argument of the number of bytes produced.  Useful
    for logging/instrumentation purposes.
    """

    def __init__ (self, producer, function):
        self.producer = producer
        self.function = function
        self.bytes = 0
        self.delay = 0.1

    def more (self):
        if self.producer:
            result = self.producer.more()
            if result is NOT_DONE_YET:
                return NOT_DONE_YET
            if not result:
                self.producer = None
                self.function (self.bytes)
            else:
                self.bytes = self.bytes + len(result)
            return result
        else:
            return ''


class deferring_http_request(http_server.http_request):
    """ The medusa http_request class uses the default set of producers in
    medusa.prodcers.  We can't use these because they don't know anything about
    deferred responses, so we override various methods here.  This was added
    to support tail -f like behavior on the logtail handler """

    def done(self, *arg, **kw):

        """ I didn't want to override this, but there's no way around
        it in order to support deferreds - CM

        finalize this transaction - send output to the http channel"""

        # ----------------------------------------
        # persistent connection management
        # ----------------------------------------

        #  --- BUCKLE UP! ----

        connection = string.lower(http_server.get_header(
            http_server.CONNECTION,
            self.header))

        close_it = 0
        wrap_in_chunking = 0
        globbing = 1

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
            elif not self.has_key('Content-Length'):
                if self.has_key('Transfer-Encoding'):
                    if not self['Transfer-Encoding'] == 'chunked':
                        close_it = 1
                elif self.use_chunked:
                    self['Transfer-Encoding'] = 'chunked'
                    wrap_in_chunking = 1
                    # globbing slows down tail -f output, so only use it if
                    # we're not in chunked mode
                    globbing = 0
                else:
                    close_it = 1
        elif self.version is None:
            # Although we don't *really* support http/0.9 (because
            # we'd have to use \r\n as a terminator, and it would just
            # yuck up a lot of stuff) it's very common for developers
            # to not want to type a version number when using telnet
            # to debug a server.
            close_it = 1

        outgoing_header = producers.simple_producer(self.build_reply_header())

        if close_it:
            self['Connection'] = 'close'

        if wrap_in_chunking:
            outgoing_producer = deferring_chunked_producer(
                    deferring_composite_producer(self.outgoing)
                    )
            # prepend the header
            outgoing_producer = deferring_composite_producer(
                [outgoing_header, outgoing_producer]
                )
        else:
            # prepend the header
            self.outgoing.insert(0, outgoing_header)
            outgoing_producer = deferring_composite_producer(self.outgoing)

        # hook logging into the output
        outgoing_producer = deferring_hooked_producer(outgoing_producer,
                                                      self.log)

        if globbing:
            outgoing_producer = deferring_globbing_producer(outgoing_producer)

        self.channel.push_with_producer(outgoing_producer)

        self.channel.current_request = None

        if close_it:
            self.channel.close_when_done()

    def log (self, bytes):
        """ We need to override this because UNIX domain sockets return
        an empty string for the addr rather than a (host, port) combination """
        if self.channel.addr:
            host = self.channel.addr[0]
            port = self.channel.addr[1]
        else:
            host = 'localhost'
            port = 0
        self.channel.server.logger.log (
                host,
                '%d - - [%s] "%s" %d %d\n' % (
                        port,
                        self.log_date_string (time.time()),
                        self.request,
                        self.reply_code,
                        bytes
                        )
                )

class deferring_http_channel(http_server.http_channel):

    # use a 4906-byte buffer size instead of the default 65536-byte buffer in
    # order to spew tail -f output faster (speculative)
    ac_out_buffer_size = 4096
    
    delay = False
    writable_check = time.time()

    def writable(self, t=time.time):
        now = t()
        if self.delay:
            # we called a deferred producer via this channel (see refill_buffer)
            last_writable_check = self.writable_check
            self.writable_check = now
            elapsed = now - last_writable_check
            if elapsed > self.delay:
                return True
            else:
                return False

        return http_server.http_channel.writable(self)

    def refill_buffer (self):
        """ Implement deferreds """
        while 1:
            if len(self.producer_fifo):
                p = self.producer_fifo.first()
                # a 'None' in the producer fifo is a sentinel,
                # telling us to close the channel.
                if p is None:
                    if not self.ac_out_buffer:
                        self.producer_fifo.pop()
                        self.close()
                    return
                elif isinstance(p, str):
                    self.producer_fifo.pop()
                    self.ac_out_buffer = self.ac_out_buffer + p
                    return

                data = p.more()

                if data is NOT_DONE_YET:
                    self.delay = p.delay
                    return

                elif data:
                    self.ac_out_buffer = self.ac_out_buffer + data
                    return
                else:
                    self.producer_fifo.pop()
            else:
                return

    def found_terminator (self):
        """ We only override this to use 'deferring_http_request' class
        instead of the normal http_request class; it sucks to need to override
        this """
        
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

            command, uri, version = http_server.crack_request (request)
            header = http_server.join_headers (lines[1:])

            # unquote path if necessary (thanks to Skip Montanaro for pointing
            # out that we must unquote in piecemeal fashion).
            rpath, rquery = http_server.splitquery(uri)
            if '%' in rpath:
                if rquery:
                    uri = http_server.unquote (rpath) + '?' + rquery
                else:
                    uri = http_server.unquote (rpath)

            r = deferring_http_request (self, request, command, uri, version,
                                         header)
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
                        (file, fun, line), t, v, tbinfo = \
                               asyncore.compact_traceback()
                        self.log_info(
                            'Server Error: %s, %s: file: %s line: %s' %
                            (t,v,file,line),
                            'error')
                        try:
                            r.error (500)
                        except:
                            pass
                    return

            # no handlers, so complain
            r.error (404)

class supervisor_http_server(http_server.http_server):
    channel_class = deferring_http_channel
    ip = None

    def prebind(self, sock, logger_object):
        """ Override __init__ to do logger setup earlier so it can
        go to our logger object instead of stdout """
        from medusa import logger

        if not logger_object:
            logger_object = logger.file_logger(sys.stdout)

        logger_object = logger.unresolving_logger(logger_object)
        self.logger = logger_object

        asyncore.dispatcher.__init__ (self)
        self.set_socket(sock)

        self.handlers = []

        sock.setblocking(0)
        self.set_reuse_addr()
        
    def postbind(self):
        from medusa.counter import counter
        from medusa.http_server import VERSION_STRING

        self.listen(1024)

        self.total_clients = counter()
        self.total_requests = counter()
        self.exceptions = counter()
        self.bytes_out = counter()
        self.bytes_in  = counter()

        self.log_info (
                'Medusa (V%s) started at %s'
                '\n\tHostname: %s'
                '\n\tPort:%s'
                '\n' % (
                        VERSION_STRING,
                        time.ctime(time.time()),
                        self.server_name,
                        self.port,
                        )
                )

    def log_info(self, message, type='info'):
        ip = ''
        if getattr(self, 'ip', None) is not None:
            ip = self.ip
        self.logger.log(ip, message)

class supervisor_af_inet_http_server(supervisor_http_server):
    """ AF_INET version of supervisor HTTP server """

    def __init__(self, ip, port, logger_object):
        self.ip = ip
        self.port = port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.prebind(sock, logger_object)
        self.bind((ip, port))

        host, port = self.socket.getsockname()
        if not ip:
            self.log_info('Computing default hostname', 'warning')
            ip = socket.gethostbyname (socket.gethostname())
        try:
            self.server_name = socket.gethostbyaddr (ip)[0]
        except socket.error:
            self.log_info('Cannot do reverse lookup', 'warning')
            self.server_name = ip       # use the IP address as the "hostname"

        self.postbind()

class supervisor_af_unix_http_server(supervisor_http_server):
    """ AF_UNIX version of supervisor HTTP server """

    def __init__(self, socketname, sockchmod, sockchown, logger_object):
        self.ip = socketname
        self.port = socketname

        # XXX this is insecure.  We really should do something like
        # http://developer.apple.com/samplecode/CFLocalServer/listing6.html
        # (see also http://developer.apple.com/technotes/tn2005/tn2083.html#SECUNIXDOMAINSOCKETS)
        # but it would be very inconvenient for the user to need to get all
        # the directory setup right.

        tempname = "%s.%d" % (socketname, os.getpid())

        try:
            os.unlink(tempname)
        except os.error:
            pass

        while 1:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(tempname)
                os.chmod(tempname, sockchmod)
                try:
                    # hard link
                    os.link(tempname, socketname)
                except os.error:
                    # Lock contention, or stale socket.
                    used = self.checkused(socketname)
                    if used:
                        # cooperate with 'openhttpserver' in supervisord
                        raise socket.error(errno.EADDRINUSE)
                        
                    # Stale socket -- delete, sleep, and try again.
                    msg = "Unlinking stale socket %s\n" % socketname
                    sys.stderr.write(msg)
                    try:
                        os.unlink(socketname)
                    except:
                        pass
                    sock.close()
                    time.sleep(.3)
                    continue
                else:
                    try:
                        os.chown(socketname, sockchown[0], sockchown[1])
                    except os.error, why:
                        if why[0] == errno.EPERM:
                            msg = ('Not permitted to chown %s to uid/gid %s; '
                                   'adjust "sockchown" value in config file or '
                                   'on command line to values that the '
                                   'current user (%s) can successfully chown')
                            raise ValueError(msg % (socketname,
                                                    repr(sockchown),
                                                    pwd.getpwuid(
                                                        os.geteuid())[0],
                                                    ),
                                             )
                        else:
                            raise
                    self.prebind(sock, logger_object)
                    break

            finally:
                try:
                    os.unlink(tempname)
                except os.error:
                    pass

        self.server_name = '<unix domain socket>'
        self.postbind()

    def checkused(self, socketname):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            s.connect(socketname)
            s.send("GET / HTTP/1.0\r\n\r\n")
            data = s.recv(1)
            s.close()
        except socket.error:
            return False
        else:
            return True

class tail_f_producer:
    def __init__(self, request, filename, head):
        self.file = open(filename, 'rb')
        self.request = request
        self.delay = 0.1
        sz = self.fsize()
        if sz >= head:
            self.sz = sz - head
        else:
            self.sz = 0

    def more(self):
        try:
            newsz = self.fsize()
        except OSError:
            # file descriptor was closed
            return ''
        bytes_added = newsz - self.sz
        if bytes_added < 0:
            self.sz = 0
            return "==> File truncated <==\n"
        if bytes_added > 0:
            self.file.seek(-bytes_added, 2)
            bytes = self.file.read(bytes_added)
            self.sz = newsz
            return bytes
        return NOT_DONE_YET

    def fsize(self):
        return os.fstat(self.file.fileno())[stat.ST_SIZE]

class logtail_handler:
    IDENT = 'Logtail HTTP Request Handler'
    path = '/logtail'

    def __init__(self, supervisord):
        self.supervisord = supervisord

    def match(self, request):
        path, params, query, fragment = request.split_uri()
        return (path[:len(self.path)] == self.path)

    def handle_request(self, request):
        if request.command != 'GET':
            request.error (400) # bad request
            return

        path, params, query, fragment = request.split_uri()

        if '%' in path:
            path = http_server.unquote(path)

        # strip off all leading slashes
        while path and path[0] == '/':
            path = path[1:]

        path, processName = path.split('/', 1)

        process = self.supervisord.processes.get(processName)
        if process is None:
            request.error(404) # not found
            return

        logfile = process.config.logfile

        if logfile is None or not os.path.exists(logfile):
            # XXX problematic: processes that don't start won't have a log
            # file and we probably don't want to go into fatal state if we try
            # to read the log of a process that did not start.
            request.error(410) # gone
            return

        mtime = os.stat(logfile)[stat.ST_MTIME]
        request['Last-Modified'] = http_date.build_http_date(mtime)
        request['Content-Type'] = 'text/plain'
        # the lack of a Content-Length header makes the outputter
        # send a 'Transfer-Encoding: chunked' response

        request.push(tail_f_producer(request, logfile, 1024))

        request.done()

def make_http_server(options, supervisord):
    if not options.http_port:
        return

    username = options.http_username
    password = options.http_password

    class LogWrapper:
        def log(self, msg):
            if msg.endswith('\n'):
                msg = msg[:-1]
            options.logger.info(msg)
    wrapper = LogWrapper()

    family = options.http_port.family
    
    if family == socket.AF_INET:
        host, port = options.http_port.address
        hs = supervisor_af_inet_http_server(host, port, logger_object=wrapper)
    elif family == socket.AF_UNIX:
        socketname = options.http_port.address
        sockchmod = options.sockchmod
        sockchown = options.sockchown
        hs = supervisor_af_unix_http_server(socketname, sockchmod, sockchown,
                                            logger_object=wrapper)
    else:
        raise ValueError('Cannot determine socket type %r' % family)

    from xmlrpc import supervisor_xmlrpc_handler
    from web import supervisor_ui_handler
    xmlrpchandler = supervisor_xmlrpc_handler(supervisord)
    tailhandler = logtail_handler(supervisord)
    here = os.path.abspath(os.path.dirname(__file__))
    templatedir = os.path.join(here, 'ui')
    filesystem = filesys.os_filesystem(templatedir)
    uihandler = supervisor_ui_handler(filesystem, supervisord)

    if username:
        # wrap the xmlrpc handler and tailhandler in an authentication handler
        users = {username:password}
        from medusa.auth_handler import auth_handler
        xmlrpchandler = auth_handler(users, xmlrpchandler)
        tailhandler = auth_handler(users, tailhandler)
        uihandler = auth_handler(users, uihandler)
    else:
        options.logger.critical('Running without any HTTP authentication '
                                'checking')
    hs.install_handler(uihandler)
    hs.install_handler(tailhandler)
    hs.install_handler(xmlrpchandler)
    return hs
