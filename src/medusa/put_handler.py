# -*- Mode: Python -*-
#
#       Author: Sam Rushing <rushing@nightmare.com>
#       Copyright 1996-2000 by Sam Rushing
#                                                All Rights Reserved.
#

RCS_ID =  '$Id: put_handler.py,v 1.4 2002/08/01 18:15:45 akuchling Exp $'

import re
import string

import default_handler
unquote         = default_handler.unquote
get_header      = default_handler.get_header

last_request = None

class put_handler:
    def __init__ (self, filesystem, uri_regex):
        self.filesystem = filesystem
        if type (uri_regex) == type(''):
            self.uri_regex = re.compile (uri_regex)
        else:
            self.uri_regex = uri_regex

    def match (self, request):
        uri = request.uri
        if request.command == 'PUT':
            m = self.uri_regex.match (uri)
            if m and m.end() == len(uri):
                return 1
        return 0

    def handle_request (self, request):

        path, params, query, fragment = request.split_uri()

        # strip off leading slashes
        while path and path[0] == '/':
            path = path[1:]

        if '%' in path:
            path = unquote (path)

        # make sure there's a content-length header
        cl = get_header (CONTENT_LENGTH, request.header)
        if not cl:
            request.error (411)
            return
        else:
            cl = string.atoi (cl)

        # don't let the try to overwrite a directory
        if self.filesystem.isdir (path):
            request.error (405)
            return

        is_update = self.filesystem.isfile (path)

        try:
            output_file = self.filesystem.open (path, 'wb')
        except:
            request.error (405)
            return

        request.collector = put_collector (output_file, cl, request, is_update)

        # no terminator while receiving PUT data
        request.channel.set_terminator (None)

        # don't respond yet, wait until we've received the data...

class put_collector:
    def __init__ (self, file, length, request, is_update):
        self.file               = file
        self.length             = length
        self.request    = request
        self.is_update  = is_update
        self.bytes_in   = 0

    def collect_incoming_data (self, data):
        ld = len(data)
        bi = self.bytes_in
        if (bi + ld) >= self.length:
            # last bit of data
            chunk = self.length - bi
            self.file.write (data[:chunk])
            self.file.close()

            if chunk != ld:
                print 'orphaned %d bytes: <%s>' % (ld - chunk, repr(data[chunk:]))

            # do some housekeeping
            r = self.request
            ch = r.channel
            ch.current_request = None
            # set the terminator back to the default
            ch.set_terminator ('\r\n\r\n')
            if self.is_update:
                r.reply_code = 204 # No content
                r.done()
            else:
                r.reply_now (201) # Created
            # avoid circular reference
            del self.request
        else:
            self.file.write (data)
            self.bytes_in = self.bytes_in + ld

    def found_terminator (self):
        # shouldn't be called
        pass

CONTENT_LENGTH = re.compile ('Content-Length: ([0-9]+)', re.IGNORECASE)
