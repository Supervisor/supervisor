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
        result = controller._upcheck()
        self.assertEqual(result, True)

    def test__upcheck_wrong_server_version(self):
        options = DummyClientOptions()
        options._server.supervisor.getVersion = lambda *x: '1.0'
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller._upcheck()
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
        result = controller._upcheck()
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
        result = controller.onecmd('help')
        self.assertEqual(result, None)
        self.failUnless(
            controller.stdout.getvalue().find('Documented commands') != -1
            )

    def test_tail_toofewargs(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: too few arguments')

    def test_tail_toomanyargs(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('one two three four')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: too many arguments')

    def test_tail_defaults(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('foo')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'output line')

    def test_tail_no_file(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('NO_FILE')
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'NO_FILE: ERROR (no log file)')

    def test_tail_failed(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('FAILED')
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'FAILED: ERROR (unknown error reading log)')

    def test_tail_bad_name(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('BAD_NAME')
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], 'BAD_NAME: ERROR (no such process name)')

    def test_tail_bytesmodifier(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('-10 foo')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], 'tput line')

    def test_tail_explicit_channel_stdout_nomodifier(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('foo stdout')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'output line')

    def test_tail_explicit_channel_stderr_nomodifier(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('foo stderr')
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'output line')

    def test_tail_explicit_channel_unrecognized(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('foo fudge')
        self.assertEqual(result, None)
        value = controller.stdout.getvalue().strip()
        self.assertEqual(value, "Error: bad channel 'fudge'")

    def test_status_oneprocess(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_status('foo')
        self.assertEqual(result, None)
        value = controller.stdout.getvalue().strip()
        self.assertEqual(value.split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
                         

    def test_status_allprocesses(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_status('')
        self.assertEqual(result, None)
        value = controller.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
        self.assertEqual(value[1].split(None, 2),
                         ['bar', 'FATAL', 'bar description'])
        self.assertEqual(value[2].split(None, 2),
                         ['baz:baz_01', 'STOPPED', 'baz description'])

    def test_start_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('')
        self.assertEqual(result, None)
        expected = "Error: start requires a process name"
        self.assertEqual(controller.stdout.getvalue().split('\n')[0], expected)

    def test_start_badname(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_start_alreadystarted(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('ALREADY_STARTED')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'ALREADY_STARTED: ERROR (already started)\n')

    def test_start_spawnerror(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('SPAWN_ERROR')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'SPAWN_ERROR: ERROR (spawn error)\n')

    def test_start_one_success(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('foo')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), 'foo: started\n')

    def test_start_many(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'foo: started\nbar: started\n')

    def test_start_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
                'foo: started\nfoo2: started\nfailed: ERROR (spawn error)\n')


    def test_stop_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('')
        self.assertEqual(result, None)
        expected = "Error: stop requires a process name"
        self.assertEqual(controller.stdout.getvalue().split('\n')[0], expected)

    def test_stop_badname(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_stop_notrunning(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('NOT_RUNNING')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'NOT_RUNNING: ERROR (not running)\n')

    def test_stop_failed(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('FAILED')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), 'FAILED\n')

    def test_stop_one_success(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('foo')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), 'foo: stopped\n')

    def test_stop_many(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'foo: stopped\nbar: stopped\n')

    def test_stop_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
         'foo: stopped\nfoo2: stopped\nfailed: ERROR (no such process)\n')

    def test_restart_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_restart('')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue().split('\n')[0],
         'Error: restart requires a process name')

    def test_restart_one(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_restart('foo')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
                         'foo: stopped\nfoo: started\n')

    def test_restart_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_restart('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
                         ('foo: stopped\nfoo2: stopped\n'
                          'failed: ERROR (no such process)\n'
                          'foo: started\nfoo2: started\n'
                          'failed: ERROR (spawn error)\n'))

    def test_reload_fail(self):
        options = DummyClientOptions()
        options.interactive = False
        options._server.supervisor._restartable = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_reload('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._restarted, False)
        
    def test_reload(self):
        options = DummyClientOptions()
        options.interactive = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_reload('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._restarted, True)
        
    def test_shutdown_fail(self):
        options = DummyClientOptions()
        options.interactive = False
        options._server.supervisor._restartable = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._shutdown, False)

    def test_shutdown(self):
        options = DummyClientOptions()
        options.interactive = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._shutdown, True)





    def test_clear_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('')
        self.assertEqual(result, None)
        expected = "Error: clear requires a process name"
        self.assertEqual(controller.stdout.getvalue().split('\n')[0], expected)

    def test_clear_badname(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_clear_one_success(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('foo')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), 'foo: cleared\n')

    def test_clear_many(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'foo: cleared\nbar: cleared\n')

    def test_clear_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
         'foo: cleared\nfoo2: cleared\nfailed: ERROR (failed)\n')

    def test_open_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_open('badname')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'ERROR: url must be http:// or unix://\n')

    def test_open_succeed(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_open('http://localhost:9002')
        self.assertEqual(result, None)
        value = controller.stdout.getvalue().split('\n')
        self.assertEqual(value[0].split(None, 2),
                         ['foo', 'RUNNING', 'foo description'])
        self.assertEqual(value[1].split(None, 2),
                         ['bar', 'FATAL', 'bar description'])
        self.assertEqual(value[2].split(None, 2),
                         ['baz:baz_01', 'STOPPED', 'baz description'])
#""")

    def test_version(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        controller.do_version(None)
        self.assertEqual(controller.stdout.getvalue(), '3000\n')

class DummyClientOptions:
    def __init__(self):
        self.prompt = 'supervisor'
        self.serverurl = 'http://localhost:9001'
        self.username = 'chrism'
        self.password = '123'
        self._server = DummyRPCServer()

    def getServerProxy(self):
        return self._server

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

