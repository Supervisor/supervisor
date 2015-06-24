#!/usr/bin/env python

""" An executable which proxies for a subprocess; upon a signal, it sends that
signal to the process identified by a pidfile. """

import os
import sys
import signal
import time
import argparse



class PidProxy:
    def __init__(self, pidfile, cmdargs, wait_pidfile_time=None):
        self.setsignals()
        self.wait_pidfile_time = wait_pidfile_time
        self.pid = None
        self.pidfile = pidfile
        self.command = os.path.abspath(cmdargs[0])
        self.cmdargs = cmdargs

    def go(self):
        print(self.cmdargs)
        self.pid = os.spawnv(os.P_NOWAIT, self.command, self.cmdargs)
        if self.wait_pidfile_time:
            self.wait_pidfile_showup()
            self.wait_pidfile_lifetime()
            return

        while True:
            time.sleep(5)
            try:
                pid, sts = os.waitpid(-1, os.WNOHANG)
            except OSError:
                pid, sts = None, None
            if pid:
                break

    def wait_pidfile_showup(self):
        for i in range(self.wait_pidfile_time*10):
            time.sleep(0.1)
            if self.pid_exists():
                return
        raise Exception("pid file %r failed to appear after %r seconds. Assuming the process died prematurely" % (
            self.pidfile, self.wait_pidfile_time))

    def wait_pidfile_lifetime(self):
        while self.pid_exists():
            time.sleep(5)

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
            pid = self.get_pid()
        except:
            print("Can't read child pidfile %s!" % self.pidfile)
            return
        os.kill(pid, sig)
        if sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
            sys.exit(0)

    def get_pid(self):
        with open(self.pidfile, 'r') as f:
            return int(f.read().strip())

    def pid_exists(self):
        try:
            pid = self.get_pid()
            os.kill(pid, 0)
            return True
        except (OSError, IOError):
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pidfile", help="pid file location")
    parser.add_argument("command", help="command to run (with args)", nargs=argparse.REMAINDER)
    parser.add_argument("--wait", help="wait pid file creation for WAIT seconds, "
                                       "then monitor the pid in order to track the process lifetime "
                                       "(useful for processes which fork to background)",
                        default=60, type=int)
    params = parser.parse_args()
    pp = PidProxy(pidfile=params.pidfile, cmdargs=params.command, wait_pidfile_time=params.wait)
    pp.go()

if __name__ == '__main__':
    main()



