# -*- Mode: Python -*-

# See http://www.xml-rpc.com/
#     http://www.pythonware.com/products/xmlrpc/

# Based on "xmlrpcserver.py" by Fredrik Lundh (fredrik@pythonware.com)

VERSION = "$Id: xmlrpc_handler.py,v 1.6 2004/04/21 14:09:24 akuchling Exp $"

from supervisor.compat import as_string

import supervisor.medusa.http_server as http_server
try:
    import xmlrpclib
except:
    import xmlrpc.client as xmlrpclib

import sys

class xmlrpc_handler:

    def match (self, request):
        # Note: /RPC2 is not required by the spec, so you may override this method.
        if request.uri[:5] == '/RPC2':
            return 1
        else:
            return 0

    def handle_request (self, request):
        if request.command == 'POST':
            request.collector = collector (self, request)
        else:
            request.error (400)

    def continue_request (self, data, request):
        params, method = xmlrpclib.loads (data)
        try:
            # generate response
            try:
                response = self.call (method, params)
                if type(response) != type(()):
                    response = (response,)
            except:
                # report exception back to server
                response = xmlrpclib.dumps (
                        xmlrpclib.Fault (1, "%s:%s" % (sys.exc_info()[0], sys.exc_info()[1]))
                        )
            else:
                response = xmlrpclib.dumps (response, methodresponse=1)
        except:
            # internal error, report as HTTP server error
            request.error (500)
        else:
            # got a valid XML RPC response
            request['Content-Type'] = 'text/xml'
            request.push (response)
            request.done()

    def call (self, method, params):
        # override this method to implement RPC methods
        raise Exception("NotYetImplemented")

class collector:

    """gathers input for POST and PUT requests"""

    def __init__ (self, handler, request):

        self.handler = handler
        self.request = request
        self.data = []

        # make sure there's a content-length header
        cl = request.get_header ('content-length')

        if not cl:
            request.error (411)
        else:
            cl = int(cl)
            # using a 'numeric' terminator
            self.request.channel.set_terminator (cl)

    def collect_incoming_data (self, data):
        self.data.append(data)

    def found_terminator (self):
        # set the terminator back to the default
        self.request.channel.set_terminator (b'\r\n\r\n')
        # convert the data back to text for processing
        data = as_string(b''.join(self.data))
        self.handler.continue_request (data, self.request)

if __name__ == '__main__':

    class rpc_demo (xmlrpc_handler):

        def call (self, method, params):
            print('method="%s" params=%s' % (method, params))
            return "Sure, that works"

    import supervisor.medusa.asyncore_25 as asyncore

    hs = http_server.http_server ('', 8000)
    rpc = rpc_demo()
    hs.install_handler (rpc)

    asyncore.loop()
