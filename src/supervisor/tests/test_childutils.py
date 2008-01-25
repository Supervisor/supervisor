import sys
import unittest
from StringIO import StringIO

class ChildUtilsTests(unittest.TestCase):
    def test_getRPCInterface(self):
        from supervisor.childutils import getRPCInterface
        rpc = getRPCInterface({'SUPERVISOR_SERVER_URL':'http://localhost:9001'})
        # we can't really test this thing; its a magic object

    def test_getRPCTransport_no_uname_pass(self):
        from supervisor.childutils import getRPCTransport
        t = getRPCTransport({'SUPERVISOR_SERVER_URL':'http://localhost:9001'})
        self.assertEqual(t.username, '')
        self.assertEqual(t.password, '')
        self.assertEqual(t.serverurl, 'http://localhost:9001')

    def test_getRPCTransport_with_uname_pass(self):
        from supervisor.childutils import getRPCTransport
        env = {'SUPERVISOR_SERVER_URL':'http://localhost:9001',
               'SUPERVISOR_USERNAME':'chrism',
               'SUPERVISOR_PASSWORD':'abc123'}
        t = getRPCTransport(env)
        self.assertEqual(t.username, 'chrism')
        self.assertEqual(t.password, 'abc123')
        self.assertEqual(t.serverurl, 'http://localhost:9001')

    def test_get_headers(self):
        from supervisor.childutils import get_headers
        line = 'a:1 b:2'
        result = get_headers(line)
        self.assertEqual(result, {'a':'1', 'b':'2'})

    def test_eventdata(self):
        from supervisor.childutils import eventdata
        payload = 'a:1 b:2\nthedata'
        headers, data = eventdata(payload)
        self.assertEqual(headers, {'a':'1', 'b':'2'})
        self.assertEqual(data, 'thedata')
        
class TestProcessCommunicationsProtocol(unittest.TestCase):
    def test_send(self):
        from supervisor.childutils import pcomm
        stdout = StringIO()
        pcomm.send('hello', stdout)
        from supervisor.events import ProcessCommunicationEvent
        begin = ProcessCommunicationEvent.BEGIN_TOKEN
        end = ProcessCommunicationEvent.END_TOKEN
        self.assertEqual(stdout.getvalue(), '%s%s%s' % (begin, 'hello', end))

    def test_stdout(self):
        from supervisor.childutils import pcomm
        old = sys.stdout
        try:
            io = sys.stdout = StringIO()
            pcomm.stdout('hello')
            from supervisor.events import ProcessCommunicationEvent
            begin = ProcessCommunicationEvent.BEGIN_TOKEN
            end = ProcessCommunicationEvent.END_TOKEN
            self.assertEqual(io.getvalue(), '%s%s%s' % (begin, 'hello', end))
        finally:
            sys.stdout = old
        
    def test_stderr(self):
        from supervisor.childutils import pcomm
        old = sys.stderr
        try:
            io = sys.stderr = StringIO()
            pcomm.stderr('hello')
            from supervisor.events import ProcessCommunicationEvent
            begin = ProcessCommunicationEvent.BEGIN_TOKEN
            end = ProcessCommunicationEvent.END_TOKEN
            self.assertEqual(io.getvalue(), '%s%s%s' % (begin, 'hello', end))
        finally:
            sys.stderr = old

class TestEventListenerProtocol(unittest.TestCase):
    def test_wait(self):
        from supervisor.childutils import listener
        from supervisor.dispatchers import PEventListenerDispatcher
        token = PEventListenerDispatcher.READY_FOR_EVENTS_TOKEN
        class Dummy:
            def readline(self):
                return 'len:5'
            def read(self, *ignored):
                return 'hello'
        stdin = Dummy()
        headers, payload = listener.wait(stdin)
        self.assertEqual(headers, {'len':'5'})
        self.assertEqual(payload, 'hello')

    def test_token(self):
        from supervisor.childutils import listener
        from supervisor.dispatchers import PEventListenerDispatcher
        token = PEventListenerDispatcher.READY_FOR_EVENTS_TOKEN
        stdout = StringIO()
        listener.ready(stdout)
        self.assertEqual(stdout.getvalue(), token)

    def test_ok(self):
        from supervisor.childutils import listener
        from supervisor.dispatchers import PEventListenerDispatcher
        begin = PEventListenerDispatcher.RESULT_TOKEN_START
        stdout = StringIO()
        listener.ok(stdout)
        self.assertEqual(stdout.getvalue(), begin + '2\nOK')

    def test_fail(self):
        from supervisor.childutils import listener
        from supervisor.dispatchers import PEventListenerDispatcher
        begin = PEventListenerDispatcher.RESULT_TOKEN_START
        stdout = StringIO()
        listener.fail(stdout)
        self.assertEqual(stdout.getvalue(), begin + '4\nFAIL')

    def test_send(self):
        from supervisor.childutils import listener
        from supervisor.dispatchers import PEventListenerDispatcher
        begin = PEventListenerDispatcher.RESULT_TOKEN_START
        stdout = StringIO()
        msg = 'the body data ya fool\n'
        listener.send(msg, stdout)
        expected = '%s%s\n%s' % (begin, len(msg), msg)
        self.assertEqual(stdout.getvalue(), expected)
        

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
