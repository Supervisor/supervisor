import os
import signal
import time
import unittest
import sys

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyPGroupConfig
from supervisor.tests.base import DummyRecorder

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
        self.assertEqual(instance.stdout_recorder.childlog.args, (
            ('/tmp/temp123.log', 20, '%(message)s'),
            {'rotating': False, 'backups': 0, 'maxbytes': 0}))
        self.assertEqual(instance.stderr_recorder.childlog.args, (
            ('/tmp/temp456.log', 20, '%(message)s'),
            {'rotating': False, 'backups': 0, 'maxbytes': 0}))
        self.assertEqual(instance.pid, 0)
        self.assertEqual(instance.laststart, 0)
        self.assertEqual(instance.laststop, 0)
        self.assertEqual(instance.delay, 0)
        self.assertEqual(instance.administrative_stop, 0)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.backoff, 0)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.spawnerr, None)
        self.assertEqual(instance.stdout_recorder.output_buffer, '')
        self.assertEqual(instance.stderr_recorder.output_buffer, '')

    def test_record_output_no_recorders(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile=None,
                              stderr_logfile=None)
        instance = self._makeOne(config)
        self.assertEqual(instance.stdout_recorder, None)
        self.assertEqual(instance.stderr_recorder, None)
        instance.record_output()
        self.assertEqual(options.logger.data, [])

    def test_drain(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test',
                              stdout_logfile='/tmp/foo',
                              stderr_logfile='/tmp/bar')
        instance = self._makeOne(config)
        instance.pipes['stdout'] = 1
        instance.pipes['stderr'] = 2
        instance.pipes['stdin'] = 3
        instance.rpipes[1] = 'stdout'
        instance.rpipes[2] = 'stderr'
        instance.rpipes[3] = 'stdin'
        instance.stdin_buffer = 'foo'
        options.readfd_result = 'abc'
        instance.drain()
        self.assertEqual(instance.stdout_recorder.output_buffer, 'abc')
        self.assertEqual(instance.stderr_recorder.output_buffer, 'abc')
        self.assertEqual(options.written[3], 'foo')
        
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
        from supervisor.process import PInputDispatcher, POutputDispatcher
        self.assertEqual(instance.dispatchers[4].__class__, PInputDispatcher)
        self.assertEqual(instance.dispatchers[5].__class__, POutputDispatcher)
        self.assertEqual(instance.dispatchers[7].__class__, POutputDispatcher)
        self.assertEqual(instance.pipes['stdin'], 4)
        self.assertEqual(instance.pipes['stdout'], 5)
        self.assertEqual(instance.pipes['stderr'], 7)
        self.assertEqual(instance.rpipes[4], 'stdin')
        self.assertEqual(instance.rpipes[5], 'stdout')
        self.assertEqual(instance.rpipes[7], 'stderr')
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
        received = instance.stdin_buffer
        self.assertEqual(sent, received)
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
        from supervisor.options import dictreverse
        instance.rpipes = dictreverse(pipes)
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.rpipes, {})
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
        from supervisor.options import dictreverse
        instance.rpipes = dictreverse(pipes)
        instance.config.exitcodes =[-1]
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.rpipes, {})
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

    def test_strip_ansi(self):
        executable = '/bin/cat'
        options = DummyOptions()
        from supervisor.options import getLogger
        options.getLogger = getLogger
        options.strip_ansi = True
        config = DummyPConfig(options, 'output', executable,
                              stdout_logfile='/tmp/foo')

        ansi = '\x1b[34mHello world... this is longer than a token!\x1b[0m'
        noansi = 'Hello world... this is longer than a token!'

        try:
            instance = self._makeOne(config)
            instance.stdout_recorder.output_buffer = ansi
            instance.record_output()
            [ x.flush() for x in instance.stdout_recorder.childlog.handlers ]
            self.assertEqual(
                open(instance.config.stdout_logfile, 'r').read(), noansi)
        finally:
            try:
                os.remove(instance.config.stdout_logfile)
            except (OSError, IOError):
                pass

        try:
            options.strip_ansi = False
            instance = self._makeOne(config)
            instance.stdout_recorder.output_buffer = ansi
            instance.record_output()
            [ x.flush() for x in instance.stdout_recorder.childlog.handlers ]
            self.assertEqual(
                open(instance.config.stdout_logfile, 'r').read(), ansi)
        finally:
            try:
                os.remove(instance.config.stdout_logfile)
            except (OSError, IOError):
                pass

    def test_drain_output_fd(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.rpipes[0] = 'stdout'
        instance.pipes['stdout'] = 0
        recorder = DummyRecorder()
        instance.stdout_recorder = recorder
        options.readfd_result = 'hello'
        instance.drain_output_fd(0)
        self.assertEqual(recorder.output_buffer, 'hello')

    def test_drain_input_fd(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.stdin_buffer = 'halloooo'
        instance.drain_input_fd(0)
        self.assertEqual(options.written[0], 'halloooo')
        
    def test_drain_input_fd_nodata(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        self.assertEqual(instance.stdin_buffer, '')
        instance.drain_input_fd(0)
        self.assertEqual(instance.stdin_buffer, '')
        self.assertEqual(options.written, {})

    def test_drain_input_fd_epipe_raised(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.stdin_buffer = 'halloooo'
        import errno
        options.write_error = errno.EPIPE
        instance.drain_input_fd(0)
        self.assertEqual(instance.stdin_buffer, '')
        self.assertEqual(options.logger.data,
            ["failed write to process 'test' stdin"])

    def xtest_drain_input_fd_uncaught_raised(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.stdin_buffer = 'halloooo'
        import errno
        options.write_error = errno.EBADF
        self.assertRaises(OSError, instance.drain_input_fd, 0)
        instance.drain_input_fd(0)
        self.assertEqual(instance.stdin_buffer, '')
        self.assertEqual(options.logger.data,
            ["failed write to process 'test' stdin"])

    def test_drain_input_fd_over_os_limit(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        options.write_accept = 1
        instance.stdin_buffer = 'a' * (2 << 16)
        instance.drain_input_fd(0)
        self.assertEqual(len(instance.stdin_buffer), (2<<16) - 1)
        self.assertEqual(options.written[0], 'a')


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
        self.assertEqual(process1.stdout_logged, 'abc')
        self.assertEqual(process1.stderr_logged, 'def')

        # this implies RUNNING
        self.assertEqual(process2.backoff, 0)
        self.assertEqual(process2.delay, 0)
        self.assertEqual(process2.system_stop, 0)
        self.assertEqual(process2.stdout_logged, 'abc')
        self.assertEqual(process2.stderr_logged, 'def')

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
        

class LoggingRecorderTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import LoggingRecorder
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
        options.getLogger = getLogger
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

class POutputDispatcherTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import POutputDispatcher
        return POutputDispatcher

    def _makeOne(self):
        process = DummyProcess(None)
        return self._getTargetClass()(process, 0)

    def test_writable(self):
        dispatcher = self._makeOne()
        self.assertEqual(dispatcher.writable(), False)
        
    def test_readable(self):
        dispatcher = self._makeOne()
        self.assertEqual(dispatcher.readable(), True)

    def test_handle_write_event(self):
        dispatcher = self._makeOne()
        self.assertRaises(NotImplementedError, dispatcher.handle_write_event)

    def test_handle_read_event(self):
        dispatcher = self._makeOne()
        self.assertEqual(dispatcher.handle_read_event(), None)
        self.assertEqual(dispatcher.process.output_fd_drained, 0)
        
    def test_handle_error(self):
        dispatcher = self._makeOne()
        self.assertRaises(NotImplementedError, dispatcher.handle_error)

class PInputDispatcherTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import PInputDispatcher
        return PInputDispatcher

    def _makeOne(self):
        process = DummyProcess(None)
        return self._getTargetClass()(process, 0)

    def test_writable_nodata(self):
        dispatcher = self._makeOne()
        dispatcher.process.stdin_buffer = 'a'
        self.assertEqual(dispatcher.writable(), True)

    def test_writable_withdata(self):
        dispatcher = self._makeOne()
        dispatcher.process.stdin_buffer = ''
        self.assertEqual(dispatcher.writable(), False)

    def test_readable(self):
        dispatcher = self._makeOne()
        self.assertEqual(dispatcher.readable(), False)

    def test_handle_write_event(self):
        dispatcher = self._makeOne()
        self.assertEqual(dispatcher.handle_write_event(), None)
        self.assertEqual(dispatcher.process.input_fd_drained, 0)

    def test_handle_read_event(self):
        dispatcher = self._makeOne()
        self.assertRaises(NotImplementedError, dispatcher.handle_read_event)
        
    def test_handle_error(self):
        dispatcher = self._makeOne()
        self.assertRaises(NotImplementedError, dispatcher.handle_error)

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

