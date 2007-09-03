import sys
import unittest

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess

class EventSubscriptionNotificationTests(unittest.TestCase):
    def setUp(self):
        from supervisor import events
        events.callbacks[:] = []

    def tearDown(self):
        from supervisor import events
        events.callbacks[:] = []

    def test_subscribe(self):
        from supervisor import events
        events.subscribe(None, None)
        self.assertEqual(events.callbacks, [(None, None)])

    def test_clear(self):
        from supervisor import events
        events.callbacks[:] = [(None, None)]
        events.clear()
        self.assertEqual(events.callbacks, [])

    def test_notify_true(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(1)
        class DummyEvent:
            pass
        events.callbacks[:] = [(DummyEvent, callback)]
        events.notify(DummyEvent())
        self.assertEqual(L, [1])

    def test_notify_false(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(1)
        class DummyEvent:
            pass
        class AnotherEvent:
            pass
        events.callbacks[:] = [(AnotherEvent, callback)]
        events.notify(DummyEvent())
        self.assertEqual(L, [])

    def test_notify_via_subclass(self):
        from supervisor import events
        L = []
        def callback(event):
            L.append(1)
        class DummyEvent:
            pass
        class ASubclassEvent(DummyEvent):
            pass
        events.callbacks[:] = [(DummyEvent, callback)]
        events.notify(ASubclassEvent())
        self.assertEqual(L, [1])
        

class TestEventTypes(unittest.TestCase):
    def test_EventBufferOverflowEvent(self):
        from supervisor.events import EventBufferOverflowEvent
        inst = EventBufferOverflowEvent(1, 2)
        self.assertEqual(inst.group, 1)
        self.assertEqual(inst.event, 2)

    def test_ProcessCommunicationEvent(self):
        from supervisor.events import ProcessCommunicationEvent
        inst = ProcessCommunicationEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)

    def test_ProcessCommunicationStdoutEvent(self):
        from supervisor.events import ProcessCommunicationStdoutEvent
        inst = ProcessCommunicationStdoutEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)
        self.assertEqual(inst.channel, 'stdout')
        
    def test_ProcessCommunicationStderrEvent(self):
        from supervisor.events import ProcessCommunicationStderrEvent
        inst = ProcessCommunicationStderrEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)
        self.assertEqual(inst.channel, 'stderr')

    def test_ProcessStateChangeEvent(self):
        from supervisor.events import ProcessStateChangeEvent
        inst = ProcessStateChangeEvent(1, 2)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        
class TestSerializations(unittest.TestCase):
    def _deserialize(self, serialization):
        data = serialization.split('\n')
        headerdata = data[0]
        payload = ''
        headers = {}
        if len(data) > 1:
            payload = data[1]
        if headerdata:
            try:
                headers = dict( [ x.split(':',1) for x in
                                  headerdata.split()] )
            except ValueError:
                raise AssertionError('headerdata %r could not be deserialized' %
                                     headerdata)
        return headers, payload
    
    def test_pcomm_stdout_event(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        from supervisor.events import ProcessCommunicationStdoutEvent
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        event = ProcessCommunicationStdoutEvent(process1, 1, 'yo')
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers['processname'], 'process1', headers)
        self.assertEqual(headers['groupname'], 'process1', headers)
        self.assertEqual(headers['pid'], '1', headers)
        self.assertEqual(payload, 'yo')
            
    def test_pcomm_stderr_event(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        from supervisor.events import ProcessCommunicationStderrEvent
        event = ProcessCommunicationStderrEvent(process1, 1, 'yo')
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers['processname'], 'process1', headers)
        self.assertEqual(headers['groupname'], 'process1', headers)
        self.assertEqual(headers['pid'], '1', headers)

    def test_overflow_event(self):
        from supervisor import events
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'foo', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        wrapped = events.ProcessCommunicationStderrEvent(process1, 1, 'yo')
        event = events.EventBufferOverflowEvent(process1, wrapped)
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers['groupname'], 'foo')
        self.assertEqual(headers['eventtype'], 'None')

    def test_process_sc_event(self):
        from supervisor import events
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        event = events.StartingFromStoppedEvent(process1, 1)
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers['processname'], 'process1')
        self.assertEqual(headers['groupname'], 'process1')
        self.assertEqual(headers['pid'], '1')

    def test_supervisor_sc_event(self):
        from supervisor import events
        event = events.SupervisorRunningEvent()
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers, {})

class TestUtilityFunctions(unittest.TestCase):
    def test_getEventNameByType(self):
        from supervisor import events
        for name, value in events.EventTypes.__dict__.items():
            self.assertEqual(events.getEventNameByType(value), name)

    def _assertStateChange(self, old, new, expected):
        from supervisor.events import getProcessStateChangeEventType
        klass = getProcessStateChangeEventType(old, new)
        self.assertEqual(expected, klass)

    def test_getProcessStateChangeEventType_STOPPED_TO_STARTING(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.STOPPED, ProcessStates.STARTING,
                                events.StartingFromStoppedEvent)
        
    def test_getProcessStateChangeEventType_STARTING_TO_RUNNING(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.STARTING, ProcessStates.RUNNING,
                                events.RunningFromStartingEvent)

    def test_getProcessStateChangeEventType_STARTING_TO_BACKOFF(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.STARTING, ProcessStates.BACKOFF,
                                events.BackoffFromStartingEvent)

    def test_getProcessStateChangeEventType_BACKOFF_TO_STARTING(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.BACKOFF, ProcessStates.STARTING,
                                events.StartingFromBackoffEvent)

    def test_getProcessStateChangeEventType_BACKOFF_TO_FATAL(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.BACKOFF, ProcessStates.FATAL,
                                events.FatalFromBackoffEvent)

    def test_getProcessStateChangeEventType_FATAL_TO_STARTING(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.FATAL, ProcessStates.STARTING,
                                events.StartingFromFatalEvent)

    def test_getProcessStateChangeEventType_STARTING_TO_RUNNING(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.STARTING, ProcessStates.RUNNING,
                                events.RunningFromStartingEvent)

    def test_getProcessStateChangeEventType_RUNNING_TO_EXITED(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.RUNNING, ProcessStates.EXITED,
                                events.ExitedFromRunningEvent)

    def test_getProcessStateChangeEventType_EXITED_TO_STARTING(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.EXITED, ProcessStates.STARTING,
                                events.StartingFromExitedEvent)

    def test_getProcessStateChangeEventType_RUNNING_TO_STOPPING(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.RUNNING, ProcessStates.STOPPING,
                                events.StoppingFromRunningEvent)

    def test_getProcessStateChangeEventType_STOPPING_TO_STOPPED(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        self._assertStateChange(ProcessStates.STOPPING, ProcessStates.STOPPED,
                                events.StoppedFromStoppingEvent)

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

