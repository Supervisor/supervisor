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
        self.assertEqual(response[0][0], '1.0')
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

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

