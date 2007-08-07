"""Test suite for supervisor.options"""

import os
import sys
import tempfile
import socket
import unittest

from supervisor.tests.base import DummyLogger

class ServerOptionsTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.options import ServerOptions
        return ServerOptions

    def _makeOne(self):
        return self._getTargetClass()()
        
    def test_options(self):
        s = """[supervisord]
http_port=127.0.0.1:8999 ; (default is to run no xmlrpc server)
http_username=chrism     ; (default is no username (open system))
http_password=foo        ; (default is no password (open system))
directory=%(tempdir)s     ; (default is not to cd during daemonization)
backofflimit=10            ; (default 3)
user=root                  ; (default is current user, required if root)
umask=022                  ; (default 022)
logfile=supervisord.log    ; (default supervisord.log)
logfile_maxbytes=1000MB    ; (default 50MB)
logfile_backups=5          ; (default 10)
loglevel=error             ; (default info)
pidfile=supervisord.pid    ; (default supervisord.pid)
nodaemon=true              ; (default false)
identifier=fleeb           ; (default supervisor)
childlogdir=%(tempdir)s           ; (default tempfile.gettempdir())
nocleanup=true             ; (default false)
minfds=2048                ; (default 1024)
minprocs=300               ; (default 200)

[program:cat]
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
command=/bin/cat
autostart=true
autorestart=false
stdout_logfile_maxbytes = 1024
stdout_logfile_backups = 2
stdout_logfile = /tmp/cat2.log

[program:cat3]
command=/bin/cat
exitcodes=0,1,127
""" % {'tempdir':tempfile.gettempdir()}

        from supervisor import datatypes

        import signal

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
        self.assertEqual(len(options.programs), 3)

        cat = options.programs[0]
        self.assertEqual(cat.name, 'cat')
        self.assertEqual(cat.command, '/bin/cat')
        self.assertEqual(cat.priority, 1)
        self.assertEqual(cat.autostart, True)
        self.assertEqual(cat.autorestart, True)
        self.assertEqual(cat.startsecs, 5)
        self.assertEqual(cat.startretries, 10)
        self.assertEqual(cat.uid, 0)
        self.assertEqual(cat.stdout_logfile, '/tmp/cat.log')
        self.assertEqual(cat.stopsignal, signal.SIGKILL)
        self.assertEqual(cat.stopwaitsecs, 5)
        self.assertEqual(cat.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(cat.stdout_logfile_backups, 10)
        self.assertEqual(cat.exitcodes, [0,2])

        cat2 = options.programs[1]
        self.assertEqual(cat2.name, 'cat2')
        self.assertEqual(cat2.command, '/bin/cat')
        self.assertEqual(cat2.priority, 999)
        self.assertEqual(cat2.autostart, True)
        self.assertEqual(cat2.autorestart, False)
        self.assertEqual(cat2.uid, None)
        self.assertEqual(cat2.stdout_logfile, '/tmp/cat2.log')
        self.assertEqual(cat2.stopsignal, signal.SIGTERM)
        self.assertEqual(cat2.stdout_logfile_maxbytes, 1024)
        self.assertEqual(cat2.stdout_logfile_backups, 2)
        self.assertEqual(cat2.exitcodes, [0,2])

        cat3 = options.programs[2]
        self.assertEqual(cat3.name, 'cat3')
        self.assertEqual(cat3.command, '/bin/cat')
        self.assertEqual(cat3.priority, 999)
        self.assertEqual(cat3.autostart, True)
        self.assertEqual(cat3.autorestart, True)
        self.assertEqual(cat3.uid, None)
        self.assertEqual(cat3.stdout_logfile, instance.AUTOMATIC)
        self.assertEqual(cat3.stdout_logfile_maxbytes,
                         datatypes.byte_size('50MB'))
        self.assertEqual(cat3.stdout_logfile_backups, 10)
        self.assertEqual(cat3.exitcodes, [0,1,127])
        
        self.assertEqual(cat2.stopsignal, signal.SIGTERM)

        here = os.path.abspath(os.getcwd())
        self.assertEqual(instance.uid, 0)
        self.assertEqual(instance.gid, 0)
        self.assertEqual(instance.directory, '/tmp')
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

    def test_programs_from_config(self):
        class DummyConfig:
            command = '/bin/cat'
            priority = 1
            autostart = 'false'
            autorestart = 'false'
            startsecs = 100
            startretries = 100
            user = 'root'
            stdout_logfile = 'NONE'
            stdout_logfile_backups = 1
            stdout_logfile_maxbytes = '100MB'
            stopsignal = 'KILL'
            stopwaitsecs = 100
            exitcodes = '1,4'
            redirect_stderr = 'false'
            environment = 'KEY1=val1,KEY2=val2'
            def sections(self):
                return ['program:foo']
            def saneget(self, section, name, default):
                return getattr(self, name, default)
        instance = self._makeOne()
        pconfig = instance.programs_from_config(DummyConfig())[0]
        import signal
        self.assertEqual(pconfig.name, 'foo')
        self.assertEqual(pconfig.command, '/bin/cat')
        self.assertEqual(pconfig.autostart, False)
        self.assertEqual(pconfig.autorestart, False)
        self.assertEqual(pconfig.startsecs, 100)
        self.assertEqual(pconfig.startretries, 100)
        self.assertEqual(pconfig.uid, 0)
        self.assertEqual(pconfig.stdout_logfile, None)
        self.assertEqual(pconfig.stdout_logfile_maxbytes, 104857600)
        self.assertEqual(pconfig.stopsignal, signal.SIGKILL)
        self.assertEqual(pconfig.stopwaitsecs, 100)
        self.assertEqual(pconfig.exitcodes, [1,4])
        self.assertEqual(pconfig.redirect_stderr, False)
        self.assertEqual(pconfig.environment, {'KEY1':'val1', 'KEY2':'val2'})
        
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

