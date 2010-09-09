"""Test suite for supervisor.socket_manager"""

import sys
import os
import unittest
import socket
import tempfile

from supervisor.tests.base import DummySocketConfig
from supervisor.datatypes import UnixStreamSocketConfig
from supervisor.datatypes import InetStreamSocketConfig

class TestObject:
    
    def __init__(self):
        self.value = 5
    
    def getValue(self):
        return self.value
        
    def setValue(self, val):
        self.value = val

class ProxyTest(unittest.TestCase):
    
    def setUp(self):
        self.on_deleteCalled = False
    
    def _getTargetClass(self):
        from supervisor.socket_manager import Proxy
        return Proxy

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)
    
    def setOnDeleteCalled(self):
        self.on_deleteCalled = True
    
    def test_proxy_getattr(self):
        proxy = self._makeOne(TestObject())
        self.assertEquals(5, proxy.getValue())
        
    def test_on_delete(self):
        proxy = self._makeOne(TestObject(), on_delete=self.setOnDeleteCalled)
        self.assertEquals(5, proxy.getValue())
        proxy = None
        self.assertTrue(self.on_deleteCalled)
        
class ReferenceCounterTest(unittest.TestCase):

    def setUp(self):
        self.running = False

    def start(self):
        self.running = True
        
    def stop(self):
        self.running = False

    def _getTargetClass(self):
        from supervisor.socket_manager import ReferenceCounter
        return ReferenceCounter

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_incr_and_decr(self):
        ctr = self._makeOne(on_zero=self.stop,on_non_zero=self.start)
        self.assertFalse(self.running)
        ctr.increment()
        self.assertTrue(self.running)
        self.assertEquals(1, ctr.get_count())
        ctr.increment()
        self.assertTrue(self.running)
        self.assertEquals(2, ctr.get_count())
        ctr.decrement()
        self.assertTrue(self.running)
        self.assertEquals(1, ctr.get_count())
        ctr.decrement()
        self.assertFalse(self.running)
        self.assertEquals(0, ctr.get_count())
    
    def test_decr_at_zero_raises_error(self):
        ctr = self._makeOne(on_zero=self.stop,on_non_zero=self.start)
        self.assertRaises(Exception, ctr.decrement)
        
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

    def test_tcp_w_ip(self):
        conf = InetStreamSocketConfig('127.0.0.1', 12345)
        sock_manager = self._makeOne(conf)
        self.assertEqual(sock_manager.socket_config, conf)
        sock = sock_manager.get_socket()
        self.assertEqual(sock.getsockname(), ('127.0.0.1', 12345))

    def test_unix(self):
        (tf_fd, tf_name) = tempfile.mkstemp();
        conf = UnixStreamSocketConfig(tf_name)
        sock_manager = self._makeOne(conf)
        self.assertEqual(sock_manager.socket_config, conf)
        sock = sock_manager.get_socket()
        self.assertEqual(sock.getsockname(), tf_name)
        sock = None
        os.close(tf_fd)
        
    def test_socket_lifecycle(self):
        conf = DummySocketConfig(2)
        sock_manager = self._makeOne(conf)
        #Assert that sockets are created on demand
        self.assertFalse(sock_manager.is_prepared())
        #Get two socket references
        sock = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared()) #socket created on demand
        sock_id = id(sock._get())
        sock2 = sock_manager.get_socket()
        sock2_id = id(sock2._get())
        #Assert that they are not the same proxy object
        self.assertNotEqual(sock, sock2)
        #Assert that they are the same underlying socket
        self.assertEqual(sock_id, sock2_id)
        #Socket not actually closed yet b/c ref ct is 2
        self.assertTrue(sock_manager.is_prepared())
        self.assertFalse(sock_manager.socket.close_called)
        sock = None
        #Socket not actually closed yet b/c ref ct is 1
        self.assertTrue(sock_manager.is_prepared())
        self.assertFalse(sock_manager.socket.close_called)
        sock2 = None
        #Socket closed
        self.assertFalse(sock_manager.is_prepared())
        self.assertTrue(sock_manager.socket.close_called)
        
        #Get a new socket reference
        sock3 = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared())
        sock3_id = id(sock3._get())
        #Assert that it is not the same socket
        self.assertNotEqual(sock_id, sock3_id)
        #Drop ref ct to zero
        del sock3
        #Now assert that socket is closed
        self.assertFalse(sock_manager.is_prepared())
        self.assertTrue(sock_manager.socket.close_called)

    def test_prepare_socket(self):
        conf = DummySocketConfig(1)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared())
        self.assertFalse(sock.bind_called)
        self.assertTrue(sock.listen_called)
        self.assertEqual(sock.listen_backlog, socket.SOMAXCONN)
        self.assertFalse(sock.close_called)
    
    def test_tcp_socket_already_taken(self):
        conf = InetStreamSocketConfig('127.0.0.1', 12345)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        sock_manager2 = self._makeOne(conf)
        self.assertRaises(socket.error, sock_manager2.get_socket)
        sock = None
        
    def test_unix_bad_sock(self):
        conf = UnixStreamSocketConfig('/notthere/foo.sock')
        sock_manager = self._makeOne(conf)
        self.assertRaises(socket.error, sock_manager.get_socket)        

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
