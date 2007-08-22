import sys
import unittest
import tempfile
import shutil
import os
import logging

from supervisor.tests.base import DummyStream

class HandlerTests:
    handler = None
    def setUp(self):
        self.basedir = tempfile.mkdtemp()
        self.filename = os.path.join(self.basedir, 'thelog')

    def tearDown(self):
        try:
            shutil.rmtree(self.basedir)
        except OSError:
            pass
        if self.handler:
            # Behold, the logging module.  Since it registers an
            # exitfunc at import time that tries to call close methods
            # on handlers that are registered in a (not just one, but
            # *two*, and private!) module globals at handler
            # construction time, we have to clean up here so it doesnt
            # spew tracebacks to stderr at shutdown (at least for 2.4
            # and 2.5).  We can't prevent it the exit handler it
            # registers from shitting itself at shutdown by using the
            # logging API because when its exitfunc is run, at least
            # in my test rig, it's run after sys.modules have been
            # cleared, so there's no way to do anything meaningful in
            # the handlers' close methods.  I am consoled only by the
            # fact that this a complete waste of time for everyone who
            # uses the logging module and not just me.  There is *no
            # fucking way* that importing a stdlib module should have
            # the side effect of registering an exitfunc.  Can you
            # tell that this annoys me?
            if hasattr(logging, '_handlerList'): # 2.3.5 doesnt have it
                hl = []
                for handler in logging._handlerList:
                    if handler is not self.handler:
                        hl.append(handler)
                logging._handlerList = hl
            try:
                del logging._handlers[self.handler]
            except KeyError:
                pass
            self.handler = None

    def _makeOne(self, *arg, **kw):
        klass = self._getTargetClass()
        self.handler = klass(*arg, **kw)
        return self.handler

    def _makeLogRecord(self, msg):
        record = logging.LogRecord('name',
                                   level=logging.INFO,
                                   pathname='pathname',
                                   lineno=5,
                                   msg=msg,
                                   args=(),
                                   exc_info=None)
        return record

class FileHandlerTests(HandlerTests, unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.loggers import FileHandler
        return FileHandler

    def test_ctor(self):
        handler = self._makeOne(self.filename)
        self.assertTrue(os.path.exists(self.filename), self.filename)
        self.assertEqual(handler.mode, 'a')
        self.assertEqual(handler.baseFilename, self.filename)
        self.assertEqual(handler.stream.name, self.filename)

    def test_close(self):
        handler = self._makeOne(self.filename)
        handler.stream = DummyStream()
        handler.close()
        self.assertEqual(handler.stream.closed, True)
        
    def test_close_raises(self):
        handler = self._makeOne(self.filename)
        handler.stream = DummyStream(OSError)
        self.assertRaises(OSError, handler.close)
        self.assertEqual(handler.stream.closed, False)

    def test_reopen(self):
        handler = self._makeOne(self.filename)
        stream = DummyStream()
        handler.stream = stream
        handler.reopen()
        self.assertEqual(stream.closed, True)
        self.assertEqual(handler.stream.name, self.filename)

    def test_reopen_raises(self):
        handler = self._makeOne(self.filename)
        stream = DummyStream()
        handler.stream = stream
        handler.baseFilename = os.path.join(self.basedir, 'notthere', 'a.log')
        self.assertRaises(IOError, handler.reopen)
        self.assertEqual(stream.closed, True)

    def test_remove_exists(self):
        handler = self._makeOne(self.filename)
        self.assertTrue(os.path.exists(self.filename), self.filename)
        handler.remove()
        self.assertFalse(os.path.exists(self.filename), self.filename)

    def test_remove_doesntexist(self):
        handler = self._makeOne(self.filename)
        os.remove(self.filename)
        self.assertFalse(os.path.exists(self.filename), self.filename)
        handler.remove() # should not raise
        self.assertFalse(os.path.exists(self.filename), self.filename)
        
    def test_remove_raises(self):
        handler = self._makeOne(self.filename)
        os.remove(self.filename)
        os.mkdir(self.filename)
        self.assertTrue(os.path.exists(self.filename), self.filename)
        self.assertRaises(OSError, handler.remove)

class RawFileHandlerTests(FileHandlerTests):
    def _getTargetClass(self):
        from supervisor.loggers import RawFileHandler
        return RawFileHandler

    def test_emit_ascii_noerror(self):
        handler = self._makeOne(self.filename)
        record = self._makeLogRecord('hello!')
        handler.emit(record)
        content = open(self.filename, 'r').read()
        self.assertEqual(content, 'hello!')
        
    def test_emit_unicode_noerror(self):
        handler = self._makeOne(self.filename)
        record = self._makeLogRecord(u'fi\xed')
        handler.emit(record)
        content = open(self.filename, 'r').read()
        self.assertEqual(content, 'fi\xc3\xad')

    def test_emit_error(self):
        handler = self._makeOne(self.filename)
        handler.stream = DummyStream(error=OSError)
        record = self._makeLogRecord('hello!')
        try:
            old_stderr = sys.stderr
            dummy_stderr = DummyStream()
            sys.stderr = dummy_stderr
            handler.emit(record)
        finally:
            sys.stderr = old_stderr

        self.assertTrue(dummy_stderr.written.endswith('OSError\n'),
                        dummy_stderr.written)

class RotatingRawFileHandlerTests(RawFileHandlerTests):
    def _getTargetClass(self):
        from supervisor.loggers import RotatingRawFileHandler
        return RotatingRawFileHandler

    def test_ctor(self):
        handler = self._makeOne(self.filename)
        self.assertEqual(handler.mode, 'a')
        self.assertEqual(handler.maxBytes, 512*1024*1024)
        self.assertEqual(handler.backupCount, 10)

    def test_shouldRollover(self):
        handler = self._makeOne(self.filename, maxBytes=10, backupCount=1)
        dummy_stream = DummyStream()
        handler.stream = dummy_stream
        record = self._makeLogRecord('hello!')
        self.assertFalse(handler.shouldRollover(record))
        record = self._makeLogRecord('a' *11)
        self.assertTrue(handler.shouldRollover(record), True)

    def test_emit_does_rollover(self):
        handler = self._makeOne(self.filename, maxBytes=10, backupCount=2)
        record = self._makeLogRecord('a' * 4)

        handler.emit(record) # 4 bytes
        self.assertFalse(os.path.exists(self.filename + '.1'))
        self.assertFalse(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 8 bytes
        self.assertFalse(os.path.exists(self.filename + '.1'))
        self.assertFalse(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 12 bytes, do rollover
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertFalse(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 16 bytes
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertFalse(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 20 bytes, do rollover
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertTrue(os.path.exists(self.filename + '.2'))

        current = open(self.filename,'r').read()
        self.assertEqual(current, 'a'*4)
        one = open(self.filename+ '.1','r').read()
        self.assertEqual(one, 'a'*8)
        two = open(self.filename+ '.2','r').read()
        self.assertEqual(two, 'a'*8)

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
