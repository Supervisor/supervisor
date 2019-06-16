import sys
import unittest
from supervisor import xmlrpc
from supervisor.compat import StringIO
from supervisor.compat import xmlrpclib
from supervisor.supervisorctl import LSBInitExitStatuses, LSBStatusExitStatuses
from supervisor.tests.base import DummyRPCServer

class fgthread_Tests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.supervisorctl import fgthread
        return fgthread

    def _makeOne(self, program, ctl):
        return self._getTargetClass()(program, ctl)

    def test_ctor(self):
        options = DummyClientOptions()
        ctl = DummyController(options)
        inst = self._makeOne(None, ctl)
        self.assertEqual(inst.killed, False)

    def test_globaltrace_call(self):
        options = DummyClientOptions()
        ctl = DummyController(options)
        inst = self._makeOne(None, ctl)
        result = inst.globaltrace(None, 'call', None)
        self.assertEqual(result, inst.localtrace)

    def test_globaltrace_noncall(self):
        options = DummyClientOptions()
        ctl = DummyController(options)
        inst = self._makeOne(None, ctl)
        result = inst.globaltrace(None, None, None)
        self.assertEqual(result, None)

    def test_localtrace_killed_whyline(self):
        options = DummyClientOptions()
        ctl = DummyController(options)
        inst = self._makeOne(None, ctl)
        inst.killed = True
        try:
            inst.localtrace(None, 'line', None)
        except SystemExit as e:
            self.assertEqual(e.code, None)
        else:
            self.fail("No exception thrown. Excepted SystemExit")

    def test_localtrace_killed_not_whyline(self):
        options = DummyClientOptions()
        ctl = DummyController(options)
        inst = self._makeOne(None, ctl)
        inst.killed = True
        result = inst.localtrace(None, None, None)
        self.assertEqual(result, inst.localtrace)

    def test_kill(self):
        options = DummyClientOptions()
        ctl = DummyController(options)
        inst = self._makeOne(None, ctl)
        inst.killed = True
        class DummyCloseable(object):
            def close(self):
                self.closed = True
        inst.output_handler = DummyCloseable()
        inst.error_handler = DummyCloseable()
        inst.kill()
        self.assertTrue(inst.killed)
        self.assertTrue(inst.output_handler.closed)
        self.assertTrue(inst.error_handler.closed)

class ControllerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.supervisorctl import Controller
        return Controller

    def _makeOne(self, options):
        return self._getTargetClass()(options)


    def test_ctor(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        self.assertEqual(controller.prompt, options.prompt + '> ')

    def test__upcheck(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        result = controller.upcheck()
        self.assertEqual(result, True)

    def test__upcheck_wrong_server_version(self):
        options = DummyClientOptions()
        options._server.supervisor.getVersion = lambda *x: '1.0'
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.upcheck()
        self.assertEqual(result, False)
        self.assertEqual(controller.stdout.getvalue(),
                         'Sorry, this version of supervisorctl expects'
                         ' to talk to a server with API version 3.0, but'
                         ' the remote version is 1.0.\n')

    def test__upcheck_unknown_method(self):
        options = DummyClientOptions()
        from supervisor.xmlrpc import Faults
        def getVersion():
            raise xmlrpclib.Fault(Faults.UNKNOWN_METHOD, 'duh')
        options._server.supervisor.getVersion = getVersion
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.upcheck()
        self.assertEqual(result, False)
        self.assertEqual(controller.stdout.getvalue(),
                         'Sorry, supervisord responded but did not recognize'
                         ' the supervisor namespace commands that'
                         ' supervisorctl uses to control it.  Please check'
                         ' that the [rpcinterface:supervisor] section is'
                         ' enabled in the configuration file'
                         ' (see sample.conf).\n')

    def test__upcheck_reraises_other_xmlrpc_faults(self):
        options = DummyClientOptions()
        from supervisor.xmlrpc import Faults
        def f(*arg, **kw):
            raise xmlrpclib.Fault(Faults.FAILED, '')
        options._server.supervisor.getVersion = f
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        self.assertRaises(xmlrpclib.Fault, controller.upcheck)
        self.assertEqual(controller.exitstatus, LSBInitExitStatuses.GENERIC)

    def test__upcheck_catches_socket_error_ECONNREFUSED(self):
        options = DummyClientOptions()
        import socket
        import errno
        def raise_fault(*arg, **kw):
            raise socket.error(errno.ECONNREFUSED, 'nobody home')
        options._server.supervisor.getVersion = raise_fault

        controller = self._makeOne(options)
        controller.stdout = StringIO()

        result = controller.upcheck()
        self.assertEqual(result, False)

        output = controller.stdout.getvalue()
        self.assertTrue('refused connection' in output)
        self.assertEqual(controller.exitstatus, LSBInitExitStatuses.INSUFFICIENT_PRIVILEGES)

    def test__upcheck_catches_socket_error_ENOENT(self):
        options = DummyClientOptions()
        import socket
        import errno
        def raise_fault(*arg, **kw):
            raise socket.error(errno.ENOENT, 'nobody home')
        options._server.supervisor.getVersion = raise_fault

        controller = self._makeOne(options)
        controller.stdout = StringIO()

        result = controller.upcheck()
        self.assertEqual(result, False)

        output = controller.stdout.getvalue()
        self.assertTrue('no such file' in output)
        self.assertEqual(controller.exitstatus, LSBInitExitStatuses.NOT_RUNNING)

    def test__upcheck_reraises_other_socket_faults(self):
        options = DummyClientOptions()
        import socket
        import errno
        def f(*arg, **kw):
            raise socket.error(errno.EBADF, '')
        options._server.supervisor.getVersion = f
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        self.assertRaises(socket.error, controller.upcheck)

    def test_onecmd(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        plugin = DummyPlugin()
        controller.options.plugins = (plugin,)
        result = controller.onecmd('help')
        self.assertEqual(result, None)
        self.assertEqual(plugin.helped, True)

    def test_onecmd_empty_does_not_repeat_previous_cmd(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        plugin = DummyPlugin()
        controller.options.plugins = (plugin,)
        plugin.helped = False
        controller.onecmd('help')
        self.assertTrue(plugin.helped)
        plugin.helped = False
        controller.onecmd('')
        self.assertFalse(plugin.helped)

    def test_onecmd_clears_completion_cache(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        controller._complete_info = {}
        controller.onecmd('help')
        self.assertEqual(controller._complete_info, None)

    def test_onecmd_bad_command_error(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        controller.onecmd("badcmd")
        self.assertEqual(controller.stdout.getvalue(),
            "*** Unknown syntax: badcmd\n")
        self.assertEqual(controller.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_complete_action_empty(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help']
        result = controller.complete('', 0, line='')
        self.assertEqual(result, 'help ')
        result = controller.complete('', 1, line='')
        self.assertEqual(result, None)

    def test_complete_action_partial(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help']
        result = controller.complete('h', 0, line='h')
        self.assertEqual(result, 'help ')
        result = controller.complete('h', 1, line='h')
        self.assertEqual(result, None)

    def test_complete_action_whole(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help']
        result = controller.complete('help', 0, line='help')
        self.assertEqual(result, 'help ')

    def test_complete_unknown_action_uncompletable(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        result = controller.complete('bad', 0, line='bad')
        self.assertEqual(result, None)

    def test_complete_unknown_action_arg_uncompletable(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'add']
        result = controller.complete('', 1, line='bad ')
        self.assertEqual(result, None)

    def test_complete_help_empty(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'start']
        result = controller.complete('', 0, line='help ')
        self.assertEqual(result, 'help ')
        result = controller.complete('', 1, line='help ')
        self.assertEqual(result, 'start ')
        result = controller.complete('', 2, line='help ')
        self.assertEqual(result, None)

    def test_complete_help_action(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'start']
        result = controller.complete('he', 0, line='help he')
        self.assertEqual(result, 'help ')
        result = controller.complete('he', 1, line='help he')
        self.assertEqual(result, None)

    def test_complete_start_empty(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'start']
        result = controller.complete('', 0, line='start ')
        self.assertEqual(result, 'foo ')
        result = controller.complete('', 1, line='start ')
        self.assertEqual(result, 'bar ')
        result = controller.complete('', 2, line='start ')
        self.assertEqual(result, 'baz:baz_01 ')
        result = controller.complete('', 3, line='start ')
        self.assertEqual(result, 'baz:* ')
        result = controller.complete('', 4, line='start ')
        self.assertEqual(result, None)

    def test_complete_start_no_colon(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'start']
        result = controller.complete('f', 0, line='start f')
        self.assertEqual(result, 'foo ')
        result = controller.complete('f', 1, line='start f')
        self.assertEqual(result, None)

    def test_complete_start_with_colon(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'start']
        result = controller.complete('foo:', 0, line='start foo:')
        self.assertEqual(result, 'foo:foo ')
        result = controller.complete('foo:', 1, line='start foo:')
        self.assertEqual(result, 'foo:* ')
        result = controller.complete('foo:', 2, line='start foo:')
        self.assertEqual(result, None)

    def test_complete_start_uncompletable(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'start']
        result = controller.complete('bad', 0, line='start bad')
        self.assertEqual(result, None)

    def test_complete_caches_process_info(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'start']
        result = controller.complete('', 0, line='start ')
        self.assertNotEqual(result, None)
        def f(*arg, **kw):
            raise Exception("should not have called getAllProcessInfo")
        controller.options._server.supervisor.getAllProcessInfo = f
        controller.complete('', 1, line='start ')

    def test_complete_add_empty(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'add']
        result = controller.complete('', 0, line='add ')
        self.assertEqual(result, 'foo ')
        result = controller.complete('', 1, line='add ')
        self.assertEqual(result, 'bar ')
        result = controller.complete('', 2, line='add ')
        self.assertEqual(result, 'baz ')
        result = controller.complete('', 3, line='add ')
        self.assertEqual(result, None)

    def test_complete_add_uncompletable(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'add']
        result = controller.complete('bad', 0, line='add bad')
        self.assertEqual(result, None)

    def test_complete_add_group(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'add']
        result = controller.complete('f', 0, line='add f')
        self.assertEqual(result, 'foo ')
        result = controller.complete('f', 1, line='add f')
        self.assertEqual(result, None)

    def test_complete_reload_arg_uncompletable(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout=StringIO()
        controller.vocab = ['help', 'reload']
        result = controller.complete('', 1, line='reload ')
        self.assertEqual(result, None)

    def test_nohelp(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        self.assertEqual(controller.nohelp, '*** No help on %s')

    def test_do_help(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        results = controller.do_help('')
        helpval = controller.stdout.getvalue()
        self.assertEqual(results, None)
        self.assertEqual(helpval, 'foo helped')

    def test_do_help_for_help(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        results = controller.do_help("help")
        self.assertEqual(results, None)
        helpval = controller.stdout.getvalue()
        self.assertTrue("help\t\tPrint a list" in helpval)

    def test_get_supervisor_returns_serverproxy_supervisor_namespace(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)

        proxy = controller.get_supervisor()
        expected = options.getServerProxy().supervisor
        self.assertEqual(proxy, expected)

    def test_get_server_proxy_with_no_args_returns_serverproxy(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)

        proxy = controller.get_server_proxy()
        expected = options.getServerProxy()
        self.assertEqual(proxy, expected)

    def test_get_server_proxy_with_namespace_returns_that_namespace(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)

        proxy = controller.get_server_proxy('system')
        expected = options.getServerProxy().system
        self.assertEqual(proxy, expected)

    def test_real_controller_initialization(self):
        from supervisor.options import ClientOptions
        args = [] # simulating starting without parameters
        options = ClientOptions()

        # No default config file search in case they would exist
        self.assertTrue(len(options.searchpaths) > 0)
        options.searchpaths = []

        options.realize(args, doc=__doc__)
        self._makeOne(options) # should not raise


class TestControllerPluginBase(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.supervisorctl import ControllerPluginBase
        return ControllerPluginBase

    def _makeOne(self, *arg, **kw):
        klass = self._getTargetClass()
        options = DummyClientOptions()
        ctl = DummyController(options)
        plugin = klass(ctl, *arg, **kw)
        return plugin

    def test_do_help_noarg(self):
        plugin = self._makeOne()
        result = plugin.do_help(None)
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), '\n')
        self.assertEqual(len(plugin.ctl.topics_printed), 1)
        topics = plugin.ctl.topics_printed[0]
        self.assertEqual(topics[0], 'unnamed commands (type help <topic>):')
        self.assertEqual(topics[1], [])
        self.assertEqual(topics[2], 15)
        self.assertEqual(topics[3], 80)

    def test_do_help_witharg(self):
        plugin = self._makeOne()
        result = plugin.do_help('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'no help on foo\n')
        self.assertEqual(len(plugin.ctl.topics_printed), 0)

class TestDefaultControllerPlugin(unittest.TestCase):

    def _getTargetClass(self):
        from supervisor.supervisorctl import DefaultControllerPlugin
        return DefaultControllerPlugin

    def _makeOne(self, *arg, **kw):
        klass = self._getTargetClass()
        options = DummyClientOptions()
        ctl = DummyController(options)
        plugin = klass(ctl, *arg, **kw)
        return plugin

    def test_tail_toofewargs(self):
        plugin = self._makeOne()
        result = plugin.do_tail('')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: too few arguments')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_toomanyargs(self):
        plugin = self._makeOne()
        result = plugin.do_tail('one two three four')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: too many arguments')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_f_noprocname(self):
        plugin = self._makeOne()
        result = plugin.do_tail('-f')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: tail requires process name')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_bad_modifier(self):
        plugin = self._makeOne()
        result = plugin.do_tail('-z foo')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: bad argument -z')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_defaults(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'stdout line')

    def test_tail_no_file(self):
        plugin = self._makeOne()
        result = plugin.do_tail('NO_FILE')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'NO_FILE: ERROR (no log file)')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_failed(self):
        plugin = self._makeOne()
        result = plugin.do_tail('FAILED')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'FAILED: ERROR (unknown error reading log)')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_bad_name(self):
        plugin = self._makeOne()
        result = plugin.do_tail('BAD_NAME')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'BAD_NAME: ERROR (no such process name)')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_bytesmodifier(self):
        plugin = self._makeOne()
        result = plugin.do_tail('-10 foo')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], 'dout line')

    def test_tail_explicit_channel_stdout_nomodifier(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo stdout')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'stdout line')

    def test_tail_explicit_channel_stderr_nomodifier(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo stderr')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'stderr line')

    def test_tail_explicit_channel_unrecognized(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo fudge')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().strip()
        self.assertEqual(value, "Error: bad channel 'fudge'")
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_tail_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        plugin.ctl.options._server.supervisor.readProcessStdoutLog = f
        plugin.do_tail('foo')
        self.assertEqual(called, [])

    def test_status_help(self):
        plugin = self._makeOne()
        plugin.help_status()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("status <name>" in out)

    def test_status_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        plugin.ctl.options._server.supervisor.getAllProcessInfo = f
        plugin.do_status('')
        self.assertEqual(called, [])

    def test_status_table_process_column_min_width(self):
        plugin = self._makeOne()
        result = plugin.do_status('')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split("\n")
        self.assertEqual(lines[0].index("RUNNING"), 33)

    def test_status_table_process_column_expands(self):
        plugin = self._makeOne()
        options = plugin.ctl.options
        def f(*arg, **kw):
            from supervisor.states import ProcessStates
            return [{'name': 'foo'*50, # long name
                     'group':'foo',
                     'pid': 11,
                     'state': ProcessStates.RUNNING,
                     'statename': 'RUNNING',
                     'start': 0,
                     'stop': 0,
                     'spawnerr': '',
                     'now': 0,
                     'description':'foo description'},
                    {
                    'name': 'bar', # short name
                    'group': 'bar',
                    'pid': 12,
                    'state': ProcessStates.FATAL,
                    'statename': 'RUNNING',
                    'start': 0,
                    'stop': 0,
                    'spawnerr': '',
                    'now': 0,
                    'description': 'bar description',
                    }]
        options._server.supervisor.getAllProcessInfo = f
        self.assertEqual(plugin.do_status(''), None)
        lines = plugin.ctl.stdout.getvalue().split("\n")
        self.assertEqual(lines[0].index("RUNNING"), 157)
        self.assertEqual(lines[1].index("RUNNING"), 157)

    def test_status_all_processes_no_arg(self):
        plugin = self._makeOne()
        result = plugin.do_status('')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
        self.assertEqual(value[1].split(None, 2),
                         ['bar', 'FATAL', 'bar description'])
        self.assertEqual(value[2].split(None, 2),
                         ['baz:baz_01', 'STOPPED', 'baz description'])
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.NOT_RUNNING)


    def test_status_success(self):
        plugin = self._makeOne()
        result = plugin.do_status('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])

    def test_status_unknown_process(self):
        plugin = self._makeOne()
        result = plugin.do_status('unknownprogram')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue()
        self.assertEqual("unknownprogram: ERROR (no such process)\n", value)
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.UNKNOWN)

    def test_status_all_processes_all_arg(self):
        plugin = self._makeOne()
        result = plugin.do_status('all')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
        self.assertEqual(value[1].split(None, 2),
                         ['bar', 'FATAL', 'bar description'])
        self.assertEqual(value[2].split(None, 2),
                         ['baz:baz_01', 'STOPPED', 'baz description'])
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.NOT_RUNNING)

    def test_status_process_name(self):
        plugin = self._makeOne()
        result = plugin.do_status('foo')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().strip()
        self.assertEqual(value.split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_status_group_name(self):
        plugin = self._makeOne()
        result = plugin.do_status('baz:*')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['baz:baz_01', 'STOPPED', 'baz description'])
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.NOT_RUNNING)

    def test_status_mixed_names(self):
        plugin = self._makeOne()
        result = plugin.do_status('foo baz:*')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
        self.assertEqual(value[1].split(None, 2),
                         ['baz:baz_01', 'STOPPED', 'baz description'])
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.NOT_RUNNING)

    def test_status_bad_group_name(self):
        plugin = self._makeOne()
        result = plugin.do_status('badgroup:*')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0], "badgroup: ERROR (no such group)")
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.UNKNOWN)

    def test_status_bad_process_name(self):
        plugin = self._makeOne()
        result = plugin.do_status('badprocess')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0], "badprocess: ERROR (no such process)")
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.UNKNOWN)

    def test_status_bad_process_name_with_group(self):
        plugin = self._makeOne()
        result = plugin.do_status('badgroup:badprocess')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0], "badgroup:badprocess: "
                                   "ERROR (no such process)")
        self.assertEqual(plugin.ctl.exitstatus, LSBStatusExitStatuses.UNKNOWN)

    def test_start_help(self):
        plugin = self._makeOne()
        plugin.help_start()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("start <name>" in out)

    def test_start_fail(self):
        plugin = self._makeOne()
        result = plugin.do_start('')
        self.assertEqual(result, None)
        expected = "Error: start requires a process name"
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0], expected)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.INVALID_ARGS)

    def test_start_badname(self):
        plugin = self._makeOne()
        result = plugin.do_start('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_start_no_file(self):
        plugin = self._makeOne()
        result = plugin.do_start('NO_FILE')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'NO_FILE: ERROR (no such file)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_start_not_executable(self):
        plugin = self._makeOne()
        result = plugin.do_start('NOT_EXECUTABLE')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'NOT_EXECUTABLE: ERROR (file is not executable)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_start_alreadystarted(self):
        plugin = self._makeOne()
        result = plugin.do_start('ALREADY_STARTED')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ALREADY_STARTED: ERROR (already started)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_start_spawnerror(self):
        plugin = self._makeOne()
        result = plugin.do_start('SPAWN_ERROR')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'SPAWN_ERROR: ERROR (spawn error)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.NOT_RUNNING)

    def test_start_abnormaltermination(self):
        plugin = self._makeOne()
        result = plugin.do_start('ABNORMAL_TERMINATION')
        self.assertEqual(result, None)
        expected = 'ABNORMAL_TERMINATION: ERROR (abnormal termination)\n'
        self.assertEqual(plugin.ctl.stdout.getvalue(), expected)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.NOT_RUNNING)

    def test_start_one_success(self):
        plugin = self._makeOne()
        result = plugin.do_start('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: started\n')

    def test_start_one_with_group_name_success(self):
        plugin = self._makeOne()
        result = plugin.do_start('foo:foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: started\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_start_many(self):
        plugin = self._makeOne()
        result = plugin.do_start('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: started\nbar: started\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_start_group(self):
        plugin = self._makeOne()
        result = plugin.do_start('foo:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo:foo_00: started\n'
                         'foo:foo_01: started\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)


    def test_start_group_bad_name(self):
        plugin = self._makeOne()
        result = plugin.do_start('BAD_NAME:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such group)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.INVALID_ARGS)

    def test_start_all(self):
        plugin = self._makeOne()
        result = plugin.do_start('all')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: started\n'
                         'foo2: started\n'
                         'failed_group:failed: ERROR (spawn error)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.NOT_RUNNING)

    def test_start_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.startAllProcesses = f
        supervisor.startProcessGroup = f
        plugin.do_start('foo')
        self.assertEqual(called, [])

    def test_stop_help(self):
        plugin = self._makeOne()
        plugin.help_stop()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("stop <name>" in out)

    def test_stop_fail(self):
        plugin = self._makeOne()
        result = plugin.do_stop('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0],
                         "Error: stop requires a process name")
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_stop_badname(self):
        plugin = self._makeOne()
        result = plugin.do_stop('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_stop_notrunning(self):
        plugin = self._makeOne()
        result = plugin.do_stop('NOT_RUNNING')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'NOT_RUNNING: ERROR (not running)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_stop_failed(self):
        plugin = self._makeOne()
        result = plugin.do_stop('FAILED')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'FAILED\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_stop_one_success(self):
        plugin = self._makeOne()
        result = plugin.do_stop('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_stop_one_with_group_name_success(self):
        plugin = self._makeOne()
        result = plugin.do_stop('foo:foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_stop_many(self):
        plugin = self._makeOne()
        result = plugin.do_stop('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\n'
                         'bar: stopped\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_stop_group(self):
        plugin = self._makeOne()
        result = plugin.do_stop('foo:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo:foo_00: stopped\n'
                         'foo:foo_01: stopped\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_stop_group_bad_name(self):
        plugin = self._makeOne()
        result = plugin.do_stop('BAD_NAME:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such group)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_stop_all(self):
        plugin = self._makeOne()
        result = plugin.do_stop('all')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\n'
                         'foo2: stopped\n'
                         'failed_group:failed: ERROR (no such process)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_stop_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.stopAllProcesses = f
        supervisor.stopProcessGroup = f
        plugin.do_stop('foo')
        self.assertEqual(called, [])

    def test_signal_help(self):
        plugin = self._makeOne()
        plugin.help_signal()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("signal <signal name> <name>" in out)

    def test_signal_fail_no_arg(self):
        plugin = self._makeOne()
        result = plugin.do_signal('')
        self.assertEqual(result, None)
        msg = 'Error: signal requires a signal name and a process name'
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0], msg)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_signal_fail_one_arg(self):
        plugin = self._makeOne()
        result = plugin.do_signal('hup')
        self.assertEqual(result, None)
        msg = 'Error: signal requires a signal name and a process name'
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0], msg)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_signal_bad_signal(self):
        plugin = self._makeOne()
        result = plugin.do_signal('BAD_SIGNAL foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: ERROR (bad signal name)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_signal_bad_name(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_signal_bad_group(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP BAD_NAME:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such group)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_signal_not_running(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP NOT_RUNNING')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'NOT_RUNNING: ERROR (not running)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.NOT_RUNNING)

    def test_signal_failed(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP FAILED')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'FAILED\n')
        self.assertEqual(plugin.ctl.exitstatus, 1)

    def test_signal_one_success(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'foo: signalled\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_signal_many(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP foo bar')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: signalled\n'
                         'bar: signalled\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_signal_group(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP foo:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo:foo_00: signalled\n'
                         'foo:foo_01: signalled\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_signal_all(self):
        plugin = self._makeOne()
        result = plugin.do_signal('HUP all')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: signalled\n'
                         'foo2: signalled\n'
                         'failed_group:failed: ERROR (no such process)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_signal_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.signalAllProcesses = f
        supervisor.signalProcessGroup = f
        plugin.do_signal('term foo')
        self.assertEqual(called, [])

    def test_restart_help(self):
        plugin = self._makeOne()
        plugin.help_restart()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("restart <name>" in out)

    def test_restart_fail(self):
        plugin = self._makeOne()
        result = plugin.do_restart('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0],
                         'Error: restart requires a process name')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_restart_one(self):
        plugin = self._makeOne()
        result = plugin.do_restart('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\nfoo: started\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_restart_all(self):
        plugin = self._makeOne()
        result = plugin.do_restart('all')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\nfoo2: stopped\n'
                         'failed_group:failed: ERROR (no such process)\n'
                         'foo: started\nfoo2: started\n'
                         'failed_group:failed: ERROR (spawn error)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.NOT_RUNNING)

    def test_restart_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.stopAllProcesses = f
        supervisor.stopProcessGroup = f
        plugin.do_restart('foo')
        self.assertEqual(called, [])

    def test_clear_help(self):
        plugin = self._makeOne()
        plugin.help_clear()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("clear <name>" in out)

    def test_clear_fail(self):
        plugin = self._makeOne()
        result = plugin.do_clear('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0],
                         "Error: clear requires a process name")
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_clear_badname(self):
        plugin = self._makeOne()
        result = plugin.do_clear('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_clear_one_success(self):
        plugin = self._makeOne()
        result = plugin.do_clear('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: cleared\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_clear_one_with_group_success(self):
        plugin = self._makeOne()
        result = plugin.do_clear('foo:foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: cleared\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_clear_many(self):
        plugin = self._makeOne()
        result = plugin.do_clear('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: cleared\nbar: cleared\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_clear_all(self):
        plugin = self._makeOne()
        result = plugin.do_clear('all')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: cleared\n'
                         'foo2: cleared\n'
                         'failed_group:failed: ERROR (failed)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_clear_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.clearAllProcessLogs = f
        supervisor.clearProcessLogs = f
        plugin.do_clear('foo')
        self.assertEqual(called, [])

    def test_open_help(self):
        plugin = self._makeOne()
        plugin.help_open()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("open <url>" in out)

    def test_open_fail(self):
        plugin = self._makeOne()
        result = plugin.do_open('badname')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: url must be http:// or unix://\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_open_succeed(self):
        plugin = self._makeOne()
        result = plugin.do_open('http://localhost:9002')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
        self.assertEqual(value[1].split(None, 2),
                         ['bar', 'FATAL', 'bar description'])
        self.assertEqual(value[2].split(None, 2),
                         ['baz:baz_01', 'STOPPED', 'baz description'])
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_version_help(self):
        plugin = self._makeOne()
        plugin.help_version()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Show the version of the remote supervisord" in out)

    def test_version(self):
        plugin = self._makeOne()
        plugin.do_version(None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), '3000\n')

    def test_version_arg(self):
        plugin = self._makeOne()
        result = plugin.do_version('bad')
        self.assertEqual(result, None)
        val = plugin.ctl.stdout.getvalue()
        self.assertTrue(val.startswith('Error: version accepts no arguments'), val)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_version_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        plugin.ctl.options._server.supervisor.getSupervisorVersion = f
        plugin.do_version('')
        self.assertEqual(called, [])

    def test_reload_help(self):
        plugin = self._makeOne()
        plugin.help_reload()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Restart the remote supervisord" in out)

    def test_reload_fail(self):
        plugin = self._makeOne()
        options = plugin.ctl.options
        options._server.supervisor._restartable = False
        result = plugin.do_reload('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._restarted, False)

    def test_reload(self):
        plugin = self._makeOne()
        options = plugin.ctl.options
        result = plugin.do_reload('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._restarted, True)

    def test_reload_arg(self):
        plugin = self._makeOne()
        result = plugin.do_reload('bad')
        self.assertEqual(result, None)
        val = plugin.ctl.stdout.getvalue()
        self.assertTrue(val.startswith('Error: reload accepts no arguments'), val)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_shutdown_help(self):
        plugin = self._makeOne()
        plugin.help_shutdown()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Shut the remote supervisord down" in out)

    def test_shutdown(self):
        plugin = self._makeOne()
        options = plugin.ctl.options
        result = plugin.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._shutdown, True)

    def test_shutdown_catches_xmlrpc_fault_shutdown_state(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc

        def raise_fault(*arg, **kw):
            raise xmlrpclib.Fault(xmlrpc.Faults.SHUTDOWN_STATE, 'bye')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        result = plugin.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: already shutting down\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_shutdown_reraises_other_xmlrpc_faults(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc

        def raise_fault(*arg, **kw):
            raise xmlrpclib.Fault(xmlrpc.Faults.CANT_REREAD, 'ouch')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        self.assertRaises(xmlrpclib.Fault,
                          plugin.do_shutdown, '')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_shutdown_catches_socket_error_ECONNREFUSED(self):
        plugin = self._makeOne()
        import socket
        import errno

        def raise_fault(*arg, **kw):
            raise socket.error(errno.ECONNREFUSED, 'nobody home')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        result = plugin.do_shutdown('')
        self.assertEqual(result, None)

        output = plugin.ctl.stdout.getvalue()
        self.assertTrue('refused connection (already shut down?)' in output)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_shutdown_catches_socket_error_ENOENT(self):
        plugin = self._makeOne()
        import socket
        import errno

        def raise_fault(*arg, **kw):
            raise socket.error(errno.ENOENT, 'no file')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        result = plugin.do_shutdown('')
        self.assertEqual(result, None)

        output = plugin.ctl.stdout.getvalue()
        self.assertTrue('no such file (already shut down?)' in output)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_shutdown_reraises_other_socket_errors(self):
        plugin = self._makeOne()
        import socket
        import errno

        def raise_fault(*arg, **kw):
            raise socket.error(errno.EPERM, 'denied')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        self.assertRaises(socket.error,
                          plugin.do_shutdown, '')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test__formatChanges(self):
        plugin = self._makeOne()
        # Don't explode, plz
        plugin._formatChanges([['added'], ['changed'], ['removed']])
        plugin._formatChanges([[], [], []])

    def test_reread_help(self):
        plugin = self._makeOne()
        plugin.help_reread()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Reload the daemon's configuration files" in out)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_reread(self):
        plugin = self._makeOne()
        calls = []
        plugin._formatChanges = lambda x: calls.append(x)
        result = plugin.do_reread(None)
        self.assertEqual(result, None)
        self.assertEqual(calls[0], [['added'], ['changed'], ['removed']])
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_reread_arg(self):
        plugin = self._makeOne()
        result = plugin.do_reread('bad')
        self.assertEqual(result, None)
        val = plugin.ctl.stdout.getvalue()
        self.assertTrue(val.startswith('Error: reread accepts no arguments'), val)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_reread_cant_reread(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc
        def reloadConfig(*arg, **kw):
            raise xmlrpclib.Fault(xmlrpc.Faults.CANT_REREAD, 'cant')
        plugin.ctl.options._server.supervisor.reloadConfig = reloadConfig
        plugin.do_reread(None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: cant\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_reread_shutdown_state(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc
        def reloadConfig(*arg, **kw):
            raise xmlrpclib.Fault(xmlrpc.Faults.SHUTDOWN_STATE, '')
        plugin.ctl.options._server.supervisor.reloadConfig = reloadConfig
        plugin.do_reread(None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: supervisor shutting down\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_reread_reraises_other_faults(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc
        def reloadConfig(*arg, **kw):
            raise xmlrpclib.Fault(xmlrpc.Faults.FAILED, '')
        plugin.ctl.options._server.supervisor.reloadConfig = reloadConfig
        self.assertRaises(xmlrpclib.Fault, plugin.do_reread, '')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test__formatConfigInfo(self):
        info = { 'group': 'group1',
                 'name': 'process1',
                 'inuse': True,
                 'autostart': True,
                 'process_prio': 999,
                 'group_prio': 999 }
        plugin = self._makeOne()
        result = plugin._formatConfigInfo(info)
        self.assertTrue('in use' in result)
        info = { 'group': 'group1',
                 'name': 'process1',
                 'inuse': False,
                 'autostart': False,
                 'process_prio': 999,
                 'group_prio': 999 }
        result = plugin._formatConfigInfo(info)
        self.assertTrue('avail' in result)

    def test_avail_help(self):
        plugin = self._makeOne()
        plugin.help_avail()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Display all configured" in out)

    def test_avail(self):
        calls = []
        plugin = self._makeOne()

        class FakeSupervisor(object):
            def getAllConfigInfo(self):
                return [{ 'group': 'group1', 'name': 'process1',
                          'inuse': False, 'autostart': False,
                          'process_prio': 999, 'group_prio': 999 }]

        plugin.ctl.get_supervisor = lambda : FakeSupervisor()
        plugin.ctl.output = calls.append
        result = plugin.do_avail('')
        self.assertEqual(result, None)

    def test_avail_arg(self):
        plugin = self._makeOne()
        result = plugin.do_avail('bad')
        self.assertEqual(result, None)
        val = plugin.ctl.stdout.getvalue()
        self.assertTrue(val.startswith('Error: avail accepts no arguments'), val)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_avail_shutdown_state(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        def getAllConfigInfo():
            from supervisor import xmlrpc
            raise xmlrpclib.Fault(xmlrpc.Faults.SHUTDOWN_STATE, '')
        supervisor.getAllConfigInfo = getAllConfigInfo

        result = plugin.do_avail('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: supervisor shutting down\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_avail_reraises_other_faults(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        def getAllConfigInfo():
            from supervisor import xmlrpc
            raise xmlrpclib.Fault(xmlrpc.Faults.FAILED, '')
        supervisor.getAllConfigInfo = getAllConfigInfo

        self.assertRaises(xmlrpclib.Fault, plugin.do_avail, '')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_add_help(self):
        plugin = self._makeOne()
        plugin.help_add()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("add <name>" in out)

    def test_add(self):
        plugin = self._makeOne()
        result = plugin.do_add('foo')
        self.assertEqual(result, None)
        supervisor = plugin.ctl.options._server.supervisor
        self.assertEqual(supervisor.processes, ['foo'])
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_add_already_added(self):
        plugin = self._makeOne()
        result = plugin.do_add('ALREADY_ADDED')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: process group already active\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_add_bad_name(self):
        plugin = self._makeOne()
        result = plugin.do_add('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: no such process/group: BAD_NAME\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_add_shutdown_state(self):
        plugin = self._makeOne()
        result = plugin.do_add('SHUTDOWN_STATE')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: shutting down\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_add_reraises_other_faults(self):
        plugin = self._makeOne()
        self.assertRaises(xmlrpclib.Fault, plugin.do_add, 'FAILED')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_remove_help(self):
        plugin = self._makeOne()
        plugin.help_remove()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("remove <name>" in out)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_remove(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.processes = ['foo']
        result = plugin.do_remove('foo')
        self.assertEqual(result, None)
        self.assertEqual(supervisor.processes, [])

    def test_remove_bad_name(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.processes = ['foo']
        result = plugin.do_remove('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: no such process/group: BAD_NAME\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_remove_still_running(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.processes = ['foo']
        result = plugin.do_remove('STILL_RUNNING')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: process/group still running: STILL_RUNNING\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_remove_reraises_other_faults(self):
        plugin = self._makeOne()
        self.assertRaises(xmlrpclib.Fault, plugin.do_remove, 'FAILED')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_update_help(self):
        plugin = self._makeOne()
        plugin.help_update()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Reload config and add/remove" in out)

    def test_update_not_on_shutdown(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor
        def reloadConfig():
            from supervisor import xmlrpc
            raise xmlrpclib.Fault(xmlrpc.Faults.SHUTDOWN_STATE, 'blah')
        supervisor.reloadConfig = reloadConfig
        supervisor.processes = ['removed']
        plugin.do_update('')
        self.assertEqual(supervisor.processes, ['removed'])

    def test_update_added_procs(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        def reloadConfig():
            return [[['new_proc'], [], []]]
        supervisor.reloadConfig = reloadConfig

        result = plugin.do_update('')
        self.assertEqual(result, None)
        self.assertEqual(supervisor.processes, ['new_proc'])

    def test_update_with_gname(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        def reloadConfig():
            return [[['added1', 'added2'], ['changed'], ['removed']]]
        supervisor.reloadConfig = reloadConfig
        supervisor.processes = ['changed', 'removed']

        plugin.do_update('changed')
        self.assertEqual(sorted(supervisor.processes),
                         sorted(['changed', 'removed']))

        plugin.do_update('added1 added2')
        self.assertEqual(sorted(supervisor.processes),
                         sorted(['changed', 'removed', 'added1', 'added2']))

        plugin.do_update('removed')
        self.assertEqual(sorted(supervisor.processes),
                         sorted(['changed', 'added1', 'added2']))

        supervisor.processes = ['changed', 'removed']
        plugin.do_update('removed added1')
        self.assertEqual(sorted(supervisor.processes),
                         sorted(['changed', 'added1']))

        supervisor.processes = ['changed', 'removed']
        plugin.do_update('all')
        self.assertEqual(sorted(supervisor.processes),
                         sorted(['changed', 'added1', 'added2']))


    def test_update_changed_procs(self):
        from supervisor import xmlrpc

        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        calls = []
        def reloadConfig():
            return [[[], ['changed_group'], []]]
        supervisor.reloadConfig = reloadConfig
        supervisor.startProcess = lambda x: calls.append(('start', x))

        supervisor.addProcessGroup('changed_group') # fake existence
        results = [{'name':        'changed_process',
                    'group':       'changed_group',
                    'status':      xmlrpc.Faults.SUCCESS,
                    'description': 'blah'}]
        def stopProcessGroup(name):
            calls.append(('stop', name))
            return results
        supervisor.stopProcessGroup = stopProcessGroup

        plugin.do_update('')
        self.assertEqual(calls, [('stop', 'changed_group')])

        supervisor.addProcessGroup('changed_group') # fake existence
        calls[:] = []
        results[:] = [{'name':        'changed_process1',
                       'group':       'changed_group',
                       'status':      xmlrpc.Faults.NOT_RUNNING,
                       'description': 'blah'},
                      {'name':        'changed_process2',
                       'group':       'changed_group',
                       'status':      xmlrpc.Faults.FAILED,
                       'description': 'blah'}]

        plugin.do_update('')
        self.assertEqual(calls, [('stop', 'changed_group')])

        supervisor.addProcessGroup('changed_group') # fake existence
        calls[:] = []
        results[:] = [{'name':        'changed_process1',
                       'group':       'changed_group',
                       'status':      xmlrpc.Faults.FAILED,
                       'description': 'blah'},
                      {'name':        'changed_process2',
                       'group':       'changed_group',
                       'status':      xmlrpc.Faults.SUCCESS,
                       'description': 'blah'}]

        plugin.do_update('')
        self.assertEqual(calls, [('stop', 'changed_group')])

    def test_update_removed_procs(self):
        from supervisor import xmlrpc

        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        def reloadConfig():
            return [[[], [], ['removed_group']]]
        supervisor.reloadConfig = reloadConfig

        results = [{'name':        'removed_process',
                    'group':       'removed_group',
                    'status':      xmlrpc.Faults.SUCCESS,
                    'description': 'blah'}]
        supervisor.processes = ['removed_group']

        def stopProcessGroup(name):
            return results
        supervisor.stopProcessGroup = stopProcessGroup

        plugin.do_update('')
        self.assertEqual(supervisor.processes, [])

        results[:] = [{'name':        'removed_process',
                       'group':       'removed_group',
                       'status':      xmlrpc.Faults.NOT_RUNNING,
                       'description': 'blah'}]
        supervisor.processes = ['removed_group']

        plugin.do_update('')
        self.assertEqual(supervisor.processes, [])

        results[:] = [{'name':        'removed_process',
                       'group':       'removed_group',
                       'status':      xmlrpc.Faults.FAILED,
                       'description': 'blah'}]
        supervisor.processes = ['removed_group']

        plugin.do_update('')
        self.assertEqual(supervisor.processes, ['removed_group'])

    def test_update_reraises_other_faults(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        def reloadConfig():
            from supervisor import xmlrpc
            raise xmlrpclib.Fault(xmlrpc.Faults.FAILED, 'FAILED')
        supervisor.reloadConfig = reloadConfig

        self.assertRaises(xmlrpclib.Fault, plugin.do_update, '')
        self.assertEqual(plugin.ctl.exitstatus, 1)

    def test_pid_help(self):
        plugin = self._makeOne()
        plugin.help_pid()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("pid <name>" in out)

    def test_pid_supervisord(self):
        plugin = self._makeOne()
        result = plugin.do_pid('')
        self.assertEqual(result, None)
        options = plugin.ctl.options
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], str(options._server.supervisor.getPID()))

    def test_pid_allprocesses(self):
        plugin = self._makeOne()
        result = plugin.do_pid('all')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().strip()
        self.assertEqual(value.split(), ['11', '12', '13'])
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_pid_badname(self):
        plugin = self._makeOne()
        result = plugin.do_pid('BAD_NAME')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().strip()
        self.assertEqual(value, 'No such process BAD_NAME')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_pid_oneprocess(self):
        plugin = self._makeOne()
        result = plugin.do_pid('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue().strip(), '11')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.SUCCESS)

    def test_pid_oneprocess_not_running(self):
        plugin = self._makeOne()
        options = plugin.ctl.options
        def f(*arg, **kw):
            from supervisor.states import ProcessStates
            return {'name': 'foo',
                     'group':'foo',
                     'pid': 0,
                     'state': ProcessStates.STOPPED,
                     'statename': 'STOPPED',
                     'start': 0,
                     'stop': 0,
                     'spawnerr': '',
                     'now': 0,
                     'description':'foo description'
                    }
        options._server.supervisor.getProcessInfo = f
        result = plugin.do_pid('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue().strip(), '0')
        self.assertEqual(plugin.ctl.exitstatus,
                         LSBInitExitStatuses.NOT_RUNNING)

    def test_pid_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        plugin.ctl.options._server.supervisor.getPID = f
        plugin.do_pid('')
        self.assertEqual(called, [])

    def test_maintail_help(self):
        plugin = self._makeOne()
        plugin.help_maintail()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("tail of supervisor main log file" in out)

    def test_maintail_toomanyargs(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('foo bar')
        self.assertEqual(result, None)
        val = plugin.ctl.stdout.getvalue()
        self.assertTrue(val.startswith('Error: too many'), val)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_maintail_minus_string_fails(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('-wrong')
        self.assertEqual(result, None)
        val = plugin.ctl.stdout.getvalue()
        self.assertTrue(val.startswith('Error: bad argument -wrong'), val)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_maintail_wrong(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('wrong')
        self.assertEqual(result, None)
        val = plugin.ctl.stdout.getvalue()
        self.assertTrue(val.startswith('Error: bad argument wrong'), val)
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def _dont_test_maintail_dashf(self):
        # https://github.com/Supervisor/supervisor/issues/285
        # TODO: Refactor so we can test more of maintail -f than just a
        # connect error, and fix this test so it passes on FreeBSD.
        plugin = self._makeOne()
        plugin.listener = DummyListener()
        result = plugin.do_maintail('-f')
        self.assertEqual(result, None)
        errors = plugin.listener.errors
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(plugin.listener.closed,
                         'http://localhost:65532/mainlogtail')
        self.assertEqual(error[0],
                         'http://localhost:65532/mainlogtail')
        self.assertTrue('Cannot connect' in error[1])

    def test_maintail_bad_modifier(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('-z')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: bad argument -z')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_maintail_nobytes(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'mainlogdata\n')

    def test_maintail_dashbytes(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('-100')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'mainlogdata\n')

    def test_maintail_readlog_error_nofile(self):
        plugin = self._makeOne()
        supervisor_rpc = plugin.ctl.get_supervisor()
        from supervisor import xmlrpc
        supervisor_rpc._readlog_error = xmlrpc.Faults.NO_FILE
        result = plugin.do_maintail('-100')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'supervisord: ERROR (no log file)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_maintail_readlog_error_failed(self):
        plugin = self._makeOne()
        supervisor_rpc = plugin.ctl.get_supervisor()
        from supervisor import xmlrpc
        supervisor_rpc._readlog_error = xmlrpc.Faults.FAILED
        result = plugin.do_maintail('-100')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'supervisord: ERROR (unknown error reading log)\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_maintail_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        plugin.ctl.options._server.supervisor.readLog = f
        plugin.do_maintail('')
        self.assertEqual(called, [])

    def test_fg_help(self):
        plugin = self._makeOne()
        plugin.help_fg()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("fg <process>" in out)

    def test_fg_too_few_args(self):
        plugin = self._makeOne()
        result = plugin.do_fg('')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'ERROR: no process name supplied')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_fg_too_many_args(self):
        plugin = self._makeOne()
        result = plugin.do_fg('foo bar')
        self.assertEqual(result, None)
        line = plugin.ctl.stdout.getvalue()
        self.assertEqual(line, 'ERROR: too many process names supplied\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_fg_badprocname(self):
        plugin = self._makeOne()
        result = plugin.do_fg('BAD_NAME')
        self.assertEqual(result, None)
        line = plugin.ctl.stdout.getvalue()
        self.assertEqual(line, 'ERROR: bad process name supplied\n')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_fg_procnotrunning(self):
        plugin = self._makeOne()
        result = plugin.do_fg('bar')
        self.assertEqual(result, None)
        line = plugin.ctl.stdout.getvalue()
        self.assertEqual(line, 'ERROR: process not running\n')
        result = plugin.do_fg('baz_01')
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(result, None)
        self.assertEqual(lines[-2], 'ERROR: process not running')
        self.assertEqual(plugin.ctl.exitstatus, LSBInitExitStatuses.GENERIC)

    def test_fg_upcheck_failed(self):
        plugin = self._makeOne()
        plugin.ctl.upcheck = lambda: False
        called = []
        def f(*arg, **kw):
            called.append(True)
        plugin.ctl.options._server.supervisor.getProcessInfo = f
        plugin.do_fg('foo')
        self.assertEqual(called, [])

    def test_exit_help(self):
        plugin = self._makeOne()
        plugin.help_exit()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Exit the supervisor shell" in out)

    def test_quit_help(self):
        plugin = self._makeOne()
        plugin.help_quit()
        out = plugin.ctl.stdout.getvalue()
        self.assertTrue("Exit the supervisor shell" in out)

class DummyListener:
    def __init__(self):
        self.errors = []
    def error(self, url, msg):
        self.errors.append((url, msg))
    def close(self, url):
        self.closed = url

class DummyPluginFactory:
    def __init__(self, ctl, **kw):
        self.ctl = ctl

    def do_help(self, arg):
        self.ctl.stdout.write('foo helped')

class DummyClientOptions:
    def __init__(self):
        self.prompt = 'supervisor'
        self.serverurl = 'http://localhost:65532'
        self.username = 'chrism'
        self.password = '123'
        self.history_file = None
        self.plugins = ()
        self._server = DummyRPCServer()
        self.interactive = False
        self.plugin_factories = [('dummy', DummyPluginFactory, {})]

    def getServerProxy(self):
        return self._server

class DummyController:
    nohelp = 'no help on %s'
    def __init__(self, options):
        self.options = options
        self.topics_printed = []
        self.stdout = StringIO()
        self.exitstatus = LSBInitExitStatuses.SUCCESS

    def upcheck(self):
        return True

    def get_supervisor(self):
        return self.get_server_proxy('supervisor')

    def get_server_proxy(self, namespace=None):
        proxy = self.options.getServerProxy()
        if namespace is None:
            return proxy
        else:
            return getattr(proxy, namespace)

    def output(self, data):
        self.stdout.write(data + '\n')

    def print_topics(self, doc_headers, cmds_doc, rows, cols):
        self.topics_printed.append((doc_headers, cmds_doc, rows, cols))

    def set_exitstatus_from_xmlrpc_fault(self, faultcode, ignored_faultcode=None):
        from supervisor.supervisorctl import DEAD_PROGRAM_FAULTS
        if faultcode in (ignored_faultcode, xmlrpc.Faults.SUCCESS):
            pass
        elif faultcode in DEAD_PROGRAM_FAULTS:
            self.exitstatus = LSBInitExitStatuses.NOT_RUNNING
        else:
            self.exitstatus = LSBInitExitStatuses.GENERIC

class DummyPlugin:
    def __init__(self, controller=None):
        self.ctl = controller

    def do_help(self, arg):
        self.helped = True

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

