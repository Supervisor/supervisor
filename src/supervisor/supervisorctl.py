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
import httplib
import fcntl
import socket
import pprint
import asyncore
import errno
import time
import datetime

class ZDCmd(cmd.Cmd):

    def __init__(self, options):
        self.options = options
        self.prompt = self.options.prompt + '> '
        cmd.Cmd.__init__(self)

    def emptyline(self):
        # We don't want a blank line to repeat the last command.
        return

    def onecmd(self, line):
        """ Override the onecmd method to catch and print all exceptions
        """
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
                return func(arg)
            except Exception, e:
                (file, fun, line), t, v, tbinfo = asyncore.compact_traceback()
                error = 'error: %s, %s: file: %s line: %s' % (t, v, file, line)
                self._output(error)

    def _output(self, stuff):
        if stuff is not None:
            print stuff

    def _getServerProxy(self):
        return xmlrpclib.ServerProxy(
            self.options.serverurl,
            transport = BasicAuthTransport(self.options.username,
                                           self.options.password))

    def _makeNamespace(self, namespace):
        proxy = self._getServerProxy()
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
        print "help\t\tPrint a list of available actions."
        print "help <action>\tPrint help for <action>."

    def do_EOF(self, arg):
        print
        return 1

    def help_EOF(self):
        print "To quit, type ^D or use the quit command."

    def do_tailf(self, arg):
        if not self._upcheck():
            return

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
            return

    def help_tailf(self):
        print ("tailf <processname>\tContinuous tail of named process stdout, "
               "Ctrl-C to exit.")

    def do_quit(self, arg):
        sys.exit(0)

    def help_quit(self):
        print "quit\tExit the supervisor shell."

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
                desc = 'unknown error (try "tailf %s")' % info['name']

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
                info = supervisor.getProcessInfo(processname)
                newinfo = self._interpretProcessInfo(info)
                self._output(template % newinfo)
        else:
            for info in supervisor.getAllProcessInfo():
                newinfo = self._interpretProcessInfo(info)
                self._output(template % newinfo)

    def help_status(self):
        print "status\t\t\tGet all process status info."
        print "status <name>\t\tGet status on a single process by name."
        print "status <name> <name>\tGet status on multiple named processes."

    def do_start(self, arg):
        if not self._upcheck():
            return

        processnames = arg.strip().split()
        supervisor = self._get_supervisor()
        if not processnames:
            print "You must provide a process name (see 'help start')"
            return
        if 'all' in processnames:
            self._output(supervisor.startAllProcesses())
        else:
            for processname in processnames:
                try:
                    self._output(supervisor.startProcess(processname))
                except xmlrpclib.Fault, e:
                    template = 'Cannot start %s (%s)'
                    if e.faultCode == rpc.FAULTS['START_BAD_NAME']:
                        self._output(template % (processname,'no such process'))
                    elif e.faultCode == rpc.FAULTS['START_ALREADY_STARTED']:
                        self._output(template % (processname,'already started'))
                    else:
                        raise

    def help_start(self):
        print "start <processname>\t\t\tStart a process."
        print "start <processname> <processname>\tStart multiple processes"
        print "start all\t\t\t\tStart all processes"
        print "  When multiple processes are started, they are started in"
        print "  priority order (see config file)"
        # XXX the above is not true yet

    def do_stop(self, arg):
        if not self._upcheck():
            return

        processnames = arg.strip().split()
        supervisor = self._get_supervisor()
        if processnames:
            for processname in processnames:
                self._output(supervisor.stopProcess(processname))

    def help_stop(self):
        print "stop <processname>\t\t\tStop a process."
        print "stop <processname> <processname>\tStop multiple processes"
        print "stop all\t\t\t\tStop all processes"
        print "  When multiple processes are stopped, they are stopped in"
        print "  reverse priority order (see config file)"
        # XXX the above is not true yet

    def do_restart(self, arg):
        if not self._upcheck():
            return

        processnames = arg.strip().split()
        supervisor = self._get_supervisor()
        if processnames:
            for processname in processnames:
                self._output(supervisor.stopProcess(processname))
                self._output(supervisor.startProcess(processname))

    def help_restart(self):
        print "restart <processname>\t\t\tRestart a process."
        print "restart <processname> <processname>\tRestart multiple processes"
        print "restart all\t\t\t\tRestart all processes"
        print "  When multiple processes are restarted, they are started in"
        print "  priority order (see config file)"
        # XXX the above is not true yet

class BasicAuthTransport(xmlrpclib.Transport):
    # Py 2.3 backwards compatibility class
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.verbose = False

    def request(self, host, handler, request_body, verbose=False):
        # issue XML-RPC request

        h = httplib.HTTP(host)
        h.putrequest("POST", handler)

        # required by HTTP/1.1
        h.putheader("Host", host)

        # required by XML-RPC
        h.putheader("User-Agent", self.user_agent)
        h.putheader("Content-Type", "text/xml")
        h.putheader("Content-Length", str(len(request_body)))

        # basic auth
        if self.username is not None and self.password is not None:
            unencoded = "%s:%s" % (self.username, self.password)
            encoded = unencoded.encode('base64')
            encoded = encoded.replace('\012', '')
            h.putheader("Authorization", "Basic %s" % encoded)

        h.endheaders()

        if request_body:
            h.send(request_body)

        errcode, errmsg, headers = h.getreply()

        if errcode != 200:
            raise xmlrpclib.ProtocolError(
                host + handler,
                errcode, errmsg,
                headers
                )

        return self.parse_response(h.getfile())

def main(args=None, options=None):
    if options is None:
        options = ClientOptions()
    options.realize(args)
    c = ZDCmd(options)
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
            print
            pass

if __name__ == "__main__":
    main()
