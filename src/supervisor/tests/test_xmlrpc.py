import sys
import unittest

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyRequest
from supervisor.tests.base import DummySupervisorRPCNamespace
from supervisor.tests.base import _NOW

class XMLRPCMarshallingTests(unittest.TestCase):
    def test_xmlrpc_marshal(self):
        import xmlrpclib
        from supervisor import xmlrpc
        data = xmlrpc.xmlrpc_marshal(1)
        self.assertEqual(data, xmlrpclib.dumps((1,), methodresponse=True))
        fault = xmlrpclib.Fault(1, 'foo')
        data = xmlrpc.xmlrpc_marshal(fault)
        self.assertEqual(data, xmlrpclib.dumps(fault))

class XMLRPCHandlerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.xmlrpc import supervisor_xmlrpc_handler
        return supervisor_xmlrpc_handler
    
    def _makeOne(self, supervisord, subinterfaces):
        return self._getTargetClass()(supervisord, subinterfaces)

    def test_ctor(self):
        supervisor = DummySupervisor()
        subinterfaces = [('supervisor', DummySupervisorRPCNamespace())]
        handler = self._makeOne(supervisor, subinterfaces)
        self.assertEqual(handler.supervisord, supervisor)
        from supervisor.xmlrpc import RootRPCInterface
        self.assertEqual(handler.rpcinterface.__class__, RootRPCInterface)

    def test_match(self):
        class DummyRequest:
            def __init__(self, uri):
                self.uri = uri
        supervisor = DummySupervisor()
        subinterfaces = [('supervisor', DummySupervisorRPCNamespace())]
        handler = self._makeOne(supervisor, subinterfaces)
        self.assertEqual(handler.match(DummyRequest('/RPC2')), True)
        self.assertEqual(handler.match(DummyRequest('/nope')), False)

    def test_continue_request_nosuchmethod(self):
        supervisor = DummySupervisor()
        subinterfaces = [('supervisor', DummySupervisorRPCNamespace())]
        handler = self._makeOne(supervisor, subinterfaces)
        import xmlrpclib
        data = xmlrpclib.dumps(('a', 'b'), 'supervisor.noSuchMethod')
        request = DummyRequest('/what/ever', None, None, None)
        handler.continue_request(data, request)
        logdata = supervisor.options.logger.data
        self.assertEqual(len(logdata), 2)
        self.assertEqual(logdata[0],
                         u'XML-RPC method called: supervisor.noSuchMethod()')
        self.assertEqual(logdata[1],
           (u'XML-RPC method supervisor.noSuchMethod() returned fault: '
            '[1] UNKNOWN_METHOD'))
        self.assertEqual(len(request.producers), 1)
        xml_response = request.producers[0]
        self.assertRaises(xmlrpclib.Fault, xmlrpclib.loads, xml_response)

    def test_continue_request_methodsuccess(self):
        supervisor = DummySupervisor()
        subinterfaces = [('supervisor', DummySupervisorRPCNamespace())]
        handler = self._makeOne(supervisor, subinterfaces)
        import xmlrpclib
        data = xmlrpclib.dumps((), 'supervisor.getAPIVersion')
        request = DummyRequest('/what/ever', None, None, None)
        handler.continue_request(data, request)
        logdata = supervisor.options.logger.data
        self.assertEqual(len(logdata), 2)
        self.assertEqual(logdata[0],
               u'XML-RPC method called: supervisor.getAPIVersion()')
        self.assertEqual(logdata[1],
            u'XML-RPC method supervisor.getAPIVersion() returned successfully')
        self.assertEqual(len(request.producers), 1)
        xml_response = request.producers[0]
        response = xmlrpclib.loads(xml_response)
        self.assertEqual(response[0][0], '3.0')
        self.assertEqual(request._done, True)
        self.assertEqual(request.headers['Content-Type'], 'text/xml')
        self.assertEqual(request.headers['Content-Length'], len(xml_response))

    def test_continue_request_500(self):
        supervisor = DummySupervisor()
        subinterfaces = [('supervisor', DummySupervisorRPCNamespace())]
        handler = self._makeOne(supervisor, subinterfaces)
        import xmlrpclib
        data = xmlrpclib.dumps((), 'supervisor.raiseError')
        request = DummyRequest('/what/ever', None, None, None)
        handler.continue_request(data, request)
        logdata = supervisor.options.logger.data
        self.assertEqual(len(logdata), 2)
        self.assertEqual(logdata[0],
               u'XML-RPC method called: supervisor.raiseError()')
        self.failUnless(logdata[1].startswith('Traceback'))
        self.failUnless(logdata[1].endswith('ValueError: error\n'))
        self.assertEqual(len(request.producers), 0)
        self.assertEqual(request._error, 500)

class TraverseTests(unittest.TestCase):
    def test_underscore(self):
        from supervisor import xmlrpc
        self.assertRaises(xmlrpc.RPCError, xmlrpc.traverse, None, '_', None)

    def test_notfound(self):
        from supervisor import xmlrpc
        self.assertRaises(xmlrpc.RPCError, xmlrpc.traverse, None, 'foo', None)

    def test_badparams(self):
        from supervisor import xmlrpc
        self.assertRaises(xmlrpc.RPCError, xmlrpc.traverse, self,
                          'test_badparams', (1, 2, 3))

    def test_success(self):
        from supervisor import xmlrpc
        L = []
        class Dummy:
            def foo(self, a):
                L.append(a)
        dummy = Dummy()
        xmlrpc.traverse(dummy, 'foo', [1])
        self.assertEqual(L, [1])

class TesstSupervisorTransport(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.xmlrpc import SupervisorTransport
        return SupervisorTransport

    def _makeOne(self, *arg, **kw):
        return self._getTargetClass()(*arg, **kw)

    def test_ctor_unix(self):
        from supervisor import xmlrpc
        transport = self._makeOne('user', 'pass', 'unix:///foo/bar')
        conn = transport._get_connection()
        self.failUnless(isinstance(conn, xmlrpc.UnixStreamHTTPConnection))
        self.assertEqual(conn.host, '/foo/bar')

    def test__get_connection_http_9001(self):
        from supervisor import xmlrpc
        import httplib
        transport = self._makeOne('user', 'pass', 'http://127.0.0.1:9001/')
        conn = transport._get_connection()
        self.failUnless(isinstance(conn, httplib.HTTPConnection))
        self.assertEqual(conn.host, '127.0.0.1')
        self.assertEqual(conn.port, 9001)

    def test__get_connection_http_80(self):
        from supervisor import xmlrpc
        import httplib
        transport = self._makeOne('user', 'pass', 'http://127.0.0.1/')
        conn = transport._get_connection()
        self.failUnless(isinstance(conn, httplib.HTTPConnection))
        self.assertEqual(conn.host, '127.0.0.1')
        self.assertEqual(conn.port, 80)

    def test_request_non_200_response(self):
        import xmlrpclib
        transport = self._makeOne('user', 'pass', 'http://127.0.0.1/')
        dummy_conn = DummyConnection(400, '')
        def getconn():
            return dummy_conn
        transport._get_connection = getconn
        self.assertRaises(xmlrpclib.ProtocolError,
                          transport.request, 'localhost', '/', '')
        self.assertEqual(transport.connection, None)
        self.assertEqual(dummy_conn.closed, True)

    def test_request_400_response(self):
        import xmlrpclib
        transport = self._makeOne('user', 'pass', 'http://127.0.0.1/')
        dummy_conn = DummyConnection(400, '')
        def getconn():
            return dummy_conn
        transport._get_connection = getconn
        self.assertRaises(xmlrpclib.ProtocolError,
                          transport.request, 'localhost', '/', '')
        self.assertEqual(transport.connection, None)
        self.assertEqual(dummy_conn.closed, True)
        self.assertEqual(dummy_conn.requestargs[0], 'POST')
        self.assertEqual(dummy_conn.requestargs[1], '/')
        self.assertEqual(dummy_conn.requestargs[2], '')
        self.assertEqual(dummy_conn.requestargs[3]['Content-Length'], '0')
        self.assertEqual(dummy_conn.requestargs[3]['Content-Type'], 'text/xml')
        self.assertEqual(dummy_conn.requestargs[3]['Authorization'],
                         'Basic dXNlcjpwYXNz')
        self.assertEqual(dummy_conn.requestargs[3]['Accept'], 'text/xml')

    def test_request_200_response(self):
        import xmlrpclib
        transport = self._makeOne('user', 'pass', 'http://127.0.0.1/')
        response = """<?xml version="1.0"?>
        <methodResponse>
        <params>
        <param>
        <value><string>South Dakota</string></value>
        </param>
        </params>
        </methodResponse>"""
        dummy_conn = DummyConnection(200, response)
        def getconn():
            return dummy_conn
        transport._get_connection = getconn
        result = transport.request('localhost', '/', '')
        self.assertEqual(transport.connection, dummy_conn)
        self.assertEqual(dummy_conn.closed, False)
        self.assertEqual(dummy_conn.requestargs[0], 'POST')
        self.assertEqual(dummy_conn.requestargs[1], '/')
        self.assertEqual(dummy_conn.requestargs[2], '')
        self.assertEqual(dummy_conn.requestargs[3]['Content-Length'], '0')
        self.assertEqual(dummy_conn.requestargs[3]['Content-Type'], 'text/xml')
        self.assertEqual(dummy_conn.requestargs[3]['Authorization'],
                         'Basic dXNlcjpwYXNz')
        self.assertEqual(dummy_conn.requestargs[3]['Accept'], 'text/xml')
        self.assertEqual(result, ('South Dakota',))

    def test_works_with_py25(self):
        instance = self._makeOne('username', 'password', 'http://127.0.0.1')
        # the test is just to insure that this method can be called; failure
        # would be an AttributeError for _use_datetime under Python 2.5
        parser, unmarshaller = instance.getparser() # this uses _use_datetime

class DummyResponse:
    def __init__(self, status=200, body='', reason='reason'):
        self.status = status
        self.body = body
        self.reason = reason

    def read(self):
        return self.body

class DummyConnection:
    closed = False
    def __init__(self, status=200, body='', reason='reason'):
        self.response = DummyResponse(status, body, reason)

    def getresponse(self):
        return self.response
        
    def request(self, *arg, **kw):
        self.requestargs = arg
        self.requestkw = kw

    def close(self):
        self.closed = True

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

