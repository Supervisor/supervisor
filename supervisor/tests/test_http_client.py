import socket
import sys
import unittest

from supervisor.compat import as_bytes
from supervisor.compat import StringIO

class ListenerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http_client import Listener
        return Listener

    def _makeOne(self):
        return self._getTargetClass()()

    def test_status(self):
        inst = self._makeOne()
        self.assertEqual(inst.status(None, None), None)

    def test_error(self):
        inst = self._makeOne()
        try:
            old_stderr = sys.stderr
            stderr = StringIO()
            sys.stderr = stderr
            self.assertEqual(inst.error('url', 'error'), None)
            self.assertEqual(stderr.getvalue(), 'url error\n')
        finally:
            sys.stderr = old_stderr

    def test_response_header(self):
        inst = self._makeOne()
        self.assertEqual(inst.response_header(None, None, None), None)

    def test_done(self):
        inst = self._makeOne()
        self.assertEqual(inst.done(None), None)

    def test_feed(self):
        inst = self._makeOne()
        try:
            old_stdout = sys.stdout
            stdout = StringIO()
            sys.stdout = stdout
            inst.feed('url', 'data')
            self.assertEqual(stdout.getvalue(), 'data')
        finally:
            sys.stdout = old_stdout

    def test_close(self):
        inst = self._makeOne()
        self.assertEqual(inst.close(None), None)

class HTTPHandlerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http_client import HTTPHandler
        return HTTPHandler

    def _makeOne(self, listener=None, username='', password=None):
        if listener is None:
            listener = self._makeListener()
        socket_map = {}
        return self._getTargetClass()(
            listener,
            username,
            password,
            map=socket_map,
            )

    def _makeListener(self):
        listener = DummyListener()
        return listener

    def test_get_url_not_None(self):
        inst = self._makeOne()
        inst.url = 'abc'
        self.assertRaises(AssertionError, inst.get, 'abc')

    def test_get_bad_scheme(self):
        inst = self._makeOne()
        self.assertRaises(
            NotImplementedError,
            inst.get,
            'nothttp://localhost',
            '/abc'
            )

    def test_get_implied_port_80(self):
        inst = self._makeOne()
        sockets = []
        connects = []
        inst.create_socket = lambda *arg: sockets.append(arg)
        inst.connect = lambda tup: connects.append(tup)
        inst.get('http://localhost', '/abc/def')
        self.assertEqual(inst.port, 80)
        self.assertEqual(sockets, [(socket.AF_INET, socket.SOCK_STREAM)])
        self.assertEqual(connects, [('localhost', 80)])

    def test_get_explicit_port(self):
        inst = self._makeOne()
        sockets = []
        connects = []
        inst.create_socket = lambda *arg: sockets.append(arg)
        inst.connect = lambda tup: connects.append(tup)
        inst.get('http://localhost:8080', '/abc/def')
        self.assertEqual(inst.port, 8080)
        self.assertEqual(sockets, [(socket.AF_INET, socket.SOCK_STREAM)])
        self.assertEqual(connects, [('localhost', 8080)])

    def test_get_explicit_unix_domain_socket(self):
        inst = self._makeOne()
        sockets = []
        connects = []
        inst.create_socket = lambda *arg: sockets.append(arg)
        inst.connect = lambda tup: connects.append(tup)
        inst.get('unix:///a/b/c', '')
        self.assertEqual(sockets, [(socket.AF_UNIX, socket.SOCK_STREAM)])
        self.assertEqual(connects, ['/a/b/c'])

    def test_close(self):
        inst = self._makeOne()
        dels = []
        inst.del_channel = lambda: dels.append(True)
        inst.socket = DummySocket()
        inst.close()
        self.assertEqual(inst.listener.closed, None)
        self.assertEqual(inst.connected, 0)
        self.assertEqual(dels, [True])
        self.assertTrue(inst.socket.closed)
        self.assertEqual(inst.url, 'CLOSED')

    def test_header(self):
        from supervisor.http_client import CRLF
        inst = self._makeOne()
        pushes = []
        inst.push = lambda val: pushes.append(val)
        inst.header('name', 'val')
        self.assertEqual(pushes, ['name: val', CRLF])

    def test_handle_error_already_handled(self):
        inst = self._makeOne()
        inst.error_handled = True
        self.assertEqual(inst.handle_error(), None)

    def test_handle_error(self):
        inst = self._makeOne()
        closed = []
        inst.close = lambda: closed.append(True)
        inst.url = 'foo'
        self.assertEqual(inst.handle_error(), None)
        self.assertEqual(inst.listener.error_url, 'foo')
        self.assertEqual(
            inst.listener.error_msg,
            'Cannot connect, error: None (None)',
            )
        self.assertEqual(closed, [True])
        self.assertTrue(inst.error_handled)

    def test_handle_connect_no_password(self):
        inst = self._makeOne()
        pushed = []
        inst.push = lambda val: pushed.append(as_bytes(val))
        inst.path = '/'
        inst.host = 'localhost'
        inst.handle_connect()
        self.assertTrue(inst.connected)
        self.assertEqual(
            pushed,
            [b'GET / HTTP/1.1',
             b'\r\n',
             b'Host: localhost',
             b'\r\n',
             b'Accept-Encoding: chunked',
             b'\r\n',
             b'Accept: */*',
             b'\r\n',
             b'User-agent: Supervisor HTTP Client',
             b'\r\n',
             b'\r\n',
             b'\r\n']
            )

    def test_handle_connect_with_password(self):
        inst = self._makeOne()
        pushed = []
        inst.push = lambda val: pushed.append(as_bytes(val))
        inst.path = '/'
        inst.host = 'localhost'
        inst.password = 'password'
        inst.username = 'username'
        inst.handle_connect()
        self.assertTrue(inst.connected)
        self.assertEqual(
            pushed,
             [b'GET / HTTP/1.1',
              b'\r\n',
              b'Host: localhost',
              b'\r\n',
              b'Accept-Encoding: chunked',
              b'\r\n',
              b'Accept: */*',
              b'\r\n',
              b'User-agent: Supervisor HTTP Client',
              b'\r\n',
              b'Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=',
              b'\r\n',
              b'\r\n',
              b'\r\n'],
            )

    def test_feed(self):
        inst = self._makeOne()
        inst.feed('data')
        self.assertEqual(inst.listener.fed_data, ['data'])

    def test_collect_incoming_data_part_is_body(self):
        inst = self._makeOne()
        inst.part = inst.body
        inst.buffer = 'abc'
        inst.collect_incoming_data('foo')
        self.assertEqual(inst.listener.fed_data, ['abcfoo'])
        self.assertEqual(inst.buffer, b'')

    def test_collect_incoming_data_part_is_not_body(self):
        inst = self._makeOne()
        inst.part = None
        inst.buffer = 'abc'
        inst.collect_incoming_data('foo')
        self.assertEqual(inst.listener.fed_data, [])
        self.assertEqual(inst.buffer, 'abcfoo')

    def test_found_terminator(self):
        inst = self._makeOne()
        parted = []
        inst.part = lambda: parted.append(True)
        inst.buffer = None
        inst.found_terminator()
        self.assertEqual(parted, [True])
        self.assertEqual(inst.buffer, b'')

    def test_ignore(self):
        inst = self._makeOne()
        inst.buffer = None
        inst.ignore()
        self.assertEqual(inst.buffer, b'')

    def test_status_line_not_startswith_http(self):
        inst = self._makeOne()
        inst.buffer = b'NOTHTTP/1.0 200 OK'
        self.assertRaises(ValueError, inst.status_line)

    def test_status_line_200(self):
        inst = self._makeOne()
        inst.buffer = b'HTTP/1.0 200 OK'
        version, status, reason = inst.status_line()
        self.assertEqual(version, b'HTTP/1.0')
        self.assertEqual(status, 200)
        self.assertEqual(reason, b'OK')
        self.assertEqual(inst.part, inst.headers)

    def test_status_line_not_200(self):
        inst = self._makeOne()
        inst.buffer = b'HTTP/1.0 201 OK'
        closed = []
        inst.close = lambda: closed.append(True)
        version, status, reason = inst.status_line()
        self.assertEqual(version, b'HTTP/1.0')
        self.assertEqual(status, 201)
        self.assertEqual(reason, b'OK')
        self.assertEqual(inst.part, inst.ignore)
        self.assertEqual(
            inst.listener.error_msg,
            'Cannot read, status code 201'
            )
        self.assertEqual(closed, [True])

    def test_headers_empty_line_nonchunked(self):
        inst = self._makeOne()
        inst.buffer = b''
        inst.encoding = b'not chunked'
        inst.length = 3
        terms = []
        inst.set_terminator = lambda L: terms.append(L)
        inst.headers()
        self.assertEqual(inst.part, inst.body)
        self.assertEqual(terms, [3])

    def test_headers_empty_line_chunked(self):
        inst = self._makeOne()
        inst.buffer = b''
        inst.encoding = b'chunked'
        inst.headers()
        self.assertEqual(inst.part, inst.chunked_size)

    def test_headers_nonempty_line_no_name_no_value(self):
        inst = self._makeOne()
        inst.buffer = b':'
        self.assertEqual(inst.headers(), None)

    def test_headers_nonempty_line_transfer_encoding(self):
        inst = self._makeOne()
        inst.buffer = b'Transfer-Encoding: chunked'
        responses = []
        inst.response_header = lambda n, v: responses.append((n, v))
        inst.headers()
        self.assertEqual(inst.encoding, b'chunked')
        self.assertEqual(responses, [(b'transfer-encoding', b'chunked')])

    def test_headers_nonempty_line_content_length(self):
        inst = self._makeOne()
        inst.buffer = b'Content-Length: 3'
        responses = []
        inst.response_header = lambda n, v: responses.append((n, v))
        inst.headers()
        self.assertEqual(inst.length, 3)
        self.assertEqual(responses, [(b'content-length', b'3')])

    def test_headers_nonempty_line_arbitrary(self):
        inst = self._makeOne()
        inst.buffer = b'X-Test: abc'
        responses = []
        inst.response_header = lambda n, v: responses.append((n, v))
        inst.headers()
        self.assertEqual(responses, [(b'x-test', b'abc')])

    def test_response_header(self):
        inst = self._makeOne()
        inst.response_header(b'a', b'b')
        self.assertEqual(inst.listener.response_header_name, b'a')
        self.assertEqual(inst.listener.response_header_value, b'b')

    def test_body(self):
        inst = self._makeOne()
        closed = []
        inst.close = lambda: closed.append(True)
        inst.body()
        self.assertEqual(closed, [True])
        self.assertTrue(inst.listener.done)

    def test_done(self):
        inst = self._makeOne()
        inst.done()
        self.assertTrue(inst.listener.done)

    def test_chunked_size_empty_line(self):
        inst = self._makeOne()
        inst.buffer = b''
        inst.length = 1
        self.assertEqual(inst.chunked_size(), None)
        self.assertEqual(inst.length, 1)

    def test_chunked_size_zero_size(self):
        inst = self._makeOne()
        inst.buffer = b'0'
        inst.length = 1
        self.assertEqual(inst.chunked_size(), None)
        self.assertEqual(inst.length, 1)
        self.assertEqual(inst.part, inst.trailer)

    def test_chunked_size_nonzero_size(self):
        inst = self._makeOne()
        inst.buffer = b'10'
        inst.length = 1
        terms = []
        inst.set_terminator = lambda sz: terms.append(sz)
        self.assertEqual(inst.chunked_size(), None)
        self.assertEqual(inst.part, inst.chunked_body)
        self.assertEqual(inst.length, 17)
        self.assertEqual(terms, [16])

    def test_chunked_body(self):
        from supervisor.http_client import CRLF
        inst = self._makeOne()
        inst.buffer = b'buffer'
        terms = []
        lines = []
        inst.set_terminator = lambda v: terms.append(v)
        inst.feed = lambda v: lines.append(v)
        inst.chunked_body()
        self.assertEqual(terms, [CRLF])
        self.assertEqual(lines, [b'buffer'])
        self.assertEqual(inst.part, inst.chunked_size)

    def test_trailer_line_not_crlf(self):
        inst = self._makeOne()
        inst.buffer = b''
        self.assertEqual(inst.trailer(), None)

    def test_trailer_line_crlf(self):
        from supervisor.http_client import CRLF
        inst = self._makeOne()
        inst.buffer = CRLF
        dones = []
        closes = []
        inst.done = lambda: dones.append(True)
        inst.close = lambda: closes.append(True)
        self.assertEqual(inst.trailer(), None)
        self.assertEqual(dones, [True])
        self.assertEqual(closes, [True])

class DummyListener(object):
    closed = None
    error_url = None
    error_msg = None
    done = False
    def __init__(self):
        self.fed_data = []

    def close(self, url):
        self.closed = url

    def error(self, url, msg):
        self.error_url = url
        self.error_msg = msg

    def feed(self, url, data):
        self.fed_data.append(data)

    def status(self, url, int):
        self.status_url = url
        self.status_int = int

    def response_header(self, url, name, value):
        self.response_header_name = name
        self.response_header_value = value

    def done(self, url):
        self.done = True

class DummySocket(object):
    closed = False
    def close(self):
        self.closed = True
