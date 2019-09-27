# -*- coding: utf-8 -*-
import errno
import sys
import unittest
import tempfile
import shutil
import os
import syslog

from supervisor.compat import PY2
from supervisor.compat import as_string
from supervisor.compat import StringIO
from supervisor.compat import unicode

from supervisor.tests.base import mock
from supervisor.tests.base import DummyStream

class LevelTests(unittest.TestCase):
    def test_LOG_LEVELS_BY_NUM_doesnt_include_builtins(self):
        from supervisor import loggers
        for level_name in loggers.LOG_LEVELS_BY_NUM.values():
            self.assertFalse(level_name.startswith('_'))

class HandlerTests:
    def setUp(self):
        self.basedir = tempfile.mkdtemp()
        self.filename = os.path.join(self.basedir, 'thelog')

    def tearDown(self):
        try:
            shutil.rmtree(self.basedir)
        except OSError:
            pass

    def _makeOne(self, *arg, **kw):
        klass = self._getTargetClass()
        return klass(*arg, **kw)

    def _makeLogRecord(self, msg):
        from supervisor import loggers
        record = loggers.LogRecord(
            level=loggers.LevelsByName.INFO,
            msg=msg,
            exc_info=None
            )
        return record

class BareHandlerTests(HandlerTests, unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.loggers import Handler
        return Handler

    def test_flush_stream_flush_raises_IOError_EPIPE(self):
        stream = DummyStream(error=IOError(errno.EPIPE))
        inst = self._makeOne(stream=stream)
        self.assertEqual(inst.flush(), None) # does not raise

    def test_flush_stream_flush_raises_IOError_not_EPIPE(self):
        stream = DummyStream(error=IOError(errno.EALREADY))
        inst = self._makeOne(stream=stream)
        self.assertRaises(IOError, inst.flush) # non-EPIPE IOError raises

    def test_close_already_closed(self):
        stream = DummyStream()
        inst = self._makeOne(stream=stream)
        inst.closed = True
        self.assertEqual(inst.close(), None)

    def test_close_stream_fileno_above_3(self):
        stream = DummyStream(fileno=50)
        inst = self._makeOne(stream=stream)
        self.assertEqual(inst.close(), None)
        self.assertTrue(inst.closed)
        self.assertTrue(inst.stream.closed)

    def test_close_stream_fileno_below_3(self):
        stream = DummyStream(fileno=0)
        inst = self._makeOne(stream=stream)
        self.assertEqual(inst.close(), None)
        self.assertFalse(inst.closed)
        self.assertFalse(inst.stream.closed)

    def test_close_stream_handles_fileno_unsupported_operation(self):
        # on python 2, StringIO does not have fileno()
        # on python 3, StringIO has fileno() but calling it raises
        stream = StringIO()
        inst = self._makeOne(stream=stream)
        inst.close() # shouldn't raise
        self.assertTrue(inst.closed)

    def test_close_stream_handles_fileno_ioerror(self):
        stream = DummyStream()
        def raise_ioerror():
            raise IOError()
        stream.fileno = raise_ioerror
        inst = self._makeOne(stream=stream)
        inst.close() # shouldn't raise
        self.assertTrue(inst.closed)

    def test_emit_gardenpath(self):
        stream = DummyStream()
        inst = self._makeOne(stream=stream)
        record = self._makeLogRecord(b'foo')
        inst.emit(record)
        self.assertEqual(stream.flushed, True)
        self.assertEqual(stream.written, b'foo')

    def test_emit_unicode_error(self):
        stream = DummyStream(error=UnicodeError)
        inst = self._makeOne(stream=stream)
        record = self._makeLogRecord(b'foo')
        inst.emit(record)
        self.assertEqual(stream.flushed, True)
        self.assertEqual(stream.written, b'foo')

    def test_emit_other_error(self):
        stream = DummyStream(error=ValueError)
        inst = self._makeOne(stream=stream)
        handled = []
        inst.handleError = lambda: handled.append(True)
        record = self._makeLogRecord(b'foo')
        inst.emit(record)
        self.assertEqual(stream.flushed, False)
        self.assertEqual(stream.written, b'')

class FileHandlerTests(HandlerTests, unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.loggers import FileHandler
        return FileHandler

    def test_ctor(self):
        handler = self._makeOne(self.filename)
        self.assertTrue(os.path.exists(self.filename), self.filename)
        self.assertEqual(handler.mode, 'ab')
        self.assertEqual(handler.baseFilename, self.filename)
        self.assertEqual(handler.stream.name, self.filename)
        handler.close()

    def test_close(self):
        handler = self._makeOne(self.filename)
        handler.stream.close()
        handler.stream = DummyStream()
        handler.close()
        self.assertEqual(handler.stream.closed, True)

    def test_close_raises(self):
        handler = self._makeOne(self.filename)
        handler.stream.close()
        handler.stream = DummyStream(OSError)
        self.assertRaises(OSError, handler.close)
        self.assertEqual(handler.stream.closed, False)

    def test_reopen(self):
        handler = self._makeOne(self.filename)
        handler.stream.close()
        stream = DummyStream()
        handler.stream = stream
        handler.reopen()
        self.assertEqual(stream.closed, True)
        self.assertEqual(handler.stream.name, self.filename)
        handler.close()

    def test_reopen_raises(self):
        handler = self._makeOne(self.filename)
        handler.stream.close()
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

    def test_emit_ascii_noerror(self):
        handler = self._makeOne(self.filename)
        record = self._makeLogRecord(b'hello!')
        handler.emit(record)
        handler.close()
        with open(self.filename, 'rb') as f:
            self.assertEqual(f.read(), b'hello!')

    def test_emit_unicode_noerror(self):
        handler = self._makeOne(self.filename)
        record = self._makeLogRecord(b'fi\xc3\xad')
        handler.emit(record)
        handler.close()
        with open(self.filename, 'rb') as f:
            self.assertEqual(f.read(), b'fi\xc3\xad')

    def test_emit_error(self):
        handler = self._makeOne(self.filename)
        handler.stream.close()
        handler.stream = DummyStream(error=OSError)
        record = self._makeLogRecord(b'hello!')
        try:
            old_stderr = sys.stderr
            dummy_stderr = DummyStream()
            sys.stderr = dummy_stderr
            handler.emit(record)
        finally:
            sys.stderr = old_stderr

        self.assertTrue(dummy_stderr.written.endswith(b'OSError\n'),
                        dummy_stderr.written)

if os.path.exists('/dev/stdout'):
    StdoutTestsBase = FileHandlerTests
else:
    # Skip the stdout tests on platforms that don't have /dev/stdout.
    StdoutTestsBase = object

class StdoutTests(StdoutTestsBase):
    def test_ctor_with_dev_stdout(self):
        handler = self._makeOne('/dev/stdout')
        # Modes 'w' and 'a' have the same semantics when applied to
        # character device files and fifos.
        self.assertTrue(handler.mode in ['wb', 'ab'], handler.mode)
        self.assertEqual(handler.baseFilename, '/dev/stdout')
        self.assertEqual(handler.stream.name, '/dev/stdout')
        handler.close()

class RotatingFileHandlerTests(FileHandlerTests):

    def _getTargetClass(self):
        from supervisor.loggers import RotatingFileHandler
        return RotatingFileHandler

    def test_ctor(self):
        handler = self._makeOne(self.filename)
        self.assertEqual(handler.mode, 'ab')
        self.assertEqual(handler.maxBytes, 512*1024*1024)
        self.assertEqual(handler.backupCount, 10)
        handler.close()

    def test_emit_does_rollover(self):
        handler = self._makeOne(self.filename, maxBytes=10, backupCount=2)
        record = self._makeLogRecord(b'a' * 4)

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

        handler.emit(record) # 20 bytes
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertFalse(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 24 bytes, do rollover
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertTrue(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 28 bytes
        handler.close()
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertTrue(os.path.exists(self.filename + '.2'))

        with open(self.filename, 'rb') as f:
            self.assertEqual(f.read(), b'a' * 4)

        with open(self.filename+'.1', 'rb') as f:
            self.assertEqual(f.read(), b'a' * 12)

        with open(self.filename+'.2', 'rb') as f:
            self.assertEqual(f.read(), b'a' * 12)

    def test_current_logfile_removed(self):
        handler = self._makeOne(self.filename, maxBytes=6, backupCount=1)
        record = self._makeLogRecord(b'a' * 4)

        handler.emit(record) # 4 bytes
        self.assertTrue(os.path.exists(self.filename))
        self.assertFalse(os.path.exists(self.filename + '.1'))

        # Someone removes the active log file! :-(
        os.unlink(self.filename)
        self.assertFalse(os.path.exists(self.filename))

        handler.emit(record) # 8 bytes, do rollover
        handler.close()
        self.assertTrue(os.path.exists(self.filename))
        self.assertFalse(os.path.exists(self.filename + '.1'))

    def test_removeAndRename_destination_does_not_exist(self):
        inst = self._makeOne(self.filename)
        renames = []
        removes = []
        inst._remove = lambda v: removes.append(v)
        inst._exists = lambda v: False
        inst._rename = lambda s, t: renames.append((s, t))
        inst.removeAndRename('foo', 'bar')
        self.assertEqual(renames, [('foo', 'bar')])
        self.assertEqual(removes, [])
        inst.close()

    def test_removeAndRename_destination_exists(self):
        inst = self._makeOne(self.filename)
        renames = []
        removes = []
        inst._remove = lambda v: removes.append(v)
        inst._exists = lambda v: True
        inst._rename = lambda s, t: renames.append((s, t))
        inst.removeAndRename('foo', 'bar')
        self.assertEqual(renames, [('foo', 'bar')])
        self.assertEqual(removes, ['bar'])
        inst.close()

    def test_removeAndRename_remove_raises_ENOENT(self):
        def remove(fn):
            raise OSError(errno.ENOENT)
        inst = self._makeOne(self.filename)
        renames = []
        inst._remove = remove
        inst._exists = lambda v: True
        inst._rename = lambda s, t: renames.append((s, t))
        inst.removeAndRename('foo', 'bar')
        self.assertEqual(renames, [('foo', 'bar')])
        inst.close()

    def test_removeAndRename_remove_raises_other_than_ENOENT(self):
        def remove(fn):
            raise OSError(errno.EAGAIN)
        inst = self._makeOne(self.filename)
        inst._remove = remove
        inst._exists = lambda v: True
        self.assertRaises(OSError, inst.removeAndRename, 'foo', 'bar')
        inst.close()

    def test_removeAndRename_rename_raises_ENOENT(self):
        def rename(s, d):
            raise OSError(errno.ENOENT)
        inst = self._makeOne(self.filename)
        inst._rename = rename
        inst._exists = lambda v: False
        self.assertEqual(inst.removeAndRename('foo', 'bar'), None)
        inst.close()

    def test_removeAndRename_rename_raises_other_than_ENOENT(self):
        def rename(s, d):
            raise OSError(errno.EAGAIN)
        inst = self._makeOne(self.filename)
        inst._rename = rename
        inst._exists = lambda v: False
        self.assertRaises(OSError, inst.removeAndRename, 'foo', 'bar')
        inst.close()

    def test_doRollover_maxbytes_lte_zero(self):
        inst = self._makeOne(self.filename)
        inst.maxBytes = 0
        self.assertEqual(inst.doRollover(), None)
        inst.close()


class BoundIOTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.loggers import BoundIO
        return BoundIO

    def _makeOne(self, maxbytes, buf=''):
        klass = self._getTargetClass()
        return klass(maxbytes, buf)

    def test_write_overflow(self):
        io = self._makeOne(1, b'a')
        io.write(b'b')
        self.assertEqual(io.buf, b'b')

    def test_getvalue(self):
        io = self._makeOne(1, b'a')
        self.assertEqual(io.getvalue(), b'a')

    def test_clear(self):
        io = self._makeOne(1, b'a')
        io.clear()
        self.assertEqual(io.buf, b'')

    def test_close(self):
        io = self._makeOne(1, b'a')
        io.close()
        self.assertEqual(io.buf, b'')

class LoggerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.loggers import Logger
        return Logger

    def _makeOne(self, level=None, handlers=None):
        klass = self._getTargetClass()
        return klass(level, handlers)

    def test_blather(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.BLAT)
        logger = self._makeOne(LevelsByName.BLAT, (handler,))
        logger.blather('hello')
        self.assertEqual(len(handler.records), 1)
        logger.level = LevelsByName.TRAC
        logger.blather('hello')
        self.assertEqual(len(handler.records), 1)

    def test_trace(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.TRAC)
        logger = self._makeOne(LevelsByName.TRAC, (handler,))
        logger.trace('hello')
        self.assertEqual(len(handler.records), 1)
        logger.level = LevelsByName.DEBG
        logger.trace('hello')
        self.assertEqual(len(handler.records), 1)

    def test_debug(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.DEBG)
        logger = self._makeOne(LevelsByName.DEBG, (handler,))
        logger.debug('hello')
        self.assertEqual(len(handler.records), 1)
        logger.level = LevelsByName.INFO
        logger.debug('hello')
        self.assertEqual(len(handler.records), 1)

    def test_info(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.INFO)
        logger = self._makeOne(LevelsByName.INFO, (handler,))
        logger.info('hello')
        self.assertEqual(len(handler.records), 1)
        logger.level = LevelsByName.WARN
        logger.info('hello')
        self.assertEqual(len(handler.records), 1)

    def test_warn(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.WARN)
        logger = self._makeOne(LevelsByName.WARN, (handler,))
        logger.warn('hello')
        self.assertEqual(len(handler.records), 1)
        logger.level = LevelsByName.ERRO
        logger.warn('hello')
        self.assertEqual(len(handler.records), 1)

    def test_error(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.ERRO)
        logger = self._makeOne(LevelsByName.ERRO, (handler,))
        logger.error('hello')
        self.assertEqual(len(handler.records), 1)
        logger.level = LevelsByName.CRIT
        logger.error('hello')
        self.assertEqual(len(handler.records), 1)

    def test_critical(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.CRIT)
        logger = self._makeOne(LevelsByName.CRIT, (handler,))
        logger.critical('hello')
        self.assertEqual(len(handler.records), 1)

    def test_close(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.CRIT)
        logger = self._makeOne(LevelsByName.CRIT, (handler,))
        logger.close()
        self.assertEqual(handler.closed, True)

    def test_getvalue(self):
        from supervisor.loggers import LevelsByName
        handler = DummyHandler(LevelsByName.CRIT)
        logger = self._makeOne(LevelsByName.CRIT, (handler,))
        self.assertRaises(NotImplementedError, logger.getvalue)


class MockSysLog(mock.Mock):
    def __call__(self, *args, **kwargs):
        message = args[-1]
        if sys.version_info < (3, 0) and isinstance(message, unicode):
            # Python 2.x raises a UnicodeEncodeError when attempting to
            #  transmit unicode characters that don't encode in the
            #  default encoding.
            message.encode()
        super(MockSysLog, self).__call__(*args, **kwargs)

class SyslogHandlerTests(HandlerTests, unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _getTargetClass(self):
        return __import__('supervisor.loggers').loggers.SyslogHandler

    def _makeOne(self):
        return self._getTargetClass()()

    def test_emit_record_asdict_raises(self):
        class Record(object):
            def asdict(self):
                raise TypeError
        record = Record()
        handler = self._makeOne()
        handled = []
        handler.handleError = lambda: handled.append(True)
        handler.emit(record)
        self.assertEqual(handled, [True])


    @mock.patch('syslog.syslog', MockSysLog())
    def test_emit_ascii_noerror(self):
        handler = self._makeOne()
        record = self._makeLogRecord(b'hello!')
        handler.emit(record)
        syslog.syslog.assert_called_with('hello!')
        record = self._makeLogRecord('hi!')
        handler.emit(record)
        syslog.syslog.assert_called_with('hi!')

    @mock.patch('syslog.syslog', MockSysLog())
    def test_close(self):
        handler = self._makeOne()
        handler.close()  # no-op for syslog

    @mock.patch('syslog.syslog', MockSysLog())
    def test_reopen(self):
        handler = self._makeOne()
        handler.reopen()  # no-op for syslog

    if PY2:
        @mock.patch('syslog.syslog', MockSysLog())
        def test_emit_unicode_noerror(self):
            handler = self._makeOne()
            inp = as_string('fií')
            record = self._makeLogRecord(inp)
            handler.emit(record)
            syslog.syslog.assert_called_with('fi\xc3\xad')
        def test_emit_unicode_witherror(self):
            handler = self._makeOne()
            called = []
            def fake_syslog(msg):
                if not called:
                    called.append(msg)
                    raise UnicodeError
            handler._syslog = fake_syslog
            record = self._makeLogRecord(as_string('fií'))
            handler.emit(record)
            self.assertEqual(called, [as_string('fi\xc3\xad')])
    else:
        @mock.patch('syslog.syslog', MockSysLog())
        def test_emit_unicode_noerror(self):
            handler = self._makeOne()
            record = self._makeLogRecord('fií')
            handler.emit(record)
            syslog.syslog.assert_called_with('fií')
        def test_emit_unicode_witherror(self):
            handler = self._makeOne()
            called = []
            def fake_syslog(msg):
                if not called:
                    called.append(msg)
                    raise UnicodeError
            handler._syslog = fake_syslog
            record = self._makeLogRecord('fií')
            handler.emit(record)
            self.assertEqual(called, ['fií'])

class DummyHandler:
    close = False
    def __init__(self, level):
        self.level = level
        self.records = []
    def emit(self, record):
        self.records.append(record)
    def close(self):
        self.closed = True

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
