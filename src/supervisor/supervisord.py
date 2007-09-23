#!/usr/bin/env python
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
-a/--minfds NUM -- the minimum number of file descriptors for start success
-t/--strip_ansi -- strip ansi escape codes from process output
--minprocs NUM  -- the minimum number of processes available for start success
--profile_options OPTIONS -- run supervisord under profiler and output
                             results based on OPTIONS, which  is a comma-sep'd
                             list of 'cumulative', 'calls', and/or 'callers',
                             e.g. 'cumulative,callers')
"""

import os
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
    stopping = False # set after we detect that we are handling a stop request
    lastshutdownreport = 0 # throttle for delayed process error reports at stop
    process_groups = None # map of process group name to process group object
    stop_groups = None # list used for priority ordered shutdown

    def __init__(self, options):
        self.options = options
        self.process_groups = {}

    def main(self):
        self.options.cleanup_fds()
        info_messages = []
        critical_messages = []
        warn_messages = []
        setuid_msg = self.options.set_uid()
        if setuid_msg:
            critical_messages.append(setuid_msg)
        if self.options.first:
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

        self.run()

    def run(self):
        self.process_groups = {} # clear
        self.stop_groups = None # clear
        events.clear()
        try:
            for config in self.options.process_group_configs:
                name = config.name
                self.process_groups[name] = config.make_group()
            self.options.process_environment()
            self.options.openhttpservers(self)
            self.options.setsignals()
            if not self.options.nodaemon:
                self.options.daemonize()
            # writing pid file needs to come *after* daemonizing or pid
            # will be wrong
            self.options.write_pidfile()
            self.runforever()
        finally:
            self.options.cleanup()

    def get_process_map(self):
        process_map = {}
        pgroups = self.process_groups.values()
        for group in pgroups:
            process_map.update(group.get_dispatchers())
        return process_map

    def shutdown_report(self):
        unstopped = []

        pgroups = self.process_groups.values()
        for group in pgroups:
            unstopped.extend(group.get_unstopped_processes())

        if unstopped:
            # throttle 'waiting for x to die' reports
            now = time.time()
            if now > (self.lastshutdownreport + 3): # every 3 secs
                names = [ p.config.name for p in unstopped ]
                namestr = ', '.join(names)
                self.options.logger.info('waiting for %s to die' % namestr)
                self.lastshutdownreport = now
                for proc in unstopped:
                    state = getProcessStateDescription(proc.get_state())
                    self.options.logger.blather(
                        '%s state: %s' % (proc.config.name, state))
        return unstopped

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

    def runforever(self):
        events.notify(events.SupervisorRunningEvent())
        timeout = 1

        socket_map = self.options.get_socket_map()

        while 1:
            combined_map = {}
            combined_map.update(socket_map)
            combined_map.update(self.get_process_map())

            pgroups = self.process_groups.values()
            pgroups.sort()

            if self.options.mood < SupervisorStates.RUNNING:
                if not self.stopping:
                    # first time, set the stopping flag, do a
                    # notification and set stop_groups
                    self.stopping = True
                    self.stop_groups = pgroups[:]
                    events.notify(events.SupervisorStoppingEvent())

                self.ordered_stop_groups_phase_1()

                if not self.shutdown_report():
                    # if there are no unstopped processes (we're done
                    # killing everything), it's OK to swtop or reload
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
                    self.options.logger.blather('EINTR encountered in select')
                else:
                    raise

            for fd in r:
                if combined_map.has_key(fd):
                    try:
                        dispatcher = combined_map[fd]
                        self.options.logger.blather(
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
                        self.options.logger.blather(
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

            if self.options.mood < SupervisorStates.RUNNING:
                self.ordered_stop_groups_phase_2()

            if self.options.test:
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
                self.options.logger.warn(
                    'received %s indicating exit request' % signame(sig))
                self.options.mood = SupervisorStates.SHUTDOWN
            elif sig == signal.SIGHUP:
                self.options.logger.warn(
                    'received %s indicating restart request' % signame(sig))
                self.options.mood = SupervisorStates.RESTARTING
            elif sig == signal.SIGCHLD:
                self.options.logger.debug(
                    'received %s indicating a child quit' % signame(sig))
            elif sig == signal.SIGUSR2:
                self.options.logger.info(
                    'received %s indicating log reopen request' % signame(sig))
                self.options.reopenlogs()
                for group in self.process_groups.values():
                    group.reopenlogs()
            else:
                self.options.logger.blather(
                    'received %s indicating nothing' % signame(sig))
        
    def get_state(self):
        return self.options.mood

# profile entry point
def profile(cmd, globals, locals, sort_order, callers):
    import profile
    import pstats
    import tempfile
    fd, fn = tempfile.mkstemp()
    try:
        profile.runctx(cmd, globals, locals, fn)
        stats = pstats.Stats(fn)
        stats.strip_dirs()
        # calls,time,cumulative and cumulative,calls,time are useful
        stats.sort_stats(*sort_order or ('cumulative', 'calls', 'time'))
        if callers:
            stats.print_callers(.3)
        else:
            stats.print_stats(.3)
    finally:
        os.remove(fn)


# Main program
def main(args=None, test=False):
    assert os.name == "posix", "This code makes Unix-specific assumptions"
    # if we hup, restart by making a new Supervisor()
    first = True
    while 1:
        options = ServerOptions()
        options.realize(args, doc=__doc__)
        options.first = first
        options.test = test
        if options.profile_options:
            sort_order, callers = options.profile_options
            profile('go(options)', globals(), locals(), sort_order, callers)
        else:
            go(options)
        if test or (options.mood < SupervisorStates.RESTARTING):
            break
        options.close_httpservers()
        options.close_logger()
        first = False

def go(options):
    d = Supervisor(options)
    try:
        d.main()
    except asyncore.ExitNow:
        pass

if __name__ == "__main__":
    main()
