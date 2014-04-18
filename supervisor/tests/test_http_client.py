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
