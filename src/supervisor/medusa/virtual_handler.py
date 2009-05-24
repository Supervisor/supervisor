# -*- Mode: Python -*-

import socket
import default_handler
import re

HOST = re.compile ('Host: ([^:/]+).*', re.IGNORECASE)

get_header = default_handler.get_header

class virtual_handler:

    """HTTP request handler for an HTTP/1.0-style virtual host.  Each
    Virtual host must have a different IP"""

    def __init__ (self, handler, hostname):
        self.handler = handler
        self.hostname = hostname
        try:
            self.ip = socket.gethostbyname (hostname)
        except socket.error:
            raise ValueError, "Virtual Hostname %s does not appear to be registered in the DNS" % hostname

    def match (self, request):
        if (request.channel.addr[0] == self.ip):
            return 1
        else:
            return 0

    def handle_request (self, request):
        return self.handler.handle_request (request)

    def __repr__ (self):
        return '<virtual request handler for %s>' % self.hostname


class virtual_handler_with_host:

    """HTTP request handler for HTTP/1.1-style virtual hosts.  This
    matches by checking the value of the 'Host' header in the request.
    You actually don't _have_ to support HTTP/1.1 to use this, since
    many browsers now send the 'Host' header.  This is a Good Thing."""

    def __init__ (self, handler, hostname):
        self.handler = handler
        self.hostname = hostname

    def match (self, request):
        host = get_header (HOST, request.header)
        if host == self.hostname:
            return 1
        else:
            return 0

    def handle_request (self, request):
        return self.handler.handle_request (request)

    def __repr__ (self):
        return '<virtual request handler for %s>' % self.hostname
