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
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.logger.data[0], "process 'sh' already running")

    def test_spawn_fail_check_execv_args(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'bad', '/bad/filename')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'bad filename')
        self.assertEqual(options.logger.data[0], "spawnerr: bad filename")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_fail_make_pipes_emfile(self):
        options = DummyOptions()
        import errno
        options.make_pipes_error = errno.EMFILE
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr,
                         "too many open files to spawn 'good'")
        self.assertEqual(options.logger.data[0],
                         "spawnerr: too many open files to spawn 'good'")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_fail_make_pipes_other(self):
        options = DummyOptions()
        options.make_pipes_error = 1
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'unknown error: EPERM')
        self.assertEqual(options.logger.data[0],
                         "spawnerr: unknown error: EPERM")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_fork_fail_eagain(self):
        options = DummyOptions()
        import errno
        options.fork_error = errno.EAGAIN
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
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

    def test_spawn_fork_fail_other(self):
        options = DummyOptions()
        options.fork_error = 1
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'unknown error: EPERM')
        self.assertEqual(options.logger.data[0],
                         "spawnerr: unknown error: EPERM")
        self.assertEqual(len(options.parent_pipes_closed), 6)
        self.assertEqual(len(options.child_pipes_closed), 6)
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

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
        instance.stop()
        self.assertEqual(instance.administrative_stop, 1)
        self.failUnless(instance.delay)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertEqual(instance.killing, 1)
        self.assertEqual(options.kills[11], signal.SIGTERM)

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
        instance.pid = 11
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.failUnless(options.logger.data[1].startswith(
            'unknown problem killing test'))
        self.assertEqual(instance.killing, 0)

    def test_kill(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertEqual(instance.killing, 1)
        self.assertEqual(options.kills[11], signal.SIGTERM)

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
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0], 'stopped: notthere '
                         '(terminated by SIGHUP)')
        self.assertEqual(instance.exitstatus, -1)

    def test_finish_expected(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo')
        instance = self._makeOne(config)
        instance.config.options.pidhistory[123] = instance
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        instance.config.exitcodes =[-1]
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0],
                         'exited: notthere (terminated by SIGHUP; expected)')
        self.assertEqual(instance.exitstatus, -1)

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

    def test_get_state(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo')
        from supervisor.process import ProcessStates

        instance = self._makeOne(config)
        instance.killing = True
        instance.laststart = 100
        self.assertEqual(instance.get_state(), ProcessStates.STOPPING)

        instance = self._makeOne(config)
        instance.laststart = 1
        instance.delay = 1
        instance.pid = 1
        self.assertEqual(instance.get_state(), ProcessStates.STARTING)

        instance = self._makeOne(config)
        instance.laststart = 1
        instance.pid = 11
        self.assertEqual(instance.get_state(), ProcessStates.RUNNING)
        
        instance = self._makeOne(config)
        instance.system_stop = True
        instance.laststart = 100
        self.assertEqual(instance.get_state(), ProcessStates.FATAL)

        instance = self._makeOne(config)
        instance.administrative_stop = True
        self.assertEqual(instance.get_state(), ProcessStates.STOPPED)
        
        instance = self._makeOne(config)
        instance.laststart = 1
        instance.exitstatus = 1
        self.assertEqual(instance.get_state(), ProcessStates.EXITED)

        instance = self._makeOne(config)
        instance.laststart = 1
        instance.delay = 1
        self.assertEqual(instance.get_state(), ProcessStates.BACKOFF)

        instance = self._makeOne(config)
        instance.laststart = 1
        self.assertEqual(instance.get_state(), ProcessStates.UNKNOWN)

class ProcessGroupTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import ProcessGroup
        return ProcessGroup

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_transition(self):
        options = DummyOptions()

        from supervisor.process import ProcessStates

        # this should go to FATAL via transition()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.BACKOFF)
        process1.backoff = 10000
        process1.delay = 1
        process1.system_stop = 0
        process1.stdout_buffer = 'abc'
        process1.stderr_buffer = 'def'

        # this should go to RUNNING via transition()
        pconfig2 = DummyPConfig(options, 'process2', 'process2','/bin/process2')
        process2 = DummyProcess(pconfig2, state=ProcessStates.STARTING)
        process2.backoff = 1
        process2.delay = 1
        process2.system_stop = 0
        process2.laststart = 1
        process2.stdout_buffer = 'abc'
        process2.stderr_buffer = 'def'

        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1, pconfig2])
        group = self._makeOne(gconfig)
        group.processes = { 'process1': process1, 'process2': process2 }

        group.transition()

        # this implies FATAL
        self.assertEqual(process1.backoff, 0)
        self.assertEqual(process1.delay, 0)
        self.assertEqual(process1.system_stop, 1)

        # this implies RUNNING
        self.assertEqual(process2.backoff, 0)
        self.assertEqual(process2.delay, 0)
        self.assertEqual(process2.system_stop, 0)

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

        self.assertEqual(process4.delay, 0)
        self.assertEqual(process4.backoff, 0)
        self.assertEqual(process4.system_stop, 1)

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
        

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

