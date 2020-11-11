import unittest
import os
import sys

from supervisor.compat import as_bytes

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyLogger
from supervisor.tests.base import DummyEvent

class PDispatcherTests(unittest.TestCase):
    def setUp(self):
        from supervisor.events import clear
        clear()

    def tearDown(self):
        from supervisor.events import clear
        clear()

    def _getTargetClass(self):
        from supervisor.dispatchers import PDispatcher
        return PDispatcher

    def _makeOne(self, process=None, channel='stdout', fd=0):
        return self._getTargetClass()(process, channel, fd)

    def test_readable(self):
        inst = self._makeOne()
        self.assertRaises(NotImplementedError, inst.readable)

    def test_writable(self):
        inst = self._makeOne()
        self.assertRaises(NotImplementedError, inst.writable)

    def test_flush(self):
        inst = self._makeOne()
        self.assertEqual(inst.flush(), None)

class POutputDispatcherTests(unittest.TestCase):
    def setUp(self):
        from supervisor.events import clear
        clear()

    def tearDown(self):
        from supervisor.events import clear
        clear()

    def _getTargetClass(self):
        from supervisor.dispatchers import POutputDispatcher
        return POutputDispatcher

    def _makeOne(self, process, channel='stdout'):
        from supervisor import events
        events = {'stdout': events.ProcessCommunicationStdoutEvent,
                  'stderr': events.ProcessCommunicationStderrEvent}
        # dispatcher derives its channel from event class
        return self._getTargetClass()(process, events[channel], 0)

    def test_writable(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.writable(), False)

    def test_readable_open(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.closed = False
        self.assertEqual(dispatcher.readable(), True)

    def test_readable_closed(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.closed = True
        self.assertEqual(dispatcher.readable(), False)

    def test_handle_write_event(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_write_event)

    def test_handle_read_event(self):
        options = DummyOptions()
        options.readfd_result = b'abc'
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_capture_maxbytes=100)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.output_buffer, b'abc')

    def test_handle_read_event_no_data_closes(self):
        options = DummyOptions()
        options.readfd_result = b''
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_capture_maxbytes=100)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertFalse(dispatcher.closed)
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.output_buffer, b'')
        self.assertTrue(dispatcher.closed)

    def test_handle_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        try:
            raise ValueError('foo')
        except:
            dispatcher.handle_error()
        result = options.logger.data[0]
        self.assertTrue(result.startswith(
            'uncaptured python exception, closing channel'),result)

    def test_toggle_capturemode_sends_event(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo',
                              stdout_capture_maxbytes=500)
        process = DummyProcess(config)
        process.pid = 4000
        dispatcher = self._makeOne(process)
        dispatcher.capturemode = True
        dispatcher.capturelog.getvalue = lambda: 'hallooo'
        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        events.subscribe(events.EventTypes.PROCESS_COMMUNICATION, doit)
        dispatcher.toggle_capturemode()
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.process, process)
        self.assertEqual(event.pid, 4000)
        self.assertEqual(event.data, 'hallooo')

    def test_removelogs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.removelogs()
        self.assertEqual(dispatcher.normallog.handlers[0].reopened, True)
        self.assertEqual(dispatcher.normallog.handlers[0].removed, True)
        self.assertEqual(dispatcher.childlog.handlers[0].reopened, True)
        self.assertEqual(dispatcher.childlog.handlers[0].removed, True)

    def test_reopenlogs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.reopenlogs()
        self.assertEqual(dispatcher.childlog.handlers[0].reopened, True)
        self.assertEqual(dispatcher.normallog.handlers[0].reopened, True)

    def test_record_output_log_non_capturemode(self):
        # stdout/stderr goes to the process log and the main log,
        # in non-capturemode, the data length doesn't matter
        options = DummyOptions()
        from supervisor import loggers
        options.loglevel = loggers.LevelsByName.TRAC
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.output_buffer = 'a'
        dispatcher.record_output()
        self.assertEqual(dispatcher.childlog.data, ['a'])
        self.assertEqual(options.logger.data[0],
             "'process1' stdout output:\na")
        self.assertEqual(dispatcher.output_buffer, b'')

    def test_record_output_emits_stdout_event_when_enabled(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_events_enabled=True)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process, 'stdout')
        dispatcher.output_buffer = b'hello from stdout'

        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        events.subscribe(events.EventTypes.PROCESS_LOG_STDOUT, doit)
        dispatcher.record_output()

        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.process, process)
        self.assertEqual(event.data, b'hello from stdout')

    def test_record_output_does_not_emit_stdout_event_when_disabled(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_events_enabled=False)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process, 'stdout')
        dispatcher.output_buffer = b'hello from stdout'

        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        events.subscribe(events.EventTypes.PROCESS_LOG_STDOUT, doit)
        dispatcher.record_output()

        self.assertEqual(len(L), 0)

    def test_record_output_emits_stderr_event_when_enabled(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stderr_events_enabled=True)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process, 'stderr')
        dispatcher.output_buffer = b'hello from stderr'

        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        events.subscribe(events.EventTypes.PROCESS_LOG_STDERR, doit)
        dispatcher.record_output()

        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.process, process)
        self.assertEqual(event.data, b'hello from stderr')

    def test_record_output_does_not_emit_stderr_event_when_disabled(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stderr_events_enabled=False)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process, 'stderr')
        dispatcher.output_buffer = b'hello from stderr'

        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        events.subscribe(events.EventTypes.PROCESS_LOG_STDERR, doit)
        dispatcher.record_output()

        self.assertEqual(len(L), 0)

    def test_record_output_capturemode_string_longer_than_token(self):
        # stdout/stderr goes to the process log and the main log,
        # in capturemode, the length of the data needs to be longer
        # than the capture token to make it out.
        options = DummyOptions()
        from supervisor import loggers
        options.loglevel = loggers.LevelsByName.TRAC
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo',
                              stdout_capture_maxbytes=100)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.output_buffer = b'stdout string longer than a token'
        dispatcher.record_output()
        self.assertEqual(dispatcher.childlog.data,
                         [b'stdout string longer than a token'])
        self.assertEqual(options.logger.data[0],
             "'process1' stdout output:\nstdout string longer than a token")

    def test_record_output_capturemode_string_not_longer_than_token(self):
        # stdout/stderr goes to the process log and the main log,
        # in capturemode, the length of the data needs to be longer
        # than the capture token to make it out.
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo',
                              stdout_capture_maxbytes=100)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.output_buffer = 'a'
        dispatcher.record_output()
        self.assertEqual(dispatcher.childlog.data, [])
        self.assertEqual(dispatcher.output_buffer, 'a')

    def test_stdout_capturemode_single_buffer(self):
        # mike reported that comm events that took place within a single
        # output buffer were broken 8/20/2007
        from supervisor.events import ProcessCommunicationEvent
        from supervisor.events import subscribe
        events = []
        def doit(event):
            events.append(event)
        subscribe(ProcessCommunicationEvent, doit)
        BEGIN_TOKEN = ProcessCommunicationEvent.BEGIN_TOKEN
        END_TOKEN = ProcessCommunicationEvent.END_TOKEN
        data = BEGIN_TOKEN + b'hello' + END_TOKEN
        options = DummyOptions()
        from supervisor.loggers import getLogger
        options.getLogger = getLogger # actually use real logger
        logfile = '/tmp/log'
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile,
                              stdout_capture_maxbytes=1000)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)

        try:
            dispatcher.output_buffer = data
            dispatcher.record_output()
            self.assertEqual(os.path.getsize(logfile), 0)
            self.assertEqual(len(dispatcher.output_buffer), 0)
            self.assertEqual(len(events), 1)

            event = events[0]
            from supervisor.events import ProcessCommunicationStdoutEvent
            self.assertEqual(event.__class__, ProcessCommunicationStdoutEvent)
            self.assertEqual(event.process, process)
            self.assertEqual(event.channel, 'stdout')
            self.assertEqual(event.data, b'hello')

        finally:
            try:
                dispatcher.capturelog.close()
                dispatcher.childlog.close()
                os.remove(logfile)
            except (OSError, IOError):
                pass

    def test_stdout_capturemode_multiple_buffers(self):
        from supervisor.events import ProcessCommunicationEvent
        from supervisor.events import subscribe
        events = []
        def doit(event):
            events.append(event)
        subscribe(ProcessCommunicationEvent, doit)
        import string
        # ascii_letters for python 3
        letters = as_bytes(getattr(string, "letters", string.ascii_letters))
        digits = as_bytes(string.digits) * 4
        BEGIN_TOKEN = ProcessCommunicationEvent.BEGIN_TOKEN
        END_TOKEN = ProcessCommunicationEvent.END_TOKEN
        data = (letters +  BEGIN_TOKEN + digits + END_TOKEN + letters)

        # boundaries that split tokens
        colon = b':'
        broken = data.split(colon)
        first = broken[0] + colon
        second = broken[1] + colon
        third = broken[2]

        options = DummyOptions()
        from supervisor.loggers import getLogger
        options.getLogger = getLogger # actually use real logger
        logfile = '/tmp/log'
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile,
                              stdout_capture_maxbytes=10000)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        try:
            dispatcher.output_buffer = first
            dispatcher.record_output()
            [ x.flush() for x in dispatcher.childlog.handlers ]
            with open(logfile, 'rb') as f:
                self.assertEqual(f.read(), letters)
            self.assertEqual(dispatcher.output_buffer, first[len(letters):])
            self.assertEqual(len(events), 0)

            dispatcher.output_buffer += second
            dispatcher.record_output()
            self.assertEqual(len(events), 0)
            [ x.flush() for x in dispatcher.childlog.handlers ]
            with open(logfile, 'rb') as f:
                self.assertEqual(f.read(), letters)
            self.assertEqual(dispatcher.output_buffer, first[len(letters):])
            self.assertEqual(len(events), 0)

            dispatcher.output_buffer += third
            dispatcher.record_output()
            [ x.flush() for x in dispatcher.childlog.handlers ]
            with open(logfile, 'rb') as f:
                self.assertEqual(f.read(), letters * 2)
            self.assertEqual(len(events), 1)
            event = events[0]
            from supervisor.events import ProcessCommunicationStdoutEvent
            self.assertEqual(event.__class__, ProcessCommunicationStdoutEvent)
            self.assertEqual(event.process, process)
            self.assertEqual(event.channel, 'stdout')
            self.assertEqual(event.data, digits)

        finally:
            try:
                dispatcher.capturelog.close()
                dispatcher.childlog.close()
                os.remove(logfile)
            except (OSError, IOError):
                pass

    def test_strip_ansi(self):
        options = DummyOptions()
        options.strip_ansi = True
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        ansi = b'\x1b[34mHello world... this is longer than a token!\x1b[0m'
        noansi = b'Hello world... this is longer than a token!'

        dispatcher.output_buffer = ansi
        dispatcher.record_output()
        self.assertEqual(len(dispatcher.childlog.data), 1)
        self.assertEqual(dispatcher.childlog.data[0], noansi)

        options.strip_ansi = False

        dispatcher.output_buffer = ansi
        dispatcher.record_output()
        self.assertEqual(len(dispatcher.childlog.data), 2)
        self.assertEqual(dispatcher.childlog.data[1], ansi)

    def test_ctor_no_logfiles(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.capturelog, None)
        self.assertEqual(dispatcher.normallog, None)
        self.assertEqual(dispatcher.childlog, None)

    def test_ctor_logfile_only(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.capturelog, None)
        self.assertEqual(dispatcher.normallog.__class__, DummyLogger)
        self.assertEqual(dispatcher.childlog, dispatcher.normallog)

    def test_ctor_capturelog_only(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_capture_maxbytes=300)
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.capturelog.__class__, DummyLogger)
        self.assertEqual(dispatcher.normallog, None)
        self.assertEqual(dispatcher.childlog, None)

    def test_ctor_stdout_logfile_is_empty_string(self):
        from supervisor.datatypes import logfile_name
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile_name(''))
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.normallog, None)

    def test_ctor_stdout_logfile_none_and_stdout_syslog_false(self):
        from supervisor.datatypes import boolean, logfile_name
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile_name('NONE'),
                              stdout_syslog=boolean('false'))
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.normallog, None)

    def test_ctor_stdout_logfile_none_and_stdout_syslog_true(self):
        from supervisor.datatypes import boolean, logfile_name
        from supervisor.loggers import LevelsByName, SyslogHandler
        from supervisor.options import ServerOptions
        options = ServerOptions() # need real options to get a real logger
        options.loglevel = LevelsByName.TRAC
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile_name('NONE'),
                              stdout_syslog=boolean('true'))
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(len(dispatcher.normallog.handlers), 1)
        self.assertEqual(dispatcher.normallog.handlers[0].__class__,
            SyslogHandler)

    def test_ctor_stdout_logfile_str_and_stdout_syslog_false(self):
        from supervisor.datatypes import boolean, logfile_name
        from supervisor.loggers import FileHandler, LevelsByName
        from supervisor.options import ServerOptions
        options = ServerOptions() # need real options to get a real logger
        options.loglevel = LevelsByName.TRAC
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile_name('/tmp/foo'),
                              stdout_syslog=boolean('false'))
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(len(dispatcher.normallog.handlers), 1)
        self.assertEqual(dispatcher.normallog.handlers[0].__class__, FileHandler)
        dispatcher.normallog.close()

    def test_ctor_stdout_logfile_str_and_stdout_syslog_true(self):
        from supervisor.datatypes import boolean, logfile_name
        from supervisor.loggers import FileHandler, LevelsByName, SyslogHandler
        from supervisor.options import ServerOptions
        options = ServerOptions() # need real options to get a real logger
        options.loglevel = LevelsByName.TRAC
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile_name('/tmp/foo'),
                              stdout_syslog=boolean('true'))
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(len(dispatcher.normallog.handlers), 2)
        self.assertTrue(any(isinstance(h, FileHandler) for h in
            dispatcher.normallog.handlers))
        self.assertTrue(any(isinstance(h, SyslogHandler) for h in
            dispatcher.normallog.handlers))
        dispatcher.normallog.close()

    def test_repr(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        drepr = repr(dispatcher)
        self.assertTrue('POutputDispatcher' in drepr)
        self.assertNotEqual(
            drepr.find('supervisor.tests.base.DummyProcess'),
            -1)
        self.assertTrue(drepr.endswith('(stdout)>'), drepr)

    def test_close(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.close()
        self.assertEqual(dispatcher.closed, True)
        dispatcher.close() # make sure we don't error if we try to close twice
        self.assertEqual(dispatcher.closed, True)


class PInputDispatcherTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.dispatchers import PInputDispatcher
        return PInputDispatcher

    def _makeOne(self, process):
        channel = 'stdin'
        return self._getTargetClass()(process, channel, 0)

    def test_writable_open_nodata(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'a'
        dispatcher.closed = False
        self.assertEqual(dispatcher.writable(), True)

    def test_writable_open_withdata(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = ''
        dispatcher.closed = False
        self.assertEqual(dispatcher.writable(), False)

    def test_writable_closed_nodata(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'a'
        dispatcher.closed = True
        self.assertEqual(dispatcher.writable(), False)

    def test_writable_closed_withdata(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = ''
        dispatcher.closed = True
        self.assertEqual(dispatcher.writable(), False)

    def test_readable(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.readable(), False)

    def test_handle_write_event(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'halloooo'
        self.assertEqual(dispatcher.handle_write_event(), None)
        self.assertEqual(options.written[0], 'halloooo')

    def test_handle_write_event_nodata(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.input_buffer, b'')
        dispatcher.handle_write_event()
        self.assertEqual(dispatcher.input_buffer, b'')
        self.assertEqual(options.written, {})

    def test_handle_write_event_epipe_raised(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'halloooo'
        import errno
        options.write_exception = OSError(errno.EPIPE,
                                          os.strerror(errno.EPIPE))
        dispatcher.handle_write_event()
        self.assertEqual(dispatcher.input_buffer, b'')
        self.assertTrue(options.logger.data[0].startswith(
            'fd 0 closed, stopped monitoring'))
        self.assertTrue(options.logger.data[0].endswith('(stdin)>'))

    def test_handle_write_event_uncaught_raised(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'halloooo'
        import errno
        options.write_exception = OSError(errno.EBADF,
                                          os.strerror(errno.EBADF))
        self.assertRaises(OSError, dispatcher.handle_write_event)

    def test_handle_write_event_over_os_limit(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        options.write_accept = 1
        dispatcher.input_buffer = 'a' * 50
        dispatcher.handle_write_event()
        self.assertEqual(len(dispatcher.input_buffer), 49)
        self.assertEqual(options.written[0], 'a')

    def test_handle_read_event(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_read_event)

    def test_handle_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        try:
            raise ValueError('foo')
        except:
            dispatcher.handle_error()
        result = options.logger.data[0]
        self.assertTrue(result.startswith(
            'uncaptured python exception, closing channel'),result)

    def test_repr(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        drepr = repr(dispatcher)
        self.assertTrue('PInputDispatcher' in drepr)
        self.assertNotEqual(
            drepr.find('supervisor.tests.base.DummyProcess'),
            -1)
        self.assertTrue(drepr.endswith('(stdin)>'), drepr)

    def test_close(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.close()
        self.assertEqual(dispatcher.closed, True)
        dispatcher.close() # make sure we don't error if we try to close twice
        self.assertEqual(dispatcher.closed, True)

class PEventListenerDispatcherTests(unittest.TestCase):
    def setUp(self):
        from supervisor.events import clear
        clear()

    def tearDown(self):
        from supervisor.events import clear
        clear()

    def _getTargetClass(self):
        from supervisor.dispatchers import PEventListenerDispatcher
        return PEventListenerDispatcher

    def _makeOne(self, process):
        channel = 'stdout'
        return self._getTargetClass()(process, channel, 0)

    def test_writable(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.writable(), False)

    def test_readable_open(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.closed = False
        self.assertEqual(dispatcher.readable(), True)

    def test_readable_closed(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.closed = True
        self.assertEqual(dispatcher.readable(), False)

    def test_handle_write_event(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_write_event)

    def test_handle_read_event_calls_handle_listener_state_change(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher = self._makeOne(process)
        options.readfd_result = dispatcher.READY_FOR_EVENTS_TOKEN
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(process.listener_state, EventListenerStates.READY)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(len(dispatcher.childlog.data), 1)
        self.assertEqual(dispatcher.childlog.data[0],
                         dispatcher.READY_FOR_EVENTS_TOKEN)

    def test_handle_read_event_nodata(self):
        options = DummyOptions()
        options.readfd_result = ''
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        from supervisor.dispatchers import EventListenerStates
        self.assertEqual(dispatcher.process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)

    def test_handle_read_event_logging_nologs(self):
        options = DummyOptions()
        options.readfd_result = b'supercalifragilisticexpialidocious'
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        # just make sure there are no errors if a child logger doesnt
        # exist
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.childlog, None)

    def test_handle_read_event_logging_childlog(self):
        options = DummyOptions()
        options.readfd_result = b'supercalifragilisticexpialidocious'
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(len(dispatcher.childlog.data), 1)
        self.assertEqual(dispatcher.childlog.data[0],
                         b'supercalifragilisticexpialidocious')

    def test_handle_listener_state_change_from_unknown(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.UNKNOWN
        dispatcher.state_buffer = b'whatever'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(options.logger.data, [])
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_acknowledged_to_ready(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher.state_buffer = b'READY\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(options.logger.data[0],
                         'process1: ACKNOWLEDGED -> READY')
        self.assertEqual(process.listener_state, EventListenerStates.READY)

    def test_handle_listener_state_change_acknowledged_gobbles(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher.state_buffer = b'READY\ngarbage\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(options.logger.data[0],
                         'process1: ACKNOWLEDGED -> READY')
        self.assertEqual(options.logger.data[1],
                         'process1: READY -> UNKNOWN')
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_acknowledged_to_insufficient(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher.state_buffer = b'RE'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'RE')
        self.assertEqual(options.logger.data, [])
        self.assertEqual(process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)

    def test_handle_listener_state_change_acknowledged_to_unknown(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher.state_buffer = b'bogus data yo'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(options.logger.data[0],
                         'process1: ACKNOWLEDGED -> UNKNOWN')
        self.assertEqual(options.logger.data[1],
                         'process1: has entered the UNKNOWN state and will '
                         'no longer receive events, this usually indicates '
                         'the process violated the eventlistener protocol')
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_ready_to_unknown(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.READY
        dispatcher.state_buffer = b'bogus data yo'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(options.logger.data[0],
                         'process1: READY -> UNKNOWN')
        self.assertEqual(options.logger.data[1],
                         'process1: has entered the UNKNOWN state and will '
                         'no longer receive events, this usually indicates '
                         'the process violated the eventlistener protocol')
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_busy_to_insufficient(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        dispatcher.state_buffer = b'bogus data yo'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'bogus data yo')
        self.assertEqual(process.listener_state, EventListenerStates.BUSY)

    def test_handle_listener_state_change_busy_to_acknowledged_procd(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        class Dummy:
            pass
        process.group = Dummy()
        process.group.config = Dummy()
        from supervisor.dispatchers import default_handler
        process.group.config.result_handler = default_handler
        dispatcher.state_buffer = b'RESULT 2\nOKabc'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'abc')
        self.assertEqual(options.logger.data[0],
                         'process1: event was processed')
        self.assertEqual(options.logger.data[1],
                         'process1: BUSY -> ACKNOWLEDGED')
        self.assertEqual(process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)

    def test_handle_listener_state_change_busy_to_acknowledged_rejected(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        class Dummy:
            pass
        process.group = Dummy()
        process.group.config = Dummy()
        from supervisor.dispatchers import default_handler
        process.group.config.result_handler = default_handler
        dispatcher.state_buffer = b'RESULT 4\nFAILabc'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'abc')
        self.assertEqual(options.logger.data[0],
                         'process1: event was rejected')
        self.assertEqual(options.logger.data[1],
                         'process1: BUSY -> ACKNOWLEDGED')
        self.assertEqual(process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)

    def test_handle_listener_state_change_busy_to_unknown(self):
        from supervisor.events import EventRejectedEvent
        from supervisor.events import subscribe
        events = []
        def doit(event):
            events.append(event)
        subscribe(EventRejectedEvent, doit)
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        current_event = DummyEvent()
        process.event = current_event
        dispatcher.state_buffer = b'bogus data\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(options.logger.data[0],
                "process1: bad result line: 'bogus data'")
        self.assertEqual(options.logger.data[1],
                'process1: BUSY -> UNKNOWN')
        self.assertEqual(options.logger.data[2],
                         'process1: has entered the UNKNOWN state and will '
                         'no longer receive events, this usually indicates '
                         'the process violated the eventlistener protocol')
        self.assertEqual(process.listener_state,
                         EventListenerStates.UNKNOWN)
        self.assertEqual(events[0].process, process)
        self.assertEqual(events[0].event, current_event)

    def test_handle_listener_state_busy_gobbles(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        class Dummy:
            pass
        process.group = Dummy()
        process.group.config = Dummy()
        from supervisor.dispatchers import default_handler
        process.group.config.result_handler = default_handler
        dispatcher.state_buffer = b'RESULT 2\nOKbogus data\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, b'')
        self.assertEqual(options.logger.data[0],
                         'process1: event was processed')
        self.assertEqual(options.logger.data[1],
                         'process1: BUSY -> ACKNOWLEDGED')
        self.assertEqual(options.logger.data[2],
                         'process1: ACKNOWLEDGED -> UNKNOWN')
        self.assertEqual(options.logger.data[3],
                         'process1: has entered the UNKNOWN state and will '
                         'no longer receive events, this usually indicates '
                         'the process violated the eventlistener protocol')
        self.assertEqual(process.listener_state,
                         EventListenerStates.UNKNOWN)

    def test_handle_result_accept(self):
        from supervisor.events import subscribe
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        subscribe(events.EventRejectedEvent, doit)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        def handle(event, result):
            pass
        class Dummy:
            pass
        process.group = Dummy()
        process.group.config = Dummy()
        process.group.config.result_handler = handle
        process.listener_state = EventListenerStates.BUSY
        dispatcher.handle_result('foo')
        self.assertEqual(len(L), 0)
        self.assertEqual(process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)
        self.assertEqual(options.logger.data[0],
                         'process1: event was processed')
        self.assertEqual(options.logger.data[1],
                         'process1: BUSY -> ACKNOWLEDGED')

    def test_handle_result_rejectevent(self):
        from supervisor.events import subscribe
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        subscribe(events.EventRejectedEvent, doit)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        def rejected(event, result):
            from supervisor.dispatchers import RejectEvent
            raise RejectEvent(result)
        class Dummy:
            pass
        process.group = Dummy()
        process.group.config = Dummy()
        process.group.config.result_handler = rejected
        process.listener_state = EventListenerStates.BUSY
        dispatcher.handle_result('foo')
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0].__class__, events.EventRejectedEvent)
        self.assertEqual(process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)
        self.assertEqual(options.logger.data[0],
                         'process1: event was rejected')
        self.assertEqual(options.logger.data[1],
                         'process1: BUSY -> ACKNOWLEDGED')

    def test_handle_result_exception(self):
        from supervisor.events import subscribe
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        L = []
        def doit(event):
            L.append(event)
        from supervisor import events
        subscribe(events.EventRejectedEvent, doit)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        def exception(event, result):
            raise ValueError
        class Dummy:
            pass
        process.group = Dummy()
        process.group.config = Dummy()
        process.group.config.result_handler = exception
        process.group.result_handler = exception
        process.listener_state = EventListenerStates.BUSY
        dispatcher.handle_result('foo')
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0].__class__, events.EventRejectedEvent)
        self.assertEqual(process.listener_state,
                         EventListenerStates.UNKNOWN)
        self.assertEqual(options.logger.data[0],
                         'process1: event caused an error')
        self.assertEqual(options.logger.data[1],
                         'process1: BUSY -> UNKNOWN')
        self.assertEqual(options.logger.data[2],
                         'process1: has entered the UNKNOWN state and will '
                         'no longer receive events, this usually indicates '
                         'the process violated the eventlistener protocol')

    def test_handle_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        try:
            raise ValueError('foo')
        except:
            dispatcher.handle_error()
        result = options.logger.data[0]
        self.assertTrue(result.startswith(
            'uncaptured python exception, closing channel'),result)

    def test_removelogs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.removelogs()
        self.assertEqual(dispatcher.childlog.handlers[0].reopened, True)
        self.assertEqual(dispatcher.childlog.handlers[0].removed, True)

    def test_reopenlogs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.reopenlogs()
        self.assertEqual(dispatcher.childlog.handlers[0].reopened, True)

    def test_strip_ansi(self):
        options = DummyOptions()
        options.strip_ansi = True
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        ansi = b'\x1b[34mHello world... this is longer than a token!\x1b[0m'
        noansi = b'Hello world... this is longer than a token!'

        options.readfd_result = ansi
        dispatcher.handle_read_event()
        self.assertEqual(len(dispatcher.childlog.data), 1)
        self.assertEqual(dispatcher.childlog.data[0], noansi)

        options.strip_ansi = False

        options.readfd_result = ansi
        dispatcher.handle_read_event()
        self.assertEqual(len(dispatcher.childlog.data), 2)
        self.assertEqual(dispatcher.childlog.data[1], ansi)

    def test_ctor_nologfiles(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.childlog, None)

    def test_ctor_logfile_only(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.childlog.__class__, DummyLogger)

    def test_repr(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        drepr = repr(dispatcher)
        self.assertTrue('PEventListenerDispatcher' in drepr)
        self.assertNotEqual(
            drepr.find('supervisor.tests.base.DummyProcess'),
            -1)
        self.assertTrue(drepr.endswith('(stdout)>'), drepr)

    def test_close(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.close()
        self.assertEqual(dispatcher.closed, True)
        dispatcher.close() # make sure we don't error if we try to close twice
        self.assertEqual(dispatcher.closed, True)


class stripEscapeTests(unittest.TestCase):
    def _callFUT(self, s):
        from supervisor.dispatchers import stripEscapes
        return stripEscapes(s)

    def test_zero_length_string(self):
        self.assertEqual(self._callFUT(b''), b'')

    def test_ansi(self):
        ansi = b'\x1b[34mHello world... this is longer than a token!\x1b[0m'
        noansi = b'Hello world... this is longer than a token!'
        self.assertEqual(self._callFUT(ansi), noansi)

    def test_noansi(self):
        noansi = b'Hello world... this is longer than a token!'
        self.assertEqual(self._callFUT(noansi), noansi)

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
