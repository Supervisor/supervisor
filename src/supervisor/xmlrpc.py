import xmlrpclib
import os
import datetime
import sys
import types
import re
import traceback
import StringIO
import time

from medusa.xmlrpc_handler import xmlrpc_handler
from medusa.http_server import get_header
from medusa import producers

from supervisor.http import NOT_DONE_YET
from supervisor.options import readFile
from supervisor.options import tailFile
from supervisor.options import gettags

from supervisor.options import NotExecutable
from supervisor.options import NotFound
from supervisor.options import NoPermission

from supervisor.supervisord import ProcessStates
from supervisor.supervisord import SupervisorStates
from supervisor.supervisord import getSupervisorStateDescription
from supervisor.supervisord import getProcessStateDescription

RPC_VERSION  = '1.0'

class Faults:
    UNKNOWN_METHOD = 1
    INCORRECT_PARAMETERS = 2
    BAD_ARGUMENTS = 3
    SIGNATURE_UNSUPPORTED = 4
    SHUTDOWN_STATE = 6
    BAD_NAME = 10
    NO_FILE = 20
    NOT_EXECUTABLE = 21
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
    COMMAND_SEPARATOR = re.compile('\s+')

    def __init__(self, supervisord):
        self.supervisord = supervisord

    def _update(self, text):
        self.update_text = text # for unit tests, mainly

        state = self.supervisord.get_state()

        if state == SupervisorStates.SHUTDOWN:
            raise RPCError(Faults.SHUTDOWN_STATE)

    # RPC API methods

    def getAPIVersion(self):
        """ Return the version of the RPC API used by supervisord

        @return string version version id
        """
        self._update('getAPIVersion')
        return RPC_VERSION

    getVersion = getAPIVersion # b/w compatibility with releases before 2.3

    def getSupervisorVersion(self):
        """ Return the version of the supervisor package in use by supervisord

        @return string version version id
        """
        self._update('getSupervisorVersion')
        import options
        return options.VERSION

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
        """ Read length bytes from the main log starting at offset

        @param int offset         offset to start reading from.
        @param int length         number of bytes to read from the log.
        @return string result     Bytes of log
        """
        self._update('readLog')

        logfile = self.supervisord.options.logfile

        if logfile is None or not os.path.exists(logfile):
            raise RPCError(Faults.NO_FILE, logfile)

        try:
            return readFile(logfile, int(offset), int(length))
        except ValueError, inst:
            why = inst.args[0]
            raise RPCError(getattr(Faults, why))

    readMainLog = readLog # b/w compatibility with releases before 2.1

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

    def startProcess(self, name, wait=True):
        """ Start a process

        @param string name Process name
        @param boolean wait Wait for process to be fully started
        @return boolean result     Always true unless error

        """
        self._update('startProcess')

        # get process to start from name
        processes = self.supervisord.processes
        process = processes.get(name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)
        
        # test filespec, don't bother trying to spawn if we know it will
        # eventually fail
        try:
            filename, argv = process.get_execv_args()
        except NotFound, why:
            raise RPCError(Faults.NO_FILE, why.args[0])
        except (NotExecutable, NoPermission), why:
            raise RPCError(Faults.NOT_EXECUTABLE, why.args[0])

        started = []

        startsecs = process.config.startsecs

        running_states = (ProcessStates.RUNNING,
                          ProcessStates.BACKOFF,
                          ProcessStates.STARTING)

        def startit():
            if not started:

                if process.get_state() in running_states:
                    raise RPCError(Faults.ALREADY_STARTED, name)

                process.spawn()

                if process.spawnerr:
                    raise RPCError(Faults.SPAWN_ERROR, name)

                # we use a list here to fake out lexical scoping;
                # using a direct assignment to 'started' in the
                # function appears to not work (symptom: 2nd or 3rd
                # call through, it forgets about 'started', claiming
                # it's undeclared).
                started.append(time.time())


            if not wait or not startsecs:
                return True
                
            t = time.time()
            runtime = (t - started[0])
            state = process.get_state()

            if state not in (ProcessStates.STARTING, ProcessStates.RUNNING):
                raise RPCError(Faults.ABNORMAL_TERMINATION, name)

            if runtime < startsecs:
                return NOT_DONE_YET

            if state == ProcessStates.RUNNING:
                return True
            raise RPCError(Faults.ABNORMAL_TERMINATION, name)

        startit.delay = 0.05
        startit.rpcinterface = self
        return startit # deferred

    def startAllProcesses(self, wait=True):
        """ Start all processes listed in the configuration file

        @param boolean wait Wait for each process to be fully started
        @return struct result     A structure containing start statuses
        """
        self._update('startAllProcesses')

        processes = self.supervisord.processes.values()
        processes.sort() # asc by priority

        results = []
        callbacks = []

        running_states = (ProcessStates.RUNNING,
                          ProcessStates.BACKOFF,
                          ProcessStates.STARTING)

        def startall():
            if not callbacks:

                for process in processes:
                    if process.get_state() not in running_states:
                        # only start nonrunning processes
                        try:
                            callbacks.append((
                                process.config.name,
                                self.startProcess(process.config.name, wait)))
                        except RPCError, e:
                            results.append({'name':process.config.name,
                                            'status':e.code,
                                            'description':e.text})
                            continue

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

        stopped = []
        called  = []

        running_states = (ProcessStates.RUNNING,
                          ProcessStates.STARTING,
                          ProcessStates.BACKOFF)

        def killit():
            if not called:
                if process.get_state() not in running_states:
                    raise RPCError(Faults.NOT_RUNNING)
                # use a mutable for lexical scoping; see startProcess
                called.append(1)

            if not stopped:
                msg = process.stop()
                if msg is not None:
                    raise RPCError(Faults.FAILED, msg)
                stopped.append(1)
                return NOT_DONE_YET
            
            if process.get_state() not in (ProcessStates.STOPPED,
                                           ProcessStates.EXITED):
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

        running_states = (ProcessStates.RUNNING,
                          ProcessStates.STARTING,
                          ProcessStates.BACKOFF)

        def killall():
            if not callbacks:

                for process in processes:
                    if process.get_state() in running_states:
                        # only stop running processes
                        try:
                            callbacks.append(
                                (process.config.name,
                                 self.stopProcess(process.config.name)))
                        except RPCError, e:
                            name = process.config.name
                            results.append({'name':name, 'status':e.code,
                                            'description':e.text})
                            continue

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

    def _interpretProcessInfo(self, info):
        state = info['state']

        if state == ProcessStates.RUNNING:
            start = info['start']
            now = info['now']
            start_dt = datetime.datetime(*time.gmtime(start)[:6])
            now_dt = datetime.datetime(*time.gmtime(now)[:6])
            uptime = now_dt - start_dt
            desc = 'pid %s, uptime %s' % (info['pid'], uptime)

        elif state in (ProcessStates.FATAL, ProcessStates.BACKOFF):
            desc = info['spawnerr']
            if not desc:
                desc = 'unknown error (try "tail %s")' % info['name']

        elif state in (ProcessStates.STOPPED, ProcessStates.EXITED):
            if info['start']:
                stop = info['stop']
                stop_dt = datetime.datetime(*time.localtime(stop)[:7])
                desc = stop_dt.strftime('%b %d %I:%M %p')
            else:
                desc = 'Not started'

        else:
            desc = ''

        return desc

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

        info = {
            'name':name,
            'start':start,
            'stop':stop,
            'now':now,
            'state':state,
            'statename':getProcessStateDescription(state),
            'spawnerr':spawnerr,
            'exitstatus':exitstatus,
            'logfile':process.config.logfile,
            'pid':process.pid
            }
        
        description = self._interpretProcessInfo(info)
        info['description'] = description
        return info

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
        """ Read length bytes from name's log starting at offset

        @param string name        the name of the process
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
            return readFile(logfile, int(offset), int(length))
        except ValueError, inst:
            why = inst.args[0]
            raise RPCError(getattr(Faults, why))

    def tailProcessLog(self, name, offset, length):
        """
        Provides a more efficient way to tail logs than readProcessLog().
        Use readProcessLog() to read chucks and tailProcessLog() to tail.
        
        Requests (length) bytes from the (name)'s log, starting at 
        (offset).  If the total log size is greater than (offset + length), 
        the overflow flag is set and the (offset) is automatically increased 
        to position the buffer at the end of the log.  If less than (length) 
        bytes are available, the maximum number of available bytes will be 
        returned.  (offset) returned is always the last offset in the log +1.

        @param string name         the name of the process
        @param int offset          offset to start reading from
        @param int length          maximum number of bytes to return
        @return array result       [string bytes, int offset, bool overflow]
        """
        self._update('tailProcessLog')

        process = self.supervisord.processes.get(name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        logfile = process.config.logfile
        
        if logfile is None or not os.path.exists(logfile):
            return ['', 0, False]

        return tailFile(logfile, int(offset), int(length))

    def clearProcessLog(self, name):
        """ Clear the log for name and reopen it

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
                    raise RPCError(Faults.INCORRECT_PARAMETERS)
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

class RootRPCInterface:
    def __init__(self, subinterfaces):
        for name, rpcinterface in subinterfaces:
            setattr(self, name, rpcinterface)

class supervisor_xmlrpc_handler(xmlrpc_handler):
    def __init__(self, supervisord, subinterfaces):
        self.rpcinterface = RootRPCInterface(subinterfaces)
        self.supervisord = supervisord
        
    def continue_request (self, data, request):
        logger = self.supervisord.options.logger
        
        try:

            params, method = xmlrpclib.loads(data)

            try:
                logger.debug('XML-RPC method called: %s()' % method)
                value = self.call(method, params)
                # application-specific: instead of we never want to
                # marshal None (even though we could by saying allow_none=True
                # in dumps within xmlrpc_marshall), this is meant as
                # a debugging fixture, see issue 223.
                assert value is not None, (
                    'return value from method %r with params %r is None' %
                    (method, params)
                    )
                logger.debug('XML-RPC method %s() returned successfully' %
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

def make_main_rpcinterface(supervisord):
    return SupervisorNamespaceRPCInterface(supervisord)
