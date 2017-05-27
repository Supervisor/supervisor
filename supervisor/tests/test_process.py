import os
import signal
import time
import unittest
import sys
import errno
from mock import Mock, patch, sentinel

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyPGroupConfig
from supervisor.tests.base import DummyDispatcher
from supervisor.tests.base import DummyEvent
from supervisor.tests.base import DummyFCGIGroupConfig
from supervisor.tests.base import DummySocketConfig
from supervisor.tests.base import DummyProcessGroup
from supervisor.tests.base import DummyFCGIProcessGroup

from supervisor.process import Subprocess
from supervisor.options import BadCommand

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
        from supervisor.states import ProcessStates
        from supervisor.process import getProcessStateDescription
        for statename, code in ProcessStates.__dict__.items():
            if isinstance(code, int):
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
        self.assertFalse(instance.administrative_stop)
        self.assertFalse(instance.killing)
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

    def test_get_execv_args_bad_command_extraquote(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'extraquote', 'extraquote"')
        instance = self._makeOne(config)
        self.assertRaises(BadCommand, instance.get_execv_args)

    def test_get_execv_args_bad_command_empty(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'empty', '')
        instance = self._makeOne(config)
        self.assertRaises(BadCommand, instance.get_execv_args)

    def test_get_execv_args_bad_command_whitespaceonly(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'whitespaceonly', ' \t ')
        instance = self._makeOne(config)
        self.assertRaises(BadCommand, instance.get_execv_args)

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
        self.assertEqual(args, ('notthere', ['notthere']))

    def test_get_execv_args_rel_withquotes_missing(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', 'notthere "an argument"')
        instance = self._makeOne(config)
        args = instance.get_execv_args()
        self.assertEqual(args, ('notthere', ['notthere', 'an argument']))

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
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'bad filename')
        self.assertEqual(options.logger.data[0], "spawnerr: bad filename")
        self.assertTrue(instance.delay)
        self.assertTrue(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(len(L), 2)
        event1 = L[0]
        event2 = L[1]
        self.assertEqual(event1.__class__, events.ProcessStateStartingEvent)
        self.assertEqual(event2.__class__, events.ProcessStateBackoffEvent)

    def test_spawn_fail_make_pipes_emfile(self):
        options = DummyOptions()
        options.make_pipes_error = errno.EMFILE
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr,
                         "too many open files to spawn 'good'")
        self.assertEqual(options.logger.data[0],
                         "spawnerr: too many open files to spawn 'good'")
        self.assertTrue(instance.delay)
        self.assertTrue(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(len(L), 2)
        event1, event2 = L
        self.assertEqual(event1.__class__, events.ProcessStateStartingEvent)
        self.assertEqual(event2.__class__, events.ProcessStateBackoffEvent)

    def test_spawn_fail_make_pipes_other(self):
        options = DummyOptions()
        options.make_pipes_error = 1
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        msg = "unknown error making dispatchers for 'good': EPERM"
        self.assertEqual(instance.spawnerr, msg)
        self.assertEqual(options.logger.data[0], "spawnerr: %s" % msg)
        self.assertTrue(instance.delay)
        self.assertTrue(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(len(L), 2)
        event1, event2 = L
        self.assertEqual(event1.__class__, events.ProcessStateStartingEvent)
        self.assertEqual(event2.__class__, events.ProcessStateBackoffEvent)

    def test_spawn_fail_make_dispatchers_eisdir(self):
        options = DummyOptions()
        config = DummyPConfig(options, name='cat', command='/bin/cat',
                              stdout_logfile='/a/directory') # not a file
        def raise_eisdir(envelope):
            raise IOError(errno.EISDIR)
        config.make_dispatchers = raise_eisdir
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        msg = "unknown error making dispatchers for 'cat': EISDIR"
        self.assertEqual(instance.spawnerr, msg)
        self.assertEqual(options.logger.data[0], "spawnerr: %s" % msg)
        self.assertTrue(instance.delay)
        self.assertTrue(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(len(L), 2)
        event1, event2 = L
        self.assertEqual(event1.__class__, events.ProcessStateStartingEvent)
        self.assertEqual(event2.__class__, events.ProcessStateBackoffEvent)

    def test_spawn_fork_fail_eagain(self):
        options = DummyOptions()
        options.fork_error = errno.EAGAIN
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        msg = "Too many processes in process table to spawn 'good'"
        self.assertEqual(instance.spawnerr, msg)
        self.assertEqual(options.logger.data[0], "spawnerr: %s" % msg)
        self.assertEqual(len(options.parent_pipes_closed), 6)
        self.assertEqual(len(options.child_pipes_closed), 6)
        self.assertTrue(instance.delay)
        self.assertTrue(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(len(L), 2)
        event1, event2 = L
        self.assertEqual(event1.__class__, events.ProcessStateStartingEvent)
        self.assertEqual(event2.__class__, events.ProcessStateBackoffEvent)

    def test_spawn_fork_fail_other(self):
        options = DummyOptions()
        options.fork_error = 1
        config = DummyPConfig(options, 'good', '/good/filename')
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.BACKOFF
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        result = instance.spawn()
        self.assertEqual(result, None)
        msg = "unknown error during fork for 'good': EPERM"
        self.assertEqual(instance.spawnerr, msg)
        self.assertEqual(options.logger.data[0], "spawnerr: %s" % msg)
        self.assertEqual(len(options.parent_pipes_closed), 6)
        self.assertEqual(len(options.child_pipes_closed), 6)
        self.assertTrue(instance.delay)
        self.assertTrue(instance.backoff)
        from supervisor.states import ProcessStates
        self.assertEqual(instance.state, ProcessStates.BACKOFF)
        self.assertEqual(len(L), 2)
        event1, event2 = L
        self.assertEqual(event1.__class__, events.ProcessStateStartingEvent)
        self.assertEqual(event2.__class__, events.ProcessStateBackoffEvent)

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
        self.assertEqual(options.privsdropped, 1)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options.execve_called, True)
        # if the real execve() succeeds, the code that writes the
        # "was not spawned" message won't be reached.  this assertion
        # is to test that no other errors were written.
        self.assertEqual(options.written,
             {2: "supervisor: child process was not spawned\n"})

    def test_spawn_as_child_setuid_fail(self):
        options = DummyOptions()
        options.forkpid = 0
        options.setuid_msg = 'failure reason'
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
             {2: "supervisor: couldn't setuid to 1: failure reason\n"
                 "supervisor: child process was not spawned\n"})
        self.assertEqual(options.privsdropped, None)
        self.assertEqual(options.execve_called, False)
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_cwd_ok(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename',
                              directory='/tmp')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(options.child_pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options.changed_directory, True)
        self.assertEqual(options.execve_called, True)
        # if the real execve() succeeds, the code that writes the
        # "was not spawned" message won't be reached.  this assertion
        # is to test that no other errors were written.
        self.assertEqual(options.written,
             {2: "supervisor: child process was not spawned\n"})

    def test_spawn_as_child_sets_umask(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename', umask=2)
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options.umaskset, 2)
        self.assertEqual(options.execve_called, True)
        # if the real execve() succeeds, the code that writes the
        # "was not spawned" message won't be reached.  this assertion
        # is to test that no other errors were written.
        self.assertEqual(options.written,
             {2: "supervisor: child process was not spawned\n"})

    def test_spawn_as_child_cwd_fail(self):
        options = DummyOptions()
        options.forkpid = 0
        options.chdir_error = 2
        config = DummyPConfig(options, 'good', '/good/filename',
                              directory='/tmp')
        instance = self._makeOne(config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.parent_pipes_closed, None)
        self.assertEqual(options.child_pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.execv_args, None)
        out = {2: "supervisor: couldn't chdir to /tmp: ENOENT\n"
                  "supervisor: child process was not spawned\n"}
        self.assertEqual(options.written, out)
        self.assertEqual(options._exitcode, 127)
        self.assertEqual(options.changed_directory, False)
        self.assertEqual(options.execve_called, False)

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
        out = {2: "supervisor: couldn't exec /good/filename: EPERM\n"
                  "supervisor: child process was not spawned\n"}
        self.assertEqual(options.written, out)
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
        msg = options.written[2] # dict, 2 is fd #
        head = "supervisor: couldn't exec /good/filename:"
        self.assertTrue(msg.startswith(head))
        self.assertTrue("exceptions.RuntimeError" in msg)
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

    def test_spawn_as_child_environment_supervisor_envvars(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'cat', '/bin/cat')
        instance = self._makeOne(config)
        class Dummy:
            name = 'dummy'
        instance.group = Dummy()
        instance.group.config = Dummy()
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.execv_args, ('/bin/cat', ['/bin/cat']) )
        self.assertEqual(
            options.execv_environment['SUPERVISOR_ENABLED'], '1')
        self.assertEqual(
            options.execv_environment['SUPERVISOR_PROCESS_NAME'], 'cat')
        self.assertEqual(
            options.execv_environment['SUPERVISOR_GROUP_NAME'], 'dummy')
        self.assertEqual(
            options.execv_environment['SUPERVISOR_SERVER_URL'],
            'http://localhost:9001')

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
        self.assertEqual(options.privsdropped, 1)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options.execve_called, True)
        # if the real execve() succeeds, the code that writes the
        # "was not spawned" message won't be reached.  this assertion
        # is to test that no other errors were written.
        self.assertEqual(options.written,
             {2: "supervisor: child process was not spawned\n"})

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
        self.assertTrue(instance.delay)
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
        self.assertRaises(OSError, instance.write, sent)
        options.forkpid = 1
        instance.spawn()
        instance.write(sent)
        stdin_fd = instance.pipes['stdin']
        self.assertEqual(sent, instance.dispatchers[stdin_fd].input_buffer)
        instance.killing = True
        self.assertRaises(OSError, instance.write, sent)

    def test_write_dispatcher_closed(self):
        executable = '/bin/cat'
        options = DummyOptions()
        config = DummyPConfig(options, 'output', executable)
        instance = self._makeOne(config)
        sent = 'a' * (1 << 13)
        self.assertRaises(OSError, instance.write, sent)
        options.forkpid = 1
        instance.spawn()
        stdin_fd = instance.pipes['stdin']
        instance.dispatchers[stdin_fd].close()
        self.assertRaises(OSError, instance.write, sent)

    def test_write_stdin_fd_none(self):
        executable = '/bin/cat'
        options = DummyOptions()
        config = DummyPConfig(options, 'output', executable)
        instance = self._makeOne(config)
        options.forkpid = 1
        instance.spawn()
        stdin_fd = instance.pipes['stdin']
        instance.dispatchers[stdin_fd].close()
        instance.pipes['stdin'] = None
        try:
            instance.write('foo')
            self.fail('nothing raised')
        except OSError, exc:
            self.assertEqual(exc.args[0], errno.EPIPE)
            self.assertEqual(exc.args[1], 'Process has no stdin channel')

    def test_write_dispatcher_flush_raises_epipe(self):
        executable = '/bin/cat'
        options = DummyOptions()
        config = DummyPConfig(options, 'output', executable)
        instance = self._makeOne(config)
        sent = 'a' * (1 << 13)
        self.assertRaises(OSError, instance.write, sent)
        options.forkpid = 1
        instance.spawn()
        stdin_fd = instance.pipes['stdin']
        instance.dispatchers[stdin_fd].flush_error = errno.EPIPE
        self.assertRaises(OSError, instance.write, sent)

    def _dont_test_spawn_and_kill(self):
        # this is a functional test
        from supervisor.tests.base import makeSpew
        try:
            sigchlds = []
            def sighandler(*args):
                sigchlds.append(True)
            signal.signal(signal.SIGCHLD, sighandler)
            executable = makeSpew()
            options = DummyOptions()
            config = DummyPConfig(options, 'spew', executable)
            instance = self._makeOne(config)
            result = instance.spawn()
            msg = options.logger.data[0]
            self.assertTrue(msg.startswith("spawned: 'spew' with pid"))
            self.assertEqual(len(instance.pipes), 6)
            self.assertTrue(instance.pid)
            self.assertEqual(instance.pid, result)
            origpid = instance.pid
            while 1:
                try:
                    data = os.popen('ps').read()
                    break
                except IOError, why:
                    if why.args[0] != errno.EINTR:
                        raise
                        # try again ;-)
            time.sleep(0.1) # arbitrary, race condition possible
            self.assertTrue(data.find(repr(origpid)) != -1 )
            msg = instance.kill(signal.SIGTERM)
            time.sleep(0.1) # arbitrary, race condition possible
            self.assertEqual(msg, None)
            pid, sts = os.waitpid(-1, os.WNOHANG)
            data = os.popen('ps').read()
            self.assertEqual(data.find(repr(origpid)), -1) # dubious
            self.assertNotEqual(sigchlds, [])
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
        instance.laststopreport = time.time()
        instance.stop()
        self.assertTrue(instance.administrative_stop)
        self.assertEqual(instance.laststopreport, 0)
        self.assertTrue(instance.delay)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertTrue(instance.killing)
        self.assertEqual(options.kills[11], signal.SIGTERM)

    def test_stop_not_in_stoppable_state_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        dispatcher = DummyDispatcher(writable=True)
        instance.dispatchers = {'foo':dispatcher}
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.STOPPED
        try:
            instance.stop()
            self.fail('nothing raised')
        except AssertionError, exc:
            self.assertEqual(exc.args[0], 'Assertion failed for test: '
                'STOPPED not in RUNNING STARTING STOPPING')

    def test_stop_report_logs_nothing_if_not_stopping_state(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        dispatcher = DummyDispatcher(writable=True)
        instance.dispatchers = {'foo':dispatcher}
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.STOPPED
        instance.stop_report()
        self.assertEqual(len(options.logger.data), 0)

    def test_stop_report_logs_throttled_by_laststopreport(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        dispatcher = DummyDispatcher(writable=True)
        instance.dispatchers = {'foo':dispatcher}
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.STOPPING
        self.assertEqual(instance.laststopreport, 0)
        instance.stop_report()
        self.assertEqual(len(options.logger.data), 1)
        self.assertEqual(options.logger.data[0], 'waiting for test to stop')
        self.assertNotEqual(instance.laststopreport, 0)
        instance.stop_report()
        self.assertEqual(len(options.logger.data), 1) # throttled

    def test_give_up(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        instance.state = ProcessStates.BACKOFF
        instance.give_up()
        self.assertTrue(instance.system_stop)
        self.assertFalse(instance.delay)
        self.assertFalse(instance.backoff)
        self.assertEqual(instance.state, ProcessStates.FATAL)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateFatalEvent)

    def test_kill_nopid(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0],
              'attempted to kill test with sig SIGTERM but it wasn\'t running')
        self.assertFalse(instance.killing)

    def test_kill_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        options.kill_error = 1
        instance = self._makeOne(config)
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.ProcessStateEvent,
                         lambda x: L.append(x))
        instance.pid = 11
        instance.state = ProcessStates.RUNNING
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertTrue(options.logger.data[1].startswith(
            'unknown problem killing test'))
        self.assertTrue('Traceback' in options.logger.data[1])
        self.assertFalse(instance.killing)
        self.assertEqual(len(L), 2)
        event1 = L[0]
        event2 = L[1]
        self.assertEqual(event1.__class__, events.ProcessStateStoppingEvent)
        self.assertEqual(event2.__class__, events.ProcessStateUnknownEvent)

    def test_kill_from_starting(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.ProcessStateEvent,lambda x: L.append(x))
        instance.state = ProcessStates.STARTING
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertTrue(instance.killing)
        self.assertEqual(options.kills[11], signal.SIGTERM)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStoppingEvent)

    def test_kill_from_running(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        instance.state = ProcessStates.RUNNING
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGTERM')
        self.assertTrue(instance.killing)
        self.assertEqual(options.kills[11], signal.SIGTERM)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStoppingEvent)

    def test_kill_from_stopping(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.Event,lambda x: L.append(x))
        instance.state = ProcessStates.STOPPING
        instance.kill(signal.SIGKILL)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) with '
                         'signal SIGKILL')
        self.assertTrue(instance.killing)
        self.assertEqual(options.kills[11], signal.SIGKILL)
        self.assertEqual(L, []) # no event because we didn't change state

    def test_kill_from_backoff(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.Event, L.append)
        instance.state = ProcessStates.BACKOFF
        instance.kill(signal.SIGKILL)
        self.assertEqual(options.logger.data[0],
                         'Attempted to kill test, which is in BACKOFF state.')
        self.assertFalse(instance.killing)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStoppedEvent)

    def test_kill_from_stopping_w_killasgroup(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test', killasgroup=True)
        instance = self._makeOne(config)
        instance.pid = 11
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.Event,lambda x: L.append(x))
        instance.state = ProcessStates.STOPPING
        instance.kill(signal.SIGKILL)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) '
                         'process group with signal SIGKILL')
        self.assertTrue(instance.killing)
        self.assertEqual(options.kills[-11], signal.SIGKILL)
        self.assertEqual(L, []) # no event because we didn't change state

    def test_stopasgroup(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test', stopasgroup=True)
        instance = self._makeOne(config)
        instance.pid = 11
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.Event,lambda x: L.append(x))
        instance.state = ProcessStates.RUNNING
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11) '
                         'process group with signal SIGTERM')
        self.assertTrue(instance.killing)
        self.assertEqual(options.kills[-11], signal.SIGTERM)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStoppingEvent)
        self.assertEqual(event.extra_values, [('pid', 11)])
        self.assertEqual(event.from_state, ProcessStates.RUNNING)

    def test_signal(self):
        options = DummyOptions()

        killedpid = []
        killedsig = []

        def kill(pid, sig):
            killedpid.append(pid)
            killedsig.append(sig)

        options.kill = kill

        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = 11

        from supervisor.states import ProcessStates
        instance.state = ProcessStates.RUNNING

        instance.signal(signal.SIGWINCH )

        self.assertEqual(killedpid, [instance.pid,])
        self.assertEqual(killedsig, [signal.SIGWINCH,])

        self.assertEqual(options.logger.data[0], 'sending test (pid 11) sig SIGWINCH')

    def test_signal_stopped(self):
        options = DummyOptions()

        killedpid = []
        killedsig = []

        def kill(pid, sig):
            killedpid.append(pid)
            killedsig.append(sig)

        options.kill = kill #don't actually start killing random processes...

        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.pid = None

        from supervisor.states import ProcessStates
        instance.state = ProcessStates.STOPPED

        instance.signal(signal.SIGWINCH )

        self.assertEqual(options.logger.data[0], "attempted to send test sig SIGWINCH "
                                                    "but it wasn't running")

        self.assertEqual(killedpid, [])

    def test_signal_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        options.kill_error = 1
        instance = self._makeOne(config)
        L = []
        from supervisor.states import ProcessStates
        from supervisor import events
        events.subscribe(events.ProcessStateEvent,
                         lambda x: L.append(x))
        instance.pid = 11
        instance.state = ProcessStates.RUNNING
        instance.signal(signal.SIGWINCH)
        self.assertEqual(options.logger.data[0],
            'sending test (pid 11) sig SIGWINCH')
        self.assertTrue(options.logger.data[1].startswith(
            'unknown problem sending sig test (11)'))
        self.assertFalse(instance.killing)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateUnknownEvent)

    def test_finish_stopping_state(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo')
        instance = self._makeOne(config)
        instance.waitstatus = (123, 1) # pid, waitstatus
        instance.config.options.pidhistory[123] = instance
        instance.killing = True
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        from supervisor.states import ProcessStates
        from supervisor import events
        instance.state = ProcessStates.STOPPING
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        instance.pid = 123
        instance.finish(123, 1)
        self.assertFalse(instance.killing)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0], 'stopped: notthere '
                         '(terminated by SIGHUP)')
        self.assertEqual(instance.exitstatus, -1)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStoppedEvent)
        self.assertEqual(event.extra_values, [('pid', 123)])
        self.assertEqual(event.from_state, ProcessStates.STOPPING)

    def test_finish_running_state_exit_expected(self):
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
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        instance.pid = 123
        instance.finish(123, 1)
        self.assertFalse(instance.killing)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0],
                         'exited: notthere (terminated by SIGHUP; expected)')
        self.assertEqual(instance.exitstatus, -1)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__,
                         events.ProcessStateExitedEvent)
        self.assertEqual(event.expected, True)
        self.assertEqual(event.extra_values, [('expected', True), ('pid', 123)])
        self.assertEqual(event.from_state, ProcessStates.RUNNING)

    def test_finish_starting_state_laststart_in_future(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo')
        instance = self._makeOne(config)
        instance.config.options.pidhistory[123] = instance
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        instance.config.exitcodes =[-1]
        instance.laststart = time.time() + 3600 # 1 hour into the future
        from supervisor.states import ProcessStates
        from supervisor import events
        instance.state = ProcessStates.STARTING
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        instance.pid = 123
        instance.finish(123, 1)
        self.assertFalse(instance.killing)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0],
                         "process 'notthere' (123) laststart time is in the "
                         "future, don't know how long process was running so "
                         "assuming it did not exit too quickly")
        self.assertEqual(options.logger.data[1],
                         'exited: notthere (terminated by SIGHUP; expected)')
        self.assertEqual(instance.exitstatus, -1)
        self.assertEqual(len(L), 2)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateRunningEvent)
        self.assertEqual(event.expected, True)
        self.assertEqual(event.extra_values, [('pid', 123)])
        self.assertEqual(event.from_state, ProcessStates.STARTING)
        event = L[1]
        self.assertEqual(event.__class__, events.ProcessStateExitedEvent)
        self.assertEqual(event.expected, True)
        self.assertEqual(event.extra_values, [('expected', True), ('pid', 123)])
        self.assertEqual(event.from_state, ProcessStates.RUNNING)

    def test_finish_starting_state_exited_too_quickly(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo', startsecs=10)
        instance = self._makeOne(config)
        instance.config.options.pidhistory[123] = instance
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        instance.config.exitcodes =[-1]
        instance.laststart = time.time()
        from supervisor.states import ProcessStates
        from supervisor import events
        instance.state = ProcessStates.STARTING
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        instance.pid = 123
        instance.finish(123, 1)
        self.assertFalse(instance.killing)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0],
                      'exited: notthere (terminated by SIGHUP; not expected)')
        self.assertEqual(instance.exitstatus, None)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateBackoffEvent)
        self.assertEqual(event.from_state, ProcessStates.STARTING)

    def test_finish_running_state_laststart_in_future(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo')
        instance = self._makeOne(config)
        instance.config.options.pidhistory[123] = instance
        pipes = {'stdout':'','stderr':''}
        instance.pipes = pipes
        instance.config.exitcodes =[-1]
        instance.laststart = time.time() + 3600 # 1 hour into the future
        from supervisor.states import ProcessStates
        from supervisor import events
        instance.state = ProcessStates.RUNNING
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        instance.pid = 123
        instance.finish(123, 1)
        self.assertFalse(instance.killing)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(options.parent_pipes_closed, pipes)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.dispatchers, {})
        self.assertEqual(options.logger.data[0],
                         "process 'notthere' (123) laststart time is in the "
                         "future, don't know how long process was running so "
                         "assuming it did not exit too quickly")
        self.assertEqual(options.logger.data[1],
                         'exited: notthere (terminated by SIGHUP; expected)')
        self.assertEqual(instance.exitstatus, -1)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__,
                         events.ProcessStateExitedEvent)
        self.assertEqual(event.expected, True)
        self.assertEqual(event.extra_values, [('expected', True), ('pid', 123)])
        self.assertEqual(event.from_state, ProcessStates.RUNNING)

    def test_finish_with_current_event_sends_rejected(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        events.subscribe(events.EventRejectedEvent, lambda x: L.append(x))
        options = DummyOptions()
        config = DummyPConfig(options, 'notthere', '/notthere',
                              stdout_logfile='/tmp/foo', startsecs=10)
        instance = self._makeOne(config)
        from supervisor.states import ProcessStates
        instance.state = ProcessStates.RUNNING
        event = DummyEvent()
        instance.event = event
        instance.finish(123, 1)
        self.assertEqual(len(L), 2)
        event1, event2 = L
        self.assertEqual(event1.__class__,
                         events.ProcessStateExitedEvent)
        self.assertEqual(event2.__class__, events.EventRejectedEvent)
        self.assertEqual(event2.process, instance)
        self.assertEqual(event2.event, event)
        self.assertEqual(instance.event, None)

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

    def test_transition_stopped_to_starting_supervisor_stopping(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates, SupervisorStates
        options = DummyOptions()
        options.mood = SupervisorStates.SHUTDOWN

        # this should not be spawned, as supervisor is shutting down
        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.laststart = 0
        process.state = ProcessStates.STOPPED
        process.transition()
        self.assertEqual(process.state, ProcessStates.STOPPED)
        self.assertEqual(L, [])

    def test_transition_stopped_to_starting_supervisor_running(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates, SupervisorStates
        options = DummyOptions()
        options.mood = SupervisorStates.RUNNING

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.laststart = 0
        process.state = ProcessStates.STOPPED
        process.transition()
        self.assertEqual(process.state, ProcessStates.STARTING)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStartingEvent)

    def test_transition_exited_to_starting_supervisor_stopping(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates, SupervisorStates
        options = DummyOptions()
        options.mood = SupervisorStates.SHUTDOWN

        # this should not be spawned, as supervisor is shutting down
        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        from supervisor.datatypes import RestartUnconditionally
        pconfig.autorestart = RestartUnconditionally
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.system_stop = True
        process.state = ProcessStates.EXITED
        process.transition()
        self.assertEqual(process.state, ProcessStates.EXITED)
        self.assertTrue(process.system_stop)
        self.assertEqual(L, [])

    def test_transition_exited_to_starting_uncond_supervisor_running(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates
        options = DummyOptions()

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        from supervisor.datatypes import RestartUnconditionally
        pconfig.autorestart = RestartUnconditionally
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.state = ProcessStates.EXITED
        process.transition()
        self.assertEqual(process.state, ProcessStates.STARTING)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStartingEvent)

    def test_transition_exited_to_starting_condit_supervisor_running(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates
        options = DummyOptions()

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        from supervisor.datatypes import RestartWhenExitUnexpected
        pconfig.autorestart = RestartWhenExitUnexpected
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.state = ProcessStates.EXITED
        process.exitstatus = 'bogus'
        process.transition()
        self.assertEqual(process.state, ProcessStates.STARTING)
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateStartingEvent)

    def test_transition_exited_to_starting_condit_fls_supervisor_running(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates
        options = DummyOptions()

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        from supervisor.datatypes import RestartWhenExitUnexpected
        pconfig.autorestart = RestartWhenExitUnexpected
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.state = ProcessStates.EXITED
        process.exitstatus = 0
        process.transition()
        self.assertEqual(process.state, ProcessStates.EXITED)
        self.assertEqual(L, [])

    def test_transition_backoff_to_starting_supervisor_stopping(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates, SupervisorStates
        options = DummyOptions()
        options.mood = SupervisorStates.SHUTDOWN

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.delay = 0
        process.backoff = 0
        process.state = ProcessStates.BACKOFF
        process.transition()
        self.assertEqual(process.state, ProcessStates.BACKOFF)
        self.assertEqual(L, [])

    def test_transition_backoff_to_starting_supervisor_running(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates, SupervisorStates
        options = DummyOptions()
        options.mood = SupervisorStates.RUNNING

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.delay = 0
        process.backoff = 0
        process.state = ProcessStates.BACKOFF
        process.transition()
        self.assertEqual(process.state, ProcessStates.STARTING)
        self.assertEqual(len(L), 1)
        self.assertEqual(L[0].__class__, events.ProcessStateStartingEvent)

    def test_transition_backoff_to_starting_supervisor_running_notyet(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates, SupervisorStates
        options = DummyOptions()
        options.mood = SupervisorStates.RUNNING

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.delay = sys.maxint
        process.backoff = 0
        process.state = ProcessStates.BACKOFF
        process.transition()
        self.assertEqual(process.state, ProcessStates.BACKOFF)
        self.assertEqual(L, [])

    def test_transition_starting_to_running(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates

        options = DummyOptions()

        # this should go from STARTING to RUNNING via transition()
        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.backoff = 1
        process.delay = 1
        process.system_stop = False
        process.laststart = 1
        process.pid = 1
        process.stdout_buffer = 'abc'
        process.stderr_buffer = 'def'
        process.state = ProcessStates.STARTING
        process.transition()

        # this implies RUNNING
        self.assertEqual(process.backoff, 0)
        self.assertEqual(process.delay, 0)
        self.assertFalse(process.system_stop)
        self.assertEqual(options.logger.data[0],
                         'success: process entered RUNNING state, process has '
                         'stayed up for > than 10 seconds (startsecs)')
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateRunningEvent)

    def test_transition_backoff_to_fatal(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates
        options = DummyOptions()

        # this should go from BACKOFF to FATAL via transition()
        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.laststart = 1
        process.backoff = 10000
        process.delay = 1
        process.system_stop = False
        process.stdout_buffer = 'abc'
        process.stderr_buffer = 'def'
        process.state = ProcessStates.BACKOFF

        process.transition()

        # this implies FATAL
        self.assertEqual(process.backoff, 0)
        self.assertEqual(process.delay, 0)
        self.assertTrue(process.system_stop)
        self.assertEqual(options.logger.data[0],
                         'gave up: process entered FATAL state, too many start'
                         ' retries too quickly')
        self.assertEqual(len(L), 1)
        event = L[0]
        self.assertEqual(event.__class__, events.ProcessStateFatalEvent)

    def test_transition_stops_unkillable_notyet(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates
        options = DummyOptions()

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.delay = sys.maxint
        process.state = ProcessStates.STOPPING

        process.transition()
        self.assertEqual(process.state, ProcessStates.STOPPING)
        self.assertEqual(L, [])

    def test_transition_stops_unkillable(self):
        from supervisor import events
        L = []
        events.subscribe(events.ProcessStateEvent, lambda x: L.append(x))
        from supervisor.states import ProcessStates
        options = DummyOptions()

        pconfig = DummyPConfig(options, 'process', 'process','/bin/process')
        process = self._makeOne(pconfig)
        process.delay = 0
        process.pid = 1
        process.killing = False
        process.state = ProcessStates.STOPPING

        process.transition()
        self.assertTrue(process.killing)
        self.assertNotEqual(process.delay, 0)
        self.assertEqual(process.state, ProcessStates.STOPPING)
        self.assertEqual(options.logger.data[0],
                         "killing 'process' (1) with SIGKILL")
        import signal
        self.assertEqual(options.kills[1], signal.SIGKILL)
        self.assertEqual(L, [])

    def test_change_state_doesnt_notify_if_no_state_change(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.state = 10
        self.assertEqual(instance.change_state(10), False)

    def test_change_state_sets_backoff_and_delay(self):
        from supervisor.states import ProcessStates
        options = DummyOptions()
        config = DummyPConfig(options, 'test', '/test')
        instance = self._makeOne(config)
        instance.state = 10
        instance.change_state(ProcessStates.BACKOFF)
        self.assertEqual(instance.backoff, 1)
        self.assertTrue(instance.delay > 0)

class FastCGISubprocessTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import FastCGISubprocess
        return FastCGISubprocess

    def _makeOne(self, *arg, **kw):
        return self._getTargetClass()(*arg, **kw)

    def tearDown(self):
        from supervisor.events import clear
        clear()

    def test_no_group(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        self.assertRaises(NotImplementedError, instance.spawn)

    def test_no_socket_manager(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        instance.group = DummyProcessGroup(DummyPGroupConfig(options))
        self.assertRaises(NotImplementedError, instance.spawn)

    def test_prepare_child_fds(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        sock_config = DummySocketConfig(7)
        gconfig = DummyFCGIGroupConfig(options, 'whatever', 999, None,
                                       sock_config)
        instance.group = DummyFCGIProcessGroup(gconfig)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(options.duped[7], 0)
        self.assertEqual(options.duped[instance.pipes['child_stdout']], 1)
        self.assertEqual(options.duped[instance.pipes['child_stderr']], 2)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)

    def test_prepare_child_fds_stderr_redirected(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        config.redirect_stderr = True
        instance = self._makeOne(config)
        sock_config = DummySocketConfig(13)
        gconfig = DummyFCGIGroupConfig(options, 'whatever', 999, None,
                                       sock_config)
        instance.group = DummyFCGIProcessGroup(gconfig)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(len(options.duped), 2)
        self.assertEqual(options.duped[13], 0)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)

    def test_before_spawn_gets_socket_ref(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        sock_config = DummySocketConfig(7)
        gconfig = DummyFCGIGroupConfig(options, 'whatever', 999, None,
                                       sock_config)
        instance.group = DummyFCGIProcessGroup(gconfig)
        self.assertTrue(instance.fcgi_sock is None)
        instance.before_spawn()
        self.assertFalse(instance.fcgi_sock is None)

    def test_after_finish_removes_socket_ref(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        instance.fcgi_sock = 'hello'
        instance.after_finish()
        self.assertTrue(instance.fcgi_sock is None)

    #Patch Subprocess.finish() method for this test to verify override
    @patch.object(Subprocess, 'finish', Mock(return_value=sentinel.finish_result))
    def test_finish_override(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        instance.after_finish = Mock()
        result = instance.finish(sentinel.pid, sentinel.sts)
        self.assertEqual(sentinel.finish_result, result,
                        'FastCGISubprocess.finish() did not pass thru result')
        self.assertEqual(1, instance.after_finish.call_count,
                            'FastCGISubprocess.after_finish() not called once')
        finish_mock = Subprocess.finish
        self.assertEqual(1, finish_mock.call_count,
                            'Subprocess.finish() not called once')
        pid_arg = finish_mock.call_args[0][1]
        sts_arg = finish_mock.call_args[0][2]
        self.assertEqual(sentinel.pid, pid_arg,
                            'Subprocess.finish() pid arg was not passed')
        self.assertEqual(sentinel.sts, sts_arg,
                            'Subprocess.finish() sts arg was not passed')

    #Patch Subprocess.spawn() method for this test to verify override
    @patch.object(Subprocess, 'spawn', Mock(return_value=sentinel.ppid))
    def test_spawn_override_success(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        instance.before_spawn = Mock()
        result = instance.spawn()
        self.assertEqual(sentinel.ppid, result,
                        'FastCGISubprocess.spawn() did not pass thru result')
        self.assertEqual(1, instance.before_spawn.call_count,
                            'FastCGISubprocess.before_spawn() not called once')
        spawn_mock = Subprocess.spawn
        self.assertEqual(1, spawn_mock.call_count,
                            'Subprocess.spawn() not called once')

    #Patch Subprocess.spawn() method for this test to verify error handling
    @patch.object(Subprocess, 'spawn', Mock(return_value=None))
    def test_spawn_error(self):
        options = DummyOptions()
        config = DummyPConfig(options, 'good', '/good/filename', uid=1)
        instance = self._makeOne(config)
        instance.before_spawn = Mock()
        instance.fcgi_sock = 'nuke me on error'
        result = instance.spawn()
        self.assertEqual(None, result,
                        'FastCGISubprocess.spawn() did return None on error')
        self.assertEqual(1, instance.before_spawn.call_count,
                            'FastCGISubprocess.before_spawn() not called once')
        self.assertEqual(None, instance.fcgi_sock,
                'FastCGISubprocess.spawn() did not remove sock ref on error')

class ProcessGroupBaseTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import ProcessGroupBase
        return ProcessGroupBase

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_get_unstopped_processes(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = { 'process1': process1 }
        unstopped = group.get_unstopped_processes()
        self.assertEqual(unstopped, [process1])

    def test_stop_all(self):
        from supervisor.states import ProcessStates
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
        from supervisor.states import ProcessStates
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
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = {'process1': process1}
        group.reopenlogs()
        self.assertEqual(process1.logs_reopened, True)

    def test_removelogs(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = {'process1': process1}
        group.removelogs()
        self.assertEqual(process1.logsremoved, True)

    def test_ordering_and_comparison(self):
        options = DummyOptions()
        gconfig1 = DummyPGroupConfig(options)
        group1 = self._makeOne(gconfig1)

        gconfig2 = DummyPGroupConfig(options)
        group2 = self._makeOne(gconfig2)

        config3 = DummyPGroupConfig(options)
        group3 = self._makeOne(config3)

        group1.config.priority = 5
        group2.config.priority = 1
        group3.config.priority = 5

        L = [group1, group2]
        L.sort()

        self.assertEqual(L, [group2, group1])
        self.assertNotEqual(group1, group2)
        self.assertEqual(group1, group3)

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
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        group = self._makeOne(gconfig)
        group.processes = {'process1': process1}
        group.transition()
        self.assertEqual(process1.transitioned, True)

class FastCGIProcessGroupTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.process import FastCGIProcessGroup
        return FastCGIProcessGroup

    def _makeOne(self, config, **kwargs):
        cls = self._getTargetClass()
        return cls(config, **kwargs)

    def test___init__without_socket_error(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        gconfig.socket_config = None
        class DummySocketManager(object):
            def __init__(self, config, logger): pass
            def get_socket(self): pass
        self._makeOne(gconfig, socketManager=DummySocketManager)
        # doesn't fail with exception

    def test___init__with_socket_error(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        gconfig.socket_config = None
        class DummySocketManager(object):
            def __init__(self, config, logger): pass
            def get_socket(self):
                raise KeyError(5)
            def config(self):
                return 'config'
        self.assertRaises(
            ValueError,
            self._makeOne, gconfig, socketManager=DummySocketManager
            )

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
            (EventType, pool._acceptEvent))
        self.assertEqual(events.callbacks[1],
            (events.EventRejectedEvent, pool.handle_rejected))
        self.assertEqual(pool.serial, -1)

    def test__eventEnvelope(self):
        options = DummyOptions()
        options.identifier = 'thesupervisorname'
        gconfig = DummyPGroupConfig(options)
        gconfig.name = 'thepoolname'
        pool = self._makeOne(gconfig)
        from supervisor import events
        result = pool._eventEnvelope(
            events.EventTypes.PROCESS_COMMUNICATION_STDOUT, 80, 20, 'payload\n')
        header, payload = result.split('\n', 1)
        headers = header.split()
        self.assertEqual(headers[0], 'ver:3.0')
        self.assertEqual(headers[1], 'server:thesupervisorname')
        self.assertEqual(headers[2], 'serial:80')
        self.assertEqual(headers[3], 'pool:thepoolname')
        self.assertEqual(headers[4], 'poolserial:20')
        self.assertEqual(headers[5], 'eventname:PROCESS_COMMUNICATION_STDOUT')
        self.assertEqual(headers[6], 'len:8')
        self.assertEqual(payload, 'payload\n')

    def test_handle_rejected_no_overflow(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        pool.event_buffer = [None, None]
        class DummyEvent1:
            serial = 'abc'
        class DummyEvent2:
            process = process1
            event = DummyEvent1()
        dummyevent = DummyEvent2()
        dummyevent.serial = 1
        pool.handle_rejected(dummyevent)
        self.assertEqual(pool.event_buffer, [dummyevent.event, None, None])

    def test_handle_rejected_event_buffer_overflowed(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        gconfig.buffer_size = 3
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        class DummyEvent:
            def __init__(self, serial):
                self.serial = serial
        class DummyRejectedEvent:
            def __init__(self, serial):
                self.process = process1
                self.event = DummyEvent(serial)
        event_a = DummyEvent('a')
        event_b = DummyEvent('b')
        event_c = DummyEvent('c')
        rej_event = DummyRejectedEvent('rejected')
        pool.event_buffer = [event_a, event_b, event_c]
        pool.handle_rejected(rej_event)
        serials = [ x.serial for x in pool.event_buffer ]
        # we popped a, and we inserted the rejected event into the 1st pos
        self.assertEqual(serials, ['rejected', 'b', 'c'])
        self.assertEqual(pool.config.options.logger.data[0],
            'pool whatever event buffer overflowed, discarding event a')

    def test_dispatch_pipe_error(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        from supervisor.states import EventListenerStates
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        process1 = pool.processes['process1']
        process1.write_error = errno.EPIPE
        process1.listener_state = EventListenerStates.READY
        event = DummyEvent()
        pool._acceptEvent(event)
        pool.dispatch()
        self.assertEqual(process1.listener_state, EventListenerStates.READY)
        self.assertEqual(pool.event_buffer, [event])
        self.assertEqual(options.logger.data[0],
                         'rebuffering event abc for pool whatever (bufsize 0)')

    def test__acceptEvent_attaches_pool_serial_and_serial(self):
        from supervisor.process import GlobalSerial
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        process1 = pool.processes['process1']
        from supervisor.states import EventListenerStates
        process1.listener_state = EventListenerStates.READY
        event = DummyEvent(None)
        pool._acceptEvent(event)
        self.assertEqual(event.serial, GlobalSerial.serial)
        self.assertEqual(event.pool_serials['whatever'], pool.serial)

    def test_repr(self):
        options = DummyOptions()
        gconfig = DummyPGroupConfig(options)
        pool = self._makeOne(gconfig)
        s = repr(pool)
        self.assertTrue(s.startswith(
            '<supervisor.process.EventListenerPool instance at'))
        self.assertTrue(s.endswith('named whatever>'))

    def test_transition_nobody_ready(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STARTING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        event = DummyEvent()
        event.serial = 'a'
        from supervisor.states import EventListenerStates
        process1.listener_state = EventListenerStates.BUSY
        pool._acceptEvent(event)
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [event])

    def test_transition_event_proc_not_running(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STARTING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        event = DummyEvent()
        from supervisor.states import EventListenerStates
        event.serial = 1
        process1.listener_state = EventListenerStates.READY
        pool._acceptEvent(event)
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [event])
        self.assertEqual(process1.stdin_buffer, '')
        self.assertEqual(process1.listener_state, EventListenerStates.READY)

    def test_transition_event_proc_running(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.RUNNING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        event = DummyEvent()
        from supervisor.states import EventListenerStates
        process1.listener_state = EventListenerStates.READY
        class DummyGroup:
            config = gconfig
        process1.group = DummyGroup
        pool._acceptEvent(event)
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [])
        header, payload = process1.stdin_buffer.split('\n', 1)
        self.assertEqual(payload, 'dummy event', payload)
        self.assertEqual(process1.listener_state, EventListenerStates.BUSY)
        self.assertEqual(process1.event, event)

    def test_transition_event_proc_running_with_dispatch_throttle_notyet(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.RUNNING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.dispatch_throttle = 5
        pool.last_dispatch = time.time()
        pool.processes = {'process1': process1}
        event = DummyEvent()
        from supervisor.states import EventListenerStates
        process1.listener_state = EventListenerStates.READY
        class DummyGroup:
            config = gconfig
        process1.group = DummyGroup
        pool._acceptEvent(event)
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [event]) # not popped

    def test_transition_event_proc_running_with_dispatch_throttle_ready(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.RUNNING)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.dispatch_throttle = 5
        pool.last_dispatch = time.time() - 1000
        pool.processes = {'process1': process1}
        event = DummyEvent()
        from supervisor.states import EventListenerStates
        process1.listener_state = EventListenerStates.READY
        class DummyGroup:
            config = gconfig
        process1.group = DummyGroup
        pool._acceptEvent(event)
        pool.transition()
        self.assertEqual(process1.transitioned, True)
        self.assertEqual(pool.event_buffer, [])
        header, payload = process1.stdin_buffer.split('\n', 1)
        self.assertEqual(payload, 'dummy event', payload)
        self.assertEqual(process1.listener_state, EventListenerStates.BUSY)
        self.assertEqual(process1.event, event)

    def test__dispatchEvent_notready(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPED)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        event = DummyEvent()
        pool._acceptEvent(event)
        self.assertEqual(pool._dispatchEvent(event), False)

    def test__dispatchEvent_proc_write_raises_non_EPIPE_OSError(self):
        options = DummyOptions()
        from supervisor.states import ProcessStates
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.RUNNING)
        def raise_epipe(envelope):
            raise OSError(errno.EAGAIN)
        process1.write = raise_epipe
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig1])
        pool = self._makeOne(gconfig)
        pool.processes = {'process1': process1}
        event = DummyEvent()
        from supervisor.states import EventListenerStates
        process1.listener_state = EventListenerStates.READY
        class DummyGroup:
            config = gconfig
        process1.group = DummyGroup
        pool._acceptEvent(event)
        self.assertRaises(OSError, pool._dispatchEvent, event)

class test_new_serial(unittest.TestCase):
    def _callFUT(self, inst):
        from supervisor.process import new_serial
        return new_serial(inst)

    def test_inst_serial_is_maxint(self):
        class Inst(object):
            def __init__(self):
                self.serial = sys.maxint
        inst = Inst()
        result = self._callFUT(inst)
        self.assertEqual(inst.serial, 0)
        self.assertEqual(result, 0)

    def test_inst_serial_is_not_maxint(self):
        class Inst(object):
            def __init__(self):
                self.serial = 1
        inst = Inst()
        result = self._callFUT(inst)
        self.assertEqual(inst.serial, 2)
        self.assertEqual(result, 2)
