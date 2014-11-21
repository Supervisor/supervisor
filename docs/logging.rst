Logging
=======

One of the main tasks that :program:`supervisord` performs is logging.
:program:`supervisord` logs an activity log detailing what it's doing
as it runs.  It also logs child process stdout and stderr output to
other files if configured to do so.

Activity Log
------------

The activity log is the place where :program:`supervisord` logs
messages about its own health, its subprocess' state changes, any
messages that result from events, and debug and informational
messages.  The path to the activity log is configured via the
``logfile`` parameter in the ``[supervisord]`` section of the
configuration file, defaulting to :file:`$CWD/supervisord.log`.
Sample activity log traffic is shown in the example below.  Some lines
have been broken to better fit the screen.

Sample Activity Log Output
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: text

   2007-09-08 14:43:22,886 DEBG 127.0.0.1:Medusa (V1.11) started at Sat Sep  8 14:43:22 2007
           Hostname: kingfish
           Port:9001
   2007-09-08 14:43:22,961 INFO RPC interface 'supervisor' initialized
   2007-09-08 14:43:22,961 CRIT Running without any HTTP authentication checking
   2007-09-08 14:43:22,962 INFO supervisord started with pid 27347
   2007-09-08 14:43:23,965 INFO spawned: 'listener_00' with pid 27349
   2007-09-08 14:43:23,970 INFO spawned: 'eventgen' with pid 27350
   2007-09-08 14:43:23,990 INFO spawned: 'grower' with pid 27351
   2007-09-08 14:43:24,059 DEBG 'listener_00' stderr output:
    /Users/chrism/projects/supervisor/supervisor2/dev-sandbox/bin/python:
    can't open file '/Users/chrism/projects/supervisor/supervisor2/src/supervisor/scripts/osx_eventgen_listener.py':
    [Errno 2] No such file or directory
   2007-09-08 14:43:24,060 DEBG fd 7 closed, stopped monitoring <PEventListenerDispatcher at 19910168 for
    <Subprocess at 18892960 with name listener_00 in state STARTING> (stdout)>
   2007-09-08 14:43:24,060 INFO exited: listener_00 (exit status 2; not expected)
   2007-09-08 14:43:24,061 DEBG received SIGCHLD indicating a child quit

The activity log "level" is configured in the config file via the
``loglevel`` parameter in the ``[supervisord]`` ini file section.
When ``loglevel`` is set, messages of the specified priority, plus
those with any higher priority are logged to the activity log.  For
example, if ``loglevel`` is ``error``, messages of ``error`` and
``critical`` priority will be logged.  However, if loglevel is
``warn``, messages of ``warn``, ``error``, and ``critical`` will be
logged.

.. _activity_log_levels:

Activity Log Levels
~~~~~~~~~~~~~~~~~~~

The below table describes the logging levels in more detail, ordered
in highest priority to lowest.  The "Config File Value" is the string
provided to the ``loglevel`` parameter in the ``[supervisord]``
section of configuration file and the "Output Code" is the code that
shows up in activity log output lines.

=================   ===========   ============================================
Config File Value   Output Code   Description
=================   ===========   ============================================
critical            CRIT          Messages that indicate a condition that
                                  requires immediate user attention, a
                                  supervisor state change, or an error in
                                  supervisor itself.
error               ERRO          Messages that indicate a potentially
                                  ignorable error condition (e.g. unable to
                                  clear a log directory).
warn                WARN          Messages that indicate an anomalous
                                  condition which isn't an error.
info                INFO          Normal informational output.  This is the
                                  default log level if none is explicitly
                                  configured.
debug               DEBG          Messages useful for users trying to debug
                                  process configuration and communications
                                  behavior (process output, listener state
                                  changes, event notifications).
trace               TRAC          Messages useful for developers trying to
                                  debug supervisor plugins, and information
                                  about HTTP and RPC requests and responses.
blather             BLAT          Messages useful for developers trying to
                                  debug supervisor itself.
=================   ===========   ============================================

Activity Log Rotation
~~~~~~~~~~~~~~~~~~~~~

The activity log is "rotated" by :program:`supervisord` based on the
combination of the ``logfile_maxbytes`` and the ``logfile_backups``
parameters in the ``[supervisord]`` section of the configuration file.
When the activity log reaches ``logfile_maxbytes`` bytes, the current
log file is moved to a backup file and a new activity log file is
created.  When this happens, if the number of existing backup files is
greater than or equal to ``logfile_backups``, the oldest backup file
is removed and the backup files are renamed accordingly.  If the file
being written to is named :file:`supervisord.log`, when it exceeds
``logfile_maxbytes``, it is closed and renamed to
:file:`supervisord.log.1`, and if files :file:`supervisord.log.1`,
:file:`supervisord.log.2` etc. exist, then they are renamed to
:file:`supervisord.log.2`, :file:`supervisord.log.3` etc.
respectively.  If ``logfile_maxbytes`` is 0, the logfile is never
rotated (and thus backups are never made).  If ``logfile_backups`` is
0, no backups will be kept.

Child Process Logs
------------------

The stdout of child processes spawned by supervisor, by default, is
captured for redisplay to users of :program:`supervisorctl` and other
clients.  If no specific logfile-related configuration is performed in
a ``[program:x]``, ``[fcgi-program:x]``, or ``[eventlistener:x]``
section in the configuration file, the following is true:

- :program:`supervisord` will capture the child process' stdout and
  stderr output into temporary files.  Each stream is captured to a
  separate file.  This is known as ``AUTO`` log mode.

- ``AUTO`` log files are named automatically and placed in the
  directory configured as ``childlogdir`` of the ``[supervisord]``
  section of the config file.

- The size of each ``AUTO`` log file is bounded by the
  ``{streamname}_logfile_maxbytes`` value of the program section
  (where {streamname} is "stdout" or "stderr").  When it reaches that
  number, it is rotated (like the activity log), based on the
  ``{streamname}_logfile_backups``.

The configuration keys that influence child process logging in
``[program:x]`` and ``[fcgi-program:x]`` sections are these:

``redirect_stderr``, ``stdout_logfile``, ``stdout_logfile_maxbytes``,
``stdout_logfile_backups``, ``stdout_capture_maxbytes``,
``stderr_logfile``, ``stderr_logfile_maxbytes``,
``stderr_logfile_backups`` and ``stderr_capture_maxbytes``.

One may set ``stdout_logfile`` or ``stderr_logfile`` to the
special string "syslog". In this case, logs will be routed to the
syslog service instead of being saved to files.

``[eventlistener:x]`` sections may not specify
``redirect_stderr``, ``stdout_capture_maxbytes``, or
``stderr_capture_maxbytes``, but otherwise they accept the same values.

The configuration keys that influence child process logging in the
``[supervisord]`` config file section are these:
``childlogdir``, and ``nocleanup``.

.. _capture_mode:

Capture Mode
~~~~~~~~~~~~

Capture mode is an advanced feature of Supervisor.  You needn't
understand capture mode unless you want to take actions based on data
parsed from subprocess output.

If a ``[program:x]`` section in the configuration file defines a
non-zero ``stdout_capture_maxbytes`` or ``stderr_capture_maxbytes``
parameter, each process represented by the program section may emit
special tokens on its stdout or stderr stream (respectively) which
will effectively cause supervisor to emit a ``PROCESS_COMMUNICATION``
event (see :ref:`events` for a description of events).

The process communications protocol relies on two tags, one which
commands supervisor to enter "capture mode" for the stream and one
which commands it to exit.  When a process stream enters "capture
mode", data sent to the stream will be sent to a separate buffer in
memory, the "capture buffer", which is allowed to contain a maximum of
``capture_maxbytes`` bytes.  During capture mode, when the buffer's
length exceeds ``capture_maxbytes`` bytes, the earliest data in the
buffer is discarded to make room for new data.  When a process stream
exits capture mode, a ``PROCESS_COMMUNICATION`` event subtype is
emitted by supervisor, which may be intercepted by event listeners.

The tag to begin "capture mode" in a process stream is
``<!--XSUPERVISOR:BEGIN-->``.  The tag to exit capture mode is
``<!--XSUPERVISOR:END-->``.  The data between these tags may be
arbitrary, and forms the payload of the ``PROCESS_COMMUNICATION``
event.  For example, if a program is set up with a
``stdout_capture_maxbytes`` of "1MB", and it emits the following on
its stdout stream:

.. code-block:: text

   <!--XSUPERVISOR:BEGIN-->Hello!<!--XSUPERVISOR:END-->

In this circumstance, :program:`supervisord` will emit a
``PROCESS_COMMUNICATIONS_STDOUT`` event with data in the payload of
"Hello!".

An example of a script (written in Python) which emits a process
communication event is in the :file:`scripts` directory of the
supervisor package, named :file:`sample_commevent.py`.

The output of processes specified as "event listeners"
(``[eventlistener:x]`` sections) is not processed this way.
Output from these processes cannot enter capture mode.
