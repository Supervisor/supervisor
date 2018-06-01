import sys
import time

from supervisor.compat import xmlrpclib
from supervisor.compat import long
from supervisor.compat import as_string

from supervisor.xmlrpc import SupervisorTransport
from supervisor.events import ProcessCommunicationEvent
from supervisor.dispatchers import PEventListenerDispatcher

def getRPCTransport(env):
    u = env.get('SUPERVISOR_USERNAME', '')
    p = env.get('SUPERVISOR_PASSWORD', '')
    return SupervisorTransport(u, p, env['SUPERVISOR_SERVER_URL'])

def getRPCInterface(env):
    # dumbass ServerProxy won't allow us to pass in a non-HTTP url,
    # so we fake the url we pass into it and always use the transport's
    # 'serverurl' to figure out what to attach to
    return xmlrpclib.ServerProxy('http://127.0.0.1', getRPCTransport(env))

def get_headers(line):
    return dict([ x.split(':') for x in line.split() ])

def eventdata(payload):
    headerinfo, data = payload.split('\n', 1)
    headers = get_headers(headerinfo)
    return headers, data

def get_asctime(now=None):
    if now is None: # for testing
        now = time.time() # pragma: no cover
    msecs = (now - long(now)) * 1000
    part1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    asctime = '%s,%03d' % (part1, msecs)
    return asctime

class ProcessCommunicationsProtocol:
    def send(self, msg, fp=sys.stdout):
        fp.write(ProcessCommunicationEvent.BEGIN_TOKEN)
        fp.write(msg)
        fp.write(ProcessCommunicationEvent.END_TOKEN)
        fp.flush()

    def stdout(self, msg):
        return self.send(msg, sys.stdout)

    def stderr(self, msg):
        return self.send(msg, sys.stderr)

pcomm = ProcessCommunicationsProtocol()

class EventListenerProtocol:
    def wait(self, stdin=sys.stdin, stdout=sys.stdout):
        self.ready(stdout)
        line = stdin.readline()
        headers = get_headers(line)
        payload = stdin.read(int(headers['len']))
        return headers, payload

    def ready(self, stdout=sys.stdout):
        stdout.write(as_string(PEventListenerDispatcher.READY_FOR_EVENTS_TOKEN))
        stdout.flush()

    def ok(self, stdout=sys.stdout):
        self.send('OK', stdout)

    def fail(self, stdout=sys.stdout):
        self.send('FAIL', stdout)

    def send(self, data, stdout=sys.stdout):
        resultlen = len(data)
        result = '%s%s\n%s' % (as_string(PEventListenerDispatcher.RESULT_TOKEN_START),
                               str(resultlen),
                               data)
        stdout.write(result)
        stdout.flush()

listener = EventListenerProtocol()
