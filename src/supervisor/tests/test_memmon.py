import sys
import unittest
from StringIO import StringIO

class MemmonTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.memmon import Memmon
        return Memmon

    def _makeOne(self, *opts):
        return self._getTargetClass()(*opts)

    def _makeOnePopulated(self, programs, groups, any):
        from supervisor.tests.base import DummyRPCServer
        rpc = DummyRPCServer()
        sendmail = 'echo'
        email = 'chrism@plope.com'
        memmon = self._makeOne(programs, groups, any, sendmail, email, rpc)
        memmon.stdin = StringIO()
        memmon.stdout = StringIO()
        memmon.stderr = StringIO()
        memmon.pscommand = 'echo 22%s'
        return memmon
        
    def test_runforever_notatick(self):
        programs = {'foo':0, 'bar':0, 'baz_01':0 }
        groups = {}
        any = None
        memmon = self._makeOnePopulated(programs, groups, any)
        memmon.stdin.write('eventname:NOTATICK len:0\n')
        memmon.stdin.seek(0)
        memmon.runforever(test=True)
        self.assertEqual(memmon.stderr.getvalue(), '')

    def test_runforever_tick_programs(self):
        programs = {'foo':0, 'bar':0, 'baz_01':0 }
        groups = {}
        any = None
        memmon = self._makeOnePopulated(programs, groups, any)
        memmon.stdin.write('eventname:TICK len:0\n')
        memmon.stdin.seek(0)
        memmon.runforever(test=True)
        lines = memmon.stderr.getvalue().split('\n')
        self.assertEqual(len(lines), 8)
        self.assertEqual(lines[0], 'Checking programs foo=0, bar=0, baz_01=0')
        self.assertEqual(lines[1], 'RSS of foo:foo is 2264064')
        self.assertEqual(lines[2], 'Restarting foo:foo')
        self.assertEqual(lines[3], 'RSS of bar:bar is 2265088')
        self.assertEqual(lines[4], 'Restarting bar:bar')
        self.assertEqual(lines[5], 'RSS of baz:baz_01 is 2265088')
        self.assertEqual(lines[6], 'Restarting baz:baz_01')
        self.assertEqual(lines[7], '')
        self.assertEqual(memmon.mailed, True)

    def test_runforever_tick_groups(self):
        programs = {}
        groups = {'foo':0}
        any = None
        memmon = self._makeOnePopulated(programs, groups, any)
        memmon.stdin.write('eventname:TICK len:0\n')
        memmon.stdin.seek(0)
        memmon.runforever(test=True)
        lines = memmon.stderr.getvalue().split('\n')
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0], 'Checking groups foo=0')
        self.assertEqual(lines[1], 'RSS of foo:foo is 2264064')
        self.assertEqual(lines[2], 'Restarting foo:foo')
        self.assertEqual(lines[3], '')
        self.assertEqual(memmon.mailed, True)

    def test_runforever_tick_any(self):
        programs = {}
        groups = {}
        any = 0
        memmon = self._makeOnePopulated(programs, groups, any)
        memmon.stdin.write('eventname:TICK len:0\n')
        memmon.stdin.seek(0)
        memmon.runforever(test=True)
        lines = memmon.stderr.getvalue().split('\n')
        self.assertEqual(len(lines), 8)
        self.assertEqual(lines[0], 'Checking any=0')
        self.assertEqual(lines[1], 'RSS of foo:foo is 2264064')
        self.assertEqual(lines[2], 'Restarting foo:foo')
        self.assertEqual(lines[3], 'RSS of bar:bar is 2265088')
        self.assertEqual(lines[4], 'Restarting bar:bar')
        self.assertEqual(lines[5], 'RSS of baz:baz_01 is 2265088')
        self.assertEqual(lines[6], 'Restarting baz:baz_01')
        self.assertEqual(lines[7], '')
        self.assertEqual(memmon.mailed, True)

    def test_runforever_tick_programs_and_groups(self):
        programs = {'baz_01':0}
        groups = {'foo':0}
        any = None
        memmon = self._makeOnePopulated(programs, groups, any)
        memmon.stdin.write('eventname:TICK len:0\n')
        memmon.stdin.seek(0)
        memmon.runforever(test=True)
        lines = memmon.stderr.getvalue().split('\n')
        self.assertEqual(len(lines), 7)
        self.assertEqual(lines[0], 'Checking programs baz_01=0')
        self.assertEqual(lines[1], 'Checking groups foo=0')
        self.assertEqual(lines[2], 'RSS of foo:foo is 2264064')
        self.assertEqual(lines[3], 'Restarting foo:foo')
        self.assertEqual(lines[4], 'RSS of baz:baz_01 is 2265088')
        self.assertEqual(lines[5], 'Restarting baz:baz_01')
        self.assertEqual(lines[6], '')
        self.assertEqual(memmon.mailed, True)

    def test_runforever_tick_programs_norestart(self):
        programs = {'foo': sys.maxint}
        groups = {}
        any = None
        memmon = self._makeOnePopulated(programs, groups, any)
        memmon.stdin.write('eventname:TICK len:0\n')
        memmon.stdin.seek(0)
        memmon.runforever(test=True)
        lines = memmon.stderr.getvalue().split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], 'Checking programs foo=%s' % sys.maxint)
        self.assertEqual(lines[1], 'RSS of foo:foo is 2264064')
        self.assertEqual(lines[2], '')
        self.assertEqual(memmon.mailed, False)

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
