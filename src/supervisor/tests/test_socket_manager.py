"""Test suite for supervisor.socket_manager"""

import sys
import os
import unittest
import socket
import tempfile

from supervisor.tests.base import DummySocket
from supervisor.tests.base import DummySocketConfig
from supervisor.datatypes import UnixStreamSocketConfig
from supervisor.datatypes import InetStreamSocketConfig

class SocketManagerTest(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.socket_manager import SocketManager
        return SocketManager

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_get_config(self):
        conf = DummySocketConfig(2)
        sock_manager = self._makeOne(conf)
        self.assertEqual(conf, sock_manager.config())

    def test_tcp_w_hostname(self):
        conf = InetStreamSocketConfig('localhost', 12345)
        sock_manager = self._makeOne(conf)
        self.assertEqual(sock_manager.socket_config, conf)
        sock = sock_manager.get_socket()
        self.assertEqual(sock.getsockname(), ('127.0.0.1', 12345))
        sock_manager.close()

    def test_tcp_w_ip(self):
        conf = InetStreamSocketConfig('127.0.0.1', 12345)
        sock_manager = self._makeOne(conf)
        self.assertEqual(sock_manager.socket_config, conf)
        sock = sock_manager.get_socket()
        self.assertEqual(sock.getsockname(), ('127.0.0.1', 12345))
        sock_manager.close()

    def test_unix(self):
        (tf_fd, tf_name) = tempfile.mkstemp();
        conf = UnixStreamSocketConfig(tf_name)
        sock_manager = self._makeOne(conf)
        self.assertEqual(sock_manager.socket_config, conf)
        sock = sock_manager.get_socket()
        self.assertEqual(sock.getsockname(), tf_name)
        sock_manager.close()
        os.close(tf_fd)
        
    def test_get_socket(self):
        conf = DummySocketConfig(2)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        sock2 = sock_manager.get_socket()
        self.assertEqual(sock, sock2)
        sock_manager.close()
        sock3 = sock_manager.get_socket()
        self.assertNotEqual(sock, sock3)

    def test_prepare_socket(self):
        conf = DummySocketConfig(1)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        self.assertTrue(sock_manager.prepared)
        self.assertTrue(sock.bind_called)
        self.assertEqual(sock.bind_addr, 'dummy addr')
        self.assertTrue(sock.listen_called)
        self.assertEqual(sock.listen_backlog, socket.SOMAXCONN)
        self.assertFalse(sock.close_called)

    def test_close(self):
        conf = DummySocketConfig(6)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        self.assertFalse(sock.close_called)
        self.assertTrue(sock_manager.prepared)
        sock_manager.close()
        self.assertFalse(sock_manager.prepared)
        self.assertTrue(sock.close_called)
    
    def test_tcp_socket_already_taken(self):
        conf = InetStreamSocketConfig('127.0.0.1', 12345)
        sock_manager = self._makeOne(conf)
        sock_manager.get_socket()
        sock_manager2 = self._makeOne(conf)
        self.assertRaises(socket.error, sock_manager2.prepare_socket)
        sock_manager.close()
        
    def test_unix_bad_sock(self):
        conf = UnixStreamSocketConfig('/notthere/foo.sock')
        sock_manager = self._makeOne(conf)
        self.assertRaises(socket.error, sock_manager.get_socket)
        sock_manager.close()
            
def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')