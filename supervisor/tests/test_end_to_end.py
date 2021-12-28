# ~*~ coding: utf-8 ~*~
from __future__ import unicode_literals

import os
import signal
import sys
import unittest
import pkg_resources
from supervisor.compat import xmlrpclib
from supervisor.xmlrpc import SupervisorTransport


# end-to-test tests are slow so only run them when asked
if 'END_TO_END' in os.environ:
    import pexpect
    BaseTestCase = unittest.TestCase
else:
    BaseTestCase = object


class EndToEndTests(BaseTestCase):

    def test_issue_291a_percent_signs_in_original_env_are_preserved(self):
        """When an environment variable whose value contains a percent sign is
        present in the environment before supervisord starts, the value is
        passed to the child without the percent sign being mangled."""
        key = "SUPERVISOR_TEST_1441B"
        val = "foo_%s_%_%%_%%%_%2_bar"
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-291a.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        try:
            os.environ[key] = val
            supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
            self.addCleanup(supervisord.kill, signal.SIGINT)
            supervisord.expect_exact(key + "=" + val)
        finally:
            del os.environ[key]

    def test_issue_550(self):
        """When an environment variable is set in the [supervisord] section,
        it should be put into the environment of the subprocess."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-550.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('success: print_env entered RUNNING state')
        supervisord.expect_exact('exited: print_env (exit status 0; expected)')

        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'tail -100000', 'print_env']
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)
        supervisorctl.expect_exact("THIS_SHOULD=BE_IN_CHILD_ENV")
        supervisorctl.expect(pexpect.EOF)

    def test_issue_565(self):
        """When a log file has Unicode characters in it, 'supervisorctl
        tail -f name' should still work."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-565.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('success: hello entered RUNNING state')

        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'tail', '-f', 'hello']
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)

        for i in range(1, 4):
            line = 'The Øresund bridge ends in Malmö - %d' % i
            supervisorctl.expect_exact(line, timeout=30)

    def test_issue_638(self):
        """When a process outputs something on its stdout or stderr file
        descriptor that is not valid UTF-8, supervisord should not crash."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-638.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        is_py2 = sys.version_info[0] < 3
        if is_py2:
            b_prefix = ''
        else:
            b_prefix = 'b'
        supervisord.expect_exact(r"Undecodable: %s'\x88\n'" % b_prefix, timeout=30)
        supervisord.expect('received SIGCH?LD indicating a child quit', timeout=30)
        if is_py2:
            # need to investigate why this message is only printed under 2.x
            supervisord.expect_exact('gave up: produce-unicode-error entered FATAL state, '
                                     'too many start retries too quickly', timeout=60)

    def test_issue_663(self):
        """When Supervisor is run on Python 3, the eventlistener protocol
        should work."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-663.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        for i in range(2):
            supervisord.expect_exact('OKREADY', timeout=60)
            supervisord.expect_exact('BUSY -> ACKNOWLEDGED', timeout=30)

    def test_issue_664(self):
        """When a subprocess name has Unicode characters, 'supervisord'
        should not send incomplete XML-RPC responses and 'supervisorctl
        status' should work."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-664.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('test_öäü entered RUNNING state', timeout=60)

        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'status']
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)
        try:
            supervisorctl.expect('test_öäü\\s+RUNNING', timeout=30)
            seen = True
        except pexpect.ExceptionPexpect:
            seen = False
        self.assertTrue(seen)

    def test_issue_733(self):
        """When a subprocess enters the FATAL state, a one-line eventlistener
        can be used to signal supervisord to shut down."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-733.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('gave up: nonexistent entered FATAL state')
        supervisord.expect_exact('received SIGTERM indicating exit request')
        supervisord.expect(pexpect.EOF)

    def test_issue_835(self):
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-835.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('cat entered RUNNING state', timeout=60)
        transport = SupervisorTransport('', '', 'unix:///tmp/issue-835.sock')
        server = xmlrpclib.ServerProxy('http://anything/RPC2', transport)
        try:
            for s in ('The Øresund bridge ends in Malmö', 'hello'):
                result = server.supervisor.sendProcessStdin('cat', s)
                self.assertTrue(result)
                supervisord.expect_exact(s, timeout=30)
        finally:
            transport.connection.close()

    def test_issue_836(self):
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-836.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('cat entered RUNNING state', timeout=60)
        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'fg', 'cat']
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)

        try:
            for s in ('Hi', 'Hello', 'The Øresund bridge ends in Malmö'):
                supervisorctl.sendline(s)
                supervisord.expect_exact(s, timeout=60)
                supervisorctl.expect_exact(s) # echoed locally
                supervisorctl.expect_exact(s) # sent back by supervisord
            seen = True
        except pexpect.ExceptionPexpect:
            seen = False
        self.assertTrue(seen)

    def test_issue_986_command_string_with_double_percent(self):
        """A percent sign can be used in a command= string without being
        expanded if it is escaped by a second percent sign."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-986.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('dhcrelay -d -q -a %h:%p %P -i Vlan1000 192.168.0.1')

    def test_issue_1054(self):
        """When run on Python 3, the 'supervisorctl avail' command
        should work."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1054.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('cat entered RUNNING state', timeout=60)
        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'avail']
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        try:
            supervisorctl.expect('cat\\s+in use\\s+auto', timeout=30)
            seen = True
        except pexpect.ExceptionPexpect:
            seen = False
        self.assertTrue(seen)

    def test_issue_1170a(self):
        """When the [supervisord] section has a variable defined in
        environment=, that variable should be able to be used in an
        %(ENV_x) expansion in a [program] section."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1170a.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact("set from [supervisord] section")

    def test_issue_1170b(self):
        """When the [supervisord] section has a variable defined in
        environment=, and a variable by the same name is defined in
        enviroment= of a [program] section, the one in the [program]
        section should be used."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1170b.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact("set from [program] section")

    def test_issue_1170c(self):
        """When the [supervisord] section has a variable defined in
        environment=, and a variable by the same name is defined in
        enviroment= of an [eventlistener] section, the one in the
        [eventlistener] section should be used."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1170c.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact("set from [eventlistener] section")

    def test_issue_1224(self):
        """When the main log file does not need rotation (logfile_maxbyte=0)
        then the non-rotating logger will be used to avoid an
        IllegalSeekError in the case that the user has configured a
        non-seekable file like /dev/stdout."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1224.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('cat entered RUNNING state', timeout=60)

    def test_issue_1231a(self):
        """When 'supervisorctl tail -f name' is run and the log contains
        unicode, it should not fail."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1231a.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('success: hello entered RUNNING state')

        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'tail', '-f', 'hello']
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)

        for i in range(1, 4):
            line = '%d - hash=57d94b…381088' % i
            supervisorctl.expect_exact(line, timeout=30)

    def test_issue_1231b(self):
        """When 'supervisorctl tail -f name' is run and the log contains
        unicode, it should not fail."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1231b.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('success: hello entered RUNNING state')

        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'tail', '-f', 'hello']
        env = os.environ.copy()
        env['LANG'] = 'oops'
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8',
                                      env=env)
        self.addCleanup(supervisorctl.kill, signal.SIGINT)

        # For Python 3 < 3.7, LANG=oops leads to warnings because of the
        # stdout encoding. For 3.7 (and presumably later), the encoding is
        # utf-8 when LANG=oops.
        if sys.version_info[:2] < (3, 7):
            supervisorctl.expect('Warning: sys.stdout.encoding is set to ',
                                 timeout=30)
            supervisorctl.expect('Unicode output may fail.', timeout=30)

        for i in range(1, 4):
            line = '%d - hash=57d94b…381088' % i
            try:
                supervisorctl.expect_exact(line, timeout=30)
            except pexpect.exceptions.EOF:
                self.assertIn('Unable to write Unicode to stdout because it '
                              'has encoding ',
                              supervisorctl.before)
                break

    def test_issue_1231c(self):
        """When 'supervisorctl tail -f name' is run and the log contains
        unicode, it should not fail."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1231c.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('success: hello entered RUNNING state')

        args = ['-m', 'supervisor.supervisorctl', '-c', filename, 'tail', 'hello']
        env = os.environ.copy()
        env['LANG'] = 'oops'
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8',
                                      env=env)
        self.addCleanup(supervisorctl.kill, signal.SIGINT)

        # For Python 3 < 3.7, LANG=oops leads to warnings because of the
        # stdout encoding. For 3.7 (and presumably later), the encoding is
        # utf-8 when LANG=oops.
        if sys.version_info[:2] < (3, 7):
            supervisorctl.expect('Warning: sys.stdout.encoding is set to ',
                                 timeout=30)
            supervisorctl.expect('Unicode output may fail.', timeout=30)

    def test_issue_1251(self):
        """When -? is given to supervisord or supervisorctl, help should be
        displayed like -h does."""
        args = ['-m', 'supervisor.supervisord', '-?']
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact("supervisord -- run a set of applications")
        supervisord.expect_exact("-l/--logfile FILENAME -- use FILENAME as")
        supervisord.expect(pexpect.EOF)

        args = ['-m', 'supervisor.supervisorctl', '-?']
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)
        supervisorctl.expect_exact("supervisorctl -- control applications")
        supervisorctl.expect_exact("-i/--interactive -- start an interactive")
        supervisorctl.expect(pexpect.EOF)

    def test_issue_1298(self):
        """When the output of 'supervisorctl tail -f worker' is piped such as
        'supervisor tail -f worker | grep something', 'supervisorctl' should
        not crash."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1298.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('success: spew entered RUNNING state')

        cmd = "'%s' -m supervisor.supervisorctl -c '%s' tail -f spew | /bin/cat -u" % (
            sys.executable, filename
            )
        bash = pexpect.spawn('/bin/sh', ['-c', cmd], encoding='utf-8')
        self.addCleanup(bash.kill, signal.SIGINT)
        bash.expect('spewage 2', timeout=30)

    def test_issue_1418_pidproxy_cmd_with_no_args(self):
        """When pidproxy is given a command to run that has no arguments, it
        runs that command."""
        args = ['-m', 'supervisor.pidproxy', 'nonexistent-pidfile', "/bin/echo"]
        pidproxy = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(pidproxy.kill, signal.SIGINT)
        pidproxy.expect(pexpect.EOF)
        self.assertEqual(pidproxy.before.strip(), "")

    def test_issue_1418_pidproxy_cmd_with_args(self):
        """When pidproxy is given a command to run that has arguments, it
        runs that command."""
        args = ['-m', 'supervisor.pidproxy', 'nonexistent-pidfile', "/bin/echo", "1", "2"]
        pidproxy = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(pidproxy.kill, signal.SIGINT)
        pidproxy.expect(pexpect.EOF)
        self.assertEqual(pidproxy.before.strip(), "1 2")

    def test_issue_1483a_identifier_default(self):
        """When no identifier is supplied on the command line or in the config
        file, the default is used."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1483a.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('supervisord started with pid')

        from supervisor.compat import xmlrpclib
        from supervisor.xmlrpc import SupervisorTransport
        transport = SupervisorTransport('', '', 'unix:///tmp/issue-1483a.sock')
        try:
            server = xmlrpclib.ServerProxy('http://transport.ignores.host/RPC2', transport)
            ident = server.supervisor.getIdentification()
        finally:
            transport.close()
        self.assertEqual(ident, "supervisor")

    def test_issue_1483b_identifier_from_config_file(self):
        """When the identifier is supplied in the config file only, that
        identifier is used instead of the default."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1483b.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('supervisord started with pid')

        from supervisor.compat import xmlrpclib
        from supervisor.xmlrpc import SupervisorTransport
        transport = SupervisorTransport('', '', 'unix:///tmp/issue-1483b.sock')
        try:
            server = xmlrpclib.ServerProxy('http://transport.ignores.host/RPC2', transport)
            ident = server.supervisor.getIdentification()
        finally:
            transport.close()
        self.assertEqual(ident, "from_config_file")

    def test_issue_1483c_identifier_from_command_line(self):
        """When an identifier is supplied in both the config file and on the
        command line, the one from the command line is used."""
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1483c.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename, '-i', 'from_command_line']
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('supervisord started with pid')

        from supervisor.compat import xmlrpclib
        from supervisor.xmlrpc import SupervisorTransport
        transport = SupervisorTransport('', '', 'unix:///tmp/issue-1483c.sock')
        try:
            server = xmlrpclib.ServerProxy('http://transport.ignores.host/RPC2', transport)
            ident = server.supervisor.getIdentification()
        finally:
            transport.close()
        self.assertEqual(ident, "from_command_line")

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
