# -*- Mode: Python -*-

import re
import string
import StringIO
import sys

import os
import sys
import time

import select_trigger
from medusa import counter
from medusa import producers

from medusa.default_handler import unquote, get_header

import threading

class request_queue:

    def __init__ (self):
        self.mon = threading.RLock()
        self.cv = threading.Condition (self.mon)
        self.queue = []

    def put (self, item):
        self.cv.acquire()
        self.queue.append(item)
        self.cv.notify()
        self.cv.release()

    def get(self):
        self.cv.acquire()
        while not self.queue:
            self.cv.wait()
        result = self.queue.pop(0)
        self.cv.release()
        return result

header2env= {
        'Content-Length'        : 'CONTENT_LENGTH',
        'Content-Type'          : 'CONTENT_TYPE',
        'Referer'                       : 'HTTP_REFERER',
        'User-Agent'            : 'HTTP_USER_AGENT',
        'Accept'                        : 'HTTP_ACCEPT',
        'Accept-Charset'        : 'HTTP_ACCEPT_CHARSET',
        'Accept-Language'       : 'HTTP_ACCEPT_LANGUAGE',
        'Host'                          : 'HTTP_HOST',
        'Connection'            : 'CONNECTION_TYPE',
        'Authorization'         : 'HTTP_AUTHORIZATION',
        'Cookie'                        : 'HTTP_COOKIE',
        }

# convert keys to lower case for case-insensitive matching
for (key,value) in header2env.items():
    del header2env[key]
    key=string.lower(key)
    header2env[key]=value

class thread_output_file (select_trigger.trigger_file):

    def close (self):
        self.trigger_close()

class script_handler:

    def __init__ (self, queue, document_root=""):
        self.modules = {}
        self.document_root = document_root
        self.queue = queue

    def add_module (self, module, *names):
        if not names:
            names = ["/%s" % module.__name__]
        for name in names:
            self.modules['/'+name] = module

    def match (self, request):
        uri = request.uri

        i = string.find(uri, "/", 1)
        if i != -1:
            uri = uri[:i]

        i = string.find(uri, "?", 1)
        if i != -1:
            uri = uri[:i]

        if self.modules.has_key (uri):
            request.module = self.modules[uri]
            return 1
        else:
            return 0

    def handle_request (self, request):

        [path, params, query, fragment] = request.split_uri()

        while path and path[0] == '/':
            path = path[1:]

        if '%' in path:
            path = unquote (path)

        env = {}

        env['REQUEST_URI'] = "/" + path
        env['REQUEST_METHOD']   = string.upper(request.command)
        env['SERVER_PORT']       = str(request.channel.server.port)
        env['SERVER_NAME']       = request.channel.server.server_name
        env['SERVER_SOFTWARE'] = request['Server']
        env['DOCUMENT_ROOT']     = self.document_root

        parts = string.split(path, "/")

        # are script_name and path_info ok?

        env['SCRIPT_NAME']      = "/" + parts[0]

        if query and query[0] == "?":
            query = query[1:]

        env['QUERY_STRING']     = query

        try:
            path_info = "/" + string.join(parts[1:], "/")
        except:
            path_info = ''

        env['PATH_INFO']                = path_info
        env['GATEWAY_INTERFACE']='CGI/1.1'                                      # what should this really be?
        env['REMOTE_ADDR']              =request.channel.addr[0]
        env['REMOTE_HOST']              =request.channel.addr[0]        # TODO: connect to resolver

        for header in request.header:
            [key,value]=string.split(header,": ",1)
            key=string.lower(key)

            if header2env.has_key(key):
                if header2env[key]:
                    env[header2env[key]]=value
            else:
                key = 'HTTP_' + string.upper(
                        string.join(
                                string.split (key,"-"),
                                "_"
                                )
                        )
                env[key]=value

        ## remove empty environment variables
        for key in env.keys():
            if env[key]=="" or env[key]==None:
                del env[key]

        try:
            httphost = env['HTTP_HOST']
            parts = string.split(httphost,":")
            env['HTTP_HOST'] = parts[0]
        except KeyError:
            pass

        if request.command in ('put', 'post'):
            # PUT data requires a correct Content-Length: header
            # (though I bet with http/1.1 we can expect chunked encoding)
            request.collector = collector (self, request, env)
            request.channel.set_terminator (None)
        else:
            sin = StringIO.StringIO ('')
            self.continue_request (sin, request, env)

    def continue_request (self, stdin, request, env):
        stdout = header_scanning_file (
                request,
                thread_output_file (request.channel)
                )
        self.queue.put (
                (request.module.main, (env, stdin, stdout))
                )

HEADER_LINE = re.compile ('([A-Za-z0-9-]+): ([^\r\n]+)')

# A file wrapper that handles the CGI 'Status:' header hack
# by scanning the output.

class header_scanning_file:

    def __init__ (self, request, file):
        self.buffer = ''
        self.request = request
        self.file = file
        self.got_header = 0
        self.bytes_out = counter.counter()

    def write (self, data):
        if self.got_header:
            self._write (data)
        else:
            # CGI scripts may optionally provide extra headers.
            #
            # If they do not, then the output is assumed to be
            # text/html, with an HTTP reply code of '200 OK'.
            #
            # If they do, we need to scan those headers for one in
            # particular: the 'Status:' header, which will tell us
            # to use a different HTTP reply code [like '302 Moved']
            #
            self.buffer = self.buffer + data
            lines = string.split (self.buffer, '\n')
            # ignore the last piece, it is either empty, or a partial line
            lines = lines[:-1]
            # look for something un-header-like
            for i in range(len(lines)):
                li = lines[i]
                if (not li) or (HEADER_LINE.match (li) is None):
                    # this is either the header separator, or it
                    # is not a header line.
                    self.got_header = 1
                    h = self.build_header (lines[:i])
                    self._write (h)
                    # rejoin the rest of the data
                    d = string.join (lines[i:], '\n')
                    self._write (d)
                    self.buffer = ''
                    break

    def build_header (self, lines):
        status = '200 OK'
        saw_content_type = 0
        hl = HEADER_LINE
        for line in lines:
            mo = hl.match (line)
            if mo is not None:
                h = string.lower (mo.group(1))
                if h == 'status':
                    status = mo.group(2)
                elif h == 'content-type':
                    saw_content_type = 1
        lines.insert (0, 'HTTP/1.0 %s' % status)
        lines.append ('Server: ' + self.request['Server'])
        lines.append ('Date: ' + self.request['Date'])
        if not saw_content_type:
            lines.append ('Content-Type: text/html')
        lines.append ('Connection: close')
        return string.join (lines, '\r\n')+'\r\n\r\n'

    def _write (self, data):
        self.bytes_out.increment (len(data))
        self.file.write (data)

    def writelines(self, list):
        self.write (string.join (list, ''))

    def flush(self):
        pass

    def close (self):
        if not self.got_header:
            # managed to slip through our header detectors
            self._write (self.build_header (['Status: 502', 'Content-Type: text/html']))
            self._write (
                    '<html><h1>Server Error</h1>\r\n'
                    '<b>Bad Gateway:</b> No Header from CGI Script\r\n'
                    '<pre>Data: %s</pre>'
                    '</html>\r\n' % (repr(self.buffer))
                    )
        self.request.log (int(self.bytes_out.as_long()))
        self.file.close()
        self.request.channel.current_request = None


class collector:

    "gathers input for PUT requests"

    def __init__ (self, handler, request, env):
        self.handler    = handler
        self.env = env
        self.request    = request
        self.data = StringIO.StringIO()

        # make sure there's a content-length header
        self.cl = request.get_header ('content-length')

        if not self.cl:
            request.error (411)
            return
        else:
            self.cl = string.atoi(self.cl)

    def collect_incoming_data (self, data):
        self.data.write (data)
        if self.data.tell() >= self.cl:
            self.data.seek(0)

            h=self.handler
            r=self.request

            # set the terminator back to the default
            self.request.channel.set_terminator ('\r\n\r\n')
            del self.handler
            del self.request

            h.continue_request (self.data, r, self.env)


class request_loop_thread (threading.Thread):

    def __init__ (self, queue):
        threading.Thread.__init__ (self)
        self.setDaemon(1)
        self.queue = queue

    def run (self):
        while 1:
            function, (env, stdin, stdout) = self.queue.get()
            function (env, stdin, stdout)
            stdout.close()

# ===========================================================================
#                                                          Testing
# ===========================================================================

if __name__ == '__main__':

    import sys

    if len(sys.argv) < 2:
        print 'Usage: %s <worker_threads>' % sys.argv[0]
    else:
        nthreads = string.atoi (sys.argv[1])

        import asyncore_25 as asyncore
        from medusa import http_server
        # create a generic web server
        hs = http_server.http_server ('', 7080)

        # create a request queue
        q = request_queue()

        # create a script handler
        sh = script_handler (q)

        # install the script handler on the web server
        hs.install_handler (sh)

        # get a couple of CGI modules
        import test_module
        import pi_module

        # install the module on the script handler
        sh.add_module (test_module, 'test')
        sh.add_module (pi_module, 'pi')

        # fire up the worker threads
        for i in range (nthreads):
            rt = request_loop_thread (q)
            rt.start()

        # start the main event loop
        asyncore.loop()
