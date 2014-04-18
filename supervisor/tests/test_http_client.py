import io
import sys
import unittest

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
            old_stdout = sys.stdout
            f = io.StringIO()
            sys.stdout = f
            self.assertEqual(inst.error('url', 'error'), None)
            self.assertEqual(f.getvalue(), 'url error\n')
        finally:
            sys.stdout = old_stdout
        
    def test_response_header(self):
        inst = self._makeOne()
        self.assertEqual(inst.response_header(None, None, None), None)

    def test_done(self):
        inst = self._makeOne()
        self.assertEqual(inst.done(None), None)

    def test_feed(self):
        from supervisor.compat import as_string
        inst = self._makeOne()
        try:
            old_stdout = sys.stdout
            f = io.StringIO()
            sys.stdout = f
            inst.feed(as_string('url'), as_string('data'))
            self.assertEqual(f.getvalue(), 'data')
        finally:
            sys.stdout = old_stdout

    def test_close(self):
        inst = self._makeOne()
        self.assertEqual(inst.close(None), None)
