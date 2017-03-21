import sys
import unittest
import errno
import select
from mock import Mock

from supervisor.poller import SelectPoller, PollPoller, KQueuePoller
from supervisor.poller import implements_poll, implements_kqueue
from supervisor.tests.base import DummyOptions

# this base class is used instead of unittest.TestCase to hide
# a TestCase subclass from test runner when the implementation is
# not available
SkipTestCase = object

class BasePollerTests(unittest.TestCase):
    def _makeOne(self, options):
        from supervisor.poller import BasePoller
        return BasePoller(options)

    def test_register_readable(self):
        inst = self._makeOne(None)
        self.assertRaises(NotImplementedError, inst.register_readable, None)

    def test_register_writable(self):
        inst = self._makeOne(None)
        self.assertRaises(NotImplementedError, inst.register_writable, None)

    def test_unregister_readable(self):
        inst = self._makeOne(None)
        self.assertRaises(NotImplementedError, inst.unregister_readable, None)

    def test_unregister_writable(self):
        inst = self._makeOne(None)
        self.assertRaises(NotImplementedError, inst.unregister_writable, None)

    def test_poll(self):
        inst = self._makeOne(None)
        self.assertRaises(NotImplementedError, inst.poll, None)

    def test_before_daemonize(self):
        inst = self._makeOne(None)
        self.assertEqual(inst.before_daemonize(), None)

    def test_after_daemonize(self):
        inst = self._makeOne(None)
        self.assertEqual(inst.after_daemonize(), None)

class SelectPollerTests(unittest.TestCase):

    def _makeOne(self, options):
        return SelectPoller(options)

    def test_register_readable(self):
        poller = self._makeOne(DummyOptions())
        poller.register_readable(6)
        poller.register_readable(7)
        self.assertEqual(sorted(poller.readables), [6,7])

    def test_register_writable(self):
        poller = self._makeOne(DummyOptions())
        poller.register_writable(6)
        poller.register_writable(7)
        self.assertEqual(sorted(poller.writables), [6,7])

    def test_unregister_readable(self):
        poller = self._makeOne(DummyOptions())
        poller.register_readable(6)
        poller.register_readable(7)
        poller.register_writable(8)
        poller.register_writable(9)
        poller.unregister_readable(6)
        poller.unregister_readable(9)
        poller.unregister_readable(100)  # not registered, ignore error
        self.assertEqual(list(poller.readables), [7])
        self.assertEqual(list(poller.writables), [8, 9])

    def test_unregister_writable(self):
        poller = self._makeOne(DummyOptions())
        poller.register_readable(6)
        poller.register_readable(7)
        poller.register_writable(8)
        poller.register_writable(6)
        poller.unregister_writable(7)
        poller.unregister_writable(6)
        poller.unregister_writable(100)  # not registered, ignore error
        self.assertEqual(list(poller.readables), [6, 7])
        self.assertEqual(list(poller.writables), [8])

    def test_poll_returns_readables_and_writables(self):
        _select = DummySelect(result={'readables': [6],
                                      'writables': [8]})
        poller = self._makeOne(DummyOptions())
        poller._select = _select
        poller.register_readable(6)
        poller.register_readable(7)
        poller.register_writable(8)
        readables, writables = poller.poll(1)
        self.assertEqual(readables, [6])
        self.assertEqual(writables, [8])

    def test_poll_ignores_eintr(self):
        _select = DummySelect(error=errno.EINTR)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._select = _select
        poller.register_readable(6)
        poller.poll(1)
        self.assertEqual(options.logger.data[0], 'EINTR encountered in poll')

    def test_poll_ignores_ebadf(self):
        _select = DummySelect(error=errno.EBADF)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._select = _select
        poller.register_readable(6)
        poller.poll(1)
        self.assertEqual(options.logger.data[0], 'EBADF encountered in poll')
        self.assertEqual(list(poller.readables), [])
        self.assertEqual(list(poller.writables), [])

    def test_poll_uncaught_exception(self):
        _select = DummySelect(error=errno.EPERM)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._select = _select
        poller.register_readable(6)
        self.assertRaises(select.error, poller.poll, 1)

if implements_kqueue():
    KQueuePollerTestsBase = unittest.TestCase
else:
    KQueuePollerTestsBase = SkipTestCase

class KQueuePollerTests(KQueuePollerTestsBase):

    def _makeOne(self, options):
        return KQueuePoller(options)

    def test_register_readable(self):
        kqueue = DummyKQueue()
        poller = self._makeOne(DummyOptions())
        poller._kqueue = kqueue
        poller.register_readable(6)
        self.assertEqual(list(poller.readables), [6])
        self.assertEqual(len(kqueue.registered_kevents), 1)
        self.assertReadEventAdded(kqueue.registered_kevents[0], 6)

    def test_register_writable(self):
        kqueue = DummyKQueue()
        poller = self._makeOne(DummyOptions())
        poller._kqueue = kqueue
        poller.register_writable(7)
        self.assertEqual(list(poller.writables), [7])
        self.assertEqual(len(kqueue.registered_kevents), 1)
        self.assertWriteEventAdded(kqueue.registered_kevents[0], 7)

    def test_unregister_readable(self):
        kqueue = DummyKQueue()
        poller = self._makeOne(DummyOptions())
        poller._kqueue = kqueue
        poller.register_writable(7)
        poller.register_readable(8)
        poller.unregister_readable(7)
        poller.unregister_readable(8)
        poller.unregister_readable(100)  # not registered, ignore error
        self.assertEqual(list(poller.writables), [7])
        self.assertEqual(list(poller.readables), [])
        self.assertWriteEventAdded(kqueue.registered_kevents[0], 7)
        self.assertReadEventAdded(kqueue.registered_kevents[1], 8)
        self.assertReadEventDeleted(kqueue.registered_kevents[2], 7)
        self.assertReadEventDeleted(kqueue.registered_kevents[3], 8)

    def test_unregister_writable(self):
        kqueue = DummyKQueue()
        poller = self._makeOne(DummyOptions())
        poller._kqueue = kqueue
        poller.register_writable(7)
        poller.register_readable(8)
        poller.unregister_writable(7)
        poller.unregister_writable(8)
        poller.unregister_writable(100)  # not registered, ignore error
        self.assertEqual(list(poller.writables), [])
        self.assertEqual(list(poller.readables), [8])
        self.assertWriteEventAdded(kqueue.registered_kevents[0], 7)
        self.assertReadEventAdded(kqueue.registered_kevents[1], 8)
        self.assertWriteEventDeleted(kqueue.registered_kevents[2], 7)
        self.assertWriteEventDeleted(kqueue.registered_kevents[3], 8)

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
        kqueue = DummyKQueue(raise_errno_poll=errno.EINTR)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = kqueue
        poller.register_readable(6)
        poller.poll(1000)
        self.assertEqual(options.logger.data[0], 'EINTR encountered in poll')

    def test_register_readable_and_writable_ignores_ebadf(self):
        _kqueue = DummyKQueue(raise_errno_register=errno.EBADF)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = _kqueue
        poller.register_readable(6)
        poller.register_writable(7)
        self.assertEqual(options.logger.data[0],
                         'EBADF encountered in kqueue. Invalid file descriptor 6')
        self.assertEqual(options.logger.data[1],
                         'EBADF encountered in kqueue. Invalid file descriptor 7')

    def test_register_uncaught_exception(self):
        _kqueue = DummyKQueue(raise_errno_register=errno.ENOMEM)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = _kqueue
        self.assertRaises(OSError, poller.register_readable, 5)

    def test_poll_uncaught_exception(self):
        kqueue = DummyKQueue(raise_errno_poll=errno.EINVAL)
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = kqueue
        poller.register_readable(6)
        self.assertRaises(OSError, poller.poll, 1000)

    def test_before_daemonize_closes_kqueue(self):
        mock_kqueue = Mock()
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = mock_kqueue
        poller.before_daemonize()
        mock_kqueue.close.assert_called_once_with()
        self.assertEqual(poller._kqueue, None)

    def test_after_daemonize_restores_kqueue(self):
        options = DummyOptions()
        poller = self._makeOne(options)
        poller.readables = [1]
        poller.writables = [3]
        poller.register_readable = Mock()
        poller.register_writable = Mock()
        poller.after_daemonize()
        self.assertTrue(isinstance(poller._kqueue, select.kqueue))
        poller.register_readable.assert_called_with(1)
        poller.register_writable.assert_called_with(3)

    def test_close_closes_kqueue(self):
        mock_kqueue = Mock()
        options = DummyOptions()
        poller = self._makeOne(options)
        poller._kqueue = mock_kqueue
        poller.close()
        mock_kqueue.close.assert_called_once_with()
        self.assertEqual(poller._kqueue, None)

    def assertReadEventAdded(self, kevent, fd):
        self.assertKevent(kevent, fd, select.KQ_FILTER_READ, select.KQ_EV_ADD)

    def assertWriteEventAdded(self, kevent, fd):
        self.assertKevent(kevent, fd, select.KQ_FILTER_WRITE, select.KQ_EV_ADD)

    def assertReadEventDeleted(self, kevent, fd):
        self.assertKevent(kevent, fd, select.KQ_FILTER_READ, select.KQ_EV_DELETE)

    def assertWriteEventDeleted(self, kevent, fd):
        self.assertKevent(kevent, fd, select.KQ_FILTER_WRITE, select.KQ_EV_DELETE)

    def assertKevent(self, kevent, ident, filter, flags):
        self.assertEqual(kevent.ident, ident)
        self.assertEqual(kevent.filter, filter)
        self.assertEqual(kevent.flags, flags)

if implements_poll():
    PollerPollTestsBase = unittest.TestCase
else:
    PollerPollTestsBase = SkipTestCase

class PollerPollTests(PollerPollTestsBase):

    def _makeOne(self, options):
        return PollPoller(options)

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
        self.assertRaises(select.error, poller.poll, 1000)

    def test_poll_ignores_and_unregisters_closed_fd(self):
        select_poll = DummySelectPoll(result=[(6, select.POLLNVAL),
                                              (7, select.POLLPRI)])
        poller = self._makeOne(DummyOptions())
        poller._poller = select_poll
        poller.register_readable(6)
        poller.register_readable(7)
        readables, writables = poller.poll(1000)
        self.assertEqual(readables, [7])
        self.assertEqual(select_poll.unregistered, [6])

class DummySelect(object):
    '''
    Fake implementation of select.select()
    '''
    def __init__(self, result=None, error=None):
        result = result or {}
        self.readables = result.get('readables', [])
        self.writables = result.get('writables', [])
        self.error = error

    def select(self, r, w, x, timeout):
        if self.error:
            raise select.error(self.error)
        return self.readables, self.writables, []

class DummySelectPoll(object):
    '''
    Fake implementation of select.poll()
    '''
    def __init__(self, result=None, error=None):
        self.result = result or []
        self.error = error
        self.registered_as_readable = []
        self.registered_as_writable = []
        self.unregistered = []

    def register(self, fd, eventmask):
        if eventmask == select.POLLIN | select.POLLPRI | select.POLLHUP:
            self.registered_as_readable.append(fd)
        elif eventmask == select.POLLOUT:
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
    '''
    Fake implementation of select.kqueue()
    '''
    def __init__(self, result=None, raise_errno_poll=None, raise_errno_register=None):
        self.result = result or []
        self.errno_poll = raise_errno_poll
        self.errno_register = raise_errno_register
        self.registered_kevents = []
        self.registered_flags = []

    def control(self, kevents, max_events, timeout=None):
        if kevents is None:    # being called on poll()
            self.assert_max_events_on_poll(max_events)
            self.raise_error(self.errno_poll)
            return self.build_result()

        self.assert_max_events_on_register(max_events)
        self.raise_error(self.errno_register)
        self.registered_kevents.extend(kevents)

    def raise_error(self, err):
        if not err: return
        ex = OSError()
        ex.errno = err
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
