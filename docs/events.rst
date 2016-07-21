.. _events:

Events
======

Events are an advanced feature of Supervisor introduced in version
3.0.  You don't need to understand events if you simply want to use
Supervisor as a mechanism to restart crashed processes or as a system
to manually control process state.  You do need to understand events
if you want to use Supervisor as part of a process
monitoring/notification framework.

Event Listeners and Event Notifications
---------------------------------------

Supervisor provides a way for a specially written program (which it
runs as a subprocess) called an "event listener" to subscribe to
"event notifications".  An event notification implies that something
happened related to a subprocess controlled by :program:`supervisord`
or to :program:`supervisord` itself.  Event notifications are grouped
into types in order to make it possible for event listeners to
subscribe to a limited subset of event notifications.  Supervisor
continually emits event notifications as its running even if there are
no listeners configured.  If a listener is configured and subscribed
to an event type that is emitted during a :program:`supervisord`
lifetime, that listener will be notified.

The purpose of the event notification/subscription system is to
provide a mechanism for arbitrary code to be run (e.g. send an email,
make an HTTP request, etc) when some condition is met.  That condition
usually has to do with subprocess state.  For instance, you may want
to notify someone via email when a process crashes and is restarted by
Supervisor.

The event notification protocol is based on communication via a
subprocess' stdin and stdout.  Supervisor sends specially-formatted
input to an event listener process' stdin and expects
specially-formatted output from an event listener's stdout, forming a
request-response cycle.  A protocol agreed upon between supervisor and
the listener's implementer allows listeners to process event
notifications.  Event listeners can be written in any language
supported by the platform you're using to run Supervisor.  Although
event listeners may be written in any language, there is special
library support for Python in the form of a
:mod:`supervisor.childutils` module, which makes creating event
listeners in Python slightly easier than in other languages.

Configuring an Event Listener
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A supervisor event listener is specified via a ``[eventlistener:x]``
section in the configuration file.  Supervisor ``[eventlistener:x]``
sections are treated almost exactly like supervisor ``[program:x]``
section with the respect to the keys allowed in their configuration
except that Supervisor does not respect "capture mode" output from
event listener processes (ie. event listeners cannot be
``PROCESS_COMMUNICATIONS_EVENT`` event generators).  Therefore it is
an error to specify ``stdout_capture_maxbytes`` or
``stderr_capture_maxbytes`` in the configuration of an eventlistener.
There is no artificial constraint on the number of eventlistener
sections that can be placed into the configuration file.

When an ``[eventlistener:x]`` section is defined, it actually defines
a "pool", where the number of event listeners in the pool is
determined by the ``numprocs`` value within the section.

The ``events`` parameter of the ``[eventlistener:x]`` section
specifies the events that will be sent to a listener pool.  A
well-written event listener will ignore events that it cannot process,
but there is no guarantee that a specific event listener won't crash
as a result of receiving an event type it cannot handle.  Therefore,
depending on the listener implementation, it may be important to
specify in the configuration that it may receive only certain types of
events.  The implementor of the event listener is the only person who
can tell you what these are (and therefore what value to put in the
``events`` configuration).  Examples of eventlistener
configurations that can be placed in ``supervisord.conf`` are as
follows.

.. code-block:: ini

   [eventlistener:memmon]
   command=memmon -a 200MB -m bob@example.com
   events=TICK_60

.. code-block:: ini

   [eventlistener:mylistener]
   command=my_custom_listener.py
   events=PROCESS_STATE,TICK_60

.. note::

   An advanced feature, specifying an alternate "result handler" for a
   pool, can be specified via the ``result_handler`` parameter of an
   ``[eventlistener:x]`` section in the form of a `pkg_resources
   <http://peak.telecommunity.com/DevCenter/PkgResources>`_ "entry
   point" string.  The default result handler is
   ``supervisord.dispatchers:default_handler``.  Creating an alternate
   result handler is not currently documented.

When an event notification is sent by supervisor, all event listener
pools which are subscribed to receive events for the event's type
(filtered by the ``events`` value in the eventlistener
section) will be found.  One of the listeners in each listener pool
will receive the event notification (any "available" listener).

Every process in an event listener pool is treated equally by
supervisor.  If a process in the pool is unavailable (because it is
already processing an event, because it has crashed, or because it has
elected to removed itself from the pool), supervisor will choose
another process from the pool.  If the event cannot be sent because
all listeners in the pool are "busy", the event will be buffered and
notification will be retried later.  "Later" is defined as "the next
time that the :program:`supervisord` select loop executes".  For
satisfactory event processing performance, you should configure a pool
with as many event listener processes as appropriate to handle your
event load.  This can only be determined empirically for any given
workload, there is no "magic number" but to help you determine the
optimal number of listeners in a given pool, Supervisor will emit
warning messages to its activity log when an event cannot be sent
immediately due to pool congestion.  There is no artificial constraint
placed on the number of processes that can be in a pool, it is limited
only by your platform constraints.

A listener pool has an event buffer queue.  The queue is sized via the
listener pool's ``buffer_size`` config file option.  If the queue is
full and supervisor attempts to buffer an event, supervisor will throw
away the oldest event in the buffer and log an error.

Writing an Event Listener
~~~~~~~~~~~~~~~~~~~~~~~~~

An event listener implementation is a program that is willing to
accept structured input on its stdin stream and produce structured
output on its stdout stream.  An event listener implementation should
operate in "unbuffered" mode or should flush its stdout every time it
needs to communicate back to the supervisord process.  Event listeners
can be written to be long-running or may exit after a single request
(depending on the implementation and the ``autorestart`` parameter in
the eventlistener's configuration).

An event listener can send arbitrary output to its stderr, which will
be logged or ignored by supervisord depending on the stderr-related
logfile configuration in its ``[eventlistener:x]`` section.

Event Notification Protocol
+++++++++++++++++++++++++++

When supervisord sends a notification to an event listener process,
the listener will first be sent a single "header" line on its
stdin. The composition of the line is a set of colon-separated tokens
(each of which represents a key-value pair) separated from each other
by a single space.  The line is terminated with a ``\n`` (linefeed)
character.  The tokens on the line are not guaranteed to be in any
particular order.  The types of tokens currently defined are in the
table below.

Header Tokens
@@@@@@@@@@@@@

=========== =============================================   ===================
Key         Description                                     Example
=========== =============================================   ===================
ver         The event system protocol version               3.0
server      The identifier of the supervisord sending the
            event (see config file ``[supervisord]``
            section ``identifier`` value.
serial      An integer assigned to each event.  No two      30
            events generated during the lifetime of
            a :program:`supervisord` process will have
            the same serial number.  The value is useful
            for functional testing and detecting event
            ordering anomalies.
pool        The name of the event listener pool which       myeventpool
            generated this event.
poolserial  An integer assigned to each event by the        30
            eventlistener pool which it is being sent
            from.  No two events generated by the same
            eventlister pool during the lifetime of a
            :program:`supervisord` process will have the
            same ``poolserial`` number.  This value can
            be used to detect event ordering anomalies.
eventname   The specific event type name (see               TICK_5
            :ref:`event_types`)
len         An integer indicating the number of bytes in    22
            the event payload, aka the ``PAYLOAD_LENGTH``
=========== =============================================   ===================

An example of a complete header line is as follows.

.. code-block:: text

   ver:3.0 server:supervisor serial:21 pool:listener poolserial:10 eventname:PROCESS_COMMUNICATION_STDOUT len:54

Directly following the linefeed character in the header is the event
payload.  It consists of ``PAYLOAD_LENGTH`` bytes representing a
serialization of the event data.  See :ref:`event_types` for the
specific event data serialization definitions.

An example payload for a ``PROCESS_COMMUNICATION_STDOUT`` event
notification is as follows.

.. code-block:: text

   processname:foo groupname:bar pid:123
   This is the data that was sent between the tags

The payload structure of any given event is determined only by the
event's type.

Event Listener States
+++++++++++++++++++++

An event listener process has three possible states that are
maintained by supervisord:

=============================   ==============================================
Name                            Description
=============================   ==============================================
ACKNOWLEDGED                    The event listener has acknowledged (accepted
                                or rejected) an event send.
READY                           Event notificatons may be sent to this event
                                listener
BUSY                            Event notifications may not be sent to this
                                event listener.
=============================   ==============================================

When an event listener process first starts, supervisor automatically
places it into the ``ACKNOWLEDGED`` state to allow for startup
activities or guard against startup failures (hangs).  Until the
listener sends a ``READY\n`` string to its stdout, it will stay in
this state.

When supervisor sends an event notification to a listener in the
``READY`` state, the listener will be placed into the ``BUSY`` state
until it receives an ``OK`` or ``FAIL`` response from the listener, at
which time, the listener will be transitioned back into the
``ACKNOWLEDGED`` state.

Event Listener Notification Protocol
++++++++++++++++++++++++++++++++++++

Supervisor will notify an event listener in the ``READY`` state of an
event by sending data to the stdin of the process.  Supervisor will
never send anything to the stdin of an event listener process while
that process is in the ``BUSY`` or ``ACKNOWLEDGED`` state.  Supervisor
starts by sending the header.

Once it has processed the header, the event listener implementation
should read ``PAYLOAD_LENGTH`` bytes from its stdin, perform an
arbitrary action based on the values in the header and the data parsed
out of the serialization.  It is free to block for an arbitrary amount
of time while doing this.  Supervisor will continue processing
normally as it waits for a response and it will send other events of
the same type to other listener processes in the same pool as
necessary.

After the event listener has processed the event serialization, in
order to notify supervisord about the result, it should send back a
result structure on its stdout.  A result structure is the word
"RESULT", followed by a space, followed by the result length, followed
by a line feed, followed by the result content.  For example,
``RESULT 2\nOK`` is the result "OK".  Conventionally, an event
listener will use either ``OK`` or ``FAIL`` as the result content.
These strings have special meaning to the default result handler.

If the default result handler receives ``OK`` as result content, it
will assume that the listener processed the event notification
successfully.  If it receives ``FAIL``, it will assume that the
listener has failed to process the event, and the event will be
rebuffered and sent again at a later time.  The event listener may
reject the event for any reason by returning a ``FAIL`` result.  This
does not indicate a problem with the event data or the event listener.
Once an ``OK`` or ``FAIL`` result is received by supervisord, the
event listener is placed into the ``ACKNOWLEDGED`` state.

Once the listener is in the ``ACKNOWLEDGED`` state, it may either exit
(and subsequently may be restarted by supervisor if its
``autorestart`` config parameter is ``true``), or it may continue
running.  If it continues to run, in order to be placed back into the
``READY`` state by supervisord, it must send a ``READY`` token
followed immediately by a line feed to its stdout.

Example Event Listener Implementation
+++++++++++++++++++++++++++++++++++++

A Python implementation of a "long-running" event listener which
accepts an event notification, prints the header and payload to its
stderr, and responds with an ``OK`` result, and then subsequently a
``READY`` is as follows.

.. code-block:: python

   import sys

   def write_stdout(s):
       # only eventlistener protocol messages may be sent to stdout
       sys.stdout.write(s)
       sys.stdout.flush()

   def write_stderr(s):
       sys.stderr.write(s)
       sys.stderr.flush()

   def main():
       while 1:
           # transition from ACKNOWLEDGED to READY
           write_stdout('READY\n')

           # read header line and print it to stderr
           line = sys.stdin.readline()
           write_stderr(line)

           # read event payload and print it to stderr
           headers = dict([ x.split(':') for x in line.split() ])
           data = sys.stdin.read(int(headers['len']))
           write_stderr(data)

           # transition from READY to ACKNOWLEDGED
           write_stdout('RESULT 2\nOK')

   if __name__ == '__main__':
       main()

Other sample event listeners are present within the :term:`superlance`
package, including one which can monitor supervisor subprocesses and
restart a process if it is using "too much" memory.

Event Listener Error Conditions
+++++++++++++++++++++++++++++++

If the event listener process dies while the event is being
transmitted to its stdin, or if it dies before sending an result
structure back to supervisord, the event is assumed to not be
processed and will be rebuffered by supervisord and sent again later.

If an event listener sends data to its stdout which supervisor does
not recognize as an appropriate response based on the state that the
event listener is in, the event listener will be placed into the
``UNKNOWN`` state, and no further event notifications will be sent to
it.  If an event was being processed by the listener during this time,
it will be rebuffered and sent again later.

Miscellaneous
+++++++++++++

Event listeners may use the Supervisor XML-RPC interface to call "back
in" to Supervisor.  As such, event listeners can impact the state of a
Supervisor subprocess as a result of receiving an event notification.
For example, you may want to generate an event every few minutes
related to process usage of Supervisor-controlled subprocesses, and if
any of those processes exceed some memory threshold, you would like
to restart it.  You would write a program that caused supervisor to
generate ``PROCESS_COMMUNICATION`` events every so often with memory
information in them, and an event listener to perform an action based
on processing the data it receives from these events.

.. _event_types:

Event Types
-----------

The event types are a controlled set, defined by Supervisor itself.
There is no way to add an event type without changing
:program:`supervisord` itself.  This is typically not a problem,
though, because metadata is attached to events that can be used by
event listeners as additional filter criterion, in conjunction with
its type.

Event types that may be subscribed to by event listeners are
predefined by supervisor and fall into several major categories,
including "process state change", "process communication", and
"supervisor state change" events. Below are tables describing
these event types.

In the below list, we indicate that some event types have a "body"
which is a a *token set*.  A token set consists of a set of charaters
with space-separated tokens.  Each token represents a key-value pair.
The key and value are separated by a colon.  For example:

.. code-block:: text

   processname:cat groupname:cat from_state:STOPPED

Token sets do not have a linefeed or carriage return character at
their end.

``EVENT`` Event Type
~~~~~~~~~~~~~~~~~~~~

The base event type.  This event type is abstract.  It will never be
sent directly.  Subscribing to this event type will cause a subscriber
to receive all event notifications emitted by Supervisor.

*Name*: ``EVENT``

*Subtype Of*: N/A

*Body Description*: N/A


``PROCESS_STATE`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This process type indicates a process has moved from one state to
another.  See :ref:`process_states` for a description of the states
that a process moves through during its lifetime.  This event type is
abstract, it will never be sent directly.  Subscribing to this event
type will cause a subscriber to receive event notifications of all the
event types that are subtypes of ``PROCESS_STATE``.

*Name*: ``PROCESS_STATE``

*Subtype Of*: ``EVENT``

Body Description
++++++++++++++++

All subtypes of ``PROCESS_STATE`` have a body which is a token set.
Additionally, each ``PROCESS_STATE`` subtype's token set has a default
set of key/value pairs: ``processname``, ``groupname``, and
``from_state``.  ``processname`` represents the process name which
supervisor knows this process as. ``groupname`` represents the name of
the supervisord group which this process is in.  ``from_state`` is the
name of the state from which this process is transitioning (the new
state is implied by the concrete event type).  Concrete subtypes may
include additional key/value pairs in the token set.

``PROCESS_STATE_STARTING`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Indicates a process has moved from a state to the STARTING state.

*Name*: ``PROCESS_STATE_STARTING``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This body is a token set.  It has the default set of key/value pairs
plus an additional ``tries`` key.  ``tries`` represents the number of
times this process has entered this state before transitioning to
RUNNING or FATAL (it will never be larger than the "startretries"
parameter of the process).  For example:

.. code-block:: text

   processname:cat groupname:cat from_state:STOPPED tries:0

``PROCESS_STATE_RUNNING`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has moved from the ``STARTING`` state to the
``RUNNING`` state.  This means that the process has successfully
started as far as Supervisor is concerned.

*Name*: ``PROCESS_STATE_RUNNING``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This body is a token set.  It has the default set of key/value pairs
plus an additional ``pid`` key.  ``pid`` represents the UNIX
process id of the process that was started.  For example:

.. code-block:: text

   processname:cat groupname:cat from_state:STARTING pid:2766

``PROCESS_STATE_BACKOFF`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has moved from the ``STARTING`` state to the
``BACKOFF`` state.  This means that the process did not successfully
enter the RUNNING state, and Supervisor is going to try to restart it
unless it has exceeded its "startretries" configuration limit.

*Name*: ``PROCESS_STATE_BACKOFF``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This body is a token set.  It has the default set of key/value pairs
plus an additional ``tries`` key.  ``tries`` represents the number of
times this process has entered this state before transitioning to
``RUNNING`` or ``FATAL`` (it will never be larger than the
"startretries" parameter of the process).  For example:

.. code-block:: text

   processname:cat groupname:cat from_state:STOPPED tries:0

``PROCESS_STATE_STOPPING`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has moved from either the ``RUNNING`` state or the
``STARTING`` state to the ``STOPPING`` state.

*Name*: ``PROCESS_STATE_STOPPING``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This body is a token set.  It has the default set of key/value pairs
plus an additional ``pid`` key.  ``pid`` represents the UNIX process
id of the process that was started.  For example:

.. code-block:: text

   processname:cat groupname:cat from_state:STARTING pid:2766

``PROCESS_STATE_EXITED`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has moved from the ``RUNNING`` state to the
``EXITED`` state.

*Name*: ``PROCESS_STATE_EXITED``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This body is a token set.  It has the default set of key/value pairs
plus two additional keys: ``pid`` and ``expected``.  ``pid``
represents the UNIX process id of the process that exited.
``expected`` represents whether the process exited with an expected
exit code or not.  It will be ``0`` if the exit code was unexpected,
or ``1`` if the exit code was expected. For example:

.. code-block:: text

   processname:cat groupname:cat from_state:RUNNING expected:0 pid:2766

``PROCESS_STATE_STOPPED`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has moved from the ``STOPPING`` state to the
``STOPPED`` state.

*Name*: ``PROCESS_STATE_STOPPED``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This body is a token set.  It has the default set of key/value pairs
plus an additional ``pid`` key.  ``pid`` represents the UNIX process
id of the process that was started.  For example:

.. code-block:: text

   processname:cat groupname:cat from_state:STOPPING pid:2766

``PROCESS_STATE_FATAL`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has moved from the ``BACKOFF`` state to the
``FATAL`` state.  This means that Supervisor tried ``startretries``
number of times unsuccessfully to start the process, and gave up
attempting to restart it.

*Name*: ``PROCESS_STATE_FATAL``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This event type is a token set with the default key/value pairs.  For
example:

.. code-block:: text

   processname:cat groupname:cat from_state:BACKOFF

``PROCESS_STATE_UNKNOWN`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has moved from any state to the ``UNKNOWN`` state
(indicates an error in :program:`supervisord`).  This state transition
will only happen if :program:`supervisord` itself has a programming
error.

*Name*: ``PROCESS_STATE_UNKNOWN``

*Subtype Of*: ``PROCESS_STATE``

Body Description
++++++++++++++++

This event type is a token set with the default key/value pairs.  For
example:

.. code-block:: text

   processname:cat groupname:cat from_state:BACKOFF

``REMOTE_COMMUNICATION`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An event type raised when the ``supervisor.sendRemoteCommEvent()``
method is called on Supervisor's RPC interface.  The ``type`` and
``data`` are arguments of the RPC method.

*Name*: ``REMOTE_COMMUNICATION``

*Subtype Of*: ``EVENT``

Body Description
++++++++++++++++

.. code-block:: text

   type:type
   data

``PROCESS_LOG`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~

An event type emitted when a process writes to stdout or stderr.  The
event will only be emitted if the file descriptor is not in capture
mode and if ``stdout_events_enabled`` or ``stderr_events_enabled``
config options are set to ``true``.  This event type is abstract, it
will never be sent directly.  Subscribing to this event type will
cause a subscriber to receive event notifications for all subtypes of
``PROCESS_LOG``.

*Name*: ``PROCESS_LOG``

*Subtype Of*: ``EVENT``

*Body Description*: N/A

``PROCESS_LOG_STDOUT`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has written to its stdout file descriptor.  The
event will only be emitted if the file descriptor is not in capture
mode and if the ``stdout_events_enabled`` config option is set to
``true``.

*Name*: ``PROCESS_LOG_STDOUT``

*Subtype Of*: ``PROCESS_LOG``

Body Description
++++++++++++++++

.. code-block:: text

   processname:name groupname:name pid:pid
   data

``PROCESS_LOG_STDERR`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has written to its stderr file descriptor.  The
event will only be emitted if the file descriptor is not in capture
mode and if the ``stderr_events_enabled`` config option is set to
``true``.

*Name*: ``PROCESS_LOG_STDERR``

*Subtype Of*: ``PROCESS_LOG``

Body Description
++++++++++++++++

.. code-block:: text

   processname:name groupname:name pid:pid
   data

``PROCESS_COMMUNICATION`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An event type raised when any process attempts to send information
between ``<!--XSUPERVISOR:BEGIN-->`` and ``<!--XSUPERVISOR:END-->``
tags in its output.  This event type is abstract, it will never be
sent directly.  Subscribing to this event type will cause a subscriber
to receive event notifications for all subtypes of
``PROCESS_COMMUNICATION``.

*Name*: ``PROCESS_COMMUNICATION``

*Subtype Of*: ``EVENT``

*Body Description*: N/A

``PROCESS_COMMUNICATION_STDOUT`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has sent a message to Supervisor on its stdout
file descriptor.

*Name*: ``PROCESS_COMMUNICATION_STDOUT``

*Subtype Of*: ``PROCESS_COMMUNICATION``

Body Description
++++++++++++++++

.. code-block:: text

   processname:name groupname:name pid:pid
   data

``PROCESS_COMMUNICATION_STDERR`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates a process has sent a message to Supervisor on its stderr
file descriptor.

*Name*: ``PROCESS_COMMUNICATION_STDERR``

*Subtype Of*: ``PROCESS_COMMUNICATION``

Body Description
++++++++++++++++

.. code-block:: text

   processname:name groupname:name pid:pid
   data

``SUPERVISOR_STATE_CHANGE`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An event type raised when the state of the :program:`supervisord`
process changes.  This type is abstract, it will never be sent
directly.  Subscribing to this event type will cause a subscriber to
receive event notifications of all the subtypes of
``SUPERVISOR_STATE_CHANGE``.

*Name*: ``SUPERVISOR_STATE_CHANGE``

*Subtype Of*: ``EVENT``

*Body Description*: N/A

``SUPERVISOR_STATE_CHANGE_RUNNING`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates that :program:`supervisord` has started.

*Name*: ``SUPERVISOR_STATE_CHANGE_RUNNING``

*Subtype Of*: ``SUPERVISOR_STATE_CHANGE``

*Body Description*: Empty string

``SUPERVISOR_STATE_CHANGE_STOPPING`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates that :program:`supervisord` is stopping.

*Name*: ``SUPERVISOR_STATE_CHANGE_STOPPING``

*Subtype Of*: ``SUPERVISOR_STATE_CHANGE``

*Body Description*: Empty string

``TICK`` Event Type
~~~~~~~~~~~~~~~~~~~

An event type that may be subscribed to for event listeners to receive
"wake-up" notifications every N seconds.  This event type is abstract,
it will never be sent directly.  Subscribing to this event type will
cause a subscriber to receive event notifications for all subtypes of
``TICK``.

Note that the only ``TICK`` events available are the ones listed below.
You cannot subscribe to an arbitrary ``TICK`` interval. If you need an
interval not provided below, you can subscribe to one of the shorter
intervals given below and keep track of the time between runs in your
event listener.

*Name*: ``TICK``

*Subtype Of*: ``EVENT``

*Body Description*: N/A

``TICK_5`` Event Type
~~~~~~~~~~~~~~~~~~~~~

An event type that may be subscribed to for event listeners to receive
"wake-up" notifications every 5 seconds.

*Name*: ``TICK_5``

*Subtype Of*: ``TICK``

Body Description
++++++++++++++++

This event type is a token set with a single key: "when", which
indicates the epoch time for which the tick was sent.

.. code-block:: text

   when:1201063880

``TICK_60`` Event Type
~~~~~~~~~~~~~~~~~~~~~~

An event type that may be subscribed to for event listeners to receive
"wake-up" notifications every 60 seconds.

*Name*: ``TICK_60``

*Subtype Of*: ``TICK``

Body Description
++++++++++++++++

This event type is a token set with a single key: "when", which
indicates the epoch time for which the tick was sent.

.. code-block:: text

   when:1201063880

``TICK_3600`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~

An event type that may be subscribed to for event listeners to receive
"wake-up" notifications every 3600 seconds (1 hour).

*Name*: ``TICK_3600``

*Subtype Of*: ``TICK``

Body Description
++++++++++++++++

This event type is a token set with a single key: "when", which
indicates the epoch time for which the tick was sent.

.. code-block:: text

   when:1201063880

``PROCESS_GROUP`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

An event type raised when a process group is added to or removed from
Supervisor.  This type is abstract, it will never be sent
directly.  Subscribing to this event type will cause a subscriber to
receive event notifications of all the subtypes of
``PROCESS_GROUP``.

*Name*: ``PROCESS_GROUP``

*Subtype Of*: ``EVENT``

*Body Description*: N/A

``PROCESS_GROUP_ADDED`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates that a process group has been added to Supervisor's configuration.

*Name*: ``PROCESS_GROUP_ADDED``

*Subtype Of*: ``PROCESS_GROUP``

*Body Description*: This body is a token set with just a groupname key/value.

.. code-block:: text

   groupname:cat

``PROCESS_GROUP_REMOVED`` Event Type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates that a process group has been removed from Supervisor's configuration.

*Name*: ``PROCESS_GROUP_REMOVED``

*Subtype Of*: ``PROCESS_GROUP``

*Body Description*: This body is a token set with just a groupname key/value.

.. code-block:: text

   groupname:cat

