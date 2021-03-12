import os
import unittest

class PidProxyTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.pidproxy import PidProxy
        return PidProxy

    def _makeOne(self, *arg, **kw):
        return self._getTargetClass()(*arg, **kw)

    def test_ctor_parses_args(self):
        args = ["pidproxy.py", "/path/to/pidfile", "./cmd", "-arg1", "-arg2"]
        pp = self._makeOne(args)
        self.assertEqual(pp.pidfile, "/path/to/pidfile")
        self.assertEqual(pp.abscmd, os.path.abspath("./cmd"))
        self.assertEqual(pp.cmdargs, ["./cmd", "-arg1", "-arg2"])
