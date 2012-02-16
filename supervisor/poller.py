import select
import errno

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

    def poll(self, timeout):
        fds = self._poll_fds(timeout)
        readables, writables = [], []
        for fd, eventmask in fds:
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
                self.options.logger.blather('EINTR encountered in select')
                return []
            raise
