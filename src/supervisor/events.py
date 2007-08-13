##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

import types

from supervisor.states import ProcessStates
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

class EventBufferOverflowEvent(Event):
    def __init__(self, group, event):
        self.group = group
        self.event = event

class ProcessCommunicationEvent(Event):
    # event mode tokens
    BEGIN_TOKEN = '<!--XSUPERVISOR:BEGIN-->'
    END_TOKEN   = '<!--XSUPERVISOR:END-->'
    def __init__(self, process, data):
        self.process = process
        self.data = data

class ProcessCommunicationStdoutEvent(ProcessCommunicationEvent):
    channel = 'stdout'

class ProcessCommunicationStderrEvent(ProcessCommunicationEvent):
    channel = 'stderr'

class ProcessStateChangeEvent(Event):
    """ Abstract class, never raised directly """
    frm = None
    to = None
    def __init__(self, process):
        self.process = process

class StartingFromStoppedEvent(ProcessStateChangeEvent):
    frm = ProcessStates.STOPPED
    to = ProcessStates.STARTING

class StartingFromBackoffEvent(ProcessStateChangeEvent):
    frm = ProcessStates.BACKOFF
    to = ProcessStates.STARTING

class StartingFromExitedEvent(ProcessStateChangeEvent):
    frm = ProcessStates.EXITED
    to = ProcessStates.STARTING

class StartingFromFatalEvent(ProcessStateChangeEvent):
    frm = ProcessStates.FATAL
    to = ProcessStates.STARTING

class RunningFromStartingEvent(ProcessStateChangeEvent):
    frm = ProcessStates.STARTING
    to = ProcessStates.RUNNING

class BackoffFromStartingEvent(ProcessStateChangeEvent):
    frm = ProcessStates.STARTING
    to = ProcessStates.BACKOFF

class StoppingFromRunningEvent(ProcessStateChangeEvent):
    frm = ProcessStates.RUNNING
    to = ProcessStates.STOPPING

class StoppingFromStartingEvent(ProcessStateChangeEvent):
    frm = ProcessStates.STARTING
    to = ProcessStates.STOPPING

class ExitedOrStoppedEvent(ProcessStateChangeEvent):
    """ Abstract class, never raised directly """
    frm = None
    to = None

class ExitedFromRunningEvent(ExitedOrStoppedEvent):
    frm = ProcessStates.RUNNING
    to = ProcessStates.EXITED

class StoppedFromStoppingEvent(ExitedOrStoppedEvent):
    frm = ProcessStates.STOPPING
    to = ProcessStates.STOPPED

class FatalFromBackoffEvent(ProcessStateChangeEvent):
    frm = ProcessStates.BACKOFF
    to = ProcessStates.FATAL

_ANY = ()

class ToUnknownEvent(ProcessStateChangeEvent):
    frm = _ANY
    to = ProcessStates.UNKNOWN

class SupervisorStateChangeEvent(Event):
    """ Abstract class """

class SupervisorRunningEvent(SupervisorStateChangeEvent):
    pass

class SupervisorStoppingEvent(SupervisorStateChangeEvent):
    pass

class EventRejectedEvent:
    def __init__(self, process, event):
        self.process = process
        self.event = event

class EventTypes:
    EVENT = Event
    PROCESS_STATE_CHANGE = ProcessStateChangeEvent
    STARTING_FROM_STOPPED = StartingFromStoppedEvent
    STARTING_FROM_BACKOFF = StartingFromBackoffEvent
    STARTING_FROM_EXITED = StartingFromExitedEvent
    STARTING_FROM_FATAL = StartingFromFatalEvent
    RUNNING = RunningFromStartingEvent
    BACKOFF = BackoffFromStartingEvent
    STOPPING_FROM_RUNNING = StoppingFromRunningEvent
    STOPPING_FROM_STARTING = StoppingFromStartingEvent
    EXITED_OR_STOPPED = ExitedOrStoppedEvent
    EXITED = ExitedFromRunningEvent
    STOPPED = StoppedFromStoppingEvent
    FATAL = FatalFromBackoffEvent
    UNKNOWN = ToUnknownEvent
    PROCESS_COMMUNICATION = ProcessCommunicationEvent
    PROCESS_COMMUNICATION_STDOUT = ProcessCommunicationStdoutEvent
    PROCESS_COMMUNICATION_STDERR = ProcessCommunicationStderrEvent
    SUPERVISOR_STATE_CHANGE = SupervisorStateChangeEvent
    SUPERVISOR_RUNNING = SupervisorRunningEvent
    SUPERVISOR_STOPPING = SupervisorStoppingEvent
    EVENT_BUFFER_OVERFLOW = EventBufferOverflowEvent

def getEventNameByType(requested):
    for name, typ in EventTypes.__dict__.items():
        if typ is requested:
            return name

_map = {}

def _makeProcessStateChangeMap():
    states = ProcessStates.__dict__.values()
    for old_state in states:
        for new_state in states:
            for name, typ in EventTypes.__dict__.items():
                if type(typ) is types.ClassType:
                    if issubclass(typ, ProcessStateChangeEvent):
                        if typ.frm == old_state or typ.frm is _ANY:
                            if typ.to == new_state or typ.to is _ANY:
                                _map[(old_state, new_state)] = typ

_makeProcessStateChangeMap()

def getProcessStateChangeEventType(old_state, new_state):
    typ = _map.get((old_state, new_state))
    if typ is None:
        old_desc = getProcessStateDescription(old_state)
        new_desc = getProcessStateDescription(new_state)
        raise NotImplementedError(
            'Unknown transition (%s (%s) -> %s (%s))' % (
            old_desc, old_state, new_desc, new_state)
            )
    return typ
        
        
