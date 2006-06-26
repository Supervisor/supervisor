# -*- Mode: Python -*-

VERSION_STRING = "$Id$"

# This will probably only work on Unix.

# The disadvantage to this technique is that it wastes file
# descriptors (especially when compared to select_trigger.py)

# May be possible to do it on Win32, using TCP localhost sockets.
# [does winsock support 'socketpair'?]

import asyncore
import asynchat

import fcntl
import FCNTL
import os
import socket
import string
import thread

# this channel slaves off of another one.  it starts a thread which
# pumps its output through the 'write' side of the pipe.  The 'read'
# side of the pipe will then notify us when data is ready.  We push
# this data on the owning data channel's output queue.

class thread_channel (asyncore.file_dispatcher):

    buffer_size = 8192

    def __init__ (self, channel, function, *args):
        self.parent = channel
        self.function = function
        self.args = args
        self.pipe = rfd, wfd = os.pipe()
        asyncore.file_dispatcher.__init__ (self, rfd)

    def start (self):
        rfd, wfd = self.pipe

        # The read side of the pipe is set to non-blocking I/O; it is
        # 'owned' by medusa.

        flags = fcntl.fcntl (rfd, FCNTL.F_GETFL, 0)
        fcntl.fcntl (rfd, FCNTL.F_SETFL, flags | FCNTL.O_NDELAY)

        # The write side of the pipe is left in blocking mode; it is
        # 'owned' by the thread.  However, we wrap it up as a file object.
        # [who wants to 'write()' to a number?]

        of = os.fdopen (wfd, 'w')

        thread.start_new_thread (
                self.function,
                # put the output file in front of the other arguments
                (of,) + self.args
                )

    def writable (self):
        return 0

    def readable (self):
        return 1

    def handle_read (self):
        data = self.recv (self.buffer_size)
        self.parent.push (data)

    def handle_close (self):
        # Depending on your intentions, you may want to close
        # the parent channel here.
        self.close()

# Yeah, it's bad when the test code is bigger than the library code.

if __name__ == '__main__':

    import time

    def thread_function (output_file, i, n):
        print 'entering thread_function'
        while n:
            time.sleep (5)
            output_file.write ('%2d.%2d %s\r\n' % (i, n, output_file))
            output_file.flush()
            n = n - 1
        output_file.close()
        print 'exiting thread_function'

    class thread_parent (asynchat.async_chat):

        def __init__ (self, conn, addr):
            self.addr = addr
            asynchat.async_chat.__init__ (self, conn)
            self.set_terminator ('\r\n')
            self.buffer = ''
            self.count = 0

        def collect_incoming_data (self, data):
            self.buffer = self.buffer + data

        def found_terminator (self):
            data, self.buffer = self.buffer, ''
            n = string.atoi (string.split (data)[0])
            tc = thread_channel (self, thread_function, self.count, n)
            self.count = self.count + 1
            tc.start()

    class thread_server (asyncore.dispatcher):

        def __init__ (self, family=socket.AF_INET, address=('127.0.0.1', 9003)):
            asyncore.dispatcher.__init__ (self)
            self.create_socket (family, socket.SOCK_STREAM)
            self.set_reuse_addr()
            self.bind (address)
            self.listen (5)

        def handle_accept (self):
            conn, addr = self.accept()
            tp = thread_parent (conn, addr)

    thread_server()
    #asyncore.loop(1.0, use_poll=1)
    asyncore.loop ()
