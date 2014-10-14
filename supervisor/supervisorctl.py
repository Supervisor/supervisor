#!/usr/bin/env python -u

"""supervisorctl -- control applications run by supervisord from the cmd line.

Usage: %s [options] [action [arguments]]

Options:
-c/--configuration -- configuration file path (default /etc/supervisord.conf)
-h/--help -- print usage message and exit
-i/--interactive -- start an interactive shell after executing commands
-s/--serverurl URL -- URL on which supervisord server is listening
     (default "http://localhost:9001").
-u/--username -- username to use for authentication with server
-p/--password -- password to use for authentication with server
-r/--history-file -- keep a readline history (if readline is available)

action [arguments] -- see below

Actions are commands like "tail" or "stop".  If -i is specified or no action is
specified on the command line, a "shell" interpreting actions typed
interactively is started.  Use the action "help" to find out about available
actions.
"""

import cmd
import sys
import getpass

import supervisor.medusa.text_socket as socket
import errno
import threading

from supervisor.compat import xmlrpclib
from supervisor.compat import urlparse
from supervisor.compat import unicode
from supervisor.compat import raw_input

from supervisor.medusa import asyncore_25 as asyncore

from supervisor.options import ClientOptions
from supervisor.options import make_namespec
from supervisor.options import split_namespec
from supervisor import xmlrpc
from supervisor import states

class fgthread(threading.Thread):
    """ A subclass of threading.Thread, with a kill() method.
    To be used for foreground output/error streaming.
    http://mail.python.org/pipermail/python-list/2004-May/260937.html
    """

    def __init__(self, program, ctl):
        threading.Thread.__init__(self)
        import supervisor.http_client as http_client
        self.killed = False
        self.program = program
        self.ctl = ctl
        self.listener = http_client.Listener()
        self.output_handler = http_client.HTTPHandler(self.listener,
                                                      self.ctl.options.username,
                                                      self.ctl.options.password)
        self.error_handler = http_client.HTTPHandler(self.listener,
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
        self.vocab = ['help']
        self._complete_info = None
        cmd.Cmd.__init__(self, completekey, stdin, stdout)
        for name, factory, kwargs in self.options.plugin_factories:
            plugin = factory(self, **kwargs)
            for a in dir(plugin):
                if a.startswith('do_') and callable(getattr(plugin, a)):
                    self.vocab.append(a[3:])
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
        self._complete_info = None
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
                except xmlrpclib.ProtocolError as e:
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
            except Exception:
                (file, fun, line), t, v, tbinfo = asyncore.compact_traceback()
                error = 'error: %s, %s: file: %s line: %s' % (t, v, file, line)
                self.output(error)
                if not self.options.interactive:
                    sys.exit(2)

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
            if isinstance(stuff, unicode):
                stuff = stuff.encode('utf-8')
            self.stdout.write(stuff + '\n')

    def get_supervisor(self):
        return self.get_server_proxy('supervisor')

    def get_server_proxy(self, namespace=None):
        proxy = self.options.getServerProxy()
        if namespace is None:
            return proxy
        else:
            return getattr(proxy, namespace)

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
        except xmlrpclib.Fault as e:
            if e.faultCode == xmlrpc.Faults.UNKNOWN_METHOD:
                self.output(
                    'Sorry, supervisord responded but did not recognize '
                    'the supervisor namespace commands that supervisorctl '
                    'uses to control it.  Please check that the '
                    '[rpcinterface:supervisor] section is enabled in the '
                    'configuration file (see sample.conf).')
                return False
            raise
        except socket.error as why:
            if why.args[0] == errno.ECONNREFUSED:
                self.output('%s refused connection' % self.options.serverurl)
                return False
            elif why.args[0] == errno.ENOENT:
                self.output('%s no such file' % self.options.serverurl)
                return False
            raise
        return True

    def complete(self, text, state, line=None):
        """Completer function that Cmd will register with readline using
        readline.set_completer().  This function will be called by readline
        as complete(text, state) where text is a fragment to complete and
        state is an integer (0..n).  Each call returns a string with a new
        completion.  When no more are available, None is returned."""
        if line is None: # line is only set in tests
            import readline
            line = readline.get_line_buffer()

        # take the last phrase from a line like "stop foo; start bar"
        phrase = line.split(';')[-1]

        matches = []
        # blank phrase completes to action list
        if not phrase.strip():
            matches = self._complete_actions(text)
        else:
            words = phrase.split()
            action = words[0]
            # incomplete action completes to action list
            if len(words) == 1 and not phrase.endswith(' '):
                matches = self._complete_actions(text)
            # actions that accept an action name
            elif action in ('help'):
                matches = self._complete_actions(text)
            # actions that accept a group name
            elif action in ('add', 'remove', 'update'):
                matches = self._complete_groups(text)
            # actions that accept a process name
            elif action in ('clear', 'fg', 'pid', 'restart', 'signal',
                            'start', 'status', 'stop', 'tail'):
                matches = self._complete_processes(text)
        if len(matches) > state:
            return matches[state]

    def _complete_actions(self, text):
        """Build a completion list of action names matching text"""
        return [ a + ' ' for a in self.vocab if a.startswith(text)]

    def _complete_groups(self, text):
        """Build a completion list of group names matching text"""
        groups = []
        for info in self._get_complete_info():
            if info['group'] not in groups:
                groups.append(info['group'])
        return [ g + ' ' for g in groups if g.startswith(text) ]

    def _complete_processes(self, text):
        """Build a completion list of process names matching text"""
        processes = []
        for info in self._get_complete_info():
            if ':' in text or info['name'] != info['group']:
                processes.append('%s:%s' % (info['group'], info['name']))
                if '%s:*' % info['group'] not in processes:
                    processes.append('%s:*' % info['group'])
            else:
                processes.append(info['name'])
        return [ p + ' ' for p in processes if p.startswith(text) ]

    def _get_complete_info(self):
        """Get all process info used for completion.  We cache this between
        commands to reduce XML-RPC calls because readline may call
        complete() many times if the user hits tab only once."""
        if self._complete_info is None:
            self._complete_info = self.get_supervisor().getAllProcessInfo()
        return self._complete_info

    def do_help(self, arg):
        if arg.strip() == 'help':
            self.help_help()
        else:
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
                    doc = getattr(self, 'do_' + arg).__doc__
                    if doc:
                        self.ctl.output(doc)
                        return
                except AttributeError:
                    pass
                self.ctl.output(self.ctl.nohelp % (arg,))
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
            self.ctl.output('')
            self.ctl.print_topics(self.doc_header, cmds_doc, 15, 80)

class DefaultControllerPlugin(ControllerPluginBase):
    name = 'default'
    listener = None # for unit tests
    def _tailf(self, path):
        self.ctl.output('==> Press Ctrl-C to exit <==')

        username = self.ctl.options.username
        password = self.ctl.options.password
        handler = None
        try:
            # Python's urllib2 (at least as of Python 2.4.2) isn't up
            # to this task; it doesn't actually implement a proper
            # HTTP/1.1 client that deals with chunked responses (it
            # always sends a Connection: close header).  We use a
            # homegrown client based on asyncore instead.  This makes
            # me sad.
            import supervisor.http_client as http_client
            if self.listener is None:
                listener = http_client.Listener()
            else:
                listener = self.listener # for unit tests
            handler = http_client.HTTPHandler(listener, username, password)
            handler.get(self.ctl.options.serverurl, path)
            asyncore.loop()
        except KeyboardInterrupt:
            if handler:
                handler.close()
            self.ctl.output('')
            return

    def do_tail(self, arg):
        if not self.ctl.upcheck():
            return

        args = arg.split()

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
            except xmlrpclib.Fault as e:
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
                    raise
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

        args = arg.split()

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
        except xmlrpclib.Fault as e:
            template = '%s: ERROR (%s)'
            if e.faultCode == xmlrpc.Faults.NO_FILE:
                self.ctl.output(template % ('supervisord', 'no log file'))
            elif e.faultCode == xmlrpc.Faults.FAILED:
                self.ctl.output(template % ('supervisord',
                                         'unknown error reading log'))
            else:
                raise
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

    def _show_statuses(self, process_infos):
        namespecs, maxlen = [], 30
        for i, info in enumerate(process_infos):
            namespecs.append(make_namespec(info['group'], info['name']))
            if len(namespecs[i]) > maxlen:
                maxlen = len(namespecs[i])

        template = '%(namespec)-' + str(maxlen+3) + 's%(state)-10s%(desc)s'
        for i, info in enumerate(process_infos):
            line = template % {'namespec': namespecs[i],
                               'state': info['statename'],
                               'desc': info['description']}
            self.ctl.output(line)

    def do_status(self, arg):
        if not self.ctl.upcheck():
            return

        supervisor = self.ctl.get_supervisor()
        all_infos = supervisor.getAllProcessInfo()

        names = arg.split()
        if not names or "all" in names:
            matching_infos = all_infos
        else:
            matching_infos = []

            for name in names:
                bad_name = True
                group_name, process_name = split_namespec(name)

                for info in all_infos:
                    matched = info['group'] == group_name
                    if process_name is not None:
                        matched = matched and info['name'] == process_name

                    if matched:
                        bad_name = False
                        matching_infos.append(info)

                if bad_name:
                    if process_name is None:
                        msg = "%s: ERROR (no such group)" % group_name
                    else:
                        msg = "%s: ERROR (no such process)" % name
                    self.ctl.output(msg)
        self._show_statuses(matching_infos)

    def help_status(self):
        self.ctl.output("status <name>\t\tGet status for a single process")
        self.ctl.output("status <gname>:*\tGet status for all "
                        "processes in a group")
        self.ctl.output("status <name> <name>\tGet status for multiple named "
                        "processes")
        self.ctl.output("status\t\t\tGet all process status info")

    def do_pid(self, arg):
        supervisor = self.ctl.get_supervisor()
        if not self.ctl.upcheck():
            return
        names = arg.split()
        if not names:
            pid = supervisor.getPID()
            self.ctl.output(str(pid))
        elif 'all' in names:
            for info in supervisor.getAllProcessInfo():
                self.ctl.output(str(info['pid']))
        else:
            for name in names:
                try:
                    info = supervisor.getProcessInfo(name)
                except xmlrpclib.Fault as e:
                    if e.faultCode == xmlrpc.Faults.BAD_NAME:
                        self.ctl.output('No such process %s' % name)
                    else:
                        raise
                else:
                    self.ctl.output(str(info['pid']))

    def help_pid(self):
        self.ctl.output("pid\t\t\tGet the PID of supervisord.")
        self.ctl.output("pid <name>\t\tGet the PID of a single "
            "child process by name.")
        self.ctl.output("pid all\t\t\tGet the PID of every child "
            "process, one per line.")

    def _startresult(self, result):
        name = make_namespec(result['group'], result['name'])
        code = result['status']
        template = '%s: ERROR (%s)'
        if code == xmlrpc.Faults.BAD_NAME:
            return template % (name, 'no such process')
        elif code == xmlrpc.Faults.NO_FILE:
            return template % (name, 'no such file')
        elif code == xmlrpc.Faults.NOT_EXECUTABLE:
            return template % (name, 'file is not executable')
        elif code == xmlrpc.Faults.ALREADY_STARTED:
            return template % (name, 'already started')
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

        names = arg.split()
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
                    try:
                        results = supervisor.startProcessGroup(group_name)
                        for result in results:
                            result = self._startresult(result)
                            self.ctl.output(result)
                    except xmlrpclib.Fault as e:
                        if e.faultCode == xmlrpc.Faults.BAD_NAME:
                            error = "%s: ERROR (no such group)" % group_name
                            self.ctl.output(error)
                        else:
                            raise
                else:
                    try:
                        result = supervisor.startProcess(name)
                    except xmlrpclib.Fault as e:
                        error = self._startresult({'status': e.faultCode,
                                                   'name': process_name,
                                                   'group': group_name,
                                                   'description': e.faultString})
                        self.ctl.output(error)
                    else:
                        name = make_namespec(group_name, process_name)
                        self.ctl.output('%s: started' % name)

    def help_start(self):
        self.ctl.output("start <name>\t\tStart a process")
        self.ctl.output("start <gname>:*\t\tStart all processes in a group")
        self.ctl.output(
            "start <name> <name>\tStart multiple processes or groups")
        self.ctl.output("start all\t\tStart all processes")

    def _signalresult(self, result, success='signalled'):
        name = make_namespec(result['group'], result['name'])
        code = result['status']
        fault_string = result['description']
        template = '%s: ERROR (%s)'
        if code == xmlrpc.Faults.BAD_NAME:
            return template % (name, 'no such process')
        elif code == xmlrpc.Faults.BAD_SIGNAL:
            return template % (name, 'bad signal name')
        elif code == xmlrpc.Faults.NOT_RUNNING:
            return template % (name, 'not running')
        elif code == xmlrpc.Faults.SUCCESS:
            return '%s: %s' % (name, success)
        elif code == xmlrpc.Faults.FAILED:
            return fault_string
        # assertion
        raise ValueError('Unknown result code %s for %s' % (code, name))

    def _stopresult(self, result):
        return self._signalresult(result, success='stopped')

    def do_stop(self, arg):
        if not self.ctl.upcheck():
            return

        names = arg.split()
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
                    try:
                        results = supervisor.stopProcessGroup(group_name)
                        for result in results:
                            result = self._stopresult(result)
                            self.ctl.output(result)
                    except xmlrpclib.Fault as e:
                        if e.faultCode == xmlrpc.Faults.BAD_NAME:
                            error = "%s: ERROR (no such group)" % group_name
                            self.ctl.output(error)
                        else:
                            raise
                else:
                    try:
                        supervisor.stopProcess(name)
                    except xmlrpclib.Fault as e:
                        error = self._stopresult({'status': e.faultCode,
                                                  'name': process_name,
                                                  'group': group_name,
                                                  'description':e.faultString})
                        self.ctl.output(error)
                    else:
                        name = make_namespec(group_name, process_name)
                        self.ctl.output('%s: stopped' % name)

    def help_stop(self):
        self.ctl.output("stop <name>\t\tStop a process")
        self.ctl.output("stop <gname>:*\t\tStop all processes in a group")
        self.ctl.output("stop <name> <name>\tStop multiple processes or groups")
        self.ctl.output("stop all\t\tStop all processes")

    def do_signal(self, arg):
        if not self.ctl.upcheck():
            return

        args = arg.split()
        if len(args) < 2:
            self.ctl.output(
                'Error: signal requires a signal name and a process name')
            self.help_signal()
            return

        sig = args[0]
        names = args[1:]
        supervisor = self.ctl.get_supervisor()

        if 'all' in names:
            results = supervisor.signalAllProcesses(sig)
            for result in results:
                result = self._signalresult(result)
                self.ctl.output(result)

        else:
            for name in names:
                group_name, process_name = split_namespec(name)
                if process_name is None:
                    try:
                        results = supervisor.signalProcessGroup(
                            group_name, sig
                            )
                        for result in results:
                            result = self._signalresult(result)
                            self.ctl.output(result)
                    except xmlrpclib.Fault as e:
                        if e.faultCode == xmlrpc.Faults.BAD_NAME:
                            error = "%s: ERROR (no such group)" % group_name
                            self.ctl.output(error)
                        else:
                            raise
                else:
                    try:
                        supervisor.signalProcess(name, sig)
                    except xmlrpclib.Fault as e:
                        error = self._signalresult({'status': e.faultCode,
                                                    'name': process_name,
                                                    'group': group_name,
                                                    'description':e.faultString})
                        self.ctl.output(error)
                    else:
                        name = make_namespec(group_name, process_name)
                        self.ctl.output('%s: signalled' % name)

    def help_signal(self):
        self.ctl.output("signal <signal name> <name>\t\tSignal a process")
        self.ctl.output("signal <signal name> <gname>:*\t\tSignal all processes in a group")
        self.ctl.output("signal <signal name> <name> <name>\tSignal multiple processes or groups")
        self.ctl.output("signal <signal name> all\t\tSignal all processes")

    def do_restart(self, arg):
        if not self.ctl.upcheck():
            return

        names = arg.split()

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
        self.ctl.output("Note: restart does not reread config files. For that,"
                        " see reread and update.")

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
            except xmlrpclib.Fault as e:
                if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                    self.ctl.output('ERROR: already shutting down')
                else:
                    raise
            except socket.error as e:
                if e.args[0] == errno.ECONNREFUSED:
                    msg = 'ERROR: %s refused connection (already shut down?)'
                    self.ctl.output(msg % self.ctl.options.serverurl)
                elif e.args[0] == errno.ENOENT:
                    msg = 'ERROR: %s no such file (already shut down?)'
                    self.ctl.output(msg % self.ctl.options.serverurl)
                else:
                    raise
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
            except xmlrpclib.Fault as e:
                if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                    self.ctl.output('ERROR: already shutting down')
                else:
                    raise
            else:
                self.ctl.output('Restarted supervisord')

    def help_reload(self):
        self.ctl.output("reload \t\tRestart the remote supervisord.")

    def _formatChanges(self, added_changed_dropped_tuple):
        added, changed, dropped = added_changed_dropped_tuple
        changedict = {}
        for n, t in [(added, 'available'),
                     (changed, 'changed'),
                     (dropped, 'disappeared')]:
            changedict.update(dict(zip(n, [t] * len(n))))

        if changedict:
            names = list(changedict.keys())
            names.sort()
            for name in names:
                self.ctl.output("%s: %s" % (name, changedict[name]))
        else:
            self.ctl.output("No config updates to processes")

    def _formatConfigInfo(self, configinfo):
        name = make_namespec(configinfo['group'], configinfo['name'])
        formatted = { 'name': name }
        if configinfo['inuse']:
            formatted['inuse'] = 'in use'
        else:
            formatted['inuse'] = 'avail'
        if configinfo['autostart']:
            formatted['autostart'] = 'auto'
        else:
            formatted['autostart'] = 'manual'
        formatted['priority'] = "%s:%s" % (configinfo['group_prio'],
                                           configinfo['process_prio'])

        template = '%(name)-32s %(inuse)-9s %(autostart)-9s %(priority)s'
        return template % formatted

    def do_avail(self, arg):
        supervisor = self.ctl.get_supervisor()
        try:
            configinfo = supervisor.getAllConfigInfo()
        except xmlrpclib.Fault as e:
            if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                self.ctl.output('ERROR: supervisor shutting down')
            else:
                raise
        else:
            for pinfo in configinfo:
                self.ctl.output(self._formatConfigInfo(pinfo))

    def help_avail(self):
        self.ctl.output("avail\t\t\tDisplay all configured processes")

    def do_reread(self, arg):
        supervisor = self.ctl.get_supervisor()
        try:
            result = supervisor.reloadConfig()
        except xmlrpclib.Fault as e:
            if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                self.ctl.output('ERROR: supervisor shutting down')
            elif e.faultCode == xmlrpc.Faults.CANT_REREAD:
                self.ctl.output('ERROR: %s' % e.faultString)
            else:
                raise
        else:
            self._formatChanges(result[0])

    def help_reread(self):
        self.ctl.output("reread \t\t\tReload the daemon's configuration files")

    def do_add(self, arg):
        names = arg.split()

        supervisor = self.ctl.get_supervisor()
        for name in names:
            try:
                supervisor.addProcessGroup(name)
            except xmlrpclib.Fault as e:
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
        names = arg.split()

        supervisor = self.ctl.get_supervisor()
        for name in names:
            try:
                supervisor.removeProcessGroup(name)
            except xmlrpclib.Fault as e:
                if e.faultCode == xmlrpc.Faults.STILL_RUNNING:
                    self.ctl.output('ERROR: process/group still running: %s'
                                    % name)
                elif e.faultCode == xmlrpc.Faults.BAD_NAME:
                    self.ctl.output(
                        "ERROR: no such process/group: %s" % name)
                else:
                    raise
            else:
                self.ctl.output("%s: removed process group" % name)

    def help_remove(self):
        self.ctl.output("remove <name> [...]\tRemoves process/group from "
                        "active config")

    def do_update(self, arg):
        def log(name, message):
            self.ctl.output("%s: %s" % (name, message))

        supervisor = self.ctl.get_supervisor()
        try:
            result = supervisor.reloadConfig()
        except xmlrpclib.Fault as e:
            if e.faultCode == xmlrpc.Faults.SHUTDOWN_STATE:
                self.ctl.output('ERROR: already shutting down')
                return
            else:
                raise

        added, changed, removed = result[0]
        valid_gnames = set(arg.split())

        # If all is specified treat it as if nothing was specified.
        if "all" in valid_gnames:
            valid_gnames = set()

        # If any gnames are specified we need to verify that they are
        # valid in order to print a useful error message.
        if valid_gnames:
            groups = set()
            for info in supervisor.getAllProcessInfo():
                groups.add(info['group'])
            # New gnames would not currently exist in this set so
            # add those as well.
            groups.update(added)

            for gname in valid_gnames:
                if gname not in groups:
                    self.ctl.output('ERROR: no such group: %s' % gname)

        for gname in removed:
            if valid_gnames and gname not in valid_gnames:
                continue
            results = supervisor.stopProcessGroup(gname)
            log(gname, "stopped")

            fails = [res for res in results
                     if res['status'] == xmlrpc.Faults.FAILED]
            if fails:
                log(gname, "has problems; not removing")
                continue
            supervisor.removeProcessGroup(gname)
            log(gname, "removed process group")

        for gname in changed:
            if valid_gnames and gname not in valid_gnames:
                continue
            supervisor.stopProcessGroup(gname)
            log(gname, "stopped")

            supervisor.removeProcessGroup(gname)
            supervisor.addProcessGroup(gname)
            log(gname, "updated process group")

        for gname in added:
            if valid_gnames and gname not in valid_gnames:
                continue
            supervisor.addProcessGroup(gname)
            log(gname, "added process group")

    def help_update(self):
        self.ctl.output("update\t\t\tReload config and add/remove as necessary")
        self.ctl.output("update all\t\tReload config and add/remove as necessary")
        self.ctl.output("update <gname> [...]\tUpdate specific groups")

    def _clearresult(self, result):
        name = make_namespec(result['group'], result['name'])
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

        names = arg.split()

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
                group_name, process_name = split_namespec(name)
                try:
                    supervisor.clearProcessLogs(name)
                except xmlrpclib.Fault as e:
                    error = self._clearresult({'status': e.faultCode,
                                               'name': process_name,
                                               'group': group_name,
                                               'description': e.faultString})
                    self.ctl.output(error)
                else:
                    name = make_namespec(group_name, process_name)
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
        args = args.split()
        if len(args) > 1:
            self.ctl.output('Error: too many process names supplied')
            return
        program = args[0]
        supervisor = self.ctl.get_supervisor()
        try:
            info = supervisor.getProcessInfo(program)
        except xmlrpclib.Fault as msg:
            if msg.faultCode == xmlrpc.Faults.BAD_NAME:
                self.ctl.output('Error: bad process name supplied')
                return
            # for any other fault
            self.ctl.output(str(msg))
            return
        if not info['state'] == states.ProcessStates.RUNNING:
            self.ctl.output('Error: process not running')
            return
        # everything good; continue
        a = None
        try:
            a = fgthread(program,self.ctl)
            # this thread takes care of
            # the output/error messages
            a.start()
            while True:
                # this takes care of the user input
                inp = raw_input() + '\n'
                try:
                    supervisor.sendProcessStdin(program, inp)
                except xmlrpclib.Fault as msg:
                    if msg.faultCode == xmlrpc.Faults.NOT_RUNNING:
                        self.ctl.output('Process got killed')
                        self.ctl.output('Exiting foreground')
                        a.kill()
                        return
                info = supervisor.getProcessInfo(program)
                if not info['state'] == states.ProcessStates.RUNNING:
                    self.ctl.output('Process got killed')
                    self.ctl.output('Exiting foreground')
                    a.kill()
                    return
                continue
        except (KeyboardInterrupt, EOFError):
            if a:
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
            delims = readline.get_completer_delims()
            delims = delims.replace(':', '') # "group:process" as one word
            delims = delims.replace('*', '') # "group:*" as one word
            delims = delims.replace('-', '') # names with "-" as one word
            readline.set_completer_delims(delims)

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
