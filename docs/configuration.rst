Configuration File Syntax and Semantics
=======================================

The supervisor configuration file is conventionally named
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

:file:`supervisord.conf` is a Windows-INI-style (Python ConfigParser)
file.  It has sections (each denoted by a ``[header]``)and key / value
pairs within the sections.  The sections and their allowable values
are described below.

``[unix_http_server]`` Section Settings
---------------------------------------

The :file:`supervisord.conf` file contains a section named
``[unix_http_server]`` under which configuration parameters for an
HTTP server that listens on a UNIX domain socket should be inserted.
If the configuration file has no ``[unix_http_server]``
section, a UNIX domain socket HTTP server will not be started.  The
allowable configuration values are as follows.

.. comment:

            <entry>Key</entry>
            <entry>Description</entry>
            <entry>Default Value</entry>
            <entry>Required</entry>
            <entry>Introduced</entry>


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

  *Default*:  Use umask of user who starts supervisord.

  *Required*:  No.

  *Introduced*: 3.0

``username``

  The username required for authentication to this HTTP server.

  *Default*:  No username required.

  *Required*:  No.

  *Introduced*: 3.0

``password``

  The password required for authentication to this HTTP server.  This
  can be a cleartext password, or can be specified as a SHA hash if
  prefixed by the string ``{SHA}``.  For example,
  ``{SHA}82ab876d1387bfafe46cc1c8a2ef074eae50cb1d`` is the SHA-stored
  version of the password "thepassword".

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
  can be a cleartext password, or can be specified as a SHA hash if
  prefixed by the string ``{SHA}``.  For example,
  ``{SHA}82ab876d1387bfafe46cc1c8a2ef074eae50cb1d`` is the SHA-stored
  version of the password "thepassword".

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
  file rotation.  Set this to 0 to indicate an unlimited number of
  backups.

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
  starting properly.  See also: :ref:`supervisor_log_levels`.

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
  supervisord will start successfully.  supervisord uses file
  descriptors liberally, and will enter a failure mode when one cannot
  be obtained fromt he OS, so it's useful to be able to specify a
  minimum value to ensure it doesn't run out of them during execution.
  This option is particularly useful on Solaris, which has a low
  per-process fd limit by default.

  *Default*:  1024

  *Required*:  No.

  *Introduced*: 3.0

``minprocs``

  The minimum nymber of process descriptors that must be available
  before supervisord will start successfully.  Supervisor will enter a
  failure mode when the OS runs out of process descriptors, so it's
  useful to ensure that enough process descriptors are available upon
  :program:`supervisord` startup.

  *Default*:  200

  *Required*:  No.

  *Introduced*: 3.0

``nocleanup``

  Prevent supervisord from clearing any existing ``AUTO``
  chlild log files at startup time.  Useful for debugging.

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

  If :program:`supervisord` is run as the root user, switch users to
  this UNIX user account before doing any meaningful processing.  This
  value has no effect if :program:`supervisord` is not run as root.

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

  A list of key/value pairs in the form ``KEY=val,KEY2=val2`` that
  will be placed in the :program:`supervisord` process' environment
  (and as a result in all of its child process' environments).  This
  option can include the value ``%(here)s``, which expands to the
  directory in which the supervisord configuration file was found.
  Note that subprocesses will inherit the environment variables of the
  shell used to start :program:`supervisord` except for the ones
  overridden here and within the program's ``environment``
  configuration stanza.  See :ref:`subprocess_environment`.

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
   environment = KEY1=value1,KEY2=value2

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

  *Introduced*: post-3.0a4 (not including 3.0a4)

``[supervisorctl]`` Section Example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   [supervisorctl]
   serverurl = unix:///tmp/supervisor.sock
   username = chris
   password = 123
   prompt = mysupervisor

  <sect2 id="programx">
    <title><code>[program:x]</code> Section Settings</title>

    <para>
      The configuration file must contain one or more
      <code>program</code> sections in order for supervisord to know
      which programs it should start and control.  The header value is
      composite value.  It is the word "program", followed directly by
      a colon, then the program name.  A header value of
      <code>[program:foo]</code> describes a program with the name of
      "foo".  The name is used within client applications that control
      the processes that are created as a result of this
      configuration.  It is an error to create a <code>program</code>
      section that does not have a name.  The name must not include a
      colon character or a bracket character.  The value of the name
      is used as the value for The <code>%(program_name)s</code>
      string expression expansion within other values where specified.
    </para>

    <note>
      <para>
        A <code>[program:x]</code> section actually represents
        a "homogeneous process group" to supervisor (as of 3.0).  The
        members of the group are defined by the combination of the
        <code>numprocs</code> and <code>process_name</code> parameters
        in the configuration.  By default, if numprocs and process_name
        are left unchanged from their defaults, the group represented by
        <code>[program:x]</code> will be named <code>x</code> and will
        have a single process named <code>x</code> in it.  This provides
        a modicum of backwards compatibility with older supervisor
        releases, which did not treat program sections as homogeneous
        process group defnitions.
      </para>
    </note>

    <para>

      But for instance, if you have a <code>[program:foo]</code>
      section with a <code>numprocs</code> of 3 and a
      <code>process_name</code> expression of
      <code>%(program_name)s_%(process_num)02d</code>, the "foo" group
      will contain three processes, named <code>foo_00</code>,
      <code>foo_01</code>, and <code>foo_02</code>.  This makes it
      possible to start a number of very similar processes using a
      single <code>[program:x]</code> section.  All logfile names, all
      environment strings, and the command of programs can also
      contain similar Python string expressions, to pass slightly
      different parameters to each process.
 
   </para>


    <table>
      <title><code>[program:x]</code> Section Values</title>
      <tgroup cols="5">
        <thead>
          <row>
            <entry>Key</entry>
            <entry>Description</entry>
            <entry>Default Value</entry>
            <entry>Required</entry>
            <entry>Introduced</entry>
          </row>
        </thead>
        <tbody>
          <row>
            <entry>command</entry>
            <entry>
              The command that will be run when this program is
              started.  The command can be either absolute,
              e.g. <code>/path/to/programname'</code> or relative
              (<code>programname</code>).  If it is relative, the
              supervisord's environment $PATH will be searched for the
              executable.  Programs can accept arguments,
              e.g. <code>/path/to/program foo bar</code>.  The command
              line can used double quotes to group arguments with
              spaces in them to pass to the program,
              e.g. <code>/path/to/program/name -p "foo bar"</code>.
              Note that the value of 'command' may include Python
              string expressions, e.g. <code>/path/to/programname
              --port=80%(process_num)02d</code> might expand to
              <code>/path/to/programname --port=8000</code> at
              runtime.  String expressions are evaluated against a
              dictionary containing the keys "group_name",
              "process_num", "program_name" and "here" (the directory
              of the supervisord config file).  NOTE: Controlled
              programs should themselves not be daemons, as
              supervisord assumes it is responsible for daemonizing
              its subprocesses (see "Nondaemonizing of Subprocesses"
              elsewhere in this document).
            </entry>
            <entry>No default (required)</entry>
            <entry>True</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>process_name</entry>
            <entry>
              A Python string expression that is used to compose the
              supervisor process name for this process.  You usually
              don't need to worry about setting this unless you change
              <code>numprocs</code>.  The string expression is
              evaluated against a dictionary that includes
              "group_name", "process_num", "program_name" and "here"
              (the directory of the supervisord config file).
            </entry>
            <entry><code>%(program_name)s</code></entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>numprocs</entry>
            <entry>
              Supervisor will start as many instances of this program
              as named by numprocs.  Note that if numprocs > 1, the
              <code>process_name</code> expression must include
              <code>%(process_num)s</code> (or any other valid Python
              string expression that includes 'process_num') within
              it.
            </entry>
            <entry>1</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>numprocs_start</entry>
            <entry>
               An integer offset that is used to compute the number at
               which numprocs starts.
            </entry>
            <entry>0</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>priority</entry>
            <entry>
              The relative priority of the program in the start and
              shutdown ordering.  Lower priorities indicate programs
              that start first and shut down last at startup and when
              aggregate commands are used in various clients
              (e.g. "start all"/"stop all").  Higher priorities
              indicate programs that start last and shut down first.
            </entry>
            <entry>999</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>autostart</entry>
            <entry>
              If true, this program will start automatically when
              supervisord is started
            </entry>
            <entry>true</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>autorestart</entry>
            <entry>
              May be one of <code>false</code>,
              <code>unexpected</code>, or <code>true</code>.  If
              <code>false</code>, the process will never be
              autorestarted.  If <code>unexpected</code>, the process
              will be restart when the program exits with an exit code
              that is not one of the exit codes associated with this
              process' configuration (see <code>exitcodes</code>).  If
              <code>true</code>, the process will be unconditionally
              restarted when it exits, without regard to its exit
              code.
            </entry>
            <entry>unexpected</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>startsecs</entry>
            <entry>
              The total number of seconds which the program needs to
              stay running after a startup to consider the start
              successful.  If the program does not stay up for this
              many seconds after it is started, even if it exits with
              an "expected" exit code (see <code>exitcodes</code>),
              the startup will be considered a failure.  Set to 0 to
              indicate that the program needn't stay running for any
              particular amount of time.
            </entry>
            <entry>1</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>startretries</entry>
            <entry>
              The number of serial failure attempts that
              <application>supervisord</application> will allow when
              attempting to start the program before giving up and
              puting the process into an <code>ERROR</code> state.
              See the process state map elsewhere in this document for
              explanation of the <code>ERROR</code> state.
            </entry>
            <entry>3</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>exitcodes</entry>
            <entry>
              The list of "expected" exit codes for this program.  If
              the <code>autorestart</code> parameter is set to
              <code>unexpected</code>, and the process exits in any
              other way than as a result of a supervisor stop request,
              <application>supervisord</application> will restart the
              process if it exits with an exit code that is not
              defined in this list.
            </entry>
            <entry>0,2</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>stopsignal</entry>
            <entry>
              The signal used to kill the program when a stop is
              requested.  This can be any of TERM, HUP, INT, QUIT,
              KILL, USR1, or USR2.
            </entry>
            <entry>TERM</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>stopwaitsecs</entry>
            <entry>
              The number of seconds to wait for the OS to return a
              SIGCHILD to <application>supervisord</application> after
              the program has been sent a stopsignal.  If this number
              of seconds elapses before
              <application>supervisord</application> receives a
              SIGCHILD from the process,
              <application>supervisord</application> will attempt to
              kill it with a final SIGKILL.
            </entry>
            <entry>10</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>user</entry>
            <entry>
              If <application>supervisord</application> runs as root,
              this UNIX user account will be used as the account which
              runs the program.  If
              <application>supervisord</application> is not running as
              root, this option has no effect.
            </entry>
            <entry>Do not switch users</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>redirect_stderr</entry>
            <entry>
              If true, cause the process' stderr output to be sent
              back to <application>supervisord</application> on it's
              stdout file descriptor (in UNIX shell terms, this is the
              equivalent of executing <code>/the/program
              2>&amp;1</code>.
            </entry>
            <entry>false</entry>
            <entry>No</entry>
            <entry>
              3.0, replaces 2.0's <code>log_stdout</code> and
              <code>log_stderr</code>
            </entry>
          </row>
          <row>
            <entry>stdout_logfile</entry>
            <entry>
              Put process stdout output in this file (and if
              redirect_stderr is true, also place stderr output in
              this file).  If <code>stdout_logfile</code> is unset or
              set to <code>AUTO</code>, supervisor will automatically
              choose a file location.  If this is set to
              <code>NONE</code>, supervisord will create no log file.
              <code>AUTO</code> log files and their backups will be
              deleted when <application>supervisord</application>
              restarts.  The <code>stdout_logfile</code> value can
              contain Python string expressions that will evaluated
              against a dictionary that contains the keys
              "process_num", "program_name", "group_name", and "here"
              (the directory of the supervisord config file).
            </entry>
            <entry>AUTO</entry>
            <entry>No</entry>
            <entry>3.0, replaces 2.0's <code>logfile</code></entry>
          </row>
          <row>
            <entry>stdout_logfile_maxbytes</entry>
            <entry>
              The maximum number of bytes that may be consumed by
              <code>stdout_logfile</code> before it is rotated (suffix
              multipliers like "KB", "MB", and "GB" can be used in the
              value).  Set this value to 0 to indicate an unlimited
              log size.
            </entry>
            <entry>50MB</entry>
            <entry>No</entry>
            <entry>3.0, replaces 2.0's
            <code>logfile_maxbytes</code></entry>
          </row>
          <row>
            <entry>stdout_logfile_backups</entry>
            <entry>
              The number of <code>stdout_logfile</code> backups to
              keep around resulting from process stdout log file
              rotation.  Set this to 0 to indicate an unlimited number
              of backups.
            </entry>
            <entry>10</entry>
            <entry>No</entry>
            <entry>3.0, replace's 2.0's
            <code>logfile_backups</code></entry>
          </row>
          <row>
            <entry>stdout_capture_maxbytes</entry>
            <entry>
              max number of bytes written to capture FIFO when process
              is in "stdout capture mode" (see "Capture Mode and
              Process Communication Events" elsewhere in this
              document).  Should be an integer (suffix multipliers
              like "KB", "MB" and "GB" can used in the value).  If
              this value is 0, process capture mode will be off.
            </entry>
            <entry>0</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>stdout_events_enabled</entry>
            <entry>
              If true, PROCESS_LOG_STDOUT events will be emitted when
              the process writes to its stdout file descriptor.  The 
              events will only be emitted if the file descriptor is 
              not in capture mode at the time the data is received 
              (see "Capture Mode and Process Communication Events" 
              elsewhere in this document). 
            </entry>
            <entry>false</entry>
            <entry>No</entry>
            <entry>3.0a7</entry>
          </row>
          <row>
            <entry>stderr_logfile</entry>
            <entry>
              Put process stderr output in this file unless
              redirect_stderr is true.  Accepts the same value types
              as <code>stdout_logfile</code> and may contain the same
              Python string expressions.
            </entry>
            <entry>AUTO</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>stderr_logfile_maxbytes</entry>
            <entry>
              The maximum number of bytes before logfile rotation for
              <code>stderr_logfile</code>.  Accepts the same value
              types as <code>stdout_logfile_maxbytes</code>.
            </entry>
            <entry>50MB</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>stderr_logfile_backups</entry>
            <entry>
                The number of backups to keep around resulting from
                process stderr log file rotation.  Set this to 0 to
                indicate an unlimited number of backups.
            </entry>
            <entry>10</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>stderr_capture_maxbytes</entry>
            <entry>
              Max number of bytes written to capture FIFO when process
              is in "stderr capture mode" (see "Capture Mode and
              Process Communication Events" elsewhere in this
              document).  Should be an integer (suffix multipliers
              like "KB", "MB" and "GB" can used in the value).  If
              this value is 0, process capture mode will be off.
            </entry>
            <entry>0</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>stderr_events_enabled</entry>
            <entry>
              If true, PROCESS_LOG_STDERR events will be emitted when
              the process writes to its stderr file descriptor.  The 
              events will only be emitted if the file descriptor is 
              not in capture mode at the time the data is received 
              (see "Capture Mode and Process Communication Events" 
              elsewhere in this document).
            </entry>
            <entry>false</entry>
            <entry>No</entry>
            <entry>3.0a7</entry>
          </row>
          <row>
            <entry>environment</entry>
            <entry>
              A list of key/value pairs in the form
              <code>KEY=val,KEY2=val2</code> that will be placed in
              the child process' environment.  The environment string
              may contain Python string expressions that will be
              evaluated against a dictionary containing "process_num",
              "program_name", "group_name" and "here" (the directory
              of the supervisord config file).  **Note** that the
              subprocess will inherit the environment variables of the
              shell used to start "supervisord" except for the ones
              overridden here.  See "Subprocess Environment"
              elsewhere.
            </entry>
            <entry>No extra environment</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>directory</entry>
            <entry>
              A file path representing a directory to which
              <application>supervisord</application> should
              temporarily chdir before exec'ing the child.
            </entry>
            <entry>No chdir (inherit supervisor's)</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>umask</entry>
            <entry>
              An octal number (e.g. 002, 022) representing the umask
              of the process.
            </entry>
            <entry>No special umask (inherit supervisor's)</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>serverurl</entry>
            <entry>
              The URL passed in the environment to the subprocess
              process as <code>SUPERVISOR_SERVER_URL</code> (see
              <code>supervisor.childutils</code>) to allow the
              subprocess to easily communicate with the internal HTTP
              server.  If provided, it should have the same syntax and
              structure as the <code>[supervisorctl]</code> section
              option of the same name.  If this is set to AUTO, or is
              unset, supervisor will automatically construct a server
              URL, giving preference to a server that listens on UNIX
              domain sockets over one that listens on an internet
              socket.
            </entry>
            <entry>AUTO</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
        </tbody>
      </tgroup>
    </table>

    <example>
      <title><code>[program:x]</code> Section Example</title>
      <programlisting>
[program:cat]
command=/bin/cat
process_name=%(program_name)s
numprocs=1
directory=/tmp
umask=022
priority=999
autostart=true
autorestart=true
startsecs=10
startretries=3
exitcodes=0,2
stopsignal=TERM
stopwaitsecs=10
user=chrism
redirect_stderr=false
stdout_logfile=/a/path
stdout_logfile_maxbytes=1MB
stdout_logfile_backups=10
stdout_capture_maxbytes=1MB
stderr_logfile=/a/path
stderr_logfile_maxbytes=1MB
stderr_logfile_backups=10
stderr_capture_maxbytes=1MB
environment=A=1,B=2
serverurl=AUTO
      </programlisting>
    </example>

  </sect2>

  <sect2 id="include">
    <title><code>[include]</code> Section Settings</title>

    <para>
      The <filename>supervisord.conf</filename> file may contain a
      section named <code>[include]</code>.  If the configuration file
      contains an <code>[include]</code>, the include section must
      contain a single key named "files".  The values in this key specify
      other configuration files to be included within the configuration.
    </para>

    <table>
      <title><code>[include]</code> Section Values</title>
      <tgroup cols="5">
        <thead>
          <row>
            <entry>Key</entry>
            <entry>Description</entry>
            <entry>Default Value</entry>
            <entry>Required</entry>
            <entry>Introduced</entry>
          </row>
        </thead>
        <tbody>
          <row>
            <entry>files</entry>
            <entry>
              A space-separated sequence of file globs.  Each file
              glob may be absolute or relative.  If the file glob is
              relative, it is considered relative to the location of
              the configuration file which includes it.  A "glob" is a
              file pattern which matches a specified pattern according
              to the rules used by the Unix shell. No tilde expansion
              is done, but <code>*</code>, <code>?</code>, and
              character ranges expressed with <code>[]</code> will be
              correctly matched.  Recursive includes from included
              files are not supported.
            </entry>
            <entry>No default (required)</entry>
            <entry>Yes</entry>
            <entry>3.0</entry>
          </row>
        </tbody>
      </tgroup>
    </table>

    <example>
      <title><code>[include]</code> Section Example</title>
      <programlisting>
[include]
file = /an/absolute/filename.conf /an/absolute/*.conf foo.conf config??.conf
      </programlisting>
    </example>

  </sect2>
  <sect2 id="groupx">
    <title><code>[group:x]</code> Section Settings</title>

    <para>
      It is often useful to group "homogeneous" processes groups (aka
      "programs") together into a "heterogeneous" process group so they
      can be controlled as a unit from Supervisor's various controller
      interfaces.
    </para>

    <para>
      To place programs into a group so you can treat them as a unit,
      define a <code>[group:x]</code> section in your configuration
      file.  The group header value is a composite.  It is the word
      "group", followed directly by a colon, then the group name.  A
      header value of <code>[group:foo]</code> describes a group with
      the name of "foo".  The name is used within client applications
      that control the processes that are created as a result of this
      configuration.  It is an error to create a <code>group</code>
      section that does not have a name.  The name must not include a
      colon character or a bracket character.
    </para>

    <para>
      For a <code>[group:x]</code>, there must be one or more
      <code>[program:x]</code> sections elsewhere in your
      configuration file, and the group must refer to them by name in
      the <code>programs</code> value.
    </para>

      <para>
        If "homogeneous" program groups" (represented by program
        sections) are placed into a "heterogeneous" group via
        <code>[group:x]</code> section's <code>programs</code> line,
        the homogeneous groups that are implied by the program section
        will not exist at runtime in supervisor.  Instead, all
        processes belonging to each of the homogeneous groups will be
        placed into the heterogeneous group.  For example, given the
        following group configuration:

        <programlisting>
[group:foo]
programs=bar,baz
priority=999
        </programlisting>

        ... at supervisord startup, the <code>bar</code> and
        <code>baz</code> homogeneous groups will not exist, and the
        processes that would have been under them will now be moved
        into the <code>foo</code> group.
    </para>

    <table>
      <title><code>[group:x]</code> Section Values</title>
      <tgroup cols="5">
        <thead>
          <row>
            <entry>Key</entry>
            <entry>Description</entry>
            <entry>Default Value</entry>
            <entry>Required</entry>
            <entry>Introduced</entry>
          </row>
        </thead>
        <tbody>
          <row>
            <entry>programs</entry>
            <entry>
              A comma-separated list of program names.  The
              programs which are listed become members of the group.
            </entry>
            <entry>N/A (required)</entry>
            <entry>Yes</entry>
            <entry>3.0</entry>
          </row>
          <row>
            <entry>priority</entry>
            <entry>
              A priority number analogous to a
              <code>[program:x]</code> priority value assigned to the
              group.
            </entry>
            <entry>999</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
        </tbody>
      </tgroup>
    </table>
          
    <example>
      <title><code>[group:x]</code> Section Example</title>
      <programlisting>
[group:foo]
programs=bar,baz
priority=999
      </programlisting>
    </example>

  </sect2>

  <sect2 id="fcgi-programx">
    <title><code>[fcgi-program:x]</code> Section Settings</title>

    <para>
      Supervisor can manage groups of
      <ulink url="http://www.fastcgi.com">FastCGI</ulink> processes that all
      listen on the same socket.  Until now, deployment flexibility
      for FastCGI was limited.  To get full process management,
      you could use mod_fastcgi under Apache but then you were stuck
      with Apache's inefficient concurrency model of one process
      or thread per connection.  In addition to requiring more CPU
      and memory resources, the process/thread per connection model
      can be quickly saturated by a slow resource, preventing other
      resources from being served.  In order to take advantage of
      newer event-driven web servers such as lighttpd or nginx which
      don't include a built-in process manager, you had to use scripts
      like cgi-fcgi or spawn-fcgi.  These can be used in conjunction
      with a process manager such as supervisord or daemontools but
      require each FastCGI child process to bind to it's own socket.
      The disadvantages of this are: unnecessarily complicated web
      server configuration, ungraceful restarts, and reduced fault
      tolerance.  With less sockets to configure, web server configurations
      are much smaller if groups of FastCGI processes can share sockets.
      Shared sockets allow for graceful restarts because the socket remains
      bound by the parent process while any of the child processes are being
      restarted.  Finally, shared sockets are more fault tolerant because
      if a given process fails, other processes can continue to serve
      inbound connections.
    </para>
		
    <para>
      With integrated FastCGI spawning support, Supervisor gives you the
      best of both worlds.  You get full-featured process management with
      groups of FastCGI processes sharing sockets without being tied to a
      particular web server.  It's a clean separation of concerns, allowing
      the web server and the process manager to each do what they do best.
    </para>

    <para>
      Note that all the options available to <code>[program:x]</code>
      sections are also respected by fcgi-program sections.
    </para>
      
    <para>
      <code>[fcgi-program:x]</code> sections have a single key which
      <code>[program:x]</code> sections do not have.
    </para>

    <variablelist>
      <varlistentry>
        <term>socket</term>
        <listitem>
          <para>
            The FastCGI socket for this program, either TCP or UNIX domain
            socket. For TCP sockets, use this format: 
            <code>tcp://localhost:9002</code>.  For UNIX domain sockets, use
            <code>unix:///absolute/path/to/file.sock</code>.  String
            expressions are evaluated against a dictionary containing the keys
            "program_name" and "here" (the directory of the supervisord config
            file).
          </para>
        </listitem>
      </varlistentry>
    </variablelist>

    <para>
      Consult <code>[program:x]</code> Section Values for allowable
      keys, delta the above constraints and additions.
    </para>

    <example>
      <title><code>[fcgi-program:x]</code> Section Example</title>
      <programlisting>
[fcgi-program:fcgiprogramname]
command=/usr/bin/example.fcgi
socket=unix:///var/run/supervisor/%(program_name)s.sock
process_name=%(program_name)s_%(process_num)02d
numprocs=5
priority=999
autostart=true
autorestart=unexpected
startsecs=1
startretries=3
exitcodes=0,2
stopsignal=QUIT
stopwaitsecs=10
user=chrism
redirect_stderr=true
stdout_logfile=/a/path
stdout_logfile_maxbytes=1MB
stdout_logfile_backups=10
stderr_logfile=/a/path
stderr_logfile_maxbytes=1MB
stderr_logfile_backups
environment=A=1,B=2
      </programlisting>
    </example>

  </sect2>

  <sect2 id="eventlistenerx">
    <title><code>[eventlistener:x]</code> Section Settings</title>

    <para>
      Supervisor allows specialized homogeneous process groups ("event
      listener pools") to be defined within the configuration file.
      These pools contain processes that are meant to receive and
      respond to event notifications from supervisor's event system.
      See "Supervisor Events" elsewhere in this document for an
      explanation of how events work and how to implement programs
      that can be declared as event listeners.
    </para>

    <para>
      Note that all the options available to <code>[program:x]</code>
      sections are respected by eventlistener sections except for
      <code>stdout_capture_maxbytes</code> and
      <code>stderr_capture_maxbytes</code> (event listeners cannot
      emit process communication events, see "Capture Mode and Process
      Communication Events" elsewhere in this document).
    </para>
      
    <para>
      <code>[eventlistener:x]</code> sections have a few keys which
      <code>[program:x]</code> sections do not have.
    </para>

    <variablelist>
      <varlistentry>
        <term>buffer_size</term>
        <listitem>
          <para>
            The event listener pool's event queue buffer size.  When a
            listener pool's event buffer is overflowed (as can happen
            when an event listener pool cannot keep up with all of the
            events sent to it), the oldest event in the buffer is
            discarded.
          </para>
        </listitem>
      </varlistentry>
      <varlistentry>
        <term>events</term>
        <listitem>
          <para>
            A comma-separated list of event type
            names that this listener is "interested" in receiving
            notifications for (see "Supervisor Events" elsewhere in this
          document for a list of valid event type names).
          </para>
        </listitem>
      </varlistentry>
      <varlistentry>
        <term>result_handler</term>
        <listitem>
          <para>
            A <ulink
            url="http://peak.telecommunity.com/DevCenter/PkgResources"
            >pkg_resources</ulink> "entry point" string that resolves
            to a Python callable.  The default value is
            <code>supervisor.dispatchers:default_handler</code>
            Specifying an alternate result handler is a very uncommon
            thing to need to do, and as a result, how to create one is
            not documented.
          </para>
        </listitem>
      </varlistentry>
    </variablelist>

    <para>
      Consult <code>[program:x]</code> Section Values for allowable
      keys, delta the above constraints and additions.
    </para>

    <example>
      <title><code>[eventlistener:x]</code> Section Example</title>
      <programlisting>
[eventlistener:theeventlistenername]
command=/bin/eventlistener
process_name=%(program_name)s_%(process_num)02d
numprocs=5
events=PROCESS_STATE_CHANGE
buffer_size=10
priority=-1
autostart=true
autorestart=unexpected
startsecs=1
startretries=3
exitcodes=0,2
stopsignal=QUIT
stopwaitsecs=10
user=chrism
redirect_stderr=true
stdout_logfile=/a/path
stdout_logfile_maxbytes=1MB
stdout_logfile_backups=10
stderr_logfile=/a/path
stderr_logfile_maxbytes=1MB
stderr_logfile_backups
environment=A=1,B=2
      </programlisting>
    </example>

  </sect2>

  <sect2 id="rpcinterfacex">
    <title><code>[rpcinterface:x]</code> Section Settings</title>

    <para>
      Adding "rpcinterface:x" settings in the configuration file is
      only useful for people who wish to extend supervisor with
      additional custom behavior.
    </para>

    <para>
      In the sample config file, there is a section which is named
      <code>[rpcinterface:supervisor]</code>.  By default it looks
      like the following.
    </para>

    <programlisting>
[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface
    </programlisting>

    <para>
      The <code>[rpcinterface:supervisor]</code> section *must* remain
      in the configuration for the standard setup of supervisor to
      work properly.  If you don't want supervisor to do anything it
      doesn't already do out of the box, this is all you need to know
      about this type of section.
    </para>
      
    <para>
      However, if you wish to add rpc interface namespaces in order to
      customize Supervisor, you may add additional [rpcinterface:foo]
      sections, where "foo" represents the namespace of the interface
      (from the web root), and the value named by
      <code>supervisor.rpcinterface_factory</code> is a factory
      callable which should have a function signature that accepts a
      single positional argument <code>supervisord</code> and as many
      keyword arguments as required to perform configuration.  Any
      extra key/value pairs defined within the
      <code>[rpcinterface:x]</code> section will be passed as keyword
      arguments to the factory.
    </para>
    
    <para>
      Here's an example of a factory function, created in the
      <code>__init__.py</code> file of the Python package
      "my.package".
    </para>

    <programlisting>
      
from my.package.rpcinterface import AnotherRPCInterface

def make_another_rpcinterface(supervisord, **config):
    retries = int(config.get('retries', 0))
    another_rpc_interface = AnotherRPCInterface(supervisord, retries)
    return another_rpc_interface

    </programlisting>

    <para>And a section in the config file meant to configure it.</para>
    <programlisting>

[rpcinterface:another]
supervisor.rpcinterface_factory = my.package:make_another_rpcinterface
retries = 1
    </programlisting>

    <table>
      <title><code>[rpcinterface:x]</code> Section Values</title>
      <tgroup cols="5">
        <thead>
          <row>
            <entry>Key</entry>
            <entry>Description</entry>
            <entry>Default Value</entry>
            <entry>Required</entry>
            <entry>Introduced</entry>
          </row>
        </thead>
        <tbody>
          <row>
            <entry>supervisor.rpcinterface_factory</entry>
            <entry>"Entry point" dotted name to your RPC interface's
            factory function</entry>
            <entry>N/A</entry>
            <entry>No</entry>
            <entry>3.0</entry>
          </row>
        </tbody>
      </tgroup>
    </table>
          
    <example>
      <title><code>[rpcinterface:x]</code> Section Example</title>
      <programlisting>
[rpcinterface:another]
supervisor.rpcinterface_factory = my.package:make_another_rpcinterface
retries = 1
      </programlisting>
    </example>

  </sect2>

</sect1>

<!--
vim:se ts=4 sw=4 et:
-->
