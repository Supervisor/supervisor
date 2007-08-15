import unittest
import sys
import os
import time

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyPGroupConfig
from supervisor.tests.base import DummyProcessGroup
from supervisor.tests.base import PopulatedDummySupervisor
from supervisor.tests.base import _NOW
from supervisor.tests.base import _TIMEFORMAT

class TestBase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def _assertRPCError(self, code, callable, *args, **kw):
        from supervisor import xmlrpc
        try:
            callable(*args, **kw)
        except xmlrpc.RPCError, inst:
            self.assertEqual(inst.code, code)
        else:
            raise AssertionError("Didnt raise")

class MainXMLRPCInterfaceTests(TestBase):

    def _getTargetClass(self):
        from supervisor import xmlrpc
        return xmlrpc.RootRPCInterface

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_ctor(self):
        interface = self._makeOne([('supervisor', None)])
        self.assertEqual(interface.supervisor, None)

    def test_traverse(self):
        dummy = DummyRPCInterface()
        interface = self._makeOne([('dummy', dummy)])
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.UNKNOWN_METHOD,
                             xmlrpc.traverse, interface, 'notthere.hello', [])
        self._assertRPCError(xmlrpc.Faults.UNKNOWN_METHOD,
                             xmlrpc.traverse, interface,
                             'supervisor._readFile', [])
        self._assertRPCError(xmlrpc.Faults.INCORRECT_PARAMETERS,
                             xmlrpc.traverse, interface,
                             'dummy.hello', [1])
        self.assertEqual(xmlrpc.traverse(
            interface, 'dummy.hello', []), 'Hello!')
            
class SupervisorNamespaceXMLRPCInterfaceTests(TestBase):
    def _getTargetClass(self):
        from supervisor import rpcinterface
        return rpcinterface.SupervisorNamespaceRPCInterface

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_update(self):
        from supervisor import xmlrpc
        from supervisor.supervisord import SupervisorStates
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        interface._update('foo')
        self.assertEqual(interface.update_text, 'foo')
        supervisord.state = SupervisorStates.SHUTDOWN
        self._assertRPCError(xmlrpc.Faults.SHUTDOWN_STATE, interface._update,
                             'foo')

    def test_getAPIVersion(self):
        from supervisor import rpcinterface
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        version = interface.getAPIVersion()
        self.assertEqual(version, rpcinterface.API_VERSION)
        self.assertEqual(interface.update_text, 'getAPIVersion')

    def test_getAPIVersion_aliased_to_deprecated_getVersion(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self.assertEqual(interface.getAPIVersion, interface.getVersion)

    def test_getSupervisorVersion(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        version = interface.getSupervisorVersion()
        from supervisor import options
        self.assertEqual(version, options.VERSION)
        self.assertEqual(interface.update_text, 'getSupervisorVersion')
        

    def test_getIdentification(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        identifier = interface.getIdentification()
        self.assertEqual(identifier, supervisord.options.identifier)
        self.assertEqual(interface.update_text, 'getIdentification')

    def test_getState(self):
        from supervisor.states import getSupervisorStateDescription
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        stateinfo = interface.getState()
        statecode = supervisord.get_state()
        statename = getSupervisorStateDescription(statecode)
        self.assertEqual(stateinfo['statecode'], statecode)
        self.assertEqual(stateinfo['statename'], statename)
        self.assertEqual(interface.update_text, 'getState')

    def test_readLog_aliased_to_deprecated_readMainLog(self):
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self.assertEqual(interface.readMainLog, interface.readLog)

    def test_readLog_unreadable(self):
        from supervisor import xmlrpc
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.NO_FILE, interface.readLog,
                             offset=0, length=1)

    def test_readLog_badargs(self):
        from supervisor import xmlrpc
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
        import os
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
        from supervisor import xmlrpc
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.NO_FILE, interface.clearLog)

    def test_clearLog_unremoveable(self):
        from supervisor import xmlrpc
        options = DummyOptions()
        options.existing = [options.logfile]
        options.remove_error = 1
        supervisord = DummySupervisor(options)
        interface = self._makeOne(supervisord)
        logfile = supervisord.options.logfile
        self.assertRaises(xmlrpc.RPCError, interface.clearLog)
        self.assertEqual(interface.update_text, 'clearLog')

    def test_clearLog(self):
        options = DummyOptions()
        options.existing = [options.logfile]
        supervisord = DummySupervisor(options)
        interface = self._makeOne(supervisord)
        result = interface.clearLog()
        self.assertEqual(interface.update_text, 'clearLog')
        self.assertEqual(result, True)
        self.assertEqual(options.removed[0], options.logfile)
        for handler in supervisord.options.logger.handlers:
            self.assertEqual(handler.reopened, True)

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
        from supervisor import xmlrpc
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False)
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'pid', 10)
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo')
        self._assertRPCError(xmlrpc.Faults.ALREADY_STARTED,
                             callback)

    def test_startProcess_bad_group_name(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False)
        supervisord = PopulatedDummySupervisor(options, 'group1', pconfig)
        interface = self._makeOne(supervisord)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.startProcess, 'group2:foo')

    def test_startProcess_bad_process_name(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False)
        supervisord = PopulatedDummySupervisor(options, 'group1', pconfig)
        interface = self._makeOne(supervisord)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.startProcess, 'group1:bar')

    def test_startProcess_file_not_found(self):
        options = DummyOptions()
        pconfig  = DummyPConfig(options, 'foo', '/foo/bar', autostart=False)
        from supervisor.options import NotFound
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        process = supervisord.process_groups['foo'].processes['foo']
        process.execv_arg_exception = NotFound
        interface = self._makeOne(supervisord)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.NO_FILE,
                             interface.startProcess, 'foo')

    def test_startProcess_file_not_executable(self):
        options = DummyOptions()
        pconfig  = DummyPConfig(options, 'foo', '/foo/bar', autostart=False)
        from supervisor.options import NotExecutable
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        process = supervisord.process_groups['foo'].processes['foo']
        process.execv_arg_exception = NotExecutable
        interface = self._makeOne(supervisord)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.NOT_EXECUTABLE,
                             interface.startProcess, 'foo')

    def test_startProcess_spawnerr(self):
        from supervisor import xmlrpc
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False)
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'state', ProcessStates.STOPPED)
        process = supervisord.process_groups['foo'].processes['foo']
        process.spawnerr = 'abc'
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo')
        self._assertRPCError(xmlrpc.Faults.SPAWN_ERROR, callback)

    def test_startProcess(self):
        from supervisor import http
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False,
                               startsecs=.01)
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo')
        self.assertEqual(callback(), http.NOT_DONE_YET)
        process = supervisord.process_groups['foo'].processes['foo']
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')
        from supervisor.process import ProcessStates
        process.state = ProcessStates.RUNNING
        time.sleep(.02)
        result = callback()
        self.assertEqual(result, True)

    def test_startProcess_nowait(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False)
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo', wait=False)
        self.assertEqual(callback(), True)
        process = supervisord.process_groups['foo'].processes['foo']
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')

    def test_startProcess_nostartsecs(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False,
                               startsecs=0)
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo', wait=True)
        self.assertEqual(callback(), True)
        process = supervisord.process_groups['foo'].processes['foo']
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')

    def test_startProcess_abnormal_term_process_not_running(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False)
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo', 100) # milliseconds
        result = callback()
        from supervisor import http
        self.assertEqual(result, http.NOT_DONE_YET)
        process = supervisord.process_groups['foo'].processes['foo']
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')
        from supervisor.process import ProcessStates
        process.state = ProcessStates.BACKOFF

        time.sleep(.1)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.ABNORMAL_TERMINATION, callback)
    
    def test_startProcess_abormal_term_startsecs_exceeded(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', __file__, autostart=False,
                               startsecs=.01)
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startProcess('foo', 100) # milliseconds
        result = callback()
        from supervisor import http
        self.assertEqual(result, http.NOT_DONE_YET)
        supervisord.set_procattr('foo', 'state', ProcessStates.STARTING)
        process = supervisord.process_groups['foo'].processes['foo']
        self.assertEqual(process.spawned, True)
        self.assertEqual(interface.update_text, 'startProcess')
        from supervisor.process import ProcessStates
        process.state = ProcessStates.STARTING

        time.sleep(.2)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.ABNORMAL_TERMINATION, callback)

    def test_startProcessGroup(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', __file__, priority=1,
                                startsecs=.01)
        pconfig2 = DummyPConfig(options, 'process2', __file__, priority=2,
                                startsecs=.01)
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        from supervisor.process import ProcessStates
        supervisord.set_procattr('process1', 'state', ProcessStates.STOPPED)
        supervisord.set_procattr('process2', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startProcessGroup('foo')

        from supervisor.http import NOT_DONE_YET

        # create callbacks in startall()
        self.assertEqual(callback(), NOT_DONE_YET)
        # start first process
        self.assertEqual(callback(), NOT_DONE_YET)
        # start second process
        self.assertEqual(callback(), NOT_DONE_YET)

        # wait for timeout 1
        time.sleep(.02)
        self.assertEqual(callback(), NOT_DONE_YET)

        # wait for timeout 2
        time.sleep(.02)
        result = callback()

        self.assertEqual(len(result), 2)

        from supervisor.xmlrpc import Faults

        # XXX not sure about this ordering, I think process1 should
        # probably show up first
        self.assertEqual(result[0]['name'], 'process2')
        self.assertEqual(result[0]['group'], 'foo')
        self.assertEqual(result[0]['status'],  Faults.SUCCESS)
        self.assertEqual(result[0]['description'], 'OK')

        self.assertEqual(result[1]['name'], 'process1')
        self.assertEqual(result[1]['group'], 'foo')
        self.assertEqual(result[1]['status'],  Faults.SUCCESS)
        self.assertEqual(result[1]['description'], 'OK')

        self.assertEqual(interface.update_text, 'startProcess')

        process1 = supervisord.process_groups['foo'].processes['process1']
        self.assertEqual(process1.spawned, True)
        process2 = supervisord.process_groups['foo'].processes['process2']
        self.assertEqual(process2.spawned, True)

    def test_startProcessGroup_nowait(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', __file__, priority=1,
                                startsecs=.01)
        pconfig2 = DummyPConfig(options, 'process2', __file__, priority=2,
                                startsecs=.01)
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        from supervisor.process import ProcessStates
        supervisord.set_procattr('process1', 'state', ProcessStates.STOPPED)
        supervisord.set_procattr('process2', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startProcessGroup('foo', wait=False)
        from supervisor.http import NOT_DONE_YET
        from supervisor.xmlrpc import Faults

        # create callbacks in startall()
        self.assertEqual(callback(), NOT_DONE_YET)

        # get a result
        result = callback()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'process1')
        self.assertEqual(result[0]['group'], 'foo')
        self.assertEqual(result[0]['status'],  Faults.SUCCESS)
        self.assertEqual(result[0]['description'], 'OK')

        self.assertEqual(result[1]['name'], 'process2')
        self.assertEqual(result[1]['group'], 'foo')
        self.assertEqual(result[1]['status'],  Faults.SUCCESS)
        self.assertEqual(result[1]['description'], 'OK')

    def test_startProcessGroup_badname(self):
        from supervisor import xmlrpc
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.startProcessGroup, 'foo')


    def test_startAllProcesses(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', __file__, priority=1,
                                startsecs=.01)
        pconfig2 = DummyPConfig(options, 'process2', __file__, priority=2,
                                startsecs=.01)
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        from supervisor.process import ProcessStates
        supervisord.set_procattr('process1', 'state', ProcessStates.STOPPED)
        supervisord.set_procattr('process2', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startAllProcesses()

        from supervisor.http import NOT_DONE_YET

        # create callbacks in startall()
        self.assertEqual(callback(), NOT_DONE_YET)
        # start first process
        self.assertEqual(callback(), NOT_DONE_YET)
        # start second process
        self.assertEqual(callback(), NOT_DONE_YET)

        # wait for timeout 1
        time.sleep(.02)
        self.assertEqual(callback(), NOT_DONE_YET)

        # wait for timeout 2
        time.sleep(.02)
        result = callback()

        self.assertEqual(len(result), 2)

        from supervisor.xmlrpc import Faults

        # XXX not sure about this ordering, I think process1 should
        # probably show up first
        self.assertEqual(result[0]['name'], 'process2')
        self.assertEqual(result[0]['group'], 'foo')
        self.assertEqual(result[0]['status'],  Faults.SUCCESS)
        self.assertEqual(result[0]['description'], 'OK')

        self.assertEqual(result[1]['name'], 'process1')
        self.assertEqual(result[1]['group'], 'foo')
        self.assertEqual(result[1]['status'],  Faults.SUCCESS)
        self.assertEqual(result[1]['description'], 'OK')

        self.assertEqual(interface.update_text, 'startProcess')

        process1 = supervisord.process_groups['foo'].processes['process1']
        self.assertEqual(process1.spawned, True)
        process2 = supervisord.process_groups['foo'].processes['process2']
        self.assertEqual(process2.spawned, True)

    def test_startAllProcesses_nowait(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', __file__, priority=1,
                                startsecs=.01)
        pconfig2 = DummyPConfig(options, 'process2', __file__, priority=2,
                                startsecs=.01)
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        from supervisor.process import ProcessStates
        supervisord.set_procattr('process1', 'state', ProcessStates.STOPPED)
        supervisord.set_procattr('process2', 'state', ProcessStates.STOPPED)
        interface = self._makeOne(supervisord)
        callback = interface.startAllProcesses(wait=False)
        from supervisor.http import NOT_DONE_YET
        from supervisor.xmlrpc import Faults

        # create callbacks in startall()
        self.assertEqual(callback(), NOT_DONE_YET)

        # get a result
        result = callback()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'process1')
        self.assertEqual(result[0]['group'], 'foo')
        self.assertEqual(result[0]['status'],  Faults.SUCCESS)
        self.assertEqual(result[0]['description'], 'OK')

        self.assertEqual(result[1]['name'], 'process2')
        self.assertEqual(result[1]['group'], 'foo')
        self.assertEqual(result[1]['status'],  Faults.SUCCESS)
        self.assertEqual(result[1]['description'], 'OK')

    def test_stopProcess_badname(self):
        from supervisor import xmlrpc
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.stopProcess, 'foo')

    def test_stopProcess(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', '/bin/foo')
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        supervisord.set_procattr('foo', 'state', ProcessStates.RUNNING)
        interface = self._makeOne(supervisord)
        callback = interface.stopProcess('foo')
        self.assertEqual(interface.update_text, 'stopProcess')
        process = supervisord.process_groups['foo'].processes['foo']
        self.assertEqual(process.backoff, 0)
        self.assertEqual(process.delay, 0)
        self.assertEqual(process.killing, 0)
        from supervisor import http
        self.assertEqual(callback(), http.NOT_DONE_YET)
        from supervisor.process import ProcessStates
        self.assertEqual(process.state, ProcessStates.STOPPED)
        self.assertEqual(callback(), True)
        self.assertEqual(len(supervisord.process_groups['foo'].processes), 1)
        self.assertEqual(interface.update_text, 'stopProcess')

    def test_stopProcessGroup(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', '/bin/foo')
        pconfig2 = DummyPConfig(options, 'process2', '/bin/foo2')
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        supervisord.set_procattr('process1', 'state', ProcessStates.RUNNING)
        supervisord.set_procattr('process2', 'state', ProcessStates.RUNNING)
        interface = self._makeOne(supervisord)
        callback = interface.stopProcessGroup('foo')
        self.assertEqual(interface.update_text, 'stopProcessGroup')
        from supervisor import http
        value = http.NOT_DONE_YET
        while 1:
            value = callback()
            if value is not http.NOT_DONE_YET:
                break

        self.assertEqual(value, [
            {'status':80,'group':'foo','name': 'process1','description': 'OK'},
            {'status':80,'group':'foo','name': 'process2','description': 'OK'},
            ] )
        process1 = supervisord.process_groups['foo'].processes['process1']
        self.assertEqual(process1.stop_called, True)
        process2 = supervisord.process_groups['foo'].processes['process2']
        self.assertEqual(process2.stop_called, True)

    def test_stopProcessGroup_badname(self):
        from supervisor import xmlrpc
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.stopProcessGroup, 'foo')

    def test_stopAllProcesses(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', '/bin/foo')
        pconfig2 = DummyPConfig(options, 'process2', '/bin/foo2')
        from supervisor.process import ProcessStates
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        supervisord.set_procattr('process1', 'state', ProcessStates.RUNNING)
        supervisord.set_procattr('process2', 'state', ProcessStates.RUNNING)
        interface = self._makeOne(supervisord)
        callback = interface.stopAllProcesses()
        self.assertEqual(interface.update_text, 'stopAllProcesses')
        from supervisor import http
        value = http.NOT_DONE_YET
        while 1:
            value = callback()
            if value is not http.NOT_DONE_YET:
                break

        self.assertEqual(value, [
            {'status':80,'group':'foo','name': 'process1','description': 'OK'},
            {'status':80,'group':'foo','name': 'process2','description': 'OK'},
            ] )
        process1 = supervisord.process_groups['foo'].processes['process1']
        self.assertEqual(process1.stop_called, True)
        process2 = supervisord.process_groups['foo'].processes['process2']
        self.assertEqual(process2.stop_called, True)

    def test__interpretProcessInfo(self):
        supervisord = DummySupervisor({})
        interface = self._makeOne(supervisord)
        start = _NOW -100
        stop  = _NOW -1
        from supervisor.process import ProcessStates
        running = {'name':'running',
                   'pid':1,
                   'state':ProcessStates.RUNNING,
                   'start':start,
                   'stop':stop,
                   'now':_NOW}
        
        description = interface._interpretProcessInfo(running)
        self.assertEqual(description, 'pid 1, uptime 0:01:40')

        fatal = {'name':'fatal',
                 'pid':2,
                 'state':ProcessStates.FATAL,
                 'start':start,
                 'stop':stop,
                 'now':_NOW,
                 'spawnerr':'Hosed'}
                 
        description = interface._interpretProcessInfo(fatal)
        self.assertEqual(description, 'Hosed')

        fatal2 = {'name':'fatal',
                  'pid':2,
                  'state':ProcessStates.FATAL,
                  'start':start,
                  'stop':stop,
                  'now':_NOW,
                  'spawnerr':'',}
                 
        description = interface._interpretProcessInfo(fatal2)
        self.assertEqual(description, 'unknown error (try "tail fatal")')
        
        stopped = {'name':'stopped',
                   'pid':3,
                   'state':ProcessStates.STOPPED,
                   'start':start,
                   'stop':stop,
                   'now':_NOW,
                   'spawnerr':'',}

        description = interface._interpretProcessInfo(stopped)
        from datetime import datetime
        stoptime = datetime(*time.localtime(stop)[:7])
        self.assertEqual(description, stoptime.strftime(_TIMEFORMAT))
        
        stopped2 = {'name':'stopped',
                   'pid':3,
                   'state':ProcessStates.STOPPED,
                   'start':0,
                   'stop':stop,
                   'now':_NOW,
                   'spawnerr':'',}

        description = interface._interpretProcessInfo(stopped2)
        self.assertEqual(description, 'Not started')
                   

    def test_getProcessInfo(self):
        from supervisor.process import ProcessStates

        options = DummyOptions()
        config = DummyPConfig(options, 'foo', '/bin/foo',
                              stdout_logfile='/tmp/fleeb.bar')
        process = DummyProcess(config)
        process.pid = 111
        process.laststart = 10
        process.laststop = 11
        pgroup_config = DummyPGroupConfig(options, name='foo')
        pgroup = DummyProcessGroup(pgroup_config)
        pgroup.processes = {'foo':process}
        supervisord = DummySupervisor(process_groups={'foo':pgroup})
        interface = self._makeOne(supervisord)
        data = interface.getProcessInfo('foo')

        self.assertEqual(interface.update_text, 'getProcessInfo')
        self.assertEqual(data['logfile'], '/tmp/fleeb.bar')
        self.assertEqual(data['name'], 'foo')
        self.assertEqual(data['pid'], 111)
        self.assertEqual(data['start'], 10)
        self.assertEqual(data['stop'], 11)
        self.assertEqual(data['state'], ProcessStates.RUNNING)
        self.assertEqual(data['statename'], 'RUNNING')
        self.assertEqual(data['exitstatus'], 0)
        self.assertEqual(data['spawnerr'], '')
        self.failUnless(data['description'].startswith('pid 111'))

    def test_getProcessInfo_logfile_NONE(self):
        from supervisor.process import ProcessStates

        options = DummyOptions()
        config = DummyPConfig(options, 'foo', '/bin/foo',
                              stdout_logfile=None)
        process = DummyProcess(config)
        process.pid = 111
        process.laststart = 10
        process.laststop = 11
        pgroup_config = DummyPGroupConfig(options, name='foo')
        pgroup = DummyProcessGroup(pgroup_config)
        pgroup.processes = {'foo':process}
        supervisord = DummySupervisor(process_groups={'foo':pgroup})
        interface = self._makeOne(supervisord)
        data = interface.getProcessInfo('foo')

        self.assertEqual(data['logfile'], 'NONE')

    def test_getAllProcessInfo(self):
        from supervisor.process import ProcessStates
        options = DummyOptions()

        p1config = DummyPConfig(options, 'process1', '/bin/process1',
                                priority=1,
                                stdout_logfile='/tmp/process1.log')

        p2config = DummyPConfig(options, 'process2', '/bin/process2',
                                priority=2,
                                stdout_logfile='/tmp/process2.log')

        supervisord = PopulatedDummySupervisor(options, 'gname', p1config,
                                               p2config)
        supervisord.set_procattr('process1', 'pid', 111)
        supervisord.set_procattr('process1', 'laststart', 10)
        supervisord.set_procattr('process1', 'laststop', 11)
        supervisord.set_procattr('process1', 'state', ProcessStates.RUNNING)

        supervisord.set_procattr('process2', 'pid', 0)
        supervisord.set_procattr('process2', 'laststart', 20)
        supervisord.set_procattr('process2', 'laststop', 11)
        supervisord.set_procattr('process2', 'state', ProcessStates.STOPPED)

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
        self.assertEqual(p1info['statename'], 'RUNNING')
        self.assertEqual(p1info['exitstatus'], 0)
        self.assertEqual(p1info['spawnerr'], '')
        self.assertEqual(p1info['group'], 'gname')
        self.failUnless(p1info['description'].startswith('pid 111'))

        p2info = info[1]
        process2 = supervisord.process_groups['gname'].processes['process2']
        self.assertEqual(p2info['logfile'], '/tmp/process2.log')
        self.assertEqual(p2info['name'], 'process2')
        self.assertEqual(p2info['pid'], 0)
        self.assertEqual(p2info['start'], process2.laststart)
        self.assertEqual(p2info['stop'], 11)
        self.assertEqual(p2info['state'], ProcessStates.STOPPED)
        self.assertEqual(p2info['statename'], 'STOPPED')
        self.assertEqual(p2info['exitstatus'], 0)
        self.assertEqual(p2info['spawnerr'], '')
        self.assertEqual(p1info['group'], 'gname')
        
        from datetime import datetime
        starttime = datetime(*time.localtime(process2.laststart)[:7])
        self.assertEqual(p2info['description'], 
                            starttime.strftime(_TIMEFORMAT))

    def test_readProcessLog_unreadable(self):
        from supervisor import xmlrpc
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'process1', '/bin/process1', priority=1,
                               stdout_logfile='/tmp/process1.log')
        supervisord = PopulatedDummySupervisor(options, 'process1', pconfig)
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.NO_FILE,
                             interface.readProcessLog,
                             'process1', offset=0, length=1)

    def test_readProcessLog_badargs(self):
        from supervisor import xmlrpc
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'process1', '/bin/process1', priority=1,
                              stdout_logfile='/tmp/process1.log')
        supervisord = PopulatedDummySupervisor(options, 'process1', pconfig)
        interface = self._makeOne(supervisord)
        import os
        process = supervisord.process_groups['process1'].processes['process1']
        logfile = process.config.stdout_logfile

        try:
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
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',
                              stdout_logfile='/tmp/fooooooo')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        interface = self._makeOne(supervisord)
        process = supervisord.process_groups['foo'].processes['foo']
        logfile = process.config.stdout_logfile
        import os
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

    def test_tailProcessLog_bad_name(self):
        from supervisor import xmlrpc
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME, 
                             interface.tailProcessLog, 'BAD_NAME', 0, 10)

    def test_tailProcessLog_all(self):
        # test entire log is returned when offset==0 and logsize < length
        from string import letters
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',
                               stdout_logfile='/tmp/fooooooo')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        interface = self._makeOne(supervisord)
        process = supervisord.process_groups['foo'].processes['foo']
        logfile = process.config.stdout_logfile
        import os
        try:
            f = open(logfile, 'w+')
            f.write(letters)
            f.close()
            
            data, offset, overflow = interface.tailProcessLog('foo', 
                                                        offset=0, 
                                                        length=len(letters))
            self.assertEqual(interface.update_text, 'tailProcessLog')
            self.assertEqual(overflow, False)
            self.assertEqual(offset, len(letters))
            self.assertEqual(data, letters)
        finally:
            os.remove(logfile)

    def test_tailProcessLog_none(self):
        # test nothing is returned when offset <= logsize
        from string import letters
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',
                               stdout_logfile='/tmp/fooooooo')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        interface = self._makeOne(supervisord)
        process = supervisord.process_groups['foo'].processes['foo']
        logfile = process.config.stdout_logfile
        import os
        try:
            f = open(logfile, 'w+')
            f.write(letters)
            f.close()

            # offset==logsize
            data, offset, overflow = interface.tailProcessLog('foo', 
                                                        offset=len(letters), 
                                                        length=100)
            self.assertEqual(interface.update_text, 'tailProcessLog')
            self.assertEqual(overflow, False)
            self.assertEqual(offset, len(letters))
            self.assertEqual(data, '')

            # offset > logsize
            data, offset, overflow = interface.tailProcessLog('foo', 
                                                        offset=len(letters)+5, 
                                                        length=100)
            self.assertEqual(interface.update_text, 'tailProcessLog')
            self.assertEqual(overflow, False)
            self.assertEqual(offset, len(letters))
            self.assertEqual(data, '')
        finally:
            os.remove(logfile)

    def test_tailProcessLog_overflow(self):
        # test buffer overflow occurs when logsize > offset+length
        from string import letters
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',
                              stdout_logfile='/tmp/fooooooo')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        interface = self._makeOne(supervisord)
        process = supervisord.process_groups['foo'].processes['foo']
        logfile = process.config.stdout_logfile
        import os
        try:
            f = open(logfile, 'w+')
            f.write(letters)
            f.close()

            data, offset, overflow = interface.tailProcessLog('foo', 
                                                        offset=0, length=5)
            self.assertEqual(interface.update_text, 'tailProcessLog')
            self.assertEqual(overflow, True)
            self.assertEqual(offset, len(letters))
            self.assertEqual(data, letters[-5:])
        finally:
            os.remove(logfile)
    
    def test_tailProcessLog_unreadable(self):
        # test nothing is returned if the log doesn't exist yet
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', '/bin/foo',
                               stdout_logfile='/tmp/fooooooo')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig)
        interface = self._makeOne(supervisord)
        process = supervisord.process_groups['foo'].processes['foo']
        logfile = process.config.stdout_logfile
                
        data, offset, overflow = interface.tailProcessLog('foo', 
                                                    offset=0, length=100)
        self.assertEqual(interface.update_text, 'tailProcessLog')
        self.assertEqual(overflow, False)
        self.assertEqual(offset, 0)
        self.assertEqual(data, '')

    def test_clearProcessLog_bad_name(self):
        from supervisor import xmlrpc
        supervisord = DummySupervisor()
        interface = self._makeOne(supervisord)
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.clearProcessLog,
                             'spew')

    def test_clearProcessLog(self):
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo')
        process = DummyProcess(pconfig)
        pgroup = DummyProcessGroup(None)
        pgroup.processes = {'foo': process}
        supervisord = DummySupervisor(process_groups={'foo':pgroup})
        interface = self._makeOne(supervisord)
        interface.clearProcessLog('foo')
        self.assertEqual(process.logsremoved, True)

    def test_clearProcessLog_failed(self):
        from supervisor import xmlrpc
        options = DummyOptions()
        pconfig = DummyPConfig(options, 'foo', 'foo')
        process = DummyProcess(pconfig)
        pgroup = DummyProcessGroup(None)
        pgroup.processes = {'foo': process}
        process.error_at_clear = True
        processes = {'foo': process}
        supervisord = DummySupervisor(process_groups={'foo':pgroup})
        interface = self._makeOne(supervisord)
        self.assertRaises(xmlrpc.RPCError, interface.clearProcessLog, 'foo')
        
    def test_clearAllProcessLogs(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'foo')
        pconfig2 = DummyPConfig(options, 'process2', 'bar')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        interface = self._makeOne(supervisord)
        callback = interface.clearAllProcessLogs()
        callback()
        results = callback()
        from supervisor import xmlrpc
        self.assertEqual(results[0],
                         {'name':'process1',
                          'group':'foo',
                          'status':xmlrpc.Faults.SUCCESS,
                          'description':'OK'})
        self.assertEqual(results[1],
                         {'name':'process2',
                          'group':'foo',
                          'status':xmlrpc.Faults.SUCCESS,
                          'description':'OK'})
        process1 = supervisord.process_groups['foo'].processes['process1']
        self.assertEqual(process1.logsremoved, True)
        process2 = supervisord.process_groups['foo'].processes['process2']
        self.assertEqual(process2.logsremoved, True)

    def test_clearAllProcessLogs_onefails(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'foo')
        pconfig2 = DummyPConfig(options, 'process2', 'bar')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1,
                                               pconfig2)
        supervisord.set_procattr('process1', 'error_at_clear', True)
        interface = self._makeOne(supervisord)
        callback = interface.clearAllProcessLogs()
        callback()
        results = callback()
        process1 = supervisord.process_groups['foo'].processes['process1']
        self.assertEqual(process1.logsremoved, False)
        process2 = supervisord.process_groups['foo'].processes['process2']
        self.assertEqual(process2.logsremoved, True)
        self.assertEqual(len(results), 2)
        from supervisor import xmlrpc
        self.assertEqual(results[0],
                         {'name':'process1',
                          'group':'foo',
                          'status':xmlrpc.Faults.FAILED,
                          'description':'FAILED: foo:process1'})
        self.assertEqual(results[1],
                         {'name':'process2',
                          'group':'foo',
                          'status':xmlrpc.Faults.SUCCESS,
                          'description':'OK'})

    def test_sendProcessStdin_raises_incorrect_params_when_not_chars(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'foo')
        supervisord = PopulatedDummySupervisor(options, 'foo', pconfig1)
        interface   = self._makeOne(supervisord)
        thing_not_chars = 42
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.INCORRECT_PARAMETERS,
                             interface.sendProcessStdin,
                             'process1', thing_not_chars)
    
    def test_sendProcessStdin_raises_bad_name_when_no_process(self):
        options = DummyOptions()
        supervisord = PopulatedDummySupervisor(options, 'foo')
        interface = self._makeOne(supervisord)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.BAD_NAME,
                             interface.sendProcessStdin,
                             'nonexistant_process_name', 'chars for stdin')

    def test_sendProcessStdin_raises_already_termed_when_not_process_pid(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'foo')
        supervisord = PopulatedDummySupervisor(options, 'process1', pconfig1)
        supervisord.set_procattr('process1', 'pid', 0)
        interface = self._makeOne(supervisord)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.ALREADY_TERMINATED,
                            interface.sendProcessStdin,
                            'process1', 'chars for stdin')

    def test_sendProcessStdin_raises_already_termed_when_killing(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'foo')
        supervisord = PopulatedDummySupervisor(options, 'process1', pconfig1)
        supervisord.set_procattr('process1', 'pid', 42)
        supervisord.set_procattr('process1', 'killing',True)
        interface   = self._makeOne(supervisord)
        from supervisor import xmlrpc
        self._assertRPCError(xmlrpc.Faults.ALREADY_TERMINATED,
                             interface.sendProcessStdin,
                             'process1', 'chars for stdin')
        
    def test_sendProcessStdin_writes_chars_and_returns_true(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'foo')
        supervisord = PopulatedDummySupervisor(options, 'process1', pconfig1)
        supervisord.set_procattr('process1', 'pid', 42)
        interface   = self._makeOne(supervisord)
        chars = 'chars for stdin'
        self.assertTrue(interface.sendProcessStdin('process1', chars))
        self.assertEqual('sendProcessStdin', interface.update_text)
        process1 = supervisord.process_groups['process1'].processes['process1']
        self.assertEqual(process1.stdin_buffer, chars)

    def test_sendProcessStdin_unicode_encoded_to_utf8(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'foo')
        supervisord = PopulatedDummySupervisor(options, 'process1', pconfig1)
        supervisord.set_procattr('process1', 'pid', 42)
        interface   = self._makeOne(supervisord)
        interface.sendProcessStdin('process1', u'fi\xed')
        process1 = supervisord.process_groups['process1'].processes['process1']
        self.assertEqual(process1.stdin_buffer, 'fi\xc3\xad')

class SystemNamespaceXMLRPCInterfaceTests(TestBase):
    def _getTargetClass(self):
        from supervisor import xmlrpc
        return xmlrpc.SystemNamespaceRPCInterface

    def _makeOne(self):
        from supervisor import rpcinterface
        supervisord = DummySupervisor()
        supervisor = rpcinterface.SupervisorNamespaceRPCInterface(supervisord)
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
        from supervisor import xmlrpc
        interface = self._makeOne()
        self._assertRPCError(xmlrpc.Faults.SIGNATURE_UNSUPPORTED,
                             interface.methodSignature,
                             ['foo.bar'])
        result = interface.methodSignature('system.methodSignature')
        self.assertEqual(result, ['array', 'string'])

    def test_allMethodDocs(self):
        from supervisor import xmlrpc
        # belt-and-suspenders test for docstring-as-typing parsing correctness
        # and documentation validity vs. implementation
        from supervisor import options
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
        from supervisor import http
        result = http.NOT_DONE_YET
        while result is http.NOT_DONE_YET:
            result = callback()
        self.assertEqual(result[0], interface.methodHelp('system.methodHelp'))
        self.assertEqual(result[1], interface.listMethods())

    def test_multicall_recursion_guard(self):
        from supervisor import xmlrpc
        interface = self._makeOne()
        callback = interface.multicall([
            {'methodName': 'system.multicall', 'params': []},        
        ])

        from supervisor import http
        result = http.NOT_DONE_YET
        while result is http.NOT_DONE_YET:
            result = callback()
        
        code = xmlrpc.Faults.INCORRECT_PARAMETERS
        desc = xmlrpc.getFaultDescription(code)
        recursion_fault = {'faultCode': code, 'faultString': desc}

        self.assertEqual(result, [recursion_fault])
        
    def test_multicall_nested_callback(self):
        interface = self._makeOne()
        callback = interface.multicall([
            {'methodName':'supervisor.stopAllProcesses'}])
        from supervisor import http
        result = http.NOT_DONE_YET
        while result is http.NOT_DONE_YET:
            result = callback()
        self.assertEqual(result[0], [])

    def test_methodHelp(self):
        from supervisor import xmlrpc
        interface = self._makeOne()
        self._assertRPCError(xmlrpc.Faults.SIGNATURE_UNSUPPORTED,
                             interface.methodHelp,
                             ['foo.bar'])
        help = interface.methodHelp('system.methodHelp')
        self.assertEqual(help, interface.methodHelp.__doc__)

class DummyRPCInterface:
    def hello(self):
        return 'Hello!'

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

