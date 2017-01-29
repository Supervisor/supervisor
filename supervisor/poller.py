import select
import errno

class BasePoller:

    def __init__(self, options):
        self.options = options
        self.initialize()

    def initialize(self):
        pass

    def register_readable(self, fd):
        raise NotImplementedError

    def register_writable(self, fd):
        raise NotImplementedError

    def unregister_readable(self, fd):
        raise NotImplementedError

    def unregister_writable(self, fd):
        raise NotImplementedError

    def poll(self, timeout):
        raise NotImplementedError

    def before_daemonize(self):
        pass

    def after_daemonize(self):
        pass

    def close(self):
        pass


class SelectPoller(BasePoller):

    def initialize(self):
        self._select = select
        self._init_fdsets()

    def register_readable(self, fd):
        self.readables.add(fd)

    def register_writable(self, fd):
        self.writables.add(fd)

    def unregister_readable(self, fd):
        self.readables.discard(fd)

    def unregister_writable(self, fd):
        self.writables.discard(fd)

    def unregister_all(self):
        self._init_fdsets()

    def poll(self, timeout):
        try:
            r, w, x = self._select.select(
                self.readables,
                self.writables,
                [], timeout
                )
        except select.error, err:
            if err.args[0] == errno.EINTR:
                self.options.logger.blather('EINTR encountered in poll')
                return [], []
            if err.args[0] == errno.EBADF:
                self.options.logger.blather('EBADF encountered in poll')
                self.unregister_all()
                return [], []
            raise
        return r, w

    def _init_fdsets(self):
        self.readables = set()
        self.writables = set()

class PollPoller(BasePoller):

    def initialize(self):
        self._poller = select.poll()
        self.READ = select.POLLIN | select.POLLPRI | select.POLLHUP
        self.WRITE = select.POLLOUT
        self.readables = set()
        self.writables = set()

    def register_readable(self, fd):
        self._poller.register(fd, self.READ)
        self.readables.add(fd)

    def register_writable(self, fd):
        self._poller.register(fd, self.WRITE)
        self.writables.add(fd)

    def unregister_readable(self, fd):
        self.readables.discard(fd)
        self._poller.unregister(fd)
        if fd in self.writables:
            self._poller.register(fd, self.WRITE)

    def unregister_writable(self, fd):
        self.writables.discard(fd)
        self._poller.unregister(fd)
        if fd in self.readables:
            self._poller.register(fd, self.READ)

    def poll(self, timeout):
        fds = self._poll_fds(timeout)
        readables, writables = [], []
        for fd, eventmask in fds:
            if self._ignore_invalid(fd, eventmask):
                continue
            if eventmask & self.READ:
                readables.append(fd)
            if eventmask & self.WRITE:
                writables.append(fd)
        return readables, writables

    def _poll_fds(self, timeout):
        try:
            return self._poller.poll(timeout * 1000)
        except select.error, err:
            if err.args[0] == errno.EINTR:
                self.options.logger.blather('EINTR encountered in poll')
                return []
            raise

    def _ignore_invalid(self, fd, eventmask):
        if eventmask & select.POLLNVAL:
            # POLLNVAL means `fd` value is invalid, not open.
            # When a process quits it's `fd`s are closed so there
            # is no more reason to keep this `fd` registered
            # If the process restarts it's `fd`s are registered again
            self._poller.unregister(fd)
            self.readables.discard(fd)
            self.writables.discard(fd)
            return True
        return False

class KQueuePoller(BasePoller):
    '''
    Wrapper for select.kqueue()/kevent()
    '''

    max_events = 1000

    def initialize(self):
        self._kqueue = select.kqueue()
        self.readables = set()
        self.writables = set()

    def register_readable(self, fd):
        self.readables.add(fd)
        kevent = select.kevent(fd, filter=select.KQ_FILTER_READ,
                               flags=select.KQ_EV_ADD)
        self._kqueue_control(fd, kevent)

    def register_writable(self, fd):
        self.writables.add(fd)
        kevent = select.kevent(fd, filter=select.KQ_FILTER_WRITE,
                               flags=select.KQ_EV_ADD)
        self._kqueue_control(fd, kevent)

    def unregister_readable(self, fd):
        kevent = select.kevent(fd, filter=select.KQ_FILTER_READ,
                               flags=select.KQ_EV_DELETE)
        self.readables.discard(fd)
        self._kqueue_control(fd, kevent)

    def unregister_writable(self, fd):
        kevent = select.kevent(fd, filter=select.KQ_FILTER_WRITE,
                               flags=select.KQ_EV_DELETE)
        self.writables.discard(fd)
        self._kqueue_control(fd, kevent)

    def _kqueue_control(self, fd, kevent):
        try:
            self._kqueue.control([kevent], 0)
        except OSError, error:
            if error.errno == errno.EBADF:
                self.options.logger.blather('EBADF encountered in kqueue. '
                                            'Invalid file descriptor %s' % fd)
            else:
                raise

    def poll(self, timeout):
        readables, writables = [], []

        try:
            kevents = self._kqueue.control(None, self.max_events, timeout)
        except OSError, error:
            if error.errno == errno.EINTR:
                self.options.logger.blather('EINTR encountered in poll')
                return readables, writables
            raise

        for kevent in kevents:
            if kevent.filter == select.KQ_FILTER_READ:
                readables.append(kevent.ident)
            if kevent.filter == select.KQ_FILTER_WRITE:
                writables.append(kevent.ident)

        return readables, writables

    def before_daemonize(self):
        self.close()

    def after_daemonize(self):
        self._kqueue = select.kqueue()
        for fd in self.readables:
            self.register_readable(fd)
        for fd in self.writables:
            self.register_writable(fd)

    def close(self):
        self._kqueue.close()
        self._kqueue = None

def implements_poll():
    return hasattr(select, 'poll')

def implements_kqueue():
    return hasattr(select, 'kqueue')

if implements_kqueue():
    Poller = KQueuePoller
elif implements_poll():
    Poller = PollPoller
else:
    Poller = SelectPoller
