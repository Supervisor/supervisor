#!/usr/bin/env python -u
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
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""supervisorctl -- control applications run by supervisord from the cmd line.

Usage: python supervisorctl.py [-C URL] [-h] [action [arguments]]

Options:
-c/--configuration URL -- configuration file or URL
-h/--help -- print usage message and exit
-i/--interactive -- start an interactive shell after executing commands
-s/--serverurl URL -- URL on which supervisord server is listening
     (default "http://localhost:9001").  
-u/--username -- username to use for authentication with server
-p/--password -- password to use for authentication with server

action [arguments] -- see below

Actions are commands like "tailf" or "stop".  If -i is specified or no action is
specified on the command line, a"shell" interpreting actions typed
interactively is started.  Use the action "help" to find out about available
actions.
"""

import os
import cmd
import sys
import time
import getpass
import supervisord
import rpc
from options import ClientOptions
import xmlrpclib
import urllib2
import fcntl
import socket
import asyncore
import errno
import time
import datetime

class Controller(cmd.Cmd):

    def __init__(self, options, completekey='tab', stdin=None, stdout=None):
        self.options = options
        self.prompt = self.options.prompt + '> '
        cmd.Cmd.__init__(self, completekey, stdin, stdout)

    def emptyline(self):
        # We don't want a blank line to repeat the last command.
        return

    def onecmd(self, line):
        """ Override the onecmd method to catch and print all exceptions
        """
        origline = line
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if cmd == '':
            return self.default(line)
        else:
            try:
                func = getattr(self, 'do_' + cmd)
            except AttributeError:
                return self.default(line)
            try:
                try:
                    return func(arg)
                except xmlrpclib.ProtocolError, e:
                    if e.errcode == 401:
                        if self.options.interactive:
                            self._output('Server requires authentication')
                            username = raw_input('Username:')
                            password = getpass.getpass(prompt='Password:')
                            self._output('')
                            self.options.username = username
                            self.options.password = password
                            return self.onecmd(origline)
                        else:
                            self.options.usage('Server requires authentication')
                    else:
                        raise
            except SystemExit:
                raise
            except Exception, e:
                (file, fun, line), t, v, tbinfo = asyncore.compact_traceback()
                error = 'error: %s, %s: file: %s line: %s' % (t, v, file, line)
                self._output(error)

    def _output(self, stuff):
        if stuff is not None:
            self.stdout.write(stuff + '\n')

    def _makeNamespace(self, namespace):
        proxy = self.options.getServerProxy()
        namespace = getattr(proxy, namespace)
        return namespace

    def _get_supervisor(self):
        supervisor = self._makeNamespace('supervisor')
        return supervisor

    def _upcheck(self):
        try:
            supervisor = self._get_supervisor()
            supervisor.getVersion()
        except socket.error, why:
            if why[0] == errno.ECONNREFUSED:
                self._output('%s refused connection' % self.options.serverurl)
                return False
            raise
        return True

    def help_help(self):
        self._output("help\t\tPrint a list of available actions.")
        self._output("help <action>\tPrint help for <action>.")

    def do_EOF(self, arg):
        self._output('')
        return 1

    def help_EOF(self):
        self._output("To quit, type ^D or use the quit command.")

    def _tailf(self, arg):
        if not self._upcheck():
            return

        self._output('==> Press Ctrl-C to exit <==')

        url = self.options.serverurl + '/logtail/' + arg
        username = self.options.username
        password = self.options.password
        try:
            # Python's urllib2 (at least as of Python 2.4.2) isn't up
            # to this task; it doesn't actually implement a proper
            # HTTP/1.1 client that deals with chunked responses (it
            # always sends a Connection: close header).  We use a
            # homegrown client based on asyncore instead.  This makes
            # me sad.
            import http_client
            listener = http_client.Listener()
            handler = http_client.HTTPHandler(listener, username, password)
            handler.get(url)
            asyncore.loop()
        except KeyboardInterrupt:
            self._output('')
            return

    def do_tail(self, arg):
        if not self._upcheck():
            return
        
        args = arg.strip().split()

        if len(args) < 1:
            self._output('Error: too few arguments')
            self.help_tail()
            return

        elif len(args) > 2:
            self._output('Error: too many arguments')
            self.help_tail()
            return

        elif len(args) == 2:
            if args[0].startswith('-'):
                what = args[0][1:]
                if what == 'f':
                    return self._tailf(args[1])
                try:
                    what = int(what)
                except:
                    self._output('Error: bad argument %s' % args[0])
                    return
                else:
                    bytes = what
            else:
                self._output('Error: bad argument %s' % args[0])
                
        else:
            bytes = 1600

        processname = args[-1]
        
        supervisor = self._get_supervisor()

        try:
            output = supervisor.readProcessLog(processname, -bytes, 0)
        except xmlrpclib.Fault, e:
            if e.faultCode == rpc.Faults.FAILED:
                self._output("Error: Log file doesn't yet exist on server")
        else:
            self._output(output)

    def help_tail(self):
        self._output(
            "tail -f <processname>\tContinuous tail of named process stdout,\n"
            "\t\t\tCtrl-C to exit.\n"
            "tail -100 <processname>\tlast 100 *bytes* of process log file\n"
            "tail <processname>\tlast 1600 *bytes* of process log file\n"
            )

    def do_quit(self, arg):
        sys.exit(0)

    def help_quit(self):
        self._output("quit\tExit the supervisor shell.")

    def _interpretProcessInfo(self, info):
        result = {}
        result['name'] = info['name']
        pid = info['pid']

        state = info['state']

        if state == supervisord.ProcessStates.RUNNING:
            start = info['start']
            now = info['now']
            start_dt = datetime.datetime(*time.gmtime(start)[:6])
            now_dt = datetime.datetime(*time.gmtime(now)[:6])
            uptime = now_dt - start_dt
            desc = 'pid %s, uptime %s' % (info['pid'], uptime)

        elif state == supervisord.ProcessStates.ERROR:
            desc = info['spawnerr']
            if not desc:
                desc = 'unknown error (try "tail %s")' % info['name']

        elif state in (supervisord.ProcessStates.STOPPED,
                       supervisord.ProcessStates.KILLED,
                       supervisord.ProcessStates.EXITED):
            stop = info['stop']
            stop_dt = datetime.datetime(*time.gmtime(stop)[:7])
            desc = stop_dt.strftime('%b %d %I:%M %p')
            desc += ' (%s)' % info['reportstatusmsg']
            

        else:
            desc = ''

        result['desc'] = desc
        result['state'] = supervisord.getProcessStateDescription(state)
        return result

    def do_status(self, arg):
        if not self._upcheck():
            return
        
        supervisor = self._get_supervisor()
        template = '%(name)-14s %(state)-10s %(desc)s'

        processnames = arg.strip().split()

        if processnames:
            for processname in processnames:
                try:
                    info = supervisor.getProcessInfo(processname)
                except xmlrpclib.Fault, e:
                    if e.faultCode == rpc.Faults.BAD_NAME:
                        self._output('No such process %s' % processname)
                    else:
                        raise
                    continue
                newinfo = self._interpretProcessInfo(info)
                self._output(template % newinfo)
        else:
            for info in supervisor.getAllProcessInfo():
                newinfo = self._interpretProcessInfo(info)
                self._output(template % newinfo)

    def help_status(self):
        self._output("status\t\t\tGet all process status info.")
        self._output("status <name>\t\tGet status on a single process by name.")
        self._output("status <name> <name>\tGet status on multiple named "
                     "processes.")

    def _startresult(self, code, processname, default=None):
        template = '%s: ERROR (%s)'
        if code == rpc.Faults.BAD_NAME:
            return template % (processname,'no such process')
        elif code == rpc.Faults.ALREADY_STARTED:
            return template % (processname,'already started')
        elif code == rpc.Faults.SPAWN_ERROR:
            return template % (processname, 'spawn error')
        elif code == rpc.Faults.ABNORMAL_TERMINATION:
            return template % (processname, 'abornal termination')
        elif code == rpc.Faults.SUCCESS:
            return '%s: started' % processname
        
        return default

    def do_start(self, arg):
        if not self._upcheck():
            return

        processnames = arg.strip().split()
        supervisor = self._get_supervisor()

        if not processnames:
            self._output("Error: start requires a process name")
            self.help_start()
            return

        if 'all' in processnames:
            results = supervisor.startAllProcesses()
            for result in results:
                name = result['name']
                code = result['status']
                result = self._startresult(code, name)
                if result is None:
                    # assertion
                    raise ValueError('Unknown result code %s for %s' %
                                     (code, name))
                else:
                    self._output(result)
                
        else:
            for processname in processnames:
                try:
                    result = supervisor.startProcess(processname)
                except xmlrpclib.Fault, e:
                    error = self._startresult(e.faultCode, processname)
                    if error is not None:
                        self._output(error)
                    else:
                        raise
                else:
                    if result == True:
                        self._output('%s: started' % processname)
                    else:
                        raise # assertion

    def help_start(self):
        self._output("start <processname>\t\t\tStart a process.")
        self._output("start <processname> <processname>\tStart multiple "
                     "processes")
        self._output("start all\t\t\t\tStart all processes")
        self._output("  When all processes are started, they are started "
                     "in")
        self._output("  priority order (see config file)")

    def _stopresult(self, code, processname, default=None):
        template = '%s: ERROR (%s)'
        if code == rpc.Faults.BAD_NAME:
            return template % (processname, 'no such process')
        elif code == rpc.Faults.NOT_RUNNING:
            return template % (processname, 'not running')
        elif code == rpc.Faults.SUCCESS:
            return '%s: stopped' % processname
        return default

    def do_stop(self, arg):
        if not self._upcheck():
            return

        processnames = arg.strip().split()
        supervisor = self._get_supervisor()

        if not processnames:
            self._output('Error: stop requires a process name')
            self.help_stop()
            return

        if 'all' in processnames:
            results = supervisor.stopAllProcesses()
            for result in results:
                name = result['name']
                code = result['status']
                result = self._stopresult(code, name)
                if result is None:
                    # assertion
                    raise ValueError('Unknown result code %s for %s' %
                                     (code, name))
                else:
                    self._output(result)

        else:

            for processname in processnames:
                try:
                    result = supervisor.stopProcess(processname)
                except xmlrpclib.Fault, e:
                    error = self._stopresult(e.faultCode, processname)
                    if error is not None:
                        self._output(error)
                    else:
                        raise
                else:
                    if result == True:
                        self._output('%s: stopped' % processname)
                    else:
                        raise # assertion

    def help_stop(self):
        self._output("stop <processname>\t\t\tStop a process.")
        self._output("stop <processname> <processname>\tStop multiple "
                     "processes")
        self._output("stop all\t\t\t\tStop all processes")
        self._output("  When all processes are stopped, they are stopped "
                     "in")
        self._output("  reverse priority order (see config file)")

    def do_restart(self, arg):
        if not self._upcheck():
            return

        processnames = arg.strip().split()

        if not processnames:
            self._output('Error: restart requires a process name')
            self.help_restart()
            return

        self.do_stop(arg)
        self.do_start(arg)

    def help_restart(self):
        self._output("restart <processname>\t\t\tRestart a process.")
        self._output("restart <processname> <processname>\tRestart multiple "
                     "processes")
        self._output("restart all\t\t\t\tRestart all processes")
        self._output("  When all processes are restarted, they are "
                     "started in")
        self._output("  priority order (see config file)")

    def do_shutdown(self, arg):
        if self.options.interactive:
            yesno = raw_input('Really shut the remote supervisord process '
                              'down y/N? ')
            really = yesno.lower().startswith('y')
        else:
            really = 1
        if really:
            supervisor = self._get_supervisor()
            try:
                supervisor.shutdown()
            except xmlrpclib.Fault, e:
                if e.faultCode == rpc.Faults.SHUTDOWN_STATE:
                    self._output('ERROR: already shutting down')
            else:
                self._output('Shut down')

    def help_shutdown(self):
        self._output("shutdown \t\tShut the remote supervisord down.")

    def do_reload(self, arg):
        if self.options.interactive:
            yesno = raw_input('Really restart the remote supervisord process '
                              'y/N? ')
            really = yesno.lower().startswith('y')
        else:
            really = 1
        if really:
            supervisor = self._get_supervisor()
            try:
                supervisor.restart()
            except xmlrpclib.Fault, e:
                if e.faultCode == rpc.Faults.SHUTDOWN_STATE:
                    self._output('ERROR: already shutting down')
            else:
                self._output('Restarted supervisord')

    def help_reload(self):
        self._output("reload \t\tRestart the remote supervisord.")

    def _clearresult(self, code, processname, default=None):
        template = '%s: ERROR (%s)'
        if code == rpc.Faults.BAD_NAME:
            return template % (processname, 'no such process')
        elif code == rpc.Faults.FAILED:
            return template % (processname, 'failed')
        elif code == rpc.Faults.SUCCESS:
            return '%s: cleared' % processname
        return default

    def do_clear(self, arg):
        if not self._upcheck():
            return

        processnames = arg.strip().split()

        if not processnames:
            self._output('Error: clear requires a process name')
            self.help_clear()
            return

        supervisor = self._get_supervisor()

        if 'all' in processnames:
            results = supervisor.clearAllProcessLogs()
            for result in results:
                name = result['name']
                code = result['status']
                result = self._clearresult(code, name)
                if result is None:
                    # assertion
                    raise ValueError('Unknown result code %s for %s' %
                                     (code, name))
                else:
                    self._output(result)

        else:

            for processname in processnames:
                try:
                    result = supervisor.clearProcessLog(processname)
                except xmlrpclib.Fault, e:
                    error = self._clearresult(e.faultCode, processname)
                    if error is not None:
                        self._output(error)
                    else:
                        raise
                else:
                    if result == True:
                        self._output('%s: cleared' % processname)
                    else:
                        raise # assertion

    def help_clear(self):
        self._output("clear <processname>\t\t\tClear a process' log file.")
        self._output("clear <processname> <processname>\tclear multiple "
                     "process log files")
        self._output("clear all\t\t\t\tClear all process log files")

def main(args=None, options=None):
    if options is None:
        options = ClientOptions()
    options.realize(args)
    c = Controller(options)
    if options.args:
        c.onecmd(" ".join(options.args))
    if options.interactive:
        try:
            import readline
        except ImportError:
            pass
        try:
            c.onecmd('status')
            c.cmdloop()
        except KeyboardInterrupt:
            c._output('')
            pass

if __name__ == "__main__":
    main()
