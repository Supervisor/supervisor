import asyncore
import asynchat
import socket
import srp
import os
import signal
import sys
import time

# response status codes
ST_OK = 200
ST_FAILED = 400
ST_AUTHREQUIRED = 401
ST_SERVERERROR = 500
PROTVERSION = "1.0"
from tailhelper import TailHelper

class CommandServerChannel(asynchat.async_chat):
    authenticating = False # flag to determine whether a connection is auth'ing
    authsession = None # SRP auth session data
    clientproof = None # SRP client proof data

    def __init__ (self, server, sock, addr):
        asynchat.async_chat.__init__ (self, sock)
        self.server = server
        self.addr = addr
        self.set_terminator ('\n')
        self.data = ''
        self.supervisord = server.supervisord
        self.options = server.supervisord.options

    def collect_incoming_data (self, data):
        self.data = self.data + data

    def found_terminator (self):
        line = self.data
        self.data = ''
        if not line:
            pass
        self.handle_command (line)

    def handle_command(self, command):
        try:
            protversion, command = command.split(' ', 1)
        except (ValueError, IndexError):
            self.sendreply(ST_FAILED, "Malformed request")
            return

        args = command.split()
        if not args:
            self.sendreply(ST_FAILED, "Empty command")
            return

        command = args[0]

        if not self.checkauth() and not command in ('auth', 'proof'):
            self.sendreply(ST_AUTHREQUIRED, "Authentication required\n")
            return

        methodname = "cmd_" + command
        method = getattr(self, methodname, None)
        if method:
            status, msg = method(args)
            self.sendreply(status, msg)
        else:
            self.sendreply(
                ST_FAILED,
                "Unknown command %r; 'capabilities' for a list\n" % command)

    def sendreply(self, status, msg):
        if not msg.endswith("\n"):
            msg = msg + "\n"
        msglen = len(msg)
        msg = "%s %s %s\n%s" % (PROTVERSION, status, msglen, msg)
        self.push(msg)

    def checkauth(self):
        if self.options.noauth:
            return True
        if self.authsession and not self.proving:
            return True
        return False

    def cmd_auth(self, args):
        if len(args) < 3:
            self.authsession = None
            return ST_FAILED, "AUTH command needs user and pubkey"
        user = args[1]
        pubkey = ' '.join(args[2:])
        try:
            A = srp.decode_long(''.join(pubkey.strip()))
        except:
            self.authsession = None
            return ST_FAILED, "malformed public key"
        try:
            if (not self.options.passwdfile or not
                os.path.exists(self.options.passwdfile)):
                raise srp.NoSuchUser
            self.authsession = tuple(
                srp.lookup(user, A, self.options.passwdfile)) + (A,)
        except srp.NoSuchUser:
            self.authsession = None
            return ST_FAILED, 'No such user "%s" \n' % user
        
        s, B, u, K, m, A = self.authsession

        key = '\t'.join([srp.encode_string(s),
                         srp.encode_long(B),
                         srp.encode_long(u)])
        
        self.proving = True
        return ST_OK, key

    def cmd_proof(self, args):
        if not self.proving:
            return ST_FAILED, "PROOF must be isssued directly afer AUTH"
        if len(args) < 2:
            self.authsession = None
            return ST_FAILED, "No client proof"
        self.clientproof = srp.decode_string(args[1])
        self.proving = False
        s, B, u, K, m, A = self.authsession

        if m == self.clientproof:
            hostproof = srp.encode_string(
                srp.host_authenticator(K, A, m))
            return ST_OK, hostproof
        else:
            self.authsession = None
            return ST_FAILED, 'Client proof failed. \n'

    def cmd_start(self, args):
        self.mood = 1
        names = args[1:]
        if not names:
            return ST_FAILED, "No process named"
        try:
            procs = self.supervisord.proclist.getmany(names)
        except KeyError, name:
            return ST_FAILED, "Unknown process named %s" % name
        resp = []
        for proc in procs:
            proc.backoff = 0
            proc.delay = 0
            proc.killing = 0
            proc.administrative_stop = 0
            if not proc.pid:
                proc.spawn()
                resp.append("%s started" % proc.name)
            else:
                resp.append("%s already started" % proc.name)
        return ST_OK, '\n'.join(resp)

    def cmd_stop(self, args):
        self.mood = 1 
        names = args[1:]
        if not names:
            return ST_FAILED, "No process named"
        try:
            procs = self.supervisord.proclist.getmany(names)
        except KeyError, name:
            return ST_FAILED, "Unknown process named %s" % name
        resp = []
        for proc in procs:
            proc.backoff = 0
            proc.delay = 0
            proc.killing = 0
            if proc.pid:
                status = proc.kill(signal.SIGTERM)
                if status:
                    resp.append(status)
                else:
                    resp.append("%s: sent SIGTERM" % proc.name)
                proc.killing = 1
                proc.administrative_stop = 1
                proc.delay = time.time() + self.options.backofflimit
            else:
                proc.administrative_stop = 1
                resp.append("%s: already stopped" % proc.name)
        return ST_OK, '\n'.join(resp)

    def cmd_restart(self, args):
        self.mood = 1 # Up
        names = args[1:]
        if not names:
            return ST_FAILED, "No process named"
        try:
            procs = self.supervisord.proclist.getmany(names)
        except KeyError, name:
            return ST_FAILED, "Unknown process named %s" % name
        resp = []
        for proc in procs:
            proc.administrative_stop = 0
            proc.backoff = 0
            proc.delay = 0
            proc.killing = 0
            if proc.pid:
                status = proc.kill(signal.SIGTERM)
                resp.append("Sent SIGTERM to %s; will restart later"
                            % proc.name)
                proc.killing = 1
                proc.delay = time.time() + self.options.backofflimit
            else:
                proc.spawn()
                resp.append("%s started" % proc.name)
        return ST_OK, '\n'.join(resp)

    def cmd_kill(self, args):
        try:
            which = args[1]
        except IndexError:
            return ST_FAILED, "No process named"
        if args[2:]:
            try:
                sig = int(args[2])
            except:
                return ST_FAILED, "Bad signal %r" % args[2]
        else:
            sig = signal.SIGTERM
        procs = self.supervisord.proclist.get(which)
        procs.reverse() # kill in reverse priority order
        resp = []
        if not procs:
            return ST_FAILED, "Unknown process %s" % which
        for proc in procs:
            if not proc.pid:
                resp.append("%s not running" % proc.name)
            else:
                msg = proc.kill(sig)
                if msg:
                    resp.append("Kill of %s with signal %d failed: %s" %
                                (proc.name, sig, msg))
                else:
                    resp.append("Signal %d sent to %s" % (sig, proc.name))
        return ST_OK, '\n'.join(resp)

    def cmd_status(self, args):
        names = args[1:]
        if not names:
            up, down = self.supervisord.proclist.getupdown()
            up = ','.join([proc.name for proc in up])
            down = ','.join([proc.name for proc in down])
            return (ST_OK,
                    "socket=%s\n" % `self.options.sockname` +
                    "supervisord_pid=%s\n" % os.getpid() +
                    "up=%s\n" % up +
                    "down=%s\n" % down)
        try:
            procs = self.supervisord.proclist.getmany(names)
        except KeyError, name:
            return ST_FAILED, "Unknown process named %s" % name

        msg = ''
        for proc in procs:
            filename = proc.get_execv_args()[0]
            msg = msg + ("name=%s\n" % proc.name +
                         "command=%s\n" % filename +
                         "status=%s\n" % (proc.pid and "up" or "down") +
                         "pid=%s\n" % proc.pid)
        return ST_OK, msg

    def cmd_list(self, args):
        try:
            which = args[1]
        except IndexError:
            which = 'all'
        if which not in ['all', 'up', 'down']:
            return ST_FAILED, 'args to list must be one of "all", "up", "down"'
        procs = self.supervisord.proclist.get(which)
        names = [ proc.name for proc in procs ]
        msg = '\n'.join(names)
        return ST_OK, msg

    def cmd_reload(self, args):
        self.mood = 0
        self.options.logger.critical('Reloading config and restarting all '
                                     'processes')
        self.supervisord.proclist.stop_all()
        return ST_OK, 'Reloading configuration after all processes have quit'
        self.close()

    def cmd_shutdown(self, args):
        self.supervisord.mood = -1 # exiting
        self.options.logger.critical("supervisord stopping via shutdown")
        self.supervisord.proclist.stop_all()
        return ST_OK, "Will shut down after all processes have quit"

    def cmd_logtail(self, args):
        try:
            numlines = args[1]
        except:
            numlines = 15
        try:
            numlines = int(numlines)
        except:
            return ST_FAILED, ('Number of lines must be integer, was: %s' %
                               numlines)
        helper = TailHelper(self.options.logfile)
        sz, lines = helper.tail(numlines)
        return ST_OK, ''.join(lines)

    def cmd_capabilities(self, args):
        caps = [
            "capabilities          -- return server capabilities",
            "status [name]         -- report application/process status",
            "kill name [signame]   -- send a signal to the application",
            "start name [name..]   -- start an application",
            "stop name [name..]    -- stop an application if running",
            "restart name [name..] -- stop followed by start",
            "list [all|up|down]    -- list controlled service names",
            "shutdown              -- Shut the supervisord process down",
            ]
        if not self.noauth:
            caps.append(
            "auth                  -- Initiate SRP authentication"
            )

        return ST_OK, '\n'.join(caps)

    def cmd_add(self, args):
        from supervisord import Subprocess
        from rpc import ProcessConfig
        try:
            processName = args[1]
        except IndexError:
            return ST_FAILED, "No process named"
        if not args[2:]:
            return ST_FAILED, "Bad no command named"
        command = ' '.join(args[2:])
        options = self.options
        logname = processName + str(time.time()) +  '.log'
        logfile = os.path.join(options.childlogdir, logname)
        config = ProcessConfig(name = processName,
            command=command, priority=999, auto_start = True,
            auto_restart = False, user = options.uid,
            logfile=logfile
            )
        process = Subprocess(options, config)
        process.metadata = ''
        self.supervisord.proclist.processes[processName] = process

        self.supervisord.proclist.start_necessary()
        return ST_OK, '%s might start' % processName

class CommandLineServer(asyncore.dispatcher):
    channel_class = CommandServerChannel
    
    def __init__(self, supervisord):
        asyncore.dispatcher.__init__(self, None, None)
        self.supervisord = supervisord
        self.options = supervisord.options
        
    def opensocket(self):
        if self.options.sockfamily == socket.AF_UNIX:
            self.open_domainsocket()
            return
        if self.options.sockfamily == socket.AF_INET:
            self.open_inetsocket()
            return
        raise RuntimeError, ('Unknown socket family %s' %
                             self.supervisord.options.sockfamily)

    def open_inetsocket(self):
        sockname = self.options.sockname
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        try:
            self.bind(sockname)
        except socket.error:
            sys.stderr.write(
                'Another process is already listening on port %s; could '
                'not start supervisord!\n' % sockname[1])
            sys.exit(1)
        self.listen(5)

    def open_domainsocket(self):
        options = self.options
        sockname = options.sockname
        tempname = "%s.%d" % (sockname, os.getpid())
        self.unlink_quietly(tempname)
        while 1:
            self.create_socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                self.bind(tempname)
                os.chmod(tempname, options.sockchmod)
                try:
                    os.link(tempname, sockname)
                    if options.sockchown:
                        try:
                            os.chown(sockname, options.sockuid, options.sockgid)
                        except os.error:
                            raise
                            options.logger.critical(
                                'Cant set uid/gid on socket!')
                            options.usage(
                                'Invalid socket-chown uid/gid %s'
                                % `self.options.sockchown`)
                    break
                except os.error:
                    # Lock contention, or stale socket.
                    self.checkopen()
                    # Stale socket -- delete, sleep, and try again.
                    msg = "Unlinking stale socket %s" % sockname
                    sys.stderr.write(msg + "\n")
                    self.options.logger.warn(msg)
                    self.unlink_quietly(sockname)
                    self.close()
                    time.sleep(1)
                    continue
            finally:
                self.unlink_quietly(tempname)
        self.listen(5)

    def unlink_quietly(self, filename):
        try:
            os.unlink(filename)
        except os.error:
            pass

    def checkopen(self):
        options = self.options
        s = socket.socket(options.sockfamily, socket.SOCK_STREAM)
        try:
            s.connect(options.sockname)
            s.send("1.0 STATUS\n")
            data = s.recv(1000)
            s.close()
        except socket.error:
            pass
        else:
            while data.endswith("\n"):
                data = data[:-1]
            msg = ("Another supervisord is already up using socket %r:\n%s" %
                   (options.sockname, data))
            sys.stderr.write(msg + "\n")
            options.logger.critical(msg)
            sys.exit(1)

    def handle_accept (self):
        conn, addr = self.accept()
        channel = self.channel_class(self, conn, addr)
        if not self.options.noauth:
            channel.authenticating = True
            channel.authsession = None
            channel.clientproof=None
        channel.authbuffer = ""
        #self.channels[channel] = 1

    def writable(self):
        return 0

    def readable(self):
        return 1

def makeCommandLineServer(supervisord):
    options = supervisord.options
    if options.sockname is None:
        return
    if options.noauth:
        options.logger.critical(
            'Running without any supervisorctl socket authentication '
            'checking')
    server = CommandLineServer(supervisord)
    options.logger.info('Running socket server on %r' % options.sockname)
    server.opensocket()
    return server
        
