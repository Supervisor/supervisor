import os
import signal
import time
import unittest
import sys

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyPGroupConfig
from supervisor.tests.base import DummyDispatcher

class SubprocessTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import Subprocess
        return Subprocess

    def _makeOne(self, *arg, **kw):
        return self._getTargetClass()(*arg, **kw)

    def tearDown(self):
        from supervisor.events import clear
        clear()

    def test_getProcessStateDescription(self):
        from supervisor.process import ProcessStates
        from supervisor.process import getProcessStateDescription
        for statename, code in ProcessStates.__dict__.items():
            self.assertEqual(getProcessStateDescription(code), statename)

    def test_ctor(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'cat', 'bin/cat',
                              stdout_logfile='/tmp/temp123.log',
                              stderr_logfile='/tmp/temp456.log')
        instance = self._makeOne(config)
        self.assertEqual(instance.config, config)
        self.assertEqual(instance.config.options, options)
        self.assertEqual(instance.laststart, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(instance.laststart, 0)
        self.assertEqual(instance.laststop, 0)
        self.assertEqual(instance.delay, 0)
        self.assertEqual(instance.administrative_stop, 0)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.backoff, 0)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(instance.spawnerr, None)

    def test_repr(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'cat', 'bin/cat')
        instance = self._makeOne(config)
        s = repr(instance)
        self.assertTrue(s.startswith('<Subprocess at'))
        self.assertTrue(s.endswith('with name cat in state STOPPED>'))

    def test_reopenlogs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.dispatchers = {0:DummyDispatcher(readable=True),
                                1:DummyDispatcher(writable=True)}
        instance.reopenlogs()
        self.assertEqual(instance.dispatchers[0].logs_reopened, True)
        self.assertEqual(instance.dispatchers[1].logs_reopened, False)
        
    def test_removelogs(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.dispatchers = {0:DummyDispatcher(readable=True),
                                1:DummyDispatcher(writable=True)}
        instance.removelogs()
        self.assertEqual(instance.dispatchers[0].logs_removed, True)
        self.assertEqual(instance.dispatchers[1].logs_removed, False)

    def test_drain(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test',
                              stdout_logfile='/tmp/foo',
                              stderr_logfile='/tmp/bar')
        instance = self._makeOne(config)
        instance.dispatchers = {0:DummyDispatcher(readable=True),
                                1:DummyDispatcher(writable=True)}
        instance.drain()
        self.assertTrue(instance.dispatchers[0].read_event_handled)
        self.assertTrue(instance.dispatchers[1].write_event_handled)
        
    def test_get_execv_args_abs_missing(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere')
        instance = self._makeOne(config)
        args = instance.get_execv_args()
        self.assertEqual(args, ('/notthere', ['/notthere']))

    def test_get_execv_args_abs_withquotes_missing(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere "an argument"')
        instance = self._makeOne(config)
        args = instance.get_execv_args()
        self.assertEqual(args, ('/notthere', ['/notthere', 'an argument']))

    def test_get_execv_args_rel_missing(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', 'notthere')
        instance = self._makeOne(config)
        args = instance.get_execv_args()
        self.assertEqual(args, (None, ['notthere']))

    def test_get_execv_args_rel_withquotes_missing(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', 'notthere "an argument"')
        instance = self._makeOne(config)
        args = instance.get_execv_args()
        self.assertEqual(args, (None, ['notthere', 'an argument']))

    def test_get_execv_args_abs(self):
        executable = '/bin/sh foo'
        options = DummyOptions()
        config = DummyPConfig(options, 'sh', executable)
        instance = self._makeOne(config)
        args = instance.get_execv_args()
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0], '/bin/sh')
        self.assertEqual(args[1], ['/bin/sh', 'foo'])

    def test_get_execv_args_rel(self):
        executable = 'sh foo'
        options = DummyOptions()
        config = DummyPConfig(options, 'sh', executable)
        instance = self._makeOne(config)
        args = instance.get_execv_args()
        self.assertEqual(len(args), 2)
        self.assertEqual(args[0], '/bin/sh')
        self.assertEqual(args[1], ['sh', 'foo'])

    def test_record_spawnerr(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.record_spawnerr('foo')
        self.assertEqual(instance.spawnerr, 'foo')
        self.assertEqual(options.logger.data[0], 'spawnerr: foo')
        self.assertEqual(instance.backoff, 1)
        self.failUnless(instance.delay)

    def test_spawn_already_running(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'sh', '/bin/sh')
        instance = self._makeOne(config)
        instance.pid = True
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.RUNNING
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.logger.data[0], "process 'sh' already running")
        self.assertEqual(instance.state, ProcessStates.RUNNING)

    def test_spawn_fail_check_execv_args(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'bad', '/bad/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateChangeEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'bad filename')
        self.assertEqual(options.logger.data[0], "spawnerr: bad filename")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(L[0].__class__, events.StartingFromBackoffEvent)
        self.assertEqual(L[1].__class__, events.BackoffFromStartingEvent)

    def test_spawn_fail_make_pipes_emfile(self):
        options = DummyOptions()
        import errno
        options.make_pipes_error = errno.EMFILE
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateChangeEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr,
                         "too many open files to spawn 'good'")
        self.assertEqual(options.logger.data[0],
                         "spawnerr: too many open files to spawn 'good'")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(L[0].__class__, events.StartingFromBackoffEvent)
        self.assertEqual(L[1].__class__, events.BackoffFromStartingEvent)

    def test_spawn_fail_make_pipes_other(self):
        options = DummyOptions()
        options.make_pipes_error = 1
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateChangeEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'unknown error: EPERM')
        self.assertEqual(options.logger.data[0],
                         "spawnerr: unknown error: EPERM")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(L[0].__class__, events.StartingFromBackoffEvent)
        self.assertEqual(L[1].__class__, events.BackoffFromStartingEvent)

    def test_spawn_fork_fail_eagain(self):
        options = DummyOptions()
        import errno
        options.fork_error = errno.EAGAIN
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateChangeEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr,
                         "Too many processes in process table to spawn 'good'")
        self.assertEqual(options.logger.data[0],
             "spawnerr: Too many processes in process table to spawn 'good'")
        self.assertEqual(len(options.parent_pipes_closed), 6)
        self.assertEqual(len(options.child_pipes_closed), 6)
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(L[0].__class__, events.StartingFromBackoffEvent)
        self.assertEqual(L[1].__class__, events.BackoffFromStartingEvent)

    def test_spawn_fork_fail_other(self):
        options = DummyOptions()
        options.fork_error = 1
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateChangeEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'unknown error: EPERM')
        self.assertEqual(options.logger.data[0],
                         "spawnerr: unknown error: EPERM")
        self.assertEqual(len(options.parent_pipes_closed), 6)
        self.assertEqual(len(options.child_pipes_closed), 6)
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(L[0].__class__, events.StartingFromBackoffEvent)
        self.assertEqual(L[1].__class__, events.BackoffFromStartingEvent)

    def test_spawn_as_child_setuid_ok(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(options.child_pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.written, {})
        self.assertEqual(options.privsdropped, 1)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_setuid_fail(self):
        options = DummyOptions()
        options.forkpid = 0
        options.setuid_msg = 'screwed'
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(options.child_pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.written,
             {1: 'supervisor: error trying to setuid to 1 (screwed)\n'})
        self.assertEqual(options.privsdropped, None)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_execv_fail_oserror(self):
        options = DummyOptions()
        options.forkpid = 0
        options.execv_error = 1
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(options.child_pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.written,
                         {1: "couldn't exec /good/filename: EPERM\n"})
        self.assertEqual(options.privsdropped, None)
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_execv_fail_runtime_error(self):
        options = DummyOptions()
        options.forkpid = 0
        options.execv_error = 2
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(options.child_pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(len(options.written), 1)
        msg = options.written[1]
        self.failUnless(msg.startswith("couldn't exec /good/filename:"))
        self.failUnless("exceptions.RuntimeError" in msg)
        self.assertEqual(options.privsdropped, None)
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_uses_pconfig_environment(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'cat', '/bin/cat',
                              environment={'_TEST_':'1'})
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.execv_args, ('/bin/cat', ['/bin/cat']) )
        self.assertEqual(options.execv_environment['_TEST_'], '1')

    def test_spawn_as_child_stderr_redirected(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        config.redirect_stderr = True
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(options.child_pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 2)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.written, {})
        self.assertEqual(options.privsdropped, 1)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_parent(self):
        options = DummyOptions()
        options.forkpid = 10
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, 10)
        self.assertEqual(instance.dispatchers[4].__class__, DummyDispatcher)
        self.assertEqual(instance.dispatchers[5].__class__, DummyDispatcher)
        self.assertEqual(instance.dispatchers[7].__class__, DummyDispatcher)
        self.assertEqual(instance.pipes['stdin'], 4)
        self.assertEqual(instance.pipes['stdout'], 5)
        self.assertEqual(instance.pipes['stderr'], 7)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(len(options.child_pipes_closed), 6)
        self.assertEqual(options.logger.data[0], "spawned: 'good' with pid 10")
        self.assertEqual(instance.spawnerr, None)
        self.failUnless(instance.delay)
        self.assertEqual(instance.config.options.pidhistory[10], instance)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.STARTING)

    def test_spawn_redirect_stderr(self):
        options = DummyOptions()
        options.forkpid = 10
        config = DummyPConfig(options, 'good', '/good/filename',
                              redirect_stderr=True)
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, 10)
        self.assertEqual(instance.dispatchers[4].__class__, DummyDispatcher)
        self.assertEqual(instance.dispatchers[5].__class__, DummyDispatcher)
        self.assertEqual(instance.pipes['stdin'], 4)
        self.assertEqual(instance.pipes['stdout'], 5)
        self.assertEqual(instance.pipes['stderr'], None)

    def test_write(self):
        executable = '/bin/cat'
        options = DummyOptions()
        config = DummyPConfig(options, 'output', executable)
        instance = self._makeOne(config)
        sent = 'a' * (1 << 13)
        self.assertRaises(IOError, instance.write, sent)
        options.forkpid = 1
        result = instance.spawn()
        instance.write(sent)
        stdin_fd = instance.pipes['stdin']
        self.assertEqual(sent, instance.dispatchers[stdin_fd].input_buffer)
        instance.killing = True
        self.assertRaises(IOError, instance.write, sent)

    def dont_test_spawn_and_kill(self):
        # this is a functional test
        from supervisor.tests.base import makeSpew
        try:
            called = 0
            def foo(*args):
                called = 1
            signal.signal(signal.SIGCHLD, foo)
            executable = makeSpew()
            options = DummyOptions()
            config = DummyPConfig(options, 'spew', executable)
            instance = self._makeOne(config)
            result = instance.spawn()
            msg = options.logger.data[0]
            self.failUnless(msg.startswith("spawned: 'spew' with pid"))
            self.assertEqual(len(instance.pipes), 6)
            self.failUnless(instance.pid)
            self.failUnlessEqual(instance.pid, result)
            origpid = instance.pid
            import errno
            while 1:
                try:
                    data = os.popen('ps').read()
                    break
                except IOError, why:
                    if why[0] != errno.EINTR:
                        raise
                        # try again ;-)
            time.sleep(0.1) # arbitrary, race condition possible
            self.failUnless(data.find(`origpid`) != -1 )
            msg = instance.kill(signal.SIGTERM)
            time.sleep(0.1) # arbitrary, race condition possible
            self.assertEqual(msg, None)
            pid, sts = os.waitpid(-1, os.WNOHANG)
            data = os.popen('ps').read()
            self.assertEqual(data.find(`origpid`), -1) # dubious
        finally:
            try:
                os.remove(executable)
            except:
                pass
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    def test_stop(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        dispatcher = DummyDispatcher(writable=True)
        instance.dispatchers = {'foo':dispatcher}
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.RUNNING
        instance.stop()
        self.assertEqual(instance.administrative_stop, 1)
        self.failUnless(instance.delay)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertEqual(instance.killing, 1)
        self.assertEqual(options.kills[11], signal.SIGTERM)
        self.assertEqual(dispatcher.write_event_handled, True)

    def test_fatal(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.FatalFromBackoffEvent, lambda x: L.append(x))
        instance.state = ProcessStates.BACKOFF
        instance.fatal()
        self.assertEqual(instance.system_stop, 1)
        self.assertFalse(instance.delay)
        self.assertFalse(instance.backoff)
        self.assertEqual(instance.state, ProcessStates.FATAL)
        self.assertEqual(L[0].__class__, events.FatalFromBackoffEvent)

    def test_kill_nopid(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0],
              'attempted to kill test with sig SIGTERM but it wasn\'t running')
        self.assertEqual(instance.killing, 0)

    def test_kill_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        options.kill_error = 1
        instance = self._makeOne(config)
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.ProcessStateChangeEvent,
                         lambda x: L.append(x))
        instance.pid = 11
        instance.state = ProcessStates.RUNNING
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.failUnless(options.logger.data[1].startswith(
            'unknown problem killing test'))
        self.assertEqual(instance.killing, 0)
        self.assertEqual(L[0].__class__, events.StoppingFromRunningEvent)
        self.assertEqual(L[1].__class__, events.ToUnknownEvent)

    def test_kill_from_starting(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.StoppingFromStartingEvent,lambda x: L.append(x))
        from supervisor.process import ProcessStates
        instance.state = ProcessStates.STARTING
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertEqual(instance.killing, 1)
        self.assertEqual(options.kills[11], signal.SIGTERM)
        self.assertEqual(L[0].__class__, events.StoppingFromStartingEvent)

    def test_kill_from_running(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.StoppingFromRunningEvent, lambda x: L.append(x))
        from supervisor.process import ProcessStates
        instance.state = ProcessStates.RUNNING
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertEqual(instance.killing, 1)
        self.assertEqual(options.kills[11], signal.SIGTERM)
        self.assertEqual(L[0].__class__, events.StoppingFromRunningEvent)

    def test_finish(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo')
        instance = self._makeOne(config)
        instance.waitstatus = (123, 1) # pid, waitstatus
        instance.config.options.pidhistory[123] = instance
        instance.killing = 1
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        from supervisor.states import ProcessStates
        from supervisor import events
        instance.state = ProcessStates.STOPPING
        L = []
        events.subscribe(events.StoppedFromStoppingEvent, lambda x: L.append(x))
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0], 'stopped: notthere '
                         '(terminated by SIGHUP)')
        self.assertEqual(instance.exitstatus, -1)
        self.assertEqual(L[0].__class__, events.StoppedFromStoppingEvent)

    def test_finish_expected(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo')
        instance = self._makeOne(config)
        instance.config.options.pidhistory[123] = instance
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        instance.config.exitcodes =[-1]
        from supervisor.states import ProcessStates
        from supervisor import events
        instance.state = ProcessStates.RUNNING
        L = []
        events.subscribe(events.ExitedFromRunningEvent, lambda x: L.append(x))
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0],
                         'exited: notthere (terminated by SIGHUP; expected)')
        self.assertEqual(instance.exitstatus, -1)
        self.assertEqual(L[0].__class__, events.ExitedFromRunningEvent)

    def test_finish_unexpected(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo', startsecs=10)
        instance = self._makeOne(config)
        instance.config.options.pidhistory[123] = instance
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        instance.config.exitcodes =[-1]
        import time
        instance.laststart = time.time()
        from supervisor.states import ProcessStates
        from supervisor import events
        instance.state = ProcessStates.STARTING
        L = []
        events.subscribe(events.BackoffFromStartingEvent, lambda x: L.append(x))
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0],
                      'exited: notthere (terminated by SIGHUP; not expected)')
        self.assertEqual(instance.exitstatus, None)
        self.assertEqual(L[0].__class__, events.BackoffFromStartingEvent)

    def test_set_uid_no_uid(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.set_uid()
        self.assertEqual(options.privsdropped, None)

    def test_set_uid(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test', uid=1)
        instance = self._makeOne(config)
        msg = instance.set_uid()
        self.assertEqual(options.privsdropped, 1)
        self.assertEqual(msg, None)

    def test_cmp_bypriority(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo',
                              priority=1)
        instance = self._makeOne(config)

        config = DummyPConfig(options, 'notthere1', '/notthere',
                              stdout_logfile='/tmp/foo',
                              priority=2)
        instance1 = self._makeOne(config)

        config = DummyPConfig(options, 'notthere2', '/notthere',
                              stdout_logfile='/tmp/foo',
                              priority=3)
        instance2 = self._makeOne(config)

        L = [instance2, instance, instance1]
        L.sort()

        self.assertEqual(L, [instance, instance1, instance2])

    def test_transition(self):
        options = DummyOptions()

        from supervisor.process import ProcessStates

        # this should go from BACKOFF to FATAL via transition()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = self._makeOne(pconfig1)
        process1.laststart = 1
        process1.backoff = 10000
        process1.delay = 1
        process1.system_stop = 0
        process1.stdout_buffer = 'abc'
        process1.stderr_buffer = 'def'
        process1.state = ProcessStates.BACKOFF

        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateChangeEvent, lambda x: L.append(x))

        process1.transition()

        # this implies FATAL
        self.assertEqual(process1.backoff, 0)
        self.assertEqual(process1.delay, 0)
        self.assertEqual(process1.system_stop, 1)
        self.assertEqual(options.logger.data[0],
                         'gave up: process1 entered FATAL state, too many start'
                         ' retries too quickly')
        self.assertEqual(L[0].__class__, events.FatalFromBackoffEvent)


        # this should go from STARTING to RUNNING via transition()
        pconfig2 = DummyPConfig(options, 'process2', 'process2','/bin/process2')
        process2 = self._makeOne(pconfig2)
        process2.backoff = 1
        process2.delay = 1
        process2.system_stop = 0
        process2.laststart = 1
        process2.pid = 1
        process2.stdout_buffer = 'abc'
        process2.stderr_buffer = 'def'
        process2.state = ProcessStates.STARTING

        process2.transition()

        # this implies RUNNING
        self.assertEqual(process2.backoff, 0)
        self.assertEqual(process2.delay, 0)
        self.assertEqual(process2.system_stop, 0)
        self.assertEqual(options.logger.data[1],
                         'success: process2 entered RUNNING state, process has '
                         'stayed up for > than 10 seconds (startsecs)')
        self.assertEqual(L[1].__class__, events.RunningFromStartingEvent)

    def test_change_state_doesnt_notify_if_no_state_change(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.state = 10
        self.assertEqual(instance.change_state(10), False)

class ProcessGroupBaseTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import ProcessGroupBase
        return ProcessGroupBase

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_get_delay_processes(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        process1.delay = 1
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = { 'process1': process1 }
        delayed = group.get_delay_processes()
        self.assertEqual(delayed, [process1])
        
    def test_get_undead(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates

        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1

        pconfig2 = DummyPConfig(options, 'process2', 'process2','/bin/process2')
        process2 = DummyProcess(pconfig2, state=ProcessStates.STOPPING)
        process2.delay = time.time() + 1000

        pconfig3 = DummyPConfig(options, 'process3', 'process3','/bin/process3')
        process3 = DummyProcess(pconfig3, state=ProcessStates.RUNNING)

        gconfig = DummyPGroupConfig(options,
                                    pconfigs=[pconfig1, pconfig2, pconfig3])
        group = self._makeOne(gconfig)
        group.processes = { 'process1': process1, 'process2': process2,
                            'process3':process3 }

        undead = group.get_undead()
        self.assertEqual(undead, [process1])

    def test_kill_undead(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates

        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1

        pconfig2 = DummyPConfig(options, 'process2', 'process2','/bin/process2')
        process2 = DummyProcess(pconfig2, state=ProcessStates.STOPPING)
        process2.delay = time.time() + 1000

        gconfig = DummyPGroupConfig(
            options,
            pconfigs=[pconfig1, pconfig2])
        group = self._makeOne(gconfig)
        group.processes = { 'process1': process1, 'process2': process2}

        group.kill_undead()
        self.assertEqual(process1.killed_with, signal.SIGKILL)

    def test_start_necessary(self):
        from supervisor.process import ProcessStates
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'killed', 'killed', '/bin/killed')
        process1 = DummyProcess(pconfig1, ProcessStates.EXITED)
        pconfig2 = DummyPConfig(options, 'error', 'error', '/bin/error')
        process2 = DummyProcess(pconfig2, ProcessStates.FATAL)

        pconfig3 = DummyPConfig(options, 'notstarted', 'notstarted',
                                '/bin/notstarted', autostart=True)
        process3 = DummyProcess(pconfig3, ProcessStates.STOPPED)
        pconfig4 = DummyPConfig(options, 'wontstart', 'wonstart',
                                '/bin/wontstart', autostart=True)
        process4 = DummyProcess(pconfig4, ProcessStates.BACKOFF)
        pconfig5 = DummyPConfig(options, 'backingoff', 'backingoff',
                                '/bin/backingoff', autostart=True)
        process5 = DummyProcess(pconfig5, ProcessStates.BACKOFF)
        now = time.time()
        process5.delay = now + 1000

        gconfig = DummyPGroupConfig(
            options,
            pconfigs=[pconfig1, pconfig2, pconfig3, pconfig4, pconfig5])
        group = self._makeOne(gconfig)
        group.processes = {'killed': process1, 'error': process2,
                           'notstarted':process3, 'wontstart':process4,
                           'backingoff':process5}
        group.start_necessary()
        self.assertEqual(process1.spawned, True)
        self.assertEqual(process2.spawned, False)
        self.assertEqual(process3.spawned, True)
        self.assertEqual(process4.spawned, True)
        self.assertEqual(process5.spawned, False)

    def test_stop_all(self):
        from supervisor.process import ProcessStates
        options = DummyOptions()

        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPED)

        pconfig2 = DummyPConfig(options, 'process2', 'process2','/bin/process2')
        process2 = DummyProcess(pconfig2, state=ProcessStates.RUNNING)

        pconfig3 = DummyPConfig(options, 'process3', 'process3','/bin/process3')
        process3 = DummyProcess(pconfig3, state=ProcessStates.STARTING)
        pconfig4 = DummyPConfig(options, 'process4', 'process4','/bin/process4')
        process4 = DummyProcess(pconfig4, state=ProcessStates.BACKOFF)
        process4.delay = 1000
        process4.backoff = 10
        gconfig = DummyPGroupConfig(
            options,
            pconfigs=[pconfig1, pconfig2, pconfig3, pconfig4])
        group = self._makeOne(gconfig)
        group.processes = {'process1': process1, 'process2': process2,
                           'process3':process3, 'process4':process4}

        group.stop_all()
        self.assertEqual(process1.stop_called, False)
        self.assertEqual(process2.stop_called, True)
        self.assertEqual(process3.stop_called, True)
        self.assertEqual(process4.stop_called, False)
        self.assertEqual(process4.state, ProcessStates.FATAL)

    def test_get_dispatchers(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        process1.dispatchers = {4:None}
        pconfig2 = DummyPConfig(options, 'process2', 'process2','/bin/process2')
        process2 = DummyProcess(pconfig2, state=ProcessStates.STOPPING)
        process2.dispatchers = {5:None}
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1, pconfig2])
        group = self._makeOne(gconfig)
        group.processes = { 'process1': process1, 'process2': process2 }
        result= group.get_dispatchers()
        self.assertEqual(result, {4:None, 5:None})
        
    def test_reopenlogs(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = {'process1': process1}
        group.reopenlogs()
        self.assertEqual(process1.logs_reopened, True)

    def test_removelogs(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = {'process1': process1}
        group.removelogs()
        self.assertEqual(process1.logsremoved, True)

    def test_cmp(self):
        options = DummyOptions()
        gconfig1 = DummyPGroupConfig(options)
        group1 = self._makeOne(gconfig1)
        
        gconfig2 = DummyPGroupConfig(options)
        group2 = self._makeOne(gconfig2)

        group1.priority = 5
        group2.priority = 1

        L = [group1, group2]
        L.sort()

        self.assertEqual(L, [group2, group1])

class ProcessGroupTests(ProcessGroupBaseTests):
    def _getTargetClass(self):
        from supervisor.process import ProcessGroup
        return ProcessGroup

    def test_repr(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        group = self._makeOne(gconfig)
        s = repr(group)
        self.assertTrue(s.startswith(
            '<supervisor.process.ProcessGroup instance at'), s)
        self.assertTrue(s.endswith('named whatever>'), s)

    def test_transition(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = {'process1': process1}
        group.transition()
        self.assertEqual(process1.transitioned, True)
        
class EventListenerPoolTests(ProcessGroupBaseTests):
    def setUp(self):
        from supervisor.events import clear
        clear()

    def tearDown(self):
        from supervisor.events import clear
        clear()
        
    def _getTargetClass(self):
        from supervisor.process import EventListenerPool
        return EventListenerPool

    def test_ctor(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        class EventType:
            pass
        gconfig.pool_events = (EventType,)
        pool = self._makeOne(gconfig)
        from supervisor import events
        self.assertEqual(len(events.callbacks), 2)
        self.assertEqual(events.callbacks[0], 
            (EventType, pool._dispatchEvent))
        self.assertEqual(events.callbacks[1], 
            (events.EventRejectedEvent, pool.handle_rejected))

    def test_handle_rejected(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        class DummyEvent1:
            pass
        class DummyEvent2:
            process = process1
            event = DummyEvent1()
        dummyevent = DummyEvent2()
        pool.handle_rejected(dummyevent)
        self.assertEqual(pool.event_buffer, [dummyevent.event])
        
    def test_handle_rejected_event_buffer_overflowed(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        gconfig.buffer_size = 1
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        class DummyEvent1:
            pass
        class DummyEvent2:
            process = process1
            event = DummyEvent1()
        dummyevent_a = DummyEvent2()
        dummyevent_b = DummyEvent2()
        pool.event_buffer = [dummyevent_a]
        pool.handle_rejected(dummyevent_b)
        self.assertEqual(pool.event_buffer, [dummyevent_b.event])
        self.assertTrue(pool.config.options.logger.data[0].startswith(
            'pool whatever event buffer overflowed, discarding'))

    def test__bufferEvent_doesnt_rebufer_overflow_events(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.event_buffer = [1]
        from supervisor.events import EventBufferOverflowEvent
        overflow = EventBufferOverflowEvent(pool, None)
        pool._bufferEvent(overflow)
        self.assertEqual(pool.event_buffer, [1])

    def test__dispatchEvent_pipe_error(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        from supervisor.states import EventListenerStates
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        process1 = pool.processes['process1']
        import errno
        process1.write_error = errno.EPIPE
        process1.listener_state = EventListenerStates.READY
        from supervisor.events import StartingFromStoppedEvent
        event = StartingFromStoppedEvent(process1)
        pool._dispatchEvent(event)
        self.assertEqual(process1.stdin_buffer, '')
        self.assertEqual(process1.listener_state, EventListenerStates.READY)

    def test_repr(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pool = self._makeOne(gconfig)
        s = repr(pool)
        self.assertTrue(s.startswith(
            '<supervisor.process.EventListenerPool instance at'))
        self.assertTrue(s.endswith('named whatever>'))

    def test_transition_nobody_listenening(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STARTING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        from supervisor.events import StartingFromStoppedEvent
        from supervisor.states import EventListenerStates
        event = StartingFromStoppedEvent(process1)
        process1.listener_state = EventListenerStates.BUSY
        pool.event_buffer = [event]
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [event])
        self.assertEqual(pool.config.options.logger.data[0], 5)
        self.assertTrue(pool.config.options.logger.data[1].startswith(
            'Failed sending buffered event'))
    
    def test_transition_event_proc_not_running(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STARTING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        from supervisor.events import StartingFromStoppedEvent
        from supervisor.states import EventListenerStates
        event = StartingFromStoppedEvent(process1)
        process1.listener_state = EventListenerStates.READY
        pool.event_buffer = [event]
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [event])
        self.assertEqual(process1.stdin_buffer, '')
        self.assertEqual(process1.listener_state, EventListenerStates.READY)

    def test_transition_event_proc_running(self):
        options = DummyOptions()
        from supervisor.process import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.RUNNING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        from supervisor.events import StartingFromStoppedEvent
        from supervisor.states import EventListenerStates
        event = StartingFromStoppedEvent(process1)
        process1.listener_state = EventListenerStates.READY
        pool.event_buffer = [event]
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [])
        self.assertEqual(
            process1.stdin_buffer,
            'SUPERVISORD3.0 STARTING_FROM_STOPPED 22\nprocess_name: process1')
        self.assertEqual(process1.listener_state, EventListenerStates.BUSY)
        self.assertEqual(process1.event, event)

class TestSerializers(unittest.TestCase):
    def test_pcomm_event(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        class DummyPCommEvent:
            process = process1
            channel = 'stdout'
            data = 'yo'
        event = DummyPCommEvent()
        from supervisor.process import pcomm_event
        self.assertEqual(pcomm_event(event),
                         'process_name: process1\nchannel: stdout\nyo'
                         )
            
    def test_overflow_event(self):
        class DummyConfig:
            name = 'foo'
        class DummyGroup:
            config = DummyConfig()
        from supervisor.events import StartingFromStoppedEvent
        class DummyOverflowEvent:
            group = DummyGroup()
            event = StartingFromStoppedEvent(None)
        event = DummyOverflowEvent()
        from supervisor.process import overflow_event
        self.assertEqual(overflow_event(event),
                         'group_name: foo\nevent_type: None')

    def test_pcomm_event(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        class DummyStateChangeEvent:
            process = process1
        event = DummyStateChangeEvent()
        from supervisor.process import proc_sc_event
        self.assertEqual(proc_sc_event(event), 'process_name: process1')

    def test_supervisor_sc_event(self):
        class DummyEvent:
            pass
        event = DummyEvent()
        from supervisor.process import supervisor_sc_event
        self.assertEqual(supervisor_sc_event(event), '')

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

