# -*- Mode: Python -*-

__author__ = 'Scott Maxwell'

from supervisor.compat import PY3
from supervisor.compat import as_string, as_bytes

from socket import * # relied on to be imported from elsewhere

if PY3:
    bin_socket = socket
    class text_socket(socket):
        def __init__(self, family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None):
            bin_socket.__init__(self, family, type, proto, fileno)

        def recv(self, *args, **kwargs):
            return as_string(bin_socket.recv(self, *args, **kwargs))

        def recvfrom(self, *args, **kwargs):
            reply, whence = bin_socket.recvfrom(self, *args, **kwargs)
            reply = as_string(reply)
            return reply, whence

        def send(self, data, *args, **kwargs):
            b = as_bytes(data)
            return bin_socket.send(self, b, *args, **kwargs)

        def sendall(self, data, *args, **kwargs):
            return bin_socket.sendall(self, as_bytes(data), *args, **kwargs)

        def sendto(self, data, *args, **kwargs):
            return bin_socket.sendto(self, as_bytes(data), *args, **kwargs)

        def accept(self):
#            sock, addr = bin_socket.accept(self)
#            sock = text_socket(self.family, self.type, self.proto, fileno=sock.fileno())
            fd, addr = self._accept()
            sock = text_socket(self.family, self.type, self.proto, fileno=fd)
            # Issue #7995: if no default timeout is set and the listening
            # socket had a (non-zero) timeout, force the new socket in blocking
            # mode to override platform-specific socket flags inheritance.
            if getdefaulttimeout() is None and self.gettimeout():
                sock.setblocking(True)
            return sock, addr

    text_socket.__init__.__doc__ = bin_socket.__init__.__doc__
    socket = text_socket
