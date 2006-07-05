#!/usr/bin/env python
##############################################################################
#
# Copyright (c) 2001, 2002 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.0 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################
"""supervisord -- run a set of applications as daemons.

Usage: %s [options]

Options:
-c/--configuration URL -- configuration file or URL
-b/--backofflimit SECONDS -- set backoff limit to SECONDS (default 3)
-n/--nodaemon -- run in the foreground (same as 'nodaemon true' in config file)
-f/--forever -- try to restart processes forever when they die (default no)
-h/--help -- print this usage message and exit
-u/--user USER -- run supervisord as this user (or numeric uid)
-m/--umask UMASK -- use this umask for daemon subprocess (default is 022)
-d/--directory DIRECTORY -- directory to chdir to when daemonized
-l/--logfile FILENAME -- use FILENAME as logfile path
-y/--logfile_maxbytes BYTES -- use BYTES to limit the max size of logfile
-z/--logfile_backups NUM -- number of backups to keep when max bytes reached
-e/--loglevel LEVEL -- use LEVEL as log level (debug,info,warn,error,critical)
-j/--pidfile FILENAME -- write a pid file for the daemon process to FILENAME
-i/--identifier STR -- identifier used for this instance of supervisord
-q/--childlogdir DIRECTORY -- the log directory for child process logs
-k/--nocleanup --  prevent the process from performing cleanup (removal of
                   orphaned child log files, etc.) at startup.
-w/--http_port SOCKET -- the host/port that the HTTP server should listen on
-g/--http_username STR -- the username for HTTP auth
-r/--http_password STR -- the password for HTTP auth
-a/--minfds NUM -- the minimum number of file descriptors for start success
--minprocs NUM  -- the minimum number of processes available for start success
"""

import os
import sys
import time
import errno
import socket
import select
import signal
import asyncore
import traceback
import StringIO
import stat
import shlex

from fcntl import fcntl
from fcntl import F_SETFL, F_GETFL

from options import ServerOptions
from options import decode_wait_status
from options import signame

class ProcessStates:
    RUNNING = 0
    STOPPING = 1
    STOPPED = 2
    KILLED = 3
    NOTSTARTED = 4
    EXITED = 5
    STARTING = 6
    ERROR = 7
    UNKNOWN = 10

def getProcessStateDescription(code):
    for statename in ProcessStates.__dict__:
        if getattr(ProcessStates, statename) == code:
            return statename

class SupervisorStates:
    ACTIVE = 0
    SHUTDOWN = 1

def getSupervisorStateDescription(code):
    for statename in SupervisorStates.__dict__:
        if getattr(SupervisorStates, statename) == code:
            return statename

class Subprocess:

    """A class to manage a subprocess."""

    # Initial state; overridden by instance variables
    pid = 0 # Subprocess pid; 0 when not running
    beenstarted = False # true if has been started at least once
    laststart = 0 # Last time the subprocess was started; 0 if never
    laststop = 0  # Last time the subprocess was stopped; 0 if never
    delay = 0 # If nonzero, delay starting or killing until this time
    administrative_stop = 0 # true if the process has been stopped by an admin
    system_stop = 0 # true if the process has been stopped by the system
    killing = 0 # flag determining whether we are trying to kill this proc
    backoff = 0 # backoff counter (to backofflimit)
    waitstatus = None
    exitstatus = None
    stdin = stderr = stdout = None
    stdinfd = stderrfd = stdoutfd = None
    childlog = None # the current logger 
    spawnerr = None
    writebuffer = '' # buffer of characters read from child's stdout/stderr
    reportstatusmsg = None # message attached to instance during reportstatus()
    
    def __init__(self, options, config):
        """Constructor.

        Arguments are a ServerOptions instance and a ProcessConfig instance.
        """
        self.options = options
        self.config = config
        if config.logfile:
            self.childlog = options.getLogger(config.logfile, 10,
                                              '%(message)s',
                                              config.logfile_backups,
                                              config.logfile_maxbytes)

    def removelogs(self):
        if self.childlog:
            for handler in self.childlog.handlers:
                handler.remove()
                handler.reopen()

    def reopenlogs(self):
        if self.childlog:
            for handler in self.childlog.handlers:
                handler.reopen()

    def log(self, data):
        if data:
            if self.childlog:
                self.childlog.info(data)
            msg = '%s output:\n%s' % (self.config.name, data)
            self.options.logger.log(self.options.TRACE, msg)

    def log_writebuffer(self):
        if self.writebuffer:
            self.log(self.writebuffer)
            self.writebuffer = ''

    def drain(self):
        self.drain_stdout()
        self.drain_stderr()

    def drain_stderr(self, *ignored):
        output = _readfd(self.stderrfd)
        if self.config.log_stderr:
            self.writebuffer += output

    def drain_stdout(self, *ignored):
        output = _readfd(self.stdoutfd)
        self.writebuffer += output

    def fd_drains(self):
        if not self.stdoutfd or not self.stderrfd:
            return []

        return ( [ self.stderrfd, self.drain_stderr],
                 [self.stdoutfd, self.drain_stdout] )
        
    def get_execv_args(self):
        """Internal: turn a program name into a file name, using $PATH,
        make sure it exists """
        commandargs = shlex.split(self.config.command)

        program = commandargs[0]

        if "/" in program:
            filename = program
            try:
                st = os.stat(filename)
                return filename, commandargs, st
            except os.error:
                return filename, commandargs, None
            
        else:
            path = get_path()
            filename = None
            st = None
            for dir in path:
                filename = os.path.join(dir, program)
                try:
                    st = os.stat(filename)
                    return filename, commandargs, st
                except os.error:
                    continue
            return None, commandargs, None

    def record_spawnerr(self, msg):
        self.spawnerr = msg
        self.options.logger.critical("spawnerr: %s" % msg)
        self.do_backoff()
        self.governor()

    def spawn(self):
        """Start the subprocess.  It must not be running already.

        Return the process id.  If the fork() call fails, return 0.
        """
        if self.pid:
            msg = 'process %r already running' % self.config.name
            self.options.logger.critical(msg)
            return

        self.beenstarted = True
        self.killing = 0
        self.spawnerr = None
        self.exitstatus = None
        self.system_stop = 0
        self.administrative_stop = 0
        self.reportstatusmsg = None
        
        self.laststart = time.time()

        filename, argv, st = self.get_execv_args()

        if st is None:
            msg = "can't find command %r" % filename
            self.record_spawnerr(msg)
            return

        if stat.S_ISDIR(st[stat.ST_MODE]):
            msg = "command at %r is a directory" % filename
            self.record_spawnerr(msg)
            return

        mode = stat.S_IMODE(st[stat.ST_MODE])
        if not (mode & 0111):
            # not executable
            msg = "command at %r is not executable" % filename
            self.record_spawnerr(msg)
            return

        if not os.access(filename, os.X_OK):
            msg = "no permission to run command %r" % filename
            self.record_spawnerr(msg)
            return

        stdin = stdout = stderr = None
        child_stdin = child_stdout = child_stderr = None

        try:
            child_stdin, stdin = os.pipe()
            stdout, child_stdout = os.pipe()
            stderr, child_stderr = os.pipe()
            # use unbuffered (0) buffering for stdin
            self.stdin = os.fdopen(stdin, 'w', 0)
            # use default (-1) for stderr, stdout
            self.stdout = os.fdopen(stdout, 'r', -1)
            self.stderr = os.fdopen(stderr, 'r', -1)
            # open stderr, stdout in nonblocking mode so we can tail them
            # in the mainloop without blocking
            fcntl(stdout, F_SETFL, fcntl(stdout, F_GETFL) | os.O_NDELAY)
            fcntl(stderr, F_SETFL, fcntl(stderr, F_GETFL) | os.O_NDELAY)
            fcntl(stdin, F_SETFL, fcntl(stdin, F_GETFL) | os.O_NDELAY)
            self.stdinfd = stdin
            self.stdoutfd = stdout
            self.stderrfd = stderr
        except OSError, why:
            for fd in (child_stdin, stdin, stdout, child_stdout, stderr,
                       child_stderr):
                if fd is not None:
                    try:
                        os.close(fd)
                    except:
                        pass
            
            if why[0] == errno.EMFILE:
                # too many file descriptors open
                msg = 'too many open files to spawn %r' % self.config.name
            else:
                msg = 'unknown error: %s' % str(why)

            self.record_spawnerr(msg)
            return

        try:
            pid = os.fork()
        except os.error, why:
            if why[0] == errno.EAGAIN:
                # process table full
                msg  = 'Too many processes in process table for %r' % (
                    self.config.name)
            else:
                msg = 'unknown error: %s' % str(why)

            self.record_spawnerr(msg)
            return

        if pid != 0:
            # Parent
            self.pid = pid
            os.close(child_stdin)
            os.close(child_stdout)
            os.close(child_stderr)
            self.options.logger.info('spawned: %r with pid %s' % (
                self.config.name, pid))
            self.spawnerr = None
            self.do_backoff()
            self.options.pidhistory[pid] = self
            return pid
        
        else:
            # Child
            try:
                # prevent child from receiving signals sent to the
                # parent by calling os.setpgrp to create a new process
                # group for the child; this prevents, for instance,
                # the case of child processes being sent a SIGINT when
                # running supervisor in foreground mode and Ctrl-C in
                # the terminal window running supervisord is pressed.
                # Presumably it also prevents HUP, etc received by
                # supervisord from being sent to children.
                os.setpgrp()
                os.dup2(child_stdin, 0)
                os.dup2(child_stdout, 1)
                os.dup2(child_stderr, 2)
                for i in range(3, self.options.minfds):
                    try:
                        os.close(i)
                    except:
                        pass
                try:
                    # sending to fd 2 will put this output in the log(s)
                    msg = self.set_uid()
                    if msg:
                        os.write(2, "%s: error trying to setuid to %s!\n" %
                                 (self.config.name, self.config.uid))
                        os.write(2, "%s: %s\n" % (self.config.name, msg))
                    os.execv(filename, argv)
                except OSError, err:
                    os.write(2, "couldn't exec %s: %s\n" % (argv[0],
                                                            err.strerror))
                except:
                    os.write(2, "couldn't exec %s\n" % argv[0])
            finally:
                os._exit(127)

    def stop(self):
        """ Administrative stop """
        self.administrative_stop = 1
        self.reportstatusmsg = None
        self.do_backoff()
        return self.kill(self.config.stopsignal)

    def kill(self, sig):
        """Send a signal to the subprocess.  This may or may not kill it.

        Return None if the signal was sent, or an error message string
        if an error occurred or if the subprocess is not running.
        """
        self.options.logger.debug('kill called')
        if not self.pid:
            return "no subprocess running"
        try:
            self.options.logger.debug('killing %s (pid %s)' % (self.config.name,
                                                               self.pid))
            self.killing = 1
            self.options.kill(self.pid, sig)
        except:
            io = StringIO.StringIO()
            traceback.print_exc(file=io)
            tb = io.getvalue()
            msg = 'unknown problem killing %s (%s):%s' % (
                self.config.name, self.pid, tb)
            self.options.logger.critical(msg)
            self.pid = 0
            self.killing = 0
            return msg
            
        return None

    def governor(self):
        # Back off if respawning too frequently
        now = time.time()
        if not self.laststart:
            pass
        elif now - self.laststart < self.options.backofflimit:
            # Exited rather quickly; slow down the restarts
            self.backoff = self.backoff + 1
            if self.backoff >= self.options.backofflimit:
                if self.options.forever:
                    self.backoff = self.options.backofflimit
                else:
                    self.options.logger.critical(
                        "stopped: %s (restarting too frequently)" % (
                        self.config.name))
                    # stop trying
                    self.system_stop = 1
                    self.backoff = 0
                    self.delay = 0
                    return
            self.options.logger.info(
                "backoff: %s (avoid rapid restarts %s)" % (
                self.config.name,
                self.backoff))
            self.delay = now + self.backoff
        else:
            # Reset the backoff timer
            self.options.logger.debug(
                'resetting backoff and delay for %s' % self.config.name)
            self.backoff = 0
            self.delay = 0

    def reportstatus(self):
        self.options.logger.debug('reportstatus called')
        pid, sts = self.waitstatus
        self.waitstatus = None
        es, msg = decode_wait_status(sts)
        process = self.options.pidhistory.get(pid)

        if process is not self:
            msg = "stopped: unknown " + msg
            self.options.logger.warn(msg)
        else:
            if self.killing:
                self.killing = 0
                self.delay = 0
            elif not es in self.config.exitcodes:
                self.governor()

            self.pid = 0
            self.stdoutfd = self.stderrfd  = self.stdinfd = None
            self.stdout = self.stderr = self.stdin = None
            processname = process.config.name

            if es in self.config.exitcodes and not self.killing:
                msg = "exited: %s (%s)" % (processname,
                                           msg + "; expected")
            elif es != -1:
                msg = "exited: %s (%s)" % (processname,
                                           msg + "; not expected")
            else:
                msg = "killed: %s (%s)" % (processname, msg)
            self.options.logger.info(msg)
            self.exitstatus = es
        self.reportstatusmsg = msg

    def do_backoff(self):
        self.delay = time.time() + self.options.backofflimit

    def set_uid(self):
        if self.config.uid is None:
            return
        msg = self.options.dropPrivileges(self.config.uid)
        return msg

    def __cmp__(self, other):
        # sort by priority
        return cmp(self.config.priority, other.config.priority)

    def get_state(self):
        if self.killing:
            return ProcessStates.STOPPING
        elif self.system_stop:
            return ProcessStates.ERROR
        elif self.administrative_stop:
            return ProcessStates.STOPPED
        elif not self.pid and self.delay:
            return ProcessStates.STARTING
        elif self.pid:
            return ProcessStates.RUNNING
        else:
            if self.exitstatus == -1:
                return ProcessStates.KILLED
            elif self.exitstatus is not None:
                return ProcessStates.EXITED
            elif not self.beenstarted:
                return ProcessStates.NOTSTARTED
            else:
                return ProcessStates.UNKNOWN

class Supervisor:
    mood = 1 # 1: up, 0: restarting, -1: suicidal
    stopping = False # set after we detect that we are handling a stop request

    def __init__(self, options):
        self.options = options

    def main(self, args=None, test=False, first=False):
        self.options.realize(args)
        self.options.cleanup_fds()
        info_messages = []
        critical_messages = []
        setuid_msg = self.options.set_uid()
        if setuid_msg:
            critical_messages.append(setuid_msg)
        if first:
            rlimit_messages = self.options.set_rlimits()
            info_messages.extend(rlimit_messages)

        # this sets the options.logger object
        # delay logger instantiation until after setuid
        self.options.make_logger(critical_messages, info_messages)

        if not self.options.nocleanup:
            # clean up old automatic logs
            self.options.clear_autochildlogdir()

        # delay "automatic" child log creation until after setuid because
        # we want to use mkstemp, which needs to create the file eagerly
        self.options.create_autochildlogs()

        self.run(test)

    def run(self, test=False):
        self.processes = {}
        for program in self.options.programs:
            name = program.name
            self.processes[name] = self.options.make_process(program)
        try:
            self.options.write_pidfile()
            self.options.openhttpserver(self)
            self.options.setsignals()
            if not self.options.nodaemon:
                self.options.daemonize()
            self.runforever(test)
        finally:
            self.options.cleanup()

    def runforever(self, test=False):
        timeout = .5

        socket_map = self.options.get_socket_map()

        while 1:
            if self.mood > 0:
                self.start_necessary()

            self.handle_procs_with_waitstatus()

            r, w, x = [], [], []

            process_map = {}

            # process output fds
            for proc in self.processes.values():
                proc.log_writebuffer()
                drains = proc.fd_drains()
                for fd, drain in drains:
                    r.append(fd)
                    process_map[fd] = drain

            # medusa i/o fds
            for fd, dispatcher in socket_map.items():
                if dispatcher.readable():
                    r.append(fd)
                if dispatcher.writable():
                    w.append(fd)

            if self.mood < 1:
                if not self.stopping:
                    self.stop_all()
                    self.stopping = True

                # if there are no delayed processes (we're done killing
                # everything), it's OK to stop or reload
                if not self.handle_procs_with_delay():
                    break

            try:
                r, w, x = select.select(r, w, x, timeout)
            except select.error, err:
                if err[0] == errno.EINTR:
                    self.options.logger.log(self.options.TRACE,
                                            'EINTR encountered in select')
                else:
                    raise
                r = w = x = []

            self.handle_procs_with_waitstatus()

            for fd in r:
                if process_map.has_key(fd):
                    drain = process_map[fd]
                    # drain the file descriptor
                    drain(fd)

                if socket_map.has_key(fd):
                    try:
                        socket_map[fd].handle_read_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        socket_map[fd].handle_error()

            for fd in w:
                if socket_map.has_key(fd):
                    try:
                        socket_map[fd].handle_write_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        socket_map[fd].handle_error()

            self.handle_procs_with_delay()
            self.reap()

            if self.options.signal:
                # clear and handle the last signal
                sig, self.options.signal = self.options.signal, None
                if sig in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT):
                    self.options.logger.critical(
                        'received %s indicating exit request' % signame(sig))
                    self.mood = -1
                elif sig == signal.SIGHUP:
                    self.options.logger.critical(
                        'received %s indicating restart request' % signame(sig))
                    self.mood = 0
                elif sig == signal.SIGUSR2:
                    self.options.logger.info(
                        'received %s indicating log reopen request' %
                        signame(sig))
                    self.logreopen()
                else:
                    self.options.logger.debug('received %s' % signame(sig))

            if test:
                break

    def get_state(self):
        if self.mood <= 0:
            return SupervisorStates.SHUTDOWN
        return SupervisorStates.ACTIVE

    def start_necessary(self):
        processes = self.processes.values()
        processes.sort() # asc by priority

        for p in processes:
            state = p.get_state()
            if state not in (ProcessStates.STOPPED, ProcessStates.ERROR,
                             ProcessStates.RUNNING, ProcessStates.STOPPING,
                             ProcessStates.STARTING):
                if state == ProcessStates.NOTSTARTED:
                    case = p.config.autostart
                else:
                    case = p.config.autorestart

                if case:
                    p.spawn()
            
    def stop_all(self):
        processes = self.processes.values()
        processes.sort()
        processes.reverse() # stop in desc priority order
        
        for proc in processes:
            if proc.pid:
                proc.stop()

    def handle_procs_with_waitstatus(self):
        processes = self.processes.values()
        for proc in processes:
            if proc.waitstatus:
                proc.reportstatus()

    def handle_procs_with_delay(self):
        delayprocs = []
        now = time.time()
        timeout = self.options.backofflimit
        processes = self.processes.values()
        delayprocs = [ proc for proc in processes if proc.delay ]
        for proc in delayprocs:
            time_left = proc.delay - now
            time_left = max(0, min(timeout, time_left))
            if time_left <= 0:
                proc.delay = 0
                if proc.killing and proc.pid:
                    self.options.logger.info(
                        'killing %r (%s) with SIGKILL' % (proc.config.name,
                                                          proc.pid))
                    proc.do_backoff()
                    proc.kill(signal.SIGKILL)
        return delayprocs

    def reap(self, once=False):
        pid, sts = self.options.waitpid()
        if pid:
            name = '<unknown>'
            process = self.options.pidhistory.get(pid)
            if process is not None:
                name = process.config.name
                process.drain()
                process.waitstatus = pid, sts
                process.killing = 0
                process.laststop = time.time()
            self.options.logger.debug('reaped %s (pid %s)' % (name, pid))
            if not once:
                self.reap() # keep reaping until no more kids to reap

    def logreopen(self):
        self.options.logger.info('supervisord logreopen')
        for handler in self.options.logger.handlers:
            if hasattr(handler, 'reopen'):
                handler.reopen()

        for process in self.processes.values():
            process.reopenlogs()
        
def _readfd(fd):
    try:
        data = os.read(fd, 2 << 16) # 128K
    except OSError, why:
        if why[0] not in (errno.EWOULDBLOCK, errno.EBADF):
            raise
        data = ''
    return data

def get_path():
    """Return a list corresponding to $PATH, or a default."""
    path = ["/bin", "/usr/bin", "/usr/local/bin"]
    if os.environ.has_key("PATH"):
        p = os.environ["PATH"]
        if p:
            path = p.split(os.pathsep)
    return path

# Main program
def main(test=False):
    assert os.name == "posix", "This code makes Unix-specific assumptions"
    first = True
    while 1:
        # if we hup, restart by making a new Supervisor()
        # the test argument just makes it possible to unit test this code
        options = ServerOptions()
        d = Supervisor(options)
        d.main(None, test, first)
        first = False
        if test:
            return d
        if d.mood < 0:
            sys.exit(0)
        for proc in d.processes.values():
            proc.removelogs()
        if d.options.httpserver:
            d.options.httpserver.close()
            

if __name__ == "__main__":
    main()
