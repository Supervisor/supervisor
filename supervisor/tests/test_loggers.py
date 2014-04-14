import sys
import unittest
import tempfile
import shutil
import os
import syslog

import mock

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
        record = loggers.LogRecord(level=loggers.LevelsByName.INFO,
                                   msg=msg,
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

class RotatingFileHandlerTests(FileHandlerTests):

    def _getTargetClass(self):
        from supervisor.loggers import RotatingFileHandler
        return RotatingFileHandler

    def test_ctor(self):
        handler = self._makeOne(self.filename)
        self.assertEqual(handler.mode, 'a')
        self.assertEqual(handler.maxBytes, 512*1024*1024)
        self.assertEqual(handler.backupCount, 10)

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

        handler.emit(record) # 20 bytes
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertFalse(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 24 bytes, do rollover
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertTrue(os.path.exists(self.filename + '.2'))

        handler.emit(record) # 28 bytes
        self.assertTrue(os.path.exists(self.filename + '.1'))
        self.assertTrue(os.path.exists(self.filename + '.2'))

        current = open(self.filename,'r').read()
        self.assertEqual(current, 'a' * 4)
        one = open(self.filename+ '.1','r').read()
        self.assertEqual(one, 'a'*12)
        two = open(self.filename+ '.2','r').read()
        self.assertEqual(two, 'a'*12)

    def test_current_logfile_removed(self):
        handler = self._makeOne(self.filename, maxBytes=6, backupCount=1)
        record = self._makeLogRecord('a' * 4)

        handler.emit(record) # 4 bytes
        self.assertTrue(os.path.exists(self.filename))
        self.assertFalse(os.path.exists(self.filename + '.1'))

        # Someone removes the active log file! :-(
        os.unlink(self.filename)
        self.assertFalse(os.path.exists(self.filename))

        handler.emit(record) # 8 bytes, do rollover
        self.assertTrue(os.path.exists(self.filename))
        self.assertFalse(os.path.exists(self.filename + '.1'))


class BoundIOTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.loggers import BoundIO
        return BoundIO

    def _makeOne(self, maxbytes, buf=''):
        klass = self._getTargetClass()
        return klass(maxbytes, buf)

    def test_write_overflow(self):
        io = self._makeOne(1, 'a')
        io.write('b')
        self.assertEqual(io.buf, 'b')

    def test_getvalue(self):
        io = self._makeOne(1, 'a')
        self.assertEqual(io.getvalue(), 'a')

    def test_clear(self):
        io = self._makeOne(1, 'a')
        io.clear()
        self.assertEqual(io.buf, '')

    def test_close(self):
        io = self._makeOne(1, 'a')
        io.close()
        self.assertEqual(io.buf, '')

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

    @mock.patch('syslog.syslog', MockSysLog())
    def test_emit_ascii_noerror(self):
        handler = self._makeOne()
        record = self._makeLogRecord('hello!')
        handler.emit(record)
        syslog.syslog.assert_called_with('hello!')

    @mock.patch('syslog.syslog', MockSysLog())
    def test_close(self):
        handler = self._makeOne()
        handler.close()  # no-op for syslog

    @mock.patch('syslog.syslog', MockSysLog())
    def test_reopen(self):
        handler = self._makeOne()
        handler.reopen()  # no-op for syslog

    @mock.patch('syslog.syslog', MockSysLog())
    def test_emit_unicode_noerror(self):
        handler = self._makeOne()
        record = self._makeLogRecord(u'fi\xed')
        handler.emit(record)
        if sys.version_info < (3, 0):
            syslog.syslog.assert_called_with('fi\xc3\xad')
        else:
            syslog.syslog.assert_called_with(u'fi\xed')

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
