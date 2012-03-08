import select
import errno
import time

class Poller:
    '''
    Wrapper for select.poll()
    '''

    READ = select.POLLIN | select.POLLPRI
    WRITE = select.POLLOUT

    def __init__(self, options):
        self.options = options
        self._poller = select.poll()

    def register_readable(self, fd):
        self._poller.register(fd, self.READ)

    def register_writable(self, fd):
        self._poller.register(fd, self.WRITE)

    def unregister(self, fd):
        self._poller.unregister(fd)

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
            return self._poller.poll(timeout)
        except select.error, err:
            if err[0] == errno.EINTR:
                self.options.logger.blather('EINTR encountered in poll')
                return []
            raise

    def _ignore_invalid(self, fd, eventmask):
        if eventmask & select.POLLNVAL:
            # POLLNVAL means `fd` value is invalid, not open.
            # When a process quits it's `fd`s are closed so there
            # is no more reason to keep this `fd` registered
            # If the process restarts it's `fd`s are registered again
            self.unregister(fd)
            return True
        return False
