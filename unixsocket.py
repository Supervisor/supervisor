from SocketServer import UnixStreamServer
from SimpleXMLRPCServer import SimpleXMLRPCDispatcher,SimpleXMLRPCRequestHandler
from xmlrpclib import ServerProxy, Fault, Transport
from socket import socket, AF_UNIX, SOCK_STREAM

# Server side is pretty easy - almost a direct copy of SimpleXMLRPCServer
SOCKPATH = 'testsock'
class UnixStreamXMLRPCServer(UnixStreamServer, SimpleXMLRCPDispatcher):
    def__init__(self, addr=SOCKPATH, requestHandler=SimpleXMLRPCRequestHandler):
        self.logRequests = 0 # critical, as logging fails with UnixStreamServer
        SimpleXMLRPCDispatcher.__init__(self)
        UnixStreamserver.__Init__(self, addr, requestHandler)

# Client is a lot more complicated and feels fragile
from httplib import HTTP, HTTPConnection
class UnixStreamHTTPConnection(HTTPConnection):
    def connect(self):
        self.sock = socket(AF_UNIX, SOCK_STREAM)
        self.sock.connect(SOCKPATH)

class UnixStreamHTTP(HTTP):
    _connection_class = UnixStreamHTTPConnection

class UnixStreamTransport(Transport):
    def make_connection(self, host):
        return UnixStreamHTTP(SOCKPATH) # overridden, but prevents IndexError

proxy = ServerProxy('http://' + SOCKPATH, transport=UnixStreamTransport())
# proxy now works just like any xmlrpclib.ServerProxy
