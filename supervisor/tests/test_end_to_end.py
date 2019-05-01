# ~*~ coding: utf-8 ~*~
from __future__ import unicode_literals

import os
import sys
import signal
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

    def test_issue_565(self):
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
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-663.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        for i in range(2):
            supervisord.expect_exact('OKREADY', timeout=60)
            supervisord.expect_exact('BUSY -> ACKNOWLEDGED', timeout=30)

    def test_issue_664(self):
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

    def test_issue_1054(self):
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

    def test_issue_1224(self):
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1224.conf')
        args = ['-m', 'supervisor.supervisord', '-c', filename]
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('cat entered RUNNING state', timeout=60)

    def test_issue_1231a(self):
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1231.conf')
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
        filename = pkg_resources.resource_filename(__name__, 'fixtures/issue-1231.conf')
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


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
