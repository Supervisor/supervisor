import xmlrpclib
import os
from supervisord import ProcessStates
from supervisord import SupervisorStates
from supervisord import getSupervisorStateDescription
import doctags
import signal
import time
from medusa.xmlrpc_handler import xmlrpc_handler
from medusa.http_server import get_header
from medusa import producers
import sys
import types
import re
import traceback
import StringIO
import tempfile
import errno
from http import NOT_DONE_YET

RPC_VERSION  = 1.0

class Faults:
    UNKNOWN_METHOD = 1
    INCORRECT_PARAMETERS = 2
    BAD_ARGUMENTS = 3
    SIGNATURE_UNSUPPORTED = 4
    SHUTDOWN_STATE = 6
    BAD_NAME = 10
    NO_FILE = 20
    FAILED = 30
    ABNORMAL_TERMINATION = 40
    SPAWN_ERROR = 50
    ALREADY_STARTED = 60
    NOT_RUNNING = 70
    SUCCESS = 80

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
            except RPCError, err:
                value = xmlrpclib.Fault(err.code, err.text)
                
            body = xmlrpc_marshal(value)

            self.finished = True

            return self.getresponse(body)

        except:
            # report unexpected exception back to server
            traceback.print_exc()
            self.finished = True
            self.request.error(500)

    def getresponse(self, body):
        self.request['Content-Type'] = 'text/xml'
        self.request['Content-Length'] = len(body)
        self.request.push(body)
        connection = get_header(self.CONNECTION, self.request.header)

        close_it = 0
        wrap_in_chunking = 0

        if self.request.version == '1.0':
            if connection == 'keep-alive':
                if not self.request.has_key ('Content-Length'):
                    close_it = 1
                else:
                    self.request['Connection'] = 'Keep-Alive'
            else:
                close_it = 1
        elif self.request.version == '1.1':
            if connection == 'close':
                close_it = 1
            elif not self.request.has_key ('Content-Length'):
                if self.request.has_key ('Transfer-Encoding'):
                    if not self.request['Transfer-Encoding'] == 'chunked':
                        close_it = 1
                elif self.request.use_chunked:
                    self.request['Transfer-Encoding'] = 'chunked'
                    wrap_in_chunking = 1
                else:
                    close_it = 1
        elif self.request.version is None:
            close_it = 1

        outgoing_header = producers.simple_producer (
            self.request.build_reply_header())

        if close_it:
            self.request['Connection'] = 'close'

        if wrap_in_chunking:
            outgoing_producer = producers.chunked_producer (
                    producers.composite_producer (self.request.outgoing)
                    )
            # prepend the header
            outgoing_producer = producers.composite_producer(
                [outgoing_header, outgoing_producer]
                )
        else:
            # prepend the header
            self.request.outgoing.insert(0, outgoing_header)
            outgoing_producer = producers.composite_producer (
                self.request.outgoing)

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

class SupervisorNamespaceRPCInterface:

    def __init__(self, supervisord):
        self.supervisord = supervisord

    def _update(self, text):
        self.update_text = text # for unit tests, mainly

        state = self.supervisord.get_state()

        if state == SupervisorStates.SHUTDOWN:
            raise RPCError(Faults.SHUTDOWN_STATE)

    # RPC API methods

    def getVersion(self):
        """ Return the version of the RPC API used by supervisord

        @return int version version id
        """
        self._update('getVersion')
        return RPC_VERSION

    def getIdentification(self):
        """ Return identifiying string of supervisord

        @return string identifier identifying string
        """
        self._update('getIdentification')
        return self.supervisord.options.identifier

    def getState(self):
        """ Return current state of supervisord as a struct

        @return struct A struct with keys string statecode, int statename
        """
        self._update('getState')

        state = self.supervisord.get_state()
        statename = getSupervisorStateDescription(state)
        data =  {
            'statecode':state,
            'statename':statename,
            }
        return data

    def readLog(self, offset, length):
        """ Read length bytes from the main log starting at offset.

        @param int offset offset to start reading from.
        @param int length number of bytes to read from the log.
        @return struct data a struct with keys 'log' (value of 'log' is string).
        """
        self._update('readLog')

        logfile = self.supervisord.options.logfile

        if logfile is None or not os.path.exists(logfile):
            raise RPCError(Faults.NO_FILE)

        try:
            return _readFile(logfile, offset, length)
        except ValueError, inst:
            why = inst.args[0]
            raise RPCError(getattr(Faults, why))

    def clearLog(self):
        """ Clear the main log.

        @return boolean result always returns True unless error
        """
        self._update('clearLog')

        logfile = self.supervisord.options.logfile
        if  logfile is None or not os.path.exists(logfile):
            raise RPCError(Faults.NO_FILE)

        try:
            os.remove(logfile) # there is a race condition here, but ignore it.
        except (os.error, IOError):
            raise RPCError(Faults.FAILED)

        for handler in self.supervisord.options.logger.handlers:
            if hasattr(handler, 'reopen'):
                self.supervisord.options.logger.info('reopening log file')
                handler.reopen()
        return True

    def shutdown(self):
        """ Shut down the supervisor process

        @return boolean result always returns True unless error
        """
        self._update('shutdown')
        
        self.supervisord.mood = -1
        return True

    def restart(self):
        """ Restart the supervisor process

        @return boolean result  always return True unless error
        """
        self._update('restart')
        
        self.supervisord.mood = 0
        return True

    def startProcess(self, name, timeout=500):
        """ Start a process

        @param string name Process name
        @param int timeout Number of milliseconds to wait for process start
        @return boolean result     Always true unless error

        """
        self._update('startProcess')

        processes = self.supervisord.processes
        process = processes.get(name)

        try:
            timeout = int(timeout)
        except:
            raise RPCError(Faults.BAD_ARGUMENTS, 'timeout: %s' % timeout)

        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        if process.pid:
            raise RPCError(Faults.ALREADY_STARTED, name)

        process.spawn()

        if process.spawnerr:
            raise RPCError(Faults.SPAWN_ERROR, name)

        if not timeout:
            timeout = 0
        
        milliseconds = timeout / 1000.0
        start = time.time()

        def check_still_running(done=False): # done arg is only for unit testing
            t = time.time()
            runtime = (t - start)
            if not done and runtime < milliseconds:
                return NOT_DONE_YET
            pid = processes[name].pid
            if pid:
                return True
            raise RPCError(Faults.ABNORMAL_TERMINATION, name)

        check_still_running.delay = milliseconds
        check_still_running.rpcinterface = self
        return check_still_running # deferred

    def startAllProcesses(self, timeout=500):
        """ Start all processes listed in the configuration file

        @param int timeout Number of milliseconds to wait for each process start
        @return struct result     A structure containing start statuses
        """
        self._update('startAllProcesses')

        try:
            timeout = int(timeout)
        except:
            raise RPCError(Faults.BAD_ARGUMENTS, 'timeout: %s' % timeout)

        processes = self.supervisord.processes.values()
        processes.sort() # asc by priority

        results = []
        callbacks = []

        for process in processes:
            if process.get_state() != ProcessStates.RUNNING:
                # only start nonrunning processes
                try:
                    callbacks.append((process.config.name,
                              self.startProcess(process.config.name, timeout)))
                except RPCError, e:
                    results.append({'name':process.config.name, 'status':e.code,
                                    'description':e.text})
                    continue

        def startall(done=False): # done arg is for unit testing
            if not callbacks:
                return results

            name, callback = callbacks.pop(0)
            try:
                value = callback(done)
            except RPCError, e:
                results.append({'name':name, 'status':e.code,
                                'description':e.text})
                return NOT_DONE_YET
            
            if value is NOT_DONE_YET:
                # push it back into the queue; it will finish eventually
                callbacks.append((name,callback))
            else:
                results.append({'name':name, 'status':Faults.SUCCESS,
                                'description':'OK'})

            if callbacks:
                return NOT_DONE_YET

            return results

        # XXX the above implementation has a weakness inasmuch as the
        # first call into each individual process callback will always
        # return NOT_DONE_YET, so they need to be called twice.  The
        # symptom of this is that calling this method causes the
        # client to block for much longer than it actually requires to
        # start all of the nonrunning processes.  See stopAllProcesses

        startall.delay = 0.05
        startall.rpcinterface = self
        return startall # deferred

    def stopProcess(self, name):
        """ Stop a process named by name

        @param string name  The name of the process to stop
        @return boolean result     Always return True unless error
        """
        self._update('stopProcess')

        process = self.supervisord.processes.get(name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        if process.get_state() != ProcessStates.RUNNING:
            raise RPCError(Faults.NOT_RUNNING)

        def killit():
            if process.killing:
                return NOT_DONE_YET
            elif process.pid:
                msg = process.stop()
                if msg is not None:
                    raise RPCError(Faults.FAILED, name)
                return NOT_DONE_YET
            else:
                return True

        killit.delay = 0.2
        killit.rpcinterface = self
        return killit # deferred

    def stopAllProcesses(self):
        """ Stop all processes in the process list

        @return boolean result Always return true unless error.
        """
        self._update('stopAllProcesses')
        processes = self.supervisord.processes.values()
        processes.sort()
        processes.reverse() # stop in reverse priority order

        callbacks = []
        results = []

        for process in processes:
            if process.get_state() == ProcessStates.RUNNING:
                # only stop running processes
                try:
                    callbacks.append((process.config.name,
                                      self.stopProcess(process.config.name)))
                except RPCError, e:
                    results.append({'name':name, 'status':e.code,
                                    'description':e.text})
                    continue

        def killall():
            if not callbacks:
                return results

            name, callback = callbacks.pop(0)
            try:
                value = callback()
            except RPCError, e:
                results.append({'name':name, 'status':e.code,
                                'description':e.text})
                return NOT_DONE_YET
            
            if value is NOT_DONE_YET:
                # push it back into the queue; it will finish eventually
                callbacks.append((name, callback))
            else:
                results.append({'name':name, 'status':Faults.SUCCESS,
                                'description':'OK'})

            if callbacks:
                return NOT_DONE_YET

            return results

        # XXX the above implementation has a weakness inasmuch as the
        # first call into each individual process callback will always
        # return NOT_DONE_YET, so they need to be called twice.  The
        # symptom of this is that calling this method causes the
        # client to block for much longer than it actually requires to
        # kill all of the running processes.  After the first call to
        # the killit callback, the process is actually dead, but the
        # above killall method processes the callbacks one at a time
        # during the select loop, which, because there is no output
        # from child processes after stopAllProcesses is called, is
        # not busy, so hits the timeout for each callback.  I
        # attempted to make this better, but the only way to make it
        # better assumes totally synchronous reaping of child
        # processes, which requires infrastructure changes to
        # supervisord that are scary at the moment as it could take a
        # while to pin down all of the platform differences and might
        # require a C extension to the Python signal module to allow
        # the setting of ignore flags to signals.

        killall.delay = 0.05
        killall.rpcinterface = self
        return killall # deferred

    def getProcessInfo(self, name):
        """ Get info about a process named name

        @param string name The name of the process
        @return struct result     A structure containing data about the process
        """
        self._update('getProcessInfo')
        
        process = self.supervisord.processes.get(name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        start = int(process.laststart)
        stop = int(process.laststop)
        now = int(time.time())
        
        state = process.get_state()
        spawnerr = process.spawnerr or ''
        exitstatus = process.exitstatus or 0
        reportstatusmsg = process.reportstatusmsg or ''

        return {
            'name':name,
            'start':start,
            'stop':stop,
            'now':now,
            'state':state,
            'spawnerr':spawnerr,
            'exitstatus':exitstatus,
            'reportstatusmsg':reportstatusmsg,
            'logfile':process.config.logfile,
            'pid':process.pid
            }

    def getAllProcessInfo(self):
        """ Get info about all processes

        @return array result  An array of process status results
        """
        self._update('getAllProcessInfo')

        processnames = self.supervisord.processes.keys()
        processnames.sort()
        output = []
        for processname in processnames:
            output.append(self.getProcessInfo(processname))
        return output

    def readProcessLog(self, name, offset, length):
        """ Read length bytes from processName's log starting at offset

        @param string name The name of the process
        @param int offset         offset to start reading from.
        @param int length         number of bytes to read from the log.
        @return string result     Bytes of log
        """
        self._update('readProcessLog')

        process = self.supervisord.processes.get(name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        logfile = process.config.logfile

        if logfile is None or not os.path.exists(logfile):
            raise RPCError(Faults.NO_FILE, logfile)

        try:
            return _readFile(logfile, offset, length)
        except ValueError, inst:
            why = inst.args[0]
            raise RPCError(getattr(Faults, why))

    def clearProcessLog(self, name):
        """ Clear the log for processName and reopen it

        @param string name   The name of the process
        @return boolean result      Always True unless error
        """
        self._update('clearProcessLog')

        process = self.supervisord.processes.get(name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        try:
            # implies a reopen
            process.removelogs()
        except (IOError, os.error):
            raise RPCError(Faults.FAILED, name)

        return True

    def clearAllProcessLogs(self):
        """ Clear all process log files

        @return boolean result      Always return true
        """
        self._update('clearAllProcessLogs')
        results  = []
        callbacks = []

        processnames = self.supervisord.processes.keys()
        processnames.sort()
        
        for processname in processnames:
            callbacks.append((processname, self.clearProcessLog))

        def clearall():
            if not callbacks:
                return results

            name, callback = callbacks.pop(0)
            try:
                callback(name)
            except RPCError, e:
                results.append({'name':name, 'status':e.code,
                                'description':e.text})
            else:
                results.append({'name':name, 'status':Faults.SUCCESS,
                                'description':'OK'})
            
            if callbacks:
                return NOT_DONE_YET

            return results
        
        clearall.delay = 0.05
        clearall.rpcinterface = self
        return clearall # deferred

    def _rotateMainLog(self):
        """ Rotate the main supervisord log (for debugging/testing) """
        self._update('_rotateMainLog')
        
        for handler in self.supervisord.options.logger.handlers:
            if hasattr(handler, 'doRollover'):
                handler.doRollover()
        return True
        
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
                meth = getattr(func, 'im_func', None)
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
        keys = methods.keys()
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
        L = []
        for method in methods:
            if method == name:
                rtype = None
                ptypes = []
                parsed = doctags.gettags(methods[method])
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
        single-item array containg the result value, or a struct of
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
                    error = 'INCORRECT_PARAMETERS'
                    raise xmlrpclib.Fault(Faults.INCORRECT_PARAMETERS,
                                          error)
                root = AttrDict(self.namespaces)
                value = traverse(root, name, params)
            except RPCError, inst:
                value = {'faultCode': inst.code,
                         'faultString': inst.text}
            except:
                errmsg = "%s:%s" % (sys.exc_type, sys.exc_value)
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
                except RPCError, inst:
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

class RPCInterface:
    def __init__(self, supervisord):
        self.supervisord = supervisord
        self.supervisor = SupervisorNamespaceRPCInterface(supervisord)
        self.system = SystemNamespaceRPCInterface(
            [('supervisor', self.supervisor)]
            )

class supervisor_xmlrpc_handler(xmlrpc_handler):
    def __init__(self, supervisord):
        self.rpcinterface = RPCInterface(supervisord)
        self.supervisord = supervisord
        
    def continue_request (self, data, request):
        logger = self.supervisord.options.logger
        
        try:

            params, method = xmlrpclib.loads(data)

            try:
                # 5 is 'trace' level
                logger.log(5, 'XML-RPC method called: %s()' % method)
                value = self.call(method, params)
                logger.log(5, 'XML-RPC method %s() returned successfully' %
                            method)
            except RPCError, err:
                # turn RPCError reported by method into a Fault instance
                value = xmlrpclib.Fault(err.code, err.text)
                logger.warn('XML-RPC method %s() returned fault: [%d] %s' % (
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
            io = StringIO.StringIO()
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

def _readFile(filename, offset, length):
    """ Read length bytes from the file named by filename starting at
    offset """

    absoffset = abs(offset)
    abslength = abs(length)

    try:
        f = open(filename, 'rb')
        if absoffset != offset:
            # negative offset returns offset bytes from tail of the file
            if length:
                raise ValueError('BAD_ARGUMENTS')
            f.seek(0, 2)
            sz = f.tell()
            pos = int(sz - absoffset)
            if pos < 0:
                pos = 0
            f.seek(pos)
            data = f.read(absoffset)
        else:
            if abslength != length:
                raise ValueError('BAD_ARGUMENTS')
            if length == 0:
                f.seek(offset)
                data = f.read()
            else:
                sz = f.seek(offset)
                data = f.read(length)
    except (os.error, IOError):
        raise ValueError('FAILED')

    return data

