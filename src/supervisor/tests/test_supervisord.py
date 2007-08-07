import unittest
import time
import signal
import sys

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess

class SupervisordTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.supervisord import Supervisor
        return Supervisor

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test_main(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig('foo', 'foo', '/bin/foo')
        options.programs = [pconfig]
        supervisord.main(args='abc', test=True, first=True)
        self.assertEqual(options.realizeargs, 'abc')
        self.assertEqual(options.environment_processed, True)
        self.assertEqual(options.fds_cleaned_up, True)
        self.assertEqual(options.rlimits_set, True)
        self.assertEqual(options.make_logger_messages,
                         (['setuid_called'], ['rlimits_set']))
        self.assertEqual(options.autochildlogdir_cleared, True)
        self.assertEqual(options.autochildlogs_created, True)
        self.assertEqual(len(supervisord.processes), 1)
        self.assertEqual(supervisord.processes['foo'].options, options)
        self.assertEqual(options.pidfile_written, True)
        self.assertEqual(options.httpserver_opened, True)
        self.assertEqual(options.signals_set, True)
        self.assertEqual(options.daemonized, True)
        self.assertEqual(options.cleaned_up, True)

    def test_get_state(self):
        from supervisor.supervisord import SupervisorStates
        options = DummyOptions()
        supervisord = self._makeOne(options)
        self.assertEqual(supervisord.get_state(), SupervisorStates.ACTIVE)
        supervisord.mood = -1
        self.assertEqual(supervisord.get_state(), SupervisorStates.SHUTDOWN)

    def test_start_necessary(self):
        from supervisor.process import ProcessStates
        options = DummyOptions()
        pconfig1 = DummyPConfig('killed', 'killed', '/bin/killed')
        process1 = DummyProcess(options, pconfig1, ProcessStates.EXITED)
        pconfig2 = DummyPConfig('error', 'error', '/bin/error')
        process2 = DummyProcess(options, pconfig2, ProcessStates.FATAL)
        pconfig3 = DummyPConfig('notstarted', 'notstarted', '/bin/notstarted',
                                autostart=True)
        process3 = DummyProcess(options, pconfig3, ProcessStates.STOPPED)
        pconfig4 = DummyPConfig('wontstart', 'wonstart', '/bin/wontstart',
                                autostart=True)
        process4 = DummyProcess(options, pconfig4, ProcessStates.BACKOFF)
        pconfig5 = DummyPConfig('backingoff', 'backingoff', '/bin/backingoff',
                                autostart=True)
        process5 = DummyProcess(options, pconfig5, ProcessStates.BACKOFF)
        now = time.time()
        process5.delay = now + 1000

        supervisord = self._makeOne(options)
        supervisord.processes = {'killed': process1, 'error': process2,
                                 'notstarted':process3, 'wontstart':process4,
                                 'backingoff':process5}
        supervisord.start_necessary()
        self.assertEqual(process1.spawned, True)
        self.assertEqual(process2.spawned, False)
        self.assertEqual(process3.spawned, True)
        self.assertEqual(process4.spawned, True)
        self.assertEqual(process5.spawned, False)

    def test_stop_all(self):
        from supervisor.process import ProcessStates
        options = DummyOptions()
        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPED)
        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.RUNNING)
        pconfig3 = DummyPConfig('process3', 'process3', '/bin/process3')
        process3 = DummyProcess(options, pconfig3, state=ProcessStates.STARTING)
        pconfig4 = DummyPConfig('process4', 'process4', '/bin/process4')
        process4 = DummyProcess(options, pconfig4, state=ProcessStates.BACKOFF)
        process4.delay = 1000
        process4.backoff = 10
        supervisord = self._makeOne(options)
        supervisord.processes = {'process1': process1, 'process2': process2,
                                 'process3':process3, 'process4':process4}

        supervisord.stop_all()
        self.assertEqual(process1.stop_called, False)
        self.assertEqual(process2.stop_called, True)
        self.assertEqual(process3.stop_called, True)
        self.assertEqual(process4.stop_called, False)

        self.assertEqual(process4.delay, 0)
        self.assertEqual(process4.backoff, 0)
        self.assertEqual(process4.system_stop, 1)

        
    def test_transition(self):
        options = DummyOptions()

        from supervisor.process import ProcessStates

        # this should go to FATAL via transition()
        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.BACKOFF)
        process1.backoff = 10000
        process1.delay = 1
        process1.system_stop = 0

        # this should go to RUNNING via transition()
        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.STARTING)
        process2.backoff = 1
        process2.delay = 1
        process2.system_stop = 0
        process2.laststart = 1

        supervisord = self._makeOne(options)
        supervisord.processes = { 'process1': process1, 'process2': process2 }

        supervisord.transition()

        # this implies FATAL
        self.assertEqual(process1.backoff, 0)
        self.assertEqual(process1.delay, 0)
        self.assertEqual(process1.system_stop, 1)

        # this implies RUNNING
        self.assertEqual(process2.backoff, 0)
        self.assertEqual(process2.delay, 0)
        self.assertEqual(process2.system_stop, 0)

    def test_get_undead(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates

        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1

        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.STOPPING)
        process2.delay = time.time() + 1000

        pconfig3 = DummyPConfig('process3', 'process3', '/bin/process3')
        process3 = DummyProcess(options, pconfig3, state=ProcessStates.RUNNING)

        supervisord = self._makeOne(options)
        supervisord.processes = { 'process1': process1, 'process2': process2,
                                  'process3':process3 }

        undead = supervisord.get_undead()
        self.assertEqual(undead, [process1])

    def test_kill_undead(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates

        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1

        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.STOPPING)
        process2.delay = time.time() + 1000

        supervisord = self._makeOne(options)
        supervisord.processes = { 'process1': process1, 'process2': process2}

        supervisord.kill_undead()
        self.assertEqual(process1.killed_with, signal.SIGKILL)

    def test_reap(self):
        options = DummyOptions()
        options.waitpid_return = 1, 1
        pconfig = DummyPConfig('process', 'process', '/bin/process1')
        process = DummyProcess(options, pconfig)
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
        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        from supervisor.process import ProcessStates
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1
        supervisord = self._makeOne(options)
        supervisord.processes = {'process1':process1}
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, 1)
        self.assertEqual(options.logs_reopened, True)
        self.assertEqual(process1.logs_reopened, True)
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

