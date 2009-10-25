import sys
import unittest
from StringIO import StringIO

from supervisor.tests.base import DummyRPCServer

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
        value = controller.stdout.getvalue()
        self.assertEqual(value, 'Sorry, this version of supervisorctl expects '
        'to talk to a server with API version 3.0, but the remote version is '
        '1.0.\n')

    def test__upcheck_unknown_method(self):
        options = DummyClientOptions()
        from xmlrpclib import Fault
        from supervisor.xmlrpc import Faults
        def getVersion():
            raise Fault(Faults.UNKNOWN_METHOD, 'duh')
        options._server.supervisor.getVersion = getVersion
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.upcheck()
        self.assertEqual(result, False)
        value = controller.stdout.getvalue()
        self.assertEqual(value, 'Sorry, supervisord responded but did not '
        'recognize the supervisor namespace commands that supervisorctl '
        'uses to control it.  Please check that the '
        '[rpcinterface:supervisor] section is enabled in the '
        'configuration file (see sample.conf).\n')

    def test_onecmd(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        plugin = DummyPlugin()
        controller.options.plugins = (plugin,)
        result = controller.onecmd('help')
        self.assertEqual(result, None)
        self.assertEqual(plugin.helped, True)

    def test_onecmd_multi_colonseparated(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        plugin = DummyPlugin()
        controller.options.plugins = (plugin,)
        result = controller.onecmd('help; help')
        self.assertEqual(result, None)
        self.assertEqual(controller.cmdqueue, [' help'])
        self.assertEqual(plugin.helped, True)

    def test_completionmatches(self):
        options=DummyClientOptions()
        controller=self._makeOne(options)
        controller.stdout=StringIO()
        plugin=DummyPlugin()
        controller.options.plugin=(plugin,)
        for i in ['add','remove']:
            result=controller.completionmatches('',i+' ',1)
            self.assertEqual(result,['foo ','bar ','baz '])
        result=controller.completionmatches('','fg baz:')
        self.assertEqual(result,['baz_01 '])

    def test_nohelp(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        self.assertEqual(controller.nohelp, '*** No help on %s')
        
    def test_do_help(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        results = controller.do_help(None)
        helpval = controller.stdout.getvalue()
        self.assertEqual(results, None)
        self.assertEqual(helpval, 'foo helped')

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
        results = plugin.do_help(None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), '\n')
        self.assertEqual(len(plugin.ctl.topics_printed), 1)
        topics = plugin.ctl.topics_printed[0]
        self.assertEqual(topics[0], 'unnamed commands (type help <topic>):')
        self.assertEqual(topics[1], [])
        self.assertEqual(topics[2], 15) 
        self.assertEqual(topics[3], 80)
        self.assertEqual(results, None)

    def test_do_help_witharg(self):
        plugin = self._makeOne()
        results = plugin.do_help('foo')
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

    def test_tail_toomanyargs(self):
        plugin = self._makeOne()
        result = plugin.do_tail('one two three four')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: too many arguments')

    def test_tail_f_noprocname(self):
        plugin = self._makeOne()
        result = plugin.do_tail('-f')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: tail requires process name')

    def test_tail_defaults(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'output line')

    def test_tail_no_file(self):
        plugin = self._makeOne()
        result = plugin.do_tail('NO_FILE')
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'NO_FILE: ERROR (no log file)')

    def test_tail_failed(self):
        plugin = self._makeOne()
        result = plugin.do_tail('FAILED')
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'FAILED: ERROR (unknown error reading log)')

    def test_tail_bad_name(self):
        plugin = self._makeOne()
        result = plugin.do_tail('BAD_NAME')
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'BAD_NAME: ERROR (no such process name)')

    def test_tail_bytesmodifier(self):
        plugin = self._makeOne()
        result = plugin.do_tail('-10 foo')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], 'tput line')

    def test_tail_explicit_channel_stdout_nomodifier(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo stdout')
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'output line')

    def test_tail_explicit_channel_stderr_nomodifier(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo stderr')
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'output line')

    def test_tail_explicit_channel_unrecognized(self):
        plugin = self._makeOne()
        result = plugin.do_tail('foo fudge')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().strip()
        self.assertEqual(value, "Error: bad channel 'fudge'")

    def test_status_oneprocess(self):
        plugin = self._makeOne()
        result = plugin.do_status('foo')
        self.assertEqual(result, None)
        value = plugin.ctl.stdout.getvalue().strip()
        self.assertEqual(value.split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
                         

    def test_status_allprocesses(self):
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

    def test_start_fail(self):
        plugin = self._makeOne()
        result = plugin.do_start('')
        self.assertEqual(result, None)
        expected = "Error: start requires a process name"
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0], expected)

    def test_start_badname(self):
        plugin = self._makeOne()
        result = plugin.do_start('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_start_no_file(self):
        plugin = self._makeOne()
        result = plugin.do_start('NO_FILE')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'NO_FILE: ERROR (no such file)\n')

    def test_start_not_executable(self):
        plugin = self._makeOne()
        result = plugin.do_start('NOT_EXECUTABLE')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'NOT_EXECUTABLE: ERROR (file is not executable)\n')

    def test_start_alreadystarted(self):
        plugin = self._makeOne()
        result = plugin.do_start('ALREADY_STARTED')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ALREADY_STARTED: ERROR (already started)\n')

    def test_start_spawnerror(self):
        plugin = self._makeOne()
        result = plugin.do_start('SPAWN_ERROR')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'SPAWN_ERROR: ERROR (spawn error)\n')

    def test_start_one_success(self):
        plugin = self._makeOne()
        result = plugin.do_start('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'foo: started\n')

    def test_start_many(self):
        plugin = self._makeOne()
        result = plugin.do_start('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: started\nbar: started\n')

    def test_start_group(self):
        plugin = self._makeOne()
        result = plugin.do_start('foo:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo_00: started\nfoo_01: started\n')

    def test_start_all(self):
        plugin = self._makeOne()
        result = plugin.do_start('all')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue(),
                'foo: started\nfoo2: started\nfailed: ERROR (spawn error)\n')


    def test_stop_fail(self):
        plugin = self._makeOne()
        result = plugin.do_stop('')
        self.assertEqual(result, None)
        expected = "Error: stop requires a process name"
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0], expected)

    def test_stop_badname(self):
        plugin = self._makeOne()
        result = plugin.do_stop('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_stop_notrunning(self):
        plugin = self._makeOne()
        result = plugin.do_stop('NOT_RUNNING')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'NOT_RUNNING: ERROR (not running)\n')

    def test_stop_failed(self):
        plugin = self._makeOne()
        result = plugin.do_stop('FAILED')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'FAILED\n')

    def test_stop_one_success(self):
        plugin = self._makeOne()
        result = plugin.do_stop('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'foo: stopped\n')

    def test_stop_many(self):
        plugin = self._makeOne()
        result = plugin.do_stop('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\nbar: stopped\n')

    def test_stop_group(self):
        plugin = self._makeOne()
        result = plugin.do_stop('foo:')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo_00: stopped\nfoo_01: stopped\n')

    def test_stop_all(self):
        plugin = self._makeOne()
        result = plugin.do_stop('all')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue(),
         'foo: stopped\nfoo2: stopped\nfailed: ERROR (no such process)\n')

    def test_restart_fail(self):
        plugin = self._makeOne()
        result = plugin.do_restart('')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0],
         'Error: restart requires a process name')

    def test_restart_one(self):
        plugin = self._makeOne()
        result = plugin.do_restart('foo')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: stopped\nfoo: started\n')

    def test_restart_all(self):
        plugin = self._makeOne()
        result = plugin.do_restart('all')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         ('foo: stopped\nfoo2: stopped\n'
                          'failed: ERROR (no such process)\n'
                          'foo: started\nfoo2: started\n'
                          'failed: ERROR (spawn error)\n'))

    def test_clear_fail(self):
        plugin = self._makeOne()
        result = plugin.do_clear('')
        self.assertEqual(result, None)
        expected = "Error: clear requires a process name"
        self.assertEqual(plugin.ctl.stdout.getvalue().split('\n')[0], expected)

    def test_clear_badname(self):
        plugin = self._makeOne()
        result = plugin.do_clear('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_clear_one_success(self):
        plugin = self._makeOne()
        result = plugin.do_clear('foo')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'foo: cleared\n')

    def test_clear_many(self):
        plugin = self._makeOne()
        result = plugin.do_clear('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'foo: cleared\nbar: cleared\n')

    def test_clear_all(self):
        plugin = self._makeOne()
        result = plugin.do_clear('all')
        self.assertEqual(result, None)

        self.assertEqual(plugin.ctl.stdout.getvalue(),
         'foo: cleared\nfoo2: cleared\nfailed: ERROR (failed)\n')

    def test_open_fail(self):
        plugin = self._makeOne()
        result = plugin.do_open('badname')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: url must be http:// or unix://\n')

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

    def test_version(self):
        plugin = self._makeOne()
        plugin.do_version(None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), '3000\n')

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

    def test_shutdown(self):
        plugin = self._makeOne()
        options = plugin.ctl.options
        result = plugin.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._shutdown, True)
        
    def test_shutdown_catches_xmlrpc_fault_shutdown_state(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc
        import xmlrpclib
        
        def raise_fault(*arg, **kw):     
            raise xmlrpclib.Fault(xmlrpc.Faults.SHUTDOWN_STATE, 'bye')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        result = plugin.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 
                         'ERROR: already shutting down\n')

    def test_shutdown_reraises_other_xmlrpc_faults(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc
        import xmlrpclib
        
        def raise_fault(*arg, **kw):     
            raise xmlrpclib.Fault(xmlrpc.Faults.CANT_REREAD, 'ouch')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        self.assertRaises(xmlrpclib.Fault, 
                          plugin.do_shutdown, '')

    def test_shutdown_catches_socket_error_ECONNREFUSED(self):
        plugin = self._makeOne()
        import socket
        import errno
        
        def raise_fault(*arg, **kw):     
            raise socket.error(errno.ECONNREFUSED, 'nobody home')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        result = plugin.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(), 
                         'ERROR: http://localhost:92491 refused'
                         ' connection (already shut down?)\n')

    def test_shutdown_reraises_other_socket_errors(self):
        plugin = self._makeOne()
        import socket
        import errno

        def raise_fault(*arg, **kw):     
            raise socket.error(errno.EPERM, 'denied')
        plugin.ctl.options._server.supervisor.shutdown = raise_fault

        self.assertRaises(socket.error, 
                          plugin.do_shutdown, '')

    def test__formatChanges(self):
        plugin = self._makeOne()
        # Don't explode, plz
        plugin._formatChanges([['added'], ['changed'], ['removed']])
        plugin._formatChanges([[], [], []])

    def test_reread(self):
        plugin = self._makeOne()
        calls = []
        plugin._formatChanges = lambda x: calls.append(x)
        result = plugin.do_reread(None)
        self.assertEqual(result, None)
        self.assertEqual(calls[0], [['added'], ['changed'], ['removed']])

    def test_reread_Fault(self):
        plugin = self._makeOne()
        from supervisor import xmlrpc
        import xmlrpclib
        def raise_fault(*arg, **kw):
            raise xmlrpclib.Fault(xmlrpc.Faults.CANT_REREAD, 'cant')
        plugin.ctl.options._server.supervisor.reloadConfig = raise_fault
        plugin.do_reread(None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: cant\n')

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

    def test_add(self):
        plugin = self._makeOne()
        result = plugin.do_add('foo')
        self.assertEqual(result, None)
        supervisor = plugin.ctl.options._server.supervisor
        self.assertEqual(supervisor.processes, ['foo'])

    def test_add_already_added(self):
        plugin = self._makeOne()
        result = plugin.do_add('ALREADY_ADDED')
        self.assertEqual(result, None)
        supervisor = plugin.ctl.options._server.supervisor
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: process group already active\n')

    def test_add_bad_name(self):
        plugin = self._makeOne()
        result = plugin.do_add('BAD_NAME')
        self.assertEqual(result, None)
        supervisor = plugin.ctl.options._server.supervisor
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: no such process/group: BAD_NAME\n')

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

    def test_remove_still_running(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor
        supervisor.processes = ['foo']
        result = plugin.do_remove('STILL_RUNNING')
        self.assertEqual(result, None)
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'ERROR: process/group still running: STILL_RUNNING\n')

    def test_update_not_on_shutdown(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor
        def reloadConfig():
            from supervisor import xmlrpc
            import xmlrpclib
            raise xmlrpclib.Fault(xmlrpc.Faults.SHUTDOWN_STATE, 'blah')
        supervisor.reloadConfig = reloadConfig
        supervisor.processes = ['removed']
        plugin.do_update('')
        self.assertEqual(supervisor.processes, ['removed'])

    def test_update_added_procs(self):
        plugin = self._makeOne()
        supervisor = plugin.ctl.options._server.supervisor

        calls = []
        def reloadConfig():
            return [[['new_proc'], [], []]]
        supervisor.reloadConfig = reloadConfig

        plugin.do_update('')
        self.assertEqual(supervisor.processes, ['new_proc'])

    def test_update_changed_procs(self):
        from supervisor import xmlrpc
        import xmlrpclib

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

    def test_pid(self):
        plugin = self._makeOne()
        result = plugin.do_pid('')
        options = plugin.ctl.options
        self.assertEqual(result, None)
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], str(options._server.supervisor.getPID()))

    def test_maintail_toomanyargs(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('foo bar')
        val = plugin.ctl.stdout.getvalue()
        self.failUnless(val.startswith('Error: too many'), val)

    def test_maintail_minus_string_fails(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('-wrong')
        val = plugin.ctl.stdout.getvalue()
        self.failUnless(val.startswith('Error: bad argument -wrong'), val)

    def test_maintail_wrong(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('wrong')
        val = plugin.ctl.stdout.getvalue()
        self.failUnless(val.startswith('Error: bad argument wrong'), val)

    def test_maintail_dashf(self):
        plugin = self._makeOne()
        plugin.listener = DummyListener()
        result = plugin.do_maintail('-f')
        errors = plugin.listener.errors
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(plugin.listener.closed,
                         'http://localhost:92491/mainlogtail')
        self.assertEqual(error[0],
                         'http://localhost:92491/mainlogtail')
        for msg in ('Cannot connect', 'socket.error'):
            self.assertTrue(msg in error[1])

    def test_maintail_nobytes(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('')
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'mainlogdata\n')

    def test_maintail_dashbytes(self):
        plugin = self._makeOne()
        result = plugin.do_maintail('-100')
        self.assertEqual(plugin.ctl.stdout.getvalue(), 'mainlogdata\n')

    def test_maintail_readlog_error_nofile(self):
        plugin = self._makeOne()
        supervisor_rpc = plugin.ctl.get_supervisor()
        from supervisor import xmlrpc
        supervisor_rpc._readlog_error = xmlrpc.Faults.NO_FILE
        result = plugin.do_maintail('-100')
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'supervisord: ERROR (no log file)\n')

    def test_maintail_readlog_error_failed(self):
        plugin = self._makeOne()
        supervisor_rpc = plugin.ctl.get_supervisor()
        from supervisor import xmlrpc
        supervisor_rpc._readlog_error = xmlrpc.Faults.FAILED
        result = plugin.do_maintail('-100')
        self.assertEqual(plugin.ctl.stdout.getvalue(),
                         'supervisord: ERROR (unknown error reading log)\n')

    def test_fg_too_few_args(self):
        plugin = self._makeOne()
        result = plugin.do_fg('')
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(result, None)
        self.assertEqual(lines[0], 'Error: no process name supplied')

    def test_fg_too_many_args(self):
        plugin = self._makeOne()
        result = plugin.do_fg('foo bar')
        line = plugin.ctl.stdout.getvalue()
        self.assertEqual(result, None)
        self.assertEqual(line, 'Error: too many process names supplied\n')

    def test_fg_badprocname(self):
        plugin = self._makeOne()
        result = plugin.do_fg('BAD_NAME')
        line = plugin.ctl.stdout.getvalue()
        self.assertEqual(result, None)
        self.assertEqual(line, 'Error: bad process name supplied\n')

    def test_fg_procnotrunning(self):
        plugin = self._makeOne()
        result = plugin.do_fg('bar')
        line = plugin.ctl.stdout.getvalue()
        self.assertEqual(result, None)
        self.assertEqual(line, 'Error: process not running\n')
        result = plugin.do_fg('baz_01')
        lines = plugin.ctl.stdout.getvalue().split('\n')
        self.assertEqual(result, None)
        self.assertEqual(lines[-2], 'Error: process not running')

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
        self.serverurl = 'http://localhost:92491' # should be uncontactable
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

class DummyPlugin:
    def __init__(self, controller=None):
        self.ctl = controller
        
    def do_help(self, arg):
        self.helped = True

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

