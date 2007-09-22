#!/usr/bin/env python -u
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
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""supervisorctl -- control applications run by supervisord from the cmd line.

Usage: python supervisorctl.py [-c file] [-h] [action [arguments]]

Options:
-c/--configuration -- configuration file path (default /etc/supervisor.conf)
-h/--help -- print usage message and exit
-i/--interactive -- start an interactive shell after executing commands
-s/--serverurl URL -- URL on which supervisord server is listening
     (default "http://localhost:9001").  
-u/--username -- username to use for authentication with server
-p/--password -- password to use for authentication with server

action [arguments] -- see below

Actions are commands like "tail" or "stop".  If -i is specified or no action is
specified on the command line, a"shell" interpreting actions typed
interactively is started.  Use the action "help" to find out about available
actions.
"""

import cmd
import sys
import getpass
import xmlrpclib
import socket
import asyncore
import errno
import urlparse

from supervisor.options import ClientOptions
from supervisor.options import split_namespec
from supervisor import xmlrpc


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
                raise
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
            api = supervisor.getVersion() # deprecated
            from supervisor import rpcinterface
            if api != rpcinterface.API_VERSION:
                self._output(
                    'Sorry, this version of supervisorctl expects to '
                    'talk to a server with API version %s, but the '
                    'remote version is %s.' % (rpcinterface.API_VERSION, api))
                return False
        except xmlrpclib.Fault, e:
            if e.faultCode == xmlrpc.Faults.UNKNOWN_METHOD:
                self._output(
                    'Sorry, supervisord responded but did not recognize '
                    'the supervisor namespace commands that supervisorctl '
                    'uses to control it.  Please check that the '
                    '[rpcinterface:supervisor] section is enabled in the '
                    'configuration file (see sample.conf).')
                return False
            raise 
        except socket.error, why:
            if why[0] == errno.ECONNREFUSED:
                self._output('%s refused connection' % self.options.serverurl)
                return False
            raise
        return True

    def help_help(self):
        self._output("help\t\tPrint a list of available actions")
        self._output("help <action>\tPrint help for <action>")

    def do_EOF(self, arg):
        self._output('')
        return 1

    def help_EOF(self):
        self._output("To quit, type ^D or use the quit command")

    def _tailf(self, path):
        if not self._upcheck():
            return

        self._output('==> Press Ctrl-C to exit <==')

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
            handler.get(self.options.serverurl, path)
            asyncore.loop()
        except KeyboardInterrupt:
            handler.close()
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

        elif len(args) > 3:
            self._output('Error: too many arguments')
            self.help_tail()
            return

        modifier = None

        if args[0].startswith('-'):
            modifier = args.pop(0)

        if len(args) == 1:
            name = args[-1]
            channel = 'stdout'
        else:
            name = args[0]
            channel = args[-1].lower()
            if channel not in ('stderr', 'stdout'):
                self._output('Error: bad channel %r' % channel)
                return

        bytes = 1600

        if modifier is not None:
            what = modifier[1:]
            if what == 'f':
                bytes = None
            else:
                try:
                    bytes = int(what)
                except:
                    self._output('Error: bad argument %s' % modifier)
                    return

        supervisor = self._get_supervisor()

        if bytes is None:
            return self._tailf('/logtail/%s/%s' % (name, channel))

        else:
            try:
                if channel is 'stdout':
                    output = supervisor.readProcessStdoutLog(name,
                                                             -bytes, 0)
                else: # if channel is 'stderr'
                    output = supervisor.readProcessStderrLog(name,
                                                             -bytes, 0)
            except xmlrpclib.Fault, e:
                template = '%s: ERROR (%s)'
                if e.faultCode == xmlrpc.Faults.NO_FILE:
                    self._output(template % (name, 'no log file'))
                elif e.faultCode == xmlrpc.Faults.FAILED:
                    self._output(template % (name,
                                             'unknown error reading log'))
                elif e.faultCode == xmlrpc.Faults.BAD_NAME:
                    self._output(template % (name,
                                             'no such process name'))
            else:
                self._output(output)

    def help_tail(self):
        self._output(
            "tail [-f] <name> [stdout|stderr] (default stdout)\n"
            "Ex:\n"
            "tail -f <name>\t\tContinuous tail of named process stdout\n"
            "\t\t\tCtrl-C to exit.\n"
            "tail -100 <name>\tlast 100 *bytes* of process stdout\n"
            "tail <name> stderr\tlast 1600 *bytes* of process stderr"
            )

    def do_maintail(self, arg):
        if not self._upcheck():
            return
        
        args = arg.strip().split()

        if len(args) > 1:
            self._output('Error: too many arguments')
            self.help_maintail()
            return

        elif len(args) == 1:
            if args[0].startswith('-'):
                what = args[0][1:]
                if what == 'f':
                    path = '/mainlogtail'
                    return self._tailf(path)
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

        supervisor = self._get_supervisor()

        try:
            output = supervisor.readLog(-bytes, 0)
        except xmlrpclib.Fault, e:
            template = '%s: ERROR (%s)'
            if e.faultCode == xmlrpc.Faults.NO_FILE:
                self._output(template % ('supervisord', 'no log file'))
            elif e.faultCode == xmlrpc.Faults.FAILED:
                self._output(template % ('supervisord',
                                         'unknown error reading log'))
        else:
            self._output(output)

    def help_maintail(self):
        self._output(
            "maintail -f \tContinuous tail of supervisor main log file"
            " (Ctrl-C to exit)\n"
            "maintail -100\tlast 100 *bytes* of supervisord main log file\n"
            "maintail\tlast 1600 *bytes* of supervisor main log file\n"
            )

    def do_quit(self, arg):
        sys.exit(0)

    def help_quit(self):
        self._output("quit\tExit the supervisor shell.")

    do_exit = do_quit

    def help_exit(self):
        self._output("exit\tExit the supervisor shell.")

    def _procrepr(self, info):
        template = '%(name)-32s %(state)-10s %(desc)s'
        if info['name'] == info['group']:
            name = info['name']
        else:
            name = '%s:%s' % (info['group'], info['name'])
                    
        return template % {'name':name, 'state':info['statename'],
                           'desc':info['description']}

    def do_status(self, arg):
        if not self._upcheck():
            return
        
        supervisor = self._get_supervisor()

        names = arg.strip().split()

        if names:
            for name in names:
                try:
                    info = supervisor.getProcessInfo(name)
                except xmlrpclib.Fault, e:
                    if e.faultCode == xmlrpc.Faults.BAD_NAME:
                        self._output('No such process %s' % name)
                    else:
                        raise
                    continue
                self._output(self._procrepr(info))
        else:
            for info in supervisor.getAllProcessInfo():
                self._output(self._procrepr(info))

    def help_status(self):
        self._output("status\t\t\tGet all process status info.")
        self._output("status <name>\t\tGet status on a single process by name.")
        self._output("status <name> <name>\tGet status on multiple named "
                     "processes.")

    def _startresult(self, result):
        name = result['name']
        code = result['status']
        template = '%s: ERROR (%s)'
        if code == xmlrpc.Faults.BAD_NAME:
            return template % (name,'no such process')
        elif code == xmlrpc.Faults.ALREADY_STARTED:
            return template % (name,'already started')
        elif code == xmlrpc.Faults.SPAWN_ERROR:
            return template % (name, 'spawn error')
        elif code == xmlrpc.Faults.ABNORMAL_TERMINATION:
            return template % (name, 'abnormal termination')
        elif code == xmlrpc.Faults.SUCCESS:
            return '%s: started' % name
        # assertion
        raise ValueError('Unknown result code %s for %s' % (code, name))

    def do_start(self, arg):
        if not self._upcheck():
            return

        names = arg.strip().split()
        supervisor = self._get_supervisor()

        if not names:
            self._output("Error: start requires a process name")
            self.help_start()
            return

        if 'all' in names:
            results = supervisor.startAllProcesses()
            for result in results:
                result = self._startresult(result)
                self._output(result)
                
        else:
            for name in names:
                group_name, process_name = split_namespec(name)
                if process_name is None:
                    results = supervisor.startProcessGroup(group_name)
                    for result in results:
                        result = self._startresult(result)
                        self._output(result)
                else:
                    try:
                        result = supervisor.startProcess(name)
                    except xmlrpclib.Fault, e:
                        error = self._startresult({'status':e.faultCode,
                                                   'name':name,
                                                   'description':e.faultString})
                        self._output(error)
                    else:
                        self._output('%s: started' % name)

    def help_start(self):
        self._output("start <name>\t\tStart a process")
        self._output("start <gname>:*\t\tStart all processes in a group")
        self._output("start <name> <name>\tStart multiple processes or groups")
        self._output("start all\t\tStart all processes")

    def _stopresult(self, result):
        name = result['name']
        code = result['status']
        fault_string = result['description']
        template = '%s: ERROR (%s)'
        if code == xmlrpc.Faults.BAD_NAME:
            return template % (name, 'no such process')
        elif code == xmlrpc.Faults.NOT_RUNNING:
            return template % (name, 'not running')
        elif code == xmlrpc.Faults.SUCCESS:
            return '%s: stopped' % name
        elif code == xmlrpc.Faults.FAILED:
            return fault_string
        # assertion
        raise ValueError('Unknown result code %s for %s' % (code, name))

    def do_stop(self, arg):
        if not self._upcheck():
            return

        names = arg.strip().split()
        supervisor = self._get_supervisor()

        if not names:
            self._output('Error: stop requires a process name')
            self.help_stop()
            return

        if 'all' in names:
            results = supervisor.stopAllProcesses()
            for result in results:
                result = self._stopresult(result)
                self._output(result)

        else:
            for name in names:
                group_name, process_name = split_namespec(name)
                if process_name is None:
                    results = supervisor.stopProcessGroup(group_name)
                    for result in results:
                        result = self._stopresult(result)
                        self._output(result)
                else:
                    try:
                        result = supervisor.stopProcess(name)
                    except xmlrpclib.Fault, e:
                        error = self._stopresult({'status':e.faultCode,
                                                  'name':name,
                                                  'description':e.faultString})
                        self._output(error)
                    else:
                        self._output('%s: stopped' % name)

    def help_stop(self):
        self._output("stop <name>\t\tStop a process")
        self._output("stop <gname>:*\t\tStop all processes in a group")
        self._output("stop <name> <name>\tStop multiple processes or groups")
        self._output("stop all\t\tStop all processes")

    def do_restart(self, arg):
        if not self._upcheck():
            return

        names = arg.strip().split()

        if not names:
            self._output('Error: restart requires a process name')
            self.help_restart()
            return

        self.do_stop(arg)
        self.do_start(arg)

    def help_restart(self):
        self._output("restart <name>\t\tRestart a process")
        self._output("restart <gname>:*\tRestart all processes in a group")
        self._output("restart <name> <name>\tRestart multiple processes or "
                     "groups")
        self._output("restart all\t\tRestart all processes")

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
                if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                    self._output('ERROR: already shutting down')
            else:
                self._output('Shut down')

    def help_shutdown(self):
        self._output("shutdown \tShut the remote supervisord down.")

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
                if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                    self._output('ERROR: already shutting down')
            else:
                self._output('Restarted supervisord')

    def help_reload(self):
        self._output("reload \t\tRestart the remote supervisord.")

    def _clearresult(self, result):
        name = result['name']
        code = result['status']
        template = '%s: ERROR (%s)'
        if code == xmlrpc.Faults.BAD_NAME:
            return template % (name, 'no such process')
        elif code == xmlrpc.Faults.FAILED:
            return template % (name, 'failed')
        elif code == xmlrpc.Faults.SUCCESS:
            return '%s: cleared' % name
        raise ValueError('Unknown result code %s for %s' % (code, name))

    def do_clear(self, arg):
        if not self._upcheck():
            return

        names = arg.strip().split()

        if not names:
            self._output('Error: clear requires a process name')
            self.help_clear()
            return

        supervisor = self._get_supervisor()

        if 'all' in names:
            results = supervisor.clearAllProcessLogs()
            for result in results:
                result = self._clearresult(result)
                self._output(result)

        else:

            for name in names:
                try:
                    result = supervisor.clearProcessLogs(name)
                except xmlrpclib.Fault, e:
                    error = self._clearresult({'status':e.faultCode,
                                               'name':name,
                                               'description':e.faultString})
                    self._output(error)
                else:
                    self._output('%s: cleared' % name)

    def help_clear(self):
        self._output("clear <name>\t\tClear a process' log files.")
        self._output("clear <name> <name>\tClear multiple process' log files")
        self._output("clear all\t\tClear all process' log files")

    def do_open(self, arg):
        url = arg.strip()
        parts = urlparse.urlparse(url)
        if parts[0] not in ('unix', 'http'):
            self._output('ERROR: url must be http:// or unix://')
            return
        self.options.serverurl = url
        self.do_status('')

    def help_open(self):
        self._output("open <url>\tConnect to a remote supervisord process.")
        self._output("\t\t(for UNIX domain socket, use unix:///socket/path)")

    def do_version(self, arg):
        if not self._upcheck():
            return
        supervisor = self._get_supervisor()
        self._output(supervisor.getSupervisorVersion())

    def help_version(self):
        self._output("version\t\t\tShow the version of the remote supervisord "
                     "process")

def main(args=None, options=None):
    if options is None:
        options = ClientOptions()
    options.realize(args, doc=__doc__)
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
