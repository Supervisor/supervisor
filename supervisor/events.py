from supervisor.states import getProcessStateDescription

callbacks = []

def subscribe(type, callback):
    callbacks.append((type, callback))
    
def notify(event):
    for type, callback in callbacks:
        if isinstance(event, type):
            callback(event)

def clear():
    callbacks[:] = []

class Event:
    """ Abstract event type """
    pass

class ProcessLogEvent(Event):
    """ Abstract """
    channel = None
    def __init__(self, process, pid, data):
        self.process = process
        self.pid = pid
        self.data = data

    def __str__(self):
        groupname = ''
        if self.process.group is not None:
            groupname = self.process.group.config.name
        return 'processname:%s groupname:%s pid:%s channel:%s\n%s' % (
            self.process.config.name,
            groupname,
            self.pid,
            self.channel,
            self.data)

class ProcessLogStdoutEvent(ProcessLogEvent):
    channel = 'stdout'

class ProcessLogStderrEvent(ProcessLogEvent):
    channel = 'stderr'

class ProcessCommunicationEvent(Event):
    """ Abstract """
    # event mode tokens
    BEGIN_TOKEN = '<!--XSUPERVISOR:BEGIN-->'
    END_TOKEN   = '<!--XSUPERVISOR:END-->'

    def __init__(self, process, pid, data):
        self.process = process
        self.pid = pid
        self.data = data

    def __str__(self):
        groupname = ''
        if self.process.group is not None:
            groupname = self.process.group.config.name
        return 'processname:%s groupname:%s pid:%s\n%s' % (
            self.process.config.name,
            groupname,
            self.pid,
            self.data)

class ProcessCommunicationStdoutEvent(ProcessCommunicationEvent):
    channel = 'stdout'

class ProcessCommunicationStderrEvent(ProcessCommunicationEvent):
    channel = 'stderr'

class RemoteCommunicationEvent(Event):
    def __init__(self, type, data):
        self.type = type
        self.data = data

    def __str__(self):
        return 'type:%s\n%s' % (self.type, self.data)

class SupervisorStateChangeEvent(Event):
    """ Abstract class """
    def __str__(self):
        return ''

class SupervisorRunningEvent(SupervisorStateChangeEvent):
    pass

class SupervisorStoppingEvent(SupervisorStateChangeEvent):
    pass

class EventRejectedEvent: # purposely does not subclass Event 
    def __init__(self, process, event):
        self.process = process
        self.event = event

class ProcessStateEvent(Event):
    """ Abstract class, never raised directly """
    frm = None
    to = None
    def __init__(self, process, from_state, expected=True):
        self.process = process
        self.from_state = from_state
        self.expected = expected
        # we eagerly render these so if the process pid, etc changes beneath
        # us, we stash the values at the time the event was sent
        self.extra_values = self.get_extra_values()

    def __str__(self):
        groupname = ''
        if self.process.group is not None:
            groupname = self.process.group.config.name
        L = [('processname', self.process.config.name), ('groupname', groupname),
             ('from_state', getProcessStateDescription(self.from_state))]
        L.extend(self.extra_values)
        s = ' '.join( [ '%s:%s' % (name, val) for (name, val) in L ] )
        return s

    def get_extra_values(self):
        return []

class ProcessStateFatalEvent(ProcessStateEvent):
    pass

class ProcessStateUnknownEvent(ProcessStateEvent):
    pass

class ProcessStateStartingOrBackoffEvent(ProcessStateEvent):
    def get_extra_values(self):
        return [('tries', int(self.process.backoff))]

class ProcessStateBackoffEvent(ProcessStateStartingOrBackoffEvent):
    pass

class ProcessStateStartingEvent(ProcessStateStartingOrBackoffEvent):
    pass

class ProcessStateExitedEvent(ProcessStateEvent):
    def get_extra_values(self):
        return [('expected', int(self.expected)), ('pid', self.process.pid)]

class ProcessStateRunningEvent(ProcessStateEvent):
    def get_extra_values(self):
        return [('pid', self.process.pid)]

class ProcessStateStoppingEvent(ProcessStateEvent):
    def get_extra_values(self):
        return [('pid', self.process.pid)]

class ProcessStateStoppedEvent(ProcessStateEvent):
    def get_extra_values(self):
        return [('pid', self.process.pid)]

class ProcessGroupEvent(Event):
    def __init__(self, group):
        self.group = group
    def __str__(self):
        return 'groupname:%s\n' % self.group

class ProcessGroupAddedEvent(ProcessGroupEvent):
    pass

class ProcessGroupRemovedEvent(ProcessGroupEvent):
    pass

class TickEvent(Event):
    """ Abstract """
    def __init__(self, when, supervisord):
        self.when = when
        self.supervisord = supervisord

    def __str__(self):
        return 'when:%s' % self.when

class Tick5Event(TickEvent):
    period = 5

class Tick60Event(TickEvent):
    period = 60

class Tick3600Event(TickEvent):
    period = 3600

TICK_EVENTS = [ Tick5Event, Tick60Event, Tick3600Event ] # imported elsewhere

class EventTypes:
    EVENT = Event # abstract
    PROCESS_STATE = ProcessStateEvent # abstract
    PROCESS_STATE_STOPPED = ProcessStateStoppedEvent
    PROCESS_STATE_EXITED = ProcessStateExitedEvent
    PROCESS_STATE_STARTING = ProcessStateStartingEvent
    PROCESS_STATE_STOPPING = ProcessStateStoppingEvent
    PROCESS_STATE_BACKOFF = ProcessStateBackoffEvent
    PROCESS_STATE_FATAL = ProcessStateFatalEvent
    PROCESS_STATE_RUNNING = ProcessStateRunningEvent
    PROCESS_STATE_UNKNOWN = ProcessStateUnknownEvent
    PROCESS_COMMUNICATION = ProcessCommunicationEvent # abstract
    PROCESS_COMMUNICATION_STDOUT = ProcessCommunicationStdoutEvent
    PROCESS_COMMUNICATION_STDERR = ProcessCommunicationStderrEvent
    PROCESS_LOG = ProcessLogEvent
    PROCESS_LOG_STDOUT = ProcessLogStdoutEvent
    PROCESS_LOG_STDERR = ProcessLogStderrEvent     
    REMOTE_COMMUNICATION = RemoteCommunicationEvent
    SUPERVISOR_STATE_CHANGE = SupervisorStateChangeEvent # abstract
    SUPERVISOR_STATE_CHANGE_RUNNING = SupervisorRunningEvent
    SUPERVISOR_STATE_CHANGE_STOPPING = SupervisorStoppingEvent
    TICK = TickEvent # abstract
    TICK_5 = Tick5Event
    TICK_60 = Tick60Event
    TICK_3600 = Tick3600Event
    PROCESS_GROUP = ProcessGroupEvent # abstract
    PROCESS_GROUP_ADDED = ProcessGroupAddedEvent
    PROCESS_GROUP_REMOVED = ProcessGroupRemovedEvent

def getEventNameByType(requested):
    for name, typ in EventTypes.__dict__.items():
        if typ is requested:
            return name

def register(name, event):
    setattr(EventTypes, name, event)
