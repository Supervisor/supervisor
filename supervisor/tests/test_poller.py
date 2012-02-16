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
        select_poll = DummySelectPoll(result={'readables': [6,7], 'writables': [7,8]})
        poller = self._makeOne(DummyOptions())
        poller._poller = select_poll
        poller.register_readable(6)
        poller.register_readable(7)
        poller.register_writable(8)
        readables, writables = poller.poll(1000)
        self.assertEqual(readables, [6,7])
        self.assertEqual(writables, [7,8])

    def test_poll_ignore_eintr(self):
        select_poll = DummySelectPoll(error=errno.EINTR)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._poller = select_poll
        poller.register_readable(9)
        poller.poll(1000)
        self.assertEqual(options.logger.data[0], 'EINTR encountered in select')

    def test_poll_uncaught_exception(self):
        select_poll = DummySelectPoll(error=errno.EBADF)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._poller = select_poll
        poller.register_readable(9)
        self.assertRaises(select.error, poller.poll, (1000,))


class DummySelectPoll:
    def __init__(self, result=None, error=None):
        self.result = result or {'readables': [], 'writables': []}
        self.error = error
        self.registered_as_readable = []
        self.registered_as_writable = []

    def register(self, fd, eventmask):
        if eventmask == Poller.READ:
            self.registered_as_readable.append(fd)
        elif eventmask == Poller.WRITE:
            self.registered_as_writable.append(fd)
        else:
            raise ValueError("Registered a fd on unknown eventmask: '{0}'".format(eventmask))

    def poll(self, timeout):
        self._raise_error_if_defined()
        return self._format_expected_result()

    def _raise_error_if_defined(self):
        if self.error:
            raise select.error(self.error)

    def _format_expected_result(self):
        fds = []
        for fd in self.result['readables']:
            fds.append((fd, Poller.READ))
        for fd in self.result['writables']:
            fds.append((fd, Poller.WRITE))
        return fds


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
