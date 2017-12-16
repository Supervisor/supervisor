# this code based on Daniel Krech's RDFLib HTTP client code (see rdflib.net)

import sys
import socket

from supervisor.compat import PY3
from supervisor.compat import long
from supervisor.compat import urlparse
from supervisor.compat import as_bytes
from supervisor.compat import as_string
from supervisor.compat import encodestring
from supervisor.medusa import asynchat_25 as asynchat

CR="\x0d"
LF="\x0a"
CRLF=CR+LF

class Listener(object):

    def status(self, url, status):
        pass

    def error(self, url, error):
        sys.stderr.write("%s %s\n" % (url, error))

    def response_header(self, url, name, value):
        pass

    def done(self, url):
        pass

    def feed(self, url, data):
        sys.stdout.write(data)
        sys.stdout.flush()

    def close(self, url):
        pass

class HTTPHandler(asynchat.async_chat):
    def __init__(
        self,
        listener,
        username='',
        password=None,
        conn=None,
        map=None
        ):
        asynchat.async_chat.__init__(self, conn, map)
        self.listener = listener
        self.user_agent = 'Supervisor HTTP Client'
        self.buffer = ''
        self.set_terminator(CRLF)
        self.connected = 0
        self.part = self.status_line
        self.chunk_size = 0
        self.chunk_read = 0
        self.length_read = 0
        self.length = 0
        self.encoding = None
        self.username = username
        self.password = password
        self.url = None
        self.error_handled = False

    def get(self, serverurl, path=''):
        if self.url is not None:
            raise AssertionError('Already doing a get')
        self.url = serverurl + path
        scheme, host, path_ignored, params, query, fragment = urlparse.urlparse(
            self.url)
        if not scheme in ("http", "unix"):
            raise NotImplementedError
        self.host = host
        if ":" in host:
            hostname, port = host.split(":", 1)
            port = int(port)
        else:
            hostname = host
            port = 80

        self.path = path
        self.port = port

        if scheme == "http":
            ip = hostname
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connect((ip, self.port))
        elif scheme == "unix":
            socketname = serverurl[7:]
            self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.connect(socketname)

    def close(self):
        self.listener.close(self.url)
        self.connected = 0
        self.del_channel()
        self.socket.close()
        self.url = "CLOSED"

    def header(self, name, value):
        self.push('%s: %s' % (name, value))
        self.push(CRLF)

    def handle_error(self):
        if self.error_handled:
            return
        if 1 or self.connected:
            t,v,tb = sys.exc_info()
            msg = 'Cannot connect, error: %s (%s)' % (t, v)
            self.listener.error(self.url, msg)
            self.part = self.ignore
            self.close()
            self.error_handled = True
            del t
            del v
            del tb

    def handle_connect(self):
        self.connected = 1
        method = "GET"
        version = "HTTP/1.1"
        self.push("%s %s %s" % (method, self.path, version))
        self.push(CRLF)
        self.header("Host", self.host)

        self.header('Accept-Encoding', 'chunked')
        self.header('Accept', '*/*')
        self.header('User-agent', self.user_agent)
        if self.password:
            auth = '%s:%s' % (self.username, self.password)
            auth = as_string(encodestring(as_bytes(auth))).strip()
            self.header('Authorization', 'Basic %s' % auth)
        self.push(CRLF)
        self.push(CRLF)

    # To extract chunk size precisely in Python3,
    # we need to work on bytes string not unicode string.
    # Therefore, we will override this method of asynchat
    def handle_read(self):

        try:
            data = self.recv(self.ac_in_buffer_size)
        except socket.error:
            self.handle_error()
            return

        self.ac_in_buffer = as_bytes(self.ac_in_buffer) + as_bytes(data)

        while self.ac_in_buffer:
            lb = len(self.ac_in_buffer)
            terminator = self.get_terminator()
            if not terminator:
                self.collect_incoming_data(self.ac_in_buffer)
                self.ac_in_buffer = ''
            elif isinstance(terminator, int) or isinstance(terminator, long):
                n = terminator
                if lb < n:
                    self.collect_incoming_data(self.ac_in_buffer)
                    self.ac_in_buffer = ''
                    self.terminator= lb
                else:
                    self.collect_incoming_data(self.ac_in_buffer[:n])
                    self.ac_in_buffer = self.ac_in_buffer[n:]
                    self.terminator = 0
                    self.found_terminator()
            else:
                terminator_len = len(as_bytes(terminator))
                index = self.ac_in_buffer.find(as_bytes(terminator))
                if index !=1:
                    if index > 0:
                        self.collect_incoming_data(self.ac_in_buffer[:index])

                    self.ac_in_buffer = self.ac_in_buffer[index + terminator_len:]
                    self.found_terminator()
                else:
                    self.collect_incoming_data(self.ac_in_buffer)
                    self.ac_in_buffer = ''

    def feed(self, data):
        self.listener.feed(self.url, as_string(data))

    def collect_incoming_data(self, data):
        if PY3:
            self.buffer = as_string(self.buffer) + as_string(data)
        else:
            self.buffer = self.buffer + data
            
        if self.part==self.body:
            self.feed(self.buffer)
            self.buffer = ''

    def found_terminator(self):
        self.part()
        self.buffer = ''

    def ignore(self):
        self.buffer = ''

    def status_line(self):
        line = self.buffer

        version, status, reason = line.split(None, 2)
        status = int(status)
        if not version.startswith('HTTP/'):
            raise ValueError(line)

        self.listener.status(self.url, status)

        if status == 200:
            self.part = self.headers
        else:
            self.part = self.ignore
            msg = 'Cannot read, status code %s' % status
            self.listener.error(self.url, msg)
            self.close()
        return version, status, reason

    def headers(self):
        line = self.buffer
        if not line:
            if self.encoding=="chunked":
                self.part = self.chunked_size
            else:
                self.part = self.body
                self.set_terminator(self.length)
        else:
            name, value = line.split(":", 1)
            if name and value:
                name = name.lower()
                value = value.strip()
                if name=="transfer-encoding":
                    self.encoding = value
                elif name=="content-length":
                    self.length = int(value)
                self.response_header(name, value)

    def response_header(self, name, value):
        self.listener.response_header(self.url, name, value)

    def body(self):
        self.done()
        self.close()

    def done(self):
        self.listener.done(self.url)

    def chunked_size(self):
        line = self.buffer
        if not line:
            return
        chunk_size = int(line.split()[0], 16)
        if chunk_size==0:
            self.part = self.trailer
        else:
            self.set_terminator(chunk_size)
            self.part = self.chunked_body
        self.length += chunk_size

    def chunked_body(self):
        line = self.buffer
        self.set_terminator(CRLF)
        self.part = self.chunked_size
        self.feed(line)

    def trailer(self):
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.6.1
        # trailer        = *(entity-header CRLF)
        line = self.buffer
        if line==CRLF:
            self.done()
            self.close()
