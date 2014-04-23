import socket
import sys
import unittest

class ListenerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http_client import Listener
        return Listener

    def _makeOne(self):
        return self._getTargetClass()()

    def _makeFakeStdout(self):
        class Stdout(object):
            def __init__(self):
                self.things = []
                self.flushed = False
            def write(self, thing):
                self.things.append(thing)
            def flush(self):
                self.flushed = True
        stdout = Stdout()
        return stdout

    def test_status(self):
        inst = self._makeOne()
        self.assertEqual(inst.status(None, None), None)
        
    def test_error(self):
        inst = self._makeOne()
        try:
            old_stdout = sys.stdout
            stdout = self._makeFakeStdout()
            sys.stdout = stdout
            self.assertEqual(inst.error('url', 'error'), None)
            self.assertEqual(stdout.things, ['url error\n'])
        finally:
            sys.stdout = old_stdout
        
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
            stdout = self._makeFakeStdout()
            sys.stdout = stdout
            inst.feed('url', 'data')
            self.assertEqual(stdout.things, ['data'])
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
        inst.push = lambda val: pushed.append(val)
        inst.path = '/'
        inst.host = 'localhost'
        inst.handle_connect()
        self.assertTrue(inst.connected)
        self.assertEqual(
            pushed,
            ['GET / HTTP/1.1',
             '\r\n',
             'Host: localhost',
             '\r\n',
             'Accept-Encoding: chunked',
             '\r\n',
             'Accept: */*',
             '\r\n',
             'User-agent: Supervisor HTTP Client',
             '\r\n',
             '\r\n',
             '\r\n']
            )

    def test_handle_connect_with_password(self):
        inst = self._makeOne()
        pushed = []
        inst.push = lambda val: pushed.append(val)
        inst.path = '/'
        inst.host = 'localhost'
        inst.password = 'password'
        inst.username = 'username'
        inst.handle_connect()
        self.assertTrue(inst.connected)
        self.assertEqual(
            pushed,
             ['GET / HTTP/1.1',
              '\r\n',
              'Host: localhost',
              '\r\n',
              'Accept-Encoding: chunked',
              '\r\n',
              'Accept: */*',
              '\r\n',
              'User-agent: Supervisor HTTP Client',
              '\r\n',
              'Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=',
              '\r\n',
              '\r\n',
              '\r\n'],
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
        self.assertEqual(inst.buffer, '')

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
        self.assertEqual(inst.buffer, '')

    def test_ignore(self):
        inst = self._makeOne()
        inst.buffer = None
        inst.ignore()
        self.assertEqual(inst.buffer, '')

    def test_status_line_not_startswith_http(self):
        inst = self._makeOne()
        inst.buffer = 'NOTHTTP/1.0 200 OK'
        self.assertRaises(ValueError, inst.status_line)

    def test_status_line_200(self):
        inst = self._makeOne()
        inst.buffer = 'HTTP/1.0 200 OK'
        version, status, reason = inst.status_line()
        self.assertEqual(version, 'HTTP/1.0')
        self.assertEqual(status, 200)
        self.assertEqual(reason, 'OK')
        self.assertEqual(inst.part, inst.headers)

    def test_status_line_not_200(self):
        inst = self._makeOne()
        inst.buffer = 'HTTP/1.0 201 OK'
        closed = []
        inst.close = lambda: closed.append(True)
        version, status, reason = inst.status_line()
        self.assertEqual(version, 'HTTP/1.0')
        self.assertEqual(status, 201)
        self.assertEqual(reason, 'OK')
        self.assertEqual(inst.part, inst.ignore)
        self.assertEqual(
            inst.listener.error_msg,
            'Cannot read, status code 201'
            )
        self.assertEqual(closed, [True])
        
class DummyListener(object):
    closed = None
    error_url = None
    error_msg = None
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

class DummySocket(object):
    closed = False
    def close(self):
        self.closed = True
