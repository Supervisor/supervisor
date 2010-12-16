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

""" An executable which proxies for a subprocess; upon a signal, it sends that
signal to the process identified by a pidfile. Or if 'multi' is provided for
the pidfile, then all child process are found dynamically and the signal is
sent to each."""

import os
import sys
import signal
import time
import re

class PidProxy:
    pid = None
    def __init__(self, args):
        self.setsignals()
        try:
            self.pidfile, cmdargs = args[1], args[2:]
            self.command = os.path.abspath(cmdargs[0])
            self.cmdargs = cmdargs
        except (ValueError, IndexError):
            self.usage()
            sys.exit(1)

    def go(self):
        self.pid = os.spawnv(os.P_NOWAIT, self.command, self.cmdargs)
        while 1:
            time.sleep(5)
            try:
                pid, sts = os.waitpid(-1, os.WNOHANG)
            except OSError:
                pid, sts = None, None
            if pid:
                break

    def usage(self):
        print "pidproxy.py (<pidfile name>|multi) <command> [<cmdarg1> ...]"

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.passtochild)
        signal.signal(signal.SIGHUP, self.passtochild)
        signal.signal(signal.SIGINT, self.passtochild)
        signal.signal(signal.SIGUSR1, self.passtochild)
        signal.signal(signal.SIGUSR2, self.passtochild)
        signal.signal(signal.SIGCHLD, self.reap)

    def reap(self, sig, frame):
        # do nothing, we reap our child synchronously
        pass

    def passtochild(self, sig, frame):
        for pid in self.get_child_pids():
            os.kill(pid, sig)  # signal/kill children
        os.kill(self.pid, sig) # signal/kill parent
        if sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
            sys.exit(0) # kill self (pidproxy)
            
    def get_child_pids(self):
        pids = []
        if self.pidfile == 'multi':
            for pid in os.listdir("/proc/"):
                if not re.match("\d+", pid):
                    continue
                try:
                    f = open('/proc/%s/status' % pid)
                    for line in f:
                        if not line.startswith('PPid:'):
                            continue
                        ppid = line.split()[1].strip()
                        if int(ppid) == self.pid:
                            pids.append(int(pid))
                        break
                    f.close()
                except IOError:
                    pass # we can ignore race conditions
        else:
            try:
                pids = [int(open(self.pidfile, 'r').read().strip())]
            except:
                print "Can't read child pidfile %s!" % self.pidfile
        return pids

def main():
    pp = PidProxy(sys.argv)
    pp.go()

if __name__ == '__main__':
    main()

