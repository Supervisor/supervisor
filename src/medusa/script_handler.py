# -*- Mode: Python -*-

# This is a simple python server-side script handler.

# A note about performance: This is really only suited for 'fast'
# scripts: The script should generate its output quickly, since the
# whole web server will stall otherwise.  This doesn't mean you have
# to write 'fast code' or anything, it simply means that you shouldn't
# call any long-running code, [like say something that opens up an
# internet connection, or a database query that will hold up the
# server].  If you need this sort of feature, you can support it using
# the asynchronous I/O 'api' that the rest of medusa is built on.  [or
# you could probably use threads]

# Put your script into your web docs directory (like a cgi-bin
# script), make sure it has the correct extension [see the overridable
# script_handler.extension member below].
#
# There's lots of things that can be done to tweak the restricted
# execution model.  Also, of course you could just use 'execfile'
# instead (this is now the default, see class variable
# script_handler.restricted)

import rexec
import re
import string
import StringIO
import sys

import counter
import default_handler
import producers

unquote    = default_handler.unquote

class script_handler:

    extension = 'mpy'
    restricted = 0

    script_regex = re.compile (
            r'.*/([^/]+\.%s)' % extension,
            re.IGNORECASE
            )

    def __init__ (self, filesystem):
        self.filesystem = filesystem
        self.hits = counter.counter()
        self.exceptions = counter.counter()

    def match (self, request):
        [path, params, query, fragment] = request.split_uri()
        m = self.script_regex.match (path)
        return (m and (m.end() == len(path)))

    def handle_request (self, request):

        [path, params, query, fragment] = request.split_uri()

        while path and path[0] == '/':
            path = path[1:]

        if '%' in path:
            path = unquote (path)

        if not self.filesystem.isfile (path):
            request.error (404)
            return
        else:

            self.hits.increment()

            request.script_filename = self.filesystem.translate (path)

            if request.command in ('PUT', 'POST'):
                # look for a Content-Length header.
                cl = request.get_header ('content-length')
                length = int(cl)
                if not cl:
                    request.error (411)
                else:
                    collector (self, length, request)
            else:
                self.continue_request (
                        request,
                        StringIO.StringIO() # empty stdin
                        )

    def continue_request (self, request, stdin):
        temp_files = stdin, StringIO.StringIO(), StringIO.StringIO()
        old_files = sys.stdin, sys.stdout, sys.stderr

        if self.restricted:
            r = rexec.RExec()

        try:
            sys.request = request
            sys.stdin, sys.stdout, sys.stderr = temp_files
            try:
                if self.restricted:
                    r.s_execfile (request.script_filename)
                else:
                    execfile (request.script_filename)
                request.reply_code = 200
            except:
                request.reply_code = 500
                self.exceptions.increment()
        finally:
            sys.stdin, sys.stdout, sys.stderr = old_files
            del sys.request

        i,o,e = temp_files

        if request.reply_code != 200:
            s = e.getvalue()
        else:
            s = o.getvalue()

        request['Content-Length'] = len(s)
        request.push (s)
        request.done()

    def status (self):
        return producers.simple_producer (
                '<li>Server-Side Script Handler'
                + '<ul>'
                + '  <li><b>Hits:</b> %s' % self.hits
                + '  <li><b>Exceptions:</b> %s' % self.exceptions
                + '</ul>'
                )


class persistent_script_handler:

    def __init__ (self):
        self.modules = {}
        self.hits = counter.counter()
        self.exceptions = counter.counter()

    def add_module (self, name, module):
        self.modules[name] = module

    def del_module (self, name):
        del self.modules[name]

    def match (self, request):
        [path, params, query, fragment] = request.split_uri()
        parts = string.split (path, '/')
        if (len(parts)>1) and self.modules.has_key (parts[1]):
            module = self.modules[parts[1]]
            request.module = module
            return 1
        else:
            return 0

    def handle_request (self, request):
        if request.command in ('PUT', 'POST'):
            # look for a Content-Length header.
            cl = request.get_header ('content-length')
            length = int(cl)
            if not cl:
                request.error (411)
            else:
                collector (self, length, request)
        else:
            self.continue_request (request, StringIO.StringIO())

    def continue_request (self, request, input_data):
        temp_files = input_data, StringIO.StringIO(), StringIO.StringIO()
        old_files = sys.stdin, sys.stdout, sys.stderr

        try:
            sys.stdin, sys.stdout, sys.stderr = temp_files
            # provide a default
            request['Content-Type'] = 'text/html'
            try:
                request.module.main (request)
                request.reply_code = 200
            except:
                request.reply_code = 500
                self.exceptions.increment()
        finally:
            sys.stdin, sys.stdout, sys.stderr = old_files

        i,o,e = temp_files

        if request.reply_code != 200:
            s = e.getvalue()
        else:
            s = o.getvalue()

        request['Content-Length'] = len(s)
        request.push (s)
        request.done()

class collector:

    def __init__ (self, handler, length, request):
        self.handler = handler
        self.request = request
        self.request.collector = self
        self.request.channel.set_terminator (length)
        self.buffer = StringIO.StringIO()

    def collect_incoming_data (self, data):
        self.buffer.write (data)

    def found_terminator (self):
        self.buffer.seek(0)
        self.request.collector = None
        self.request.channel.set_terminator ('\r\n\r\n')
        self.handler.continue_request (
                self.request,
                self.buffer
                )
