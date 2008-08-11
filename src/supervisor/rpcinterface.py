##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the BSD-like license at
# http://www.repoze.org/LICENSE.txt.  A copy of the license should accompany
# this distribution.  THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL
# EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND
# FITNESS FOR A PARTICULAR PURPOSE
#
##############################################################################

import os
import time
import datetime
import errno

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

from supervisor.states import SupervisorStates
from supervisor.states import getSupervisorStateDescription
from supervisor.states import ProcessStates
from supervisor.states import getProcessStateDescription
from supervisor.states import RUNNING_STATES

API_VERSION  = '3.0'

class SupervisorNamespaceRPCInterface:
    def __init__(self, supervisord):
        self.supervisord = supervisord

    def _update(self, text):
        self.update_text = text # for unit tests, mainly
        if self.supervisord.options.mood < SupervisorStates.RUNNING:
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

        state = self.supervisord.options.mood
        statename = getSupervisorStateDescription(state)
        data =  {
            'statecode':state,
            'statename':statename,
            }
        return data

    def getPID(self):
        """ Return the PID of supervisord
        
        @return int PID
        """
        self._update('getPID')
        return self.supervisord.options.get_pid()

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
        except (OSError, IOError):
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
        self.supervisord.options.mood = SupervisorStates.SHUTDOWN
        return True

    def restart(self):
        """ Restart the supervisor process

        @return boolean result  always return True unless error
        """
        self._update('restart')
        
        self.supervisord.options.mood = SupervisorStates.RESTARTING
        return True

    def addProcessGroup(self, name):
        """ Update the config for a running process from config file.

        @param string name         name of process group to add
        @return boolean result     true if successful
        """
        self._update('addProcessGroup')

        for config in self.supervisord.options.process_group_configs:
            if config.name == name:
                result = self.supervisord.add_process_group(config)
                if not result:
                    raise RPCError(Faults.ALREADY_ADDED, name)
                return True
        raise RPCError(Faults.BAD_NAME, name)

    def removeProcessGroup(self, name):
        """ Remove a stopped process from the active configuration.

        @param string name         name of process group to remove
        @return boolean result     Indicates wether the removal was successful
        """
        self._update('removeProcessGroup')
        if name not in self.supervisord.process_groups:
            raise RPCError(Faults.BAD_NAME, name)

        result = self.supervisord.remove_process_group(name)
        if not result:
            raise RPCError(Faults.STILL_RUNNING)
        return True

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

    def _getGroupAndProcess(self, name):
        # get process to start from name
        group_name, process_name = split_namespec(name)

        group = self.supervisord.process_groups.get(group_name)
        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        if process_name is None:
            return group, None

        process = group.processes.get(process_name)
        if process is None:
            raise RPCError(Faults.BAD_NAME, name)
        
        return group, process
        
    def startProcess(self, name, wait=True):
        """ Start a process

        @param string name Process name (or 'group:name', or 'group:*')
        @param boolean wait Wait for process to be fully started
        @return boolean result     Always true unless error

        """
        self._update('startProcess')
        group, process = self._getGroupAndProcess(name)
        if process is None:
            group_name, process_name = split_namespec(name)
            return self.startProcessGroup(group_name, wait)

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

        def startit():
            if not started:

                if process.get_state() in RUNNING_STATES:
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

    def startProcessGroup(self, name, wait=True):
        """ Start all processes in the group named 'name'

        @param string name        The group name
        @param boolean wait       Wait for each process to be fully started
        @return struct result     A structure containing start statuses
        """
        self._update('startProcessGroup')

        group = self.supervisord.process_groups.get(name)

        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        processes = group.processes.values()
        processes.sort()
        processes = [ (group, process) for process in processes ]

        startall = make_allfunc(processes, isNotRunning, self.startProcess,
                                wait=wait)
            
        startall.delay = 0.05
        startall.rpcinterface = self
        return startall # deferred

    def startAllProcesses(self, wait=True):
        """ Start all processes listed in the configuration file

        @param boolean wait Wait for each process to be fully started
        @return struct result     A structure containing start statuses
        """
        self._update('startAllProcesses')

        processes = self._getAllProcesses()
        startall = make_allfunc(processes, isNotRunning, self.startProcess,
                                wait=wait)

        startall.delay = 0.05
        startall.rpcinterface = self
        return startall # deferred

    def stopProcess(self, name, wait=True):
        """ Stop a process named by name

        @param string name  The name of the process to stop (or 'group:name')
        @param boolean wait        Wait for the process to be fully stopped
        @return boolean result     Always return True unless error
        """
        self._update('stopProcess')

        group, process = self._getGroupAndProcess(name)

        if process is None:
            group_name, process_name = split_namespec(name)
            return self.stopProcessGroup(group_name, wait)

        stopped = []
        called  = []

        def killit():
            if not called:
                if process.get_state() not in RUNNING_STATES:
                    raise RPCError(Faults.NOT_RUNNING)
                # use a mutable for lexical scoping; see startProcess
                called.append(1)

            if not stopped:
                msg = process.stop()
                if msg is not None:
                    raise RPCError(Faults.FAILED, msg)
                stopped.append(1)
                
                if wait:
                    return NOT_DONE_YET
                else:
                    return True
            
            if process.get_state() not in (ProcessStates.STOPPED,
                                           ProcessStates.EXITED):
                return NOT_DONE_YET
            else:
                return True

        killit.delay = 0.2
        killit.rpcinterface = self
        return killit # deferred

    def stopProcessGroup(self, name, wait=True):
        """ Stop all processes in the process group named 'name'

        @param string name  The group name
        @param boolean wait    Wait for each process to be fully stopped
        @return boolean result Always return true unless error.
        """
        self._update('stopProcessGroup')
        
        group = self.supervisord.process_groups.get(name)

        if group is None:
            raise RPCError(Faults.BAD_NAME, name)

        processes = group.processes.values()
        processes.sort()
        processes = [ (group, process) for process in processes ]

        killall = make_allfunc(processes, isRunning, self.stopProcess,
                               wait=wait)
            
        killall.delay = 0.05
        killall.rpcinterface = self
        return killall # deferred

    def stopAllProcesses(self, wait=True):
        """ Stop all processes in the process list

        @param boolean wait    Wait for each process to be fully stopped
        @return boolean result Always return true unless error.
        """
        self._update('stopAllProcesses')
        
        processes = self._getAllProcesses()

        killall = make_allfunc(processes, isRunning, self.stopProcess,
                               wait=wait)

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

        group, process = self._getGroupAndProcess(name)

        start = int(process.laststart)
        stop = int(process.laststop)
        now = int(time.time())
        
        state = process.get_state()
        spawnerr = process.spawnerr or ''
        exitstatus = process.exitstatus or 0
        stdout_logfile = process.config.stdout_logfile or ''
        stderr_logfile = process.config.stderr_logfile or ''

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
            'logfile':stdout_logfile, # b/c alias
            'stdout_logfile':stdout_logfile,
            'stderr_logfile':stderr_logfile,
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

    def _readProcessLog(self, name, offset, length, channel):
        group, process = self._getGroupAndProcess(name)

        logfile = getattr(process.config, '%s_logfile' % channel)

        if logfile is None or not os.path.exists(logfile):
            raise RPCError(Faults.NO_FILE, logfile)

        try:
            return readFile(logfile, int(offset), int(length))
        except ValueError, inst:
            why = inst.args[0]
            raise RPCError(getattr(Faults, why))

    def readProcessStdoutLog(self, name, offset, length):
        """ Read length bytes from name's stdout log starting at offset

        @param string name        the name of the process (or 'group:name')
        @param int offset         offset to start reading from.
        @param int length         number of bytes to read from the log.
        @return string result     Bytes of log
        """
        self._update('readProcessStdoutLog')
        return self._readProcessLog(name, offset, length, 'stdout')

    readProcessLog = readProcessStdoutLog # b/c alias

    def readProcessStderrLog(self, name, offset, length):
        """ Read length bytes from name's stderr log starting at offset

        @param string name        the name of the process (or 'group:name')
        @param int offset         offset to start reading from.
        @param int length         number of bytes to read from the log.
        @return string result     Bytes of log
        """
        self._update('readProcessStderrLog')
        return self._readProcessLog(name, offset, length, 'stderr')

    def _tailProcessLog(self, name, offset, length, channel):
        group, process = self._getGroupAndProcess(name)

        logfile = getattr(process.config, '%s_logfile' % channel)
        
        if logfile is None or not os.path.exists(logfile):
            return ['', 0, False]

        return tailFile(logfile, int(offset), int(length))

    def tailProcessStdoutLog(self, name, offset, length):
        """
        Provides a more efficient way to tail the (stdout) log than
        readProcessStdoutLog().  Use readProcessStdoutLog() to read
        chunks and tailProcessStdoutLog() to tail.
        
        Requests (length) bytes from the (name)'s log, starting at
        (offset).  If the total log size is greater than (offset +
        length), the overflow flag is set and the (offset) is
        automatically increased to position the buffer at the end of
        the log.  If less than (length) bytes are available, the
        maximum number of available bytes will be returned.  (offset)
        returned is always the last offset in the log +1.

        @param string name         the name of the process (or 'group:name')
        @param int offset          offset to start reading from
        @param int length          maximum number of bytes to return
        @return array result       [string bytes, int offset, bool overflow]
        """
        self._update('tailProcessStdoutLog')
        return self._tailProcessLog(name, offset, length, 'stdout')

    tailProcessLog = tailProcessStdoutLog # b/c alias

    def tailProcessStderrLog(self, name, offset, length):
        """
        Provides a more efficient way to tail the (stderr) log than
        readProcessStderrLog().  Use readProcessStderrLog() to read
        chunks and tailProcessStderrLog() to tail.
        
        Requests (length) bytes from the (name)'s log, starting at
        (offset).  If the total log size is greater than (offset +
        length), the overflow flag is set and the (offset) is
        automatically increased to position the buffer at the end of
        the log.  If less than (length) bytes are available, the
        maximum number of available bytes will be returned.  (offset)
        returned is always the last offset in the log +1.

        @param string name         the name of the process (or 'group:name')
        @param int offset          offset to start reading from
        @param int length          maximum number of bytes to return
        @return array result       [string bytes, int offset, bool overflow]
        """
        self._update('tailProcessStderrLog')
        return self._tailProcessLog(name, offset, length, 'stderr')

    def clearProcessLogs(self, name):
        """ Clear the stdout and stderr logs for the named process and
        reopen them.

        @param string name   The name of the process (or 'group:name')
        @return boolean result      Always True unless error
        """
        self._update('clearProcessLogs')

        group, process = self._getGroupAndProcess(name)

        try:
            # implies a reopen
            process.removelogs()
        except (IOError, OSError):
            raise RPCError(Faults.FAILED, name)

        return True

    clearProcessLog = clearProcessLogs # b/c alias

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

    def sendProcessStdin(self, name, chars):
        """ Send a string of chars to the stdin of the process name.
        If non-7-bit data is sent (unicode), it is encoded to utf-8
        before being sent to the process' stdin.  If chars is not a
        string or is not unicode, raise INCORRECT_PARAMETERS.  If the
        process is not running, raise NOT_RUNNING.  If the process' 
        stdin cannot accept input (e.g. it was closed by the child 
        process), raise NO_FILE.

        @param string name        The process name to send to (or 'group:name')
        @param string chars       The character data to send to the process
        @return boolean result    Always return True unless error
        """
        self._update('sendProcessStdin')

        if isinstance(chars, unicode):
            chars = chars.encode('utf-8')

        if not isinstance(chars, basestring):
            raise RPCError(Faults.INCORRECT_PARAMETERS, chars)

        group, process = self._getGroupAndProcess(name)

        if process is None:
            raise RPCError(Faults.BAD_NAME, name)

        if not process.pid or process.killing:
            raise RPCError(Faults.NOT_RUNNING, name)

        try:
            process.write(chars)
        except OSError, why:
            if why[0] == errno.EPIPE:
                raise RPCError(Faults.NO_FILE, name)
            else:
                raise

        return True

def make_allfunc(processes, predicate, func, **extra_kwargs):
    """ Return a closure representing a function that calls a
    function for every process, and returns a result """

    callbacks = []
    results = []

    def allfunc(processes=processes, predicate=predicate, func=func,
                extra_kwargs=extra_kwargs, callbacks=callbacks,
                results=results):
        if not callbacks:

            for group, process in processes:
                name = make_namespec(group.config.name, process.config.name)
                if predicate(process):
                    try:
                        callback = func(name, **extra_kwargs)
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
    # from child processes after e.g. stopAllProcesses is called,
    # is not busy, so hits the timeout for each callback.  I
    # attempted to make this better, but the only way to make it
    # better assumes totally synchronous reaping of child
    # processes, which requires infrastructure changes to
    # supervisord that are scary at the moment as it could take a
    # while to pin down all of the platform differences and might
    # require a C extension to the Python signal module to allow
    # the setting of ignore flags to signals.
    return allfunc

def isRunning(process):
    if process.get_state() in RUNNING_STATES:
        return True

def isNotRunning(process):
    return not isRunning(process)

# this is not used in code but referenced via an entry point in the conf file
def make_main_rpcinterface(supervisord):
    return SupervisorNamespaceRPCInterface(supervisord)

