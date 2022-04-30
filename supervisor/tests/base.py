_NOW = 1151365354
_TIMEFORMAT = '%b %d %I:%M %p'

import functools

from supervisor.compat import Fault
from supervisor.compat import as_bytes

# mock is imported here for py2/3 compat.  we only declare mock as a dependency
# via tests_require so it is not available on all supervisor installs.  the
# modules imported in supervisor.compat must always be available.

try: # pragma: no cover
    from unittest.mock import Mock, patch, sentinel
except ImportError: # pragma: no cover
    from mock import Mock, patch, sentinel

try: # pragma: no cover
    import unittest.mock as mock
except ImportError: # pragma: no cover
    import mock

class DummyOptions:
    loglevel = 20
    minfds = 5

    chdir_exception = None
    fork_exception = None
    execv_exception = None
    kill_exception = None
    make_pipes_exception = None
    remove_exception = None
    write_exception = None

    def __init__(self):
        self.identifier = 'supervisor'
        self.childlogdir = '/tmp'
        self.uid = 999
        self.logger = self.getLogger()
        self.backofflimit = 10
        self.logfile = '/tmp/logfile'
        self.nocleanup = False
        self.strip_ansi = False
        self.pidhistory = {}
        self.process_group_configs = []
        self.nodaemon = False
        self.socket_map = {}
        self.mood = 1
        self.mustreopen = False
        self.realizeargs = None
        self.fds_cleaned_up = False
        self.rlimit_set = False
        self.setuid_called = False
        self.httpservers_opened = False
        self.signals_set = False
        self.daemonized = False
        self.make_logger_messages = None
        self.autochildlogdir_cleared = False
        self.cleaned_up = False
        self.pidfile_written = False
        self.directory = None
        self.waitpid_return = None, None
        self.kills = {}
        self._signal = None
        self.parent_pipes_closed = None
        self.child_pipes_closed = None
        self.forkpid = 0
        self.pgrp_set = None
        self.duped = {}
        self.written = {}
        self.fds_closed = []
        self._exitcode = None
        self.execve_called = False
        self.execv_args = None
        self.setuid_msg = None
        self.privsdropped = None
        self.logs_reopened = False
        self.write_accept = None
        self.tempfile_name = '/foo/bar'
        self.removed = []
        self.existing = []
        self.openreturn = None
        self.readfd_result = ''
        self.parse_criticals = []
        self.parse_warnings = []
        self.parse_infos = []
        self.serverurl = 'http://localhost:9001'
        self.changed_directory = False
        self.umaskset = None
        self.poller = DummyPoller(self)
        self.silent = False

    def getLogger(self, *args, **kw):
        logger = DummyLogger()
        logger.handlers = [DummyLogger()]
        logger.args = args, kw
        return logger

    def realize(self, args, **kw):
        self.realizeargs = args
        self.realizekw = kw

    def process_config(self, do_usage=True):
        pass

    def cleanup_fds(self):
        self.fds_cleaned_up = True

    def set_rlimits_or_exit(self):
        self.rlimits_set = True
        self.parse_infos.append('rlimits_set')

    def set_uid_or_exit(self):
        self.setuid_called = True
        self.parse_criticals.append('setuid_called')

    def openhttpservers(self, supervisord):
        self.httpservers_opened = True

    def daemonize(self):
        self.daemonized = True

    def setsignals(self):
        self.signals_set = True

    def get_signal(self):
        return self._signal

    def get_socket_map(self):
        return self.socket_map

    def make_logger(self):
        pass

    def clear_autochildlogdir(self):
        self.autochildlogdir_cleared = True

    def get_autochildlog_name(self, *ignored):
        return self.tempfile_name

    def cleanup(self):
        self.cleaned_up = True

    def write_pidfile(self):
        self.pidfile_written = True

    def waitpid(self):
        return self.waitpid_return

    def kill(self, pid, sig):
        if self.kill_exception is not None:
            raise self.kill_exception
        self.kills[pid] = sig

    def stat(self, filename):
        import os
        return os.stat(filename)

    def get_path(self):
        return ["/bin", "/usr/bin", "/usr/local/bin"]

    def get_pid(self):
        import os
        return os.getpid()

    def check_execv_args(self, filename, argv, st):
        if filename == '/bad/filename':
            from supervisor.options import NotFound
            raise NotFound('bad filename')

    def make_pipes(self, stderr=True):
        if self.make_pipes_exception is not None:
            raise self.make_pipes_exception
        pipes = {'child_stdin': 3, 'stdin': 4, 'stdout': 5, 'child_stdout': 6}
        if stderr:
            pipes['stderr'], pipes['child_stderr'] = (7, 8)
        else:
            pipes['stderr'], pipes['child_stderr'] = None, None
        return pipes

    def write(self, fd, chars):
        if self.write_exception is not None:
            raise self.write_exception
        if self.write_accept:
            chars = chars[self.write_accept]
        data = self.written.setdefault(fd, '')
        data += chars
        self.written[fd] = data
        return len(chars)

    def fork(self):
        if self.fork_exception is not None:
            raise self.fork_exception
        return self.forkpid

    def close_fd(self, fd):
        self.fds_closed.append(fd)

    def close_parent_pipes(self, pipes):
        self.parent_pipes_closed = pipes

    def close_child_pipes(self, pipes):
        self.child_pipes_closed = pipes

    def setpgrp(self):
        self.pgrp_set = True

    def dup2(self, frm, to):
        self.duped[frm] = to

    def _exit(self, code):
        self._exitcode = code

    def execve(self, filename, argv, environment):
        self.execve_called = True
        if self.execv_exception is not None:
            raise self.execv_exception
        self.execv_args = (filename, argv)
        self.execv_environment = environment

    def drop_privileges(self, uid):
        if self.setuid_msg:
            return self.setuid_msg
        self.privsdropped = uid

    def readfd(self, fd):
        return self.readfd_result

    def reopenlogs(self):
        self.logs_reopened = True

    def mktempfile(self, prefix, suffix, dir):
        return self.tempfile_name

    def remove(self, path):
        if self.remove_exception is not None:
            raise self.remove_exception
        self.removed.append(path)

    def exists(self, path):
        if path in self.existing:
            return True
        return False

    def open(self, name, mode='r'):
        if self.openreturn:
            return self.openreturn
        return open(name, mode)

    def chdir(self, dir):
        if self.chdir_exception is not None:
            raise self.chdir_exception
        self.changed_directory = True

    def setumask(self, mask):
        self.umaskset = mask

class DummyLogger:
    level = None

    def __init__(self):
        self.reopened = False
        self.removed = False
        self.closed = False
        self.data = []

    def info(self, msg, **kw):
        if kw:
            msg = msg % kw
        self.data.append(msg)
    warn = debug = critical = trace = error = blather = info

    def log(self, level, msg, **kw):
        if kw:
            msg = msg % kw
        self.data.append(msg)

    def addHandler(self, handler):
        handler.close()

    def reopen(self):
        self.reopened = True
    def close(self):
        self.closed = True
    def remove(self):
        self.removed = True
    def flush(self):
        self.flushed = True
    def getvalue(self):
        return ''.join(self.data)

class DummySupervisor:
    def __init__(self, options=None, state=None, process_groups=None):
        if options is None:
            self.options = DummyOptions()
        else:
            self.options = options
        if state is None:
            from supervisor.supervisord import SupervisorStates
            self.options.mood = SupervisorStates.RUNNING
        else:
            self.options.mood = state
        if process_groups is None:
            self.process_groups = {}
        else:
            self.process_groups = process_groups

    def get_state(self):
        return self.options.mood

class DummySocket:
    bind_called = False
    bind_addr = None
    listen_called = False
    listen_backlog = None
    close_called = False

    def __init__(self, fd):
        self.fd = fd

    def fileno(self):
        return self.fd

    def bind(self, addr):
        self.bind_called = True
        self.bind_addr = addr

    def listen(self, backlog):
        self.listen_called = True
        self.listen_backlog = backlog

    def close(self):
        self.close_called = True

    def __str__(self):
        return 'dummy socket'

class DummySocketConfig:
    def __init__(self, fd, backlog=128):
        self.fd = fd
        self.backlog = backlog
        self.url = 'unix:///sock'

    def addr(self):
        return 'dummy addr'

    def __eq__(self, other):
        return self.fd == other.fd

    def __ne__(self, other):
        return not self.__eq__(other)

    def get_backlog(self):
        return self.backlog

    def create_and_bind(self):
        return DummySocket(self.fd)

class DummySocketManager:
    def __init__(self, config, **kwargs):
        self._config = config

    def config(self):
        return self._config

    def get_socket(self):
        return DummySocket(self._config.fd)

@functools.total_ordering
class DummyProcess(object):
    write_exception = None

    # Initial state; overridden by instance variables
    pid = 0 # Subprocess pid; 0 when not running
    laststart = 0 # Last time the subprocess was started; 0 if never
    laststop = 0  # Last time the subprocess was stopped; 0 if never
    delay = 0 # If nonzero, delay starting or killing until this time
    administrative_stop = False # true if the process stopped by an admin
    system_stop = False # true if the process has been stopped by the system
    killing = False # flag determining whether we are trying to kill this proc
    backoff = 0 # backoff counter (to backofflimit)
    waitstatus = None
    exitstatus = None
    pipes = None
    rpipes = None
    dispatchers = None
    stdout_logged = ''
    stderr_logged = ''
    spawnerr = None
    stdout_buffer = '' # buffer of characters from child stdout output to log
    stderr_buffer = '' # buffer of characters from child stderr output to log
    stdin_buffer = '' # buffer of characters to send to child process' stdin
    listener_state = None
    group = None
    sent_signal = None

    def __init__(self, config, state=None):
        self.config = config
        self.logsremoved = False
        self.stop_called = False
        self.stop_report_called = True
        self.backoff_secs = None
        self.spawned = False
        if state is None:
            from supervisor.process import ProcessStates
            state = ProcessStates.RUNNING
        self.state = state
        self.error_at_clear = False
        self.killed_with = None
        self.drained = False
        self.stdout_buffer = as_bytes('')
        self.stderr_buffer = as_bytes('')
        self.stdout_logged = as_bytes('')
        self.stderr_logged = as_bytes('')
        self.stdin_buffer = as_bytes('')
        self.pipes = {}
        self.rpipes = {}
        self.dispatchers = {}
        self.finished = None
        self.logs_reopened = False
        self.execv_arg_exception = None
        self.input_fd_drained = None
        self.output_fd_drained = None
        self.transitioned = False

    def reopenlogs(self):
        self.logs_reopened = True

    def removelogs(self):
        if self.error_at_clear:
            raise IOError('whatever')
        self.logsremoved = True

    def get_state(self):
        return self.state

    def stop(self):
        self.stop_called = True
        self.killing = False
        from supervisor.process import ProcessStates
        self.state = ProcessStates.STOPPED

    def stop_report(self):
        self.stop_report_called = True

    def kill(self, signal):
        self.killed_with = signal

    def signal(self, signal):
        self.sent_signal = signal


    def spawn(self):
        self.spawned = True
        from supervisor.process import ProcessStates
        self.state = ProcessStates.RUNNING

    def drain(self):
        self.drained = True

    def readable_fds(self):
        return []

    def record_output(self):
        self.stdout_logged += self.stdout_buffer
        self.stdout_buffer = ''

        self.stderr_logged += self.stderr_buffer
        self.stderr_buffer = ''

    def finish(self, pid, sts):
        self.finished = pid, sts

    def give_up(self):
        from supervisor.process import ProcessStates
        self.state = ProcessStates.FATAL

    def get_execv_args(self):
        if self.execv_arg_exception:
            raise self.execv_arg_exception('whatever')
        import shlex
        commandargs = shlex.split(self.config.command)
        program = commandargs[0]
        return program, commandargs

    def drain_output_fd(self, fd):
        self.output_fd_drained = fd

    def drain_input_fd(self, fd):
        self.input_fd_drained = fd

    def write(self, chars):
        if self.write_exception is not None:
            raise self.write_exception
        self.stdin_buffer += chars

    def transition(self):
        self.transitioned = True

    def __eq__(self, other):
        return self.config.priority == other.config.priority

    def __lt__(self, other):
        return self.config.priority < other.config.priority

class DummyPConfig:
    def __init__(self, options, name, command, directory=None, umask=None,
                 priority=999, autostart=True,
                 autorestart=True, startsecs=10, startretries=999,
                 uid=None, stdout_logfile=None, stdout_capture_maxbytes=0,
                 stdout_events_enabled=False,
                 stdout_logfile_backups=0, stdout_logfile_maxbytes=0,
                 stdout_syslog=False,
                 stderr_logfile=None, stderr_capture_maxbytes=0,
                 stderr_events_enabled=False,
                 stderr_logfile_backups=0, stderr_logfile_maxbytes=0,
                 stderr_syslog=False,
                 redirect_stderr=False,
                 stopsignal=None, stopwaitsecs=10, stopasgroup=False, killasgroup=False,
                 exitcodes=(0,), environment=None, serverurl=None):
        self.options = options
        self.name = name
        self.command = command
        self.priority = priority
        self.autostart = autostart
        self.autorestart = autorestart
        self.startsecs = startsecs
        self.startretries = startretries
        self.uid = uid
        self.stdout_logfile = stdout_logfile
        self.stdout_capture_maxbytes = stdout_capture_maxbytes
        self.stdout_events_enabled = stdout_events_enabled
        self.stdout_logfile_backups = stdout_logfile_backups
        self.stdout_logfile_maxbytes = stdout_logfile_maxbytes
        self.stdout_syslog = stdout_syslog
        self.stderr_logfile = stderr_logfile
        self.stderr_capture_maxbytes = stderr_capture_maxbytes
        self.stderr_events_enabled = stderr_events_enabled
        self.stderr_logfile_backups = stderr_logfile_backups
        self.stderr_logfile_maxbytes = stderr_logfile_maxbytes
        self.stderr_syslog = stderr_syslog
        self.redirect_stderr = redirect_stderr
        if stopsignal is None:
            import signal
            stopsignal = signal.SIGTERM
        self.stopsignal = stopsignal
        self.stopwaitsecs = stopwaitsecs
        self.stopasgroup = stopasgroup
        self.killasgroup = killasgroup
        self.exitcodes = exitcodes
        self.environment = environment
        self.directory = directory
        self.umask = umask
        self.autochildlogs_created = False
        self.serverurl = serverurl

    def get_path(self):
        return ["/bin", "/usr/bin", "/usr/local/bin"]

    def create_autochildlogs(self):
        self.autochildlogs_created = True

    def make_process(self, group=None):
        process = DummyProcess(self)
        process.group = group
        return process

    def make_dispatchers(self, proc):
        use_stderr = not self.redirect_stderr
        pipes = self.options.make_pipes(use_stderr)
        stdout_fd,stderr_fd,stdin_fd = (pipes['stdout'],pipes['stderr'],
                                        pipes['stdin'])
        dispatchers = {}
        if stdout_fd is not None:
            dispatchers[stdout_fd] = DummyDispatcher(readable=True)
        if stderr_fd is not None:
            dispatchers[stderr_fd] = DummyDispatcher(readable=True)
        if stdin_fd is not None:
            dispatchers[stdin_fd] = DummyDispatcher(writable=True)
        return dispatchers, pipes

def makeExecutable(file, substitutions=None):
    import os
    import sys
    import tempfile

    if substitutions is None:
        substitutions = {}
    data = open(file).read()
    last = os.path.split(file)[1]

    substitutions['PYTHON'] = sys.executable
    for key in substitutions.keys():
        data = data.replace('<<%s>>' % key.upper(), substitutions[key])

    with tempfile.NamedTemporaryFile(prefix=last, delete=False) as f:
        tmpnam = f.name
        f.write(data)
    os.chmod(tmpnam, 0o755)
    return tmpnam

def makeSpew(unkillable=False):
    import os
    here = os.path.dirname(__file__)
    if not unkillable:
        return makeExecutable(os.path.join(here, 'fixtures/spew.py'))
    return makeExecutable(os.path.join(here, 'fixtures/unkillable_spew.py'))

class DummyMedusaServerLogger:
    def __init__(self):
        self.logged = []
    def log(self, category, msg):
        self.logged.append((category, msg))

class DummyMedusaServer:
    def __init__(self):
        self.logger = DummyMedusaServerLogger()

class DummyMedusaChannel:
    def __init__(self):
        self.server = DummyMedusaServer()
        self.producer = None

    def push_with_producer(self, producer):
        self.producer = producer

    def close_when_done(self):
        pass

    def set_terminator(self, terminator):
        pass

class DummyRequest(object):
    command = 'GET'
    _error = None
    _done = False
    version = '1.0'
    def __init__(self, path, params, query, fragment, env=None):
        self.args = path, params, query, fragment
        self.producers = []
        self.headers = {}
        self.header = []
        self.outgoing = []
        self.channel = DummyMedusaChannel()
        if env is None:
            self.env = {}
        else:
            self.env = env

    def split_uri(self):
        return self.args

    def error(self, code):
        self._error = code

    def push(self, producer):
        self.producers.append(producer)

    def __setitem__(self, header, value):
        self.headers[header] = value

    def __getitem__(self, header):
        return self.headers[header]

    def __delitem__(self, header):
        del self.headers[header]

    def has_key(self, header):
        return header in self.headers

    def __contains__(self, item):
        return item in self.headers

    def done(self):
        self._done = True

    def build_reply_header(self):
        return ''

    def log(self, *arg, **kw):
        pass

    def cgi_environment(self):
        return self.env

    def get_server_url(self):
        return 'http://example.com'


class DummyRPCInterfaceFactory:
    def __init__(self, supervisord, **config):
        self.supervisord = supervisord
        self.config = config

class DummyRPCServer:
    def __init__(self):
        self.supervisor = DummySupervisorRPCNamespace()
        self.system = DummySystemRPCNamespace()

class DummySystemRPCNamespace:
    pass

class DummySupervisorRPCNamespace:
    _restartable = True
    _restarted = False
    _shutdown = False
    _readlog_error = False


    from supervisor.process import ProcessStates
    all_process_info = [
        {
        'name':'foo',
        'group':'foo',
        'pid':11,
        'state':ProcessStates.RUNNING,
        'statename':'RUNNING',
        'start':_NOW - 100,
        'stop':0,
        'spawnerr':'',
        'now':_NOW,
        'description':'foo description',
        },
        {
        'name':'bar',
        'group':'bar',
        'pid':12,
        'state':ProcessStates.FATAL,
        'statename':'FATAL',
        'start':_NOW - 100,
        'stop':_NOW - 50,
        'spawnerr':'screwed',
        'now':_NOW,
        'description':'bar description',
        },
        {
        'name':'baz_01',
        'group':'baz',
        'pid':13,
        'state':ProcessStates.STOPPED,
        'statename':'STOPPED',
        'start':_NOW - 100,
        'stop':_NOW - 25,
        'spawnerr':'',
        'now':_NOW,
        'description':'baz description',
        },
        ]

    def getAPIVersion(self):
        return '3.0'

    getVersion = getAPIVersion # deprecated

    def getPID(self):
        return 42

    def _read_log(self, channel, name, offset, length):
        from supervisor import xmlrpc
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        elif name == 'FAILED':
            raise Fault(xmlrpc.Faults.FAILED, 'FAILED')
        elif name == 'NO_FILE':
            raise Fault(xmlrpc.Faults.NO_FILE, 'NO_FILE')
        a = (channel + ' line\n') * 10
        return a[offset:]

    def readProcessStdoutLog(self, name, offset, length):
        return self._read_log('stdout', name, offset, length)
    readProcessLog = readProcessStdoutLog

    def readProcessStderrLog(self, name, offset, length):
        return self._read_log('stderr', name, offset, length)

    def getAllProcessInfo(self):
        return self.all_process_info

    def getProcessInfo(self, name):
        from supervisor import xmlrpc
        for i in self.all_process_info:
            if i['name']==name:
                info=i
                return info
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        if name == 'FAILED':
            raise Fault(xmlrpc.Faults.FAILED, 'FAILED')
        if name == 'NO_FILE':
            raise Fault(xmlrpc.Faults.NO_FILE, 'NO_FILE')

    def startProcess(self, name):
        from supervisor import xmlrpc
        if name == 'BAD_NAME:BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME:BAD_NAME')
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        if name == 'NO_FILE':
            raise Fault(xmlrpc.Faults.NO_FILE, 'NO_FILE')
        if name == 'NOT_EXECUTABLE':
            raise Fault(xmlrpc.Faults.NOT_EXECUTABLE, 'NOT_EXECUTABLE')
        if name == 'ALREADY_STARTED':
            raise Fault(xmlrpc.Faults.ALREADY_STARTED, 'ALREADY_STARTED')
        if name == 'SPAWN_ERROR':
            raise Fault(xmlrpc.Faults.SPAWN_ERROR, 'SPAWN_ERROR')
        if name == 'ABNORMAL_TERMINATION':
            raise Fault(xmlrpc.Faults.ABNORMAL_TERMINATION,
                        'ABNORMAL_TERMINATION')
        return True

    def startProcessGroup(self, name):
        from supervisor import xmlrpc
        from supervisor.compat import Fault
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        return [
            {'name':'foo_00', 'group':'foo',
             'status': xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'foo_01', 'group':'foo',
             'status':xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            ]

    def startAllProcesses(self):
        from supervisor import xmlrpc
        return [
            {'name':'foo', 'group':'foo',
             'status': xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'foo2', 'group':'foo2',
             'status':xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'failed', 'group':'failed_group',
             'status':xmlrpc.Faults.SPAWN_ERROR,
             'description':'SPAWN_ERROR'}
            ]

    def stopProcessGroup(self, name):
        from supervisor import xmlrpc
        from supervisor.compat import Fault
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        return [
            {'name':'foo_00', 'group':'foo',
             'status': xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'foo_01', 'group':'foo',
             'status':xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            ]

    def stopProcess(self, name):
        from supervisor import xmlrpc
        if name == 'BAD_NAME:BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME:BAD_NAME')
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        if name == 'NOT_RUNNING':
            raise Fault(xmlrpc.Faults.NOT_RUNNING, 'NOT_RUNNING')
        if name == 'FAILED':
            raise Fault(xmlrpc.Faults.FAILED, 'FAILED')

        return True

    def stopAllProcesses(self):
        from supervisor import xmlrpc
        return [
            {'name':'foo','group':'foo',
             'status': xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'foo2', 'group':'foo2',
             'status':xmlrpc.Faults.SUCCESS,'description': 'OK'},
            {'name':'failed', 'group':'failed_group',
             'status':xmlrpc.Faults.BAD_NAME,
             'description':'FAILED'}
            ]

    def restart(self):
        if self._restartable:
            self._restarted = True
            return
        from supervisor import xmlrpc
        raise Fault(xmlrpc.Faults.SHUTDOWN_STATE, '')

    def shutdown(self):
        if self._restartable:
            self._shutdown = True
            return
        from supervisor import xmlrpc
        raise Fault(xmlrpc.Faults.SHUTDOWN_STATE, '')

    def reloadConfig(self):
        return [[['added'], ['changed'], ['removed']]]

    def addProcessGroup(self, name):
        from supervisor import xmlrpc
        if name == 'ALREADY_ADDED':
            raise Fault(xmlrpc.Faults.ALREADY_ADDED, '')
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, '')
        if name == 'FAILED':
            raise Fault(xmlrpc.Faults.FAILED, '')
        if name == 'SHUTDOWN_STATE':
            raise Fault(xmlrpc.Faults.SHUTDOWN_STATE, '')
        if hasattr(self, 'processes'):
            self.processes.append(name)
        else:
            self.processes = [name]

    def removeProcessGroup(self, name):
        from supervisor import xmlrpc
        if name == 'STILL_RUNNING':
            raise Fault(xmlrpc.Faults.STILL_RUNNING, '')
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, '')
        if name == 'FAILED':
            raise Fault(xmlrpc.Faults.FAILED, '')
        self.processes.remove(name)

    def clearProcessStdoutLog(self, name):
        from supervisor import xmlrpc
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        return True

    clearProcessLog = clearProcessStdoutLog
    clearProcessStderrLog = clearProcessStdoutLog
    clearProcessLogs = clearProcessStdoutLog

    def clearAllProcessLogs(self):
        from supervisor import xmlrpc
        return [
            {'name':'foo',
             'group':'foo',
             'status':xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'foo2',
             'group':'foo2',
             'status':xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'failed',
             'group':'failed_group',
             'status':xmlrpc.Faults.FAILED,
             'description':'FAILED'}
            ]

    def raiseError(self):
        raise ValueError('error')

    def getXmlRpcUnmarshallable(self):
        return {'stdout_logfile': None}  # None is unmarshallable

    def getSupervisorVersion(self):
        return '3000'

    def readLog(self, whence, offset):
        if self._readlog_error:
            raise Fault(self._readlog_error, '')
        return 'mainlogdata'

    def signalProcessGroup(self, name, signal):
        from supervisor import xmlrpc
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        return [
            {'name':'foo_00',
             'group':'foo',
             'status': xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'foo_01',
             'group':'foo',
             'status':xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            ]

    def signalProcess(self, name, signal):
        from supervisor import xmlrpc
        if signal == 'BAD_SIGNAL':
            raise Fault(xmlrpc.Faults.BAD_SIGNAL, 'BAD_SIGNAL')
        if name == 'BAD_NAME:BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME:BAD_NAME')
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        if name == 'NOT_RUNNING':
            raise Fault(xmlrpc.Faults.NOT_RUNNING, 'NOT_RUNNING')
        if name == 'FAILED':
            raise Fault(xmlrpc.Faults.FAILED, 'FAILED')

        return True

    def signalAllProcesses(self, signal):
        from supervisor import xmlrpc
        return [
            {'name':'foo',
             'group':'foo',
             'status': xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'foo2',
             'group':'foo2',
             'status':xmlrpc.Faults.SUCCESS,
             'description': 'OK'},
            {'name':'failed',
             'group':'failed_group',
             'status':xmlrpc.Faults.BAD_NAME,
             'description':'FAILED'}
            ]

class DummyPGroupConfig:
    def __init__(self, options, name='whatever', priority=999, pconfigs=None):
        self.options = options
        self.name = name
        self.priority = priority
        if pconfigs is None:
            pconfigs = []
        self.process_configs = pconfigs
        self.after_setuid_called = False
        self.pool_events = []
        self.buffer_size = 10

    def after_setuid(self):
        self.after_setuid_called = True

    def make_group(self):
        return DummyProcessGroup(self)

    def __repr__(self):
        return '<%s instance at %s named %s>' % (self.__class__, id(self),
                                                 self.name)

class DummyFCGIGroupConfig(DummyPGroupConfig):
    def __init__(self, options, name='whatever', priority=999, pconfigs=None, socket_config=DummySocketConfig(1)):
        DummyPGroupConfig.__init__(self, options, name, priority, pconfigs)
        self.socket_config = socket_config

@functools.total_ordering
class DummyProcessGroup(object):
    def __init__(self, config):
        self.config = config
        self.transitioned = False
        self.all_stopped = False
        self.dispatchers = {}
        self.unstopped_processes = []
        self.before_remove_called = False

    def transition(self):
        self.transitioned = True

    def before_remove(self):
        self.before_remove_called = True

    def stop_all(self):
        self.all_stopped = True

    def get_unstopped_processes(self):
        return self.unstopped_processes

    def get_dispatchers(self):
        return self.dispatchers

    def __lt__(self, other):
        return self.config.priority < other.config.priority

    def __eq__(self, other):
        return self.config.priority == other.config.priority

    def reopenlogs(self):
        self.logs_reopened = True

class DummyFCGIProcessGroup(DummyProcessGroup):

    def __init__(self, config):
        DummyProcessGroup.__init__(self, config)
        self.socket_manager = DummySocketManager(config.socket_config)

class PopulatedDummySupervisor(DummySupervisor):
    def __init__(self, options, group_name, *pconfigs):
        DummySupervisor.__init__(self, options)
        self.process_groups = {}
        processes = {}
        self.group_name = group_name
        gconfig = DummyPGroupConfig(options, group_name, pconfigs=pconfigs)
        pgroup = DummyProcessGroup(gconfig)
        self.process_groups[group_name] = pgroup
        for pconfig in pconfigs:
            process = DummyProcess(pconfig)
            processes[pconfig.name] = process
        pgroup.processes = processes

    def set_procattr(self, process_name, attr_name, val, group_name=None):
        if group_name is None:
            group_name = self.group_name
        process = self.process_groups[group_name].processes[process_name]
        setattr(process, attr_name, val)

    def reap(self):
        self.reaped = True

class DummyDispatcher:
    flush_exception = None

    write_event_handled = False
    read_event_handled = False
    error_handled = False
    logs_reopened = False
    logs_removed = False
    closed = False
    flushed = False

    def __init__(self, readable=False, writable=False, error=False):
        self._readable = readable
        self._writable = writable
        self._error = error
        self.input_buffer = ''
        if readable:
            # only readable dispatchers should have these methods
            def reopenlogs():
                self.logs_reopened = True
            self.reopenlogs = reopenlogs
            def removelogs():
                self.logs_removed = True
            self.removelogs = removelogs

    def readable(self):
        return self._readable
    def writable(self):
        return self._writable
    def handle_write_event(self):
        if self._error:
            raise self._error
        self.write_event_handled = True
    def handle_read_event(self):
        if self._error:
            raise self._error
        self.read_event_handled = True
    def handle_error(self):
        self.error_handled = True
    def close(self):
        self.closed = True
    def flush(self):
        if self.flush_exception:
            raise self.flush_exception
        self.flushed = True

class DummyStream:
    def __init__(self, error=None, fileno=20):
        self.error = error
        self.closed = False
        self.flushed = False
        self.written = b''
        self._fileno = fileno
    def close(self):
        if self.error:
            raise self.error
        self.closed = True
    def flush(self):
        if self.error:
            raise self.error
        self.flushed = True
    def write(self, msg):
        if self.error:
            error = self.error
            self.error = None
            raise error
        self.written += as_bytes(msg)
    def seek(self, num, whence=0):
        pass
    def tell(self):
        return len(self.written)
    def fileno(self):
        return self._fileno

class DummyEvent:
    def __init__(self, serial='abc'):
        if serial is not None:
            self.serial = serial

    def payload(self):
        return 'dummy event'

class DummyPoller:
    def __init__(self, options):
        self.result = [], []
        self.closed = False

    def register_readable(self, fd):
        pass

    def register_writable(self, fd):
        pass

    def poll(self, timeout):
        return self.result

    def close(self):
        self.closed = True

def dummy_handler(event, result):
    pass

def rejecting_handler(event, result):
    from supervisor.dispatchers import RejectEvent
    raise RejectEvent(result)

def exception_handler(event, result):
    raise ValueError(result)

def lstrip(s):
    strings = [x.strip() for x in s.split('\n')]
    return '\n'.join(strings)
