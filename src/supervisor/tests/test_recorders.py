import unittest
import os
import sys

from supervisor.tests.base import DummyOptions

class LoggingRecorderTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.recorders import LoggingRecorder
        return LoggingRecorder

    def _makeOne(self, options, procname, channel, logfile, logfile_backups,
                 logfile_maxbytes, capturefile):
        return self._getTargetClass()(options, procname, channel, logfile,
                                      logfile_backups, logfile_maxbytes,
                                      capturefile)

    def test_toggle_capturemode_buffer_overrun(self):
        executable = '/bin/cat'
        options = DummyOptions()
        from StringIO import StringIO
        options.openreturn = StringIO('a' * (3 << 20)) # > 2MB
        instance = self._makeOne(options, 'whatever', 'stdout',
                                 '/tmp/log', None, None, '/tmp/capture')
        instance.capturemode = True
        events = []
        def doit(event):
            events.append(event)
        instance.toggle_capturemode()
        result = options.logger.data[0]
        self.failUnless(result.startswith('Truncated oversized'), result)

    def test_removelogs(self):
        options = DummyOptions()
        instance = self._makeOne(options, 'whatever', 'stdout',
                                 '/tmp/log', None, None, '/tmp/capture')
        instance.removelogs()
        self.assertEqual(instance.childlog.handlers[0].reopened, True)
        self.assertEqual(instance.childlog.handlers[0].removed, True)
        self.assertEqual(instance.childlog.handlers[0].reopened, True)
        self.assertEqual(instance.childlog.handlers[0].removed, True)

    def test_reopenlogs(self):
        options = DummyOptions()
        instance = self._makeOne(options, 'whatever', 'stdout',
                                 '/tmp/log', None, None, '/tmp/capture')
        instance.reopenlogs()
        self.assertEqual(instance.childlog.handlers[0].reopened, True)

    def test_record_output(self):
        # stdout/stderr goes to the process log and the main log
        options = DummyOptions()
        instance = self._makeOne(options, 'whatever', 'stdout',
                                 '/tmp/log', None, 100, '/tmp/capture')
        instance.output_buffer = 'stdout string longer than a token'
        instance.record_output()
        self.assertEqual(instance.childlog.data,
                         ['stdout string longer than a token'])
        self.assertEqual(options.logger.data[0], 5)
        self.assertEqual(options.logger.data[1],
             "'whatever' stdout output:\nstdout string longer than a token")

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
        instance = self._makeOne(options, 'whatever', 'stdout',
                                 logfile, None, None, capturefile)

        try:
            instance.output_buffer = first
            instance.record_output()
            [ x.flush() for x in instance.childlog.handlers]
            self.assertEqual(open(logfile, 'r').read(), letters)
            self.assertEqual(instance.output_buffer, first[len(letters):])
            self.assertEqual(len(events), 0)

            instance.output_buffer += second
            instance.record_output()
            self.assertEqual(len(events), 0)
            [ x.flush() for x in instance.childlog.handlers]
            self.assertEqual(open(logfile, 'r').read(), letters)
            self.assertEqual(instance.output_buffer, first[len(letters):])
            self.assertEqual(len(events), 0)

            instance.output_buffer += third
            instance.record_output()
            [ x.flush() for x in instance.childlog.handlers]
            self.assertEqual(open(logfile, 'r').read(), letters *2)
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event.__class__, ProcessCommunicationEvent)
            self.assertEqual(event.process_name, 'whatever')
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
        instance = self._makeOne(options, 'whatever', 'stdout',
                                 '/tmp/log', None, 100, '/tmp/capture')
        ansi = '\x1b[34mHello world... this is longer than a token!\x1b[0m'
        noansi = 'Hello world... this is longer than a token!'

        instance.output_buffer = ansi
        instance.record_output()
        self.assertEqual(len(instance.childlog.data), 1)
        self.assertEqual(instance.childlog.data[0], noansi)

        options.strip_ansi = False

        instance.output_buffer = ansi
        instance.record_output()
        self.assertEqual(len(instance.childlog.data), 2)
        self.assertEqual(instance.childlog.data[1], ansi)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
