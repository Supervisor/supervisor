import sys
import unittest

from supervisor.tests.base import DummyOptions
from supervisor.tests.base import DummyPConfig
from supervisor.tests.base import DummyProcess
from supervisor.tests.base import DummyEvent

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
    def test_ProcessLogEvent_attributes(self):
        from supervisor.events import ProcessLogEvent
        inst = ProcessLogEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)

    def test_ProcessLogEvent_inheritence(self):
        from supervisor.events import ProcessLogEvent
        from supervisor.events import Event
        self.assertTrue(
            issubclass(ProcessLogEvent, Event)
        )

    def test_ProcessLogStdoutEvent_attributes(self):
        from supervisor.events import ProcessLogStdoutEvent
        inst = ProcessLogStdoutEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)
        self.assertEqual(inst.channel, 'stdout')

    def test_ProcessLogStdoutEvent_inheritence(self):
        from supervisor.events import ProcessLogStdoutEvent
        from supervisor.events import ProcessLogEvent
        self.assertTrue(
            issubclass(ProcessLogStdoutEvent, ProcessLogEvent)
        )

    def test_ProcessLogStderrEvent_attributes(self):
        from supervisor.events import ProcessLogStderrEvent
        inst = ProcessLogStderrEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)
        self.assertEqual(inst.channel, 'stderr')

    def test_ProcessLogStderrEvent_inheritence(self):
        from supervisor.events import ProcessLogStderrEvent
        from supervisor.events import ProcessLogEvent
        self.assertTrue(
            issubclass(ProcessLogStderrEvent, ProcessLogEvent)
        )

    def test_ProcessCommunicationEvent_attributes(self):
        from supervisor.events import ProcessCommunicationEvent
        inst = ProcessCommunicationEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)

    def test_ProcessCommunicationEvent_inheritence(self):
        from supervisor.events import ProcessCommunicationEvent
        from supervisor.events import Event
        self.assertTrue(
            issubclass(ProcessCommunicationEvent, Event)
        )

    def test_ProcessCommunicationStdoutEvent_attributes(self):
        from supervisor.events import ProcessCommunicationStdoutEvent
        inst = ProcessCommunicationStdoutEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)
        self.assertEqual(inst.channel, 'stdout')

    def test_ProcessCommunicationStdoutEvent_inheritence(self):
        from supervisor.events import ProcessCommunicationStdoutEvent
        from supervisor.events import ProcessCommunicationEvent
        self.assertTrue(
            issubclass(ProcessCommunicationStdoutEvent, 
                       ProcessCommunicationEvent)
        )
        
    def test_ProcessCommunicationStderrEvent_attributes(self):
        from supervisor.events import ProcessCommunicationStderrEvent
        inst = ProcessCommunicationStderrEvent(1, 2, 3)
        self.assertEqual(inst.process, 1)
        self.assertEqual(inst.pid, 2)
        self.assertEqual(inst.data, 3)
        self.assertEqual(inst.channel, 'stderr')

    def test_ProcessCommunicationStderrEvent_inheritence(self):
        from supervisor.events import ProcessCommunicationStderrEvent
        from supervisor.events import ProcessCommunicationEvent
        self.assertTrue(
            issubclass(ProcessCommunicationStderrEvent, 
                       ProcessCommunicationEvent)
        )

    def test_RemoteCommunicationEvent_attributes(self):
        from supervisor.events import RemoteCommunicationEvent
        inst = RemoteCommunicationEvent(1, 2)
        self.assertEqual(inst.type, 1)
        self.assertEqual(inst.data, 2)

    def test_RemoteCommunicationEvent_inheritence(self):
        from supervisor.events import RemoteCommunicationEvent
        from supervisor.events import Event
        self.assertTrue(
            issubclass(RemoteCommunicationEvent, Event)
        )

    def test_EventRejectedEvent_attributes(self):
        from supervisor.events import EventRejectedEvent
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process = DummyProcess(pconfig1)
        rejected_event = DummyEvent()
        event = EventRejectedEvent(process, rejected_event)
        self.assertEqual(event.process, process)
        self.assertEqual(event.event, rejected_event)

    def test_EventRejectedEvent_does_not_inherit_from_event(self):
        from supervisor.events import EventRejectedEvent
        from supervisor.events import Event
        self.assertFalse(
            issubclass(EventRejectedEvent, Event)
        )

    def test_all_SupervisorStateChangeEvents(self):
        from supervisor import events
        for klass in (
            events.SupervisorStateChangeEvent,
            events.SupervisorRunningEvent,
            events.SupervisorStoppingEvent        
            ):
            self._test_one_SupervisorStateChangeEvent(klass)

    def _test_one_SupervisorStateChangeEvent(self, klass):
        from supervisor.events import SupervisorStateChangeEvent
        self.assertTrue(issubclass(klass, SupervisorStateChangeEvent))

    def test_all_ProcessStateEvents(self):
        from supervisor import events
        for klass in (
            events.ProcessStateEvent,
            events.ProcessStateStoppedEvent,
            events.ProcessStateExitedEvent,
            events.ProcessStateFatalEvent,
            events.ProcessStateBackoffEvent,
            events.ProcessStateRunningEvent,
            events.ProcessStateUnknownEvent,
            events.ProcessStateStoppingEvent,
            events.ProcessStateStartingEvent,
            ):
            self._test_one_ProcessStateEvent(klass)

    def _test_one_ProcessStateEvent(self, klass):
        from supervisor.states import ProcessStates
        from supervisor.events import ProcessStateEvent
        self.assertTrue(issubclass(klass, ProcessStateEvent))
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process = DummyProcess(pconfig1)
        inst = klass(process, ProcessStates.STARTING)
        self.assertEqual(inst.process, process)
        self.assertEqual(inst.from_state, ProcessStates.STARTING)
        self.assertEqual(inst.expected, True)

    def test_all_TickEvents(self):
        from supervisor import events
        for klass in (
           events.TickEvent,
           events.Tick5Event,
           events.Tick60Event,
           events.Tick3600Event
           ):
           self._test_one_TickEvent(klass)

    def _test_one_TickEvent(self, klass):
        from supervisor.events import TickEvent
        self.assertTrue(issubclass(klass, TickEvent))
        
        inst = klass(1, 2)
        self.assertEqual(inst.when, 1)
        self.assertEqual(inst.supervisord, 2)
        
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

    def test_plog_stdout_event(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        from supervisor.events import ProcessLogStdoutEvent
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        event = ProcessLogStdoutEvent(process1, 1, 'yo')
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers['processname'], 'process1', headers)
        self.assertEqual(headers['groupname'], 'process1', headers)
        self.assertEqual(headers['pid'], '1', headers)
        self.assertEqual(payload, 'yo')

    def test_plog_stderr_event(self):
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        from supervisor.events import ProcessLogStderrEvent
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        event = ProcessLogStderrEvent(process1, 1, 'yo')
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers['processname'], 'process1', headers)
        self.assertEqual(headers['groupname'], 'process1', headers)
        self.assertEqual(headers['pid'], '1', headers)
        self.assertEqual(payload, 'yo')
            
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
        self.assertEqual(payload, 'yo')

    def test_remote_comm_event(self):
        from supervisor.events import RemoteCommunicationEvent
        event = RemoteCommunicationEvent('foo', 'bar')
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers['type'], 'foo', headers)
        self.assertEqual(payload, 'bar')

    def test_process_state_events_without_extra_values(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        for klass in (
            events.ProcessStateFatalEvent,
            events.ProcessStateUnknownEvent,
            ):
            options = DummyOptions()
            pconfig1 = DummyPConfig(options, 'process1', 'process1',
                                    '/bin/process1')
            class DummyGroup:
                config = pconfig1
            process1 = DummyProcess(pconfig1)
            process1.group = DummyGroup
            event = klass(process1, ProcessStates.STARTING)
            headers, payload = self._deserialize(str(event))
            self.assertEqual(len(headers), 3)
            self.assertEqual(headers['processname'], 'process1')
            self.assertEqual(headers['groupname'], 'process1')
            self.assertEqual(headers['from_state'], 'STARTING')
            self.assertEqual(payload, '')

    def test_process_state_events_with_pid(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        for klass in (
            events.ProcessStateRunningEvent,
            events.ProcessStateStoppedEvent,
            events.ProcessStateStoppingEvent,
            ):
            options = DummyOptions()
            pconfig1 = DummyPConfig(options, 'process1', 'process1',
                                    '/bin/process1')
            class DummyGroup:
                config = pconfig1
            process1 = DummyProcess(pconfig1)
            process1.group = DummyGroup
            process1.pid = 1
            event = klass(process1, ProcessStates.STARTING)
            headers, payload = self._deserialize(str(event))
            self.assertEqual(len(headers), 4)
            self.assertEqual(headers['processname'], 'process1')
            self.assertEqual(headers['groupname'], 'process1')
            self.assertEqual(headers['from_state'], 'STARTING')
            self.assertEqual(headers['pid'], '1')
            self.assertEqual(payload, '')

    def test_process_state_events_starting_and_backoff(self):
        from supervisor.states import ProcessStates
        from supervisor import events
        for klass in (
            events.ProcessStateStartingEvent,
            events.ProcessStateBackoffEvent,
            ):
            options = DummyOptions()
            pconfig1 = DummyPConfig(options, 'process1', 'process1',
                                    '/bin/process1')
            class DummyGroup:
                config = pconfig1
            process1 = DummyProcess(pconfig1)
            process1.group = DummyGroup
            event = klass(process1, ProcessStates.STARTING)
            headers, payload = self._deserialize(str(event))
            self.assertEqual(len(headers), 4)
            self.assertEqual(headers['processname'], 'process1')
            self.assertEqual(headers['groupname'], 'process1')
            self.assertEqual(headers['from_state'], 'STARTING')
            self.assertEqual(headers['tries'], '0')
            self.assertEqual(payload, '')
            process1.backoff = 1
            event = klass(process1, ProcessStates.STARTING)
            headers, payload = self._deserialize(str(event))
            self.assertEqual(headers['tries'], '1')
            process1.backoff = 2
            event = klass(process1, ProcessStates.STARTING)
            headers, payload = self._deserialize(str(event))
            self.assertEqual(headers['tries'], '2')
        
    def test_process_state_exited_event_expected(self):
        from supervisor import events
        from supervisor.states import ProcessStates
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        process1.pid = 1
        event = events.ProcessStateExitedEvent(process1,
                                               ProcessStates.STARTING,
                                               expected=True)
        headers, payload = self._deserialize(str(event))
        self.assertEqual(len(headers), 5)
        self.assertEqual(headers['processname'], 'process1')
        self.assertEqual(headers['groupname'], 'process1')
        self.assertEqual(headers['pid'], '1')
        self.assertEqual(headers['from_state'], 'STARTING')
        self.assertEqual(headers['expected'], '1')
        self.assertEqual(payload, '')

    def test_process_state_exited_event_unexpected(self):
        from supervisor import events
        from supervisor.states import ProcessStates
        options = DummyOptions()
        pconfig1 = DummyPConfig(options, 'process1', 'process1','/bin/process1')
        process1 = DummyProcess(pconfig1)
        class DummyGroup:
            config = pconfig1
        process1.group = DummyGroup
        process1.pid = 1
        event = events.ProcessStateExitedEvent(process1,
                                               ProcessStates.STARTING,
                                               expected=False)
        headers, payload = self._deserialize(str(event))
        self.assertEqual(len(headers), 5)
        self.assertEqual(headers['processname'], 'process1')
        self.assertEqual(headers['groupname'], 'process1')
        self.assertEqual(headers['pid'], '1')
        self.assertEqual(headers['from_state'], 'STARTING')
        self.assertEqual(headers['expected'], '0')
        self.assertEqual(payload, '')

    def test_supervisor_sc_event(self):
        from supervisor import events
        event = events.SupervisorRunningEvent()
        headers, payload = self._deserialize(str(event))
        self.assertEqual(headers, {})
        self.assertEqual(payload, '')

    def test_tick_events(self):
        from supervisor import events
        for klass in (
            events.Tick5Event,
            events.Tick60Event,
            events.Tick3600Event,
            ):
            event = klass(1, 2)
            headers, payload = self._deserialize(str(event))
            self.assertEqual(headers, {'when':'1'})
            self.assertEqual(payload, '')

class TestUtilityFunctions(unittest.TestCase):
    def test_getEventNameByType(self):
        from supervisor import events
        for name, value in events.EventTypes.__dict__.items():
            self.assertEqual(events.getEventNameByType(value), name)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

