import base64
import os
import socket
import stat
import sys
import tempfile
import unittest

try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import PopulatedDummySupervisor
from supervisor.tests.base import DummyRPCInterfaceFactory
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyRequest

from supervisor.http import NOT_DONE_YET

class HandlerTests:
    def _makeOne(self, supervisord):
        return self._getTargetClass()(supervisord)

    def test_match(self):
        class DummyRequest:
            def __init__(self, uri):
                self.uri = uri
        supervisor = DummySupervisor()
        handler = self._makeOne(supervisor)
        self.assertEqual(handler.match(DummyRequest(handler.path)), True)

class LogtailHandlerTests(HandlerTests, unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import logtail_handler
        return logtail_handler

    def test_handle_request_stdout_logfile_none(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'process1', '/bin/process1', priority=1,
                               stdout_logfile='/tmp/process1.log')
        supervisord = PopulatedDummySupervisor(options, 'process1', pconfig)
        handler = self._makeOne(supervisord)
        request = DummyRequest('/logtail/process1', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request_stdout_logfile_missing(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', 'it/is/missing')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        handler = self._makeOne(supervisord)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request(self):
        f = tempfile.NamedTemporaryFile()
        t = f.name
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', stdout_logfile=t)
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        handler = self._makeOne(supervisord)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, None)
        from supervisor.medusa import http_date
        self.assertEqual(request.headers['Last-Modified'],
                         http_date.build_http_date(os.stat(t)[stat.ST_MTIME]))
        self.assertEqual(request.headers['Content-Type'], 'text/plain')
        self.assertEqual(len(request.producers), 1)
        self.assertEqual(request._done, True)

class MainLogTailHandlerTests(HandlerTests, unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import mainlogtail_handler
        return mainlogtail_handler

    def test_handle_request_stdout_logfile_none(self):
        supervisor = DummySupervisor()
        handler = self._makeOne(supervisor)
        request = DummyRequest('/mainlogtail', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request_stdout_logfile_missing(self):
        supervisor = DummySupervisor()
        supervisor.options.logfile = '/not/there'
        request = DummyRequest('/mainlogtail', None, None, None)
        handler = self._makeOne(supervisor)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request(self):
        supervisor = DummySupervisor()
        f = tempfile.NamedTemporaryFile()
        t = f.name
        supervisor.options.logfile = t
        handler = self._makeOne(supervisor)
        request = DummyRequest('/mainlogtail', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, None)
        from supervisor.medusa import http_date
        self.assertEqual(request.headers['Last-Modified'],
                         http_date.build_http_date(os.stat(t)[stat.ST_MTIME]))
        self.assertEqual(request.headers['Content-Type'], 'text/plain')
        self.assertEqual(len(request.producers), 1)
        self.assertEqual(request._done, True)


class TailFProducerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import tail_f_producer
        return tail_f_producer

    def _makeOne(self, request, filename, head):
        return self._getTargetClass()(request, filename, head)

    def test_handle_more(self):
        request = DummyRequest('/logtail/foo', None, None, None)
        from supervisor import http
        f = tempfile.NamedTemporaryFile()
        f.write('a' * 80)
        f.flush()
        producer = self._makeOne(request, f.name, 80)
        result = producer.more()
        self.assertEqual(result, 'a' * 80)
        f.write('w' * 100)
        f.flush()
        result = producer.more()
        self.assertEqual(result, 'w' * 100)
        result = producer.more()
        self.assertEqual(result, http.NOT_DONE_YET)
        f.truncate(0)
        f.flush()
        result = producer.more()
        self.assertEqual(result, '==> File truncated <==\n')

    def test_handle_more_follow(self):
        request = DummyRequest('/logtail/foo', None, None, None)
        f = tempfile.NamedTemporaryFile()
        f.write('a' * 80)
        f.flush()
        producer = self._makeOne(request, f.name, 80)
        result = producer.more()
        self.assertEqual(result, 'a' * 80)
        f.close()
        f2 = open(f.name, 'w')
        try:
            f2.write('b' * 80)
            f2.close()
            result = producer.more()
        finally:
            os.unlink(f2.name)
        self.assertEqual(result, 'b' * 80)

class DeferringChunkedProducerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import deferring_chunked_producer
        return deferring_chunked_producer

    def _makeOne(self, producer, footers=None):
        return self._getTargetClass()(producer, footers)

    def test_more_not_done_yet(self):
        wrapped = DummyProducer(NOT_DONE_YET)
        producer = self._makeOne(wrapped)
        self.assertEqual(producer.more(), NOT_DONE_YET)

    def test_more_string(self):
        wrapped = DummyProducer('hello')
        producer = self._makeOne(wrapped)
        self.assertEqual(producer.more(), '5\r\nhello\r\n')

    def test_more_nodata(self):
        wrapped = DummyProducer()
        producer = self._makeOne(wrapped, footers=['a', 'b'])
        self.assertEqual(producer.more(), '0\r\na\r\nb\r\n\r\n')

class DeferringCompositeProducerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import deferring_composite_producer
        return deferring_composite_producer

    def _makeOne(self, producers):
        return self._getTargetClass()(producers)

    def test_more_not_done_yet(self):
        wrapped = DummyProducer(NOT_DONE_YET)
        producer = self._makeOne([wrapped])
        self.assertEqual(producer.more(), NOT_DONE_YET)

    def test_more_string(self):
        wrapped1 = DummyProducer('hello')
        wrapped2 = DummyProducer('goodbye')
        producer = self._makeOne([wrapped1, wrapped2])
        self.assertEqual(producer.more(), 'hello')
        self.assertEqual(producer.more(), 'goodbye')
        self.assertEqual(producer.more(), '')

    def test_more_nodata(self):
        wrapped = DummyProducer()
        producer = self._makeOne([wrapped])
        self.assertEqual(producer.more(), '')

class DeferringGlobbingProducerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import deferring_globbing_producer
        return deferring_globbing_producer

    def _makeOne(self, producer, buffer_size=1<<16):
        return self._getTargetClass()(producer, buffer_size)

    def test_more_not_done_yet(self):
        wrapped = DummyProducer(NOT_DONE_YET)
        producer = self._makeOne(wrapped)
        self.assertEqual(producer.more(), NOT_DONE_YET)

    def test_more_string(self):
        wrapped = DummyProducer('hello', 'there', 'guy')
        producer = self._makeOne(wrapped, buffer_size=1)
        self.assertEqual(producer.more(), 'hello')

        wrapped = DummyProducer('hello', 'there', 'guy')
        producer = self._makeOne(wrapped, buffer_size=50)
        self.assertEqual(producer.more(), 'hellothereguy')

    def test_more_nodata(self):
        wrapped = DummyProducer()
        producer = self._makeOne(wrapped)
        self.assertEqual(producer.more(), '')

class DeferringHookedProducerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import deferring_hooked_producer
        return deferring_hooked_producer

    def _makeOne(self, producer, function):
        return self._getTargetClass()(producer, function)

    def test_more_not_done_yet(self):
        wrapped = DummyProducer(NOT_DONE_YET)
        producer = self._makeOne(wrapped, None)
        self.assertEqual(producer.more(), NOT_DONE_YET)

    def test_more_string(self):
        wrapped = DummyProducer('hello')
        L = []
        def callback(bytes):
            L.append(bytes)
        producer = self._makeOne(wrapped, callback)
        self.assertEqual(producer.more(), 'hello')
        self.assertEqual(L, [])
        producer.more()
        self.assertEqual(L, [5])

    def test_more_nodata(self):
        wrapped = DummyProducer()
        L = []
        def callback(bytes):
            L.append(bytes)
        producer = self._makeOne(wrapped, callback)
        self.assertEqual(producer.more(), '')
        self.assertEqual(L, [0])

class EncryptedDictionaryAuthorizedTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import encrypted_dictionary_authorizer
        return encrypted_dictionary_authorizer

    def _makeOne(self, dict):
        return self._getTargetClass()(dict)

    def test_authorize_baduser(self):
        authorizer = self._makeOne({})
        self.assertFalse(authorizer.authorize(('foo', 'bar')))

    def test_authorize_gooduser_badpassword(self):
        authorizer = self._makeOne({'foo':'password'})
        self.assertFalse(authorizer.authorize(('foo', 'bar')))

    def test_authorize_gooduser_goodpassword(self):
        authorizer = self._makeOne({'foo':'password'})
        self.assertTrue(authorizer.authorize(('foo', 'password')))

    def test_authorize_gooduser_goodpassword_with_colon(self):
        authorizer = self._makeOne({'foo':'pass:word'})
        self.assertTrue(authorizer.authorize(('foo', 'pass:word')))

    def test_authorize_gooduser_badpassword_sha(self):
        password = '{SHA}' + sha1('password').hexdigest()
        authorizer = self._makeOne({'foo':password})
        self.assertFalse(authorizer.authorize(('foo', 'bar')))

    def test_authorize_gooduser_goodpassword_sha(self):
        password = '{SHA}' + sha1('password').hexdigest()
        authorizer = self._makeOne({'foo':password})
        self.assertTrue(authorizer.authorize(('foo', 'password')))

class SupervisorAuthHandlerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import supervisor_auth_handler
        return supervisor_auth_handler

    def _makeOne(self, dict, handler):
        return self._getTargetClass()(dict, handler)

    def test_ctor(self):
        handler = self._makeOne({'a':1}, None)
        from supervisor.http import encrypted_dictionary_authorizer
        self.assertEqual(handler.authorizer.__class__,
                         encrypted_dictionary_authorizer)

    def test_handle_request_authorizes_good_credentials(self):
        request = DummyRequest('/logtail/process1', None, None, None)
        encoded = base64.b64encode("user:password")
        request.header = ["Authorization: Basic %s" % encoded]
        handler = DummyHandler()
        auth_handler = self._makeOne({'user':'password'}, handler)
        auth_handler.handle_request(request)
        self.assertTrue(handler.handled_request)

    def test_handle_request_authorizes_good_password_with_colon(self):
        request = DummyRequest('/logtail/process1', None, None, None)
        encoded = base64.b64encode("user:pass:word") # password contains colon
        request.header = ["Authorization: Basic %s" % encoded]
        handler = DummyHandler()
        auth_handler = self._makeOne({'user':'pass:word'}, handler)
        auth_handler.handle_request(request)
        self.assertTrue(handler.handled_request)

    def test_handle_request_does_not_authorize_bad_credentials(self):
        request = DummyRequest('/logtail/process1', None, None, None)
        encoded = base64.b64encode("wrong:wrong")
        request.header = ["Authorization: Basic %s" % encoded]
        handler = DummyHandler()
        auth_handler = self._makeOne({'user':'password'}, handler)
        auth_handler.handle_request(request)
        self.assertFalse(handler.handled_request)


class TopLevelFunctionTests(unittest.TestCase):
    def _make_http_servers(self, sconfigs):
        options = DummyOptions()
        options.server_configs = sconfigs
        options.rpcinterface_factories = [('dummy',DummyRPCInterfaceFactory,{})]
        supervisord = DummySupervisor()
        from supervisor.http import make_http_servers
        servers = make_http_servers(options, supervisord)
        try:
            for config, s in servers:
                s.close()
                socketfile = config.get('file')
                if socketfile is not None:
                    os.unlink(socketfile)
        finally:
            from asyncore import socket_map
            socket_map.clear()
        return servers

    def test_make_http_servers_noauth(self):
        socketfile = tempfile.mktemp()
        inet = {'family':socket.AF_INET, 'host':'localhost', 'port':17735,
                'username':None, 'password':None, 'section':'inet_http_server'}
        unix = {'family':socket.AF_UNIX, 'file':socketfile, 'chmod':0700,
                'chown':(-1, -1), 'username':None, 'password':None,
                'section':'unix_http_server'}
        servers = self._make_http_servers([inet, unix])
        self.assertEqual(len(servers), 2)

        inetdata = servers[0]
        self.assertEqual(inetdata[0], inet)
        server = inetdata[1]
        idents = [
            'Supervisor XML-RPC Handler',
            'Logtail HTTP Request Handler',
            'Main Logtail HTTP Request Handler',
            'Supervisor Web UI HTTP Request Handler',
            'Default HTTP Request Handler'
            ]
        self.assertEqual([x.IDENT for x in server.handlers], idents)

        unixdata = servers[1]
        self.assertEqual(unixdata[0], unix)
        server = unixdata[1]
        self.assertEqual([x.IDENT for x in server.handlers], idents)

    def test_make_http_servers_withauth(self):
        socketfile = tempfile.mktemp()
        inet = {'family':socket.AF_INET, 'host':'localhost', 'port':17736,
                'username':'username', 'password':'password',
                'section':'inet_http_server'}
        unix = {'family':socket.AF_UNIX, 'file':socketfile, 'chmod':0700,
                'chown':(-1, -1), 'username':'username', 'password':'password',
                'section':'unix_http_server'}
        servers = self._make_http_servers([inet, unix])
        self.assertEqual(len(servers), 2)
        from supervisor.http import supervisor_auth_handler
        for config, server in servers:
            for handler in server.handlers:
                self.assertTrue(isinstance(handler, supervisor_auth_handler),
                                handler)

class DummyHandler:
    def __init__(self):
        self.handled_request = False

    def handle_request(self, request):
        self.handled_request = True

class DummyProducer:
    def __init__(self, *data):
        self.data = list(data)

    def more(self):
        if self.data:
            return self.data.pop(0)
        else:
            return ''

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
