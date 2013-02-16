"""Test suite for supervisor.options"""

import os
import sys
import tempfile
import socket
import unittest
import signal
import shutil
import errno
try:
    # Python < 3
    from StringIO import StringIO
except ImportError:
    # Python >= 3
    from io import StringIO

from mock import Mock, patch, sentinel

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyLogger
from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummySocketConfig
from supervisor.tests.base import lstrip

class OptionTests(unittest.TestCase):

    def _makeOptions(self, read_error=False):
        from cStringIO import StringIO
        from supervisor.options import Options
        from supervisor.datatypes import integer

        class MyOptions(Options):
            master = {
                'other': 41 }
            def __init__(self, read_error=read_error):
                self.read_error = read_error
                Options.__init__(self)
                class Foo(object): pass
                self.configroot = Foo()

            def read_config(self, fp):
                if self.read_error:
                    raise ValueError(self.read_error)
                # Pretend we read it from file:
                self.configroot.__dict__.update(self.default_map)
                self.configroot.__dict__.update(self.master)

        options = MyOptions()
        options.configfile = StringIO()
        options.add(name='anoption', confname='anoption',
                    short='o', long='option', default='default')
        options.add(name='other', confname='other', env='OTHER',
                    short='p:', long='other=', handler=integer)
        return options

    def test_searchpaths(self):
        options = self._makeOptions()
        self.assertEquals(len(options.searchpaths), 5)
        self.assertTrue('supervisord.conf' in options.searchpaths)
        self.assertTrue('etc/supervisord.conf' in options.searchpaths)
        self.assertTrue('/etc/supervisord.conf' in options.searchpaths)

    def test_options_and_args_order(self):
        # Only config file exists
        options = self._makeOptions()
        options.realize([])
        self.assertEquals(options.anoption, 'default')
        self.assertEquals(options.other, 41)

        # Env should trump config
        options = self._makeOptions()
        os.environ['OTHER'] = '42'
        options.realize([])
        self.assertEquals(options.other, 42)

        # Opt should trump both env (still set) and config
        options = self._makeOptions()
        options.realize(['-p', '43'])
        self.assertEquals(options.other, 43)
        del os.environ['OTHER']

    def test_config_reload(self):
        options = self._makeOptions()
        options.realize([])
        self.assertEquals(options.other, 41)
        options.master['other'] = 42
        options.process_config()
        self.assertEquals(options.other, 42)

    def test_config_reload_do_usage_false(self):
        options = self._makeOptions(read_error='error')
        self.assertRaises(ValueError, options.process_config,
                          False)

    def test_config_reload_do_usage_true(self):
        options = self._makeOptions(read_error='error')
        from StringIO import StringIO
        L = []
        def exit(num):
            L.append(num)
        options.stderr = options.stdout = StringIO()
        options.exit = exit
        options.configroot.anoption = 1
        options.configroot.other = 1
        options.process_config(True)
        self.assertEqual(L, [2])

    def test__set(self):
        from supervisor.options import Options
        options = Options()
        options._set('foo', 'bar', 0)
        self.assertEquals(options.foo, 'bar')
        self.assertEquals(options.attr_priorities['foo'], 0)
        options._set('foo', 'baz', 1)
        self.assertEquals(options.foo, 'baz')
        self.assertEquals(options.attr_priorities['foo'], 1)
        options._set('foo', 'gazonk', 0)
        self.assertEquals(options.foo, 'baz')
        self.assertEquals(options.attr_priorities['foo'], 1)
        options._set('foo', 'gazonk', 1)
        self.assertEquals(options.foo, 'gazonk')

class ClientOptionsTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import ClientOptions
        return ClientOptions

    def _makeOne(self):
        return self._getTargetClass()()

    def test_no_config_file(self):
        """Making sure config file is not required."""
        instance = self._makeOne()

        # No default config file search in case they would exist
        self.assertTrue(len(instance.searchpaths) > 0)
        instance.searchpaths = []

        class DummyException(Exception):
            pass
        def dummy_exit(self, _exitcode=0):
            raise DummyException()
        instance.exit = dummy_exit

        instance.realize(args=['-s', 'http://localhost:9001', '-u', 'chris',
                               '-p', '123'])

        self.assertEquals(instance.interactive, 1)
        self.assertEqual(instance.serverurl, 'http://localhost:9001')
        self.assertEqual(instance.username, 'chris')
        self.assertEqual(instance.password, '123')

    def test_options(self):
        tempdir = tempfile.gettempdir()
        s = lstrip("""[supervisorctl]
        serverurl=http://localhost:9001
        username=chris
        password=123
        prompt=mysupervisor
        history_file=%s/sc_history
        """ % tempdir)

        from StringIO import StringIO
        fp = StringIO(s)
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize(args=[])
        self.assertEqual(instance.interactive, True)
        history_file = os.path.join(tempdir, 'sc_history')
        self.assertEqual(instance.history_file, history_file)
        options = instance.configroot.supervisorctl
        self.assertEqual(options.prompt, 'mysupervisor')
        self.assertEqual(options.serverurl, 'http://localhost:9001')
        self.assertEqual(options.username, 'chris')
        self.assertEqual(options.password, '123')
        self.assertEqual(options.history_file, history_file)

    def test_options_unixsocket_cli(self):
        from StringIO import StringIO
        fp = StringIO('[supervisorctl]')
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize(args=['--serverurl', 'unix:///dev/null'])
        self.assertEqual(instance.serverurl, 'unix:///dev/null')

class ServerOptionsTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import ServerOptions
        return ServerOptions

    def _makeOne(self):
        return self._getTargetClass()()

    def test_version(self):
        from supervisor.options import VERSION
        options = self._makeOne()
        from StringIO import StringIO
        options.stdout = StringIO()
        self.assertRaises(SystemExit, options.version, None)
        self.assertEqual(options.stdout.getvalue(), VERSION + '\n')

    def test_options(self):
        s = lstrip("""[inet_http_server]
        port=127.0.0.1:8999
        username=chrism
        password=foo

        [supervisord]
        directory=%(tempdir)s
        backofflimit=10
        user=root
        umask=022
        logfile=supervisord.log
        logfile_maxbytes=1000MB
        logfile_backups=5
        loglevel=error
        pidfile=supervisord.pid
        nodaemon=true
        identifier=fleeb
        childlogdir=%(tempdir)s
        nocleanup=true
        minfds=2048
        minprocs=300
        environment=FAKE_ENV_VAR=/some/path

        [program:cat1]
        command=/bin/cat
        priority=1
        autostart=true
        user=root
        stdout_logfile=/tmp/cat.log
        stopsignal=KILL
        stopwaitsecs=5
        startsecs=5
        startretries=10
        directory=/tmp
        umask=002

        [program:cat2]
        priority=2
        command=/bin/cat
        autostart=true
        autorestart=false
        stdout_logfile_maxbytes = 1024
        stdout_logfile_backups = 2
        stdout_logfile = /tmp/cat2.log

        [program:cat3]
        priority=3
        process_name = replaced
        command=/bin/cat
        autorestart=true
        exitcodes=0,1,127
        stopasgroup=true
        killasgroup=true

        [program:cat4]
        priority=4
        process_name = fleeb_%%(process_num)s
        numprocs = 2
        command = /bin/cat
        autorestart=unexpected
        """ % {'tempdir':tempfile.gettempdir()})

        from supervisor import datatypes

        from StringIO import StringIO
        fp = StringIO(s)
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize(args=[])
        options = instance.configroot.supervisord
        self.assertEqual(options.directory, tempfile.gettempdir())
        self.assertEqual(options.umask, 022)
        self.assertEqual(options.logfile, 'supervisord.log')
        self.assertEqual(options.logfile_maxbytes, 1000 * 1024 * 1024)
        self.assertEqual(options.logfile_backups, 5)
        self.assertEqual(options.loglevel, 40)
        self.assertEqual(options.pidfile, 'supervisord.pid')
        self.assertEqual(options.nodaemon, True)
        self.assertEqual(options.identifier, 'fleeb')
        self.assertEqual(options.childlogdir, tempfile.gettempdir())
        self.assertEqual(len(options.server_configs), 1)
        self.assertEqual(options.server_configs[0]['family'], socket.AF_INET)
        self.assertEqual(options.server_configs[0]['host'], '127.0.0.1')
        self.assertEqual(options.server_configs[0]['port'], 8999)
        self.assertEqual(options.server_configs[0]['username'], 'chrism')
        self.assertEqual(options.server_configs[0]['password'], 'foo')
        self.assertEqual(options.nocleanup, True)
        self.assertEqual(options.minfds, 2048)
        self.assertEqual(options.minprocs, 300)
        self.assertEqual(options.nocleanup, True)
        self.assertEqual(len(options.process_group_configs), 4)
        self.assertEqual(options.environment, dict(FAKE_ENV_VAR='/some/path'))

        cat1 = options.process_group_configs[0]
        self.assertEqual(cat1.name, 'cat1')
        self.assertEqual(cat1.priority, 1)
        self.assertEqual(len(cat1.process_configs), 1)

        proc1 = cat1.process_configs[0]
        self.assertEqual(proc1.name, 'cat1')
        self.assertEqual(proc1.command, '/bin/cat')
        self.assertEqual(proc1.priority, 1)
        self.assertEqual(proc1.autostart, True)
        self.assertEqual(proc1.autorestart, datatypes.RestartWhenExitUnexpected)
        self.assertEqual(proc1.startsecs, 5)
        self.assertEqual(proc1.startretries, 10)
        self.assertEqual(proc1.uid, 0)
        self.assertEqual(proc1.stdout_logfile, '/tmp/cat.log')
        self.assertEqual(proc1.stopsignal, signal.SIGKILL)
        self.assertEqual(proc1.stopwaitsecs, 5)
        self.assertEqual(proc1.stopasgroup, False)
        self.assertEqual(proc1.killasgroup, False)
        self.assertEqual(proc1.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc1.stdout_logfile_backups, 10)
        self.assertEqual(proc1.exitcodes, [0,2])
        self.assertEqual(proc1.directory, '/tmp')
        self.assertEqual(proc1.umask, 002)
        self.assertEqual(proc1.environment, dict(FAKE_ENV_VAR='/some/path'))

        cat2 = options.process_group_configs[1]
        self.assertEqual(cat2.name, 'cat2')
        self.assertEqual(cat2.priority, 2)
        self.assertEqual(len(cat2.process_configs), 1)

        proc2 = cat2.process_configs[0]
        self.assertEqual(proc2.name, 'cat2')
        self.assertEqual(proc2.command, '/bin/cat')
        self.assertEqual(proc2.priority, 2)
        self.assertEqual(proc2.autostart, True)
        self.assertEqual(proc2.autorestart, False)
        self.assertEqual(proc2.uid, None)
        self.assertEqual(proc2.stdout_logfile, '/tmp/cat2.log')
        self.assertEqual(proc2.stopsignal, signal.SIGTERM)
        self.assertEqual(proc2.stopasgroup, False)
        self.assertEqual(proc2.killasgroup, False)
        self.assertEqual(proc2.stdout_logfile_maxbytes, 1024)
        self.assertEqual(proc2.stdout_logfile_backups, 2)
        self.assertEqual(proc2.exitcodes, [0,2])
        self.assertEqual(proc2.directory, None)

        cat3 = options.process_group_configs[2]
        self.assertEqual(cat3.name, 'cat3')
        self.assertEqual(cat3.priority, 3)
        self.assertEqual(len(cat3.process_configs), 1)

        proc3 = cat3.process_configs[0]
        self.assertEqual(proc3.name, 'replaced')
        self.assertEqual(proc3.command, '/bin/cat')
        self.assertEqual(proc3.priority, 3)
        self.assertEqual(proc3.autostart, True)
        self.assertEqual(proc3.autorestart, datatypes.RestartUnconditionally)
        self.assertEqual(proc3.uid, None)
        self.assertEqual(proc3.stdout_logfile, datatypes.Automatic)
        self.assertEqual(proc3.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc3.stdout_logfile_backups, 10)
        self.assertEqual(proc3.exitcodes, [0,1,127])
        self.assertEqual(proc3.stopsignal, signal.SIGTERM)
        self.assertEqual(proc3.stopasgroup, True)
        self.assertEqual(proc3.killasgroup, True)

        cat4 = options.process_group_configs[3]
        self.assertEqual(cat4.name, 'cat4')
        self.assertEqual(cat4.priority, 4)
        self.assertEqual(len(cat4.process_configs), 2)

        proc4_a = cat4.process_configs[0]
        self.assertEqual(proc4_a.name, 'fleeb_0')
        self.assertEqual(proc4_a.command, '/bin/cat')
        self.assertEqual(proc4_a.priority, 4)
        self.assertEqual(proc4_a.autostart, True)
        self.assertEqual(proc4_a.autorestart,
                         datatypes.RestartWhenExitUnexpected)
        self.assertEqual(proc4_a.uid, None)
        self.assertEqual(proc4_a.stdout_logfile, datatypes.Automatic)
        self.assertEqual(proc4_a.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc4_a.stdout_logfile_backups, 10)
        self.assertEqual(proc4_a.exitcodes, [0,2])
        self.assertEqual(proc4_a.stopsignal, signal.SIGTERM)
        self.assertEqual(proc4_a.stopasgroup, False)
        self.assertEqual(proc4_a.killasgroup, False)

        proc4_b = cat4.process_configs[1]
        self.assertEqual(proc4_b.name, 'fleeb_1')
        self.assertEqual(proc4_b.command, '/bin/cat')
        self.assertEqual(proc4_b.priority, 4)
        self.assertEqual(proc4_b.autostart, True)
        self.assertEqual(proc4_b.autorestart,
                         datatypes.RestartWhenExitUnexpected)
        self.assertEqual(proc4_b.uid, None)
        self.assertEqual(proc4_b.stdout_logfile, datatypes.Automatic)
        self.assertEqual(proc4_b.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc4_b.stdout_logfile_backups, 10)
        self.assertEqual(proc4_b.exitcodes, [0,2])
        self.assertEqual(proc4_b.stopsignal, signal.SIGTERM)
        self.assertEqual(proc4_b.stopasgroup, False)
        self.assertEqual(proc4_b.killasgroup, False)

        here = os.path.abspath(os.getcwd())
        self.assertEqual(instance.uid, 0)
        self.assertEqual(instance.gid, 0)
        self.assertEqual(instance.directory, tempfile.gettempdir())
        self.assertEqual(instance.umask, 022)
        self.assertEqual(instance.logfile, os.path.join(here,'supervisord.log'))
        self.assertEqual(instance.logfile_maxbytes, 1000 * 1024 * 1024)
        self.assertEqual(instance.logfile_backups, 5)
        self.assertEqual(instance.loglevel, 40)
        self.assertEqual(instance.pidfile, os.path.join(here,'supervisord.pid'))
        self.assertEqual(instance.nodaemon, True)
        self.assertEqual(instance.passwdfile, None)
        self.assertEqual(instance.identifier, 'fleeb')
        self.assertEqual(instance.childlogdir, tempfile.gettempdir())

        self.assertEqual(len(instance.server_configs), 1)
        self.assertEqual(instance.server_configs[0]['family'], socket.AF_INET)
        self.assertEqual(instance.server_configs[0]['host'], '127.0.0.1')
        self.assertEqual(instance.server_configs[0]['port'], 8999)
        self.assertEqual(instance.server_configs[0]['username'], 'chrism')
        self.assertEqual(instance.server_configs[0]['password'], 'foo')

        self.assertEqual(instance.nocleanup, True)
        self.assertEqual(instance.minfds, 2048)
        self.assertEqual(instance.minprocs, 300)

    def test_no_config_file_exits(self):
        instance = self._makeOne()

        # No default config file search in case they would exist
        self.assertTrue(len(instance.searchpaths) > 0)
        instance.searchpaths = []

        class DummyException(Exception):
            def __init__(self, exitcode):
                self.exitcode = exitcode
        def dummy_exit(exitcode=2):
            # Important default exitcode=2 like sys.exit.
            raise DummyException(exitcode)
        instance.exit = dummy_exit

        # Making sure we capture stdout and stderr
        instance.stderr = StringIO()

        try:
            instance.realize()
        except DummyException, e:
            # Caught expected exception
            import traceback
            self.assertEquals(e.exitcode, 2,
                              "Wrong exitcode for: %s" % traceback.format_exc(e))
        else:
            self.fail("Did not get a DummyException.")

    def test_reload(self):
        from cStringIO import StringIO
        text = lstrip("""\
        [supervisord]
        user=root

        [program:one]
        command = /bin/cat

        [program:two]
        command = /bin/dog

        [program:four]
        command = /bin/sheep

        [group:thegroup]
        programs = one,two
        """)

        instance = self._makeOne()
        instance.configfile = StringIO(text)
        instance.realize(args=[])

        section = instance.configroot.supervisord

        self.assertEqual(len(section.process_group_configs), 2)

        cat = section.process_group_configs[0]
        self.assertEqual(len(cat.process_configs), 1)

        cat = section.process_group_configs[1]
        self.assertEqual(len(cat.process_configs), 2)
        self.assertTrue(section.process_group_configs is
                        instance.process_group_configs)

        text = lstrip("""\
        [supervisord]
        user=root

        [program:one]
        command = /bin/cat

        [program:three]
        command = /bin/pig

        [group:thegroup]
        programs = three
        """)
        instance.configfile = StringIO(text)
        instance.process_config()

        section = instance.configroot.supervisord

        self.assertEqual(len(section.process_group_configs), 2)

        cat = section.process_group_configs[0]
        self.assertEqual(len(cat.process_configs), 1)
        proc = cat.process_configs[0]
        self.assertEqual(proc.name, 'one')
        self.assertEqual(proc.command, '/bin/cat')
        self.assertTrue(section.process_group_configs is
                        instance.process_group_configs)

        cat = section.process_group_configs[1]
        self.assertEqual(len(cat.process_configs), 1)
        proc = cat.process_configs[0]
        self.assertEqual(proc.name, 'three')
        self.assertEqual(proc.command, '/bin/pig')

    def test_reload_clears_parse_warnings(self):
        instance = self._makeOne()
        old_warning = "Warning from a prior config read"
        instance.parse_warnings = [old_warning]

        from cStringIO import StringIO
        text = lstrip("""\
        [supervisord]
        user=root

        [program:cat]
        command = /bin/cat
        """)
        instance.configfile = StringIO(text)
        instance.realize(args=[])
        self.assertFalse(old_warning in instance.parse_warnings)

    def test_readFile_failed(self):
        from supervisor.options import readFile
        try:
            readFile('/notthere', 0, 10)
        except ValueError, inst:
            self.assertEqual(inst.args[0], 'FAILED')
        else:
            raise AssertionError("Didn't raise")

    def test_get_pid(self):
        instance = self._makeOne()
        self.assertEqual(os.getpid(), instance.get_pid())

    def test_get_signal_delegates_to_signal_receiver(self):
        instance = self._makeOne()
        instance.signal_receiver.receive(signal.SIGTERM, None)
        instance.signal_receiver.receive(signal.SIGCHLD, None)
        self.assertEqual(instance.get_signal(), signal.SIGTERM)
        self.assertEqual(instance.get_signal(), signal.SIGCHLD)
        self.assertEqual(instance.get_signal(), None)

    def test_check_execv_args_cant_find_command(self):
        instance = self._makeOne()
        from supervisor.options import NotFound
        self.assertRaises(NotFound, instance.check_execv_args,
                          '/not/there', None, None)

    def test_check_execv_args_notexecutable(self):
        instance = self._makeOne()
        from supervisor.options import NotExecutable
        self.assertRaises(NotExecutable,
                          instance.check_execv_args, '/etc/passwd',
                          ['etc/passwd'], os.stat('/etc/passwd'))

    def test_check_execv_args_isdir(self):
        instance = self._makeOne()
        from supervisor.options import NotExecutable
        self.assertRaises(NotExecutable,
                          instance.check_execv_args, '/',
                          ['/'], os.stat('/'))

    def test_cleanup_afunix_unlink(self):
        fn = tempfile.mktemp()
        f = open(fn, 'w')
        f.write('foo')
        f.close()
        instance = self._makeOne()
        class Port:
            family = socket.AF_UNIX
            address = fn
        class Server:
            pass
        instance.httpservers = [({'family':socket.AF_UNIX, 'file':fn},
                                 Server())]
        instance.pidfile = ''
        instance.cleanup()
        self.failIf(os.path.exists(fn))

    def test_cleanup_afunix_nounlink(self):
        fn = tempfile.mktemp()
        try:
            f = open(fn, 'w')
            f.write('foo')
            f.close()
            instance = self._makeOne()
            class Port:
                family = socket.AF_UNIX
                address = fn
            class Server:
                pass
            instance.httpservers = [({'family':socket.AF_UNIX, 'file':fn},
                                     Server())]
            instance.pidfile = ''
            instance.unlink_socketfiles = False
            instance.cleanup()
            self.failUnless(os.path.exists(fn))
        finally:
            try:
                os.unlink(fn)
            except OSError:
                pass

    def test_close_httpservers(self):
        instance = self._makeOne()
        class Server:
            closed = False
            def close(self):
                self.closed = True
        server = Server()
        instance.httpservers = [({}, server)]
        instance.close_httpservers()
        self.assertEqual(server.closed, True)

    def test_close_logger(self):
        instance = self._makeOne()
        logger = DummyLogger()
        instance.logger = logger
        instance.close_logger()
        self.assertEqual(logger.closed, True)

    def test_write_pidfile_ok(self):
        fn = tempfile.mktemp()
        try:
            instance = self._makeOne()
            instance.logger = DummyLogger()
            instance.pidfile = fn
            instance.write_pidfile()
            self.failUnless(os.path.exists(fn))
            pid = int(open(fn, 'r').read()[:-1])
            self.assertEqual(pid, os.getpid())
            msg = instance.logger.data[0]
            self.failUnless(msg.startswith('supervisord started with pid'))
        finally:
            try:
                os.unlink(fn)
            except OSError:
                pass

    def test_write_pidfile_fail(self):
        fn = '/cannot/possibly/exist'
        instance = self._makeOne()
        instance.logger = DummyLogger()
        instance.pidfile = fn
        instance.write_pidfile()
        msg = instance.logger.data[0]
        self.failUnless(msg.startswith('could not write pidfile'))

    def test_close_fd(self):
        instance = self._makeOne()
        innie, outie = os.pipe()
        os.read(innie, 0) # we can read it while its open
        os.write(outie, 'foo') # we can write to it while its open
        instance.close_fd(innie)
        self.assertRaises(OSError, os.read, innie, 0)
        instance.close_fd(outie)
        self.assertRaises(OSError, os.write, outie, 'foo')

    def test_processes_from_section(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        priority = 1
        autostart = false
        autorestart = false
        startsecs = 100
        startretries = 100
        user = root
        stdout_logfile = NONE
        stdout_logfile_backups = 1
        stdout_logfile_maxbytes = 100MB
        stdout_events_enabled = true
        stopsignal = KILL
        stopwaitsecs = 100
        killasgroup = true
        exitcodes = 1,4
        redirect_stderr = false
        environment = KEY1=val1,KEY2=val2,KEY3=%(process_num)s
        numprocs = 2
        process_name = %(group_name)s_%(program_name)s_%(process_num)02d
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        pconfigs = instance.processes_from_section(config, 'program:foo', 'bar')
        self.assertEqual(len(pconfigs), 2)
        pconfig = pconfigs[0]
        self.assertEqual(pconfig.name, 'bar_foo_00')
        self.assertEqual(pconfig.command, '/bin/cat')
        self.assertEqual(pconfig.autostart, False)
        self.assertEqual(pconfig.autorestart, False)
        self.assertEqual(pconfig.startsecs, 100)
        self.assertEqual(pconfig.startretries, 100)
        self.assertEqual(pconfig.uid, 0)
        self.assertEqual(pconfig.stdout_logfile, None)
        self.assertEqual(pconfig.stdout_capture_maxbytes, 0)
        self.assertEqual(pconfig.stdout_logfile_maxbytes, 104857600)
        self.assertEqual(pconfig.stdout_events_enabled, True)
        self.assertEqual(pconfig.stopsignal, signal.SIGKILL)
        self.assertEqual(pconfig.stopasgroup, False)
        self.assertEqual(pconfig.killasgroup, True)
        self.assertEqual(pconfig.stopwaitsecs, 100)
        self.assertEqual(pconfig.exitcodes, [1,4])
        self.assertEqual(pconfig.redirect_stderr, False)
        self.assertEqual(pconfig.environment,
                         {'KEY1':'val1', 'KEY2':'val2', 'KEY3':'0'})

    def test_processes_from_section_host_node_name_expansion(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/foo --host=%(host_node_name)s
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        pconfigs = instance.processes_from_section(config, 'program:foo', 'bar')
        import platform
        expected = "/bin/foo --host=" + platform.node()
        self.assertEqual(pconfigs[0].command, expected)

    def test_processes_from_section_environment_variables_expansion(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/foo --path='%(ENV_PATH)s'
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        pconfigs = instance.processes_from_section(config, 'program:foo', 'bar')
        expected = "/bin/foo --path='%s'" % os.environ['PATH']
        self.assertEqual(pconfigs[0].command, expected)

    def test_all_options_environment_variables_expansions(self):
        # we can only test "common" cross-platform env vars: HOME,USER
        instance = self._makeOne()
        text = lstrip("""\
        [supervisord]
        logfile = %(ENV_HOME)s/supervisord.log
        logfile_maxbytes = 50MB
        logfile_backups=10
        loglevel = info
        nodaemon = false
        minfds = 1024
        minprocs = 200
        umask = 002
        identifier = supervisor_%(ENV_USER)s
        nocleanup = true
        childlogdir = %(ENV_HOME)s
        strip_ansi = false
        environment =
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance.configfile = StringIO(text)
        conf = instance.read_config(StringIO(text))
        instance.realize(args=[])
        self.assertEqual(instance.logfile, '%(HOME)s/supervisord.log' % os.environ)
        self.assertEqual(instance.identifier, 'supervisor_%(USER)s' % os.environ)

    def test_processes_from_section_no_procnum_in_processname(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        numprocs = 2
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        self.assertRaises(ValueError, instance.processes_from_section,
                          config, 'program:foo', None)

    def test_processes_from_section_no_command(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        numprocs = 2
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        self.assertRaises(ValueError, instance.processes_from_section,
                          config, 'program:foo', None)

    def test_processes_from_section_missing_replacement_in_process_name(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        process_name = %(not_there)s
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        self.assertRaises(ValueError, instance.processes_from_section,
                          config, 'program:foo', None)

    def test_processes_from_section_bad_expression_in_process_name(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        process_name = %(program_name)
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        self.assertRaises(ValueError, instance.processes_from_section,
                          config, 'program:foo', None)

    def test_processes_from_section_stopasgroup_implies_killasgroup(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        process_name = %(program_name)s
        stopasgroup = true
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        pconfigs = instance.processes_from_section(config, 'program:foo', 'bar')
        self.assertEqual(len(pconfigs), 1)
        pconfig = pconfigs[0]
        self.assertEqual(pconfig.stopasgroup, True)
        self.assertEqual(pconfig.killasgroup, True)
    
    def test_processes_from_section_killasgroup_mismatch_w_stopasgroup(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        process_name = %(program_name)s
        stopasgroup = true
        killasgroup = false
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        self.assertRaises(ValueError, instance.processes_from_section,
                          config, 'program:foo', None)

    def test_processes_from_autolog_without_rollover(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/foo
        stdout_logfile = AUTO
        stdout_logfile_maxbytes = 0
        stderr_logfile = AUTO
        stderr_logfile_maxbytes = 0
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        instance.logger = DummyLogger()
        config.read_string(text)
        instance.processes_from_section(config, 'program:foo', None)
        self.assertEqual(instance.parse_warnings[0],
             'For [program:foo], AUTO logging used for stdout_logfile '
             'without rollover, set maxbytes > 0 to avoid filling up '
              'filesystem unintentionally')
        self.assertEqual(instance.parse_warnings[1],
             'For [program:foo], AUTO logging used for stderr_logfile '
             'without rollover, set maxbytes > 0 to avoid filling up '
              'filesystem unintentionally')

    def test_homogeneous_process_groups_from_parser(self):
        text = lstrip("""\
        [program:many]
        process_name = %(program_name)s_%(process_num)s
        command = /bin/cat
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        gconfigs = instance.process_groups_from_parser(config)
        self.assertEqual(len(gconfigs), 1)
        gconfig = gconfigs[0]
        self.assertEqual(gconfig.name, 'many')
        self.assertEqual(gconfig.priority, 1)
        self.assertEqual(len(gconfig.process_configs), 2)

    def test_event_listener_pools_from_parser(self):
        text = lstrip("""\
        [eventlistener:dog]
        events=PROCESS_COMMUNICATION
        process_name = %(program_name)s_%(process_num)s
        command = /bin/dog
        numprocs = 2
        priority = 1

        [eventlistener:cat]
        events=PROCESS_COMMUNICATION
        process_name = %(program_name)s_%(process_num)s
        command = /bin/cat
        numprocs = 3

        [eventlistener:biz]
        events=PROCESS_COMMUNICATION
        process_name = %(program_name)s_%(process_num)s
        command = /bin/biz
        numprocs = 2
        """)
        from supervisor.options import UnhosedConfigParser
        from supervisor.dispatchers import default_handler
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        gconfigs = instance.process_groups_from_parser(config)
        self.assertEqual(len(gconfigs), 3)

        gconfig1 = gconfigs[0]
        self.assertEqual(gconfig1.name, 'biz')
        self.assertEqual(gconfig1.result_handler, default_handler)
        self.assertEqual(len(gconfig1.process_configs), 2)

        gconfig1 = gconfigs[1]
        self.assertEqual(gconfig1.name, 'cat')
        self.assertEqual(gconfig1.priority, -1)
        self.assertEqual(gconfig1.result_handler, default_handler)
        self.assertEqual(len(gconfig1.process_configs), 3)

        gconfig1 = gconfigs[2]
        self.assertEqual(gconfig1.name, 'dog')
        self.assertEqual(gconfig1.priority, 1)
        self.assertEqual(gconfig1.result_handler, default_handler)
        self.assertEqual(len(gconfig1.process_configs), 2)

    def test_event_listener_pool_with_event_results_handler(self):
        text = lstrip("""\
        [eventlistener:dog]
        events=PROCESS_COMMUNICATION
        command = /bin/dog
        result_handler = supervisor.tests.base:dummy_handler
        """)
        from supervisor.options import UnhosedConfigParser
        from supervisor.tests.base import dummy_handler
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        gconfigs = instance.process_groups_from_parser(config)
        self.assertEqual(len(gconfigs), 1)

        gconfig1 = gconfigs[0]
        self.assertEqual(gconfig1.result_handler, dummy_handler)

    def test_event_listener_pool_noeventsline(self):
        text = lstrip("""\
        [eventlistener:dog]
        process_name = %(program_name)s_%(process_num)s
        command = /bin/dog
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_event_listener_pool_unknown_eventtype(self):
        text = lstrip("""\
        [eventlistener:dog]
        events=PROCESS_COMMUNICATION,THIS_EVENT_TYPE_DOESNT_EXIST
        process_name = %(program_name)s_%(process_num)s
        command = /bin/dog
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_programs_from_parser(self):
        from supervisor.options import FastCGIGroupConfig
        from supervisor.options import FastCGIProcessConfig
        text = lstrip("""\
        [fcgi-program:foo]
        socket = unix:///tmp/%(program_name)s.sock
        socket_owner = testuser:testgroup
        socket_mode = 0666
        process_name = %(program_name)s_%(process_num)s
        command = /bin/foo
        numprocs = 2
        priority = 1

        [fcgi-program:bar]
        socket = unix:///tmp/%(program_name)s.sock
        process_name = %(program_name)s_%(process_num)s
        command = /bin/bar
        user = testuser
        numprocs = 3

        [fcgi-program:flub]
        socket = unix:///tmp/%(program_name)s.sock
        command = /bin/flub

        [fcgi-program:cub]
        socket = tcp://localhost:6000
        command = /bin/cub
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()

        #Patch pwd and grp module functions to give us sentinel
        #uid/gid values so that the test does not depend on
        #any specific system users
        pwd_mock = Mock()
        pwd_mock.return_value = (None, None, sentinel.uid, sentinel.gid)
        grp_mock = Mock()
        grp_mock.return_value = (None, None, sentinel.gid)
        @patch('pwd.getpwuid', pwd_mock)
        @patch('pwd.getpwnam', pwd_mock)
        @patch('grp.getgrnam', grp_mock)
        def get_process_groups(instance, config):
            return instance.process_groups_from_parser(config)

        gconfigs = get_process_groups(instance, config)

        exp_owner = (sentinel.uid, sentinel.gid)

        self.assertEqual(len(gconfigs), 4)

        gconf_foo = gconfigs[0]
        self.assertEqual(gconf_foo.__class__, FastCGIGroupConfig)
        self.assertEqual(gconf_foo.name, 'foo')
        self.assertEqual(gconf_foo.priority, 1)
        self.assertEqual(gconf_foo.socket_config.url,
                                'unix:///tmp/foo.sock')
        self.assertEqual(exp_owner, gconf_foo.socket_config.get_owner())
        self.assertEqual(0666, gconf_foo.socket_config.get_mode())
        self.assertEqual(len(gconf_foo.process_configs), 2)
        pconfig_foo = gconf_foo.process_configs[0]
        self.assertEqual(pconfig_foo.__class__, FastCGIProcessConfig)

        gconf_bar = gconfigs[1]
        self.assertEqual(gconf_bar.name, 'bar')
        self.assertEqual(gconf_bar.priority, 999)
        self.assertEqual(gconf_bar.socket_config.url,
                         'unix:///tmp/bar.sock')
        self.assertEqual(exp_owner, gconf_bar.socket_config.get_owner())
        self.assertEqual(0700, gconf_bar.socket_config.get_mode())
        self.assertEqual(len(gconf_bar.process_configs), 3)

        gconf_cub = gconfigs[2]
        self.assertEqual(gconf_cub.name, 'cub')
        self.assertEqual(gconf_cub.socket_config.url,
                         'tcp://localhost:6000')
        self.assertEqual(len(gconf_cub.process_configs), 1)

        gconf_flub = gconfigs[3]
        self.assertEqual(gconf_flub.name, 'flub')
        self.assertEqual(gconf_flub.socket_config.url,
                         'unix:///tmp/flub.sock')
        self.assertEqual(None, gconf_flub.socket_config.get_owner())
        self.assertEqual(0700, gconf_flub.socket_config.get_mode())
        self.assertEqual(len(gconf_flub.process_configs), 1)



    def test_fcgi_program_no_socket(self):
        text = lstrip("""\
        [fcgi-program:foo]
        process_name = %(program_name)s_%(process_num)s
        command = /bin/foo
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_unknown_socket_protocol(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket=junk://blah
        process_name = %(program_name)s_%(process_num)s
        command = /bin/foo
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_rel_unix_sock_path(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket=unix://relative/path
        process_name = %(program_name)s_%(process_num)s
        command = /bin/foo
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_bad_tcp_sock_format(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket=tcp://missingport
        process_name = %(program_name)s_%(process_num)s
        command = /bin/foo
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_bad_expansion_proc_num(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket=unix:///tmp/%(process_num)s.sock
        process_name = %(program_name)s_%(process_num)s
        command = /bin/foo
        numprocs = 2
        priority = 1
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_socket_owner_set_for_tcp(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket=tcp://localhost:8000
        socket_owner=nobody:nobody
        command = /bin/foo
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_socket_mode_set_for_tcp(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket = tcp://localhost:8000
        socket_mode = 0777
        command = /bin/foo
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_bad_socket_owner(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket = unix:///tmp/foo.sock
        socket_owner = sometotaljunkuserthatshouldnobethere
        command = /bin/foo
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_fcgi_program_bad_socket_mode(self):
        text = lstrip("""\
        [fcgi-program:foo]
        socket = unix:///tmp/foo.sock
        socket_mode = junk
        command = /bin/foo
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError,instance.process_groups_from_parser,config)

    def test_heterogeneous_process_groups_from_parser(self):
        text = lstrip("""\
        [program:one]
        command = /bin/cat

        [program:two]
        command = /bin/cat

        [group:thegroup]
        programs = one,two
        priority = 5
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        gconfigs = instance.process_groups_from_parser(config)
        self.assertEqual(len(gconfigs), 1)
        gconfig = gconfigs[0]
        self.assertEqual(gconfig.name, 'thegroup')
        self.assertEqual(gconfig.priority, 5)
        self.assertEqual(len(gconfig.process_configs), 2)

    def test_mixed_process_groups_from_parser1(self):
        text = lstrip("""\
        [program:one]
        command = /bin/cat

        [program:two]
        command = /bin/cat

        [program:many]
        process_name = %(program_name)s_%(process_num)s
        command = /bin/cat
        numprocs = 2
        priority = 1

        [group:thegroup]
        programs = one,two
        priority = 5
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        gconfigs = instance.process_groups_from_parser(config)
        self.assertEqual(len(gconfigs), 2)

        manyconfig = gconfigs[0]
        self.assertEqual(manyconfig.name, 'many')
        self.assertEqual(manyconfig.priority, 1)
        self.assertEqual(len(manyconfig.process_configs), 2)

        gconfig = gconfigs[1]
        self.assertEqual(gconfig.name, 'thegroup')
        self.assertEqual(gconfig.priority, 5)
        self.assertEqual(len(gconfig.process_configs), 2)

    def test_mixed_process_groups_from_parser2(self):
        text = lstrip("""\
        [program:one]
        command = /bin/cat

        [program:two]
        command = /bin/cat

        [program:many]
        process_name = %(program_name)s_%(process_num)s
        command = /bin/cat
        numprocs = 2
        priority = 1

        [group:thegroup]
        programs = one,two, many
        priority = 5
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        gconfigs = instance.process_groups_from_parser(config)
        self.assertEqual(len(gconfigs), 1)

        gconfig = gconfigs[0]
        self.assertEqual(gconfig.name, 'thegroup')
        self.assertEqual(gconfig.priority, 5)
        self.assertEqual(len(gconfig.process_configs), 4)

    def test_unknown_program_in_heterogeneous_group(self):
        text = lstrip("""\
        [program:one]
        command = /bin/cat

        [group:foo]
        programs = notthere
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        self.assertRaises(ValueError, instance.process_groups_from_parser,
                          config)

    def test_rpcinterfaces_from_parser(self):
        text = lstrip("""\
        [rpcinterface:dummy]
        supervisor.rpcinterface_factory = %s
        foo = bar
        """ % __name__)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        factories = instance.get_plugins(config,
                                         'supervisor.rpcinterface_factory',
                                         'rpcinterface:')
        self.assertEqual(len(factories), 1)
        factory = factories[0]
        self.assertEqual(factory[0], 'dummy')
        self.assertEqual(factory[1], sys.modules[__name__])
        self.assertEqual(factory[2], {'foo':'bar'})

    def test_clear_autochildlogdir(self):
        dn = tempfile.mkdtemp()
        try:
            instance = self._makeOne()
            instance.childlogdir = dn
            sid = 'supervisor'
            instance.identifier = sid
            logfn = instance.get_autochildlog_name('foo', sid,'stdout')
            first = logfn + '.1'
            second = logfn + '.2'
            open(first, 'w')
            open(second, 'w')
            instance.clear_autochildlogdir()
            self.failIf(os.path.exists(logfn))
            self.failIf(os.path.exists(first))
            self.failIf(os.path.exists(second))
        finally:
            shutil.rmtree(dn)

    def test_clear_autochildlog_oserror(self):
        instance = self._makeOne()
        instance.childlogdir = '/tmp/this/cant/possibly/existjjjj'
        instance.logger = DummyLogger()
        instance.clear_autochildlogdir()
        self.assertEqual(instance.logger.data, ['Could not clear childlog dir'])

    def test_openhttpservers_reports_friendly_usage_when_eaddrinuse(self):
        supervisord = DummySupervisor()
        instance = self._makeOne()

        def raise_eaddrinuse(supervisord):
            raise socket.error(errno.EADDRINUSE)
        instance.make_http_servers = raise_eaddrinuse

        recorder = []
        def record_usage(message):
            recorder.append(message)
        instance.usage = record_usage

        instance.openhttpservers(supervisord)
        self.assertEqual(len(recorder), 1)
        expected = 'Another program is already listening'
        self.assertTrue(recorder[0].startswith(expected))

    def test_openhttpservers_reports_socket_error_with_errno(self):
        supervisord = DummySupervisor()
        instance = self._makeOne()

        def make_http_servers(supervisord):
            raise socket.error(errno.EPERM)
        instance.make_http_servers = make_http_servers

        recorder = []
        def record_usage(message):
            recorder.append(message)
        instance.usage = record_usage

        instance.openhttpservers(supervisord)
        self.assertEqual(len(recorder), 1)
        expected = ('Cannot open an HTTP server: socket.error '
                    'reported errno.EPERM (%d)' % errno.EPERM)
        self.assertEqual(recorder[0], expected)

    def test_openhttpservers_reports_other_socket_errors(self):
        supervisord = DummySupervisor()
        instance = self._makeOne()

        def make_http_servers(supervisord):
            raise socket.error('uh oh')
        instance.make_http_servers = make_http_servers

        recorder = []
        def record_usage(message):
            recorder.append(message)
        instance.usage = record_usage

        instance.openhttpservers(supervisord)
        self.assertEqual(len(recorder), 1)
        expected = ('Cannot open an HTTP server: socket.error '
                    'reported uh oh')
        self.assertEqual(recorder[0], expected)

    def test_openhttpservers_reports_value_errors(self):
        supervisord = DummySupervisor()
        instance = self._makeOne()

        def make_http_servers(supervisord):
            raise ValueError('not prefixed with help')
        instance.make_http_servers = make_http_servers

        recorder = []
        def record_usage(message):
            recorder.append(message)
        instance.usage = record_usage

        instance.openhttpservers(supervisord)
        self.assertEqual(len(recorder), 1)
        expected = 'not prefixed with help'
        self.assertEqual(recorder[0], expected)

    def test_openhttpservers_does_not_catch_other_exception_types(self):
        supervisord = DummySupervisor()
        instance = self._makeOne()

        def make_http_servers(supervisord):
            raise OverflowError
        instance.make_http_servers = make_http_servers

        # this scenario probably means a bug in supervisor.  we dump
        # all the gory details on the poor user for troubleshooting
        self.assertRaises(OverflowError,
                          instance.openhttpservers, supervisord)


class TestProcessConfig(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import ProcessConfig
        return ProcessConfig

    def _makeOne(self, *arg, **kw):
        defaults = {}
        for name in ('name', 'command', 'directory', 'umask',
                     'priority', 'autostart', 'autorestart',
                     'startsecs', 'startretries', 'uid',
                     'stdout_logfile', 'stdout_capture_maxbytes',
                     'stdout_events_enabled',
                     'stdout_logfile_backups', 'stdout_logfile_maxbytes',
                     'stderr_logfile', 'stderr_capture_maxbytes',
                     'stderr_events_enabled',
                     'stderr_logfile_backups', 'stderr_logfile_maxbytes',
                     'stopsignal', 'stopwaitsecs', 'stopasgroup', 'killasgroup', 'exitcodes',
                     'redirect_stderr', 'environment'):
            defaults[name] = name
        defaults.update(kw)
        return self._getTargetClass()(*arg, **defaults)

    def test_create_autochildlogs(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        from supervisor.datatypes import Automatic
        instance.stdout_logfile = Automatic
        instance.stderr_logfile = Automatic
        instance.create_autochildlogs()
        self.assertEqual(instance.stdout_logfile, options.tempfile_name)
        self.assertEqual(instance.stderr_logfile, options.tempfile_name)

    def test_make_process(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        process = instance.make_process()
        from supervisor.process import Subprocess
        self.assertEqual(process.__class__, Subprocess)
        self.assertEqual(process.group, None)

    def test_make_process_with_group(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        process = instance.make_process('abc')
        from supervisor.process import Subprocess
        self.assertEqual(process.__class__, Subprocess)
        self.assertEqual(process.group, 'abc')

    def test_make_dispatchers_stderr_not_redirected(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        instance.redirect_stderr = False
        process1 = DummyProcess(instance)
        dispatchers, pipes = instance.make_dispatchers(process1)
        self.assertEqual(dispatchers[5].channel, 'stdout')
        from supervisor.events import ProcessCommunicationStdoutEvent
        self.assertEqual(dispatchers[5].event_type,
                         ProcessCommunicationStdoutEvent)
        self.assertEqual(pipes['stdout'], 5)
        self.assertEqual(dispatchers[7].channel, 'stderr')
        from supervisor.events import ProcessCommunicationStderrEvent
        self.assertEqual(dispatchers[7].event_type,
                         ProcessCommunicationStderrEvent)
        self.assertEqual(pipes['stderr'], 7)

    def test_make_dispatchers_stderr_redirected(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        process1 = DummyProcess(instance)
        dispatchers, pipes = instance.make_dispatchers(process1)
        self.assertEqual(dispatchers[5].channel, 'stdout')
        self.assertEqual(pipes['stdout'], 5)
        self.assertEqual(pipes['stderr'], None)

class FastCGIProcessConfigTest(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import FastCGIProcessConfig
        return FastCGIProcessConfig

    def _makeOne(self, *arg, **kw):
        defaults = {}
        for name in ('name', 'command', 'directory', 'umask',
                     'priority', 'autostart', 'autorestart',
                     'startsecs', 'startretries', 'uid',
                     'stdout_logfile', 'stdout_capture_maxbytes',
                     'stdout_events_enabled',
                     'stdout_logfile_backups', 'stdout_logfile_maxbytes',
                     'stderr_logfile', 'stderr_capture_maxbytes',
                     'stderr_events_enabled',
                     'stderr_logfile_backups', 'stderr_logfile_maxbytes',
                     'stopsignal', 'stopwaitsecs', 'stopasgroup', 'killasgroup', 'exitcodes',
                     'redirect_stderr', 'environment'):
            defaults[name] = name
        defaults.update(kw)
        return self._getTargetClass()(*arg, **defaults)

    def test_make_process(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        self.assertRaises(NotImplementedError, instance.make_process)

    def test_make_process_with_group(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        process = instance.make_process('abc')
        from supervisor.process import FastCGISubprocess
        self.assertEqual(process.__class__, FastCGISubprocess)
        self.assertEqual(process.group, 'abc')

    def test_make_dispatchers(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        instance.redirect_stderr = False
        process1 = DummyProcess(instance)
        dispatchers, pipes = instance.make_dispatchers(process1)
        self.assertEqual(dispatchers[4].channel, 'stdin')
        self.assertEqual(dispatchers[4].closed, True)
        self.assertEqual(dispatchers[5].channel, 'stdout')
        from supervisor.events import ProcessCommunicationStdoutEvent
        self.assertEqual(dispatchers[5].event_type,
                         ProcessCommunicationStdoutEvent)
        self.assertEqual(pipes['stdout'], 5)
        self.assertEqual(dispatchers[7].channel, 'stderr')
        from supervisor.events import ProcessCommunicationStderrEvent
        self.assertEqual(dispatchers[7].event_type,
                         ProcessCommunicationStderrEvent)
        self.assertEqual(pipes['stderr'], 7)

class ProcessGroupConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import ProcessGroupConfig
        return ProcessGroupConfig

    def _makeOne(self, options, name, priority, pconfigs):
        return self._getTargetClass()(options, name, priority, pconfigs)

    def test_ctor(self):
        options = DummyOptions()
        instance = self._makeOne(options, 'whatever', 999, [])
        self.assertEqual(instance.options, options)
        self.assertEqual(instance.name, 'whatever')
        self.assertEqual(instance.priority, 999)
        self.assertEqual(instance.process_configs, [])

    def test_after_setuid(self):
        options = DummyOptions()
        pconfigs = [DummyPConfig(options, 'process1', '/bin/process1')]
        instance = self._makeOne(options, 'whatever', 999, pconfigs)
        instance.after_setuid()
        self.assertEqual(pconfigs[0].autochildlogs_created, True)

    def test_make_group(self):
        options = DummyOptions()
        pconfigs = [DummyPConfig(options, 'process1', '/bin/process1')]
        instance = self._makeOne(options, 'whatever', 999, pconfigs)
        group = instance.make_group()
        from supervisor.process import ProcessGroup
        self.assertEqual(group.__class__, ProcessGroup)

class FastCGIGroupConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import FastCGIGroupConfig
        return FastCGIGroupConfig

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_ctor(self):
        options = DummyOptions()
        sock_config = DummySocketConfig(6)
        instance = self._makeOne(options, 'whatever', 999, [], sock_config)
        self.assertEqual(instance.options, options)
        self.assertEqual(instance.name, 'whatever')
        self.assertEqual(instance.priority, 999)
        self.assertEqual(instance.process_configs, [])
        self.assertEqual(instance.socket_config, sock_config)

    def test_same_sockets_are_equal(self):
        options = DummyOptions()
        sock_config1 = DummySocketConfig(6)
        instance1 = self._makeOne(options, 'whatever', 999, [], sock_config1)

        sock_config2 = DummySocketConfig(6)
        instance2 = self._makeOne(options, 'whatever', 999, [], sock_config2)

        self.assertTrue(instance1 == instance2)
        self.assertFalse(instance1 != instance2)

    def test_diff_sockets_are_not_equal(self):
        options = DummyOptions()
        sock_config1 = DummySocketConfig(6)
        instance1 = self._makeOne(options, 'whatever', 999, [], sock_config1)

        sock_config2 = DummySocketConfig(7)
        instance2 = self._makeOne(options, 'whatever', 999, [], sock_config2)

        self.assertTrue(instance1 != instance2)
        self.assertFalse(instance1 == instance2)

class SignalReceiverTests(unittest.TestCase):
    def test_returns_None_initially(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        self.assertEquals(sr.get_signal(), None)

    def test_returns_signals_in_order_received(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        sr.receive(signal.SIGTERM, 'frame')
        sr.receive(signal.SIGCHLD, 'frame')
        self.assertEquals(sr.get_signal(), signal.SIGTERM)
        self.assertEquals(sr.get_signal(), signal.SIGCHLD)
        self.assertEquals(sr.get_signal(), None)

    def test_does_not_queue_duplicate_signals(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        sr.receive(signal.SIGTERM, 'frame')
        sr.receive(signal.SIGTERM, 'frame')
        self.assertEquals(sr.get_signal(), signal.SIGTERM)
        self.assertEquals(sr.get_signal(), None)

    def test_queues_again_after_being_emptied(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        sr.receive(signal.SIGTERM, 'frame')
        self.assertEquals(sr.get_signal(), signal.SIGTERM)
        self.assertEquals(sr.get_signal(), None)
        sr.receive(signal.SIGCHLD, 'frame')
        self.assertEquals(sr.get_signal(), signal.SIGCHLD)
        self.assertEquals(sr.get_signal(), None)

class UtilFunctionsTests(unittest.TestCase):
    def test_make_namespec(self):
        from supervisor.options import make_namespec
        self.assertEquals(make_namespec('group', 'process'), 'group:process')
        self.assertEquals(make_namespec('process', 'process'), 'process')

    def test_split_namespec(self):
        from supervisor.options import split_namespec
        s = split_namespec
        self.assertEquals(s('process:group'), ('process', 'group'))
        self.assertEquals(s('process'), ('process', 'process'))
        self.assertEquals(s('group:'), ('group', None))
        self.assertEquals(s('group:*'), ('group', None))

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

