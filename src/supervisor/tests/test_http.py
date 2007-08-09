import sys
import unittest

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyRequest
from supervisor.tests.base import DummyProcess

class LogtailHandlerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.http import logtail_handler
        return logtail_handler

    def _makeOne(self, supervisord):
        return self._getTargetClass()(supervisord)

    def test_handle_request_stdout_logfile_none(self):
        supervisor = DummySupervisor()
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', None)
        supervisor.processes = {'foo':DummyProcess(pconfig)}
        handler = self._makeOne(supervisor)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request_stdout_logfile_missing(self):
        supervisor = DummySupervisor()
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', 'it/is/missing')
        supervisor.processes = {'foo':DummyProcess(pconfig)}
        handler = self._makeOne(supervisor)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request(self):
        supervisor = DummySupervisor()
        import tempfile
        import os
        import stat
        f = tempfile.NamedTemporaryFile()
        t = f.name
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', stdout_logfile=t)
        supervisor.processes = {'foo':DummyProcess(pconfig)}
        handler = self._makeOne(supervisor)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, None)
        from medusa import http_date
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
        import tempfile
        from supervisor import http
        f = tempfile.NamedTemporaryFile()
        f.write('a' * 80)
        f.flush()
        t = f.name
        producer = self._makeOne(request, t, 80)
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


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
