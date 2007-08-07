#!/usr/bin/env python
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
"""supervisord -- run a set of applications as daemons.

Usage: %s [options]

Options:
-c/--configuration URL -- configuration file or URL
-n/--nodaemon -- run in the foreground (same as 'nodaemon true' in config file)
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
-t/--strip_ansi -- strip ansi escape codes from output
--minprocs NUM  -- the minimum number of processes available for start success
"""

import os
import sys
import time
import errno
import select
import signal
import asyncore

from supervisor.options import ServerOptions
from supervisor.options import signame
from supervisor.process import ProcessStates

class SupervisorStates:
    ACTIVE = 0
    SHUTDOWN = 1

def getSupervisorStateDescription(code):
    for statename in SupervisorStates.__dict__:
        if getattr(SupervisorStates, statename) == code:
            return statename


class Supervisor:
    mood = 1 # 1: up, 0: restarting, -1: suicidal
    stopping = False # set after we detect that we are handling a stop request
    lastdelayreport = 0 # while we're stopping, if delayed, last time we tried

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
            self.options.process_environment()
            self.options.openhttpserver(self)
            self.options.setsignals()
            if not self.options.nodaemon:
                self.options.daemonize()
            # writing pid file needs to come *after* daemonizing or pid
            # will be wrong
            self.options.write_pidfile()
            self.runforever(test)
        finally:
            self.options.cleanup()

    def runforever(self, test=False):
        timeout = 1

        socket_map = self.options.get_socket_map()

        while 1:
            if self.mood > 0:
                self.start_necessary()

            r, w, x = [], [], []

            if self.mood < 1:
                if not self.stopping:
                    self.stop_all()
                    self.stopping = True

                # if there are no delayed processes (we're done killing
                # everything), it's OK to stop or reload
                delayprocs = self.get_delay_processes()
                if delayprocs:
                    now = time.time()
                    if now > (self.lastdelayreport + 3): # every 3 secs
                        names = [ p.config.name for p in delayprocs]
                        namestr = ', '.join(names)
                        self.options.logger.info('waiting for %s to die' %
                                                 namestr)
                        self.lastdelayreport = now
                else:
                    break

            process_map = {}

            # process input and output
            for proc in self.processes.values():
                proc.log_output()

                # process output fds
                for fd, drain in proc.get_output_drains():
                    r.append(fd)
                    process_map[fd] = drain

                # process input fds
                if proc.stdin_buffer:
                    input_drains = proc.get_input_drains()
                    for fd, drain in input_drains:
                        w.append(fd)
                        process_map[fd] = drain

            # medusa i/o fds
            for fd, dispatcher in socket_map.items():
                if dispatcher.readable():
                    r.append(fd)
                if dispatcher.writable():
                    w.append(fd)

            try:
                r, w, x = select.select(r, w, x, timeout)
            except select.error, err:
                r = w = x = []
                if err[0] == errno.EINTR:
                    self.options.logger.log(self.options.TRACE,
                                            'EINTR encountered in select')
                    
                else:
                    raise

            for fd in r:
                if process_map.has_key(fd):
                    drain = process_map[fd]
                    # drain the file descriptor data to the stdout/stderr_buffer
                    drain()

                if socket_map.has_key(fd):
                    try:
                        socket_map[fd].handle_read_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        socket_map[fd].handle_error()

            for fd in w:
                if process_map.has_key(fd):
                    # drain the stdin_buffer by sending it to child's stdin
                    drain = process_map[fd]
                    drain()

                if socket_map.has_key(fd):
                    try:
                        socket_map[fd].handle_write_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        socket_map[fd].handle_error()

            self.transition()
            self.kill_undead()
            self.reap()
            self.handle_signal()

            if test:
                break

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
        now = time.time()
        processes = self.processes.values()
        for proc in processes:
            state = proc.get_state()

            # we need to transition processes between BACKOFF ->
            # FATAL and STARTING -> RUNNING within here
            
            config = proc.config
            logger = self.options.logger

            if state == ProcessStates.BACKOFF:
                if proc.backoff > config.startretries:
                    # BACKOFF -> FATAL if the proc has exceeded its number
                    # of retries
                    proc.delay = 0
                    proc.backoff = 0
                    proc.system_stop = 1
                    msg = ('entered FATAL state, too many start retries too '
                           'quickly')
                    logger.info('gave up: %s %s' % (config.name, msg))

            elif state == ProcessStates.STARTING:
                if now - proc.laststart > config.startsecs:
                    # STARTING -> RUNNING if the proc has started
                    # successfully and it has stayed up for at least
                    # self.config.startsecs,
                    proc.delay = 0
                    proc.backoff = 0
                    msg = ('entered RUNNING state, process has stayed up for '
                           '> than %s seconds (startsecs)' % config.startsecs)
                    logger.info('success: %s %s' % (config.name, msg))

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
            self.options.logger.critical(
                'killing %r (%s) with SIGKILL' % (undead.config.name,
                                                  undead.pid))
            undead.kill(signal.SIGKILL)

    def reap(self, once=False):
        pid, sts = self.options.waitpid()
        if pid:
            process = self.options.pidhistory.get(pid, None)
            if process is None:
                self.options.logger.critical('reaped unknown pid %s)' % pid)
            else:
                name = process.config.name
                process.finish(pid, sts)
            if not once:
                self.reap() # keep reaping until no more kids to reap

    def handle_signal(self):
        if self.options.signal:
            sig, self.options.signal = self.options.signal, None
            if sig in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT):
                self.options.logger.critical(
                    'received %s indicating exit request' % signame(sig))
                self.mood = -1
            elif sig == signal.SIGHUP:
                self.options.logger.critical(
                    'received %s indicating restart request' % signame(sig))
                self.mood = 0
            elif sig == signal.SIGCHLD:
                self.options.logger.info(
                    'received %s indicating a child quit' % signame(sig))
            elif sig == signal.SIGUSR2:
                self.options.logger.info(
                    'received %s indicating log reopen request' % signame(sig))
                self.options.reopenlogs()
                for process in self.processes.values():
                    process.reopenlogs()
            else:
                self.options.logger.debug(
                    'received %s indicating nothing' % signame(sig))
        
    def get_state(self):
        if self.mood <= 0:
            return SupervisorStates.SHUTDOWN
        return SupervisorStates.ACTIVE

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
