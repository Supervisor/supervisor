"""Test suite for supervisor.options"""

import logging
import os
import sys
import tempfile
import socket
import unittest
import signal
import shutil
import errno

from supervisor.compat import StringIO
from supervisor.compat import as_bytes

from supervisor.tests.base import Mock, sentinel, patch
from supervisor.loggers import LevelsByName

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyLogger
from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummySocketConfig
from supervisor.tests.base import lstrip


class DummyExitException(Exception):
    def __init__(self, exitcode):
        self.exitcode = exitcode

def dummy_exit():
    """Dummy out exit so we don't actually exit"""
    def dummy_exit(_exitcode=0):
        raise DummyExitException(exitcode=_exitcode)
    return dummy_exit

def _getTempFile(name):
    prefix = 'supervisor.{0}.'.format(name)
    return tempfile.NamedTemporaryFile(prefix=prefix)

logger = logging.getLogger(__name__)


class OptionTests(unittest.TestCase):

    def _getTargetClass(self):
        from supervisor.options import Options
        return Options

    def _makeOptions(self, read_error=False):
        Options = self._getTargetClass()
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

    def test_add_flag_not_None_handler_not_None(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(ValueError, inst.add, flag=True, handler=True)

    def test_add_flag_not_None_long_false_short_false(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(
            ValueError,
            inst.add,
            flag=True,
            long=False,
            short=False,
            )

    def test_add_flag_not_None_short_endswith_colon(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(
            ValueError,
            inst.add,
            flag=True,
            long=False,
            short=":",
            )

    def test_add_flag_not_None_long_endswith_equal(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(
            ValueError,
            inst.add,
            flag=True,
            long='=',
            short=False,
            )

    def test_add_inconsistent_short_long_options(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(
            ValueError,
            inst.add,
            long='=',
            short='abc',
            )

    def test_add_short_option_startswith_dash(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(
            ValueError,
            inst.add,
            long=False,
            short='-abc',
            )

    def test_add_short_option_too_long(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(
            ValueError,
            inst.add,
            long=False,
            short='abc',
            )

    def test_add_duplicate_short_option_key(self):
        cls = self._getTargetClass()
        inst = cls()
        inst.options_map = {'-a':True}
        self.assertRaises(
            ValueError,
            inst.add,
            long=False,
            short='a',
            )

    def test_add_long_option_startswith_dash(self):
        cls = self._getTargetClass()
        inst = cls()
        self.assertRaises(
            ValueError,
            inst.add,
            long='-abc',
            short=False,
            )

    def test_add_duplicate_long_option_key(self):
        cls = self._getTargetClass()
        inst = cls()
        inst.options_map = {'--abc':True}
        self.assertRaises(
            ValueError,
            inst.add,
            long='abc',
            short=False,
            )

    def test_searchpaths(self):
        options = self._makeOptions()
        self.assertEqual(len(options.searchpaths), 5)
        self.assertTrue('supervisord.conf' in options.searchpaths)
        self.assertTrue('etc/supervisord.conf' in options.searchpaths)
        self.assertTrue('/etc/supervisord.conf' in options.searchpaths)

    def test_options_and_args_order(self):
        # Only config file exists
        options = self._makeOptions()
        options.realize([])
        self.assertEqual(options.anoption, 'default')
        self.assertEqual(options.other, 41)

        # Env should trump config
        options = self._makeOptions()
        os.environ['OTHER'] = '42'
        options.realize([])
        self.assertEqual(options.other, 42)

        # Opt should trump both env (still set) and config
        options = self._makeOptions()
        options.realize(['-p', '43'])
        self.assertEqual(options.other, 43)
        del os.environ['OTHER']

    def test_config_reload(self):
        options = self._makeOptions()
        options.realize([])
        self.assertEqual(options.other, 41)
        options.master['other'] = 42
        options.process_config()
        self.assertEqual(options.other, 42)

    def test_config_reload_do_usage_false(self):
        options = self._makeOptions(read_error='error')
        self.assertRaises(ValueError, options.process_config,
                          False)

    def test_config_reload_do_usage_true(self):
        options = self._makeOptions(read_error='error')
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
        self.assertEqual(options.foo, 'bar')
        self.assertEqual(options.attr_priorities['foo'], 0)
        options._set('foo', 'baz', 1)
        self.assertEqual(options.foo, 'baz')
        self.assertEqual(options.attr_priorities['foo'], 1)
        options._set('foo', 'gazonk', 0)
        self.assertEqual(options.foo, 'baz')
        self.assertEqual(options.attr_priorities['foo'], 1)
        options._set('foo', 'gazonk', 1)
        self.assertEqual(options.foo, 'gazonk')

    def test_missing_default_config(self):
        options = self._makeOptions()
        options.searchpaths = []
        options.exit = dummy_exit()
        options.stderr = StringIO()
        try:
            options.default_configfile()
        except DummyExitException as e:
            self.assertEqual(e.exitcode, 2)
        else:
            self.fail("expected exception")
        msg = "Error: No config file found at default paths"
        self.assertTrue(options.stderr.getvalue().startswith(msg))

    def test_default_config(self):
        options = self._makeOptions()
        tempf = tempfile.NamedTemporaryFile()
        options.searchpaths = [tempf.name]
        config = options.default_configfile()
        self.assertEqual(config, tempf.name)
        tempf.close()

    def test_help(self):
        options = self._makeOptions()
        options.exit = dummy_exit()
        options.stdout = StringIO()
        options.progname = 'test_help'
        options.doc = 'A sample docstring for %s'
        self.assertRaises(DummyExitException,
            options.help, 'Argument ignored?')
        msg = 'A sample docstring for test_help\n'
        self.assertEqual(options.stdout.getvalue(), msg)

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

        instance.exit = dummy_exit()

        instance.realize(args=['-s', 'http://localhost:9001', '-u', 'chris',
                               '-p', '123'])

        self.assertEqual(instance.interactive, 1)
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

    @patch.dict('os.environ', { 'HOME': tempfile.gettempdir(),
                                'USER': 'johndoe',
                                'SERVER_PORT': '9210',
                                'CLIENT_USER': 'someuser',
                                'CLIENT_PASS': 'passwordhere',
                                'CLIENT_PROMPT': 'xsupervisor',
                                'CLIENT_HIST_EXT': '.hist',
                                })
    def test_options_with_environment_expansions(self):
        s = lstrip("""[supervisorctl]
        serverurl=http://localhost:%(ENV_SERVER_PORT)s
        username=%(ENV_CLIENT_USER)s
        password=%(ENV_CLIENT_PASS)s
        prompt=%(ENV_CLIENT_PROMPT)s
        history_file=/path/to/histdir/.supervisorctl%(ENV_CLIENT_HIST_EXT)s
        """)

        fp = StringIO(s)
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize(args=[])
        self.assertEqual(instance.interactive, True)
        options = instance.configroot.supervisorctl
        self.assertEqual(options.prompt, 'xsupervisor')
        self.assertEqual(options.serverurl, 'http://localhost:9210')
        self.assertEqual(options.username, 'someuser')
        self.assertEqual(options.password, 'passwordhere')
        self.assertEqual(options.history_file, '/path/to/histdir/.supervisorctl.hist')

    def test_read_config_not_found(self):
        instance = self._makeOne()
        def dummy_exists(fn):
            return False
        instance.exists = dummy_exists

        try:
            instance.read_config('filename')
        except ValueError as e:
            self.assertTrue("could not find config file" in str(e))
        else:
            self.fail("expected exception")

    def test_read_config_unreadable(self):
        instance = self._makeOne()
        def dummy_exists(fn):
            return True
        instance.exists = dummy_exists
        def dummy_open(fn, mode):
            raise IOError(errno.EACCES, 'Permission denied: %s' % fn)
        instance.open = dummy_open

        try:
            instance.read_config('filename')
        except ValueError as e:
            self.assertTrue("could not read config file" in str(e))
        else:
            self.fail("expected exception")

    def test_options_unixsocket_cli(self):
        fp = StringIO('[supervisorctl]')
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize(args=['--serverurl', 'unix:///dev/null'])
        self.assertEqual(instance.serverurl, 'unix:///dev/null')

    def test_options_unixsocket_configfile(self):
        s = lstrip("""[supervisorctl]
        serverurl=unix:///dev/null
        """)
        fp = StringIO(s)
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize(args=[])
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

        [program:cat5]
        priority=5
        process_name = foo_%%(process_num)02d
        numprocs = 2
        numprocs_start = 1
        command = /bin/cat
        directory = /some/path/foo_%%(process_num)02d
        """ % {'tempdir':tempfile.gettempdir()})

        from supervisor import datatypes

        fp = StringIO(s)
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize(args=[])
        options = instance.configroot.supervisord
        self.assertEqual(options.directory, tempfile.gettempdir())
        self.assertEqual(options.umask, 18) # 022 in Py2, 0o22 in Py3
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
        self.assertEqual(len(options.process_group_configs), 5)
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
        self.assertEqual(proc1.umask, 2)
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
        self.assertEqual(proc4_a.directory, None)

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
        self.assertEqual(proc4_b.directory, None)

        cat5 = options.process_group_configs[4]
        self.assertEqual(cat5.name, 'cat5')
        self.assertEqual(cat5.priority, 5)
        self.assertEqual(len(cat5.process_configs), 2)

        proc5_a = cat5.process_configs[0]
        self.assertEqual(proc5_a.name, 'foo_01')
        self.assertEqual(proc5_a.directory, '/some/path/foo_01')

        proc5_b = cat5.process_configs[1]
        self.assertEqual(proc5_b.name, 'foo_02')
        self.assertEqual(proc5_b.directory, '/some/path/foo_02')

        here = os.path.abspath(os.getcwd())
        self.assertEqual(instance.uid, 0)
        self.assertEqual(instance.gid, 0)
        self.assertEqual(instance.directory, tempfile.gettempdir())
        self.assertEqual(instance.umask, 18) # 022 in Py2, 0o22 in Py3
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

        instance.exit = dummy_exit()

        # Making sure we capture stdout and stderr
        instance.stderr = StringIO()

        try:
            instance.realize(args=[])
        except DummyExitException as e:
            # Caught expected exception
            import traceback
            self.assertEqual(
                e.exitcode, 2,
                "Wrong exitcode for: %s" % traceback.format_exc()
                )
        else:
            self.fail("Did not get a DummyExitException.")

    def test_reload(self):
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

        text = lstrip("""\
        [supervisord]
        user=root

        [program:cat]
        command = /bin/cat
        """)
        instance.configfile = StringIO(text)
        instance.realize(args=[])
        self.assertFalse(old_warning in instance.parse_warnings)

    def test_read_config_not_found(self):
        instance = self._makeOne()
        def dummy_exists(fn):
            return False
        instance.exists = dummy_exists

        try:
            instance.read_config('filename')
        except ValueError as e:
            self.assertTrue("could not find config file" in str(e))
        else:
            self.fail("expected exception")

    def test_read_config_unreadable(self):
        instance = self._makeOne()
        def dummy_exists(fn):
            return True
        instance.exists = dummy_exists
        def dummy_open(fn, mode):
            raise IOError(errno.EACCES, 'Permission denied: %s' % fn)
        instance.open = dummy_open

        try:
            instance.read_config('filename')
        except ValueError as e:
            self.assertTrue("could not read config file" in str(e))
        else:
            self.fail("expected exception")

    def test_readFile_failed(self):
        from supervisor.options import readFile
        try:
            readFile('/notthere', 0, 10)
        except ValueError as inst:
            self.assertEqual(inst.args[0], 'FAILED')
        else:
            raise AssertionError("Didn't raise")

    def test_include_with_no_matching_files_logs_warning(self):
        instance = self._makeOne()
        text = lstrip("""\
        [supervisord]
        user=root

        [include]
        files=nonexistant/*
        """)
        instance.configfile = StringIO(text)
        instance.realize(args=[])
        self.assertEqual(instance.parse_warnings,
                         ['No file matches via include "./nonexistant/*"'])

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

    def test_options_afunix(self):
        instance = self._makeOne()
        text = lstrip("""\
        [unix_http_server]
        file=/tmp/supvtest.sock
        username=johndoe
        password=passwordhere

        [supervisord]
        ; ...
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance.configfile = StringIO(text)
        instance.read_config(StringIO(text))
        instance.realize(args=[])
        # unix_http_server
        options = instance.configroot.supervisord
        self.assertEqual(options.server_configs[0]['family'], socket.AF_UNIX)
        self.assertEqual(options.server_configs[0]['file'], '/tmp/supvtest.sock')
        self.assertEqual(options.server_configs[0]['chmod'], 448) # defaults
        self.assertEqual(options.server_configs[0]['chown'], (-1,-1)) # defaults

    def test_options_afunix_chxxx_values_valid(self):
        instance = self._makeOne()
        text = lstrip("""\
        [unix_http_server]
        file=/tmp/supvtest.sock
        username=johndoe
        password=passwordhere
        chmod=0755

        [supervisord]
        ; ...
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance.configfile = StringIO(text)
        instance.read_config(StringIO(text))
        instance.realize(args=[])
        # unix_http_server
        options = instance.configroot.supervisord
        self.assertEqual(options.server_configs[0]['family'], socket.AF_UNIX)
        self.assertEqual(options.server_configs[0]['file'], '/tmp/supvtest.sock')
        self.assertEqual(options.server_configs[0]['chmod'], 493)

    def test_cleanup_afunix_unlink(self):
        fn = tempfile.mktemp()
        with open(fn, 'w') as f:
            f.write('foo')
        instance = self._makeOne()
        class Server:
            pass
        instance.httpservers = [({'family':socket.AF_UNIX, 'file':fn},
                                 Server())]
        instance.pidfile = ''
        instance.cleanup()
        self.assertFalse(os.path.exists(fn))

    def test_cleanup_afunix_nounlink(self):
        fn = tempfile.mktemp()
        try:
            with open(fn, 'w') as f:
                f.write('foo')
            instance = self._makeOne()
            class Server:
                pass
            instance.httpservers = [({'family':socket.AF_UNIX, 'file':fn},
                                     Server())]
            instance.pidfile = ''
            instance.unlink_socketfiles = False
            instance.cleanup()
            self.assertTrue(os.path.exists(fn))
        finally:
            try:
                os.unlink(fn)
            except OSError:
                pass

    def test_cleanup_afunix_ignores_oserror_enoent(self):
        notfound = os.path.join(os.path.dirname(__file__), 'notfound')
        socketname = tempfile.mktemp()
        try:
            with open(socketname, 'w') as f:
                f.write('foo')
            instance = self._makeOne()
            class Server:
                pass
            instance.httpservers = [
                ({'family': socket.AF_UNIX, 'file': notfound}, Server()),
                ({'family': socket.AF_UNIX, 'file': socketname}, Server()),
            ]
            instance.pidfile = ''
            instance.cleanup()
            self.assertFalse(os.path.exists(socketname))
        finally:
            try:
                os.unlink(socketname)
            except OSError:
                pass

    def test_cleanup_removes_pidfile(self):
        pidfile = tempfile.mktemp()
        try:
            with open(pidfile, 'w') as f:
                f.write('2')
            instance = self._makeOne()
            instance.pidfile = pidfile
            instance.cleanup()
            self.assertFalse(os.path.exists(pidfile))
        finally:
            try:
                os.unlink(pidfile)
            except OSError:
                pass

    def test_cleanup_pidfile_ignores_oserror_enoent(self):
        notfound = os.path.join(os.path.dirname(__file__), 'notfound')
        instance = self._makeOne()
        instance.pidfile = notfound
        instance.cleanup() # shouldn't raise

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
            self.assertTrue(os.path.exists(fn))
            with open(fn, 'r') as f:
                pid = int(f.read().strip())
            self.assertEqual(pid, os.getpid())
            msg = instance.logger.data[0]
            self.assertTrue(msg.startswith('supervisord started with pid'))
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
        self.assertTrue(msg.startswith('could not write pidfile'))

    def test_close_fd(self):
        instance = self._makeOne()
        innie, outie = os.pipe()
        os.read(innie, 0) # we can read it while its open
        os.write(outie, as_bytes('foo')) # we can write to it while its open
        instance.close_fd(innie)
        self.assertRaises(OSError, os.read, innie, 0)
        instance.close_fd(outie)
        self.assertRaises(OSError, os.write, outie, as_bytes('foo'))

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

    def test_processes_from_section_process_num_expansion(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/foo --num=%(process_num)d
        directory = /tmp/foo_%(process_num)d
        stderr_logfile = /tmp/foo_%(process_num)d_stderr
        stdout_logfile = /tmp/foo_%(process_num)d_stdout
        environment = NUM=%(process_num)d
        process_name = foo_%(process_num)d
        numprocs = 2
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        pconfigs = instance.processes_from_section(config, 'program:foo', 'bar')
        self.assertEqual(len(pconfigs), 2)
        for num in (0, 1):
            self.assertEqual(pconfigs[num].name, 'foo_%d' % num)
            self.assertEqual(pconfigs[num].command, "/bin/foo --num=%d" % num)
            self.assertEqual(pconfigs[num].directory, '/tmp/foo_%d' % num)
            self.assertEqual(pconfigs[num].stderr_logfile,
                '/tmp/foo_%d_stderr' % num)
            self.assertEqual(pconfigs[num].stdout_logfile,
                '/tmp/foo_%d_stdout' % num)
            self.assertEqual(pconfigs[num].environment, {'NUM': '%d' % num})

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

    @patch.dict('os.environ', { 'HOME': tempfile.gettempdir(),
                                'USER': 'johndoe',
                                'HTSRV_PORT': '9210',
                                'HTSRV_USER': 'someuser',
                                'HTSRV_PASS': 'passwordhere',
                                'SUPD_LOGFILE_MAXBYTES': '51MB',
                                'SUPD_LOGFILE_BACKUPS': '10',
                                'SUPD_LOGLEVEL': 'info',
                                'SUPD_NODAEMON': 'false',
                                'SUPD_MINFDS': '1024',
                                'SUPD_MINPROCS': '200',
                                'SUPD_UMASK': '002',
                                'SUPD_NOCLEANUP': 'true',
                                'SUPD_STRIP_ANSI': 'false',
                                'CAT1_COMMAND': '/bin/customcat',
                                'CAT1_COMMAND_LOGDIR': '/path/to/logs',
                                'CAT1_PRIORITY': '3',
                                'CAT1_AUTOSTART': 'true',
                                'CAT1_USER': 'root', # resolved to uid
                                'CAT1_STDOUT_LOGFILE': '/tmp/cat.log',
                                'CAT1_STDOUT_LOGFILE_MAXBYTES': '78KB',
                                'CAT1_STDOUT_LOGFILE_BACKUPS': '2',
                                'CAT1_STOPSIGNAL': 'KILL',
                                'CAT1_STOPWAIT': '5',
                                'CAT1_STARTWAIT': '5',
                                'CAT1_STARTRETRIES': '10',
                                'CAT1_DIR': '/tmp',
                                'CAT1_UMASK': '002',
                                })
    def test_options_with_environment_expansions(self):
        instance = self._makeOne()
        text = lstrip("""\
        [inet_http_server]
        port=*:%(ENV_HTSRV_PORT)s
        username=%(ENV_HTSRV_USER)s
        password=%(ENV_HTSRV_PASS)s

        [supervisord]
        logfile = %(ENV_HOME)s/supervisord.log
        logfile_maxbytes = %(ENV_SUPD_LOGFILE_MAXBYTES)s
        logfile_backups = %(ENV_SUPD_LOGFILE_BACKUPS)s
        loglevel = %(ENV_SUPD_LOGLEVEL)s
        nodaemon = %(ENV_SUPD_NODAEMON)s
        minfds = %(ENV_SUPD_MINFDS)s
        minprocs = %(ENV_SUPD_MINPROCS)s
        umask = %(ENV_SUPD_UMASK)s
        identifier = supervisor_%(ENV_USER)s
        nocleanup = %(ENV_SUPD_NOCLEANUP)s
        childlogdir = %(ENV_HOME)s
        strip_ansi = %(ENV_SUPD_STRIP_ANSI)s
        environment = FAKE_ENV_VAR=/some/path

        [program:cat1]
        command=%(ENV_CAT1_COMMAND)s --logdir=%(ENV_CAT1_COMMAND_LOGDIR)s
        priority=%(ENV_CAT1_PRIORITY)s
        autostart=%(ENV_CAT1_AUTOSTART)s
        user=%(ENV_CAT1_USER)s
        stdout_logfile=%(ENV_CAT1_STDOUT_LOGFILE)s
        stdout_logfile_maxbytes = %(ENV_CAT1_STDOUT_LOGFILE_MAXBYTES)s
        stdout_logfile_backups = %(ENV_CAT1_STDOUT_LOGFILE_BACKUPS)s
        stopsignal=%(ENV_CAT1_STOPSIGNAL)s
        stopwaitsecs=%(ENV_CAT1_STOPWAIT)s
        startsecs=%(ENV_CAT1_STARTWAIT)s
        startretries=%(ENV_CAT1_STARTRETRIES)s
        directory=%(ENV_CAT1_DIR)s
        umask=%(ENV_CAT1_UMASK)s

        """)
        from supervisor import datatypes
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance.configfile = StringIO(text)
        instance.read_config(StringIO(text))
        instance.realize(args=[])
        # supervisord
        self.assertEqual(instance.logfile,
                         '%(HOME)s/supervisord.log' % os.environ)
        self.assertEqual(instance.identifier,
                         'supervisor_%(USER)s' % os.environ)
        self.assertEqual(instance.logfile_maxbytes, 53477376)
        self.assertEqual(instance.logfile_backups, 10)
        self.assertEqual(instance.loglevel, LevelsByName.INFO)
        self.assertEqual(instance.nodaemon, False)
        self.assertEqual(instance.minfds, 1024)
        self.assertEqual(instance.minprocs, 200)
        self.assertEqual(instance.nocleanup, True)
        self.assertEqual(instance.childlogdir, os.environ['HOME'])
        self.assertEqual(instance.strip_ansi, False)
        # inet_http_server
        options = instance.configroot.supervisord
        self.assertEqual(options.server_configs[0]['family'], socket.AF_INET)
        self.assertEqual(options.server_configs[0]['host'], '')
        self.assertEqual(options.server_configs[0]['port'], 9210)
        self.assertEqual(options.server_configs[0]['username'], 'someuser')
        self.assertEqual(options.server_configs[0]['password'], 'passwordhere')
        # cat1
        cat1 = options.process_group_configs[0]
        self.assertEqual(cat1.name, 'cat1')
        self.assertEqual(cat1.priority, 3)
        self.assertEqual(len(cat1.process_configs), 1)
        proc1 = cat1.process_configs[0]
        self.assertEqual(proc1.name, 'cat1')
        self.assertEqual(proc1.command,
                         '/bin/customcat --logdir=/path/to/logs')
        self.assertEqual(proc1.priority, 3)
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
                         datatypes.byte_size('78KB'))
        self.assertEqual(proc1.stdout_logfile_backups, 2)
        self.assertEqual(proc1.exitcodes, [0,2])
        self.assertEqual(proc1.directory, '/tmp')
        self.assertEqual(proc1.umask, 2)
        self.assertEqual(proc1.environment, dict(FAKE_ENV_VAR='/some/path'))

    def test_processes_from_section_bad_program_name_spaces(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:spaces are bad]
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        self.assertRaises(ValueError, instance.processes_from_section,
                          config, 'program:spaces are bad', None)

    def test_processes_from_section_bad_program_name_colons(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:colons:are:bad]
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        self.assertRaises(ValueError, instance.processes_from_section,
                          config, 'program:colons:are:bad', None)

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
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        try:
            instance.processes_from_section(config, 'program:foo', None)
            self.fail('nothing raised')
        except ValueError as exc:
            self.assertTrue(exc.args[0].startswith(
                'program section program:foo does not specify a command'))

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

    def test_processes_from_section_bad_chars_in_process_name(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        process_name = colons:are:bad
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

    def test_processes_from_section_unexpected_end_of_key_value_pairs(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        command = /bin/cat
        environment = KEY1=val1,KEY2=val2,KEY3
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        try:
            instance.processes_from_section(config, 'program:foo', None)
        except ValueError as e:
            self.assertTrue(
                "Unexpected end of key/value pairs in value "
                "'KEY1=val1,KEY2=val2,KEY3' in section 'program:foo'"
                in str(e))
        else:
            self.fail('instance.processes_from_section should '
                      'raise a ValueError')

    def test_processes_from_section_shows_conf_filename_on_valueerror(self):
        instance = self._makeOne()
        text = lstrip("""\
        [program:foo]
        ;no command
        """)
        f = tempfile.NamedTemporaryFile(mode="w+")
        try:
            f.write(text)
            f.flush()
            from supervisor.options import UnhosedConfigParser
            config = UnhosedConfigParser()
            config.read(f.name)
            instance.processes_from_section(config, 'program:foo', None)
        except ValueError as e:
            self.assertEqual(e.args[0],
                "program section program:foo does not specify a command "
                "in section 'program:foo' (file: %s)" % f.name)
        else:
            self.fail('nothing raised')
        finally:
            f.close()

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

    @patch.dict('os.environ', { 'HOME': tempfile.gettempdir(),
                                'USER': 'johndoe',
                                'EL1_PROCNAME': 'myeventlistener',
                                'EL1_COMMAND': '/bin/dog',
                                'EL1_NUMPROCS': '2',
                                'EL1_PRIORITY': '1',
                                })
    def test_event_listener_pools_from_parser_with_environment_expansions(self):
        text = lstrip("""\
        [eventlistener:dog]
        events=PROCESS_COMMUNICATION
        process_name = %(ENV_EL1_PROCNAME)s_%(program_name)s_%(process_num)s
        command = %(ENV_EL1_COMMAND)s
        numprocs = %(ENV_EL1_NUMPROCS)s
        priority = %(ENV_EL1_PRIORITY)s

        [eventlistener:cat]
        events=PROCESS_COMMUNICATION
        process_name = %(program_name)s_%(process_num)s
        command = /bin/cat
        numprocs = 3

        """)
        from supervisor.options import UnhosedConfigParser
        from supervisor.dispatchers import default_handler
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        gconfigs = instance.process_groups_from_parser(config)
        self.assertEqual(len(gconfigs), 2)

        gconfig0 = gconfigs[0]
        self.assertEqual(gconfig0.name, 'cat')
        self.assertEqual(gconfig0.priority, -1)
        self.assertEqual(gconfig0.result_handler, default_handler)
        self.assertEqual(len(gconfig0.process_configs), 3)

        gconfig1 = gconfigs[1]
        self.assertEqual(gconfig1.name, 'dog')
        self.assertEqual(gconfig1.priority, 1)
        self.assertEqual(gconfig1.result_handler, default_handler)
        self.assertEqual(len(gconfig1.process_configs), 2)
        dog0 = gconfig1.process_configs[0]
        self.assertEqual(dog0.name, 'myeventlistener_dog_0')
        self.assertEqual(dog0.command, '/bin/dog')
        self.assertEqual(dog0.priority, 1)
        dog1 = gconfig1.process_configs[1]
        self.assertEqual(dog1.name, 'myeventlistener_dog_1')
        self.assertEqual(dog1.command, '/bin/dog')
        self.assertEqual(dog1.priority, 1)

    def test_event_listener_pool_disallows_redirect_stderr(self):
        text = lstrip("""\
        [eventlistener:dog]
        events=PROCESS_COMMUNICATION
        command = /bin/dog
        redirect_stderr = True
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        try:
            instance.process_groups_from_parser(config)
            self.fail('nothing raised')
        except ValueError as exc:
            self.assertEqual(exc.args[0], '[eventlistener:dog] section sets '
                'redirect_stderr=true but this is not allowed because it '
                'will interfere with the eventlistener protocol')

    def test_event_listener_pool_with_event_result_handler(self):
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

    def test_event_listener_pool_result_handler_unimportable(self):
        text = lstrip("""\
        [eventlistener:cat]
        events=PROCESS_COMMUNICATION
        command = /bin/cat
        result_handler = supervisor.tests.base:nonexistant
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        try:
            instance.process_groups_from_parser(config)
            self.fail('nothing raised')
        except ValueError as exc:
            self.assertEqual(exc.args[0],
                'supervisor.tests.base:nonexistant cannot be '
                'resolved within [eventlistener:cat]')

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
        self.assertEqual(438, gconf_foo.socket_config.get_mode()) # 0666 in Py2, 0o666 in Py3
        self.assertEqual(len(gconf_foo.process_configs), 2)
        pconfig_foo = gconf_foo.process_configs[0]
        self.assertEqual(pconfig_foo.__class__, FastCGIProcessConfig)

        gconf_bar = gconfigs[1]
        self.assertEqual(gconf_bar.name, 'bar')
        self.assertEqual(gconf_bar.priority, 999)
        self.assertEqual(gconf_bar.socket_config.url,
                         'unix:///tmp/bar.sock')
        self.assertEqual(exp_owner, gconf_bar.socket_config.get_owner())
        self.assertEqual(448, gconf_bar.socket_config.get_mode()) # 0700 in Py2, 0o700 in Py3
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
        self.assertEqual(448, gconf_flub.socket_config.get_mode()) # 0700 in Py2, 0o700 in Py3
        self.assertEqual(len(gconf_flub.process_configs), 1)


    @patch.dict('os.environ', { 'HOME': '/tmp',
                                'SERVER_PORT': '9210',
                                'FOO_SOCKET_EXT': '.usock',
                                'FOO_SOCKET_USER': 'testuser',
                                'FOO_SOCKET_MODE': '0666',
                                'FOO_PROCESS_PREFIX': 'fcgi-',
                                'FOO_COMMAND_ARG1': 'bar',
                                'FOO_NUMPROCS': '2',
                                'FOO_PRIORITY': '1',
                                })
    def test_fcgi_programs_from_parser_with_environment_expansions(self):
        from supervisor.options import FastCGIGroupConfig
        from supervisor.options import FastCGIProcessConfig
        text = lstrip("""\
        [fcgi-program:foo]
        socket = unix:///tmp/%(program_name)s%(ENV_FOO_SOCKET_EXT)s
        socket_owner = %(ENV_FOO_SOCKET_USER)s:testgroup
        socket_mode = %(ENV_FOO_SOCKET_MODE)s
        process_name = %(ENV_FOO_PROCESS_PREFIX)s_%(program_name)s_%(process_num)s
        command = /bin/foo --arg1=%(ENV_FOO_COMMAND_ARG1)s
        numprocs = %(ENV_FOO_NUMPROCS)s
        priority = %(ENV_FOO_PRIORITY)s
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

        self.assertEqual(len(gconfigs), 1)

        gconf_foo = gconfigs[0]
        self.assertEqual(gconf_foo.__class__, FastCGIGroupConfig)
        self.assertEqual(gconf_foo.name, 'foo')
        self.assertEqual(gconf_foo.priority, 1)
        self.assertEqual(gconf_foo.socket_config.url,
                                'unix:///tmp/foo.usock')
        self.assertEqual(exp_owner, gconf_foo.socket_config.get_owner())
        self.assertEqual(438, gconf_foo.socket_config.get_mode()) # 0666 in Py2, 0o666 in Py3
        self.assertEqual(len(gconf_foo.process_configs), 2)
        pconfig_foo = gconf_foo.process_configs[0]
        self.assertEqual(pconfig_foo.__class__, FastCGIProcessConfig)
        self.assertEqual(pconfig_foo.command, '/bin/foo --arg1=bar')

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

    def test_rpcinterfaces_from_parser_factory_missing(self):
        text = lstrip("""\
        [rpcinterface:dummy]
        # note: no supervisor.rpcinterface_factory here
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        try:
            instance.get_plugins(config,
                                 'supervisor.rpcinterface_factory',
                                 'rpcinterface:')
            self.fail('nothing raised')
        except ValueError as exc:
            self.assertEqual(exc.args[0], 'section [rpcinterface:dummy] '
                'does not specify a supervisor.rpcinterface_factory')

    def test_rpcinterfaces_from_parser_factory_not_importable(self):
        text = lstrip("""\
        [rpcinterface:dummy]
        supervisor.rpcinterface_factory = nonexistant
        """)
        from supervisor.options import UnhosedConfigParser
        config = UnhosedConfigParser()
        config.read_string(text)
        instance = self._makeOne()
        try:
            instance.get_plugins(config,
                                 'supervisor.rpcinterface_factory',
                                 'rpcinterface:')
            self.fail('nothing raised')
        except ValueError as exc:
            self.assertEqual(exc.args[0], 'nonexistant cannot be resolved '
                'within [rpcinterface:dummy]')

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
            f1 = open(first, 'w')
            f2 = open(second, 'w')
            instance.clear_autochildlogdir()
            self.assertFalse(os.path.exists(logfn))
            self.assertFalse(os.path.exists(first))
            self.assertFalse(os.path.exists(second))
            f1.close()
            f2.close()
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

    def test_dropPrivileges_user_none(self):
        instance = self._makeOne()
        msg = instance.dropPrivileges(None)
        self.assertEqual(msg, "No user specified to setuid to!")

    @patch('pwd.getpwuid', Mock(return_value=["foo", None, 12, 34]))
    @patch('os.getuid', Mock(return_value=12))
    def test_dropPrivileges_nonroot_same_user(self):
        instance = self._makeOne()
        msg = instance.dropPrivileges(os.getuid())
        self.assertEqual(msg, None) # no error if same user

    @patch('pwd.getpwuid', Mock(return_value=["foo", None, 55, 34]))
    @patch('os.getuid', Mock(return_value=12))
    def test_dropPrivileges_nonroot_different_user(self):
        instance = self._makeOne()
        msg = instance.dropPrivileges(42)
        self.assertEqual(msg, "Can't drop privilege as nonroot user")

    def test_daemonize_notifies_poller_before_and_after_fork(self):
        instance = self._makeOne()
        instance._daemonize = lambda: None
        instance.poller = Mock()
        instance.daemonize()
        instance.poller.before_daemonize.assert_called_once_with()
        instance.poller.after_daemonize.assert_called_once_with()

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
                     'stdout_events_enabled', 'stdout_syslog',
                     'stderr_logfile', 'stderr_capture_maxbytes',
                     'stderr_events_enabled', 'stderr_syslog',
                     'stopsignal', 'stopwaitsecs', 'stopasgroup',
                     'killasgroup', 'exitcodes', 'redirect_stderr',
                     'environment'):
            defaults[name] = name
        for name in ('stdout_logfile_backups', 'stdout_logfile_maxbytes',
                     'stderr_logfile_backups', 'stderr_logfile_maxbytes'):
            defaults[name] = 10
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
        with _getTempFile('stderr_logfile') as stdout_logfile:
            with _getTempFile('stderr_logfile') as stderr_logfile:
                instance.stdout_logfile = stdout_logfile.name
                instance.stderr_logfile = stderr_logfile.name
                logger.debug('instance.stdout_logfile = %r',
                             instance.stdout_logfile)
                logger.debug('instance.stderr_logfile = %r',
                             instance.stderr_logfile)
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
        with _getTempFile('stderr_logfile') as stdout_logfile:
            instance.stdout_logfile = stdout_logfile.name
            logger.debug('instance.stdout_logfile = %r',
                         instance.stdout_logfile)
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
                     'stdout_events_enabled', 'stdout_syslog',
                     'stderr_logfile', 'stderr_capture_maxbytes',
                     'stderr_events_enabled', 'stderr_syslog',
                     'stopsignal', 'stopwaitsecs', 'stopasgroup',
                     'killasgroup', 'exitcodes', 'redirect_stderr',
                     'environment'):
            defaults[name] = name
        for name in ('stdout_logfile_backups', 'stdout_logfile_maxbytes',
                     'stderr_logfile_backups', 'stderr_logfile_maxbytes'):
            defaults[name] = 10
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
        with _getTempFile('stderr_logfile') as stdout_logfile:
            with _getTempFile('stderr_logfile') as stderr_logfile:
                instance.stdout_logfile = stdout_logfile.name
                instance.stderr_logfile = stderr_logfile.name
                logger.debug('instance.stdout_logfile = %r',
                             instance.stdout_logfile)
                logger.debug('instance.stderr_logfile = %r',
                             instance.stderr_logfile)
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

class EventListenerPoolConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import EventListenerPoolConfig
        return EventListenerPoolConfig

    def _makeOne(self, options, name, priority, process_configs, buffer_size,
                 pool_events, result_handler):
        return self._getTargetClass()(options, name, priority,
                                      process_configs, buffer_size,
                                      pool_events, result_handler)

    def test_make_group(self):
        options = DummyOptions()
        pconfigs = [DummyPConfig(options, 'process1', '/bin/process1')]
        instance = self._makeOne(options, 'name', 999, pconfigs, 1, [], None)
        group = instance.make_group()
        from supervisor.process import EventListenerPool
        self.assertEqual(group.__class__, EventListenerPool)

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

    def test_make_group(self):
        options = DummyOptions()
        sock_config = DummySocketConfig(6)
        instance = self._makeOne(options, 'name', 999, [], sock_config)
        group = instance.make_group()
        from supervisor.process import FastCGIProcessGroup
        self.assertEqual(group.__class__, FastCGIProcessGroup)

class SignalReceiverTests(unittest.TestCase):
    def test_returns_None_initially(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        self.assertEqual(sr.get_signal(), None)

    def test_returns_signals_in_order_received(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        sr.receive(signal.SIGTERM, 'frame')
        sr.receive(signal.SIGCHLD, 'frame')
        self.assertEqual(sr.get_signal(), signal.SIGTERM)
        self.assertEqual(sr.get_signal(), signal.SIGCHLD)
        self.assertEqual(sr.get_signal(), None)

    def test_does_not_queue_duplicate_signals(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        sr.receive(signal.SIGTERM, 'frame')
        sr.receive(signal.SIGTERM, 'frame')
        self.assertEqual(sr.get_signal(), signal.SIGTERM)
        self.assertEqual(sr.get_signal(), None)

    def test_queues_again_after_being_emptied(self):
        from supervisor.options import SignalReceiver
        sr = SignalReceiver()
        sr.receive(signal.SIGTERM, 'frame')
        self.assertEqual(sr.get_signal(), signal.SIGTERM)
        self.assertEqual(sr.get_signal(), None)
        sr.receive(signal.SIGCHLD, 'frame')
        self.assertEqual(sr.get_signal(), signal.SIGCHLD)
        self.assertEqual(sr.get_signal(), None)

class UnhosedConfigParserTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import UnhosedConfigParser
        return UnhosedConfigParser

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_read_filenames_as_string(self):
        f = tempfile.NamedTemporaryFile(mode="w+")
        config = self._makeOne()
        try:
            f.write("[foo]\n")
            f.flush()
            ok_filenames = config.read(f.name)
        finally:
            f.close()
        self.assertEqual(ok_filenames, [f.name])

    def test_read_filenames_as_list(self):
        f = tempfile.NamedTemporaryFile(mode="w+")
        parser = self._makeOne()
        try:
            f.write("[foo]\n")
            f.flush()
            ok_filenames = parser.read([f.name])
        finally:
            f.close()
        self.assertEqual(ok_filenames, [f.name])

    def test_read_returns_ok_filenames_like_rawconfigparser(self):
        nonexistant = os.path.join(os.path.dirname(__file__), "nonexistant")
        f = tempfile.NamedTemporaryFile(mode="w+")
        parser = self._makeOne()
        try:
            f.write("[foo]\n")
            f.flush()
            ok_filenames = parser.read([nonexistant, f.name])
        finally:
            f.close()
        self.assertEqual(ok_filenames, [f.name])

    def test_read_section_to_file_initially_empty(self):
        parser = self._makeOne()
        self.assertEqual(parser.section_to_file, {})

    def test_read_section_to_file_read_one_file(self):
        f = tempfile.NamedTemporaryFile(mode="w+")
        try:
            f.write("[foo]\n")
            f.flush()
            parser = self._makeOne()
            parser.read([f.name])
        finally:
            f.close()
        self.assertEqual(parser.section_to_file['foo'], f.name)

    def test_read_section_to_file_read_multiple_files(self):
        f1 = tempfile.NamedTemporaryFile(mode="w+")
        f2 = tempfile.NamedTemporaryFile(mode="w+")
        try:
            f1.write("[foo]\n")
            f1.flush()
            f2.write("[bar]\n")
            f2.flush()
            parser = self._makeOne()
            parser.read([f1.name, f2.name])
        finally:
            f1.close()
            f2.close()
        self.assertEqual(parser.section_to_file['foo'], f1.name)
        self.assertEqual(parser.section_to_file['bar'], f2.name)

class UtilFunctionsTests(unittest.TestCase):
    def test_make_namespec(self):
        from supervisor.options import make_namespec
        self.assertEqual(make_namespec('group', 'process'), 'group:process')
        self.assertEqual(make_namespec('process', 'process'), 'process')

    def test_split_namespec(self):
        from supervisor.options import split_namespec
        s = split_namespec
        self.assertEqual(s('process:group'), ('process', 'group'))
        self.assertEqual(s('process'), ('process', 'process'))
        self.assertEqual(s('group:'), ('group', None))
        self.assertEqual(s('group:*'), ('group', None))

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

