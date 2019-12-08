import unittest
import time
import signal
import sys
import os
import tempfile
import shutil

from supervisor.states import ProcessStates
from supervisor.states import SupervisorStates

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyPGroupConfig
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyProcessGroup
from supervisor.tests.base import DummyDispatcher

from supervisor.compat import StringIO

try:
    import pstats
except ImportError: # pragma: no cover
    # Debian-packaged pythons may not have the pstats module
    # unless the "python-profiler" package is installed.
    pstats = None

class EntryPointTests(unittest.TestCase):
    def test_main_noprofile(self):
        from supervisor.supervisord import main
        conf = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'fixtures',
            'donothing.conf')
        new_stdout = StringIO()
        new_stdout.fileno = lambda: 1
        old_stdout = sys.stdout
        try:
            tempdir = tempfile.mkdtemp()
            log = os.path.join(tempdir, 'log')
            pid = os.path.join(tempdir, 'pid')
            sys.stdout = new_stdout
            main(args=['-c', conf, '-l', log, '-j', pid, '-n'],
                 test=True)
        finally:
            sys.stdout = old_stdout
            shutil.rmtree(tempdir)
        output = new_stdout.getvalue()
        self.assertTrue('supervisord started' in output, output)

    if pstats:
        def test_main_profile(self):
            from supervisor.supervisord import main
            conf = os.path.join(
                os.path.abspath(os.path.dirname(__file__)), 'fixtures',
                'donothing.conf')
            new_stdout = StringIO()
            new_stdout.fileno = lambda: 1
            old_stdout = sys.stdout
            try:
                tempdir = tempfile.mkdtemp()
                log = os.path.join(tempdir, 'log')
                pid = os.path.join(tempdir, 'pid')
                sys.stdout = new_stdout
                main(args=['-c', conf, '-l', log, '-j', pid, '-n',
                           '--profile_options=cumulative,calls'], test=True)
            finally:
                sys.stdout = old_stdout
                shutil.rmtree(tempdir)
            output = new_stdout.getvalue()
            self.assertTrue('cumulative time, call count' in output, output)

    def test_silent_off(self):
        from supervisor.supervisord import main
        conf = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'fixtures',
            'donothing.conf')
        new_stdout = StringIO()
        new_stdout.fileno = lambda: 1
        old_stdout = sys.stdout

        try:
            tempdir = tempfile.mkdtemp()
            log = os.path.join(tempdir, 'log')
            pid = os.path.join(tempdir, 'pid')
            sys.stdout = new_stdout
            main(args=['-c', conf, '-l', log, '-j', pid, '-n'], test=True)
        finally:
            sys.stdout = old_stdout
            shutil.rmtree(tempdir)
        output = new_stdout.getvalue()
        self.assertGreater(len(output), 0)

    def test_silent_on(self):
        from supervisor.supervisord import main
        conf = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), 'fixtures',
            'donothing.conf')
        new_stdout = StringIO()
        new_stdout.fileno = lambda: 1
        old_stdout = sys.stdout

        try:
            tempdir = tempfile.mkdtemp()
            log = os.path.join(tempdir, 'log')
            pid = os.path.join(tempdir, 'pid')
            sys.stdout = new_stdout
            main(args=['-c', conf, '-l', log, '-j', pid, '-n', '-s'], test=True)
        finally:
            sys.stdout = old_stdout
            shutil.rmtree(tempdir)
        output = new_stdout.getvalue()
        self.assertEqual(len(output), 0)

class SupervisordTests(unittest.TestCase):
    def tearDown(self):
        from supervisor.events import clear
        clear()

    def _getTargetClass(self):
        from supervisor.supervisord import Supervisor
        return Supervisor

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test_main_first(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', '/bin/foo')
        gconfigs = [DummyPGroupConfig(options,'foo', pconfigs=[pconfig])]
        options.process_group_configs = gconfigs
        options.test = True
        options.first = True
        supervisord = self._makeOne(options)
        supervisord.main()
        self.assertEqual(options.environment_processed, True)
        self.assertEqual(options.fds_cleaned_up, False)
        self.assertEqual(options.rlimits_set, True)
        self.assertEqual(options.parse_criticals, ['setuid_called'])
        self.assertEqual(options.parse_warnings, [])
        self.assertEqual(options.parse_infos, ['rlimits_set'])
        self.assertEqual(options.autochildlogdir_cleared, True)
        self.assertEqual(len(supervisord.process_groups), 1)
        self.assertEqual(supervisord.process_groups['foo'].config.options,
                         options)
        self.assertEqual(options.environment_processed, True)
        self.assertEqual(options.httpservers_opened, True)
        self.assertEqual(options.signals_set, True)
        self.assertEqual(options.daemonized, True)
        self.assertEqual(options.pidfile_written, True)
        self.assertEqual(options.cleaned_up, True)

    def test_main_notfirst(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', '/bin/foo')
        gconfigs = [DummyPGroupConfig(options,'foo', pconfigs=[pconfig])]
        options.process_group_configs = gconfigs
        options.test = True
        options.first = False
        supervisord = self._makeOne(options)
        supervisord.main()
        self.assertEqual(options.environment_processed, True)
        self.assertEqual(options.fds_cleaned_up, True)
        self.assertFalse(hasattr(options, 'rlimits_set'))
        self.assertEqual(options.parse_criticals, ['setuid_called'])
        self.assertEqual(options.parse_warnings, [])
        self.assertEqual(options.parse_infos, [])
        self.assertEqual(options.autochildlogdir_cleared, True)
        self.assertEqual(len(supervisord.process_groups), 1)
        self.assertEqual(supervisord.process_groups['foo'].config.options,
                         options)
        self.assertEqual(options.environment_processed, True)
        self.assertEqual(options.httpservers_opened, True)
        self.assertEqual(options.signals_set, True)
        self.assertEqual(options.daemonized, False)
        self.assertEqual(options.pidfile_written, True)
        self.assertEqual(options.cleaned_up, True)

    def test_reap(self):
        options = DummyOptions()
        options.waitpid_return = 1, 1
        pconfig = DummyPConfig(options, 'process', 'process', '/bin/process1')
        process = DummyProcess(pconfig)
        process.drained = False
        process.killing = True
        process.laststop = None
        process.waitstatus = None, None
        options.pidhistory = {1:process}
        supervisord = self._makeOne(options)

        supervisord.reap(once=True)
        self.assertEqual(process.finished, (1,1))

    def test_reap_recursionguard(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)
        result = supervisord.reap(once=True, recursionguard=100)
        self.assertEqual(result, None)

    def test_reap_more_than_once(self):
        options = DummyOptions()
        options.waitpid_return = 1, 1
        pconfig = DummyPConfig(options, 'process', 'process', '/bin/process1')
        process = DummyProcess(pconfig)
        process.drained = False
        process.killing = True
        process.laststop = None
        process.waitstatus = None, None
        options.pidhistory = {1:process}
        supervisord = self._makeOne(options)

        supervisord.reap(recursionguard=99)
        self.assertEqual(process.finished, (1,1))

    def test_reap_unknown_pid(self):
        options = DummyOptions()
        options.waitpid_return = 2, 0 # pid, status
        pconfig = DummyPConfig(options, 'process', 'process', '/bin/process1')
        process = DummyProcess(pconfig)
        process.drained = False
        process.killing = True
        process.laststop = None
        process.waitstatus = None, None
        options.pidhistory = {1: process}
        supervisord = self._makeOne(options)

        supervisord.reap(once=True)
        self.assertEqual(process.finished, None)
        self.assertEqual(options.logger.data[0],
                         'reaped unknown pid 2 (exit status 0)')

    def test_handle_sigterm(self):
        options = DummyOptions()
        options._signal = signal.SIGTERM
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.SHUTDOWN)
        self.assertEqual(options.logger.data[0],
                         'received SIGTERM indicating exit request')

    def test_handle_sigint(self):
        options = DummyOptions()
        options._signal = signal.SIGINT
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.SHUTDOWN)
        self.assertEqual(options.logger.data[0],
                         'received SIGINT indicating exit request')

    def test_handle_sigquit(self):
        options = DummyOptions()
        options._signal = signal.SIGQUIT
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.SHUTDOWN)
        self.assertEqual(options.logger.data[0],
                         'received SIGQUIT indicating exit request')

    def test_handle_sighup_in_running_state(self):
        options = DummyOptions()
        options._signal = signal.SIGHUP
        supervisord = self._makeOne(options)
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.RUNNING)
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.RESTARTING)
        self.assertEqual(options.logger.data[0],
                         'received SIGHUP indicating restart request')

    def test_handle_sighup_in_shutdown_state(self):
        options = DummyOptions()
        options._signal = signal.SIGHUP
        supervisord = self._makeOne(options)
        supervisord.options.mood = SupervisorStates.SHUTDOWN
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.SHUTDOWN)
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.SHUTDOWN) # unchanged
        self.assertEqual(options.logger.data[0],
                         'ignored SIGHUP indicating restart request '
                         '(shutdown in progress)')

    def test_handle_sigchld(self):
        options = DummyOptions()
        options._signal = signal.SIGCHLD
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.RUNNING)
        # supervisor.options.signame(signal.SIGCHLD) may return "SIGCLD"
        # on linux or other systems where SIGCHLD = SIGCLD.
        msgs = ('received SIGCHLD indicating a child quit',
                'received SIGCLD indicating a child quit')
        self.assertTrue(options.logger.data[0] in msgs)

    def test_handle_sigusr2(self):
        options = DummyOptions()
        options._signal = signal.SIGUSR2
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1
        supervisord = self._makeOne(options)
        pconfigs = [DummyPConfig(options, 'foo', 'foo', '/bin/foo')]
        options.process_group_configs = DummyPGroupConfig(
            options, 'foo',
            pconfigs=pconfigs)
        dummypgroup = DummyProcessGroup(options)
        supervisord.process_groups = {None:dummypgroup}
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.RUNNING)
        self.assertEqual(options.logs_reopened, True)
        self.assertEqual(options.logger.data[0],
                         'received SIGUSR2 indicating log reopen request')
        self.assertEqual(dummypgroup.logs_reopened, True)

    def test_handle_unknown_signal(self):
        options = DummyOptions()
        options._signal = signal.SIGUSR1
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.options.mood,
                         SupervisorStates.RUNNING)
        self.assertEqual(options.logger.data[0],
                         'received SIGUSR1 indicating nothing')

    def test_get_state(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)
        self.assertEqual(supervisord.get_state(), SupervisorStates.RUNNING)

    def test_diff_add_remove(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)

        pconfig = DummyPConfig(options, 'process1', 'process1')
        group1 = DummyPGroupConfig(options, 'group1', pconfigs=[pconfig])

        pconfig = DummyPConfig(options, 'process2', 'process2')
        group2 = DummyPGroupConfig(options, 'group2', pconfigs=[pconfig])

        new = [group1, group2]

        added, changed, removed = supervisord.diff_to_active()
        self.assertEqual(added, [])
        self.assertEqual(changed, [])
        self.assertEqual(removed, [])

        added, changed, removed = supervisord.diff_to_active(new)
        self.assertEqual(added, new)
        self.assertEqual(changed, [])
        self.assertEqual(removed, [])

        supervisord.options.process_group_configs = new
        added, changed, removed = supervisord.diff_to_active()
        self.assertEqual(added, new)

        supervisord.add_process_group(group1)
        supervisord.add_process_group(group2)

        pconfig = DummyPConfig(options, 'process3', 'process3')
        new_group1 = DummyPGroupConfig(options, pconfigs=[pconfig])

        pconfig = DummyPConfig(options, 'process4', 'process4')
        new_group2 = DummyPGroupConfig(options, pconfigs=[pconfig])

        new = [group2, new_group1, new_group2]

        added, changed, removed = supervisord.diff_to_active(new)
        self.assertEqual(added, [new_group1, new_group2])
        self.assertEqual(changed, [])
        self.assertEqual(removed, [group1])

    def test_diff_changed(self):
        from supervisor.options import ProcessConfig, ProcessGroupConfig

        options = DummyOptions()
        supervisord = self._makeOne(options)

        def make_pconfig(name, command, **params):
            result = {
                'name': name, 'command': command,
                'directory': None, 'umask': None, 'priority': 999, 'autostart': True,
                'autorestart': True, 'startsecs': 10, 'startretries': 999,
                'uid': None, 'stdout_logfile': None, 'stdout_capture_maxbytes': 0,
                'stdout_events_enabled': False,
                'stdout_logfile_backups': 0, 'stdout_logfile_maxbytes': 0,
                'stdout_syslog': False,
                'stderr_logfile': None, 'stderr_capture_maxbytes': 0,
                'stderr_events_enabled': False,
                'stderr_logfile_backups': 0, 'stderr_logfile_maxbytes': 0,
                'stderr_syslog': False,
                'redirect_stderr': False,
                'stopsignal': None, 'stopwaitsecs': 10,
                'stopasgroup': False,
                'killasgroup': False,
                'exitcodes': (0,), 'environment': None, 'serverurl': None,
            }
            result.update(params)
            return ProcessConfig(options, **result)

        def make_gconfig(name, pconfigs):
            return ProcessGroupConfig(options, name, 25, pconfigs)

        pconfig = make_pconfig('process1', 'process1', uid='new')
        group1 = make_gconfig('group1', [pconfig])

        pconfig = make_pconfig('process2', 'process2')
        group2 = make_gconfig('group2', [pconfig])
        new = [group1, group2]

        pconfig = make_pconfig('process1', 'process1', uid='old')
        group3 = make_gconfig('group1', [pconfig])

        pconfig = make_pconfig('process2', 'process2')
        group4 = make_gconfig('group2', [pconfig])
        supervisord.add_process_group(group3)
        supervisord.add_process_group(group4)

        added, changed, removed = supervisord.diff_to_active(new)

        self.assertEqual([added, removed], [[], []])
        self.assertEqual(changed, [group1])

        options = DummyOptions()
        supervisord = self._makeOne(options)

        pconfig1 = make_pconfig('process1', 'process1')
        pconfig2 = make_pconfig('process2', 'process2')
        group1 = make_gconfig('group1', [pconfig1, pconfig2])
        new = [group1]

        supervisord.add_process_group(make_gconfig('group1', [pconfig1]))

        added, changed, removed = supervisord.diff_to_active(new)
        self.assertEqual([added, removed], [[], []])
        self.assertEqual(changed, [group1])

    def test_diff_changed_eventlistener(self):
        from supervisor.events import EventTypes
        from supervisor.options import EventListenerConfig, EventListenerPoolConfig

        options = DummyOptions()
        supervisord = self._makeOne(options)

        def make_pconfig(name, command, **params):
            result = {
                'name': name, 'command': command,
                'directory': None, 'umask': None, 'priority': 999, 'autostart': True,
                'autorestart': True, 'startsecs': 10, 'startretries': 999,
                'uid': None, 'stdout_logfile': None, 'stdout_capture_maxbytes': 0,
                'stdout_events_enabled': False,
                'stdout_logfile_backups': 0, 'stdout_logfile_maxbytes': 0,
                'stdout_syslog': False,
                'stderr_logfile': None, 'stderr_capture_maxbytes': 0,
                'stderr_events_enabled': False,
                'stderr_logfile_backups': 0, 'stderr_logfile_maxbytes': 0,
                'stderr_syslog': False,
                'redirect_stderr': False,
                'stopsignal': None, 'stopwaitsecs': 10,
                'stopasgroup': False,
                'killasgroup': False,
                'exitcodes': (0,), 'environment': None, 'serverurl': None,
            }
            result.update(params)
            return EventListenerConfig(options, **result)

        def make_econfig(*pool_event_names):
            result = []
            for pool_event_name in pool_event_names:
                result.append(getattr(EventTypes, pool_event_name, None))
            return result

        def make_gconfig(name, pconfigs, pool_events, result_handler='supervisor.dispatchers:default_handler'):
            return EventListenerPoolConfig(options, name, 25, pconfigs, 10, pool_events, result_handler)

	    # Test that changing an event listener command causes the diff_to_activate
        pconfig = make_pconfig('process1', 'process1-new')
        econfig = make_econfig("TICK_60")
        group1 = make_gconfig('group1', [pconfig], econfig)

        pconfig = make_pconfig('process2', 'process2')
        econfig = make_econfig("TICK_3600")
        group2 = make_gconfig('group2', [pconfig], econfig)
        new = [group1, group2]

        pconfig = make_pconfig('process1', 'process1-old')
        econfig = make_econfig("TICK_60")
        group3 = make_gconfig('group1', [pconfig], econfig)

        pconfig = make_pconfig('process2', 'process2')
        econfig = make_econfig("TICK_3600")
        group4 = make_gconfig('group2', [pconfig], econfig)
        supervisord.add_process_group(group3)
        supervisord.add_process_group(group4)

        added, changed, removed = supervisord.diff_to_active(new)

        self.assertEqual([added, removed], [[], []])
        self.assertEqual(changed, [group1])

        # Test that changing the event triggers diff_to_activate
        options = DummyOptions()
        supervisord = self._makeOne(options)

        pconfig = make_pconfig('process1', 'process1')
        econfig = make_econfig("TICK_60")
        group1 = make_gconfig('group1', [pconfig], econfig)

        pconfig = make_pconfig('process2', 'process2')
        econfig = make_econfig("TICK_3600")
        group2 = make_gconfig('group2', [pconfig], econfig)
        new = [group1, group2]

        pconfig = make_pconfig('process1', 'process1')
        econfig = make_econfig("TICK_5")
        group3 = make_gconfig('group1', [pconfig], econfig)

        pconfig = make_pconfig('process2', 'process2')
        econfig = make_econfig("TICK_3600")
        group4 = make_gconfig('group2', [pconfig], econfig)
        supervisord.add_process_group(group3)
        supervisord.add_process_group(group4)

        added, changed, removed = supervisord.diff_to_active(new)

        self.assertEqual([added, removed], [[], []])
        self.assertEqual(changed, [group1])

        # Test that changing the result_handler triggers diff_to_activate
        options = DummyOptions()
        supervisord = self._makeOne(options)

        pconfig = make_pconfig('process1', 'process1')
        econfig = make_econfig("TICK_60")
        group1 = make_gconfig('group1', [pconfig], econfig, 'new-result-handler')

        pconfig = make_pconfig('process2', 'process2')
        econfig = make_econfig("TICK_3600")
        group2 = make_gconfig('group2', [pconfig], econfig)
        new = [group1, group2]

        pconfig = make_pconfig('process1', 'process1')
        econfig = make_econfig("TICK_60")
        group3 = make_gconfig('group1', [pconfig], econfig, 'old-result-handler')

        pconfig = make_pconfig('process2', 'process2')
        econfig = make_econfig("TICK_3600")
        group4 = make_gconfig('group2', [pconfig], econfig)
        supervisord.add_process_group(group3)
        supervisord.add_process_group(group4)

        added, changed, removed = supervisord.diff_to_active(new)

        self.assertEqual([added, removed], [[], []])
        self.assertEqual(changed, [group1])

    def test_add_process_group(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(options,'foo', pconfigs=[pconfig])
        options.process_group_configs = [gconfig]
        supervisord = self._makeOne(options)

        self.assertEqual(supervisord.process_groups, {})

        result = supervisord.add_process_group(gconfig)
        self.assertEqual(list(supervisord.process_groups.keys()), ['foo'])
        self.assertTrue(result)

        group = supervisord.process_groups['foo']
        result = supervisord.add_process_group(gconfig)
        self.assertEqual(group, supervisord.process_groups['foo'])
        self.assertTrue(not result)

    def test_add_process_group_event(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(1)
        events.subscribe(events.ProcessGroupAddedEvent, callback)
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(options,'foo', pconfigs=[pconfig])
        options.process_group_configs = [gconfig]
        supervisord = self._makeOne(options)

        supervisord.add_process_group(gconfig)

        options.test = True
        supervisord.runforever()
        self.assertEqual(L, [1])

    def test_remove_process_group(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(options, 'foo', pconfigs=[pconfig])
        supervisord = self._makeOne(options)

        self.assertRaises(KeyError, supervisord.remove_process_group, 'asdf')

        supervisord.add_process_group(gconfig)
        group = supervisord.process_groups['foo']
        result = supervisord.remove_process_group('foo')
        self.assertTrue(group.before_remove_called)
        self.assertEqual(supervisord.process_groups, {})
        self.assertTrue(result)

        supervisord.add_process_group(gconfig)
        supervisord.process_groups['foo'].unstopped_processes = [DummyProcess(None)]
        result = supervisord.remove_process_group('foo')
        self.assertEqual(list(supervisord.process_groups.keys()), ['foo'])
        self.assertTrue(not result)

    def test_remove_process_group_event(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(1)
        events.subscribe(events.ProcessGroupRemovedEvent, callback)
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo', '/bin/foo')
        gconfig = DummyPGroupConfig(options,'foo', pconfigs=[pconfig])
        options.process_group_configs = [gconfig]
        supervisord = self._makeOne(options)

        supervisord.add_process_group(gconfig)
        supervisord.process_groups['foo'].stopped_processes = [DummyProcess(None)]
        supervisord.remove_process_group('foo')
        options.test = True
        supervisord.runforever()

        self.assertEqual(L, [1])

    def test_runforever_emits_generic_startup_event(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(1)
        events.subscribe(events.SupervisorStateChangeEvent, callback)
        options = DummyOptions()
        supervisord = self._makeOne(options)
        options.test = True
        supervisord.runforever()
        self.assertEqual(L, [1])

    def test_runforever_emits_generic_specific_event(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(2)
        events.subscribe(events.SupervisorRunningEvent, callback)
        options = DummyOptions()
        options.test = True
        supervisord = self._makeOne(options)
        supervisord.runforever()
        self.assertEqual(L, [2])

    def test_runforever_calls_tick(self):
        options = DummyOptions()
        options.test = True
        supervisord = self._makeOne(options)
        self.assertEqual(len(supervisord.ticks), 0)
        supervisord.runforever()
        self.assertEqual(len(supervisord.ticks), 3)

    def test_runforever_poll_dispatchers(self):
        options = DummyOptions()
        options.poller.result = [6], [7, 8]
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)
        readable = DummyDispatcher(readable=True)
        writable = DummyDispatcher(writable=True)
        error = DummyDispatcher(writable=True, error=OSError)
        pgroup.dispatchers = {6:readable, 7:writable, 8:error}
        supervisord.process_groups = {'foo': pgroup}
        options.test = True
        supervisord.runforever()
        self.assertEqual(pgroup.transitioned, True)
        self.assertEqual(readable.read_event_handled, True)
        self.assertEqual(writable.write_event_handled, True)
        self.assertEqual(error.error_handled, True)

    def test_runforever_select_dispatcher_exitnow_via_read(self):
        options = DummyOptions()
        options.poller.result = [6], []
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)
        from supervisor.medusa import asyncore_25 as asyncore
        exitnow = DummyDispatcher(readable=True, error=asyncore.ExitNow)
        pgroup.dispatchers = {6:exitnow}
        supervisord.process_groups = {'foo': pgroup}
        options.test = True
        self.assertRaises(asyncore.ExitNow, supervisord.runforever)

    def test_runforever_select_dispatcher_exitnow_via_write(self):
        options = DummyOptions()
        options.poller.result = [], [6]
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)
        from supervisor.medusa import asyncore_25 as asyncore
        exitnow = DummyDispatcher(readable=True, error=asyncore.ExitNow)
        pgroup.dispatchers = {6:exitnow}
        supervisord.process_groups = {'foo': pgroup}
        options.test = True
        self.assertRaises(asyncore.ExitNow, supervisord.runforever)

    def test_runforever_select_dispatcher_handle_error_via_read(self):
        options = DummyOptions()
        options.poller.result = [6], []
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)
        notimpl = DummyDispatcher(readable=True, error=NotImplementedError)
        pgroup.dispatchers = {6:notimpl}
        supervisord.process_groups = {'foo': pgroup}
        options.test = True
        supervisord.runforever()
        self.assertEqual(notimpl.error_handled, True)

    def test_runforever_select_dispatcher_handle_error_via_write(self):
        options = DummyOptions()
        options.poller.result = [], [6]
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)
        notimpl = DummyDispatcher(readable=True, error=NotImplementedError)
        pgroup.dispatchers = {6:notimpl}
        supervisord.process_groups = {'foo': pgroup}
        options.test = True
        supervisord.runforever()
        self.assertEqual(notimpl.error_handled, True)

    def test_runforever_stopping_emits_events(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)
        gconfig = DummyPGroupConfig(options)
        pgroup = DummyProcessGroup(gconfig)
        supervisord.process_groups = {'foo': pgroup}
        supervisord.options.mood = SupervisorStates.SHUTDOWN
        L = []
        def callback(event):
            L.append(event)
        from supervisor import events
        events.subscribe(events.SupervisorStateChangeEvent, callback)
        from supervisor.medusa import asyncore_25 as asyncore
        options.test = True
        self.assertRaises(asyncore.ExitNow, supervisord.runforever)
        self.assertTrue(pgroup.all_stopped)
        self.assertTrue(isinstance(L[0], events.SupervisorRunningEvent))
        self.assertTrue(isinstance(L[0], events.SupervisorStateChangeEvent))
        self.assertTrue(isinstance(L[1], events.SupervisorStoppingEvent))
        self.assertTrue(isinstance(L[1], events.SupervisorStateChangeEvent))

    def test_exit(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)
        L = []
        def callback():
            L.append(1)
        supervisord.process_groups = {'foo': pgroup}
        supervisord.options.mood = SupervisorStates.RESTARTING
        supervisord.options.test = True
        from supervisor.medusa import asyncore_25 as asyncore
        self.assertRaises(asyncore.ExitNow, supervisord.runforever)
        self.assertEqual(pgroup.all_stopped, True)

    def test_exit_delayed(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',)
        process = DummyProcess(pconfig)
        gconfig = DummyPGroupConfig(options, pconfigs=[pconfig])
        pgroup = DummyProcessGroup(gconfig)
        pgroup.unstopped_processes = [process]
        L = []
        def callback():
            L.append(1)
        supervisord.process_groups = {'foo': pgroup}
        supervisord.options.mood = SupervisorStates.RESTARTING
        supervisord.options.test = True
        supervisord.runforever()
        self.assertNotEqual(supervisord.lastshutdownreport, 0)

    def test_getSupervisorStateDescription(self):
        from supervisor.states import getSupervisorStateDescription
        result = getSupervisorStateDescription(SupervisorStates.RUNNING)
        self.assertEqual(result, 'RUNNING')

    def test_tick(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(event)
        events.subscribe(events.TickEvent, callback)
        options = DummyOptions()
        supervisord = self._makeOne(options)

        supervisord.tick(now=0)
        self.assertEqual(supervisord.ticks[5], 0)
        self.assertEqual(supervisord.ticks[60], 0)
        self.assertEqual(supervisord.ticks[3600], 0)
        self.assertEqual(len(L), 0)

        supervisord.tick(now=6)
        self.assertEqual(supervisord.ticks[5], 5)
        self.assertEqual(supervisord.ticks[60], 0)
        self.assertEqual(supervisord.ticks[3600], 0)
        self.assertEqual(len(L), 1)
        self.assertEqual(L[-1].__class__, events.Tick5Event)

        supervisord.tick(now=61)
        self.assertEqual(supervisord.ticks[5], 60)
        self.assertEqual(supervisord.ticks[60], 60)
        self.assertEqual(supervisord.ticks[3600], 0)
        self.assertEqual(len(L), 3)
        self.assertEqual(L[-1].__class__, events.Tick60Event)

        supervisord.tick(now=3601)
        self.assertEqual(supervisord.ticks[5], 3600)
        self.assertEqual(supervisord.ticks[60], 3600)
        self.assertEqual(supervisord.ticks[3600], 3600)
        self.assertEqual(len(L), 6)
        self.assertEqual(L[-1].__class__, events.Tick3600Event)

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

