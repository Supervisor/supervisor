# This module must not depend on any other non-stdlib module to prevent
# circular import problems.
from functools import partial


def getState(cls, code):
    for statename in cls.__dict__:
        if getattr(cls, statename) == code:
            return statename


class ProcessStates:
    STOPPED = 0
    STARTING = 10
    RUNNING = 20
    BACKOFF = 30
    STOPPING = 40
    EXITED = 100
    FATAL = 200
    UNKNOWN = 1000

STOPPED_STATES = (ProcessStates.STOPPED,
                  ProcessStates.EXITED,
                  ProcessStates.FATAL,
                  ProcessStates.UNKNOWN)

RUNNING_STATES = (ProcessStates.RUNNING,
                  ProcessStates.BACKOFF,
                  ProcessStates.STARTING)


getProcessStateDescription = partial(getState, ProcessStates)


class SupervisorStates:
    FATAL = 2
    RUNNING = 1
    RESTARTING = 0
    SHUTDOWN = -1


getSupervisorStateDescription = partial(getState, SupervisorStates)


class EventListenerStates:
    READY = 10 # the process ready to be sent an event from supervisor
    BUSY = 20 # event listener is processing an event sent to it by supervisor
    ACKNOWLEDGED = 30 # the event listener processed an event
    UNKNOWN = 40 # the event listener is in an unknown state

getEventListenerStateDescription = partial(getState, EventListenerStates)
