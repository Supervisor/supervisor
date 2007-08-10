import os
import time
import datetime

from supervisor.options import readFile
from supervisor.options import tailFile
from supervisor.options import NotExecutable
from supervisor.options import NotFound
from supervisor.options import NoPermission
from supervisor.options import make_namespec
from supervisor.options import split_namespec

from supervisor.http import NOT_DONE_YET
from supervisor.xmlrpc import Faults
from supervisor.xmlrpc import RPCError

from supervisor.supervisord import SupervisorStates
from supervisor.supervisord import getSupervisorStateDescription
from supervisor.process import ProcessStates
from supervisor.process import getProcessStateDescription

API_VERSION  = '2.0'

class SupervisorNamespaceRPCInterface:
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
        return API_VERSION

    getVersion = getAPIVersion # b/w compatibility with releases before 3.0

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
        if  logfile is None or not self.supervisord.options.exists(logfile):
            raise RPCError(Faults.NO_FILE)

        # there is a race condition here, but ignore it.
        try:
            self.supervisord.options.remove(logfile)
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

        @param string name Process name (or 'group:name')
        @param boolean wait Wait for process to be fully started
        @return boolean result     Always true unless error

        """
        self._update('startProcess')

        # get process to start from name
        group_name, process_name = split_namespec(name)

        group = self.supervisord.process_groups.get(group_name)
        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        process = group.processes.get(process_name)
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

    def _getAllProcesses(self, lexical=False):
        # if lexical is true, return processes sorted in lexical order,
        # otherwise, sort in priority order
        all_processes = []

        if lexical:
            group_names = self.supervisord.process_groups.keys()
            group_names.sort()
            for group_name in group_names:
                group = self.supervisord.process_groups[group_name]
                process_names = group.processes.keys()
                process_names.sort()
                for process_name in process_names:
                    process = group.processes[process_name]
                    all_processes.append((group, process))
        else:
            groups = self.supervisord.process_groups.values()
            groups.sort() # asc by priority

            for group in groups:
                processes = group.processes.values()
                processes.sort() # asc by priority
                for process in processes:
                    all_processes.append((group, process))

        return all_processes

    def startAllProcesses(self, wait=True):
        """ Start all processes listed in the configuration file

        @param boolean wait Wait for each process to be fully started
        @return struct result     A structure containing start statuses
        """
        self._update('startAllProcesses')

        all_processes = self._getAllProcesses()

        results = []
        callbacks = []
        running_states = (ProcessStates.RUNNING,
                          ProcessStates.BACKOFF,
                          ProcessStates.STARTING)

        def startall():
            if not callbacks:

                for group, process in all_processes:
                    name = make_namespec(group.config.name, process.config.name)
                    if process.get_state() not in running_states:
                        # only start nonrunning processes
                        try:
                            callback = self.startProcess(name, wait)
                            callbacks.append((group, process, callback))
                        except RPCError, e:
                            results.append({'name':process.config.name,
                                            'group':group.config.name,
                                            'status':e.code,
                                            'description':e.text})
                            continue

            if not callbacks:
                return results

            group, process, callback = callbacks.pop(0)

            try:
                value = callback()
            except RPCError, e:
                results.append({'name':process.config.name,
                                'group':group.config.name,
                                'status':e.code,
                                'description':e.text})
                return NOT_DONE_YET

            if value is NOT_DONE_YET:
                # push it back into the queue; it will finish eventually
                callbacks.append((group, process, callback))
            else:
                results.append({'name':process.config.name,
                                'group':group.config.name,
                                'status':Faults.SUCCESS,
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

        @param string name  The name of the process to stop (or 'group:name')
        @return boolean result     Always return True unless error
        """
        self._update('stopProcess')

        # get process to start from name
        group_name, process_name = split_namespec(name)

        group = self.supervisord.process_groups.get(group_name)
        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        process = group.processes.get(process_name)
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
        
        all_processes = self._getAllProcesses()

        callbacks = []
        results = []

        running_states = (ProcessStates.RUNNING,
                          ProcessStates.STARTING,
                          ProcessStates.BACKOFF)

        def killall():
            if not callbacks:

                for group, process in all_processes:
                    name = make_namespec(group.config.name, process.config.name)
                    if process.get_state() in running_states:
                        # only stop running processes
                        try:
                            callback = self.stopProcess(name)
                            callbacks.append((group, process, callback))
                        except RPCError, e:
                            results.append({'name':process.config.name,
                                            'group':group.config.name,
                                            'status':e.code,
                                            'description':e.text})
                            continue

            if not callbacks:
                return results

            group, process, callback = callbacks.pop(0)

            try:
                value = callback()
            except RPCError, e:
                results.append(
                    {'name':process.config.name,
                     'group':group.config.name,
                     'status':e.code,
                     'description':e.text})
                return NOT_DONE_YET
            
            if value is NOT_DONE_YET:
                # push it back into the queue; it will finish eventually
                callbacks.append((group, process, callback))
            else:
                results.append(
                    {'name':process.config.name,
                     'group':group.config.name,
                     'status':Faults.SUCCESS,
                     'description':'OK'}
                    )

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

        @param string name The name of the process (or 'group:name')
        @return struct result     A structure containing data about the process
        """
        self._update('getProcessInfo')

        group_name, process_name = split_namespec(name)

        group = self.supervisord.process_groups.get(group_name)
        if group is None:
            raise RPCError(Faults.BAD_NAME, name)
        
        process = group.processes.get(process_name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        start = int(process.laststart)
        stop = int(process.laststop)
        now = int(time.time())
        
        state = process.get_state()
        spawnerr = process.spawnerr or ''
        exitstatus = process.exitstatus or 0

        info = {
            'name':process.config.name,
            'group':group.config.name,
            'start':start,
            'stop':stop,
            'now':now,
            'state':state,
            'statename':getProcessStateDescription(state),
            'spawnerr':spawnerr,
            'exitstatus':exitstatus,
            'logfile':process.config.stdout_logfile,
            'pid':process.pid,
            }
        
        description = self._interpretProcessInfo(info)
        info['description'] = description
        return info

    def getAllProcessInfo(self):
        """ Get info about all processes

        @return array result  An array of process status results
        """
        self._update('getAllProcessInfo')

        all_processes = self._getAllProcesses(lexical=True)

        output = []
        for group, process in all_processes:
            name = make_namespec(group.config.name, process.config.name)
            output.append(self.getProcessInfo(name))
        return output

    def readProcessLog(self, name, offset, length):
        """ Read length bytes from name's log starting at offset

        @param string name        the name of the process (or 'group:name')
        @param int offset         offset to start reading from.
        @param int length         number of bytes to read from the log.
        @return string result     Bytes of log
        """
        self._update('readProcessLog')

        group_name, process_name = split_namespec(name)
        group = self.supervisord.process_groups.get(group_name)
        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        process = group.processes.get(process_name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        logfile = process.config.stdout_logfile

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
        Use readProcessLog() to read chunks and tailProcessLog() to tail.
        
        Requests (length) bytes from the (name)'s log, starting at 
        (offset).  If the total log size is greater than (offset + length), 
        the overflow flag is set and the (offset) is automatically increased 
        to position the buffer at the end of the log.  If less than (length) 
        bytes are available, the maximum number of available bytes will be 
        returned.  (offset) returned is always the last offset in the log +1.

        @param string name         the name of the process (or 'group:name')
        @param int offset          offset to start reading from
        @param int length          maximum number of bytes to return
        @return array result       [string bytes, int offset, bool overflow]
        """
        self._update('tailProcessLog')

        group_name, process_name = split_namespec(name)

        group = self.supervisord.process_groups.get(group_name)
        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        process = group.processes.get(process_name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        logfile = process.config.stdout_logfile
        
        if logfile is None or not os.path.exists(logfile):
            return ['', 0, False]

        return tailFile(logfile, int(offset), int(length))

    def clearProcessLog(self, name):
        """ Clear the log for the named process and reopen it.

        @param string name   The name of the process (or 'group:name')
        @return boolean result      Always True unless error
        """
        self._update('clearProcessLog')
        group_name, process_name = split_namespec(name)
        group = self.supervisord.process_groups.get(group_name)

        if group is None:
            raise RPCError(Faults.BAD_NAME, group_name)

        process = group.processes.get(process_name)
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

        all_processes = self._getAllProcesses()

        for group, process in all_processes:
            callbacks.append((group, process, self.clearProcessLog))

        def clearall():
            if not callbacks:
                return results

            group, process, callback = callbacks.pop(0)
            name = make_namespec(group.config.name, process.config.name)
            try:
                callback(name)
            except RPCError, e:
                results.append(
                    {'name':process.config.name,
                     'group':group.config.name,
                     'status':e.code,
                     'description':e.text})
            else:
                results.append(
                    {'name':process.config.name,
                     'group':group.config.name,
                     'status':Faults.SUCCESS,
                     'description':'OK'}
                    )

            if callbacks:
                return NOT_DONE_YET

            return results
        
        clearall.delay = 0.05
        clearall.rpcinterface = self
        return clearall # deferred

# this is not used in code but referenced via an entry point in the conf file
def make_main_rpcinterface(supervisord):
    return SupervisorNamespaceRPCInterface(supervisord)

