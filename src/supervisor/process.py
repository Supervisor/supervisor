##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

import asyncore
import os
import time
import errno
import shlex
import logging
import StringIO
import traceback
import signal

from supervisor.options import decode_wait_status
from supervisor.options import signame
from supervisor.options import ProcessException

from supervisor.events import ProcessCommunicationEvent
from supervisor.events import notify

class ProcessStates:
    STOPPED = 0
    STARTING = 10
    RUNNING = 20
    BACKOFF = 30
    STOPPING = 40
    EXITED = 100
    FATAL = 200
    UNKNOWN = 1000

def getProcessStateDescription(code):
    for statename in ProcessStates.__dict__:
        if getattr(ProcessStates, statename) == code:
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
    backoff = 0 # backoff counter (to startretries)
    pipes = None # mapping of pipe descriptor purpose to file descriptor
    stdout_logger = None # Logger instance representing stdout
    stderr_logger = None # Logger instance representing stderr
    stdin_buffer = '' # buffer of characters to be sent to child's stdin
    exitstatus = None # status attached to dead process by finsh()
    spawnerr = None # error message attached by spawn() if any
    
    def __init__(self, config):
        """Constructor.

        Argument is a ProcessConfig instance.
        """
        self.config = config
        self.pipes = {}
        self.loggers = {'stdout':None, 'stderr':None}
        if config.stdout_logfile:
            self.loggers['stdout'] = Logger(
                options = config.options,
                procname = config.name,
                channel = 'stdout',
                logfile = config.stdout_logfile,
                logfile_backups = config.stdout_logfile_backups,
                logfile_maxbytes = config.stdout_logfile_maxbytes,
                capturefile = config.stdout_capturefile)
        if config.stderr_logfile and not config.redirect_stderr:
            self.loggers['stderr'] = Logger(
                options = config.options,
                procname = config.name,
                channel = 'stderr',
                logfile = config.stderr_logfile,
                logfile_backups = config.stderr_logfile_backups,
                logfile_maxbytes = config.stderr_logfile_maxbytes,
                capturefile = config.stderr_capturefile)

    def removelogs(self):
        for logger in (self.loggers['stdout'], self.loggers['stderr']):
            if logger is not None:
                logger.removelogs()

    def reopenlogs(self):
        for logger in (self.loggers['stdout'], self.loggers['stderr']):
            if logger is not None:
                logger.reopenlogs()

    def log_output(self):
        for logger in (self.loggers['stdout'], self.loggers['stderr']):
            if logger is not None:
                logger.log_output()

    def _drain_output_pipe(self, name):
        fd = self.pipes[name]
        if fd is None:
            return
        output = self.config.options.readfd(fd)
        if self.loggers[name] is not None:
            self.loggers[name].output_buffer += output

    def drain_stdout(self):
        return self._drain_output_pipe('stdout')

    def drain_stderr(self):
        return self._drain_output_pipe('stderr')

    def get_output_drains(self):
        drains = []
        stdout_pipe = self.pipes.get('stdout', None)
        stderr_pipe = self.pipes.get('stderr', None)
        if stdout_pipe is not None:
            drains.append((stdout_pipe, self.drain_stdout))
        if stderr_pipe is not None:
            drains.append((stderr_pipe, self.drain_stderr))
        return drains

    def get_input_drains(self):
        return [(self.pipes['stdin'], self.drain_stdin)]

    def write(self, chars):
        if not self.pid or self.killing:
            raise IOError(errno.EPIPE, "Process already closed")
        self.stdin_buffer = self.stdin_buffer + chars

    def drain_stdin(self):
        if self.stdin_buffer:
            to_send = self.stdin_buffer[:2<<16]
            try:
                sent = self.config.options.write(self.pipes['stdin'], to_send)
                self.stdin_buffer = self.stdin_buffer[sent:]
            except OSError, why:
                if why[0] == errno.EPIPE:
                    msg = 'failed write to process %r stdin' % self.config.name
                    self.stdin_buffer = ''
                    self.config.options.logger.info(msg)
                else:
                    raise

    def drain(self):
        self.drain_stdout()
        self.drain_stderr()
        self.drain_stdin()

    def get_execv_args(self):
        """Internal: turn a program name into a file name, using $PATH,
        make sure it exists / is executable, raising a ProcessException
        if not """
        commandargs = shlex.split(self.config.command)

        program = commandargs[0]

        if "/" in program:
            filename = program
            try:
                st = self.config.options.stat(filename)
            except OSError:
                st = None
            
        else:
            path = self.config.options.get_path()
            filename = None
            st = None
            for dir in path:
                filename = os.path.join(dir, program)
                try:
                    st = self.config.options.stat(filename)
                except OSError:
                    filename = None
                else:
                    break

        # check_execv_args will raise a ProcessException if the execv
        # args are bogus, we break it out into a separate options
        # method call here only to service unit tests
        self.config.options.check_execv_args(filename, commandargs, st)

        return filename, commandargs

    def record_spawnerr(self, msg):
        now = time.time()
        self.spawnerr = msg
        self.config.options.logger.critical("spawnerr: %s" % msg)
        self.backoff = self.backoff + 1
        self.delay = now + self.backoff

    def spawn(self):
        """Start the subprocess.  It must not be running already.

        Return the process id.  If the fork() call fails, return None.
        """
        pname = self.config.name
        options = self.config.options

        if self.pid:
            msg = 'process %r already running' % pname
            options.logger.critical(msg)
            return

        self.killing = 0
        self.spawnerr = None
        self.exitstatus = None
        self.system_stop = 0
        self.administrative_stop = 0
        
        self.laststart = time.time()

        try:
            filename, argv = self.get_execv_args()
        except ProcessException, what:
            self.record_spawnerr(what.args[0])
            return

        try:
            use_stderr = not self.config.redirect_stderr
            self.pipes = options.make_pipes(use_stderr)
        except OSError, why:
            code = why[0]
            if code == errno.EMFILE:
                # too many file descriptors open
                msg = 'too many open files to spawn %r' % pname
            else:
                msg = 'unknown error: %s' % errno.errorcode.get(code, code)
            self.record_spawnerr(msg)
            return

        try:
            pid = options.fork()
        except OSError, why:
            code = why[0]
            if code == errno.EAGAIN:
                # process table full
                msg  = 'Too many processes in process table to spawn %r' % pname
            else:
                msg = 'unknown error: %s' % errno.errorcode.get(code, code)

            self.record_spawnerr(msg)
            options.close_parent_pipes(self.pipes)
            options.close_child_pipes(self.pipes)
            return

        if pid != 0:
            # Parent
            self.pid = pid
            options.close_child_pipes(self.pipes)
            options.logger.info('spawned: %r with pid %s' % (pname, pid))
            self.spawnerr = None
            # we use self.delay here as a mechanism to indicate that we're in
            # the STARTING state.
            self.delay = time.time() + self.config.startsecs
            options.pidhistory[pid] = self
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
                options.setpgrp()
                options.dup2(self.pipes['child_stdin'], 0)
                options.dup2(self.pipes['child_stdout'], 1)
                if self.config.redirect_stderr:
                    options.dup2(self.pipes['child_stdout'], 2)
                else:
                    options.dup2(self.pipes['child_stderr'], 2)
                for i in range(3, options.minfds):
                    options.close_fd(i)
                # sending to fd 1 will put this output in the log(s)
                msg = self.set_uid()
                if msg:
                    uid = self.config.uid
                    s = 'supervisor: error trying to setuid to %s ' % uid
                    options.write(1, s)
                    options.write(1, "(%s)\n" % msg)
                try:
                    env = os.environ.copy()
                    if self.config.environment is not None:
                        env.update(self.config.environment)
                    options.execve(filename, argv, env)
                except OSError, why:
                    code = why[0]
                    options.write(1, "couldn't exec %s: %s\n" % (
                        argv[0], errno.errorcode.get(code, code)))
                except:
                    (file, fun, line), t,v,tbinfo = asyncore.compact_traceback()
                    error = '%s, %s: file: %s line: %s' % (t, v, file, line)
                    options.write(1, "couldn't exec %s: %s\n" % (filename,
                                                                      error))
            finally:
                options._exit(127)

    def stop(self):
        """ Administrative stop """
        self.administrative_stop = 1
        return self.kill(self.config.stopsignal)

    def kill(self, sig):
        """Send a signal to the subprocess.  This may or may not kill it.

        Return None if the signal was sent, or an error message string
        if an error occurred or if the subprocess is not running.
        """
        now = time.time()
        options = self.config.options
        if not self.pid:
            msg = ("attempted to kill %s with sig %s but it wasn't running" %
                   (self.config.name, signame(sig)))
            options.logger.debug(msg)
            return msg
        try:
            options.logger.debug('killing %s (pid %s) with signal %s'
                                 % (self.config.name,
                                    self.pid,
                                    signame(sig)))
            # RUNNING -> STOPPING
            self.killing = 1
            self.delay = now + self.config.stopwaitsecs
            options.kill(self.pid, sig)
        except:
            io = StringIO.StringIO()
            traceback.print_exc(file=io)
            tb = io.getvalue()
            msg = 'unknown problem killing %s (%s):%s' % (self.config.name,
                                                          self.pid, tb)
            options.logger.critical(msg)
            self.pid = 0
            self.killing = 0
            self.delay = 0
            return msg
            
        return None

    def finish(self, pid, sts):
        """ The process was reaped and we need to report and manage its state
        """
        self.drain()
        self.log_output()

        es, msg = decode_wait_status(sts)

        now = time.time()
        self.laststop = now
        processname = self.config.name

        tooquickly = now - self.laststart < self.config.startsecs
        badexit = not es in self.config.exitcodes
        expected = not (tooquickly or badexit)

        if self.killing:
            # likely the result of a stop request
            # implies STOPPING -> STOPPED
            self.killing = 0
            self.delay = 0
            self.exitstatus = es
            msg = "stopped: %s (%s)" % (processname, msg)
        elif expected:
            # this finish was not the result of a stop request, but
            # was otherwise expected
            # implies RUNNING -> EXITED
            self.delay = 0
            self.backoff = 0
            self.exitstatus = es
            msg = "exited: %s (%s)" % (processname, msg + "; expected")
        else:
            # the program did not stay up long enough or exited with
            # an unexpected exit code
            self.exitstatus = None
            self.backoff = self.backoff + 1
            self.delay = now + self.backoff
            if tooquickly:
                self.spawnerr = (
                    'Exited too quickly (process log may have details)')
            elif badexit:
                self.spawnerr = 'Bad exit code %s' % es
            msg = "exited: %s (%s)" % (processname, msg + "; not expected")

        self.config.options.logger.info(msg)

        self.pid = 0
        self.config.options.close_parent_pipes(self.pipes)
        self.pipes = {}

    def set_uid(self):
        if self.config.uid is None:
            return
        msg = self.config.options.dropPrivileges(self.config.uid)
        return msg

    def __cmp__(self, other):
        # sort by priority
        return cmp(self.config.priority, other.config.priority)

    def __repr__(self):
        return '<Subprocess at %s with name %s in state %s>' % (
            id(self),
            self.config.name,
            getProcessStateDescription(self.get_state()))

    def get_state(self):
        if not self.laststart:
            return ProcessStates.STOPPED
        elif self.killing:
            return ProcessStates.STOPPING
        elif self.system_stop:
            return ProcessStates.FATAL
        elif self.exitstatus is not None:
            if self.administrative_stop:
                return ProcessStates.STOPPED
            else:
                return ProcessStates.EXITED
        elif self.delay:
            if self.pid:
                return ProcessStates.STARTING
            else:
                return ProcessStates.BACKOFF
        elif self.pid:
            return ProcessStates.RUNNING
        return ProcessStates.UNKNOWN

    def select(self):
        r, w, x = [], [], []
        callbacks = {}

        # self.log_output is required, we'd never log anything if it wasnt here
        self.log_output() 

        # process output fds
        for fd, drain in self.get_output_drains():
            r.append(fd)
            callbacks[fd] = drain

        # process input fds
        if self.stdin_buffer:
            for fd, drain in self.get_input_drains():
                w.append(fd)
                callbacks[fd] = drain

        return callbacks, r, w, x

class ProcessGroup:
    def __init__(self, config):
        self.config = config
        self.processes = {}
        for pconfig in self.config.process_configs:
            options = self.config.options
            self.processes[pconfig.name] = options.make_process(pconfig)
        

    def __cmp__(self, other):
        return cmp(self.config.priority, other.config.priority)

    def __repr__(self):
        return '<%s instance at %s named %s>' % (self.__class__, id(self),
                                                 self.config.name)

    def removelogs(self):
        for process in self.processes.values():
            process.removelogs()

    def reopenlogs(self):
        for process in self.processes.values():
            process.reopenlogs()

    def select(self):
        r, w, x = [], [], []
        callbacks = {}

        for proc in self.processes.values():
            proc_callbacks, proc_r, proc_w, proc_x = proc.select()
            callbacks.update(proc_callbacks)
            r.extend(proc_r)
            w.extend(proc_w)
            x.extend(proc_x)

        return callbacks, r, w, x

    def start_necessary(self):
        processes = self.processes.values()
        processes.sort() # asc by priority
        now = time.time()

        for p in processes:
            state = p.get_state()
            if state == ProcessStates.STOPPED and not p.laststart:
                if p.config.autostart:
                    # STOPPED -> STARTING
                    p.spawn()
            elif state == ProcessStates.EXITED:
                if p.config.autorestart:
                    # EXITED -> STARTING
                    p.spawn()
            elif state == ProcessStates.BACKOFF:
                if now > p.delay:
                    # BACKOFF -> STARTING
                    p.spawn()

    def stop_all(self):
        processes = self.processes.values()
        processes.sort()
        processes.reverse() # stop in desc priority order

        for proc in processes:
            state = proc.get_state()
            if state == ProcessStates.RUNNING:
                # RUNNING -> STOPPING
                proc.stop()
            elif state == ProcessStates.STARTING:
                # STARTING -> STOPPING (unceremoniously subvert the RUNNING
                # state)
                proc.stop()
            elif state == ProcessStates.BACKOFF:
                # BACKOFF -> FATAL
                proc.delay = 0
                proc.backoff = 0
                proc.system_stop = 1

    def transition(self):
        self.kill_undead()
        now = time.time()

        for proc in self.processes.values():
            state = proc.get_state()

            # we need to transition processes between BACKOFF ->
            # FATAL and STARTING -> RUNNING within here
            
            logger = self.config.options.logger

            if state == ProcessStates.BACKOFF:
                if proc.backoff > proc.config.startretries:
                    # BACKOFF -> FATAL if the proc has exceeded its number
                    # of retries
                    proc.delay = 0
                    proc.backoff = 0
                    proc.system_stop = 1
                    msg = ('entered FATAL state, too many start retries too '
                           'quickly')
                    logger.info('gave up: %s %s' % (proc.config.name, msg))

            elif state == ProcessStates.STARTING:
                if now - proc.laststart > proc.config.startsecs:
                    # STARTING -> RUNNING if the proc has started
                    # successfully and it has stayed up for at least
                    # proc.config.startsecs,
                    proc.delay = 0
                    proc.backoff = 0
                    msg = (
                        'entered RUNNING state, process has stayed up for '
                        '> than %s seconds (startsecs)' % proc.config.startsecs)
                    logger.info('success: %s %s' % (proc.config.name, msg))

    def get_delay_processes(self):
        """ Processes which are starting or stopping """
        return [ x for x in self.processes.values() if x.delay ]

    def get_undead(self):
        """ Processes which we've attempted to stop but which haven't responded
        to a kill request within a given amount of time (stopwaitsecs) """
        now = time.time()
        processes = self.processes.values()
        undead = []

        for proc in processes:
            if proc.get_state() == ProcessStates.STOPPING:
                time_left = proc.delay - now
                if time_left <= 0:
                    undead.append(proc)
        return undead

    def kill_undead(self):
        for undead in self.get_undead():
            # kill processes which are taking too long to stop with a final
            # sigkill.  if this doesn't kill it, the process will be stuck
            # in the STOPPING state forever.
            self.config.options.logger.critical(
                'killing %r (%s) with SIGKILL' % (undead.config.name,
                                                  undead.pid))
            undead.kill(signal.SIGKILL)



class Logger:
    options = None # reference to options.ServerOptions instance
    procname = '' # process name which "owns" this logger
    channel = None # 'stdin' or 'stdout'
    capturemode = False # are we capturing process event data
    mainlog = None #  the process' "normal" log file
    capturelog = None # the log file while we're in capturemode
    childlog = None # the current logger (event or main)
    output_buffer = '' # data waiting to be logged
    
    def __init__(self, options, procname, channel, logfile, logfile_backups,
                 logfile_maxbytes, capturefile):
        self.procname = procname
        self.channel = channel
        self.options = options
        self.mainlog = options.getLogger(
                logfile, logging.INFO,
                '%(message)s',
                rotating=not not logfile_maxbytes,
                maxbytes=logfile_maxbytes,
                backups=logfile_backups)
        self.childlog = self.mainlog

        self.capturefile = capturefile
        if capturefile:
            self.capturelog = options.getLogger(
                capturefile,
                logging.INFO,
                '%(message)s',
                rotating=False)

    def removelogs(self):
        for log in (self.mainlog, self.capturelog):
            if log is not None:
                for handler in log.handlers:
                    handler.remove()
                    handler.reopen()

    def reopenlogs(self):
        for log in (self.mainlog, self.capturelog):
            if log is not None:
                for handler in log.handlers:
                    handler.reopen()

    def log_output(self):
        if self.capturemode:
            token = ProcessCommunicationEvent.END_TOKEN
        else:
            token = ProcessCommunicationEvent.BEGIN_TOKEN

        data = self.output_buffer
        self.output_buffer = ''

        if len(data) <= len(token):
            self.output_buffer = data
            return # not enough data

        try:
            before, after = data.split(token, 1)
        except ValueError:
            after = None
            index = find_prefix_at_end(data, token)
            if index:
                self.output_buffer = self.output_buffer + data[-index:]
                data = data[:-index]
        else:
            data = before
            self.toggle_capturemode()
            self.output_buffer = after

        if self.childlog and data:
            if self.options.strip_ansi:
                data = self.options.stripEscapes(data)
            self.childlog.info(data)

        if data:
            msg = '%r %s output:\n%s' % (self.procname, self.channel, data)
            self.options.logger.log(self.options.TRACE, msg)

        if after:
            self.log_output()

    def toggle_capturemode(self):
        self.capturemode = not self.capturemode

        if self.capturelog is not None:
            if self.capturemode:
                self.childlog = self.capturelog
            else:
                capturefile = self.capturefile
                for handler in self.capturelog.handlers:
                    handler.flush()
                data = ''
                f = self.options.open(capturefile, 'r')
                while 1:
                    new = f.read(1<<20) # 1MB
                    data += new
                    if not new:
                        break
                    if len(data) > (1 << 21): #2MB
                        data = data[:1<<21]
                        # DWIM: don't overrun memory
                        self.options.logger.info(
                            'Truncated oversized EVENT mode log to 2MB')
                        break 

                channel = self.channel
                procname = self.procname
                notify(ProcessCommunicationEvent(procname, channel, data))
                                        
                msg = "%r %s emitted a comm event" % (procname, channel)
                self.options.logger.log(self.options.TRACE, msg)
                                        
                for handler in self.capturelog.handlers:
                    handler.remove()
                    handler.reopen()
                self.childlog = self.mainlog
        
def find_prefix_at_end(haystack, needle):
    l = len(needle) - 1
    while l and not haystack.endswith(needle[:l]):
        l -= 1
    return l

