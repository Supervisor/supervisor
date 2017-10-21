Configuration File
==================

The Supervisor configuration file is conventionally named
:file:`supervisord.conf`.  It is used by both :program:`supervisord`
and :program:`supervisorctl`.  If either application is started
without the ``-c`` option (the option which is used to tell the
application the configuration filename explicitly), the application
will look for a file named :file:`supervisord.conf` within the
following locations, in the specified order.  It will use the first
file it finds.

#. :file:`$CWD/supervisord.conf`

#. :file:`$CWD/etc/supervisord.conf`

#. :file:`/etc/supervisord.conf`

#. :file:`/etc/supervisor/supervisord.conf` (since Supervisor 3.3.0)

#. :file:`../etc/supervisord.conf` (Relative to the executable)

#. :file:`../supervisord.conf` (Relative to the executable)

.. note::

  Many versions of Supervisor packaged for Debian and Ubuntu included a patch
  that added ``/etc/supervisor/supervisord.conf`` to the search paths.  The
  first PyPI package of Supervisor to include it was Supervisor 3.3.0.

File Format
-----------

:file:`supervisord.conf` is a Windows-INI-style (Python ConfigParser)
file.  It has sections (each denoted by a ``[header]``) and key / value
pairs within the sections.  The sections and their allowable values
are described below.

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

Environment variables that are present in the environment at the time that
:program:`supervisord` is started can be used in the configuration file
using the Python string expression syntax ``%(ENV_X)s``:

.. code-block:: ini

    [program:example]
    command=/usr/bin/example --loglevel=%(ENV_LOGLEVEL)s

In the example above, the expression ``%(ENV_LOGLEVEL)s`` would be expanded
to the value of the environment variable ``LOGLEVEL``.

.. note::

    In Supervisor 3.2 and later, ``%(ENV_X)s`` expressions are supported in
    all options.  In prior versions, some options support them, but most
    do not.  See the documentation for each option below.


``[unix_http_server]`` Section Settings
---------------------------------------

The :file:`supervisord.conf` file contains a section named
``[unix_http_server]`` under which configuration parameters for an
HTTP server that listens on a UNIX domain socket should be inserted.
If the configuration file has no ``[unix_http_server]`` section, a
UNIX domain socket HTTP server will not be started.  The allowable
configuration values are as follows.

``[unix_http_server]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``file``

  A path to a UNIX domain socket (e.g. :file:`/tmp/supervisord.sock`)
  on which supervisor will listen for HTTP/XML-RPC requests.
  :program:`supervisorctl` uses XML-RPC to communicate with
  :program:`supervisord` over this port.  This option can include the
  value ``%(here)s``, which expands to the directory in which the
  :program:`supervisord` configuration file was found.

  *Default*:  None.

  *Required*:  No.

  *Introduced*: 3.0

``chmod``

  Change the UNIX permission mode bits of the UNIX domain socket to
  this value at startup.

  *Default*: ``0700``

  *Required*:  No.

  *Introduced*: 3.0

``chown``

  Change the user and group of the socket file to this value.  May be
  a UNIX username (e.g. ``chrism``) or a UNIX username and group
  separated by a colon (e.g. ``chrism:wheel``).

  *Default*:  Use the username and group of the user who starts supervisord.

  *Required*:  No.

  *Introduced*: 3.0

``username``

  The username required for authentication to this HTTP server.

  *Default*:  No username required.

  *Required*:  No.

  *Introduced*: 3.0

``password``

  The password required for authentication to this HTTP server.  This
  can be a cleartext password, or can be specified as a SHA-1 hash if
  prefixed by the string ``{SHA}``.  For example,
  ``{SHA}82ab876d1387bfafe46cc1c8a2ef074eae50cb1d`` is the SHA-stored
  version of the password "thepassword".

  Note that hashed password must be in hex format.

  *Default*:  No password required.

  *Required*:  No.

  *Introduced*: 3.0

``[unix_http_server]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [unix_http_server]
   file = /tmp/supervisor.sock
   chmod = 0777
   chown= nobody:nogroup
   username = user
   password = 123

``[inet_http_server]`` Section Settings
---------------------------------------

The :file:`supervisord.conf` file contains a section named
``[inet_http_server]`` under which configuration parameters for an
HTTP server that listens on a TCP (internet) socket should be
inserted.  If the configuration file has no ``[inet_http_server]``
section, an inet HTTP server will not be started.  The allowable
configuration values are as follows.

``[inet_http_server]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``port``

  A TCP host:port value or (e.g. ``127.0.0.1:9001``) on which
  supervisor will listen for HTTP/XML-RPC requests.
  :program:`supervisorctl` will use XML-RPC to communicate with
  :program:`supervisord` over this port.  To listen on all interfaces
  in the machine, use ``:9001`` or ``*:9001``.

  *Default*:  No default.

  *Required*:  Yes.

  *Introduced*: 3.0

``username``

  The username required for authentication to this HTTP server.

  *Default*:  No username required.

  *Required*:  No.

  *Introduced*: 3.0

``password``

  The password required for authentication to this HTTP server.  This
  can be a cleartext password, or can be specified as a SHA-1 hash if
  prefixed by the string ``{SHA}``.  For example,
  ``{SHA}82ab876d1387bfafe46cc1c8a2ef074eae50cb1d`` is the SHA-stored
  version of the password "thepassword".

  Note that hashed password must be in hex format.

  *Default*:  No password required.

  *Required*:  No.

  *Introduced*: 3.0

``[inet_http_server]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [inet_http_server]
   port = 127.0.0.1:9001
   username = user
   password = 123

``[supervisord]`` Section Settings
----------------------------------

The :file:`supervisord.conf` file contains a section named
``[supervisord]`` in which global settings related to the
:program:`supervisord` process should be inserted.  These are as
follows.

``[supervisord]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``logfile``

  The path to the activity log of the supervisord process.  This
  option can include the value ``%(here)s``, which expands to the
  directory in which the supervisord configuration file was found.

  *Default*:  :file:`$CWD/supervisord.log`

  *Required*:  No.

  *Introduced*: 3.0

``logfile_maxbytes``

  The maximum number of bytes that may be consumed by the activity log
  file before it is rotated (suffix multipliers like "KB", "MB", and
  "GB" can be used in the value).  Set this value to 0 to indicate an
  unlimited log size.

  *Default*:  50MB

  *Required*:  No.

  *Introduced*: 3.0

``logfile_backups``

  The number of backups to keep around resulting from activity log
  file rotation.  If set to 0, no backups will be kept.

  *Default*:  10

  *Required*:  No.

  *Introduced*: 3.0

``loglevel``

  The logging level, dictating what is written to the supervisord
  activity log.  One of ``critical``, ``error``, ``warn``, ``info``,
  ``debug``, ``trace``, or ``blather``.  Note that at log level
  ``debug``, the supervisord log file will record the stderr/stdout
  output of its child processes and extended info info about process
  state changes, which is useful for debugging a process which isn't
  starting properly.  See also: :ref:`activity_log_levels`.

  *Default*:  info

  *Required*:  No.

  *Introduced*: 3.0

``pidfile``

  The location in which supervisord keeps its pid file.  This option
  can include the value ``%(here)s``, which expands to the directory
  in which the supervisord configuration file was found.

  *Default*:  :file:`$CWD/supervisord.pid`

  *Required*:  No.

  *Introduced*: 3.0

``umask``

  The :term:`umask` of the supervisord process.

  *Default*:  ``022``

  *Required*:  No.

  *Introduced*: 3.0

``nodaemon``

  If true, supervisord will start in the foreground instead of
  daemonizing.

  *Default*:  false

  *Required*:  No.

  *Introduced*: 3.0

``minfds``

  The minimum number of file descriptors that must be available before
  supervisord will start successfully.  A call to setrlimit will be made
  to attempt to raise the soft and hard limits of the supervisord process to
  satisfy ``minfds``.  The hard limit may only be raised if supervisord
  is run as root.  supervisord uses file descriptors liberally, and will
  enter a failure mode when one cannot be obtained from the OS, so it's
  useful to be able to specify a minimum value to ensure it doesn't run out
  of them during execution.  These limits will be inherited by the managed
  subprocesses.  This option is particularly useful on Solaris,
  which has a low per-process fd limit by default.

  *Default*:  1024

  *Required*:  No.

  *Introduced*: 3.0

``minprocs``

  The minimum number of process descriptors that must be available
  before supervisord will start successfully.  A call to setrlimit will be
  made to attempt to raise the soft and hard limits of the supervisord process
  to satisfy ``minprocs``.  The hard limit may only be raised if supervisord
  is run as root.  supervisord will enter a failure mode when the OS runs out
  of process descriptors, so it's useful to ensure that enough process
  descriptors are available upon :program:`supervisord` startup.

  *Default*:  200

  *Required*:  No.

  *Introduced*: 3.0

``nocleanup``

  Prevent supervisord from clearing any existing ``AUTO``
  child log files at startup time.  Useful for debugging.

  *Default*:  false

  *Required*:  No.

  *Introduced*: 3.0

``childlogdir``

  The directory used for ``AUTO`` child log files.  This option can
  include the value ``%(here)s``, which expands to the directory in
  which the :program:`supervisord` configuration file was found.

  *Default*: value of Python's :func:`tempfile.get_tempdir`

  *Required*:  No.

  *Introduced*: 3.0

``user``

  Instruct :program:`supervisord` to switch users to this UNIX user
  account before doing any meaningful processing.  The user can only
  be switched if :program:`supervisord` is started as the root user.
  If :program:`supervisord` can't switch users, it will still continue
  but will write a log message at the ``critical`` level saying that it
  can't drop privileges.

  *Default*: do not switch users

  *Required*:  No.

  *Introduced*: 3.0

``directory``

  When :program:`supervisord` daemonizes, switch to this directory.
  This option can include the value ``%(here)s``, which expands to the
  directory in which the :program:`supervisord` configuration file was
  found.

  *Default*: do not cd

  *Required*:  No.

  *Introduced*: 3.0

``strip_ansi``

  Strip all ANSI escape sequences from child log files.

  *Default*: false

  *Required*:  No.

  *Introduced*: 3.0

``environment``

  A list of key/value pairs in the form ``KEY="val",KEY2="val2"`` that
  will be placed in the :program:`supervisord` process' environment
  (and as a result in all of its child process' environments).  This
  option can include the value ``%(here)s``, which expands to the
  directory in which the supervisord configuration file was found.
  Values containing non-alphanumeric characters should be quoted
  (e.g. ``KEY="val:123",KEY2="val,456"``).  Otherwise, quoting the
  values is optional but recommended.  To escape percent characters,
  simply use two. (e.g. ``URI="/first%%20name"``) **Note** that
  subprocesses will inherit the environment variables of the shell
  used to start :program:`supervisord` except for the ones overridden
  here and within the program's ``environment`` option.  See
  :ref:`subprocess_environment`.

  *Default*: no values

  *Required*:  No.

  *Introduced*: 3.0

``identifier``

  The identifier string for this supervisor process, used by the RPC
  interface.

  *Default*: supervisor

  *Required*:  No.

  *Introduced*: 3.0

``[supervisord]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [supervisord]
   logfile = /tmp/supervisord.log
   logfile_maxbytes = 50MB
   logfile_backups=10
   loglevel = info
   pidfile = /tmp/supervisord.pid
   nodaemon = false
   minfds = 1024
   minprocs = 200
   umask = 022
   user = chrism
   identifier = supervisor
   directory = /tmp
   nocleanup = true
   childlogdir = /tmp
   strip_ansi = false
   environment = KEY1="value1",KEY2="value2"

``[supervisorctl]`` Section Settings
------------------------------------

  The configuration file may contain settings for the
  :program:`supervisorctl` interactive shell program.  These options
  are listed below.

``[supervisorctl]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``serverurl``

  The URL that should be used to access the supervisord server,
  e.g. ``http://localhost:9001``.  For UNIX domain sockets, use
  ``unix:///absolute/path/to/file.sock``.

  *Default*: ``http://localhost:9001``

  *Required*:  No.

  *Introduced*: 3.0

``username``

  The username to pass to the supervisord server for use in
  authentication.  This should be same as ``username`` from the
  supervisord server configuration for the port or UNIX domain socket
  you're attempting to access.

  *Default*: No username

  *Required*:  No.

  *Introduced*: 3.0

``password``

  The password to pass to the supervisord server for use in
  authentication. This should be the cleartext version of ``password``
  from the supervisord server configuration for the port or UNIX
  domain socket you're attempting to access.  This value cannot be
  passed as a SHA hash.  Unlike other passwords specified in this
  file, it must be provided in cleartext.

  *Default*: No password

  *Required*:  No.

  *Introduced*: 3.0

``prompt``

  String used as supervisorctl prompt.

  *Default*: ``supervisor``

  *Required*:  No.

  *Introduced*: 3.0

``history_file``

  A path to use as the ``readline`` persistent history file.  If you
  enable this feature by choosing a path, your supervisorctl commands
  will be kept in the file, and you can use readline (e.g. arrow-up)
  to invoke commands you performed in your last supervisorctl session.

  *Default*: No file

  *Required*:  No.

  *Introduced*: 3.0a5

``[supervisorctl]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [supervisorctl]
   serverurl = unix:///tmp/supervisor.sock
   username = chris
   password = 123
   prompt = mysupervisor

.. _programx_section:

``[program:x]`` Section Settings
--------------------------------

The configuration file must contain one or more ``program`` sections
in order for supervisord to know which programs it should start and
control.  The header value is composite value.  It is the word
"program", followed directly by a colon, then the program name.  A
header value of ``[program:foo]`` describes a program with the name of
"foo".  The name is used within client applications that control the
processes that are created as a result of this configuration.  It is
an error to create a ``program`` section that does not have a name.
The name must not include a colon character or a bracket character.
The value of the name is used as the value for the
``%(program_name)s`` string expression expansion within other values
where specified.

.. note::

   A ``[program:x]`` section actually represents a "homogeneous
   process group" to supervisor (as of 3.0).  The members of the group
   are defined by the combination of the ``numprocs`` and
   ``process_name`` parameters in the configuration.  By default, if
   numprocs and process_name are left unchanged from their defaults,
   the group represented by ``[program:x]`` will be named ``x`` and
   will have a single process named ``x`` in it.  This provides a
   modicum of backwards compatibility with older supervisor releases,
   which did not treat program sections as homogeneous process group
   definitions.

   But for instance, if you have a ``[program:foo]`` section with a
   ``numprocs`` of 3 and a ``process_name`` expression of
   ``%(program_name)s_%(process_num)02d``, the "foo" group will
   contain three processes, named ``foo_00``, ``foo_01``, and
   ``foo_02``.  This makes it possible to start a number of very
   similar processes using a single ``[program:x]`` section.  All
   logfile names, all environment strings, and the command of programs
   can also contain similar Python string expressions, to pass
   slightly different parameters to each process.

``[program:x]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``command``

  The command that will be run when this program is started.  The
  command can be either absolute (e.g. ``/path/to/programname``) or
  relative (e.g. ``programname``).  If it is relative, the
  supervisord's environment ``$PATH`` will be searched for the
  executable.  Programs can accept arguments, e.g. ``/path/to/program
  foo bar``.  The command line can use double quotes to group
  arguments with spaces in them to pass to the program,
  e.g. ``/path/to/program/name -p "foo bar"``.  Note that the value of
  ``command`` may include Python string expressions,
  e.g. ``/path/to/programname --port=80%(process_num)02d`` might
  expand to ``/path/to/programname --port=8000`` at runtime.  String
  expressions are evaluated against a dictionary containing the keys
  ``group_name``, ``host_node_name``, ``process_num``, ``program_name``,
  ``here`` (the directory of the supervisord config file), and all
  supervisord's environment variables prefixed with ``ENV_``.  Controlled
  programs should themselves not be daemons, as supervisord assumes it is
  responsible for daemonizing its subprocesses (see
  :ref:`nondaemonizing_of_subprocesses`).

  .. note::

    The command will be truncated if it looks like a config file comment,
    e.g. ``command=bash -c 'foo ; bar'`` will be truncated to
    ``command=bash -c 'foo``.  Quoting will not prevent this behavior,
    since the configuration file reader does not parse the command like
    a shell would.

  *Default*: No default.

  *Required*:  Yes.

  *Introduced*: 3.0

``process_name``

  A Python string expression that is used to compose the supervisor
  process name for this process.  You usually don't need to worry
  about setting this unless you change ``numprocs``.  The string
  expression is evaluated against a dictionary that includes
  ``group_name``, ``host_node_name``, ``process_num``, ``program_name``,
  and ``here`` (the directory of the supervisord config file).

  *Default*: ``%(program_name)s``

  *Required*:  No.

  *Introduced*: 3.0

``numprocs``

  Supervisor will start as many instances of this program as named by
  numprocs.  Note that if numprocs > 1, the ``process_name``
  expression must include ``%(process_num)s`` (or any other
  valid Python string expression that includes ``process_num``) within
  it.

  *Default*: 1

  *Required*:  No.

  *Introduced*: 3.0

``numprocs_start``

  An integer offset that is used to compute the number at which
  ``numprocs`` starts.

  *Default*: 0

  *Required*:  No.

  *Introduced*: 3.0

``priority``

  The relative priority of the program in the start and shutdown
  ordering.  Lower priorities indicate programs that start first and
  shut down last at startup and when aggregate commands are used in
  various clients (e.g. "start all"/"stop all").  Higher priorities
  indicate programs that start last and shut down first.

  *Default*: 999

  *Required*:  No.

  *Introduced*: 3.0

``autostart``

  If true, this program will start automatically when supervisord is
  started.

  *Default*: true

  *Required*:  No.

  *Introduced*: 3.0

``startsecs``

  The total number of seconds which the program needs to stay running
  after a startup to consider the start successful (moving the process
  from the ``STARTING`` state to the ``RUNNING`` state).  Set to ``0``
  to indicate that the program needn't stay running for any particular
  amount of time.

  .. note::

      Even if a process exits with an "expected" exit code (see
      ``exitcodes``), the start will still be considered a failure
      if the process exits quicker than ``startsecs``.

  *Default*: 1

  *Required*:  No.

  *Introduced*: 3.0

``startretries``

  The number of serial failure attempts that :program:`supervisord`
  will allow when attempting to start the program before giving up and
  putting the process into an ``FATAL`` state.  See
  :ref:`process_states` for explanation of the ``FATAL`` state.

  *Default*: 3

  *Required*:  No.

  *Introduced*: 3.0

``autorestart``

  Specifies if :program:`supervisord` should automatically restart a
  process if it exits when it is in the ``RUNNING`` state.  May be
  one of ``false``, ``unexpected``, or ``true``.  If ``false``, the
  process will not be autorestarted.  If ``unexpected``, the process
  will be restarted when the program exits with an exit code that is
  not one of the exit codes associated with this process' configuration
  (see ``exitcodes``).  If ``true``, the process will be unconditionally
  restarted when it exits, without regard to its exit code.

  .. note::

      ``autorestart`` controls whether :program:`supervisord` will
      autorestart a program if it exits after it has successfully started
      up (the process is in the ``RUNNING`` state).

      :program:`supervisord` has a different restart mechanism for when the
      process is starting up (the process is in the ``STARTING`` state).
      Retries during process startup are controlled by ``startsecs``
      and ``startretries``.

  *Default*: unexpected

  *Required*:  No.

  *Introduced*: 3.0

``exitcodes``

  The list of "expected" exit codes for this program used with ``autorestart``.
  If the ``autorestart`` parameter is set to ``unexpected``, and the process
  exits in any other way than as a result of a supervisor stop
  request, :program:`supervisord` will restart the process if it exits
  with an exit code that is not defined in this list.

  *Default*: 0,2

  *Required*:  No.

  *Introduced*: 3.0

``stopsignal``

  The signal used to kill the program when a stop is requested.  This
  can be any of TERM, HUP, INT, QUIT, KILL, USR1, or USR2.

  *Default*: TERM

  *Required*:  No.

  *Introduced*: 3.0

``stopwaitsecs``

  The number of seconds to wait for the OS to return a SIGCHLD to
  :program:`supervisord` after the program has been sent a stopsignal.
  If this number of seconds elapses before :program:`supervisord`
  receives a SIGCHLD from the process, :program:`supervisord` will
  attempt to kill it with a final SIGKILL.

  *Default*: 10

  *Required*:  No.

  *Introduced*: 3.0

``stopasgroup``

  If true, the flag causes supervisor to send the stop signal to the
  whole process group and implies ``killasgroup`` is true.  This is useful
  for programs, such as Flask in debug mode, that do not propagate
  stop signals to their children, leaving them orphaned.

  *Default*: false

  *Required*:  No.

  *Introduced*: 3.0b1

``killasgroup``

  If true, when resorting to send SIGKILL to the program to terminate
  it send it to its whole process group instead, taking care of its
  children as well, useful e.g with Python programs using
  :mod:`multiprocessing`.

  *Default*: false

  *Required*:  No.

  *Introduced*: 3.0a11

``user``

  Instruct :program:`supervisord` to use this UNIX user account as the
  account which runs the program.  The user can only be switched if
  :program:`supervisord` is run as the root user.  If :program:`supervisord`
  can't switch to the specified user, the program will not be started.

  .. note::

      The user will be changed using ``setuid`` only.  This does not start
      a login shell and does not change environment variables like
      ``USER`` or ``HOME``.  See :ref:`subprocess_environment` for details.

  *Default*: Do not switch users

  *Required*:  No.

  *Introduced*: 3.0

``redirect_stderr``

  If true, cause the process' stderr output to be sent back to
  :program:`supervisord` on its stdout file descriptor (in UNIX shell
  terms, this is the equivalent of executing ``/the/program 2>&1``).

  .. note::

     Do not set ``redirect_stderr=true`` in an ``[eventlistener:x]`` section.
     Eventlisteners use ``stdout`` and ``stdin`` to communicate with
     ``supervisord``.  If ``stderr`` is redirected, output from
     ``stderr`` will interfere with the eventlistener protocol.

  *Default*: false

  *Required*:  No.

  *Introduced*: 3.0, replaces 2.0's ``log_stdout`` and ``log_stderr``

``stdout_logfile``

  Put process stdout output in this file (and if redirect_stderr is
  true, also place stderr output in this file).  If ``stdout_logfile``
  is unset or set to ``AUTO``, supervisor will automatically choose a
  file location.  If this is set to ``NONE``, supervisord will create
  no log file.  ``AUTO`` log files and their backups will be deleted
  when :program:`supervisord` restarts.  The ``stdout_logfile`` value
  can contain Python string expressions that will evaluated against a
  dictionary that contains the keys ``group_name``, ``host_node_name``,
  ``process_num``, ``program_name``, and ``here`` (the directory of the
  supervisord config file).

  .. note::

     It is not possible for two processes to share a single log file
     (``stdout_logfile``) when rotation (``stdout_logfile_maxbytes``)
     is enabled.  This will result in the file being corrupted.

  *Default*: ``AUTO``

  *Required*:  No.

  *Introduced*: 3.0, replaces 2.0's ``logfile``

``stdout_logfile_maxbytes``

  The maximum number of bytes that may be consumed by
  ``stdout_logfile`` before it is rotated (suffix multipliers like
  "KB", "MB", and "GB" can be used in the value).  Set this value to 0
  to indicate an unlimited log size.

  *Default*: 50MB

  *Required*:  No.

  *Introduced*: 3.0, replaces 2.0's ``logfile_maxbytes``

``stdout_logfile_backups``

  The number of ``stdout_logfile`` backups to keep around resulting
  from process stdout log file rotation.  If set to 0, no backups
  will be kept.

  *Default*: 10

  *Required*:  No.

  *Introduced*: 3.0, replaces 2.0's ``logfile_backups``

``stdout_capture_maxbytes``

  Max number of bytes written to capture FIFO when process is in
  "stdout capture mode" (see :ref:`capture_mode`).  Should be an
  integer (suffix multipliers like "KB", "MB" and "GB" can used in the
  value).  If this value is 0, process capture mode will be off.

  *Default*: 0

  *Required*:  No.

  *Introduced*: 3.0

``stdout_events_enabled``

  If true, PROCESS_LOG_STDOUT events will be emitted when the process
  writes to its stdout file descriptor.  The events will only be
  emitted if the file descriptor is not in capture mode at the time
  the data is received (see :ref:`capture_mode`).

  *Default*: 0

  *Required*:  No.

  *Introduced*: 3.0a7

``stderr_logfile``

  Put process stderr output in this file unless ``redirect_stderr`` is
  true.  Accepts the same value types as ``stdout_logfile`` and may
  contain the same Python string expressions.

  .. note::

     It is not possible for two processes to share a single log file
     (``stderr_logfile``) when rotation (``stderr_logfile_maxbytes``)
     is enabled.  This will result in the file being corrupted.

  *Default*: ``AUTO``

  *Required*:  No.

  *Introduced*: 3.0

``stderr_logfile_maxbytes``

  The maximum number of bytes before logfile rotation for
  ``stderr_logfile``.  Accepts the same value types as
  ``stdout_logfile_maxbytes``.

  *Default*: 50MB

  *Required*:  No.

  *Introduced*: 3.0

``stderr_logfile_backups``

  The number of backups to keep around resulting from process stderr
  log file rotation.  If set to 0, no backups will be kept.

  *Default*: 10

  *Required*:  No.

  *Introduced*: 3.0

``stderr_capture_maxbytes``

  Max number of bytes written to capture FIFO when process is in
  "stderr capture mode" (see :ref:`capture_mode`).  Should be an
  integer (suffix multipliers like "KB", "MB" and "GB" can used in the
  value).  If this value is 0, process capture mode will be off.

  *Default*: 0

  *Required*:  No.

  *Introduced*: 3.0

``stderr_events_enabled``

  If true, PROCESS_LOG_STDERR events will be emitted when the process
  writes to its stderr file descriptor.  The events will only be
  emitted if the file descriptor is not in capture mode at the time
  the data is received (see :ref:`capture_mode`).

  *Default*: false

  *Required*:  No.

  *Introduced*: 3.0a7

``environment``

  A list of key/value pairs in the form ``KEY="val",KEY2="val2"`` that
  will be placed in the child process' environment.  The environment
  string may contain Python string expressions that will be evaluated
  against a dictionary containing ``group_name``, ``host_node_name``,
  ``process_num``, ``program_name``, and ``here`` (the directory of the
  supervisord config file).  Values containing non-alphanumeric characters
  should be quoted (e.g. ``KEY="val:123",KEY2="val,456"``).  Otherwise,
  quoting the values is optional but recommended.  **Note** that the
  subprocess will inherit the environment variables of the shell used to
  start "supervisord" except for the ones overridden here.  See
  :ref:`subprocess_environment`.

  *Default*: No extra environment

  *Required*:  No.

  *Introduced*: 3.0

``directory``

  A file path representing a directory to which :program:`supervisord`
  should temporarily chdir before exec'ing the child.

  *Default*: No chdir (inherit supervisor's)

  *Required*:  No.

  *Introduced*: 3.0

``umask``

  An octal number (e.g. 002, 022) representing the umask of the
  process.

  *Default*: No special umask (inherit supervisor's)

  *Required*:  No.

  *Introduced*: 3.0

``serverurl``

  The URL passed in the environment to the subprocess process as
  ``SUPERVISOR_SERVER_URL`` (see :mod:`supervisor.childutils`) to
  allow the subprocess to easily communicate with the internal HTTP
  server.  If provided, it should have the same syntax and structure
  as the ``[supervisorctl]`` section option of the same name.  If this
  is set to AUTO, or is unset, supervisor will automatically construct
  a server URL, giving preference to a server that listens on UNIX
  domain sockets over one that listens on an internet socket.

  *Default*: AUTO

  *Required*:  No.

  *Introduced*: 3.0

``[program:x]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [program:cat]
   command=/bin/cat
   process_name=%(program_name)s
   numprocs=1
   directory=/tmp
   umask=022
   priority=999
   autostart=true
   autorestart=unexpected
   startsecs=10
   startretries=3
   exitcodes=0,2
   stopsignal=TERM
   stopwaitsecs=10
   stopasgroup=false
   killasgroup=false
   user=chrism
   redirect_stderr=false
   stdout_logfile=/a/path
   stdout_logfile_maxbytes=1MB
   stdout_logfile_backups=10
   stdout_capture_maxbytes=1MB
   stdout_events_enabled=false
   stderr_logfile=/a/path
   stderr_logfile_maxbytes=1MB
   stderr_logfile_backups=10
   stderr_capture_maxbytes=1MB
   stderr_events_enabled=false
   environment=A="1",B="2"
   serverurl=AUTO

``[include]`` Section Settings
------------------------------

The :file:`supervisord.conf` file may contain a section named
``[include]``.  If the configuration file contains an ``[include]``
section, it must contain a single key named "files".  The values in
this key specify other configuration files to be included within the
configuration.

.. note::

    The ``[include]`` section is processed only by ``supervisord``.  It is
    ignored by ``supervisorctl``.


``[include]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``files``

  A space-separated sequence of file globs.  Each file glob may be
  absolute or relative.  If the file glob is relative, it is
  considered relative to the location of the configuration file which
  includes it.  A "glob" is a file pattern which matches a specified
  pattern according to the rules used by the Unix shell. No tilde
  expansion is done, but ``*``, ``?``, and character ranges expressed
  with ``[]`` will be correctly matched.  The string expression is
  evaluated against a dictionary that includes ``host_node_name``
  and ``here`` (the directory of the supervisord config file).  Recursive
  includes from included files are not supported.

  *Default*: No default (required)

  *Required*:  Yes.

  *Introduced*: 3.0

  *Changed*: 3.3.0.  Added support for the ``host_node_name`` expansion.

``[include]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [include]
   files = /an/absolute/filename.conf /an/absolute/*.conf foo.conf config??.conf

``[group:x]`` Section Settings
------------------------------

It is often useful to group "homogeneous" process groups (aka
"programs") together into a "heterogeneous" process group so they can
be controlled as a unit from Supervisor's various controller
interfaces.

To place programs into a group so you can treat them as a unit, define
a ``[group:x]`` section in your configuration file.  The group header
value is a composite.  It is the word "group", followed directly by a
colon, then the group name.  A header value of ``[group:foo]``
describes a group with the name of "foo".  The name is used within
client applications that control the processes that are created as a
result of this configuration.  It is an error to create a ``group``
section that does not have a name.  The name must not include a colon
character or a bracket character.

For a ``[group:x]``, there must be one or more ``[program:x]``
sections elsewhere in your configuration file, and the group must
refer to them by name in the ``programs`` value.

If "homogeneous" process groups (represented by program sections) are
placed into a "heterogeneous" group via ``[group:x]`` section's
``programs`` line, the homogeneous groups that are implied by the
program section will not exist at runtime in supervisor.  Instead, all
processes belonging to each of the homogeneous groups will be placed
into the heterogeneous group.  For example, given the following group
configuration:

.. code-block:: ini

   [group:foo]
   programs=bar,baz
   priority=999

Given the above, at supervisord startup, the ``bar`` and ``baz``
homogeneous groups will not exist, and the processes that would have
been under them will now be moved into the ``foo`` group.

``[group:x]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``programs``

  A comma-separated list of program names.  The programs which are
  listed become members of the group.

  *Default*: No default (required)

  *Required*:  Yes.

  *Introduced*: 3.0

``priority``

  A priority number analogous to a ``[program:x]`` priority value
  assigned to the group.

  *Default*: 999

  *Required*:  No.

  *Introduced*: 3.0

``[group:x]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [group:foo]
   programs=bar,baz
   priority=999


``[fcgi-program:x]`` Section Settings
-------------------------------------

Supervisor can manage groups of `FastCGI <http://www.fastcgi.com>`_
processes that all listen on the same socket.  Until now, deployment
flexibility for FastCGI was limited.  To get full process management,
you could use mod_fastcgi under Apache but then you were stuck with
Apache's inefficient concurrency model of one process or thread per
connection.  In addition to requiring more CPU and memory resources,
the process/thread per connection model can be quickly saturated by a
slow resource, preventing other resources from being served.  In order
to take advantage of newer event-driven web servers such as lighttpd
or nginx which don't include a built-in process manager, you had to
use scripts like cgi-fcgi or spawn-fcgi.  These can be used in
conjunction with a process manager such as supervisord or daemontools
but require each FastCGI child process to bind to its own socket.
The disadvantages of this are: unnecessarily complicated web server
configuration, ungraceful restarts, and reduced fault tolerance.  With
fewer sockets to configure, web server configurations are much smaller
if groups of FastCGI processes can share sockets.  Shared sockets
allow for graceful restarts because the socket remains bound by the
parent process while any of the child processes are being restarted.
Finally, shared sockets are more fault tolerant because if a given
process fails, other processes can continue to serve inbound
connections.

With integrated FastCGI spawning support, Supervisor gives you the
best of both worlds.  You get full-featured process management with
groups of FastCGI processes sharing sockets without being tied to a
particular web server.  It's a clean separation of concerns, allowing
the web server and the process manager to each do what they do best.

.. note::

   The socket manager in Supervisor was originally developed to support
   FastCGI processes but it is not limited to FastCGI.  Other protocols may
   be used as well with no special configuration.  Any program that can
   access an open socket from a file descriptor (e.g. with
   `socket.fromfd <http://docs.python.org/library/socket.html#socket.fromfd>`_
   in Python) can use the socket manager.  Supervisor will automatically
   create the socket, bind, and listen before forking the first child in a
   group.  The socket will be passed to each child on file descriptor
   number ``0`` (zero).  When the last child in the group exits,
   Supervisor will close the socket.

All the options available to ``[program:x]`` sections are
also respected by ``fcgi-program`` sections.

``[fcgi-program:x]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``[fcgi-program:x]`` sections have a single key which ``[program:x]``
sections do not have.

``socket``

  The FastCGI socket for this program, either TCP or UNIX domain
  socket. For TCP sockets, use this format: ``tcp://localhost:9002``.
  For UNIX domain sockets, use ``unix:///absolute/path/to/file.sock``.
  String expressions are evaluated against a dictionary containing the
  keys "program_name" and "here" (the directory of the supervisord
  config file).

  *Default*: No default.

  *Required*:  Yes.

  *Introduced*: 3.0

``socket_owner``

  For UNIX domain sockets, this parameter can be used to specify the user
  and group for the FastCGI socket. May be a UNIX username (e.g. chrism)
  or a UNIX username and group separated by a colon (e.g. chrism:wheel).

  *Default*: Uses the user and group set for the fcgi-program

  *Required*:  No.

  *Introduced*: 3.0

``socket_mode``

  For UNIX domain sockets, this parameter can be used to specify the
  permission mode.

  *Default*: 0700

  *Required*:  No.

  *Introduced*: 3.0

Consult :ref:`programx_section` for other allowable keys, delta the
above constraints and additions.

``[fcgi-program:x]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [fcgi-program:fcgiprogramname]
   command=/usr/bin/example.fcgi
   socket=unix:///var/run/supervisor/%(program_name)s.sock
   socket_owner=chrism
   socket_mode=0700
   process_name=%(program_name)s_%(process_num)02d
   numprocs=5
   directory=/tmp
   umask=022
   priority=999
   autostart=true
   autorestart=unexpected
   startsecs=1
   startretries=3
   exitcodes=0,2
   stopsignal=QUIT
   stopasgroup=false
   killasgroup=false
   stopwaitsecs=10
   user=chrism
   redirect_stderr=true
   stdout_logfile=/a/path
   stdout_logfile_maxbytes=1MB
   stdout_logfile_backups=10
   stdout_events_enabled=false
   stderr_logfile=/a/path
   stderr_logfile_maxbytes=1MB
   stderr_logfile_backups=10
   stderr_events_enabled=false
   environment=A="1",B="2"
   serverurl=AUTO

``[eventlistener:x]`` Section Settings
--------------------------------------

Supervisor allows specialized homogeneous process groups ("event
listener pools") to be defined within the configuration file.  These
pools contain processes that are meant to receive and respond to event
notifications from supervisor's event system.  See :ref:`events` for
an explanation of how events work and how to implement programs that
can be declared as event listeners.

Note that all the options available to ``[program:x]`` sections are
respected by eventlistener sections *except* for ``stdout_capture_maxbytes``.
Eventlisteners cannot emit process communication events on ``stdout``,
but can emit on ``stderr`` (see :ref:`capture_mode`).

``[eventlistener:x]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``[eventlistener:x]`` sections have a few keys which ``[program:x]``
sections do not have.

``buffer_size``

  The event listener pool's event queue buffer size.  When a listener
  pool's event buffer is overflowed (as can happen when an event
  listener pool cannot keep up with all of the events sent to it), the
  oldest event in the buffer is discarded.

``events``

  A comma-separated list of event type names that this listener is
  "interested" in receiving notifications for (see
  :ref:`event_types` for a list of valid event type names).

``result_handler``

  A `pkg_resources entry point string
  <http://peak.telecommunity.com/DevCenter/PkgResources>`_ that
  resolves to a Python callable.  The default value is
  ``supervisor.dispatchers:default_handler``.  Specifying an alternate
  result handler is a very uncommon thing to need to do, and as a
  result, how to create one is not documented.

Consult :ref:`programx_section` for other allowable keys, delta the
above constraints and additions.

``[eventlistener:x]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [eventlistener:theeventlistenername]
   command=/bin/eventlistener
   process_name=%(program_name)s_%(process_num)02d
   numprocs=5
   events=PROCESS_STATE
   buffer_size=10
   directory=/tmp
   umask=022
   priority=-1
   autostart=true
   autorestart=unexpected
   startsecs=1
   startretries=3
   exitcodes=0,2
   stopsignal=QUIT
   stopwaitsecs=10
   stopasgroup=false
   killasgroup=false
   user=chrism
   redirect_stderr=false
   stdout_logfile=/a/path
   stdout_logfile_maxbytes=1MB
   stdout_logfile_backups=10
   stdout_events_enabled=false
   stderr_logfile=/a/path
   stderr_logfile_maxbytes=1MB
   stderr_logfile_backups=10
   stderr_events_enabled=false
   environment=A="1",B="2"
   serverurl=AUTO

``[rpcinterface:x]`` Section Settings
-------------------------------------

Adding ``rpcinterface:x`` settings in the configuration file is only
useful for people who wish to extend supervisor with additional custom
behavior.

In the sample config file, there is a section which is named
``[rpcinterface:supervisor]``.  By default it looks like the
following.

.. code-block:: ini

   [rpcinterface:supervisor]
   supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

The ``[rpcinterface:supervisor]`` section *must* remain in the
configuration for the standard setup of supervisor to work properly.
If you don't want supervisor to do anything it doesn't already do out
of the box, this is all you need to know about this type of section.

However, if you wish to add rpc interface namespaces in order to
customize supervisor, you may add additional ``[rpcinterface:foo]``
sections, where "foo" represents the namespace of the interface (from
the web root), and the value named by
``supervisor.rpcinterface_factory`` is a factory callable which should
have a function signature that accepts a single positional argument
``supervisord`` and as many keyword arguments as required to perform
configuration.  Any extra key/value pairs defined within the
``[rpcinterface:x]`` section will be passed as keyword arguments to
the factory.

Here's an example of a factory function, created in the
``__init__.py`` file of the Python package ``my.package``.

.. code-block:: python

   from my.package.rpcinterface import AnotherRPCInterface

   def make_another_rpcinterface(supervisord, **config):
       retries = int(config.get('retries', 0))
       another_rpc_interface = AnotherRPCInterface(supervisord, retries)
       return another_rpc_interface

And a section in the config file meant to configure it.

.. code-block:: ini

   [rpcinterface:another]
   supervisor.rpcinterface_factory = my.package:make_another_rpcinterface
   retries = 1

``[rpcinterface:x]`` Section Values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``supervisor.rpcinterface_factory``

  ``pkg_resources`` "entry point" dotted name to your RPC interface's
  factory function.

  *Default*: N/A

  *Required*:  No.

  *Introduced*: 3.0

``[rpcinterface:x]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [rpcinterface:another]
   supervisor.rpcinterface_factory = my.package:make_another_rpcinterface
   retries = 1
