"""Test suite for supervisor.socket_manager"""

import gc
import sys
import os
import unittest
import socket
import tempfile

try:
    import __pypy__
except ImportError:
    __pypy__ = None

from supervisor.tests.base import DummySocketConfig
from supervisor.tests.base import DummyLogger
from supervisor.datatypes import UnixStreamSocketConfig
from supervisor.datatypes import InetStreamSocketConfig

class Subject:

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
        proxy = self._makeOne(Subject())
        self.assertEqual(5, proxy.getValue())

    def test_on_delete(self):
        proxy = self._makeOne(Subject(), on_delete=self.setOnDeleteCalled)
        self.assertEqual(5, proxy.getValue())
        proxy = None
        gc_collect()
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
        self.assertEqual(1, ctr.get_count())
        ctr.increment()
        self.assertTrue(self.running)
        self.assertEqual(2, ctr.get_count())
        ctr.decrement()
        self.assertTrue(self.running)
        self.assertEqual(1, ctr.get_count())
        ctr.decrement()
        self.assertFalse(self.running)
        self.assertEqual(0, ctr.get_count())

    def test_decr_at_zero_raises_error(self):
        ctr = self._makeOne(on_zero=self.stop,on_non_zero=self.start)
        self.assertRaises(Exception, ctr.decrement)

class SocketManagerTest(unittest.TestCase):

    def tearDown(self):
        gc_collect()

    def _getTargetClass(self):
        from supervisor.socket_manager import SocketManager
        return SocketManager

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_repr(self):
        conf = DummySocketConfig(2)
        sock_manager = self._makeOne(conf)
        expected = "<%s at %s for %s>" % (
            sock_manager.__class__, id(sock_manager), conf.url)
        self.assertEqual(repr(sock_manager), expected)

    def test_get_config(self):
        conf = DummySocketConfig(2)
        sock_manager = self._makeOne(conf)
        self.assertEqual(conf, sock_manager.config())

    def test_tcp_w_hostname(self):
        conf = InetStreamSocketConfig('localhost', 51041)
        sock_manager = self._makeOne(conf)
        self.assertEqual(sock_manager.socket_config, conf)
        sock = sock_manager.get_socket()
        self.assertEqual(sock.getsockname(), ('127.0.0.1', 51041))

    def test_tcp_w_ip(self):
        conf = InetStreamSocketConfig('127.0.0.1', 51041)
        sock_manager = self._makeOne(conf)
        self.assertEqual(sock_manager.socket_config, conf)
        sock = sock_manager.get_socket()
        self.assertEqual(sock.getsockname(), ('127.0.0.1', 51041))

    def test_unix(self):
        (tf_fd, tf_name) = tempfile.mkstemp()
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
        # Assert that sockets are created on demand
        self.assertFalse(sock_manager.is_prepared())
        # Get two socket references
        sock = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared()) #socket created on demand
        sock_id = id(sock._get())
        sock2 = sock_manager.get_socket()
        sock2_id = id(sock2._get())
        # Assert that they are not the same proxy object
        self.assertNotEqual(sock, sock2)
        # Assert that they are the same underlying socket
        self.assertEqual(sock_id, sock2_id)
        # Socket not actually closed yet b/c ref ct is 2
        self.assertEqual(2, sock_manager.get_socket_ref_count())
        self.assertTrue(sock_manager.is_prepared())
        self.assertFalse(sock_manager.socket.close_called)
        sock = None
        gc_collect()
        # Socket not actually closed yet b/c ref ct is 1
        self.assertTrue(sock_manager.is_prepared())
        self.assertFalse(sock_manager.socket.close_called)
        sock2 = None
        gc_collect()
        # Socket closed
        self.assertFalse(sock_manager.is_prepared())
        self.assertTrue(sock_manager.socket.close_called)

        # Get a new socket reference
        sock3 = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared())
        sock3_id = id(sock3._get())
        # Assert that it is not the same socket
        self.assertNotEqual(sock_id, sock3_id)
        # Drop ref ct to zero
        del sock3
        gc_collect()
        # Now assert that socket is closed
        self.assertFalse(sock_manager.is_prepared())
        self.assertTrue(sock_manager.socket.close_called)

    def test_logging(self):
        conf = DummySocketConfig(1)
        logger = DummyLogger()
        sock_manager = self._makeOne(conf, logger=logger)
        # socket open
        sock = sock_manager.get_socket()
        self.assertEqual(len(logger.data), 1)
        self.assertEqual('Creating socket %s' % repr(conf), logger.data[0])
        # socket close
        del sock
        gc_collect()
        self.assertEqual(len(logger.data), 2)
        self.assertEqual('Closing socket %s' % repr(conf), logger.data[1])

    def test_prepare_socket(self):
        conf = DummySocketConfig(1)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared())
        self.assertFalse(sock.bind_called)
        self.assertTrue(sock.listen_called)
        self.assertFalse(sock.close_called)

    def test_prepare_socket_uses_configured_backlog(self):
        conf = DummySocketConfig(1, backlog=42)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared())
        self.assertEqual(sock.listen_backlog, conf.get_backlog())

    def test_prepare_socket_uses_somaxconn_if_no_backlog_configured(self):
        conf = DummySocketConfig(1, backlog=None)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        self.assertTrue(sock_manager.is_prepared())
        self.assertEqual(sock.listen_backlog, socket.SOMAXCONN)

    def test_tcp_socket_already_taken(self):
        conf = InetStreamSocketConfig('127.0.0.1', 51041)
        sock_manager = self._makeOne(conf)
        sock = sock_manager.get_socket()
        sock_manager2 = self._makeOne(conf)
        self.assertRaises(socket.error, sock_manager2.get_socket)
        del sock

    def test_unix_bad_sock(self):
        conf = UnixStreamSocketConfig('/notthere/foo.sock')
        sock_manager = self._makeOne(conf)
        self.assertRaises(socket.error, sock_manager.get_socket)

    def test_close_requires_prepared_socket(self):
        conf = InetStreamSocketConfig('127.0.0.1', 51041)
        sock_manager = self._makeOne(conf)
        self.assertFalse(sock_manager.is_prepared())
        try:
            sock_manager._close()
            self.fail()
        except Exception as e:
            self.assertEqual(e.args[0], 'Socket has not been prepared')

def gc_collect():
    if __pypy__ is not None:
        gc.collect()
        gc.collect()
        gc.collect()

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
