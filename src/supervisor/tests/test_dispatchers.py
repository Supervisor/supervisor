import unittest
import os
import sys

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyLogger

class POutputDispatcherTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.dispatchers import POutputDispatcher
        return POutputDispatcher

    def _makeOne(self, process):
        from supervisor.events import ProcessCommunicationStdoutEvent
        return self._getTargetClass()(process,
                                      ProcessCommunicationStdoutEvent, 0)

    def test_writable(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.writable(), False)
        
    def test_readable(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.readable(), True)

    def test_handle_write_event(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_write_event)

    def test_handle_read_event(self):
        options = DummyOptions()
        options.readfd_result = 'abc'
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.output_buffer, 'abc')
        
    def test_handle_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_error)

    def test_toggle_capturemode_buffer_overrun(self):
        executable = '/bin/cat'
        options = DummyOptions()
        from StringIO import StringIO
        options.openreturn = StringIO('a' * (3 << 20)) # > 2MB
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo',
                              stdout_capturefile='/tmp/capture')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.capturemode = True
        events = []
        def doit(event):
            events.append(event)
        dispatcher.toggle_capturemode()
        result = options.logger.data[0]
        self.failUnless(result.startswith('Truncated oversized'), result)

    def test_removelogs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.removelogs()
        self.assertEqual(dispatcher.mainlog.handlers[0].reopened, True)
        self.assertEqual(dispatcher.mainlog.handlers[0].removed, True)
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
        self.assertEqual(dispatcher.mainlog.handlers[0].reopened, True)

    def test_record_output(self):
        # stdout/stderr goes to the process log and the main log
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.output_buffer = 'stdout string longer than a token'
        dispatcher.record_output()
        self.assertEqual(dispatcher.childlog.data,
                         ['stdout string longer than a token'])
        self.assertEqual(options.logger.data[0], 5)
        self.assertEqual(options.logger.data[1],
             "'process1' stdout output:\nstdout string longer than a token")

    def test_stdout_capturemode_switch(self):
        from supervisor.events import ProcessCommunicationEvent
        from supervisor.events import subscribe
        events = []
        def doit(event):
            events.append(event)
        subscribe(ProcessCommunicationEvent, doit)
        import string
        letters = string.letters
        digits = string.digits * 4
        BEGIN_TOKEN = ProcessCommunicationEvent.BEGIN_TOKEN
        END_TOKEN = ProcessCommunicationEvent.END_TOKEN
        data = (letters +  BEGIN_TOKEN + digits + END_TOKEN + letters)

        # boundaries that split tokens
        broken = data.split(':')
        first = broken[0] + ':'
        second = broken[1] + ':'
        third = broken[2]

        executable = '/bin/cat'
        options = DummyOptions()
        from supervisor.options import getLogger
        options.getLogger = getLogger # actually use real logger
        logfile = '/tmp/log'
        capturefile = '/tmp/capture'
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile=logfile,
                              stdout_capturefile=capturefile)
        config.stdout_logfile = logfile
        config.capturefile = capturefile
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        try:
            dispatcher.output_buffer = first
            dispatcher.record_output()
            [ x.flush() for x in dispatcher.childlog.handlers]
            self.assertEqual(open(logfile, 'r').read(), letters)
            self.assertEqual(dispatcher.output_buffer, first[len(letters):])
            self.assertEqual(len(events), 0)

            dispatcher.output_buffer += second
            dispatcher.record_output()
            self.assertEqual(len(events), 0)
            [ x.flush() for x in dispatcher.childlog.handlers]
            self.assertEqual(open(logfile, 'r').read(), letters)
            self.assertEqual(dispatcher.output_buffer, first[len(letters):])
            self.assertEqual(len(events), 0)

            dispatcher.output_buffer += third
            dispatcher.record_output()
            [ x.flush() for x in dispatcher.childlog.handlers]
            self.assertEqual(open(logfile, 'r').read(), letters *2)
            self.assertEqual(len(events), 1)
            event = events[0]
            from supervisor.events import ProcessCommunicationStdoutEvent
            self.assertEqual(event.__class__, ProcessCommunicationStdoutEvent)
            self.assertEqual(event.process, process)
            self.assertEqual(event.channel, 'stdout')
            self.assertEqual(event.data, digits)

        finally:
            try:
                os.remove(logfile)
            except (OSError, IOError):
                pass
            try:
                os.remove(capturefile)
            except (OSError, IOError):
                pass

    def test_strip_ansi(self):
        options = DummyOptions()
        options.strip_ansi = True
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        ansi = '\x1b[34mHello world... this is longer than a token!\x1b[0m'
        noansi = 'Hello world... this is longer than a token!'

        dispatcher.output_buffer = ansi
        dispatcher.record_output()
        self.assertEqual(len(dispatcher.childlog.data), 1)
        self.assertEqual(dispatcher.childlog.data[0], noansi)

        options.strip_ansi = False

        dispatcher.output_buffer = ansi
        dispatcher.record_output()
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
        self.assertEqual(dispatcher.capturefile, None)
        self.assertEqual(dispatcher.capturelog, None)
        self.assertEqual(dispatcher.mainlog, None)
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
        self.assertEqual(dispatcher.capturefile, None)
        self.assertEqual(dispatcher.capturelog, None)
        self.assertEqual(dispatcher.mainlog.__class__, DummyLogger)
        self.assertEqual(dispatcher.childlog, dispatcher.mainlog)

    def test_ctor_capturelog_only(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_capturefile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.capturefile, '/tmp/foo')
        self.assertEqual(dispatcher.capturelog.__class__,DummyLogger)
        self.assertEqual(dispatcher.mainlog, None)
        self.assertEqual(dispatcher.childlog, None)

    def test_ctor_nologs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.process, process)
        self.assertEqual(dispatcher.channel, 'stdout')
        self.assertEqual(dispatcher.fd, 0)
        self.assertEqual(dispatcher.capturefile, None)
        self.assertEqual(dispatcher.capturelog, None)
        self.assertEqual(dispatcher.mainlog, None)
        self.assertEqual(dispatcher.childlog, None)


class PInputDispatcherTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.dispatchers import PInputDispatcher
        return PInputDispatcher

    def _makeOne(self, process):
        channel = 'stdin'
        return self._getTargetClass()(process, channel, 0)

    def test_writable_nodata(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'a'
        self.assertEqual(dispatcher.writable(), True)

    def test_writable_withdata(self):
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = ''
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
        self.assertEqual(dispatcher.input_buffer, '')
        dispatcher.handle_write_event
        self.assertEqual(dispatcher.input_buffer, '')
        self.assertEqual(options.written, {})

    def test_handle_write_event_epipe_raised(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'halloooo'
        import errno
        options.write_error = errno.EPIPE
        dispatcher.handle_write_event()
        self.assertEqual(dispatcher.input_buffer, '')
        self.assertEqual(options.logger.data,
            ["failed write to process 'test' stdin"])

    def test_handle_write_event_uncaught_raised(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        dispatcher.input_buffer = 'halloooo'
        import errno
        options.write_error = errno.EBADF
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
        process = DummyProcess(None)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_error)



class PEventListenerDispatcherTests(unittest.TestCase):
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
        
    def test_readable(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.readable(), True)

    def test_handle_write_event(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_write_event)

    def test_handle_read_event_nodata(self):
        options = DummyOptions()
        options.readfd_result = ''
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        from supervisor.dispatchers import EventListenerStates
        self.assertEqual(dispatcher.process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)

    def test_handle_read_event_logging_nologs(self):
        options = DummyOptions()
        options.readfd_result = 'supercalifragilisticexpialidocious'
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        # just make sure there are no errors if a child logger doesnt
        # exist
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.childlog, None)

    def test_handle_read_event_logging_childlog(self):
        options = DummyOptions()
        options.readfd_result = 'supercalifragilisticexpialidocious'
        config = DummyPConfig(options, 'process1', '/bin/process1',
                              stdout_logfile='/tmp/foo')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(len(dispatcher.childlog.data), 1)
        self.assertEqual(dispatcher.childlog.data[0],
                         'supercalifragilisticexpialidocious')

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
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(len(dispatcher.childlog.data), 1)
        self.assertEqual(dispatcher.childlog.data[0],
                         dispatcher.READY_FOR_EVENTS_TOKEN)

    def test_handle_listener_state_change_from_unknown(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.UNKNOWN
        dispatcher.state_buffer = 'whatever'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(options.logger.data, [])
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_acknowledged_to_ready(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher.state_buffer = 'READY\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(options.logger.data,
                         [5, 'process1: ACKNOWLEDGED -> READY'])
        self.assertEqual(process.listener_state, EventListenerStates.READY)

    def test_handle_listener_state_change_acknowledged_gobbles(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher.state_buffer = 'READY\ngarbage\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(options.logger.data[0:2],
                         [5, 'process1: ACKNOWLEDGED -> READY'])
        self.assertEqual(options.logger.data[2:4],
                         [5, 'process1: READY -> UNKNOWN'])
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_acknowledged_to_insufficient(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.ACKNOWLEDGED
        dispatcher.state_buffer = 'RE'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, 'RE')
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
        dispatcher.state_buffer = 'bogus data yo'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(options.logger.data,
                         [5, 'process1: ACKNOWLEDGED -> UNKNOWN'])
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_ready_to_unknown(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.READY
        dispatcher.state_buffer = 'bogus data yo'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(options.logger.data,
                         [5, 'process1: READY -> UNKNOWN'])
        self.assertEqual(process.listener_state, EventListenerStates.UNKNOWN)

    def test_handle_listener_state_change_busy_to_insufficient(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        dispatcher.state_buffer = 'bogus data yo'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, 'bogus data yo')
        self.assertEqual(process.listener_state, EventListenerStates.BUSY)

    def test_handle_listener_state_change_busy_to_acknowledged_procd(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        dispatcher.state_buffer = dispatcher.EVENT_PROCESSED_TOKEN + 'abc'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, 'abc')
        self.assertEqual(options.logger.data,
                         [5, 'process1: BUSY -> ACKNOWLEDGED (processed)'])
        self.assertEqual(process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)

    def test_handle_listener_state_change_busy_to_acknowledged_rejected(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        dispatcher.state_buffer = dispatcher.EVENT_REJECTED_TOKEN + 'abc'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, 'abc')
        self.assertEqual(options.logger.data,
                         [5, 'process1: BUSY -> ACKNOWLEDGED (rejected)'])
        self.assertEqual(process.listener_state,
                         EventListenerStates.ACKNOWLEDGED)

    def test_handle_listener_state_change_busy_to_unknown(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        dispatcher.state_buffer = 'bogus data\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(options.logger.data,
                         [5, 'process1: BUSY -> UNKNOWN'])
        self.assertEqual(process.listener_state,
                         EventListenerStates.UNKNOWN)

    def test_handle_listener_state_busy_gobbles(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        from supervisor.dispatchers import EventListenerStates
        dispatcher = self._makeOne(process)
        process.listener_state = EventListenerStates.BUSY
        dispatcher.state_buffer = 'OK\nbogus data\n'
        self.assertEqual(dispatcher.handle_listener_state_change(), None)
        self.assertEqual(dispatcher.state_buffer, '')
        self.assertEqual(options.logger.data[0:2],
                         [5, 'process1: BUSY -> ACKNOWLEDGED (processed)'])
        self.assertEqual(options.logger.data[2:4],
                         [5, 'process1: ACKNOWLEDGED -> UNKNOWN'])
        self.assertEqual(process.listener_state,
                         EventListenerStates.UNKNOWN)

    def test_handle_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'process1', '/bin/process1')
        process = DummyProcess(config)
        dispatcher = self._makeOne(process)
        self.assertRaises(NotImplementedError, dispatcher.handle_error)

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
        ansi = '\x1b[34mHello world... this is longer than a token!\x1b[0m'
        noansi = 'Hello world... this is longer than a token!'

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

    


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
