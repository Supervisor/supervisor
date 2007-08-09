import unittest
import time
import signal
import sys

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyPGroupConfig
from supervisor.tests.base import DummyProcess

class SupervisordTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.supervisord import Supervisor
        return Supervisor

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test_main(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', '/bin/foo')
        gconfigs = [DummyPGroupConfig(options,'foo', pconfigs=[pconfig])]
        options.process_group_configs = gconfigs
        supervisord = self._makeOne(options)
        supervisord.main(args='abc', test=True, first=True)
        self.assertEqual(options.realizeargs, 'abc')
        self.assertEqual(options.environment_processed, True)
        self.assertEqual(options.fds_cleaned_up, True)
        self.assertEqual(options.rlimits_set, True)
        self.assertEqual(options.make_logger_messages,
                         (['setuid_called'], ['rlimits_set']))
        self.assertEqual(options.autochildlogdir_cleared, True)
        self.assertEqual(len(supervisord.process_groups), 1)
        self.assertEqual(supervisord.process_groups['foo'].config.options,
                         options)
        self.assertEqual(options.environment_processed, True)
        self.assertEqual(options.httpserver_opened, True)
        self.assertEqual(options.signals_set, True)
        self.assertEqual(options.daemonized, True)
        self.assertEqual(options.pidfile_written, True)
        self.assertEqual(options.cleaned_up, True)

    def test_get_state(self):
        from supervisor.supervisord import SupervisorStates
        options = DummyOptions()
        supervisord = self._makeOne(options)
        self.assertEqual(supervisord.get_state(), SupervisorStates.ACTIVE)
        supervisord.mood = -1
        self.assertEqual(supervisord.get_state(), SupervisorStates.SHUTDOWN)

    def test_reap(self):
        options = DummyOptions()
        options.waitpid_return = 1, 1
        pconfig = DummyPConfig(options, 'process', 'process', '/bin/process1')
        process = DummyProcess(pconfig)
        process.drained = False
        process.killing = 1
        process.laststop = None
        process.waitstatus = None, None
        options.pidhistory = {1:process}
        supervisord = self._makeOne(options)
        
        supervisord.reap(once=True)
        self.assertEqual(process.finished, (1,1))

    def test_handle_sigterm(self):
        options = DummyOptions()
        options.signal = signal.SIGTERM
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, -1)
        self.assertEqual(options.logger.data[0],
                         'received SIGTERM indicating exit request')

    def test_handle_sigint(self):
        options = DummyOptions()
        options.signal = signal.SIGINT
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, -1)
        self.assertEqual(options.logger.data[0],
                         'received SIGINT indicating exit request')

    def test_handle_sigquit(self):
        options = DummyOptions()
        options.signal = signal.SIGQUIT
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, -1)
        self.assertEqual(options.logger.data[0],
                         'received SIGQUIT indicating exit request')

    def test_handle_sighup(self):
        options = DummyOptions()
        options.signal = signal.SIGHUP
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, 0)
        self.assertEqual(options.logger.data[0],
                         'received SIGHUP indicating restart request')

    def test_handle_sigusr2(self):
        options = DummyOptions()
        options.signal = signal.SIGUSR2
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        from supervisor.process import ProcessStates
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1
        supervisord = self._makeOne(options)
        pconfigs = [DummyPConfig(options, 'foo', 'foo', '/bin/foo')]
        options.process_group_configs = DummyPGroupConfig(
            options, 'foo',
            pconfigs=pconfigs)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, 1)
        self.assertEqual(options.logs_reopened, True)
        self.assertEqual(options.logger.data[0],
                         'received SIGUSR2 indicating log reopen request')

    def test_handle_unknown_signal(self):
        options = DummyOptions()
        options.signal = signal.SIGUSR1
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, 1)
        self.assertEqual(options.logger.data[0],
                         'received SIGUSR1 indicating nothing')

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

