#!/usr/bin/env python

""" An executable which proxies for a subprocess; upon a signal, it sends that
signal to the process identified by a pidfile. """

import os
import sys
import signal
import time

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
                pid = os.waitpid(-1, os.WNOHANG)[0]
            except OSError:
                pid = None
            if pid:
                break

    def usage(self):
        print("pidproxy.py <pidfile name> <command> [<cmdarg1> ...]")

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.passtochild)
        signal.signal(signal.SIGHUP, self.passtochild)
        signal.signal(signal.SIGINT, self.passtochild)
        signal.signal(signal.SIGUSR1, self.passtochild)
        signal.signal(signal.SIGUSR2, self.passtochild)
        signal.signal(signal.SIGQUIT, self.passtochild)
        signal.signal(signal.SIGCHLD, self.reap)

    def reap(self, sig, frame):
        # do nothing, we reap our child synchronously
        pass

    def passtochild(self, sig, frame):
        try:
            with open(self.pidfile, 'r') as f:
                pid = int(f.read().strip())
        except:
            print("Can't read child pidfile %s!" % self.pidfile)
            return
        os.kill(pid, sig)
        if sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
            sys.exit(0)

def main():
    pp = PidProxy(sys.argv)
    pp.go()

if __name__ == '__main__':
    main()



