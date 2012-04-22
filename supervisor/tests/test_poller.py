import sys
import unittest
import errno
import select

from supervisor.poller import Poller, KQueuePoller
from supervisor.tests.base import DummyOptions

class KQueuePollerTests(unittest.TestCase):

    def _makeOne(self, options):
        return KQueuePoller(options)

    def test_register_readable(self):
        kqueue = DummyKQueue()
        poller = self._makeOne(DummyOptions())
        poller._kqueue = kqueue
        poller.register_readable(6)
        self.assertEqual(len(kqueue.registered_kevents), 1)
        self.assertReadEventAdded(kqueue, kqueue.registered_kevents[0], 6)

    def test_register_writable(self):
        kqueue = DummyKQueue()
        poller = self._makeOne(DummyOptions())
        poller._kqueue = kqueue
        poller.register_writable(7)
        self.assertEqual(len(kqueue.registered_kevents), 1)
        self.assertWriteEventAdded(kqueue, kqueue.registered_kevents[0], 7)

    def test_poll_returns_readables_and_writables(self):
        kqueue = DummyKQueue(result=[(6, select.KQ_FILTER_READ),
                                     (7, select.KQ_FILTER_READ),
                                     (8, select.KQ_FILTER_WRITE)])
        poller = self._makeOne(DummyOptions())
        poller._kqueue = kqueue
        poller.register_readable(6)
        poller.register_readable(7)
        poller.register_writable(8)
        readables, writables = poller.poll(1000)
        self.assertEqual(readables, [6,7])
        self.assertEqual(writables, [8])

    def test_poll_ignores_eintr(self):
        kqueue = DummyKQueue(raise_errno=errno.EINTR)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = kqueue
        poller.register_readable(6)
        poller.poll(1000)
        self.assertEqual(options.logger.data[0], 'EINTR encountered in poll')

    def test_poll_uncaught_exception(self):
        kqueue = DummyKQueue(raise_errno=errno.EBADF)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = kqueue
        poller.register_readable(6)
        self.assertRaises(OSError, poller.poll, (1000,))

    def assertReadEventAdded(self, kqueue, kevent, fd):
        self.assertEventAdded(kqueue, kevent, fd, select.KQ_FILTER_READ)

    def assertWriteEventAdded(self, kqueue, kevent, fd):
        self.assertEventAdded(kqueue, kevent, fd, select.KQ_FILTER_WRITE)

    def assertEventAdded(self, kqueue, kevent, fd, filter_spec):
        self.assertEqual(kevent.ident, fd)
        self.assertEqual(kevent.filter, filter_spec)
        self.assertEqual(kevent.flags, select.KQ_EV_ADD)


class PollerPollTests(unittest.TestCase):

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
        select_poll = DummySelectPoll(result=[(6, select.POLLIN),
                                              (7, select.POLLPRI),
                                              (8, select.POLLOUT),
                                              (9, select.POLLHUP)])
        poller = self._makeOne(DummyOptions())
        poller._poller = select_poll
        poller.register_readable(6)
        poller.register_readable(7)
        poller.register_writable(8)
        poller.register_readable(9)
        readables, writables = poller.poll(1000)
        self.assertEqual(readables, [6,7,9])
        self.assertEqual(writables, [8])

    def test_poll_ignores_eintr(self):
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

class DummySelectPoll(object):
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


class DummyKQueue(object):
    def __init__(self, result=None, raise_errno=None):
        self.result = result or []
        self.errno = raise_errno
        self.registered_kevents = []
        self.registered_flags = []

    def control(self, kevents, max_events, timeout=None):
        if kevents is None:    # being called on poll()
            self.assert_max_events_on_poll(max_events)
            self.raise_error()
            return self.build_result()

        self.assert_max_events_on_register(max_events)
        self.registered_kevents.extend(kevents)

    def raise_error(self):
        if self.errno:
            ex = OSError()
            ex.errno = self.errno
            raise ex

    def build_result(self):
        return [FakeKEvent(ident, filter) for ident,filter in self.result]

    def assert_max_events_on_poll(self, max_events):
        assert max_events == KQueuePoller.max_events, (
            "`max_events` parameter of `kqueue.control() should be %d"
            % KQueuePoller.max_events)

    def assert_max_events_on_register(self, max_events):
        assert max_events == 0, (
            "`max_events` parameter of `kqueue.control()` should be 0 on register")

class FakeKEvent(object):
    def __init__(self, ident, filter):
        self.ident = ident
        self.filter = filter


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
