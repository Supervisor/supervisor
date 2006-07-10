#!/usr/bin/env python
"""Test suite for supervisord.py."""

import os
import stat
import sys
import time
import signal
import tempfile
import unittest
import socket
import pickle
import pwd
import errno
from StringIO import StringIO

import supervisord
import datatypes
import xmlrpc
import http
from supervisord import ProcessStates
from supervisord import SupervisorStates
try:
    __file__
except:
    __file__ = sys.argv[0]


DEBUG = 0


import unittest

class ServerOptionsTests(unittest.TestCase):
    def _getTargetClass(self):
        from options import ServerOptions
        return ServerOptions

    def _makeOne(self):
        return self._getTargetClass()()
        
    def test_options(self):
        s = """[supervisord]
http_port=127.0.0.1:8999 ; (default is to run no xmlrpc server)
http_username=chrism     ; (default is no username (open system))
http_password=foo        ; (default is no password (open system))
directory=%(tempdir)s     ; (default is not to cd during daemonization)
backofflimit=10            ; (default 3)
user=root                  ; (default is current user, required if root)
umask=022                  ; (default 022)
logfile=supervisord.log    ; (default supervisord.log)
logfile_maxbytes=1000MB    ; (default 50MB)
logfile_backups=5          ; (default 10)
loglevel=error             ; (default info)
pidfile=supervisord.pid    ; (default supervisord.pid)
nodaemon=true              ; (default false)
identifier=fleeb           ; (default supervisor)
childlogdir=%(tempdir)s           ; (default tempfile.gettempdir())
nocleanup=true             ; (default false)
minfds=2048                ; (default 1024)
minprocs=300               ; (default 200)

[program:cat]
command=/bin/cat
priority=1
autostart=true
autorestart=true
user=root
logfile=/tmp/cat.log
stopsignal=KILL
stopwaitsecs=5
startsecs=5
startretries=10

[program:cat2]
command=/bin/cat
autostart=true
autorestart=false
logfile_maxbytes = 1024
logfile_backups = 2
logfile = /tmp/cat2.log

[program:cat3]
command=/bin/cat
exitcodes=0,1,127
""" % {'tempdir':tempfile.gettempdir()}

        from StringIO import StringIO
        fp = StringIO(s)
        instance = self._makeOne()
        instance.configfile = fp
        instance.realize()
        options = instance.configroot.supervisord
        import socket
        self.assertEqual(options.directory, tempfile.gettempdir())
        self.assertEqual(options.umask, 022)
        self.assertEqual(options.logfile, 'supervisord.log')
        self.assertEqual(options.logfile_maxbytes, 1000 * 1024 * 1024)
        self.assertEqual(options.logfile_backups, 5)
        self.assertEqual(options.loglevel, 40)
        self.assertEqual(options.pidfile, 'supervisord.pid')
        self.assertEqual(options.nodaemon, True)
        self.assertEqual(options.identifier, 'fleeb')
        self.assertEqual(options.childlogdir, tempfile.gettempdir())
        self.assertEqual(options.http_port.family, socket.AF_INET)
        self.assertEqual(options.http_port.address, ('127.0.0.1', 8999))
        self.assertEqual(options.http_username, 'chrism')
        self.assertEqual(options.http_password, 'foo')
        self.assertEqual(options.nocleanup, True)
        self.assertEqual(options.minfds, 2048)
        self.assertEqual(options.minprocs, 300)
        self.assertEqual(options.nocleanup, True)
        self.assertEqual(len(options.programs), 3)

        cat = options.programs[0]
        self.assertEqual(cat.name, 'cat')
        self.assertEqual(cat.command, '/bin/cat')
        self.assertEqual(cat.priority, 1)
        self.assertEqual(cat.autostart, True)
        self.assertEqual(cat.autorestart, True)
        self.assertEqual(cat.startsecs, 5)
        self.assertEqual(cat.startretries, 10)
        self.assertEqual(cat.uid, 0)
        self.assertEqual(cat.logfile, '/tmp/cat.log')
        self.assertEqual(cat.stopsignal, signal.SIGKILL)
        self.assertEqual(cat.stopwaitsecs, 5)
        self.assertEqual(cat.logfile_maxbytes, datatypes.byte_size('50MB'))
        self.assertEqual(cat.logfile_backups, 10)
        self.assertEqual(cat.exitcodes, [0,2])

        cat2 = options.programs[1]
        self.assertEqual(cat2.name, 'cat2')
        self.assertEqual(cat2.command, '/bin/cat')
        self.assertEqual(cat2.priority, 999)
        self.assertEqual(cat2.autostart, True)
        self.assertEqual(cat2.autorestart, False)
        self.assertEqual(cat2.uid, None)
        self.assertEqual(cat2.logfile, '/tmp/cat2.log')
        self.assertEqual(cat2.stopsignal, signal.SIGTERM)
        self.assertEqual(cat2.logfile_maxbytes, 1024)
        self.assertEqual(cat2.logfile_backups, 2)
        self.assertEqual(cat2.exitcodes, [0,2])

        cat3 = options.programs[2]
        self.assertEqual(cat3.name, 'cat3')
        self.assertEqual(cat3.command, '/bin/cat')
        self.assertEqual(cat3.priority, 999)
        self.assertEqual(cat3.autostart, True)
        self.assertEqual(cat3.autorestart, True)
        self.assertEqual(cat3.uid, None)
        self.assertEqual(cat3.logfile, instance.AUTOMATIC)
        self.assertEqual(cat3.logfile_maxbytes, datatypes.byte_size('50MB'))
        self.assertEqual(cat3.logfile_backups, 10)
        self.assertEqual(cat3.exitcodes, [0,1,127])
        
        self.assertEqual(cat2.stopsignal, signal.SIGTERM)

        here = os.path.abspath(os.getcwd())
        self.assertEqual(instance.uid, 0)
        self.assertEqual(instance.gid, 0)
        self.assertEqual(instance.directory, '/tmp')
        self.assertEqual(instance.umask, 022)
        self.assertEqual(instance.logfile, os.path.join(here,'supervisord.log'))
        self.assertEqual(instance.logfile_maxbytes, 1000 * 1024 * 1024)
        self.assertEqual(instance.logfile_backups, 5)
        self.assertEqual(instance.loglevel, 40)
        self.assertEqual(instance.pidfile, os.path.join(here,'supervisord.pid'))
        self.assertEqual(instance.nodaemon, True)
        self.assertEqual(instance.passwdfile, None)
        self.assertEqual(instance.identifier, 'fleeb')
        self.assertEqual(instance.childlogdir, tempfile.gettempdir())
        self.assertEqual(instance.http_port.family, socket.AF_INET)
        self.assertEqual(instance.http_port.address, ('127.0.0.1', 8999))
        self.assertEqual(instance.http_username, 'chrism')
        self.assertEqual(instance.http_password, 'foo')
        self.assertEqual(instance.nocleanup, True)
        self.assertEqual(instance.minfds, 2048)
        self.assertEqual(instance.minprocs, 300)

    def test_readFile_failed(self):
        from options import readFile
        try:
            readFile('/notthere', 0, 10)
        except ValueError, inst:
            self.assertEqual(inst.args[0], 'FAILED')
        else:
            raise AssertionError("Didn't raise")

    def test_check_execv_args_cant_find_command(self):
        instance = self._makeOne()
        result = instance.check_execv_args('/not/there', None, None)
        self.assertEqual(result, "can't find command '/not/there'")

    def test_check_execv_args_notexecutable(self):
        instance = self._makeOne()
        result = instance.check_execv_args('/etc/passwd', None,
                                           os.stat('/etc/passwd'))
        self.assertEqual(result, "command at '/etc/passwd' is not executable")

    def test_check_execv_args_isdir(self):
        instance = self._makeOne()
        result = instance.check_execv_args('/', None, os.stat('/'))
        self.assertEqual(result, "command at '/' is a directory")

class TestBase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _assertRPCError(self, code, callable, *args, **kw):
        try:
            callable(*args, **kw)
        except xmlrpc.RPCError, inst:
            self.assertEqual(inst.code, code)
        else:
            raise AssertionError("Didnt raise")

class MainXMLRPCInterfaceTests(TestBase):

    def _getTargetClass(self):
        return xmlrpc.RPCInterface

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_ctor(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self.assertEqual(interface.supervisor.supervisord, supervisord)
        self.failUnless(interface.system)

    def test_traverse(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        from xmlrpc import traverse
        self._assertRPCError(xmlrpc.Faults.UNKNOWN_METHOD,
                             traverse, interface, 'notthere.hello', [])
        self._assertRPCError(xmlrpc.Faults.UNKNOWN_METHOD,
                             traverse, interface, 'supervisor._readFile', [])
        self._assertRPCError(xmlrpc.Faults.INCORRECT_PARAMETERS,
                             traverse, interface,
                             'supervisor.getIdentification', [1])
        self.assertEqual(
            traverse(interface, 'supervisor.getIdentification', []),
            'supervisor')
            
def makeExecutable(file, substitutions=None):
    if substitutions is None:
        substitutions = {}
    data = open(file).read()
    last = os.path.split(file)[1]

    substitutions['PYTHON'] = sys.executable
    for key in substitutions.keys():
        data = data.replace('<<%s>>' % key.upper(), substitutions[key])
    
    import tempfile
    tmpnam = tempfile.mktemp(prefix=last)
    f = open(tmpnam, 'w')
    f.write(data)
    f.close()
    os.chmod(tmpnam, 0755)
    return tmpnam

def makeSpew(unkillable=False):
    here = os.path.dirname(__file__)
    if not unkillable:
        return makeExecutable(os.path.join(here, 'fixtures/spew.py'))
    return makeExecutable(os.path.join(here, 'fixtures/unkillable_spew.py'))

class SupervisorNamespaceXMLRPCInterfaceTests(TestBase):
    def _getTargetClass(self):
        return xmlrpc.SupervisorNamespaceRPCInterface

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_update(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        interface._update('foo')
        self.assertEqual(interface.update_text, 'foo')
        supervisord.state = SupervisorStates.SHUTDOWN
        self._assertRPCError(xmlrpc.Faults.SHUTDOWN_STATE, interface._update,
                             'foo')

    def test_getVersion(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        version = interface.getVersion()
        self.assertEqual(version, xmlrpc.RPC_VERSION)
        self.assertEqual(interface.update_text, 'getVersion')

    def test_getIdentification(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        identifier = interface.getIdentification()
        self.assertEqual(identifier, supervisord.options.identifier)
        self.assertEqual(interface.update_text, 'getIdentification')

    def test_getState(self):
        from supervisord import getSupervisorStateDescription
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        stateinfo = interface.getState()
        statecode = supervisord.get_state()
        statename = getSupervisorStateDescription(statecode)
        self.assertEqual(stateinfo['statecode'], statecode)
        self.assertEqual(stateinfo['statename'], statename)
        self.assertEqual(interface.update_text, 'getState')

    def test_readLog_unreadable(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.NO_FILE, interface.readLog,
                             offset=0, length=1)

    def test_readLog_badargs(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        try:
            logfile = supervisord.options.logfile
            f = open(logfile, 'w+')
            f.write('x' * 2048)
            f.close()
            self._assertRPCError(xmlrpc.Faults.BAD_ARGUMENTS,
                                 interface.readLog, offset=-1, length=1)
            self._assertRPCError(xmlrpc.Faults.BAD_ARGUMENTS,
                                 interface.readLog, offset=-1,
                                 length=-1)
        finally:
            os.remove(logfile)

    def test_readLog(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        logfile = supervisord.options.logfile
        try:
            f = open(logfile, 'w+')
            f.write('x' * 2048)
            f.write('y' * 2048)
            f.close()
            data = interface.readLog(offset=0, length=0)
            self.assertEqual(interface.update_text, 'readLog')
            self.assertEqual(data, ('x' * 2048) + ('y' * 2048))
            data = interface.readLog(offset=2048, length=0)
            self.assertEqual(data, 'y' * 2048)
            data = interface.readLog(offset=0, length=2048)
            self.assertEqual(data, 'x' * 2048)
            data = interface.readLog(offset=-4, length=0)
            self.assertEqual(data, 'y' * 4)
        finally:
            os.remove(logfile)

    def test_clearLog_unreadable(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.NO_FILE, interface.clearLog)

    def test_clearLog(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        logfile = supervisord.options.logfile
        try:
            f = open(logfile, 'w+')
            f.write('x')
            f.close()
            result = interface.clearLog()
            self.assertEqual(interface.update_text, 'clearLog')
            self.assertEqual(result, True)
            self.failIf(os.path.exists(logfile))
        finally:
            try:
                os.remove(logfile)
            except:
                pass

        self.assertEqual(supervisord.options.logger.handlers[0].reopened, True)

    def test_shutdown(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        value = interface.shutdown()
        self.assertEqual(value, True)
        self.assertEqual(supervisord.mood, -1)

    def test_restart(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        value = interface.restart()
        self.assertEqual(value, True)
        self.assertEqual(supervisord.mood, 0)

    def test_startProcess_already_started(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config)
        process.pid = 10
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.ALREADY_STARTED,
                             interface.startProcess,'foo')

    def test_startProcess_badname(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.startProcess,
                             'foo')

    def test_startProcess_spawnerr(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config, ProcessStates.STOPPED)
        process.spawnerr = 'abc'
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.SPAWN_ERROR,
                             interface.startProcess,
                             'foo')

    def test_startProcess(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config, state=ProcessStates.STOPPED)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo')
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')
        self.assertEqual(callback(), http.NOT_DONE_YET)

        process.pid = 1234
        self.assertEqual(callback(done=True), True)

    def test_startProcess_abnormal_term(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config, ProcessStates.STOPPED)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo')
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')
        process.state = ProcessStates.BACKOFF
        self._assertRPCError(xmlrpc.Faults.ABNORMAL_TERMINATION,
                             callback, True)
    
    def test_startProcess_badtimeout(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_ARGUMENTS,
                             interface.startProcess, 'foo', 'flee')

    def test_startAllProcesses(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', priority=1)
        config2 = DummyPConfig('foo2', '/bin/foo2', priority=2)
        process = DummyProcess(options, config, ProcessStates.STOPPED)
        process2 = DummyProcess(options, config2, ProcessStates.STOPPED)
        supervisord = DummySupervisor({'foo':process, 'foo2':process2})
        interface = self._makeOne(supervisord)
        callback = interface.startAllProcesses()
        #process.pid = 1234
        #process2.pid = 12345
        # first process
        from http import NOT_DONE_YET
        self.assertEqual(callback(done=True), NOT_DONE_YET)
        # second process
        self.assertEqual(
            callback(done=True),
            [
            {'name':'foo', 'status': 80, 'description': 'OK'},
            {'name':'foo2', 'status': 80, 'description': 'OK'},
            ]
            )
        self.assertEqual(interface.update_text, 'startProcess')

        self.assertEqual(process.spawned, True)
        self.assertEqual(process2.spawned, True)
        

    def test_stopProcess_badname(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.stopProcess, 'foo')

    def test_stopProcess(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo')
        process = DummyProcess(options, config, ProcessStates.RUNNING)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        callback = interface.stopProcess('foo')
        self.assertEqual(interface.update_text, 'stopProcess')
        process = supervisord.processes.get('foo')
        self.assertEqual(process.backoff, 0)
        self.assertEqual(process.delay, 0)
        self.assertEqual(process.killing, 0)
        process.state = ProcessStates.STOPPING
        self.assertEqual(callback(), http.NOT_DONE_YET)
        process.state = ProcessStates.STOPPED
        self.assertEqual(callback(), True)
        self.assertEqual(len(supervisord.processes), 1)
        self.assertEqual(interface.update_text, 'stopProcess')


    def test_stopAllProcesses(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo')
        config2 = DummyPConfig('foo2', '/bin/foo2')
        process = DummyProcess(options, config, ProcessStates.RUNNING)
        process2 = DummyProcess(options, config2, ProcessStates.RUNNING)
        supervisord = DummySupervisor({'foo':process, 'foo2':process2})
        interface = self._makeOne(supervisord)
        callback = interface.stopAllProcesses()
        self.assertEqual(interface.update_text, 'stopAllProcesses')
        value = http.NOT_DONE_YET
        while 1:
            value = callback()
            if value is not http.NOT_DONE_YET:
                break

        processes = supervisord.processes
        self.assertEqual(value, [
            {'status': 80, 'name': 'foo2', 'description': 'OK'},
            {'status': 80, 'name': 'foo', 'description': 'OK'}
            ] )
        self.assertEqual(len(processes), 2)
        self.assertEqual(process.stop_called, True)
        self.assertEqual(process2.stop_called, True)

    def test_getProcessInfo(self):
        from supervisord import ProcessStates

        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', logfile='/tmp/fleeb.bar')
        process = DummyProcess(options, config)
        process.pid = 111
        process.laststart = 10
        process.laststop = 11
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        data = interface.getProcessInfo('foo')

        self.assertEqual(interface.update_text, 'getProcessInfo')
        self.assertEqual(data['logfile'], '/tmp/fleeb.bar')
        self.assertEqual(data['name'], 'foo')
        self.assertEqual(data['pid'], 111)
        self.assertEqual(data['start'], 10)
        self.assertEqual(data['stop'], 11)
        self.assertEqual(data['state'], ProcessStates.RUNNING)
        self.assertEqual(data['exitstatus'], 0)
        self.assertEqual(data['spawnerr'], '')

    def test_getAllProcessInfo(self):
        from supervisord import ProcessStates
        options = DummyOptions()

        p1config = DummyPConfig('process1', '/bin/process1', priority=1,
                                logfile='/tmp/process1.log')
        p2config = DummyPConfig('process2', '/bin/process2', priority=2,
                                logfile='/tmp/process2.log')
        process1 = DummyProcess(options, p1config)
        process1.reportstatusmsg = 'foo'
        process1.pid = 111
        process1.laststart = 10
        process1.laststop = 11
        process2 = DummyProcess(options, p2config)
        process2.reportstatusmsg = 'bar'
        process2.pid = 222
        process2.laststart = 20
        process2.laststop = 11
        supervisord = DummySupervisor({'process1':process1,
                                       'process2':process2})
        interface = self._makeOne(supervisord)

        info = interface.getAllProcessInfo()

        self.assertEqual(interface.update_text, 'getProcessInfo')
        self.assertEqual(len(info), 2)

        p1info = info[0]
        self.assertEqual(p1info['logfile'], '/tmp/process1.log')
        self.assertEqual(p1info['name'], 'process1')
        self.assertEqual(p1info['pid'], 111)
        self.assertEqual(p1info['start'], 10)
        self.assertEqual(p1info['stop'], 11)
        self.assertEqual(p1info['state'], ProcessStates.RUNNING)
        self.assertEqual(p1info['exitstatus'], 0)
        self.assertEqual(p1info['spawnerr'], '')

        p2info = info[1]
        self.assertEqual(p2info['logfile'], '/tmp/process2.log')
        self.assertEqual(p2info['name'], 'process2')
        self.assertEqual(p2info['pid'], 222)
        self.assertEqual(p2info['start'], 20)
        self.assertEqual(p2info['stop'], 11)
        self.assertEqual(p2info['state'], ProcessStates.RUNNING)
        self.assertEqual(p2info['exitstatus'], 0)
        self.assertEqual(p2info['spawnerr'], '')

    def test_readProcessLog_unreadable(self):
        options = DummyOptions()
        config = DummyPConfig('process1', '/bin/process1', priority=1,
                              logfile='/tmp/process1.log')
        process = DummyProcess(options, config)
        supervisord = DummySupervisor({'process1':process})
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.NO_FILE,
                             interface.readProcessLog,
                             'process1', offset=0, length=1)

    def test_readProcessLog_badargs(self):
        options = DummyOptions()
        config = DummyPConfig('process1', '/bin/process1', priority=1,
                              logfile='/tmp/process1.log')
        process = DummyProcess(options, config)
        supervisord = DummySupervisor({'process1':process})
        interface = self._makeOne(supervisord)

        try:
            logfile = process.config.logfile
            f = open(logfile, 'w+')
            f.write('x' * 2048)
            f.close()
            self._assertRPCError(xmlrpc.Faults.BAD_ARGUMENTS,
                                 interface.readProcessLog,
                                 'process1', offset=-1, length=1)
            self._assertRPCError(xmlrpc.Faults.BAD_ARGUMENTS,
                                 interface.readProcessLog, 'process1',
                                 offset=-1, length=-1)
        finally:
            os.remove(logfile)

    def test_readProcessLog(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', logfile='/tmp/fooooooo')
        process = DummyProcess(options, config)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        process = supervisord.processes.get('foo')
        logfile = process.config.logfile
        try:
            f = open(logfile, 'w+')
            f.write('x' * 2048)
            f.write('y' * 2048)
            f.close()
            data = interface.readProcessLog('foo', offset=0, length=0)
            self.assertEqual(interface.update_text, 'readProcessLog')
            self.assertEqual(data, ('x' * 2048) + ('y' * 2048))
            data = interface.readProcessLog('foo', offset=2048, length=0)
            self.assertEqual(data, 'y' * 2048)
            data = interface.readProcessLog('foo', offset=0, length=2048)
            self.assertEqual(data, 'x' * 2048)
            data = interface.readProcessLog('foo', offset=-4, length=0)
            self.assertEqual(data, 'y' * 4)
        finally:
            os.remove(logfile)

    def test_clearProcessLog_bad_name(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.clearProcessLog,
                             'spew')

    def test_clearProcessLog(self):
        pconfig = DummyPConfig('foo', 'foo')
        options = DummyOptions()
        process = DummyProcess(options, pconfig)
        processes = {'foo': process}
        supervisord = DummySupervisor(processes)
        interface = self._makeOne(supervisord)
        interface.clearProcessLog('foo')
        self.assertEqual(process.logsremoved, True)

    def test_clearProcessLog_failed(self):
        pconfig = DummyPConfig('foo', 'foo')
        options = DummyOptions()
        process = DummyProcess(options, pconfig)
        process.error_at_clear = True
        processes = {'foo': process}
        supervisord = DummySupervisor(processes)
        interface = self._makeOne(supervisord)
        self.assertRaises(xmlrpc.RPCError, interface.clearProcessLog, 'foo')
        

    def test_clearAllProcessLogs(self):
        pconfig = DummyPConfig('foo', 'foo')
        pconfig2 = DummyPConfig('bar', 'bar')
        options = DummyOptions()
        process = DummyProcess(options, pconfig)
        process2= DummyProcess(options, pconfig2)
        processes = {'foo': process, 'bar':process2}
        supervisord = DummySupervisor(processes)
        interface = self._makeOne(supervisord)
        callback = interface.clearAllProcessLogs()
        callback()
        callback()
        self.assertEqual(process.logsremoved, True)
        self.assertEqual(process2.logsremoved, True)

    def test_clearAllProcessLogs_onefails(self):
        pconfig = DummyPConfig('foo', 'foo')
        pconfig2 = DummyPConfig('bar', 'bar')
        options = DummyOptions()
        process = DummyProcess(options, pconfig)
        process2= DummyProcess(options, pconfig2)
        process2.error_at_clear = True
        processes = {'foo': process, 'bar':process2}
        supervisord = DummySupervisor(processes)
        interface = self._makeOne(supervisord)
        callback = interface.clearAllProcessLogs()
        callback()
        results = callback()
        self.assertEqual(process.logsremoved, True)
        self.assertEqual(process2.logsremoved, False)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], {'name':'bar',
                                      'status':xmlrpc.Faults.FAILED,
                                      'description':'FAILED: bar'})
        self.assertEqual(results[1], {'name':'foo',
                                      'status':xmlrpc.Faults.SUCCESS,
                                      'description':'OK'})

class SystemNamespaceXMLRPCInterfaceTests(TestBase):
    def _getTargetClass(self):
        return xmlrpc.SystemNamespaceRPCInterface

    def _makeOne(self):
        supervisord = DummySupervisor()
        supervisor = xmlrpc.SupervisorNamespaceRPCInterface(supervisord)
        return self._getTargetClass()(
            [('supervisor', supervisor),
             ]
            )

    def test_ctor(self):
        interface = self._makeOne()
        self.failUnless(interface.namespaces['supervisor'])
        self.failUnless(interface.namespaces['system'])

    def test_listMethods(self):
        interface = self._makeOne()
        methods = interface.listMethods()
        methods.sort()
        keys = interface._listMethods().keys()
        keys.sort()
        self.assertEqual(methods, keys)

    def test_methodSignature(self):
        interface = self._makeOne()
        self._assertRPCError(xmlrpc.Faults.SIGNATURE_UNSUPPORTED,
                             interface.methodSignature,
                             ['foo.bar'])
        result = interface.methodSignature('system.methodSignature')
        self.assertEqual(result, ['array', 'string'])

    def test_allMethodDocs(self):
        # belt-and-suspenders test for docstring-as-typing parsing correctness
        # and documentation validity vs. implementation
        import options
        _RPCTYPES = ['int', 'double', 'string', 'boolean', 'dateTime.iso8601',
                     'base64', 'binary', 'array', 'struct']
        interface = self._makeOne()
        methods = interface._listMethods()
        for k in methods.keys():
            # if a method doesn't have a @return value, an RPCError is raised.
            # Detect that here.
            try:
                interface.methodSignature(k)
            except xmlrpc.RPCError:
                raise AssertionError, ('methodSignature for %s raises '
                                       'RPCError (missing @return doc?)' % k)

            # we want to test that the number of arguments implemented in
            # the function is the same as the number of arguments implied by
            # the doc @params, and that they show up in the same order.
            ns_name, method_name = k.split('.', 1)
            namespace = interface.namespaces[ns_name]
            meth = getattr(namespace, method_name)
            code = meth.func_code
            argnames = code.co_varnames[1:code.co_argcount]
            parsed = options.gettags(str(meth.__doc__))

            plines = []
            ptypes = []
            pnames = []
            ptexts = []

            rlines = []
            rtypes = []
            rnames = []
            rtexts = []

            for thing in parsed:
                if thing[1] == 'param': # tag name
                    plines.append(thing[0]) # doc line number
                    ptypes.append(thing[2]) # data type
                    pnames.append(thing[3]) # function name
                    ptexts.append(thing[4])  # description
                elif thing[1] == 'return': # tag name
                    rlines.append(thing[0]) # doc line number
                    rtypes.append(thing[2]) # data type
                    rnames.append(thing[3]) # function name
                    rtexts.append(thing[4])  # description
                elif thing[1] is not None:
                    raise AssertionError(
                        'unknown tag type %s for %s, parsed %s' % (thing[1],
                                                                   k,
                                                                   parsed))
            # param tokens

            if len(argnames) != len(pnames):
                raise AssertionError, ('Incorrect documentation '
                                       '(%s args, %s doc params) in %s'
                                       % (len(argnames), len(pnames), k))
            for docline in plines:
                self.failUnless(type(docline) == int, (docline,
                                                       type(docline),
                                                       k,
                                                       parsed))
            for doctype in ptypes:
                self.failUnless(doctype in _RPCTYPES, doctype)
            for x in range(len(pnames)):
                if pnames[x] != argnames[x]:
                    msg = 'Name wrong: (%s vs. %s in %s)\n%s' % (pnames[x],
                                                                 argnames[x],
                                                                 k,
                                                                 parsed)
                    raise AssertionError, msg
            for doctext in ptexts:
                self.failUnless(type(doctext) == type(''), doctext)

            # result tokens
            
            if len(rlines) > 1:
                raise AssertionError(
                    'Duplicate @return values in docs for %s' % k)
            for docline in rlines:
                self.failUnless(type(docline) == int, (docline,
                                                       type(docline), k))
            for doctype in rtypes:
                self.failUnless(doctype in _RPCTYPES, doctype)
            for docname in rnames:
                self.failUnless(type(docname) == type(''), (docname,
                                                            type(docname),
                                                            k))
            for doctext in rtexts:
                self.failUnless(type(doctext) == type(''), (doctext,
                                                            type(doctext), k))

    def test_multicall_simplevals(self):
        interface = self._makeOne()
        callback = interface.multicall([
            {'methodName':'system.methodHelp', 'params':['system.methodHelp']},
            {'methodName':'system.listMethods', 'params':[]},
            ])
        result = http.NOT_DONE_YET
        while result is http.NOT_DONE_YET:
            result = callback()
        self.assertEqual(result[0], interface.methodHelp('system.methodHelp'))
        self.assertEqual(result[1], interface.listMethods())

    def test_multicall_nested_callback(self):
        interface = self._makeOne()
        callback = interface.multicall([
            {'methodName':'supervisor.stopAllProcesses'}])
        result = http.NOT_DONE_YET
        while result is http.NOT_DONE_YET:
            result = callback()
        self.assertEqual(result[0], [])

    def test_methodHelp(self):
        interface = self._makeOne()
        self._assertRPCError(xmlrpc.Faults.SIGNATURE_UNSUPPORTED,
                             interface.methodHelp,
                             ['foo.bar'])
        help = interface.methodHelp('system.methodHelp')
        self.assertEqual(help, interface.methodHelp.__doc__)

class SubprocessTests(unittest.TestCase):
    def _getTargetClass(self):
        return supervisord.Subprocess

    def _makeOne(self, *arg, **kw):
        return supervisord.Subprocess(*arg, **kw)

    def test_ctor(self):
        options = DummyOptions()
        config = DummyPConfig('cat', 'bin/cat', logfile='/tmp/temp123.log')
        instance = self._makeOne(options, config)
        self.assertEqual(instance.options, options)
        self.assertEqual(instance.config, config)
        self.assertEqual(instance.laststart, 0)
        self.assertEqual(instance.childlog.args, (
            ('/tmp/temp123.log', 20, '%(message)s'),
            {'rotating': False, 'backups': 0, 'maxbytes': 0}))
        self.assertEqual(instance.pid, 0)
        self.assertEqual(instance.laststart, 0)
        self.assertEqual(instance.laststop, 0)
        self.assertEqual(instance.delay, 0)
        self.assertEqual(instance.administrative_stop, 0)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.backoff, 0)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(instance.spawnerr, None)
        self.assertEqual(instance.logbuffer, '')

    def test_removelogs(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.removelogs()
        self.assertEqual(instance.childlog.handlers[0].reopened, True)
        self.assertEqual(instance.childlog.handlers[0].removed, True)

    def test_reopenlogs(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.reopenlogs()
        self.assertEqual(instance.childlog.handlers[0].reopened, True)

    def test_log_output(self):
        # stdout goes to the process log and the main log
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.logbuffer = 'foo'
        instance.log_output()
        self.assertEqual(instance.childlog.data, ['foo'])
        self.assertEqual(options.logger.data, [5, 'notthere output:\nfoo'])

    def test_drain_stdout(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.pipes['stdout'] = 'abc'
        instance.drain_stdout()
        self.assertEqual(instance.logbuffer, 'abc')

    def test_drain_stderr(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.pipes['stderr'] = 'abc'
        instance.drain_stderr()
        self.assertEqual(instance.logbuffer, '')

        instance.config.log_stderr = True
        instance.drain_stderr()
        self.assertEqual(instance.logbuffer, 'abc')

    def test_drain(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.config.log_stderr = True
        instance.pipes['stdout'] = 'abc'
        instance.pipes['stderr'] = 'def'
        instance.drain()
        self.assertEqual(instance.logbuffer, 'abcdef')

        instance.logbuffer = ''
        instance.config.log_stderr = False
        instance.drain()
        self.assertEqual(instance.logbuffer, 'abc')
        
    def test_get_pipe_drains(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.config.log_stderr = True
        instance.pipes['stdout'] = 'abc'
        instance.pipes['stderr'] = 'def'

        drains = instance.get_pipe_drains()
        self.assertEqual(len(drains), 2)
        self.assertEqual(drains[0], ['abc', instance.drain_stdout])
        self.assertEqual(drains[1], ['def', instance.drain_stderr])

        instance.pipes = {}
        drains = instance.get_pipe_drains()
        self.assertEqual(drains, [])
        

    def test_get_execv_args_abs_missing(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere')
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args, ('/notthere', ['/notthere'], None))

    def test_get_execv_args_abs_withquotes_missing(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere "an argument"')
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args, ('/notthere', ['/notthere', 'an argument'],
                                None))

    def test_get_execv_args_rel_missing(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', 'notthere')
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args, (None, ['notthere'], None))

    def test_get_execv_args_rel_withquotes_missing(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', 'notthere "an argument"')
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args, (None, ['notthere', 'an argument'], None))

    def test_get_execv_args_abs(self):
        executable = '/bin/sh foo'
        options = DummyOptions()
        config = DummyPConfig('sh', executable)
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args[0], '/bin/sh')
        self.assertEqual(args[1], ['/bin/sh', 'foo'])
        self.assertEqual(len(args[2]), 10)

    def test_get_execv_args_rel(self):
        executable = 'sh foo'
        options = DummyOptions()
        config = DummyPConfig('sh', executable)
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args[0], '/bin/sh')
        self.assertEqual(args[1], ['sh', 'foo'])
        self.assertEqual(len(args[2]), 10)

    def test_record_spawnerr(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.record_spawnerr('foo')
        self.assertEqual(instance.spawnerr, 'foo')
        self.assertEqual(options.logger.data[0], 'spawnerr: foo')
        self.assertEqual(instance.backoff, 1)
        self.failUnless(instance.delay)

    def test_spawn_already_running(self):
        options = DummyOptions()
        config = DummyPConfig('sh', '/bin/sh')
        instance = self._makeOne(options, config)
        instance.pid = True
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.logger.data[0], "process 'sh' already running")

    def test_spawn_fail_check_execv_args(self):
        options = DummyOptions()
        config = DummyPConfig('bad', '/bad/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'bad filename')
        self.assertEqual(options.logger.data[0], "spawnerr: bad filename")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_fail_make_pipes_emfile(self):
        options = DummyOptions()
        options.make_pipes_error = errno.EMFILE
        config = DummyPConfig('good', '/good/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr,
                         "too many open files to spawn 'good'")
        self.assertEqual(options.logger.data[0],
                         "spawnerr: too many open files to spawn 'good'")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_fail_make_pipes_other(self):
        options = DummyOptions()
        options.make_pipes_error = 1
        config = DummyPConfig('good', '/good/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'unknown error: EPERM')
        self.assertEqual(options.logger.data[0],
                         "spawnerr: unknown error: EPERM")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_fork_fail_eagain(self):
        options = DummyOptions()
        options.fork_error = errno.EAGAIN
        config = DummyPConfig('good', '/good/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr,
                         "Too many processes in process table to spawn 'good'")
        self.assertEqual(options.logger.data[0],
             "spawnerr: Too many processes in process table to spawn 'good'")
        self.assertEqual(len(options.pipes_closed), 6)
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_fork_fail_other(self):
        options = DummyOptions()
        options.fork_error = 1
        config = DummyPConfig('good', '/good/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, 'unknown error: EPERM')
        self.assertEqual(options.logger.data[0],
                         "spawnerr: unknown error: EPERM")
        self.assertEqual(len(options.pipes_closed), 6)
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_as_child_setuid_ok(self):
        options = DummyOptions()
        options.forkpid = 0
        config = DummyPConfig('good', '/good/filename', uid=1)
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.written, {})
        self.assertEqual(options.privsdropped, 1)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_setuid_fail(self):
        options = DummyOptions()
        options.forkpid = 0
        options.setuid_msg = 'screwed'
        config = DummyPConfig('good', '/good/filename', uid=1)
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.written,
             {1: ['good: error trying to setuid to 1!\n', 'good: screwed\n']})
        self.assertEqual(options.privsdropped, None)
        self.assertEqual(options.execv_args,
                         ('/good/filename', ['/good/filename']) )
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_execv_fail_oserror(self):
        options = DummyOptions()
        options.forkpid = 0
        options.execv_error = 1
        config = DummyPConfig('good', '/good/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(options.written,
                         {1: ["couldn't exec /good/filename: EPERM\n"]})
        self.assertEqual(options.privsdropped, None)
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_child_execv_fail_runtime_error(self):
        options = DummyOptions()
        options.forkpid = 0
        options.execv_error = 2
        config = DummyPConfig('good', '/good/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.pipes_closed, None)
        self.assertEqual(options.pgrp_set, True)
        self.assertEqual(len(options.duped), 3)
        self.assertEqual(len(options.fds_closed), options.minfds - 3)
        self.assertEqual(len(options.written), 1)
        self.failUnless(options.written[1][0].startswith(
         "couldn't exec /good/filename: exceptions.RuntimeError, 2: "
         "file: test.py line:"))
        self.assertEqual(options.privsdropped, None)
        self.assertEqual(options._exitcode, 127)

    def test_spawn_as_parent(self):
        options = DummyOptions()
        options.forkpid = 10
        config = DummyPConfig('good', '/good/filename')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, 10)
        self.assertEqual(options.pipes_closed, None)
        self.assertEqual(len(options.fds_closed), 3)
        self.assertEqual(options.logger.data[0], "spawned: 'good' with pid 10")
        self.assertEqual(instance.spawnerr, None)
        self.failUnless(instance.delay)
        self.assertEqual(instance.options.pidhistory[10], instance)

    def dont_test_spawn_and_kill(self):
        # this is a functional test
        try:
            called = 0
            def foo(*args):
                called = 1
            signal.signal(signal.SIGCHLD, foo)
            executable = makeSpew()
            options = DummyOptions()
            config = DummyPConfig('spew', executable)
            instance = self._makeOne(options, config)
            result = instance.spawn()
            msg = options.logger.data[0]
            self.failUnless(msg.startswith("spawned: 'spew' with pid"))
            self.assertEqual(len(instance.pipes), 6)
            self.failUnless(instance.pid)
            self.failUnlessEqual(instance.pid, result)
            origpid = instance.pid
            while 1:
                try:
                    data = os.popen('ps').read()
                    break
                except IOError, why:
                    if why[0] != errno.EINTR:
                        raise
                        # try again ;-)
            time.sleep(0.1) # arbitrary, race condition possible
            self.failUnless(data.find(`origpid`) != -1 )
            msg = instance.kill(signal.SIGTERM)
            time.sleep(0.1) # arbitrary, race condition possible
            self.assertEqual(msg, None)
            pid, sts = os.waitpid(-1, os.WNOHANG)
            data = os.popen('ps').read()
            self.assertEqual(data.find(`origpid`), -1) # dubious
        finally:
            try:
                os.remove(executable)
            except:
                pass
            signal.signal(signal.SIGCHLD, signal.SIG_DFL)

    def test_stop(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.pid = 11
        instance.stop()
        self.assertEqual(instance.administrative_stop, 1)
        self.failUnless(instance.delay)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11)')
        self.assertEqual(instance.killing, 1)
        self.assertEqual(options.kills[11], signal.SIGTERM)

    def test_kill_nopid(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0],
              'attempted to kill test with sig SIGTERM but it wasn\'t running')
        self.assertEqual(instance.killing, 0)

    def test_kill_error(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        options.kill_error = 1
        instance = self._makeOne(options, config)
        instance.pid = 11
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11)')
        self.failUnless(options.logger.data[1].startswith(
            'unknown problem killing test'))
        self.assertEqual(instance.killing, 0)

    def test_kill(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.pid = 11
        instance.kill(signal.SIGTERM)
        self.assertEqual(options.logger.data[0], 'killing test (pid 11)')
        self.assertEqual(instance.killing, 1)
        self.assertEqual(options.kills[11], signal.SIGTERM)

    def test_finish(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.waitstatus = (123, 1) # pid, waitstatus
        instance.options.pidhistory[123] = instance
        instance.killing = 1
        instance.pipes = {'stdout':'','stderr':''}
        instance.finish(123, 1)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(instance.pipes, {})
        self.assertEqual(options.logger.data[0], 'killed: notthere '
                         '(terminated by SIGHUP)')
        self.assertEqual(instance.exitstatus, -1)

    def test_set_uid_no_uid(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test')
        instance = self._makeOne(options, config)
        instance.set_uid()
        self.assertEqual(options.privsdropped, None)

    def test_set_uid(self):
        options = DummyOptions()
        config = DummyPConfig('test', '/test', uid=1)
        instance = self._makeOne(options, config)
        msg = instance.set_uid()
        self.assertEqual(options.privsdropped, 1)
        self.assertEqual(msg, None)

    def test_cmp_bypriority(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo',
                              priority=1)
        instance = self._makeOne(options, config)

        config = DummyPConfig('notthere1', '/notthere', logfile='/tmp/foo',
                              priority=2)
        instance1 = self._makeOne(options, config)

        config = DummyPConfig('notthere2', '/notthere', logfile='/tmp/foo',
                              priority=3)
        instance2 = self._makeOne(options, config)

        L = [instance2, instance, instance1]
        L.sort()

        self.assertEqual(L, [instance, instance1, instance2])

    def test_get_state(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        from supervisord import ProcessStates

        instance = self._makeOne(options, config)
        instance.killing = True
        self.assertEqual(instance.get_state(), ProcessStates.STOPPING)

        instance = self._makeOne(options, config)
        instance.laststart = 1
        instance.delay = 1
        self.assertEqual(instance.get_state(), ProcessStates.STARTING)

        instance = self._makeOne(options, config)
        instance.laststart = 1
        instance.pid = 11
        self.assertEqual(instance.get_state(), ProcessStates.RUNNING)
        
        instance = self._makeOne(options, config)
        instance.system_stop = True
        self.assertEqual(instance.get_state(), ProcessStates.FATAL)

        instance = self._makeOne(options, config)
        instance.administrative_stop = True
        self.assertEqual(instance.get_state(), ProcessStates.STOPPED)
        
        instance = self._makeOne(options, config)
        instance.laststart = 1
        instance.exitstatus = 1
        self.assertEqual(instance.get_state(), ProcessStates.EXITED)

        instance = self._makeOne(options, config)
        instance.laststart = 1
        instance.backoff = 1
        self.assertEqual(instance.get_state(), ProcessStates.BACKOFF)

        instance = self._makeOne(options, config)
        instance.laststart = 1
        self.assertEqual(instance.get_state(), ProcessStates.UNKNOWN)

class XMLRPCMarshallingTests(unittest.TestCase):
    def test_xmlrpc_marshal(self):
        import xmlrpclib
        data = xmlrpc.xmlrpc_marshal(1)
        self.assertEqual(data, xmlrpclib.dumps((1,), methodresponse=True))
        fault = xmlrpclib.Fault(1, 'foo')
        data = xmlrpc.xmlrpc_marshal(fault)
        self.assertEqual(data, xmlrpclib.dumps(fault))

class LogtailHandlerTests(unittest.TestCase):
    def _getTargetClass(self):
        from http import logtail_handler
        return logtail_handler

    def _makeOne(self, supervisord):
        return self._getTargetClass()(supervisord)

    def test_handle_request_logfile_none(self):
        supervisor = DummySupervisor()
        pconfig = DummyPConfig('foo', 'foo', None)
        options = DummyOptions()
        supervisor.processes = {'foo':DummyProcess(options, pconfig)}
        handler = self._makeOne(supervisor)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request_logfile_missing(self):
        supervisor = DummySupervisor()
        pconfig = DummyPConfig('foo', 'foo', 'it/is/missing')
        options = DummyOptions()
        supervisor.processes = {'foo':DummyProcess(options, pconfig)}
        handler = self._makeOne(supervisor)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, 410)

    def test_handle_request(self):
        supervisor = DummySupervisor()
        f = tempfile.NamedTemporaryFile()
        t = f.name
        options = DummyOptions()
        pconfig = DummyPConfig('foo', 'foo', logfile=t)
        supervisor.processes = {'foo':DummyProcess(options, pconfig)}
        handler = self._makeOne(supervisor)
        request = DummyRequest('/logtail/foo', None, None, None)
        handler.handle_request(request)
        self.assertEqual(request._error, None)
        from medusa import http_date
        self.assertEqual(request.headers['Last-Modified'],
                         http_date.build_http_date(os.stat(t)[stat.ST_MTIME]))
        self.assertEqual(request.headers['Content-Type'], 'text/plain')
        self.assertEqual(len(request.producers), 1)
        self.assertEqual(request._done, True)

class SupervisordTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisord import Supervisor
        return Supervisor

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test_main(self):
        options = DummyOptions()
        supervisord = self._makeOne(options)
        pconfig = DummyPConfig('foo', 'foo', '/bin/foo')
        options.programs = [pconfig]
        supervisord.main(args='abc', test=True, first=True)
        self.assertEqual(options.realizeargs, 'abc')
        self.assertEqual(options.fds_cleaned_up, True)
        self.assertEqual(options.rlimits_set, True)
        self.assertEqual(options.make_logger_messages,
                         (['setuid_called'], ['rlimits_set']))
        self.assertEqual(options.autochildlogdir_cleared, True)
        self.assertEqual(options.autochildlogs_created, True)
        self.assertEqual(len(supervisord.processes), 1)
        self.assertEqual(supervisord.processes['foo'].options, options)
        self.assertEqual(options.pidfile_written, True)
        self.assertEqual(options.httpserver_opened, True)
        self.assertEqual(options.signals_set, True)
        self.assertEqual(options.daemonized, True)
        self.assertEqual(options.cleaned_up, True)

    def test_get_state(self):
        from supervisord import SupervisorStates
        options = DummyOptions()
        supervisord = self._makeOne(options)
        self.assertEqual(supervisord.get_state(), SupervisorStates.ACTIVE)
        supervisord.mood = -1
        self.assertEqual(supervisord.get_state(), SupervisorStates.SHUTDOWN)

    def test_start_necessary(self):
        from supervisord import ProcessStates
        options = DummyOptions()
        pconfig1 = DummyPConfig('killed', 'killed', '/bin/killed')
        process1 = DummyProcess(options, pconfig1, ProcessStates.EXITED)
        pconfig2 = DummyPConfig('error', 'error', '/bin/error')
        process2 = DummyProcess(options, pconfig2, ProcessStates.FATAL)
        pconfig3 = DummyPConfig('notstarted', 'notstarted', '/bin/notstarted',
                                autostart=True)
        process3 = DummyProcess(options, pconfig3, ProcessStates.STOPPED)
        pconfig4 = DummyPConfig('wontstart', 'wonstart', '/bin/wontstart',
                                autostart=True)
        process4 = DummyProcess(options, pconfig4, ProcessStates.BACKOFF)
        pconfig5 = DummyPConfig('backingoff', 'backingoff', '/bin/backingoff',
                                autostart=True)
        process5 = DummyProcess(options, pconfig5, ProcessStates.BACKOFF)
        now = time.time()
        process5.delay = now + 1000

        supervisord = self._makeOne(options)
        supervisord.processes = {'killed': process1, 'error': process2,
                                 'notstarted':process3, 'wontstart':process4,
                                 'backingoff':process5}
        supervisord.start_necessary()
        self.assertEqual(process1.spawned, True)
        self.assertEqual(process2.spawned, False)
        self.assertEqual(process3.spawned, True)
        self.assertEqual(process4.spawned, True)
        self.assertEqual(process5.spawned, False)

    def test_stop_all(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPED)
        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.RUNNING)
        pconfig3 = DummyPConfig('process3', 'process3', '/bin/process3')
        process3 = DummyProcess(options, pconfig3, state=ProcessStates.BACKOFF)
        pconfig4 = DummyPConfig('process4', 'process4', '/bin/process4')
        process4 = DummyProcess(options, pconfig4, state=ProcessStates.STARTING)
        supervisord = self._makeOne(options)
        supervisord.processes = {'process1': process1, 'process2': process2,
                                 'process3':process3, 'process4':process4}

        supervisord.stop_all()
        self.assertEqual(process1.stop_called, False)
        self.assertEqual(process2.stop_called, True)
        self.assertEqual(process1.backoff, 0)
        self.assertEqual(process2.backoff, 0)
        self.assertEqual(process3.backoff, 1000)
        self.assertEqual(process4.backoff, 1000)
        
    def test_give_up(self):
        options = DummyOptions()

        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.BACKOFF)
        process1.backoff = 10000
        process1.delay = 1
        process1.system_stop = 0

        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.BACKOFF)
        process2.backoff = 1
        process2.delay = 1
        process2.system_stop = 0

        pconfig3 = DummyPConfig('process3', 'process3', '/bin/process3')
        process3 = DummyProcess(options, pconfig3, state=ProcessStates.RUNNING)
        process3.delay = 5

        supervisord = self._makeOne(options)
        supervisord.processes = { 'process1': process1, 'process2': process2,
                                  'process3':process3 }

        supervisord.give_up()
        self.assertEqual(process1.backoff, 0)
        self.assertEqual(process1.delay, 0)
        self.assertEqual(process1.system_stop, 1)
        self.assertEqual(process2.backoff, 1)
        self.assertEqual(process2.delay, 1)
        self.assertEqual(process2.system_stop, 0)
        self.assertEqual(process3.delay, 0)

    def test_get_undead(self):
        options = DummyOptions()

        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1

        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.STOPPING)
        process2.delay = time.time() + 1000

        pconfig3 = DummyPConfig('process3', 'process3', '/bin/process3')
        process3 = DummyProcess(options, pconfig3, state=ProcessStates.RUNNING)

        supervisord = self._makeOne(options)
        supervisord.processes = { 'process1': process1, 'process2': process2,
                                  'process3':process3 }

        undead = supervisord.get_undead()
        self.assertEqual(undead, [process1])

    def test_kill_undead(self):
        options = DummyOptions()

        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1

        pconfig2 = DummyPConfig('process2', 'process2', '/bin/process2')
        process2 = DummyProcess(options, pconfig2, state=ProcessStates.STOPPING)
        process2.delay = time.time() + 1000

        supervisord = self._makeOne(options)
        supervisord.processes = { 'process1': process1, 'process2': process2}

        supervisord.kill_undead()
        self.assertEqual(process1.killed_with, signal.SIGKILL)

    def test_reap(self):
        options = DummyOptions()
        options.waitpid_return = 1, 1
        pconfig = DummyPConfig('process', 'process', '/bin/process1')
        process = DummyProcess(options, pconfig)
        process.drained = False
        process.killing = 1
        process.laststop = None
        process.waitstatus = None, None
        options.pidhistory = {1:process}
        supervisord = self._makeOne(options)
        
        supervisord.reap(once=True)
        self.assertEqual(process.finished, (1,1))

    def test_handle_sigterm(self):
        options = DummyOptions()
        options.signal = signal.SIGTERM
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, -1)
        self.assertEqual(options.logger.data[0],
                         'received SIGTERM indicating exit request')

    def test_handle_sigint(self):
        options = DummyOptions()
        options.signal = signal.SIGINT
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, -1)
        self.assertEqual(options.logger.data[0],
                         'received SIGINT indicating exit request')

    def test_handle_sigquit(self):
        options = DummyOptions()
        options.signal = signal.SIGQUIT
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, -1)
        self.assertEqual(options.logger.data[0],
                         'received SIGQUIT indicating exit request')

    def test_handle_sighup(self):
        options = DummyOptions()
        options.signal = signal.SIGHUP
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, 0)
        self.assertEqual(options.logger.data[0],
                         'received SIGHUP indicating restart request')

    def test_handle_sigusr2(self):
        options = DummyOptions()
        options.signal = signal.SIGUSR2
        pconfig1 = DummyPConfig('process1', 'process1', '/bin/process1')
        process1 = DummyProcess(options, pconfig1, state=ProcessStates.STOPPING)
        process1.delay = time.time() - 1
        supervisord = self._makeOne(options)
        supervisord.processes = {'process1':process1}
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, 1)
        self.assertEqual(options.logs_reopened, True)
        self.assertEqual(process1.logs_reopened, True)
        self.assertEqual(options.logger.data[0],
                         'received SIGUSR2 indicating log reopen request')

    def test_handle_unknown_signal(self):
        options = DummyOptions()
        options.signal = signal.SIGUSR1
        supervisord = self._makeOne(options)
        supervisord.handle_signal()
        self.assertEqual(supervisord.mood, 1)
        self.assertEqual(options.logger.data[0],
                         'received SIGUSR1 indicating nothing')
        

class ControllerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisorctl import Controller
        return Controller

    def _makeOne(self, options):
        return self._getTargetClass()(options)

    def test_ctor(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        self.assertEqual(controller.prompt, options.prompt + '> ')

    def test__upcheck(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        result = controller._upcheck()
        self.assertEqual(result, True)

    def test_onecmd(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.onecmd('help')
        self.assertEqual(result, None)
        self.failUnless(
            controller.stdout.getvalue().find('Documented commands') != -1
            )

    def test_tail_noname(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: too few arguments')

    def test_tail_toomanyargs(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('one two three')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(lines[0], 'Error: too many arguments')

    def test_tail_onearg(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('foo')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 12)
        self.assertEqual(lines[0], 'output line')

    def test_tail_twoargs(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_tail('-10 foo')
        self.assertEqual(result, None)
        lines = controller.stdout.getvalue().split('\n')
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], 'tput line')

    def test_status_oneprocess(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_status('foo')
        self.assertEqual(result, None)
        expected = "foo            RUNNING    pid 11, uptime 0:01:40\n"
        self.assertEqual(controller.stdout.getvalue(), expected)

    def test_status_allprocesses(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_status('')
        self.assertEqual(result, None)
        expected = """\
foo            RUNNING    pid 11, uptime 0:01:40
bar            FATAL      screwed
baz            STOPPED    Jun 26 07:42 PM
"""
        self.assertEqual(controller.stdout.getvalue(), expected)

    def test_start_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('')
        self.assertEqual(result, None)
        expected = "Error: start requires a process name"
        self.assertEqual(controller.stdout.getvalue().split('\n')[0], expected)

    def test_start_badname(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_start_alreadystarted(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('ALREADY_STARTED')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'ALREADY_STARTED: ERROR (already started)\n')

    def test_start_spawnerror(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('SPAWN_ERROR')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'SPAWN_ERROR: ERROR (spawn error)\n')

    def test_start_one_success(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('foo')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), 'foo: started\n')

    def test_start_many(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'foo: started\nbar: started\n')

    def test_start_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_start('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
                'foo: started\nfoo2: started\nfailed: ERROR (spawn error)\n')


    def test_stop_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('')
        self.assertEqual(result, None)
        expected = "Error: stop requires a process name"
        self.assertEqual(controller.stdout.getvalue().split('\n')[0], expected)

    def test_stop_badname(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_stop_notrunning(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('NOT_RUNNING')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'NOT_RUNNING: ERROR (not running)\n')

    def test_stop_one_success(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('foo')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), 'foo: stopped\n')

    def test_stop_many(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'foo: stopped\nbar: stopped\n')

    def test_stop_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_stop('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
         'foo: stopped\nfoo2: stopped\nfailed: ERROR (no such process)\n')

    def test_restart_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_restart('')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue().split('\n')[0],
         'Error: restart requires a process name')

    def test_restart_one(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_restart('foo')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
                         'foo: stopped\nfoo: started\n')

    def test_restart_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_restart('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
                         ('foo: stopped\nfoo2: stopped\n'
                          'failed: ERROR (no such process)\n'
                          'foo: started\nfoo2: started\n'
                          'failed: ERROR (spawn error)\n'))

    def test_reload_fail(self):
        options = DummyClientOptions()
        options.interactive = False
        options._server.supervisor._restartable = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_reload('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._restarted, False)
        
    def test_reload(self):
        options = DummyClientOptions()
        options.interactive = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_reload('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._restarted, True)
        
    def test_shutdown_fail(self):
        options = DummyClientOptions()
        options.interactive = False
        options._server.supervisor._restartable = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._shutdown, False)

    def test_shutdown(self):
        options = DummyClientOptions()
        options.interactive = False
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_shutdown('')
        self.assertEqual(result, None)
        self.assertEqual(options._server.supervisor._shutdown, True)





    def test_clear_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('')
        self.assertEqual(result, None)
        expected = "Error: clear requires a process name"
        self.assertEqual(controller.stdout.getvalue().split('\n')[0], expected)

    def test_clear_badname(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('BAD_NAME')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'BAD_NAME: ERROR (no such process)\n')

    def test_clear_one_success(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('foo')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), 'foo: cleared\n')

    def test_clear_many(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('foo bar')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'foo: cleared\nbar: cleared\n')

    def test_clear_all(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_clear('all')
        self.assertEqual(result, None)

        self.assertEqual(controller.stdout.getvalue(),
         'foo: cleared\nfoo2: cleared\nfailed: ERROR (failed)\n')

    def test_open_fail(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_open('badname')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(),
                         'ERROR: url must be http:// or unix://\n')

    def test_open_succeed(self):
        options = DummyClientOptions()
        controller = self._makeOne(options)
        controller.stdout = StringIO()
        result = controller.do_open('http://localhost:9002')
        self.assertEqual(result, None)
        self.assertEqual(controller.stdout.getvalue(), """\
foo            RUNNING    pid 11, uptime 0:01:40
bar            FATAL      screwed
baz            STOPPED    Jun 26 07:42 PM
""")
        
class TailFProducerTests(unittest.TestCase):
    def _getTargetClass(self):
        from http import tail_f_producer
        return tail_f_producer

    def _makeOne(self, request, filename, head):
        return self._getTargetClass()(request, filename, head)

    def test_handle_more(self):
        request = DummyRequest('/logtail/foo', None, None, None)
        f = tempfile.NamedTemporaryFile()
        f.write('a' * 80)
        f.flush()
        t = f.name
        producer = self._makeOne(request, t, 80)
        result = producer.more()
        self.assertEqual(result, 'a' * 80)
        f.write('w' * 100)
        f.flush()
        result = producer.more()
        self.assertEqual(result, 'w' * 100)
        result = producer.more()
        self.assertEqual(result, http.NOT_DONE_YET)
        f.truncate(0)
        f.flush()
        result = producer.more()
        self.assertEqual(result, '==> File truncated <==\n')

class DummyProcess:
    # Initial state; overridden by instance variables
    pid = 0 # Subprocess pid; 0 when not running
    laststart = 0 # Last time the subprocess was started; 0 if never
    laststop = 0  # Last time the subprocess was stopped; 0 if never
    delay = 0 # If nonzero, delay starting or killing until this time
    administrative_stop = 0 # true if the process has been stopped by an admin
    system_stop = 0 # true if the process has been stopped by the system
    killing = 0 # flag determining whether we are trying to kill this proc
    backoff = 0 # backoff counter (to backofflimit)
    waitstatus = None
    exitstatus = None
    pipes = None
    childlog = None # the current logger 
    spawnerr = None
    logbuffer = '' # buffer of characters to send to child process' stdin
    
    def __init__(self, options, config, state=ProcessStates.RUNNING):
        self.options = options
        self.config = config
        self.childlog = DummyLogger()
        self.logsremoved = False
        self.stop_called = False
        self.backoff_secs = None
        self.spawned = False
        self.state = state
        self.error_at_clear = False
        self.killed_with = None
        self.drained = False
        self.logbuffer = ''
        self.logged = ''
        self.pipes = {}
        self.finished = None
        self.logs_reopened = False

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
        self.state = ProcessStates.STOPPED

    def kill(self, signal):
        self.killed_with = signal

    def spawn(self):
        self.spawned = True
        self.state = ProcessStates.RUNNING

    def drain(self):
        self.drained = True

    def get_pipe_drains(self):
        return []

    def __cmp__(self, other):
        return cmp(self.config.priority, other.config.priority)

    def readable_fds(self):
        return []

    def log_output(self):
        self.logged = self.logged + self.logbuffer
        self.logbuffer = ''

    def finish(self, pid, sts):
        self.finished = pid, sts

class DummyPConfig:
    def __init__(self, name, command, priority=999, autostart=True,
                 autorestart=True, startsecs=10, startretries=999,
                 uid=None, logfile=None, logfile_backups=0,
                 logfile_maxbytes=0, log_stdout=True, log_stderr=False,
                 stopsignal=signal.SIGTERM, stopwaitsecs=10,
                 exitcodes=[0,2]):
        self.name = name
        self.command = command
        self.priority = priority
        self.autostart = autostart
        self.autorestart = autorestart
        self.startsecs = startsecs
        self.startretries = startretries
        self.uid = uid
        self.logfile = logfile
        self.logfile_backups = logfile_backups
        self.logfile_maxbytes = logfile_maxbytes
        self.log_stdout = log_stdout
        self.log_stderr = log_stderr
        self.stopsignal = stopsignal
        self.stopwaitsecs = stopwaitsecs
        self.exitcodes = exitcodes
        

class DummyLogger:
    def __init__(self):
        self.reopened = False
        self.removed = False
        self.closed = False
        self.data = []

    def info(self, *args):
        for arg in args:
            self.data.append(arg)
    log = debug = critical = trace = info
    def reopen(self):
        self.reopened = True
    def close(self):
        self.closed = True
    def remove(self):
        self.removed = True

class DummyOptions:

    TRACE = 5
    make_pipes_error = None
    fork_error = None
    execv_error = None
    kill_error = None
    minfds = 5

    def __init__(self):
        self.identifier = 'supervisor'
        self.childlogdir = '/tmp'
        self.uid = 999
        self.logger = self.getLogger()
        self.backofflimit = 10
        self.logfile = '/tmp/logfile'
        self.nocleanup = False
        self.pidhistory = {}
        self.programs = []
        self.nodaemon = False
        self.socket_map = {}
        self.mood = 1
        self.mustreopen = False
        self.realizeargs = None
        self.fds_cleaned_up = False
        self.rlimit_set = False
        self.setuid_called = False
        self.httpserver_opened = False
        self.signals_set = False
        self.daemonized = False
        self.make_logger_messages = None
        self.autochildlogs_created = False
        self.autochildlogdir_cleared = False
        self.cleaned_up = False
        self.pidfile_written = False
        self.directory = None
        self.waitpid_return = None, None
        self.kills = {}
        self.signal = None
        self.pipes_closed = None
        self.forkpid = 0
        self.pgrp_set = None
        self.duped = {}
        self.written = {}
        self.fds_closed = []
        self._exitcode = None
        self.execv_args = None
        self.setuid_msg = None
        self.privsdropped = None
        self.logs_reopened = False

    def getLogger(self, *args, **kw):
        logger = DummyLogger()
        logger.handlers = [DummyLogger()]
        logger.args = args, kw
        return logger

    def realize(self, args):
        self.realizeargs = args

    def cleanup_fds(self):
        self.fds_cleaned_up = True

    def set_rlimits(self):
        self.rlimits_set = True
        return ['rlimits_set']

    def set_uid(self):
        self.setuid_called = True
        return 'setuid_called'

    def openhttpserver(self, supervisord):
        self.httpserver_opened = True

    def daemonize(self):
        self.daemonized = True

    def setsignals(self):
        self.signals_set = True

    def get_socket_map(self):
        return self.socket_map

    def make_logger(self, critical_msgs, info_msgs):
        self.make_logger_messages = critical_msgs, info_msgs

    def create_autochildlogs(self):
        self.autochildlogs_created = True

    def clear_autochildlogdir(self):
        self.autochildlogdir_cleared = True

    def cleanup(self):
        self.cleaned_up = True

    def write_pidfile(self):
        self.pidfile_written = True

    def waitpid(self):
        return self.waitpid_return

    def make_process(self, config):
        return DummyProcess(self, config)

    def kill(self, pid, sig):
        if self.kill_error:
            raise OSError(self.kill_error)
        self.kills[pid] = sig

    def stat(self, filename):
        return os.stat(filename)

    def get_path(self):
        return ["/bin", "/usr/bin", "/usr/local/bin"]

    def check_execv_args(self, filename, argv, st):
        if filename == '/bad/filename':
            return 'bad filename'
        return None

    def make_pipes(self):
        if self.make_pipes_error:
            raise OSError(self.make_pipes_error)
        pipes = {}
        pipes['child_stdin'], pipes['stdin'] = (3, 4)
        pipes['stdout'], pipes['child_stdout'] = (5, 6)
        pipes['stderr'], pipes['child_stderr'] = (7, 8)
        return pipes

    def fork(self):
        if self.fork_error:
            raise OSError(self.fork_error)
        return self.forkpid

    def close_fd(self, fd):
        self.fds_closed.append(fd)

    def close_pipes(self, pipes):
        self.pipes_closed = pipes

    def setpgrp(self):
        self.pgrp_set = True

    def dup2(self, frm, to):
        self.duped[frm] = to

    def write(self, fd, data):
        old_data = self.written.setdefault(fd, [])
        old_data.append(data)

    def _exit(self, code):
        self._exitcode = code

    def execv(self, filename, argv):
        if self.execv_error:
            if self.execv_error == 1:
                raise OSError(self.execv_error)
            else:
                raise RuntimeError(self.execv_error)
        self.execv_args = (filename, argv)

    def dropPrivileges(self, uid):
        if self.setuid_msg:
            return self.setuid_msg
        self.privsdropped = uid

    def readfd(self, fd):
        return fd

    def reopenlogs(self):
        self.logs_reopened = True
        

class DummyClientOptions:
    def __init__(self):
        self.prompt = 'supervisor'
        self.serverurl = 'http://localhost:9001'
        self.username = 'chrism'
        self.password = '123'
        self._server = DummyRPCServer()

    def getServerProxy(self):
        return self._server

_NOW = 1151365354

class DummySupervisorRPCNamespace:
    _restartable = True
    _restarted = False
    _shutdown = False

    def getVersion(self):
        return '1.0'

    def readProcessLog(self, name, offset, length):
        a = 'output line\n' * 10
        return a[offset:]

    def getAllProcessInfo(self):
        return [
            {
            'name':'foo',
            'pid':11,
            'state':ProcessStates.RUNNING,
            'start':_NOW - 100,
            'stop':0,
            'spawnerr':'',
            'reportstatusmsg':'',
            'now':_NOW,
             },
            {
            'name':'bar',
            'pid':12,
            'state':ProcessStates.FATAL,
            'start':_NOW - 100,
            'stop':_NOW - 50,
            'spawnerr':'screwed',
            'reportstatusmsg':'statusmsg',
            'now':_NOW,
             },
            {
            'name':'baz',
            'pid':12,
            'state':ProcessStates.STOPPED,
            'start':_NOW - 100,
            'stop':_NOW - 25,
            'spawnerr':'',
            'reportstatusmsg':'OK',
            'now':_NOW,
             },
            ]
                

    def getProcessInfo(self, name):
        return {
            'name':'foo',
            'pid':11,
            'state':ProcessStates.RUNNING,
            'start':_NOW - 100,
            'stop':0,
            'spawnerr':'',
            'reportstatusmsg':'',
            'now':_NOW,
             }

    def startProcess(self, name):
        from xmlrpclib import Fault
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        if name == 'ALREADY_STARTED':
            raise Fault(xmlrpc.Faults.ALREADY_STARTED, 'ALREADY_STARTED')
        if name == 'SPAWN_ERROR':
            raise Fault(xmlrpc.Faults.SPAWN_ERROR, 'SPAWN_ERROR')
        return True

    def startAllProcesses(self):
        return [
            {'name':'foo', 'status': xmlrpc.Faults.SUCCESS,'description': 'OK'},
            {'name':'foo2', 'status':xmlrpc.Faults.SUCCESS,'description': 'OK'},
            {'name':'failed', 'status':xmlrpc.Faults.SPAWN_ERROR,
             'description':'SPAWN_ERROR'}
            ]

    def stopProcess(self, name):
        from xmlrpclib import Fault
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        if name == 'NOT_RUNNING':
            raise Fault(xmlrpc.Faults.NOT_RUNNING, 'NOT_RUNNING')
        return True
    
    def stopAllProcesses(self):
        return [
            {'name':'foo','status': xmlrpc.Faults.SUCCESS,'description': 'OK'},
            {'name':'foo2', 'status':xmlrpc.Faults.SUCCESS,'description': 'OK'},
            {'name':'failed', 'status':xmlrpc.Faults.BAD_NAME,
             'description':'FAILED'}
            ]

    def restart(self):
        if self._restartable:
            self._restarted = True
            return
        from xmlrpclib import Fault
        raise Fault(xmlrpc.Faults.SHUTDOWN_STATE, '')

    def shutdown(self):
        if self._restartable:
            self._shutdown = True
            return
        from xmlrpclib import Fault
        raise Fault(xmlrpc.Faults.SHUTDOWN_STATE, '')

    def clearProcessLog(self, name):
        from xmlrpclib import Fault
        if name == 'BAD_NAME':
            raise Fault(xmlrpc.Faults.BAD_NAME, 'BAD_NAME')
        return True

    def clearAllProcessLogs(self):
        return [
            {'name':'foo', 'status':xmlrpc.Faults.SUCCESS,'description': 'OK'},
            {'name':'foo2', 'status':xmlrpc.Faults.SUCCESS,'description': 'OK'},
            {'name':'failed','status':xmlrpc.Faults.FAILED,
             'description':'FAILED'}
            ]
        
        

class DummySystemRPCNamespace:
    pass

class DummyRPCServer:
    def __init__(self):
        self.supervisor = DummySupervisorRPCNamespace()
        self.system = DummySystemRPCNamespace()

class DummySupervisor:
    def __init__(self, processes=None, state=SupervisorStates.ACTIVE):
        if processes is None:
            processes = {}
        self.processes = processes
        self.options = DummyOptions()
        self.state = state

    def get_state(self):
        return self.state

class DummyRequest:
    command = 'GET'
    _error = None
    _done = False
    def __init__(self, path, params, query, fragment):
        self.args = path, params, query, fragment
        self.producers = []
        self.headers = {}

    def split_uri(self):
        return self.args

    def error(self, code):
        self._error = code

    def push(self, producer):
        self.producers.append(producer)

    def __setitem__(self, header, value):
        self.headers[header] = value

    def done(self):
        self._done = True
        
def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SupervisordTests))
    suite.addTest(unittest.makeSuite(ControllerTests))
    suite.addTest(unittest.makeSuite(ServerOptionsTests))
    suite.addTest(unittest.makeSuite(SupervisorNamespaceXMLRPCInterfaceTests))
    suite.addTest(unittest.makeSuite(MainXMLRPCInterfaceTests))
    suite.addTest(unittest.makeSuite(SystemNamespaceXMLRPCInterfaceTests))
    suite.addTest(unittest.makeSuite(SubprocessTests))
    suite.addTest(unittest.makeSuite(XMLRPCMarshallingTests))
    suite.addTest(unittest.makeSuite(LogtailHandlerTests))
    suite.addTest(unittest.makeSuite(TailFProducerTests))
    return suite

if __name__ == '__main__':
    __file__ = sys.argv[0]
    unittest.main(defaultTest='test_suite')
