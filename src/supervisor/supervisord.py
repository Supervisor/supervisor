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
-c/--configuration FILENAME -- configuration file
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
                   old automatic child log files) at startup.
-w/--http_port SOCKET -- the host/port that the HTTP server should listen on
-g/--http_username STR -- the username for HTTP auth
-r/--http_password STR -- the password for HTTP auth
-a/--minfds NUM -- the minimum number of file descriptors for start success
-t/--strip_ansi -- strip ansi escape codes from process output
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
from supervisor import events
from supervisor.states import SupervisorStates
from supervisor.states import getProcessStateDescription

class Supervisor:
    mood = 1 # 1: up, 0: restarting, -1: suicidal
    stopping = False # set after we detect that we are handling a stop request
    lastdelayreport = 0 # throttle for delayed process error reports at stop
    process_groups = None # map of process group name to process group object
    stop_groups = None # list used for priority ordered shutdown

    def __init__(self, options):
        self.options = options
        self.process_groups = {}

    def main(self, args=None, test=False, first=False):
        self.options.realize(args, doc=__doc__)
        self.options.cleanup_fds()
        info_messages = []
        critical_messages = []
        warn_messages = []
        setuid_msg = self.options.set_uid()
        if setuid_msg:
            critical_messages.append(setuid_msg)
        if first:
            rlimit_messages = self.options.set_rlimits()
            info_messages.extend(rlimit_messages)
        warn_messages.extend(self.options.parse_warnings)

        # this sets the options.logger object
        # delay logger instantiation until after setuid
        self.options.make_logger(critical_messages, warn_messages,
                                 info_messages)

        if not self.options.nocleanup:
            # clean up old automatic logs
            self.options.clear_autochildlogdir()

        for config in self.options.process_group_configs:
            config.after_setuid()

        self.run(test)

    def run(self, test=False):
        self.process_groups = {} # clear
        self.stop_groups = None # clear
        events.clear()
        try:
            for config in self.options.process_group_configs:
                name = config.name
                self.process_groups[name] = config.make_group()
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

    def get_process_map(self):
        process_map = {}
        pgroups = self.process_groups.values()
        for group in pgroups:
            process_map.update(group.get_dispatchers())
        return process_map

    def get_delay_processes(self):
        delayprocs = []

        pgroups = self.process_groups.values()
        for group in pgroups:
            delayprocs.extend(group.get_delay_processes())

        if delayprocs:
            # throttle 'waiting for x to die' reports
            now = time.time()
            if now > (self.lastdelayreport + 3): # every 3 secs
                names = [ p.config.name for p in delayprocs]
                namestr = ', '.join(names)
                self.options.logger.info('waiting for %s to die' % namestr)
                self.lastdelayreport = now
                for proc in delayprocs:
                    state = getProcessStateDescription(proc.get_state())
                    self.options.logger.debug(
                        '%s state: %s' % (proc.config.name, state))
        return delayprocs

    def ordered_stop_groups_phase_1(self):
        if self.stop_groups:
            # stop the last group (the one with the "highest" priority)
            self.stop_groups[-1].stop_all()

    def ordered_stop_groups_phase_2(self):
        # after phase 1 we've transitioned and reaped, let's see if we
        # can remove the group we stopped from the stop_groups queue.
        if self.stop_groups:
            # pop the last group (the one with the "highest" priority)
            group = self.stop_groups.pop()
            if group.get_unstopped_processes():
                # if any processes in the group aren't yet in a
                # stopped state, we're not yet done shutting this
                # group down, so push it back on to the end of the
                # stop group queue
                self.stop_groups.append(group)

    def runforever(self, test=False):
        events.notify(events.SupervisorRunningEvent())
        timeout = 1

        socket_map = self.options.get_socket_map()

        while 1:
            combined_map = {}
            combined_map.update(socket_map)
            combined_map.update(self.get_process_map())

            pgroups = self.process_groups.values()
            pgroups.sort()

            if self.mood > 0:
                [ group.start_necessary() for group in pgroups ]

            elif self.mood < 1:
                if not self.stopping:
                    # first time, set the stopping flag, do a
                    # notification and set stop_groups
                    self.stopping = True
                    self.stop_groups = pgroups[:]
                    events.notify(events.SupervisorStoppingEvent())

                self.ordered_stop_groups_phase_1()

                if not self.get_delay_processes():
                    # if there are no delayed processes (we're done killing
                    # everything), it's OK to stop or reload
                    raise asyncore.ExitNow

            r, w, x = [], [], []

            for fd, dispatcher in combined_map.items():
                if dispatcher.readable():
                    r.append(fd)
                if dispatcher.writable():
                    w.append(fd)

            try:
                r, w, x = self.options.select(r, w, x, timeout)
            except select.error, err:
                r = w = x = []
                if err[0] == errno.EINTR:
                    self.options.logger.trace('EINTR encountered in select')
                else:
                    raise

            for fd in r:
                if combined_map.has_key(fd):
                    try:
                        dispatcher = combined_map[fd]
                        self.options.logger.trace(
                            'read event caused by %(dispatcher)s',
                            dispatcher=dispatcher)
                        dispatcher.handle_read_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        combined_map[fd].handle_error()

            for fd in w:
                if combined_map.has_key(fd):
                    try:
                        dispatcher = combined_map[fd]
                        self.options.logger.trace(
                            'write event caused by %(dispatcher)s',
                            dispatcher=dispatcher)
                        dispatcher.handle_write_event()
                    except asyncore.ExitNow:
                        raise
                    except:
                        combined_map[fd].handle_error()

            [ group.transition() for group  in pgroups ]

            self.reap()
            self.handle_signal()

            if self.mood < 1:
                self.ordered_stop_groups_phase_2()

            if test:
                break

    def reap(self, once=False):
        pid, sts = self.options.waitpid()
        if pid:
            process = self.options.pidhistory.get(pid, None)
            if process is None:
                self.options.logger.critical('reaped unknown pid %s)' % pid)
            else:
                process.finish(pid, sts)
                del self.options.pidhistory[pid]
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
                for group in self.process_groups.values():
                    group.reopenlogs()
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
        try:
            d.main(None, test, first)
        except asyncore.ExitNow:
            pass
        first = False
        if test:
            return d
        if d.mood < 0:
            break
        if d.options.httpserver:
            d.options.httpserver.close()

if __name__ == "__main__":
    main()
