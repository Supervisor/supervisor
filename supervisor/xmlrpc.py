import types
import re
import traceback
import sys
import datetime
import time
from xml.etree.ElementTree import iterparse

from supervisor.compat import xmlrpclib
from supervisor.compat import func_attribute
from supervisor.compat import StringIO
from supervisor.compat import urllib
from supervisor.compat import as_bytes
from supervisor.compat import as_string
from supervisor.compat import encodestring
from supervisor.compat import decodestring
from supervisor.compat import httplib

import supervisor.medusa.text_socket as socket
from supervisor.medusa.http_server import get_header
from supervisor.medusa.xmlrpc_handler import xmlrpc_handler
from supervisor.medusa import producers

from supervisor.http import NOT_DONE_YET

class Faults:
    UNKNOWN_METHOD = 1
    INCORRECT_PARAMETERS = 2
    BAD_ARGUMENTS = 3
    SIGNATURE_UNSUPPORTED = 4
    SHUTDOWN_STATE = 6
    BAD_NAME = 10
    BAD_SIGNAL = 11
    NO_FILE = 20
    NOT_EXECUTABLE = 21
    FAILED = 30
    ABNORMAL_TERMINATION = 40
    SPAWN_ERROR = 50
    ALREADY_STARTED = 60
    NOT_RUNNING = 70
    SUCCESS = 80
    ALREADY_ADDED = 90
    STILL_RUNNING = 91
    CANT_REREAD = 92

def getFaultDescription(code):
    for faultname in Faults.__dict__:
        if getattr(Faults, faultname) == code:
            return faultname
    return 'UNKNOWN'

class RPCError(Exception):
    def __init__(self, code, extra=None):
        self.code = code
        self.text = getFaultDescription(code)
        if extra is not None:
            self.text = '%s: %s' % (self.text, extra)

class DeferredXMLRPCResponse:
    """ A medusa producer that implements a deferred callback; requires
    a subclass of asynchat.async_chat that handles NOT_DONE_YET sentinel """
    CONNECTION = re.compile ('Connection: (.*)', re.IGNORECASE)
    traceback = traceback # for testing override

    def __init__(self, request, callback):
        self.callback = callback
        self.request = request
        self.finished = False
        self.delay = float(callback.delay)

    def more(self):
        if self.finished:
            return ''
        try:
            try:
                value = self.callback()
                if value is NOT_DONE_YET:
                    return NOT_DONE_YET
            except RPCError as err:
                value = xmlrpclib.Fault(err.code, err.text)

            body = xmlrpc_marshal(value)

            self.finished = True

            return self.getresponse(body)

        except:
            # report unexpected exception back to server
            self.traceback.print_exc()
            self.finished = True
            self.request.error(500)

    def getresponse(self, body):
        self.request['Content-Type'] = 'text/xml'
        self.request['Content-Length'] = len(body)
        self.request.push(body)
        connection = get_header(self.CONNECTION, self.request.header)

        close_it = 0

        if self.request.version == '1.0':
            if connection == 'keep-alive':
                self.request['Connection'] = 'Keep-Alive'
            else:
                close_it = 1
        elif self.request.version == '1.1':
            if connection == 'close':
                close_it = 1
        elif self.request.version is None:
            close_it = 1

        outgoing_header = producers.simple_producer (
            self.request.build_reply_header())

        if close_it:
            self.request['Connection'] = 'close'

        # prepend the header
        self.request.outgoing.insert(0, outgoing_header)
        outgoing_producer = producers.composite_producer(self.request.outgoing)

        # apply a few final transformations to the output
        self.request.channel.push_with_producer (
                # globbing gives us large packets
                producers.globbing_producer (
                        # hooking lets us log the number of bytes sent
                        producers.hooked_producer (
                                outgoing_producer,
                                self.request.log
                                )
                        )
                )

        self.request.channel.current_request = None

        if close_it:
            self.request.channel.close_when_done()

def xmlrpc_marshal(value):
    ismethodresponse = not isinstance(value, xmlrpclib.Fault)
    if ismethodresponse:
        if not isinstance(value, tuple):
            value = (value,)
        body = xmlrpclib.dumps(value,  methodresponse=ismethodresponse)
    else:
        body = xmlrpclib.dumps(value)
    return body

class SystemNamespaceRPCInterface:
    def __init__(self, namespaces):
        self.namespaces = {}
        for name, inst in namespaces:
            self.namespaces[name] = inst
        self.namespaces['system'] = self

    def _listMethods(self):
        methods = {}
        for ns_name in self.namespaces:
            namespace = self.namespaces[ns_name]
            for method_name in namespace.__class__.__dict__:
                # introspect; any methods that don't start with underscore
                # are published
                func = getattr(namespace, method_name)
                meth = getattr(func, func_attribute, None)
                if meth is not None:
                    if not method_name.startswith('_'):
                        sig = '%s.%s' % (ns_name, method_name)
                        methods[sig] = str(func.__doc__)
        return methods

    def listMethods(self):
        """ Return an array listing the available method names

        @return array result  An array of method names available (strings).
        """
        methods = self._listMethods()
        keys = list(methods.keys())
        keys.sort()
        return keys

    def methodHelp(self, name):
        """ Return a string showing the method's documentation

        @param string name   The name of the method.
        @return string result The documentation for the method name.
        """
        methods = self._listMethods()
        for methodname in methods.keys():
            if methodname == name:
                return methods[methodname]
        raise RPCError(Faults.SIGNATURE_UNSUPPORTED)

    def methodSignature(self, name):
        """ Return an array describing the method signature in the
        form [rtype, ptype, ptype...] where rtype is the return data type
        of the method, and ptypes are the parameter data types that the
        method accepts in method argument order.

        @param string name  The name of the method.
        @return array result  The result.
        """
        methods = self._listMethods()
        for method in methods:
            if method == name:
                rtype = None
                ptypes = []
                parsed = gettags(methods[method])
                for thing in parsed:
                    if thing[1] == 'return': # tag name
                        rtype = thing[2] # datatype
                    elif thing[1] == 'param': # tag name
                        ptypes.append(thing[2]) # datatype
                if rtype is None:
                    raise RPCError(Faults.SIGNATURE_UNSUPPORTED)
                return [rtype] + ptypes
        raise RPCError(Faults.SIGNATURE_UNSUPPORTED)

    def multicall(self, calls):
        """Process an array of calls, and return an array of
        results. Calls should be structs of the form {'methodName':
        string, 'params': array}. Each result will either be a
        single-item array containing the result value, or a struct of
        the form {'faultCode': int, 'faultString': string}. This is
        useful when you need to make lots of small calls without lots
        of round trips.

        @param array calls  An array of call requests
        @return array result  An array of results
        """
        producers = []

        for call in calls:
            try:
                name = call['methodName']
                params = call.get('params', [])
                if name == 'system.multicall':
                    # Recursive system.multicall forbidden
                    raise RPCError(Faults.INCORRECT_PARAMETERS)
                root = AttrDict(self.namespaces)
                value = traverse(root, name, params)
            except RPCError as inst:
                value = {'faultCode': inst.code,
                         'faultString': inst.text}
            except:
                errmsg = "%s:%s" % (sys.exc_info()[0], sys.exc_info()[1])
                value = {'faultCode': 1, 'faultString': errmsg}
            producers.append(value)

        results = []

        def multiproduce():
            """ Run through all the producers in order """
            if not producers:
                return []

            callback = producers.pop(0)

            if isinstance(callback, types.FunctionType):
                try:
                    value = callback()
                except RPCError as inst:
                    value = {'faultCode':inst.code, 'faultString':inst.text}

                if value is NOT_DONE_YET:
                    # push it back in the front of the queue because we
                    # need to finish the calls in requested order
                    producers.insert(0, callback)
                    return NOT_DONE_YET
            else:
                value = callback

            results.append(value)

            if producers:
                # only finish when all producers are finished
                return NOT_DONE_YET

            return results

        multiproduce.delay = .05
        return multiproduce

class AttrDict(dict):
    # hack to make a dict's getattr equivalent to its getitem
    def __getattr__(self, name):
        return self[name]

class RootRPCInterface:
    def __init__(self, subinterfaces):
        for name, rpcinterface in subinterfaces:
            setattr(self, name, rpcinterface)

def make_datetime(text):
    return datetime.datetime(
        *time.strptime(text, "%Y%m%dT%H:%M:%S")[:6]
    )

class supervisor_xmlrpc_handler(xmlrpc_handler):
    path = '/RPC2'
    IDENT = 'Supervisor XML-RPC Handler'

    unmarshallers = {
        "int": lambda x: int(x.text),
        "i4": lambda x: int(x.text),
        "boolean": lambda x: x.text == "1",
        "string": lambda x: x.text or "",
        "double": lambda x: float(x.text),
        "dateTime.iso8601": lambda x: make_datetime(x.text),
        "array": lambda x: x[0].text,
        "data": lambda x: [v.text for v in x],
        "struct": lambda x: dict([(k.text or "", v.text) for k, v in x]),
        "base64": lambda x: as_string(decodestring(as_bytes(x.text or ""))),
        "value": lambda x: x[0].text,
        "param": lambda x: x[0].text,
        }

    def __init__(self, supervisord, subinterfaces):
        self.rpcinterface = RootRPCInterface(subinterfaces)
        self.supervisord = supervisord

    def loads(self, data):
        params = method = None
        for action, elem in iterparse(StringIO(data)):
            unmarshall = self.unmarshallers.get(elem.tag)
            if unmarshall:
                data = unmarshall(elem)
                elem.clear()
                elem.text = data
            elif elem.tag == "methodName":
                method = elem.text
            elif elem.tag == "params":
                params = tuple([v.text for v in elem])
        return params, method

    def match(self, request):
        return request.uri.startswith(self.path)

    def continue_request (self, data, request):
        logger = self.supervisord.options.logger

        try:

            params, method = self.loads(data)

            # no <methodName> in the request or name is an empty string
            if not method:
                logger.trace('XML-RPC request received with no method name')
                request.error(400)
                return

            # we allow xml-rpc clients that do not send empty <params>
            # when there are no parameters for the method call
            if params is None:
                params = ()

            try:
                logger.trace('XML-RPC method called: %s()' % method)
                value = self.call(method, params)
                # application-specific: instead of we never want to
                # marshal None (even though we could by saying allow_none=True
                # in dumps within xmlrpc_marshall), this is meant as
                # a debugging fixture, see issue 223.
                assert value is not None, (
                    'return value from method %r with params %r is None' %
                    (method, params)
                    )
                logger.trace('XML-RPC method %s() returned successfully' %
                             method)
            except RPCError as err:
                # turn RPCError reported by method into a Fault instance
                value = xmlrpclib.Fault(err.code, err.text)
                logger.trace('XML-RPC method %s() returned fault: [%d] %s' % (
                    method,
                    err.code, err.text))

            if isinstance(value, types.FunctionType):
                # returning a function from an RPC method implies that
                # this needs to be a deferred response (it needs to block).
                pushproducer = request.channel.push_with_producer
                pushproducer(DeferredXMLRPCResponse(request, value))

            else:
                # if we get anything but a function, it implies that this
                # response doesn't need to be deferred, we can service it
                # right away.
                body = xmlrpc_marshal(value)
                request['Content-Type'] = 'text/xml'
                request['Content-Length'] = len(body)
                request.push(body)
                request.done()

        except:
            io = StringIO()
            traceback.print_exc(file=io)
            val = io.getvalue()
            logger.critical(val)
            # internal error, report as HTTP server error
            request.error(500)

    def call(self, method, params):
        return traverse(self.rpcinterface, method, params)

def traverse(ob, method, params):
    path = method.split('.')
    for name in path:
        if name.startswith('_'):
            # security (don't allow things that start with an underscore to
            # be called remotely)
            raise RPCError(Faults.UNKNOWN_METHOD)
        ob = getattr(ob, name, None)
        if ob is None:
            raise RPCError(Faults.UNKNOWN_METHOD)

    try:
        return ob(*params)
    except TypeError:
        raise RPCError(Faults.INCORRECT_PARAMETERS)

class SupervisorTransport(xmlrpclib.Transport):
    """
    Provides a Transport for xmlrpclib that uses
    httplib.HTTPConnection in order to support persistent
    connections.  Also support basic auth and UNIX domain socket
    servers.
    """
    connection = None

    def __init__(self, username=None, password=None, serverurl=None):
        xmlrpclib.Transport.__init__(self)
        self.username = username
        self.password = password
        self.verbose = False
        self.serverurl = serverurl
        if serverurl.startswith('http://'):
            type, uri = urllib.splittype(serverurl)
            host, path = urllib.splithost(uri)
            host, port = urllib.splitport(host)
            if port is None:
                port = 80
            else:
                port = int(port)
            def get_connection(host=host, port=port):
                return httplib.HTTPConnection(host, port)
            self._get_connection = get_connection
        elif serverurl.startswith('unix://'):
            def get_connection(serverurl=serverurl):
                # we use 'localhost' here because domain names must be
                # < 64 chars (or we'd use the serverurl filename)
                conn = UnixStreamHTTPConnection('localhost')
                conn.socketfile = serverurl[7:]
                return conn
            self._get_connection = get_connection
        else:
            raise ValueError('Unknown protocol for serverurl %s' % serverurl)

    def request(self, host, handler, request_body, verbose=0):
        if not self.connection:
            self.connection = self._get_connection()
            self.headers = {
                "User-Agent" : self.user_agent,
                "Content-Type" : "text/xml",
                "Accept": "text/xml"
                }

            # basic auth
            if self.username is not None and self.password is not None:
                unencoded = "%s:%s" % (self.username, self.password)
                encoded = as_string(encodestring(as_bytes(unencoded)))
                encoded = encoded.replace('\n', '')
                encoded = encoded.replace('\012', '')
                self.headers["Authorization"] = "Basic %s" % encoded

        self.headers["Content-Length"] = str(len(request_body))

        self.connection.request('POST', handler, request_body, self.headers)

        r = self.connection.getresponse()

        if r.status != 200:
            self.connection.close()
            self.connection = None
            raise xmlrpclib.ProtocolError(host + handler,
                                          r.status,
                                          r.reason,
                                          '' )
        data = r.read()
        p, u = self.getparser()
        p.feed(data)
        p.close()
        return u.close()

class UnixStreamHTTPConnection(httplib.HTTPConnection):
    def connect(self): # pragma: no cover
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # we abuse the host parameter as the socketname
        self.sock.connect(self.socketfile)

def gettags(comment):
    """ Parse documentation strings into JavaDoc-like tokens """

    tags = []

    tag = None
    datatype = None
    name = None
    tag_lineno = lineno = 0
    tag_text = []

    for line in comment.split('\n'):
        line = line.strip()
        if line.startswith("@"):
            tags.append((tag_lineno, tag, datatype, name, '\n'.join(tag_text)))
            parts = line.split(None, 3)
            if len(parts) == 1:
                datatype = ''
                name = ''
                tag_text = []
            elif len(parts) == 2:
                datatype = parts[1]
                name = ''
                tag_text = []
            elif len(parts) == 3:
                datatype = parts[1]
                name = parts[2]
                tag_text = []
            elif len(parts) == 4:
                datatype = parts[1]
                name = parts[2]
                tag_text = [parts[3].lstrip()]
            tag = parts[0][1:]
            tag_lineno = lineno
        else:
            if line:
                tag_text.append(line)
        lineno += 1

    tags.append((tag_lineno, tag, datatype, name, '\n'.join(tag_text)))

    return tags


