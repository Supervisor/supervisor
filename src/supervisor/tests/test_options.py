"""Test suite for supervisor.options"""

import os
import sys
import tempfile
import socket
import unittest
import signal

from supervisor.tests.base import DummyLogger
from supervisor.tests.base import DummyOptions
from supervisor.tests.base import lstrip

class ServerOptionsTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import ServerOptions
        return ServerOptions

    def _makeOne(self):
        return self._getTargetClass()()
        
    def test_options(self):
        s = lstrip("""[supervisord]
        http_port=127.0.0.1:8999
        http_username=chrism
        http_password=foo   
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
        
        [program:cat1]
        command=/bin/cat
        priority=1
        autostart=true
        autorestart=true
        user=root
        stdout_logfile=/tmp/cat.log
        stopsignal=KILL
        stopwaitsecs=5
        startsecs=5
        startretries=10
        
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
        exitcodes=0,1,127
        
        [program:cat4]
        priority=4
        process_name = fleeb_%%(process_num)s
        numprocs = 2
        command = /bin/cat
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
        self.assertEqual(options.http_port.family, socket.AF_INET)
        self.assertEqual(options.http_port.address, ('127.0.0.1', 8999))
        self.assertEqual(options.http_username, 'chrism')
        self.assertEqual(options.http_password, 'foo')
        self.assertEqual(options.nocleanup, True)
        self.assertEqual(options.minfds, 2048)
        self.assertEqual(options.minprocs, 300)
        self.assertEqual(options.nocleanup, True)
        self.assertEqual(len(options.process_group_configs), 4)

        cat1 = options.process_group_configs[0]
        self.assertEqual(cat1.name, 'cat1')
        self.assertEqual(cat1.priority, 1)
        self.assertEqual(len(cat1.process_configs), 1)
        
        proc1 = cat1.process_configs[0]
        self.assertEqual(proc1.name, 'cat1')
        self.assertEqual(proc1.command, '/bin/cat')
        self.assertEqual(proc1.priority, 1)
        self.assertEqual(proc1.autostart, True)
        self.assertEqual(proc1.autorestart, True)
        self.assertEqual(proc1.startsecs, 5)
        self.assertEqual(proc1.startretries, 10)
        self.assertEqual(proc1.uid, 0)
        self.assertEqual(proc1.stdout_logfile, '/tmp/cat.log')
        self.assertEqual(proc1.stopsignal, signal.SIGKILL)
        self.assertEqual(proc1.stopwaitsecs, 5)
        self.assertEqual(proc1.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc1.stdout_logfile_backups, 10)
        self.assertEqual(proc1.exitcodes, [0,2])

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
        self.assertEqual(proc2.stdout_logfile_maxbytes, 1024)
        self.assertEqual(proc2.stdout_logfile_backups, 2)
        self.assertEqual(proc2.exitcodes, [0,2])

        cat3 = options.process_group_configs[2]
        self.assertEqual(cat3.name, 'cat3')
        self.assertEqual(cat3.priority, 3)
        self.assertEqual(len(cat3.process_configs), 1)

        proc3 = cat3.process_configs[0]
        self.assertEqual(proc3.name, 'replaced')
        self.assertEqual(proc3.command, '/bin/cat')
        self.assertEqual(proc3.priority, 3)
        self.assertEqual(proc3.autostart, True)
        self.assertEqual(proc3.autorestart, True)
        self.assertEqual(proc3.uid, None)
        self.assertEqual(proc3.stdout_logfile, datatypes.Automatic)
        self.assertEqual(proc3.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc3.stdout_logfile_backups, 10)
        self.assertEqual(proc3.exitcodes, [0,1,127])
        self.assertEqual(proc3.stopsignal, signal.SIGTERM)

        cat4 = options.process_group_configs[3]
        self.assertEqual(cat4.name, 'cat4')
        self.assertEqual(cat4.priority, 4)
        self.assertEqual(len(cat4.process_configs), 2)

        proc4_a = cat4.process_configs[0]
        self.assertEqual(proc4_a.name, 'fleeb_0')
        self.assertEqual(proc4_a.command, '/bin/cat')
        self.assertEqual(proc4_a.priority, 4)
        self.assertEqual(proc4_a.autostart, True)
        self.assertEqual(proc4_a.autorestart, True)
        self.assertEqual(proc4_a.uid, None)
        self.assertEqual(proc4_a.stdout_logfile, datatypes.Automatic)
        self.assertEqual(proc4_a.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc4_a.stdout_logfile_backups, 10)
        self.assertEqual(proc4_a.exitcodes, [0,2])
        self.assertEqual(proc4_a.stopsignal, signal.SIGTERM)

        proc4_b = cat4.process_configs[1]
        self.assertEqual(proc4_b.name, 'fleeb_1')
        self.assertEqual(proc4_b.command, '/bin/cat')
        self.assertEqual(proc4_b.priority, 4)
        self.assertEqual(proc4_b.autostart, True)
        self.assertEqual(proc4_b.autorestart, True)
        self.assertEqual(proc4_b.uid, None)
        self.assertEqual(proc4_b.stdout_logfile, datatypes.Automatic)
        self.assertEqual(proc4_b.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(proc4_b.stdout_logfile_backups, 10)
        self.assertEqual(proc4_b.exitcodes, [0,2])
        self.assertEqual(proc4_b.stopsignal, signal.SIGTERM)

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
        self.assertEqual(instance.http_port.family, socket.AF_INET)
        self.assertEqual(instance.http_port.address, ('127.0.0.1', 8999))
        self.assertEqual(instance.http_username, 'chrism')
        self.assertEqual(instance.http_password, 'foo')
        self.assertEqual(instance.nocleanup, True)
        self.assertEqual(instance.minfds, 2048)
        self.assertEqual(instance.minprocs, 300)

    def test_readFile_failed(self):
        from supervisor.options import readFile
        try:
            readFile('/notthere', 0, 10)
        except ValueError, inst:
            self.assertEqual(inst.args[0], 'FAILED')
        else:
            raise AssertionError("Didn't raise")

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
        instance.http_port = Port()
        instance.httpserver = Server()
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
            instance.http_port = Port()
            instance.httpserver = Server()
            instance.pidfile = ''
            instance.unlink_socketfile = False
            instance.cleanup()
            self.failUnless(os.path.exists(fn))
        finally:
            try:
                os.unlink(fn)
            except os.error:
                pass

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
            except os.error:
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
        self.assertRaises(os.error, os.read, innie, 0)
        instance.close_fd(outie)
        self.assertRaises(os.error, os.write, outie, 'foo')

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
        stdout_capturelogfile = NONE
        stdout_logfile_backups = 1
        stdout_logfile_maxbytes = 100MB
        stopsignal = KILL
        stopwaitsecs = 100
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
        from supervisor import datatypes
        self.assertEqual(pconfig.name, 'bar_foo_00')
        self.assertEqual(pconfig.command, '/bin/cat')
        self.assertEqual(pconfig.autostart, False)
        self.assertEqual(pconfig.autorestart, False)
        self.assertEqual(pconfig.startsecs, 100)
        self.assertEqual(pconfig.startretries, 100)
        self.assertEqual(pconfig.uid, 0)
        self.assertEqual(pconfig.stdout_logfile, None)
        self.assertEqual(pconfig.stdout_capturefile, datatypes.Automatic)
        self.assertEqual(pconfig.stdout_logfile_maxbytes, 104857600)
        self.assertEqual(pconfig.stopsignal, signal.SIGKILL)
        self.assertEqual(pconfig.stopwaitsecs, 100)
        self.assertEqual(pconfig.exitcodes, [1,4])
        self.assertEqual(pconfig.redirect_stderr, False)
        self.assertEqual(pconfig.environment,
                         {'KEY1':'val1', 'KEY2':'val2', 'KEY3':'0'})

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

    def test_missing_replacement_in_process_name(self):
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

    def test_bad_expression_in_process_name(self):
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
        factories = instance.rpcinterfaces_from_parser(config)
        self.assertEqual(len(factories), 1)
        factory = factories[0]
        self.assertEqual(factory[0], 'dummy')
        self.assertEqual(factory[1], sys.modules[__name__])
        self.assertEqual(factory[2], {'foo':'bar'})
        
class TestProcessConfig(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import ProcessConfig
        return ProcessConfig

    def _makeOne(self, *arg, **kw):
        defaults = {}
        for name in ('name', 'command', 'priority', 'autostart', 'autorestart',
                     'startsecs', 'startretries', 'uid',
                     'stdout_logfile', 'stdout_capturefile',
                     'stdout_logfile_backups', 'stdout_logfile_maxbytes',
                     'stderr_logfile', 'stderr_capturefile',
                     'stderr_logfile_backups', 'stderr_logfile_maxbytes',
                     'stopsignal', 'stopwaitsecs', 'exitcodes',
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

    def test_make_stderr_recorder(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        instance.redirect_stderr = False
        recorder = instance.make_stderr_recorder()
        from supervisor.recorders import LoggingRecorder
        self.assertEqual(recorder.__class__, LoggingRecorder)
        self.assertEqual(recorder.procname, 'name')
        self.assertEqual(recorder.channel, 'stderr')
        self.assertEqual(recorder.options, options)
        self.assertEqual(recorder.mainlog.__class__, DummyLogger)
        self.assertEqual(recorder.mainlog.args, (
            ('stderr_logfile', 20, '%(message)s'),
            {'rotating': True,
             'backups': 'stderr_logfile_backups',
             'maxbytes': 'stderr_logfile_maxbytes'}
            ))
        self.assertEqual(recorder.childlog, recorder.mainlog)
        self.assertEqual(recorder.capturelog.__class__, DummyLogger)
        self.assertEqual(recorder.capturelog.args,
                         (('stderr_capturefile', 20, '%(message)s'),
                          {'rotating': False}))

    def test_make_stderr_recorder_nocapture(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        instance.redirect_stderr = False
        instance.stderr_capturefile = None
        recorder = instance.make_stderr_recorder()
        from supervisor.recorders import LoggingRecorder
        self.assertEqual(recorder.capturelog, None)

    def test_make_stdout_recorder(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        recorder = instance.make_stdout_recorder()
        from supervisor.recorders import LoggingRecorder
        self.assertEqual(recorder.__class__, LoggingRecorder)
        self.assertEqual(recorder.procname, 'name')
        self.assertEqual(recorder.channel, 'stdout')
        self.assertEqual(recorder.options, options)
        self.assertEqual(recorder.mainlog.__class__, DummyLogger)
        self.assertEqual(recorder.mainlog.args, (
            ('stdout_logfile', 20, '%(message)s'),
            {'rotating': True,
             'backups': 'stdout_logfile_backups',
             'maxbytes': 'stdout_logfile_maxbytes'}
            ))
        self.assertEqual(recorder.childlog, recorder.mainlog)
        self.assertEqual(recorder.capturelog.__class__, DummyLogger)
        self.assertEqual(recorder.capturelog.args,
                         (('stdout_capturefile', 20, '%(message)s'),
                          {'rotating': False}))

    def test_make_stdout_recorder_nocapture(self):
        options = DummyOptions()
        instance = self._makeOne(options)
        instance.redirect_stderr = False
        instance.stdout_capturefile = None
        recorder = instance.make_stdout_recorder()
        from supervisor.recorders import LoggingRecorder
        self.assertEqual(recorder.capturelog, None)
            
class BasicAuthTransportTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import BasicAuthTransport
        return BasicAuthTransport

    def _makeOne(self, username=None, password=None, serverurl=None):
        klass = self._getTargetClass()
        return klass(username, password, serverurl)

    def test_ctor(self):
        instance = self._makeOne('username', 'password', 'serverurl')
        self.assertEqual(instance.username, 'username')
        self.assertEqual(instance.password, 'password')
        self.assertEqual(instance.serverurl, 'serverurl')
        self.assertEqual(instance.verbose, False)

    def test_works_with_py25(self):
        instance = self._makeOne('username', 'password', 'serverurl')
        # the test is just to insure that this method can be called; failure
        # would be an AttributeError for _use_datetime under Python 2.5
        parser, unmarshaller = instance.getparser() # this uses _use_datetime

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

