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

import os
import sys
import time
import errno
import socket
import select
import signal
import pwd
import grp
import asyncore
import traceback
import StringIO
import resource
import stat
import re
import tempfile

from fcntl import fcntl
from fcntl import F_SETFL, F_GETFL

from options import ServerOptions

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
    readbuffer = ''  # buffer of characters written to child's stdout
    finaloutput = '' # buffer of characters read from child's stdout right
                     # before process reapage
    reportstatusmsg = None # message attached to instance during reportstatus()
    
    def __init__(self, options, config):
        """Constructor.

        Arguments are a ServerOptions instance and a ProcessConfig instance.
        """
        self.options = options
        self.config = config
        self.pidhistory = []
        self.readbuffer = ""
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

    def get_execv_args(self):
        """Internal: turn a program name into a file name, using $PATH,
        make sure it exists """
        commandargs = self.config.command.split()

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
        self.options.logger.critical(msg)
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
            self.options.logger.info('spawned process %r with pid %s' % (
                self.config.name, pid))
            self.spawnerr = None
            self.do_backoff()
            return pid
        
        else:
            # Child
            try:
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
        self.administrative_stop = 1
        # backoff needs to come before kill on MacOS, as there's
        # an apparent a race condition if it comes after
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
            self.options.logger.info('killing %s (%s)' % (self.config.name,
                                                          self.pid))
            self.killing = 1
            os.kill(self.pid, sig)
            self.addpidtohistory(self.pid)
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

    def addpidtohistory(self, pid):
        self.pidhistory.append(pid)
        if len(self.pidhistory) > 10: # max pid history to keep around is 10
            self.pidhistory.pop(0)

    def isoneofmypids(self, pid):
        if pid == self.pid:
            return True
        return pid in self.pidhistory

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
                        "%s: restarting too frequently; quit" % (
                        self.config.name))
                    # stop trying
                    self.system_stop = 1
                    self.backoff = 0
                    self.delay = 0
                    return
            self.options.logger.info(
                "%s: sleep %s to avoid rapid restarts" % (self.config.name,
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
        msg = "pid %d: " % pid + msg
        if not self.isoneofmypids(pid):
            msg = "unknown " + msg
            self.options.logger.warn(msg)
        else:
            if self.killing:
                self.killing = 0
                self.delay = 0
            elif not es in self.config.exitcodes:
                self.governor()

            if self.pid:
                self.addpidtohistory(self.pid)
            self.pid = 0
            
            self.stdoutfd = self.stderrfd  = self.stdinfd = None
            self.stdout = self.stderr = self.stdin = None

            if es in self.config.exitcodes and not self.killing:
                msg = msg + "; OK"
            self.options.logger.info(msg)
            self.exitstatus = es
        self.reportstatusmsg = msg

    def do_backoff(self):
        self.delay = time.time() + self.options.backofflimit

    def set_uid(self):
        if self.config.uid is None:
            return
        msg = dropPrivileges(self.config.uid)
        return msg

    def __cmp__(self, other):
        # sort by priority
        return cmp(self.config.priority, other.config.priority)

    def log(self, data):
        if data:
            if self.childlog:
                self.childlog.info(data)

    def trace(self, data):
        # 'trace' level logging to main log file
        msg = '%s output:\n%s' % (self.config.name, data)
        self.options.logger.log(5, msg)

    def log_stdout(self, data):
        if data:
            self.log(data)
            self.trace(data)

    log_stderr = log_stdout

    def get_state(self):
        if self.killing:
            return ProcessStates.STOPPING
        elif self.system_stop:
            return ProcessStates.ERROR
        if self.administrative_stop:
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
            elif not self.pidhistory:
                return ProcessStates.NOTSTARTED
            else:
                return ProcessStates.UNKNOWN

class Supervisor:

    mood = 1 # 1: up, 0: restarting, -1: suicidal
    stopping = False # set after we detect that we are handling a stop request

    def main(self, args=None, test=False, first=False):
        self.options = ServerOptions()
        self.options.realize(args)
        self.cleanup_fds()
        held_messages = []
        setuid_msg = self.set_uid()
        if setuid_msg:
            held_messages.append(setuid_msg)
        if first:
            rlimit_messages = self.set_rlimits()
            held_messages.extend(rlimit_messages)

        # this sets the options.logger object
        # delay logger instantiation until after setuid
        self.options.make_logger(held_messages)

        if not self.options.nocleanup:
            # clean up old automatic logs
            self.options.clear_childlogdir()

        # delay "automatic" child log creation until after setuid because
        # we want to use mkstemp, which needs to create the file eagerly
        for program in self.options.programs:
            if program.logfile is self.options.AUTOMATIC:
                # temporary logfile which is erased at start time
                prefix='%s---%s-' % (program.name, self.options.identifier)
                fd, logfile = tempfile.mkstemp(
                    suffix='.log',
                    prefix=prefix,
                    dir=self.options.childlogdir)
                os.close(fd)
                program.logfile = logfile

        self.run(test)

    def get_state(self):
        if self.mood <= 0:
            return SupervisorStates.SHUTDOWN
        return SupervisorStates.ACTIVE

    def start_necessary(self):
        processes = self.processes.values()
        processes.sort() # asc by priority

        for p in processes:
            if not p.pid and not p.delay:
                if not p.pidhistory:
                    case = p.config.autostart
                else:
                    case = p.config.autorestart
                if case:
                    if not p.administrative_stop and not p.system_stop:
                        self.options.logger.info('(Re)starting %s' %
                                                 p.config.name)
                        p.spawn()

    def handle_procs_with_waitstatus(self):
        processes = self.processes.values()
        for proc in processes:
            if proc.waitstatus:
                proc.reportstatus()

    def stop_all(self):
        processes = self.processes.values()
        processes.sort()
        processes.reverse() # stop in desc priority order
        
        for proc in processes:
            if proc.pid:
                proc.stop()

    def handle_procs_with_delay(self):
        delayprocs = []
        now = time.time()
        timeout = self.options.backofflimit
        for name in self.processes.keys():
            proc = self.processes[name]
            if proc.delay:
                delayprocs.append(proc)
                timeout = max(0, min(timeout, proc.delay - now))
                if timeout <= 0:
                    proc.delay = 0
                    if proc.killing and proc.pid:
                        self.options.logger.info(
                            'killing %r (%s) with SIGKILL' % (name, proc.pid))
                        proc.do_backoff()
                        proc.kill(signal.SIGKILL)
        return delayprocs

    def reap(self):
        # need pthread_sigmask here to avoid concurrent sigchild, but
        # Python doesn't offer it as it's not standard across UNIX versions.
        # there is still a race condition here; we can get a sigchild while
        # we're sitting in the waitpid call.
        try:
            pid, sts = os.waitpid(-1, os.WNOHANG)
        except os.error, why:
            err = why[0]
            if err not in (errno.ECHILD, errno.EINTR):
                self.options.logger.info(
                    'waitpid error; a process may not be cleaned up properly')
            if err == errno.EINTR:
                self.options.logger.debug('EINTR during reap')
            pid, sts = None, None
        if pid:
            self.options.logger.info('child with pid %s was reaped' % pid)
            self.setwaitstatus(pid, sts)
            self.reap() # keep reaping until no more kids to reap
        return pid, sts

    def setwaitstatus(self, pid, sts):
        self.options.logger.debug('setwaitstatus called')
        for name in self.processes.keys():
            proc = self.processes[name]
            if proc.isoneofmypids(pid):
                self.options.logger.debug('set wait status on %s' % name)
                proc.finaloutput = _readfd(proc.stdoutfd)
                proc.waitstatus = pid, sts
                proc.killing = 0
                proc.laststop = time.time()

    def cleanup_fds(self):
        # try to close any unused file descriptors to prevent leakage.
        # we start at the "highest" descriptor in the asyncore socket map
        # because this might be called remotely and we don't want to close
        # the internet channel during this call.
        asyncore_fds = asyncore.socket_map.keys()
        start = 5
        if asyncore_fds:
            start = max(asyncore_fds) + 1
        for x in range(start, self.options.minfds):
            try:
                os.close(x)
            except:
                pass

    def set_uid(self):
        if self.options.uid is None:
            if os.getuid() == 0:
                self.options.usage('supervisord may not be run as the root '
                                   'user without a "user" setting in the '
                                   'configuration file')
            return
        return dropPrivileges(self.options.uid)

    def set_rlimits(self):
        limits = []
        if hasattr(resource, 'RLIMIT_NOFILE'):
            limits.append(
                {
                'msg':('The minimum number of file descriptors required '
                       'to run this process is %(min)s as per the "minfds" '
                       'command-line argument or config file setting. '
                       'The current environment will only allow you '
                       'to open %(hard)s file descriptors.  Either raise '
                       'the number of usable file descriptors in your '
                       'environment (see README.txt) or lower the '
                       'minfds setting in the config file to allow '
                       'the process to start.'),
                'min':self.options.minfds,
                'resource':resource.RLIMIT_NOFILE,
                'name':'RLIMIT_NOFILE',
                })
        if hasattr(resource, 'RLIMIT_NPROC'):
            limits.append(
                {
                'msg':('The minimum number of available processes required '
                       'to run this program is %(min)s as per the "minprocs" '
                       'command-line argument or config file setting. '
                       'The current environment will only allow you '
                       'to open %(hard)s processes.  Either raise '
                       'the number of usable processes in your '
                       'environment (see README.txt) or lower the '
                       'minprocs setting in the config file to allow '
                       'the program to start.'),
                'min':self.options.minprocs,
                'resource':resource.RLIMIT_NPROC,
                'name':'RLIMIT_NPROC',
                })

        msgs = []
            
        for limit in limits:

            min = limit['min']
            res = limit['resource']
            msg = limit['msg']
            name = limit['name']

            soft, hard = resource.getrlimit(res)
            
            if (soft < min) and (soft != -1): # -1 means unlimited 
                if (hard < min) and (hard != -1):
                    self.options.usage(msg % locals())

                try:
                    resource.setrlimit(res, (min, hard))
                    msgs.append('Increased %(name)s limit to %(min)s' %
                                locals())
                except (resource.error, ValueError):
                    self.options.usage(msg % locals())
        return msgs

    def run(self, test=False):
        self.processes = {}
        for program in self.options.programs:
            name = program.name
            self.processes[name] = Subprocess(self.options, program)
        try:
            self.openhttpserver()
            self.setsignals()
            if not self.options.nodaemon:
                self.daemonize()
            pid = os.getpid()
            f = open(self.options.pidfile, 'w')
            f.write('%s\n' % pid)
            f.close()
            self.options.logger.info('supervisord started with pid %s' % pid)
            self.runforever(test)
        finally:
            try:
                if self.options.http_port is not None:
                    if self.options.http_port.family == socket.AF_UNIX:
                        os.unlink(self.options.http_port.address)
            except os.error:
                pass
            try:
                os.unlink(self.options.pidfile)
            except os.error:
                pass

    def openhttpserver(self):
        from http import makeHTTPServer
        try:
            self.httpserver = makeHTTPServer(self)
        except socket.error, why:
            if why[0] == errno.EADDRINUSE:
                port = str(self.options.http_port.address)
                self.options.usage('Another program is already listening on '
                                   'the port that our HTTP server is '
                                   'configured to use (%s).  Shut this program '
                                   'down first before starting supervisord. ' %
                                   port)
        except ValueError, why:
            self.options.usage(why[0])

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.sigexit)
        signal.signal(signal.SIGHUP, self.sighup)
        signal.signal(signal.SIGINT, self.sigexit)
        signal.signal(signal.SIGCHLD, self.sigchild)
        signal.signal(signal.SIGUSR2, self.sigreopenlog)

    def sigexit(self, sig, frame):
        self.options.logger.critical("supervisord stopping via %s" %
                                     signame(sig))
        self.mood = -1 # exiting

    def sighup(self, sig, frame):
        self.options.logger.critical("supervisord reload via %s" %
                                     signame(sig))
        self.mood = 0 # restarting

    def sigreopenlog(self, sig, frame):
        self.options.logger.info('supervisord log reopen via %s' %
                                 signame(sig))
        for handler in self.options.logger.handlers:
            if hasattr(handler, 'reopen'):
                handler.reopen()

    def sigchild(self, sig, frame):
        # do nothing here, we reap our children synchronously
        self.options.logger.info('received sigchild')

    def daemonize(self):

        # To daemonize, we need to become the leader of our own session
        # (process) group.  If we do not, signals sent to our
        # parent process will also be sent to us.   This might be bad because
        # signals such as SIGINT can be sent to our parent process during
        # normal (uninteresting) operations such as when we press Ctrl-C in the
        # parent terminal window to escape from a logtail command.
        # To disassociate ourselves from our parent's session group we use
        # os.setsid.  It means "set session id", which has the effect of
        # disassociating a process from is current session and process group
        # and setting itself up as a new session leader.
        #
        # Unfortunately we cannot call setsid if we're already a session group
        # leader, so we use "fork" to make a copy of ourselves that is
        # guaranteed to not be a session group leader.
        #
        # We also change directories, set stderr and stdout to null, and
        # change our umask.
        #
        # This explanation was (gratefully) garnered from
        # http://www.hawklord.uklinux.net/system/daemons/d3.htm

        pid = os.fork()
        if pid != 0:
            # Parent
            self.options.logger.debug("supervisord forked; parent exiting")
            os._exit(0)
        # Child
        self.options.logger.info("daemonizing the process")
        if self.options.directory:
            try:
                os.chdir(self.options.directory)
            except os.error, err:
                self.options.logger.warn("can't chdir into %r: %s"
                                         % (self.options.directory, err))
            else:
                self.options.logger.info("set current directory: %r"
                                         % self.options.directory)
        os.close(0)
        sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        sys.stderr = sys.__stderr__ = open("/dev/null", "w")
        os.setsid()
        os.umask(self.options.umask)
        # XXX Stevens, in his Advanced Unix book, section 13.3 (page
        # 417) recommends calling umask(0) and closing unused
        # file descriptors.  In his Network Programming book, he
        # additionally recommends ignoring SIGHUP and forking again
        # after the setsid() call, for obscure SVR4 reasons.

    def runforever(self, test=False):
        timeout = .5

        socket_map = asyncore.socket_map

        while 1:
            if self.mood > 0:
                self.start_necessary()

            self.handle_procs_with_waitstatus()

            r, w, x = [], [], []

            all = self.processes.values()

            stdoutfds = {}
            stderrfds = {}
            for proc in all:
                if proc.stdoutfd:
                    r.append(proc.stdoutfd)
                    stdoutfds[proc.stdoutfd] = proc
                if proc.stderrfd:
                    r.append(proc.stderrfd)
                    stderrfds[proc.stderrfd] = proc
                if proc.finaloutput:
                    proc.log_stdout(proc.finaloutput)
                    proc.finaloutput = ''

            if self.mood < 1:
                if not self.stopping:
                    self.stop_all()
                    self.stopping = True
                # reget the delay list after attempting to stop
                delayprocs = self.handle_procs_with_delay()
                if not delayprocs:
                    break # reload or stop

            for fd, dispatcher in socket_map.items():
                if dispatcher.readable():
                    r.append(fd)
                if dispatcher.writable():
                    w.append(fd)

            try:
                r, w, x = select.select(r, w, x, timeout)
            except select.error, err:
                if err[0] == errno.EINTR:
                    #trace
                    self.options.logger.log(5,'EINTR encountered in select')
                else:
                    raise
                r = w = x = []

            self.handle_procs_with_waitstatus()

            for fd in r:
                stdoutproc = stdoutfds.get(fd)
                stderrproc = stderrfds.get(fd)

                if stdoutproc:
                    data = _readfd(fd)
                    stdoutproc.log_stdout(data)
                if stderrproc:
                    data = _readfd(fd)
                    if stderrproc.config.log_stderr:
                        stderrproc.log_stderr(data)

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

            if test:
                break

def _readfd(fd):
    try:
        data = os.read(fd, 2 << 16) # 128K
    except OSError, why:
        if why[0] not in (errno.EWOULDBLOCK, errno.EBADF):
            raise
        data = ''
    return data

# Helpers for dealing with signals and exit status

def decode_wait_status(sts):
    """Decode the status returned by wait() or waitpid().

    Return a tuple (exitstatus, message) where exitstatus is the exit
    status, or -1 if the process was killed by a signal; and message
    is a message telling what happened.  It is the caller's
    responsibility to display the message.
    """
    if os.WIFEXITED(sts):
        es = os.WEXITSTATUS(sts) & 0xffff
        msg = "exit status %s" % es
        return es, msg
    elif os.WIFSIGNALED(sts):
        sig = os.WTERMSIG(sts)
        msg = "terminated by %s" % signame(sig)
        if hasattr(os, "WCOREDUMP"):
            iscore = os.WCOREDUMP(sts)
        else:
            iscore = sts & 0x80
        if iscore:
            msg += " (core dumped)"
        return -1, msg
    else:
        msg = "unknown termination cause 0x%04x" % sts
        return -1, msg

_signames = None

def signame(sig):
    """Return a symbolic name for a signal.

    Return "signal NNN" if there is no corresponding SIG name in the
    signal module.
    """

    if _signames is None:
        _init_signames()
    return _signames.get(sig) or "signal %d" % sig

def _init_signames():
    global _signames
    d = {}
    for k, v in signal.__dict__.items():
        k_startswith = getattr(k, "startswith", None)
        if k_startswith is None:
            continue
        if k_startswith("SIG") and not k_startswith("SIG_"):
            d[v] = k
    _signames = d

def get_path():
    """Return a list corresponding to $PATH, or a default."""
    path = ["/bin", "/usr/bin", "/usr/local/bin"]
    if os.environ.has_key("PATH"):
        p = os.environ["PATH"]
        if p:
            path = p.split(os.pathsep)
    return path

def dropPrivileges(user):
    # Drop root privileges if we have them
    if user is None:
        return "No used specified to setuid to!"
    if os.getuid() != 0:
        return "Can't drop privilege as nonroot user"
    try:
        uid = int(user)
    except ValueError:
        try:
            pwrec = pwd.getpwnam(user)
        except KeyError:
            return "Can't find username %r" % user
        uid = pwrec[2]
    else:
        try:
            pwrec = pwd.getpwuid(uid)
        except KeyError:
            return "Can't find uid %r" % uid
    if hasattr(os, 'setgroups'):
        user = pwrec[0]
        groups = [grprec[2] for grprec in grp.getgrall() if user in grprec[3]]
        try:
            os.setgroups(groups)
        except OSError:
            return 'Could not set groups of effective user'
    gid = pwrec[3]
    try:
        os.setgid(gid)
    except OSError:
        return 'Could not set group id of effective user'
    os.setuid(uid)

# Main program
def main(test=False):
    assert os.name == "posix", "This code makes Unix-specific assumptions"
    first = True
    while 1:
        # if we hup, restart by making a new Supervisor()
        # the test argument just makes it possible to unit test this code
        d = Supervisor()
        d.main(None, test, first)
        first = False
        if test:
            return d
        if d.mood < 0:
            sys.exit(0)
        for proc in d.processes.values():
            proc.removelogs()
        if d.httpserver:
            d.httpserver.close()
            

if __name__ == "__main__":
    main()
