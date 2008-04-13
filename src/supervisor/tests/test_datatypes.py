"""Test suite for supervisor.datatypes"""

import sys
import os
import unittest
import socket
import tempfile

from supervisor.datatypes import UnixStreamSocketConfig
from supervisor.datatypes import InetStreamSocketConfig

class InetStreamSocketConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        return InetStreamSocketConfig
        
    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_url(self):
        conf = self._makeOne('127.0.0.1', 8675)
        self.assertEqual(conf.url, 'tcp://127.0.0.1:8675')
                
    def test_repr(self):
        conf = self._makeOne('127.0.0.1', 8675)
        s = repr(conf)
        self.assertTrue(s.startswith(
            '<supervisor.datatypes.InetStreamSocketConfig at'), s)
        self.assertTrue(s.endswith('for tcp://127.0.0.1:8675>'), s)

    def test_addr(self):
        conf = self._makeOne('127.0.0.1', 8675)
        addr = conf.addr()
        self.assertEqual(addr, ('127.0.0.1', 8675))

    def test_port_as_string(self):
        conf = self._makeOne('localhost', '5001')
        addr = conf.addr()
        self.assertEqual(addr, ('localhost', 5001))
        
    def test_create(self):
        conf = self._makeOne('127.0.0.1', 8675)
        sock = conf.create()
        reuse = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        self.assertTrue(reuse)
        sock.close
        
class UnixStreamSocketConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        return UnixStreamSocketConfig
        
    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_url(self):
        conf = self._makeOne('/tmp/foo.sock')
        self.assertEqual(conf.url, 'unix:///tmp/foo.sock')
            
    def test_repr(self):
        conf = self._makeOne('/tmp/foo.sock')
        s = repr(conf)
        self.assertTrue(s.startswith(
            '<supervisor.datatypes.UnixStreamSocketConfig at'), s)
        self.assertTrue(s.endswith('for unix:///tmp/foo.sock>'), s)

    def test_get_addr(self):
        conf = self._makeOne('/tmp/foo.sock')
        addr = conf.addr()
        self.assertEqual(addr, '/tmp/foo.sock')
        
    def test_create(self):
        (tf_fd, tf_name) = tempfile.mkstemp()
        conf = self._makeOne(tf_name)
        os.close(tf_fd)
        sock = conf.create()
        self.assertFalse(os.path.exists(tf_name))
        sock.close

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
