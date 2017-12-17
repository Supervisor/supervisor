# ~*~ coding: utf-8 ~*~
from __future__ import unicode_literals

import sys
import signal
import unittest
from supervisor.compat import xmlrpclib

try:
    import pexpect
except ImportError:
    pexpect = None


class TestEndToEnd(unittest.TestCase):

    @unittest.skipUnless(pexpect, 'This test needs the pexpect library')
    def test_issue_565(self):
        args = '-m supervisor.supervisord -c supervisor/tests/fixtures/issue-565.conf'.split()
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('success: hello entered RUNNING state')

        args = '-m supervisor.supervisorctl -c supervisor/tests/fixtures/issue-565.conf tail -f hello'.split()
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)

        for i in range(1, 4):
            line = 'The Øresund bridge ends in Malmö - %d' % i
            supervisorctl.expect_exact(line, timeout=2)

    @unittest.skipUnless(pexpect, 'This test needs the pexpect library')
    def test_issue_638(self):
        args = '-m supervisor.supervisord -c supervisor/tests/fixtures/issue-638.conf'.split()
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        is_py2 = sys.version_info[0] < 3
        if is_py2:
            b_prefix = ''
        else:
            b_prefix = 'b'
        supervisord.expect_exact(r"Undecodable: %s'\x88\n'" % b_prefix, timeout=2)
        supervisord.expect('received SIGCH?LD indicating a child quit', timeout=5)
        if is_py2:
            # need to investigate why this message is only printed under 2.x
            supervisord.expect_exact('gave up: produce-unicode-error entered FATAL state, '
                                     'too many start retries too quickly', timeout=10)

    @unittest.skipUnless(pexpect, 'This test needs the pexpect library')
    def test_issue_663(self):
        args = '-m supervisor.supervisord -c supervisor/tests/fixtures/issue-663.conf'.split()
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        for i in range(2):
            supervisord.expect_exact('OKREADY', timeout=10)
            supervisord.expect_exact('BUSY -> ACKNOWLEDGED', timeout=2)

    @unittest.skipUnless(pexpect, 'This test needs the pexpect library')
    def test_issue_664(self):
        args = '-m supervisor.supervisord -c supervisor/tests/fixtures/issue-664.conf'.split()
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('test_öäü entered RUNNING state', timeout=10)
        args = '-m supervisor.supervisorctl -c supervisor/tests/fixtures/issue-664.conf status'.split()
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)
        try:
            supervisorctl.expect('test_öäü\s+RUNNING', timeout=5)
            seen = True
        except pexpect.ExceptionPexpect:
            seen = False
        self.assertTrue(seen)

    @unittest.skipUnless(pexpect, 'This test needs the pexpect library')
    def test_issue_835(self):
        args = '-m supervisor.supervisord -c supervisor/tests/fixtures/issue-836.conf'.split()
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('cat entered RUNNING state', timeout=10)
        server = xmlrpclib.ServerProxy('http://127.0.0.1:9001/RPC2')
        for s in ('The Øresund bridge ends in Malmö', 'hello'):
            result = server.supervisor.sendProcessStdin('cat', s)
            self.assertTrue(result)
            supervisord.expect_exact(s, timeout=5)
        server('close')()

    @unittest.skipUnless(pexpect, 'This test needs the pexpect library')
    def test_issue_836(self):
        args = '-m supervisor.supervisord -c supervisor/tests/fixtures/issue-836.conf'.split()
        supervisord = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisord.kill, signal.SIGINT)
        supervisord.expect_exact('cat entered RUNNING state', timeout=10)
        args = '-m supervisor.supervisorctl -c supervisor/tests/fixtures/issue-836.conf fg cat'.split()
        supervisorctl = pexpect.spawn(sys.executable, args, encoding='utf-8')
        self.addCleanup(supervisorctl.kill, signal.SIGINT)

        # TODO investigate - failure
        try:
            for s in ('Hi', 'Hello', 'The Øresund bridge ends in Malmö'):
                supervisorctl.sendline(s)
                supervisord.expect_exact(s, timeout=10)
                supervisorctl.expect_exact(s) # echoed locally
                supervisorctl.expect_exact(s) # sent back by supervisord
            seen = True
        except pexpect.ExceptionPexpect:
            seen = False
        self.assertTrue(seen)

if __name__ == '__main__':
    unittest.main()
