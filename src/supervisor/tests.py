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
import rpc
import http
from options import ServerOptions
from supervisord import ProcessStates
from supervisord import SupervisorStates
try:
    __file__
except:
    __file__ = sys.argv[0]


DEBUG = 0


import unittest

class INIOptionTests(unittest.TestCase):
    def test_options(self):
        s = """[supervisord]
xmlrpc_port=127.0.0.1:8999 ; (default is to run no xmlrpc server)
xmlrpc_username=chrism     ; (default is no username (open system))
xmlrpc_password=foo        ; (default is no password (open system))
directory=%(tempdir)s     ; (default is not to cd during daemonization)
backofflimit=10            ; (default 3)
forever=false              ; (default false)
exitcodes=0,1              ; (default 0,2)
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

[program:cat2]
command=/bin/cat
autostart=true
autorestart=false
logfile_maxbytes = 1024
logfile_backups = 2
logfile = /tmp/cat2.log

[program:cat3]
command=/bin/cat
""" % {'tempdir':tempfile.gettempdir()}

        from StringIO import StringIO
        fp = StringIO(s)
        instance = ServerOptions(*[])
        instance.configfile = fp
        instance.realize()
        options = instance.configroot.supervisord
        import socket
        self.assertEqual(options.directory, tempfile.gettempdir())
        self.assertEqual(options.backofflimit, 10)
        self.assertEqual(options.forever, False)
        self.assertEqual(options.exitcodes, [0,1])
        self.assertEqual(options.umask, 022)
        self.assertEqual(options.prompt, 'supervisor')
        self.assertEqual(options.logfile, 'supervisord.log')
        self.assertEqual(options.logfile_maxbytes, 1000 * 1024 * 1024)
        self.assertEqual(options.logfile_backups, 5)
        self.assertEqual(options.loglevel, 40)
        self.assertEqual(options.pidfile, 'supervisord.pid')
        self.assertEqual(options.nodaemon, True)
        self.assertEqual(options.passwdfile, None)
        self.assertEqual(options.noauth, True)
        self.assertEqual(options.identifier, 'fleeb')
        self.assertEqual(options.childlogdir, tempfile.gettempdir())
        self.assertEqual(options.xmlrpc_port.family, socket.AF_INET)
        self.assertEqual(options.xmlrpc_port.address, ('127.0.0.1', 8999))
        self.assertEqual(options.xmlrpc_username, 'chrism')
        self.assertEqual(options.xmlrpc_password, 'foo')
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
        self.assertEqual(cat.uid, 0)
        self.assertEqual(cat.logfile, '/tmp/cat.log')
        self.assertEqual(cat.stopsignal, signal.SIGKILL)
        self.assertEqual(cat.logfile_maxbytes, datatypes.byte_size('5MB'))
        self.assertEqual(cat.logfile_backups, 1)

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

        cat3 = options.programs[2]
        self.assertEqual(cat3.name, 'cat3')
        self.assertEqual(cat3.command, '/bin/cat')
        self.assertEqual(cat3.priority, 999)
        self.assertEqual(cat3.autostart, True)
        self.assertEqual(cat3.autorestart, True)
        self.assertEqual(cat3.uid, None)
        self.failUnless(cat3.logfile.startswith('%s/cat3---fleeb' %
                                                tempfile.gettempdir()))
        self.assertEqual(cat3.logfile_maxbytes, datatypes.byte_size('5MB'))
        self.assertEqual(cat3.logfile_backups, 1)
        
        self.assertEqual(cat2.stopsignal, signal.SIGTERM)

        here = os.path.abspath(os.getcwd())
        self.assertEqual(instance.uid, 0)
        self.assertEqual(instance.gid, 0)
        self.assertEqual(instance.directory, '/tmp')
        self.assertEqual(instance.backofflimit, 10)
        self.assertEqual(instance.forever, False)
        self.assertEqual(instance.exitcodes, [0,1])
        self.assertEqual(instance.umask, 022)
        self.assertEqual(instance.prompt, 'supervisor')
        self.assertEqual(instance.logfile, os.path.join(here,'supervisord.log'))
        self.assertEqual(instance.logfile_maxbytes, 1000 * 1024 * 1024)
        self.assertEqual(instance.logfile_backups, 5)
        self.assertEqual(instance.loglevel, 40)
        self.assertEqual(instance.pidfile, os.path.join(here,'supervisord.pid'))
        self.assertEqual(instance.nodaemon, True)
        self.assertEqual(instance.passwdfile, None)
        self.assertEqual(instance.noauth, True)
        self.assertEqual(instance.identifier, 'fleeb')
        self.assertEqual(instance.childlogdir, tempfile.gettempdir())
        self.assertEqual(instance.xmlrpc_port.family, socket.AF_INET)
        self.assertEqual(instance.xmlrpc_port.address, ('127.0.0.1', 8999))
        self.assertEqual(instance.xmlrpc_username, 'chrism')
        self.assertEqual(instance.xmlrpc_password, 'foo')
        self.assertEqual(instance.nocleanup, True)
        self.assertEqual(instance.minfds, 2048)
        self.assertEqual(instance.minprocs, 300)

class SupervisorTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisord import Supervisor
        return Supervisor

    def _makeOne(self):
        return self._getTargetClass()()
    
    def test_main(self):
        supervisor = self._makeOne()
        supervisor.main(['-c' 'sample.conf'], test=True)
        self.assertEqual(supervisor.processes, {})
        self.failUnless(supervisor.httpserver)
        

class TestBase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _assertRPCError(self, errtext, callable, *args, **kw):
        try:
            callable(*args, **kw)
        except rpc.RPCError, inst:
            self.assertEqual(inst.text, errtext)
        else:
            raise AssertionError("Didnt raise")

class MainXMLRPCInterfaceTests(TestBase):

    def _getTargetClass(self):
        return rpc.RPCInterface

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
        from rpc import traverse
        self._assertRPCError('UNKNOWN_METHOD',
                             traverse, interface, 'notthere.hello', [])
        self._assertRPCError('UNKNOWN_METHOD',
                             traverse, interface, 'supervisor._readFile', [])
        self._assertRPCError('INCORRECT_PARAMETERS',
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
        return rpc.SupervisorNamespaceRPCInterface

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_update(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        interface._update('foo')
        self.assertEqual(interface.update_text, 'foo')
        supervisord.state = SupervisorStates.SHUTDOWN
        self._assertRPCError('SHUTDOWN_STATE', interface._update, 'foo')

    def test_getVersion(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        version = interface.getVersion()
        self.assertEqual(version, rpc.RPC_VERSION)
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
        self._assertRPCError('NO_FILE', interface.readLog,
                             offset=0, length=1)

    def test_readLog_badargs(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        try:
            logfile = supervisord.options.logfile
            f = open(logfile, 'w+')
            f.write('x' * 2048)
            f.close()
            self._assertRPCError('BAD_ARGUMENTS',
                                 interface.readLog, offset=-1, length=1)
            self._assertRPCError('BAD_ARGUMENTS',
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
        self._assertRPCError('NO_FILE', interface.clearLog)

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
        self._assertRPCError('ALREADY_STARTED',
                             interface.startProcess,'foo')

    def test_startProcess_badname(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError('BAD_NAME',  interface.startProcess,
                             'foo')

    def test_startProcess_spawnerr(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config)
        process.spawnerr = 'abc'
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        self._assertRPCError('SPAWN_ERROR',  interface.startProcess,
                             'foo')

    def test_startProcess(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config)
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
        process = DummyProcess(options, config)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo')
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')
        process.pid = 0
        self._assertRPCError('ABNORMAL_TERMINATION', callback, True)
    
    def test_startProcess_notimeout(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo', autostart=False)
        process = DummyProcess(options, config)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        value = interface.startProcess('foo', timeout=0)
        self.assertEqual(value, True)
        self.assertEqual(interface.update_text, 'startProcess')

        self.assertEqual(process.spawned, True)

    def test_startAllProcesses(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo')
        config2 = DummyPConfig('foo2', '/bin/foo2')
        process = DummyProcess(options, config, ProcessStates.NOTSTARTED)
        process2 = DummyProcess(options, config2, ProcessStates.NOTSTARTED)
        supervisord = DummySupervisor({'foo':process, 'foo2':process2})
        interface = self._makeOne(supervisord)
        callback = interface.startAllProcesses()
        process.pid = 1234
        process2.pid = 12345
        # first process
        from http import NOT_DONE_YET
        self.assertEqual(callback(done=True), NOT_DONE_YET)
        # second process
        self.assertEqual(callback(done=True), True)
        self.assertEqual(interface.update_text, 'startProcess')

        self.assertEqual(process.spawned, True)
        self.assertEqual(process2.spawned, True)
        

    def test_stopProcess_badname(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError('BAD_NAME', interface.stopProcess, 'foo')

    def test_stopProcess(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo')
        process = DummyProcess(options, config)
        supervisord = DummySupervisor({'foo':process})
        interface = self._makeOne(supervisord)
        callback = interface.stopProcess('foo')
        self.assertEqual(interface.update_text, 'stopProcess')
        process = supervisord.processes.get('foo')
        self.assertEqual(process.backoff, 0)
        self.assertEqual(process.delay, 0)
        self.assertEqual(process.killing, 0)
        process.killing = 1
        self.assertEqual(callback(), http.NOT_DONE_YET)
        process.killing = 0
        process.pid = 0
        self.assertEqual(callback(), True)
        self.assertEqual(len(supervisord.processes), 1)
        self.assertEqual(interface.update_text, 'stopProcess')


    def test_stopAllProcesses(self):
        options = DummyOptions()
        config = DummyPConfig('foo', '/bin/foo')
        config2 = DummyPConfig('foo2', '/bin/foo2')
        process = DummyProcess(options, config)
        process2 = DummyProcess(options, config2)
        supervisord = DummySupervisor({'foo':process, 'foo2':process2})
        interface = self._makeOne(supervisord)
        process.pid = process2.pid = 1234
        callback = interface.stopAllProcesses()
        self.assertEqual(interface.update_text, 'stopProcess')
        value = http.NOT_DONE_YET
        while 1:
            value = callback()
            if value is True:
                break

        processes = supervisord.processes
        self.assertEqual(value, True)
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
        self.assertEqual(data['reportstatusmsg'], '')
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
        self.assertEqual(p1info['reportstatusmsg'], 'foo')
        self.assertEqual(p1info['logfile'], '/tmp/process1.log')
        self.assertEqual(p1info['name'], 'process1')
        self.assertEqual(p1info['pid'], 111)
        self.assertEqual(p1info['start'], 10)
        self.assertEqual(p1info['stop'], 11)
        self.assertEqual(p1info['state'], ProcessStates.RUNNING)
        self.assertEqual(p1info['exitstatus'], 0)
        self.assertEqual(p1info['spawnerr'], '')

        p2info = info[1]
        self.assertEqual(p2info['reportstatusmsg'], 'bar')
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
        self._assertRPCError('NO_FILE', interface.readProcessLog,
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
            self._assertRPCError('BAD_ARGUMENTS',
                                 interface.readProcessLog,
                                 'process1', offset=-1, length=1)
            self._assertRPCError('BAD_ARGUMENTS',
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
        self._assertRPCError('BAD_NAME', interface.clearProcessLog,
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

    def test_readFile_failed(self):
        from rpc import _readFile
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        logfile = supervisord.options.logfile
        try:
            _readFile('/notthere', 0, 10)
        except ValueError, inst:
            self.assertEqual(inst.args[0], 'FAILED')
        else:
            raise AssertionError("Didn't raise")


class SystemNamespaceXMLRPCInterfaceTests(TestBase):
    def _getTargetClass(self):
        return rpc.SystemNamespaceRPCInterface

    def _makeOne(self):
        supervisord = DummySupervisor()
        supervisor = rpc.SupervisorNamespaceRPCInterface(supervisord)
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
        self._assertRPCError('SIGNATURE_UNSUPPORTED', interface.methodSignature,
                             ['foo.bar'])
        result = interface.methodSignature('system.methodSignature')
        self.assertEqual(result, ['array', 'string'])

    def test_allMethodDocs(self):
        # belt-and-suspenders test for docstring-as-typing parsing correctness
        # and documentation validity vs. implementation
        import doctags
        _RPCTYPES = ['int', 'double', 'string', 'boolean', 'dateTime.iso8601',
                     'base64', 'binary', 'array', 'struct']
        interface = self._makeOne()
        methods = interface._listMethods()
        for k in methods.keys():
            # if a method doesn't have a @return value, an RPCError is raised.
            # Detect that here.
            try:
                interface.methodSignature(k)
            except rpc.RPCError:
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
            parsed = doctags.gettags(str(meth.__doc__))

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
        self.assertEqual(result[0], True)

    def test_methodHelp(self):
        interface = self._makeOne()
        self._assertRPCError('SIGNATURE_UNSUPPORTED', interface.methodHelp,
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
        self.assertEqual(instance.pidhistory, [])
        self.assertEqual(instance.childlog.args, (config.logfile, 10,
                                                  '%(message)s', 0, 0))
        self.assertEqual(instance.pid, 0)
        self.assertEqual(instance.laststart, 0)
        self.assertEqual(instance.laststop, 0)
        self.assertEqual(instance.delay, 0)
        self.assertEqual(instance.administrative_stop, 0)
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.backoff, 0)
        self.assertEqual(instance.waitstatus, None)
        self.assertEqual(instance.stdout, None)
        self.assertEqual(instance.stdin, None)
        self.assertEqual(instance.stderr, None)
        self.assertEqual(instance.stdoutfd, None)
        self.assertEqual(instance.stdinfd, None)
        self.assertEqual(instance.stderrfd, None)
        self.assertEqual(instance.spawnerr, None)
        self.assertEqual(instance.readbuffer, '')
        self.assertEqual(instance.finaloutput, '')

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

    def test_addpidtohistory(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        self.assertEqual(instance.pidhistory, [])
        instance.addpidtohistory(1)
        self.assertEqual(instance.pidhistory, [1])
        instance.addpidtohistory(2)
        self.assertEqual(instance.pidhistory, [1, 2])
        for x in range(3, 16):
            instance.addpidtohistory(x)
        self.assertEqual(instance.pidhistory, [6,7,8,9,10,11,12,13,14,15])

    def test_isoneofmypids(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.pidhistory = [1]
        self.failUnless(instance.isoneofmypids(1))

    def test_governor_system_stop(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        options.backofflimit = 1
        options.forever = False
        instance.backoff = 1 # gt backofflimit
        instance.laststart = time.time()
        instance.governor()
        self.assertEqual(instance.backoff, 2)
        self.assertEqual(instance.system_stop, 1)
        self.assertEqual(options.logger.data[0],
                         "notthere: restarting too frequently; quit")

    def test_reportstatus(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.waitstatus = (123, 1) # pid, waitstatus
        instance.pidhistory = [123]
        instance.killing = 1
        instance.stdout = 'will be replaced'
        instance.reportstatus()
        self.assertEqual(instance.killing, 0)
        self.assertEqual(instance.pid, 0)
        self.assertEqual(instance.stdout, None)
        self.assertEqual(options.logger.data[1], 'pid 123: terminated by '
                         'SIGHUP')
        self.assertEqual(instance.exitstatus, -1)
        self.assertEqual(instance.reportstatusmsg, 'pid 123: terminated by '
                         'SIGHUP')

    def test_do_backoff(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        now = time.time()
        instance.do_backoff()
        self.failUnless(instance.delay >= now + options.backofflimit)

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

    def test_log(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.log('foo')
        self.assertEqual(instance.childlog.data, ['foo'])

    def test_trace(self):
        # trace messages go to the main logger
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.trace('foo')
        self.assertEqual(options.logger.data, [5, 'notthere output:\nfoo'])

    def test_log_stdout(self):
        # stdout goes to the process log and the main log
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.log_stdout('foo')
        self.assertEqual(instance.childlog.data, ['foo'])
        self.assertEqual(options.logger.data, [5, 'notthere output:\nfoo'])

    def test_log_stderr(self):
        # sterr goes to the process log and the main log
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        instance = self._makeOne(options, config)
        instance.log_stderr('foo')
        self.assertEqual(instance.childlog.data, ['foo'])
        self.assertEqual(options.logger.data, [5, 'notthere output:\nfoo'])

    def test_get_state(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere', logfile='/tmp/foo')
        from supervisord import ProcessStates

        instance = self._makeOne(options, config)
        instance.killing = True
        self.assertEqual(instance.get_state(), ProcessStates.STOPPING)

        instance = self._makeOne(options, config)
        instance.delay = 1
        self.assertEqual(instance.get_state(), ProcessStates.STARTING)

        instance = self._makeOne(options, config)
        instance.pid = 11
        self.assertEqual(instance.get_state(), ProcessStates.RUNNING)
        
        instance = self._makeOne(options, config)
        instance.system_stop = True
        self.assertEqual(instance.get_state(), ProcessStates.ERROR)

        instance = self._makeOne(options, config)
        instance.administrative_stop = True
        self.assertEqual(instance.get_state(), ProcessStates.STOPPED)
        
        instance = self._makeOne(options, config)
        instance.exitstatus = -1
        self.assertEqual(instance.get_state(), ProcessStates.KILLED)
        
        instance = self._makeOne(options, config)
        instance.exitstatus = 1
        self.assertEqual(instance.get_state(), ProcessStates.EXITED)
        
        instance = self._makeOne(options, config)
        instance.pidhistory = []
        self.assertEqual(instance.get_state(), ProcessStates.NOTSTARTED)

        instance = self._makeOne(options, config)
        instance.pidhistory = [1]
        self.assertEqual(instance.get_state(), ProcessStates.UNKNOWN)

    def test_get_execv_args_abs_missing(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/notthere')
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args, ('/notthere', ['/notthere'], None))

    def test_get_execv_args_rel_missing(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', 'notthere')
        instance = self._makeOne(options, config)
        args = instance.get_execv_args()
        self.assertEqual(args, (None, ['notthere'], None))

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
        
    def test_spawn_already_running(self):
        options = DummyOptions()
        config = DummyPConfig('sh', '/bin/sh')
        instance = self._makeOne(options, config)
        instance.pid = True
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(options.logger.data[0], "process 'sh' already running")

    def test_spawn_cant_find_command(self):
        options = DummyOptions()
        config = DummyPConfig('notthere', '/not/there')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, "can't find command '/not/there'")
        self.assertEqual(options.logger.data[0],
                         "can't find command '/not/there'")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_isdir(self):
        options = DummyOptions()
        config = DummyPConfig('dir', '/')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr, "command at '/' is a directory")
        self.assertEqual(options.logger.data[0],
                         "command at '/' is a directory")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_notexecutable(self):
        options = DummyOptions()
        config = DummyPConfig('dir', '/etc/passwd')
        instance = self._makeOne(options, config)
        result = instance.spawn()
        self.assertEqual(result, None)
        self.assertEqual(instance.spawnerr,
                         "command at '/etc/passwd' is not executable")
        self.assertEqual(options.logger.data[0],
                         "command at '/etc/passwd' is not executable")
        self.failUnless(instance.delay)
        self.failUnless(instance.backoff)

    def test_spawn_and_kill(self):
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
            self.assert_(options.logger.data[0].startswith("spawned process"))
            self.failUnless(instance.stdin)
            self.failUnless(instance.stdout)
            self.failUnless(instance.stderr)
            self.failUnless(instance.stdinfd)
            self.failUnless(instance.stdoutfd)
            self.failUnless(instance.stderrfd)
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


class XMLRPCMarshallingTests(unittest.TestCase):
    def test_xmlrpc_marshal(self):
        from rpc import xmlrpc_marshal
        import xmlrpclib
        data = xmlrpc_marshal(1)
        self.assertEqual(data, xmlrpclib.dumps((1,), methodresponse=True))
        fault = xmlrpclib.Fault(1, 'foo')
        data = xmlrpc_marshal(fault)
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
    stdin = stderr = stdout = None
    stdinfd = stderrfd = stdoutfd = None
    childlog = None # the current logger 
    spawnerr = None
    writebuffer = '' # buffer of characters to send to child process' stdin
    readbuffer = ''  # buffer of characters written to child's stdout
    finaloutput = '' # buffer of characters read from child's stdout right
                     # before process reapage
    reportstatusmsg = None # message attached to instance during reportstatus()
    
    def __init__(self, options, config, state=ProcessStates.RUNNING):
        self.options = options
        self.config = config
        self.pidhistory = []
        self.writebuffer = ''
        self.readbuffer = ''
        self.childlog = DummyLogger()
        self.logsremoved = False
        self.stop_called = False
        self.backoff_done = False
        self.spawned = True
        self.state = state

    def removelogs(self):
        self.logsremoved = True

    def get_state(self):
        return self.state

    def stop(self):
        self.stop_called = True
        self.killing = False
        self.pid = 0

    def do_backoff(self):
        self.backoff_done = True

    def spawn(self):
        self.spawned = True

class DummyPConfig:
    def __init__(self, name, command, priority=999, autostart=True,
                 autorestart=False, uid=None, logfile=None, logfile_backups=0,
                 logfile_maxbytes=0):
        self.name = name
        self.command = command
        self.priority = priority
        self.autostart = autostart
        self.autorestart = autorestart
        self.uid = uid
        self.logfile = logfile
        self.logfile_backups = logfile_backups
        self.logfile_maxbytes = logfile_maxbytes


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
    def __init__(self):
        self.identifier = 'supervisor'
        self.childlogdir = '/tmp'
        self.uid = 999
        self.logger = self.getLogger()
        self.backofflimit = 10
        self.exitcodes = 0,2
        self.logfile = '/tmp/logfile'
        self.nocleanup = True

    def getLogger(self, *args):
        logger = DummyLogger()
        logger.handlers = [DummyLogger()]
        logger.args = args
        return logger

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
    #suite.addTest(unittest.makeSuite(SupervisorTests))
    suite.addTest(unittest.makeSuite(INIOptionTests))
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
