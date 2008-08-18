#!/usr/bin/env python -u
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
-r/--history-file -- keep a readline history (if readline is available)

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
import threading

from supervisor.options import ClientOptions
from supervisor.options import split_namespec
from supervisor import xmlrpc

class fgthread(threading.Thread):
    
    # A subclass of threading.Thread, with a kill() method.
    # To be used for foreground output/error streaming.
    # http://mail.python.org/pipermail/python-list/2004-May/260937.html
  
    def __init__(self, program, ctl):
        threading.Thread.__init__(self)
        import http_client
        self.killed = False
        self.program=program
        self.ctl=ctl
        self.listener=http_client.Listener()
        self.output_handler=http_client.HTTPHandler(self.listener,
                                                    self.ctl.options.username,
                                                    self.ctl.options.password)
        self.error_handler=http_client.HTTPHandler(self.listener,
                                                   self.ctl.options.username,
                                                   self.ctl.options.password)

    def start(self):
        # Start the thread
        self.__run_backup = self.run
        self.run = self.__run
        threading.Thread.start(self)

    def run(self):
        self.output_handler.get(self.ctl.options.serverurl,
                                '/logtail/%s/stdout'%self.program)
        self.error_handler.get(self.ctl.options.serverurl,
                               '/logtail/%s/stderr'%self.program)
        asyncore.loop()

    def __run(self):
        # Hacked run function, which installs the trace
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, why, arg):
        if why == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, why, arg):
        if self.killed:
            if why == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.output_handler.close()
        self.error_handler.close()
        self.killed = True

class Controller(cmd.Cmd):

    def __init__(self, options, completekey='tab', stdin=None,
                 stdout=None):
        self.options = options
        self.prompt = self.options.prompt + '> '
        self.options.plugins = []
        self.vocab = ['add','exit','maintail','pid','reload',
                      'restart','start','stop','version','clear',
                      'fg','open','quit','remove','shutdown','status',
                      'tail','help']
        self.info=self.get_supervisor().getAllProcessInfo()
        cmd.Cmd.__init__(self, completekey, stdin, stdout)
        for name, factory, kwargs in self.options.plugin_factories:
            plugin = factory(self, **kwargs)
            self.options.plugins.append(plugin)
            plugin.name = name

    def emptyline(self):
        # We don't want a blank line to repeat the last command.
        return

    def onecmd(self, line):
        """ Override the onecmd method to:
          - catch and print all exceptions
          - allow for composite commands in interactive mode (foo; bar)
          - call 'do_foo' on plugins rather than ourself
        """
        origline = line
        lines = line.split(';') # don't filter(None, line.split), as we pop
        line = lines.pop(0)
        # stuffing the remainder into cmdqueue will cause cmdloop to
        # call us again for each command.
        self.cmdqueue.extend(lines)
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if cmd == '':
            return self.default(line)
        else:
            do_func = self._get_do_func(cmd)
            if do_func is None:
                return self.default(line)
            try:
                try:
                    return do_func(arg)
                except xmlrpclib.ProtocolError, e:
                    if e.errcode == 401:
                        if self.options.interactive:
                            self.output('Server requires authentication')
                            username = raw_input('Username:')
                            password = getpass.getpass(prompt='Password:')
                            self.output('')
                            self.options.username = username
                            self.options.password = password
                            return self.onecmd(origline)
                        else:
                            self.options.usage('Server requires authentication')
                    else:
                        raise
                do_func(arg)
            except SystemExit:
                raise
            except Exception, e:
                (file, fun, line), t, v, tbinfo = asyncore.compact_traceback()
                error = 'error: %s, %s: file: %s line: %s' % (t, v, file, line)
                self.output(error)

    def _get_do_func(self, cmd):
        func_name = 'do_' + cmd
        func = getattr(self, func_name, None)
        if not func:
            for plugin in self.options.plugins:
                func = getattr(plugin, func_name, None)
                if func is not None:
                    break
        return func

    def output(self, stuff):
        if stuff is not None:
            self.stdout.write(stuff + '\n')

    def get_supervisor(self):
        proxy = self.options.getServerProxy()
        namespace = getattr(proxy, 'supervisor')
        return namespace

    def upcheck(self):
        try:
            supervisor = self.get_supervisor()
            api = supervisor.getVersion() # deprecated
            from supervisor import rpcinterface
            if api != rpcinterface.API_VERSION:
                self.output(
                    'Sorry, this version of supervisorctl expects to '
                    'talk to a server with API version %s, but the '
                    'remote version is %s.' % (rpcinterface.API_VERSION, api))
                return False
        except xmlrpclib.Fault, e:
            if e.faultCode == xmlrpc.Faults.UNKNOWN_METHOD:
                self.output(
                    'Sorry, supervisord responded but did not recognize '
                    'the supervisor namespace commands that supervisorctl '
                    'uses to control it.  Please check that the '
                    '[rpcinterface:supervisor] section is enabled in the '
                    'configuration file (see sample.conf).')
                return False
            raise 
        except socket.error, why:
            if why[0] == errno.ECONNREFUSED:
                self.output('%s refused connection' % self.options.serverurl)
                return False
            raise
        return True

    def completionmatches(self,text,line,flag=0):
        groups=[]
        programs=[]
        groupwiseprograms={}
        for i in self.info:
            programs.append(i['name'])
            if i['group'] not in groups:
                groups.append(i['group'])
                groupwiseprograms[i['group']]=[]
            groupwiseprograms[i['group']].append(i['name'])
        total=[]
        for i in groups:
            if i in programs:
                total.append(i+' ')
            else:
                for n in groupwiseprograms[i]:
                    total.append(i+':'+n+' ')
        if flag:
            # add/remove require only the group name
            return [i+' ' for i in groups if i.startswith(text)]
        if len(line.split()) == 1:
            return total
        else:
            current=line.split()[-1]
            if line.endswith(' ') and len(line.split()) > 1:
                results=[i for i in total if i.startswith(text)]
                return results
            if ':' in current:
                g=current.split(':')[0]
                results = [i+' ' for i in groupwiseprograms[g]
                           if i.startswith(text)]
                return results
            results = [i for i in total if i.startswith(text)]
            return results

    def complete(self,text,state):
        try:
            import readline
        except ImportError:
            return None
        line=readline.get_line_buffer()
        if line == '':
            results = [i+' ' for i in self.vocab if i.startswith(text)]+[None]
            return results[state]
        else:
            exp=line.split()[0]
            if exp in ['start','stop','restart','clear','status','tail','fg']:
                if not line.endswith(' ') and len(line.split()) == 1:
                    return [text+' ',None][state]
                if exp == 'fg':
                    if line.endswith(' ') and len(line.split()) > 1:
                        return None
                results=self.completionmatches(text,line)+[None]
                return results[state]
            elif exp in ['maintail','pid','reload','shutdown','exit','open',
                         'quit','version','EOF']:
                return None
            elif exp == 'help':
                if line.endswith(' ') and len(line.split()) > 1:
                    return None
                results=[i+' ' for i in self.vocab if i.startswith(text)]+[None]
                return results[state]
            elif exp in ['add','remove']:
                results=self.completionmatches(text,line,flag=1)+[None]
                return results[state]
            else:
                results=[i+' ' for i in self.vocab if i.startswith(text)]+[None]
                return results[state]

    def do_help(self, arg):
        for plugin in self.options.plugins:
            plugin.do_help(arg)

    def help_help(self):
        self.output("help\t\tPrint a list of available actions")
        self.output("help <action>\tPrint help for <action>")

    def do_EOF(self, arg):
        self.output('')
        return 1

    def help_EOF(self):
        self.output("To quit, type ^D or use the quit command")

def get_names(inst):
    names = []
    classes = [inst.__class__]
    while classes:
        aclass = classes.pop(0)
        if aclass.__bases__:
            classes = classes + list(aclass.__bases__)
        names = names + dir(aclass)
    return names

class ControllerPluginBase:
    name = 'unnamed'

    def __init__(self, controller):
        self.ctl = controller

    def _doc_header(self):
        return "%s commands (type help <topic>):" % self.name
    doc_header = property(_doc_header)

    def do_help(self, arg):
        if arg:
            # XXX check arg syntax
            try:
                func = getattr(self, 'help_' + arg)
            except AttributeError:
                try:
                    doc=getattr(self, 'do_' + arg).__doc__
                    if doc:
                        self.ctl.stdout.write("%s\n"%str(doc))
                        return
                except AttributeError:
                    pass
                self.ctl.stdout.write("%s\n"%str(self.ctl.nohelp % (arg,)))
                return
            func()
        else:
            names = get_names(self)
            cmds_doc = []
            cmds_undoc = []
            help = {}
            for name in names:
                if name[:5] == 'help_':
                    help[name[5:]]=1
            names.sort()
            # There can be duplicates if routines overridden
            prevname = ''
            for name in names:
                if name[:3] == 'do_':
                    if name == prevname:
                        continue
                    prevname = name
                    cmd=name[3:]
                    if cmd in help:
                        cmds_doc.append(cmd)
                        del help[cmd]
                    elif getattr(self, name).__doc__:
                        cmds_doc.append(cmd)
                    else:
                        cmds_undoc.append(cmd)
            self.ctl.stdout.write("\n")
            self.ctl.print_topics(self.doc_header,   cmds_doc,   15,80)

class DefaultControllerPlugin(ControllerPluginBase):
    name = 'default'
    listener = None # for unit tests
    def _tailf(self, path):
        if not self.ctl.upcheck():
            return

        self.ctl.output('==> Press Ctrl-C to exit <==')

        username = self.ctl.options.username
        password = self.ctl.options.password
        try:
            # Python's urllib2 (at least as of Python 2.4.2) isn't up
            # to this task; it doesn't actually implement a proper
            # HTTP/1.1 client that deals with chunked responses (it
            # always sends a Connection: close header).  We use a
            # homegrown client based on asyncore instead.  This makes
            # me sad.
            import http_client
            if self.listener is None:
                listener = http_client.Listener()
            else:
                listener = self.listener # for unit tests
            handler = http_client.HTTPHandler(listener, username, password)
            handler.get(self.ctl.options.serverurl, path)
            asyncore.loop()
        except KeyboardInterrupt:
            handler.close()
            self.ctl.output('')
            return

    def do_tail(self, arg):
        if not self.ctl.upcheck():
            return
        
        args = arg.strip().split()

        if len(args) < 1:
            self.ctl.output('Error: too few arguments')
            self.help_tail()
            return

        elif len(args) > 3:
            self.ctl.output('Error: too many arguments')
            self.help_tail()
            return

        modifier = None

        if args[0].startswith('-'):
            modifier = args.pop(0)

        if len(args) == 1:
            name = args[-1]
            channel = 'stdout'
        else:
            if args:
                name = args[0]
                channel = args[-1].lower()
                if channel not in ('stderr', 'stdout'):
                    self.ctl.output('Error: bad channel %r' % channel)
                    return
            else:
                self.ctl.output('Error: tail requires process name')
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
                    self.ctl.output('Error: bad argument %s' % modifier)
                    return

        supervisor = self.ctl.get_supervisor()

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
                    self.ctl.output(template % (name, 'no log file'))
                elif e.faultCode == xmlrpc.Faults.FAILED:
                    self.ctl.output(template % (name,
                                             'unknown error reading log'))
                elif e.faultCode == xmlrpc.Faults.BAD_NAME:
                    self.ctl.output(template % (name,
                                             'no such process name'))
            else:
                self.ctl.output(output)

    def help_tail(self):
        self.ctl.output(
            "tail [-f] <name> [stdout|stderr] (default stdout)\n"
            "Ex:\n"
            "tail -f <name>\t\tContinuous tail of named process stdout\n"
            "\t\t\tCtrl-C to exit.\n"
            "tail -100 <name>\tlast 100 *bytes* of process stdout\n"
            "tail <name> stderr\tlast 1600 *bytes* of process stderr"
            )

    def do_maintail(self, arg):
        if not self.ctl.upcheck():
            return
        
        args = arg.strip().split()

        if len(args) > 1:
            self.ctl.output('Error: too many arguments')
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
                    self.ctl.output('Error: bad argument %s' % args[0])
                    return
                else:
                    bytes = what
            else:
                self.ctl.output('Error: bad argument %s' % args[0])
                return
            
        else:
            bytes = 1600

        supervisor = self.ctl.get_supervisor()

        try:
            output = supervisor.readLog(-bytes, 0)
        except xmlrpclib.Fault, e:
            template = '%s: ERROR (%s)'
            if e.faultCode == xmlrpc.Faults.NO_FILE:
                self.ctl.output(template % ('supervisord', 'no log file'))
            elif e.faultCode == xmlrpc.Faults.FAILED:
                self.ctl.output(template % ('supervisord',
                                         'unknown error reading log'))
        else:
            self.ctl.output(output)

    def help_maintail(self):
        self.ctl.output(
            "maintail -f \tContinuous tail of supervisor main log file"
            " (Ctrl-C to exit)\n"
            "maintail -100\tlast 100 *bytes* of supervisord main log file\n"
            "maintail\tlast 1600 *bytes* of supervisor main log file\n"
            )

    def do_quit(self, arg):
        sys.exit(0)

    def help_quit(self):
        self.ctl.output("quit\tExit the supervisor shell.")

    do_exit = do_quit

    def help_exit(self):
        self.ctl.output("exit\tExit the supervisor shell.")

    def _procrepr(self, info):
        template = '%(name)-32s %(state)-10s %(desc)s'
        if info['name'] == info['group']:
            name = info['name']
        else:
            name = '%s:%s' % (info['group'], info['name'])
                    
        return template % {'name':name, 'state':info['statename'],
                           'desc':info['description']}

    def do_status(self, arg):
        if not self.ctl.upcheck():
            return
        
        supervisor = self.ctl.get_supervisor()

        names = arg.strip().split()

        if names:
            for name in names:
                try:
                    info = supervisor.getProcessInfo(name)
                except xmlrpclib.Fault, e:
                    if e.faultCode == xmlrpc.Faults.BAD_NAME:
                        self.ctl.output('No such process %s' % name)
                    else:
                        raise
                    continue
                self.ctl.output(self._procrepr(info))
        else:
            for info in supervisor.getAllProcessInfo():
                self.ctl.output(self._procrepr(info))

    def help_status(self):
        self.ctl.output("status\t\t\tGet all process status info.")
        self.ctl.output(
            "status <name>\t\tGet status on a single process by name.")
        self.ctl.output("status <name> <name>\tGet status on multiple named "
                     "processes.")

    def do_pid(self, arg):
        supervisor = self.ctl.get_supervisor()
        pid = supervisor.getPID()
        self.ctl.output(str(pid))

    def help_pid(self):
        self.ctl.output("pid\t\t\tGet the PID of supervisord.")    

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
        if not self.ctl.upcheck():
            return

        names = arg.strip().split()
        supervisor = self.ctl.get_supervisor()

        if not names:
            self.ctl.output("Error: start requires a process name")
            self.help_start()
            return

        if 'all' in names:
            results = supervisor.startAllProcesses()
            for result in results:
                result = self._startresult(result)
                self.ctl.output(result)
                
        else:
            for name in names:
                group_name, process_name = split_namespec(name)
                if process_name is None:
                    results = supervisor.startProcessGroup(group_name)
                    for result in results:
                        result = self._startresult(result)
                        self.ctl.output(result)
                else:
                    try:
                        result = supervisor.startProcess(name)
                    except xmlrpclib.Fault, e:
                        error = self._startresult({'status':e.faultCode,
                                                   'name':name,
                                                   'description':e.faultString})
                        self.ctl.output(error)
                    else:
                        self.ctl.output('%s: started' % name)

    def help_start(self):
        self.ctl.output("start <name>\t\tStart a process")
        self.ctl.output("start <gname>:*\t\tStart all processes in a group")
        self.ctl.output(
            "start <name> <name>\tStart multiple processes or groups")
        self.ctl.output("start all\t\tStart all processes")

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
        if not self.ctl.upcheck():
            return

        names = arg.strip().split()
        supervisor = self.ctl.get_supervisor()

        if not names:
            self.ctl.output('Error: stop requires a process name')
            self.help_stop()
            return

        if 'all' in names:
            results = supervisor.stopAllProcesses()
            for result in results:
                result = self._stopresult(result)
                self.ctl.output(result)

        else:
            for name in names:
                group_name, process_name = split_namespec(name)
                if process_name is None:
                    results = supervisor.stopProcessGroup(group_name)
                    for result in results:
                        result = self._stopresult(result)
                        self.ctl.output(result)
                else:
                    try:
                        result = supervisor.stopProcess(name)
                    except xmlrpclib.Fault, e:
                        error = self._stopresult({'status':e.faultCode,
                                                  'name':name,
                                                  'description':e.faultString})
                        self.ctl.output(error)
                    else:
                        self.ctl.output('%s: stopped' % name)

    def help_stop(self):
        self.ctl.output("stop <name>\t\tStop a process")
        self.ctl.output("stop <gname>:*\t\tStop all processes in a group")
        self.ctl.output("stop <name> <name>\tStop multiple processes or groups")
        self.ctl.output("stop all\t\tStop all processes")

    def do_restart(self, arg):
        if not self.ctl.upcheck():
            return

        names = arg.strip().split()

        if not names:
            self.ctl.output('Error: restart requires a process name')
            self.help_restart()
            return

        self.do_stop(arg)
        self.do_start(arg)

    def help_restart(self):
        self.ctl.output("restart <name>\t\tRestart a process")
        self.ctl.output("restart <gname>:*\tRestart all processes in a group")
        self.ctl.output("restart <name> <name>\tRestart multiple processes or "
                     "groups")
        self.ctl.output("restart all\t\tRestart all processes")

    def do_shutdown(self, arg):
        if self.ctl.options.interactive:
            yesno = raw_input('Really shut the remote supervisord process '
                              'down y/N? ')
            really = yesno.lower().startswith('y')
        else:
            really = 1
        if really:
            supervisor = self.ctl.get_supervisor()
            try:
                supervisor.shutdown()
            except xmlrpclib.Fault, e:
                if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                    self.ctl.output('ERROR: already shutting down')
            else:
                self.ctl.output('Shut down')

    def help_shutdown(self):
        self.ctl.output("shutdown \tShut the remote supervisord down.")

    def do_reload(self, arg):
        if self.ctl.options.interactive:
            yesno = raw_input('Really restart the remote supervisord process '
                              'y/N? ')
            really = yesno.lower().startswith('y')
        else:
            really = 1
        if really:
            supervisor = self.ctl.get_supervisor()
            try:
                supervisor.restart()
            except xmlrpclib.Fault, e:
                if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                    self.ctl.output('ERROR: already shutting down')
            else:
                self.ctl.output('Restarted supervisord')

    def help_reload(self):
        self.ctl.output("reload \t\tRestart the remote supervisord.")

    def do_add(self, arg):
        names = arg.strip().split()

        supervisor = self.ctl.get_supervisor()
        for name in names:
            try:
                supervisor.addProcess(name)
            except xmlrpclib.Fault, e:
                if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                    self.ctl.output('ERROR: shutting down')
                elif e.faultCode == xmlrpc.Faults.ALREADY_ADDED:
                    self.ctl.output('ERROR: process group already active')
                elif e.faultCode == xmlrpc.Faults.BAD_NAME:
                    self.ctl.output(
                        "ERROR: no such process/group: %s" % name)
                else:
                    raise
            else:
                self.ctl.output("%s: added process group" % name)

    def help_add(self):
        self.ctl.output("add <name> [...]\tActivates any updates in config "
                        "for process/group")

    def do_remove(self, arg):
        names = arg.strip().split()

        supervisor = self.ctl.get_supervisor()
        for name in names:
            try:
                result = supervisor.removeProcess(name)
            except xmlrpclib.Fault, e:
                if e.faultCode == xmlrpc.Faults.STILL_RUNNING:
                    self.ctl.output('ERROR: process/group still running: %s'
                                    % name)
                elif e.faultCode == xmlrpc.Faults.BAD_NAME:
                    self.ctl.output(
                        "ERROR: no such process/group: %s" % name)
                else:
                    raise
            else:
                self.ctl.output("%s: removed" % name)

    def help_remove(self):
        self.ctl.output("remove <name> [...]\tRemoves process/group from "
                        "active config")

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
        if not self.ctl.upcheck():
            return

        names = arg.strip().split()

        if not names:
            self.ctl.output('Error: clear requires a process name')
            self.help_clear()
            return

        supervisor = self.ctl.get_supervisor()

        if 'all' in names:
            results = supervisor.clearAllProcessLogs()
            for result in results:
                result = self._clearresult(result)
                self.ctl.output(result)

        else:

            for name in names:
                try:
                    result = supervisor.clearProcessLogs(name)
                except xmlrpclib.Fault, e:
                    error = self._clearresult({'status':e.faultCode,
                                               'name':name,
                                               'description':e.faultString})
                    self.ctl.output(error)
                else:
                    self.ctl.output('%s: cleared' % name)

    def help_clear(self):
        self.ctl.output("clear <name>\t\tClear a process' log files.")
        self.ctl.output(
            "clear <name> <name>\tClear multiple process' log files")
        self.ctl.output("clear all\t\tClear all process' log files")

    def do_open(self, arg):
        url = arg.strip()
        parts = urlparse.urlparse(url)
        if parts[0] not in ('unix', 'http'):
            self.ctl.output('ERROR: url must be http:// or unix://')
            return
        self.ctl.options.serverurl = url
        self.do_status('')

    def help_open(self):
        self.ctl.output("open <url>\tConnect to a remote supervisord process.")
        self.ctl.output("\t\t(for UNIX domain socket, use unix:///socket/path)")

    def do_version(self, arg):
        if not self.ctl.upcheck():
            return
        supervisor = self.ctl.get_supervisor()
        self.ctl.output(supervisor.getSupervisorVersion())

    def help_version(self):
        self.ctl.output(
            "version\t\t\tShow the version of the remote supervisord "
            "process")

    def do_fg(self,args=None):
        if not self.ctl.upcheck():
            return
        if not args:
            self.ctl.output('Error: no process name supplied')
            self.help_fg()
            return
        args=args.split()
        if len(args)>1:
            self.ctl.output('Error: too many process names supplied')
            return
        program=args[0]
        supervisor=self.ctl.get_supervisor()
        try:
            info=supervisor.getProcessInfo(program)
        except xmlrpclib.Fault, msg:
            if msg.faultCode == xmlrpc.Faults.BAD_NAME:
                self.ctl.output('Error: bad process name supplied')
                return
            # for any other fault
            self.ctl.output(str(msg))
            return
        if not info['statename'] == 'RUNNING':
            self.ctl.output('Error: process not running')
            return
        # everything good; continue
        try:
            a=fgthread(program,self.ctl)
            # this thread takes care of
            # the output/error messages
            a.start()
            while True:
                # this takes care of the user input
                inp = raw_input() + '\n'
                try:
                    supervisor.sendProcessStdin(program,inp)
                except xmlrpclib.Fault, msg:
                    if msg.faultCode == 70:
                        self.ctl.output('Process got killed')
                        self.ctl.output('Exiting foreground')
                        a.kill()
                        return
                info = supervisor.getProcessInfo(program)
                if not info['statename'] == 'RUNNING':
                    self.ctl.output('Process got killed')
                    self.ctl.output('Exiting foreground')
                    a.kill()
                    return
                continue
        except KeyboardInterrupt:
            a.kill()
            self.ctl.output('Exiting foreground')
        return

    def help_fg(self,args=None):
        self.ctl.output('fg <process>\tConnect to a process in foreground mode')
        self.ctl.output('Press Ctrl+C to exit foreground')

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
            if options.history_file:
                try:
                    readline.read_history_file(options.history_file)
                except IOError:
                    pass
                def save():
                    try:
                        readline.write_history_file(options.history_file)
                    except IOError:
                        pass
                import atexit
                atexit.register(save)
        except ImportError:
            pass
        try:
            c.cmdqueue.append('status')
            c.cmdloop()
        except KeyboardInterrupt:
            c.output('')
            pass

if __name__ == "__main__":
    main()
