# -*- Mode: Python -*-

import re, sys
from supervisor.medusa import asyncore_25 as asyncore
from supervisor.medusa import http_server
from supervisor.medusa import default_handler
from supervisor.medusa import logger
from supervisor.medusa import script_handler
from supervisor.medusa import filesys

PUBLISHING_ROOT='/home/medusa'
CONTENT_LENGTH = re.compile ('Content-Length: ([0-9]+)', re.IGNORECASE)

class sample_input_collector:
    def __init__ (self, request, length):
        self.request = request
        self.length = length

    def collect_incoming_data (self, data):
        print 'data from %s: <%s>' % (self.request, repr(data))

class post_script_handler (script_handler.script_handler):

    def handle_request (self, request):
        if request.command == 'post':
            cl = default_handler.get_header(CONTENT_LENGTH, request.header)
            ic = sample_input_collector(request, cl)
            request.collector = ic
            print request.header

        return script_handler.script_handler.handle_request (self, request)

lg = logger.file_logger (sys.stdout)
fs = filesys.os_filesystem (PUBLISHING_ROOT)
dh = default_handler.default_handler (fs)
ph = post_script_handler (fs)
hs = http_server.http_server ('', 8081, logger_object = lg)

hs.install_handler (dh)
hs.install_handler (ph)

asyncore.loop()
