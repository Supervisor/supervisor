import sys
import unittest
import errno
import select

from supervisor.poller import Poller
from supervisor.tests.base import DummyOptions

class PollerTests(unittest.TestCase):

    def _makeOne(self, options):
        return Poller(options)

    def test_register_readable(self):
        select_poll = DummySelectPoll()
        poller = self._makeOne(DummyOptions())
        poller._poller = select_poll
        poller.register_readable(6)
        poller.register_readable(7)
        self.assertEqual(select_poll.registered_as_readable, [6,7])

    def test_register_writable(self):
        select_poll = DummySelectPoll()
        poller = self._makeOne(DummyOptions())
        poller._poller = select_poll
        poller.register_writable(6)
        self.assertEqual(select_poll.registered_as_writable, [6])

    def test_poll_returns_readables_and_writables(self):
        select_poll = DummySelectPoll(result=[(6, Poller.READ),
                                              (7, Poller.READ),
                                              (8, Poller.WRITE)])
        poller = self._makeOne(DummyOptions())
        poller._poller = select_poll
        poller.register_readable(6)
        poller.register_readable(7)
        poller.register_writable(8)
        readables, writables = poller.poll(1000)
        self.assertEqual(readables, [6,7])
        self.assertEqual(writables, [8])

    def test_poll_ignore_eintr(self):
        select_poll = DummySelectPoll(error=errno.EINTR)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._poller = select_poll
        poller.register_readable(9)
        poller.poll(1000)
        self.assertEqual(options.logger.data[0], 'EINTR encountered in poll')

    def test_poll_uncaught_exception(self):
        select_poll = DummySelectPoll(error=errno.EBADF)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._poller = select_poll
        poller.register_readable(9)
        self.assertRaises(select.error, poller.poll, (1000,))

    def test_poll_ignores_and_unregisters_closed_fd(self):
        select_poll = DummySelectPoll(result=[(6, select.POLLNVAL),
                                              (7, Poller.READ)])
        poller = self._makeOne(DummyOptions())
        poller._poller = select_poll
        poller.register_readable(6)
        poller.register_readable(7)
        readables, writables = poller.poll(1000)
        self.assertEqual(readables, [7])
        self.assertEqual(select_poll.unregistered, [6])

class DummySelectPoll:
    def __init__(self, result=None, error=None):
        self.result = result or []
        self.error = error
        self.registered_as_readable = []
        self.registered_as_writable = []
        self.unregistered = []

    def register(self, fd, eventmask):
        if eventmask == Poller.READ:
            self.registered_as_readable.append(fd)
        elif eventmask == Poller.WRITE:
            self.registered_as_writable.append(fd)
        else:
            raise ValueError("Registered a fd on unknown eventmask: '{0}'".format(eventmask))

    def unregister(self, fd):
        self.unregistered.append(fd)

    def poll(self, timeout):
        if self.error:
            raise select.error(self.error)
        return self.result


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
