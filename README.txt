Supervisor: A System for Allowing the Control of Process State on UNIX

History

  7/3/2006: updated for version 2.0

  8/30/2006: updated for version 2.1

  3/31/2007: updated for version 2.2

  8/15/2007: updated for version 3.0a1

  8/21/2007: updated for version 3.0a2

Upgrading

  If you are upgrading from supervisor version 2.X to version 3.X, and
  you wish to preserve your supervisor configuration file, you will
  need to read the file named 'UPGRADING.txt' within the same
  directory as this file.  Some configuration file options have
  changed and new ones have been added.

Introduction

  The supervisor is a client/server system that allows its users to
  control a number of processes on UNIX-like operating systems.  It
  was inspired by the following:

   - It is often inconvenient to need to write "rc.d" scripts for
     every single process instance.  rc.d scripts are a great
     lowest-common-denominator form of process
     initialization/autostart/management, but they can be painful to
     write and maintain.  Additionally, rc.d scripts cannot
     automatically restart a crashed process and many programs do not
     restart themselves properly on a crash.  Supervisord starts
     processes as its subprocesses, and can be configured to
     automatically restart them on a crash.  It can also automatically
     be configured to start processes on its own invocation.

   - It's often difficult to get accurate up/down status on processes
     on UNIX.  Pidfiles often lie.  Supervisord starts processes as
     subprocesses, so it always knows the true up/down status of its
     children and can be queried conveniently for this data.

   - Users who need to control process state often need only to do
     that.  They don't want or need full-blown shell access to the
     machine on which the processes are running.  Supervisorctl allows
     a very limited form of access to the machine, essentially
     allowing users to see process status and control
     supervisord-controlled subprocesses by emitting "stop", "start",
     and "restart" commands from a simple shell or web UI.

   - Users often need to control processes on many machines.
     Supervisor provides a simple, secure, and uniform mechanism for
     interactively and automatically controlling processes on groups
     of machines.

   - Processes which listen on "low" TCP ports often need to be
     started and restarted as the root user (a UNIX misfeature).  It's
     usually the case that it's perfectly fine to allow "normal"
     people to stop or restart such a process, but providing them with
     shell access is often impractical, and providing them with root
     access or sudo access is often impossible.  It's also (rightly)
     difficult to explain to them why this problem exists.  If
     supervisord is started as root, it is possible to allow "normal"
     users to control such processes without needing to explain the
     intricacies of the problem to them.

   - Processes often need to be started and stopped in groups,
     sometimes even in a "priority order".  It's often difficult to
     explain to people how to do this.  Supervisor allows you to
     assign priorities to processes, and allows user to emit commands
     via the supervisorctl client like "start all", and "restart all",
     which starts them in the preassigned priority order.
     Additionally, processes can be grouped into "process groups" and
     a set of logically related processes can be stopped and started
     as a unit.

Supported Platforms

  Supervisor has been tested and is known to run on Linux (Fedora Core
  5, Ubuntu 6), Mac OS X (10.4), and Solaris (10 for Intel) and
  FreeBSD 6.1.  It will likely work fine on most UNIX systems.

  Supervisor will not run at all under any version of Windows.

  Supervisor requires Python 2.3 or better.

Installing

  Run "python setup.py install".  This will download and install all
  distributions depended upon by supervisor and finally install
  supervisor itself.  Once that's done, copy the "sample.conf" file
  you'll find in the same directory as this file to
  /etc/supervisord.conf and modify to your liking.  If you'd rather
  not put the supervisord.conf file in /etc, you can place it anywhere
  and start supervisord and point it at the configuration file via the
  -c flag, e.g. "python supervisord.py -c /path/to/sample/conf" or, if
  you use the shell script named "supervisord", "supervisord -c
  /path/to/sample.conf".

  If your system does not have a C compiler, 'setup.py install' will
  fail, as by default, at least one of supervisor's dependent
  distributions, meld3, attempts to compile C extensions.  These
  extensions are optional, and meld3 (as of its release 0.6.1) will
  work fine without them.  To avoid attempting to compile meld3
  extensions, set the environment variable
  "NO_MELD3_EXTENSION_MODULES=1" in the shell in which you invoke
  supervisor's 'setup.py install' command, e.g.::

     NO_MELD3_EXTENSION_MODULES=1 python setup.py install

  This will cause meld3 to skip attempting to build its extensions,
  and thus supervisor's installation will succeed.

  I make reference below to a "$BINDIR" when explaining how to run
  supervisord and supervisorctl.  This is the "bindir" directory that
  your Python installation has been configured with.  For example, for
  an installation of Python installed via "./configure
  --prefix=/usr/local/python; make; make install", $BINDIR would be
  "/usr/local/python/bin".  Python interpreters on different platforms
  use different $BINDIRs.  Look at the output of "setup.py install" if
  you can't figure out where yours is.

Installing Without Internet Access

  Since "setup.py install" performs downloads of dependent software,
  it will not work on machines without internet access.  To install to
  a machine which is not internet connected, obtain the following
  dependencies on a machine which is internet-connected:

  - setuptools (latest) from http://pypi.python.org/pypi/setuptools

  - meld3 (0.6) from http://www.plope.com/software/meld3/

  - medusa (0.5.4) from http://www.amk.ca/python/code/medusa.html

  - elementtree (1.2.6) from http://effbot.org/downloads#elementtree

  And then copy these files to removable media and put them on the
  target machine.  Install each onto the target machine as per its
  instructions.

  *Note* -- if the machine you're installing on does not have a C
  compiler, meld3's "setup.py install" probably won't work because
  meld3 uses C extensions, but you can either copy the meld3/meld3
  directory into your Python's site-packages directory, or you can
  build a binary distribution for your platform on a similar machine
  that does have a C compiler before shipping it over by doing "python
  setup.py bdist".

  Finally, run supervisor's "python setup.py install".
  
Running Supervisord

  To start supervisord, run $BINDIR/supervisord.  The resulting
  process will daemonize itself and detach from the terminal.  It
  keeps an operations log at "/tmp/supervisor.log" by default.

  You can start supervisord in the foreground by passing the "-n" flag
  on its command line.  This is useful to debug startup problems.

  To change the set of programs controlled by supervisord, edit the
  supervisord.conf file and kill -HUP or otherwise restart the
  supervisord process.  This file has several example program
  definitions.

  Supervisord accepts a number of command-line overrides.  Type
  'supervisord -h' for an overview.

Running Supervisorctl

  To start supervisorctl, run $BINDIR/supervisorctl.  A shell will
  be presented that will allow you to control the processes that are
  currently managed by supervisord.  Type "help" at the prompt to get
  information about the supported commands.

  supervisorctl may be invoked with "one time" commands when invoked
  with arguments from a command line.  An example: "supervisorctl stop
  all".  If arguments are present on the supervisorctl command-line,
  it will prevent the interactive shell from being invoked.  Instead,
  the command will be executed and supervisorctl will exit.

  If supervisorctl is invoked in interactive mode against a
  supervisord that requires authentication, you will be asked for
  authentication credentials.

Components

  Supervisord

    The server piece of the supervisor is named "supervisord".  It is
    responsible for responding to commands from the client process as
    well as restarting crashed or exited processes.  It is meant to be
    run as the root user in most production setups.  NOTE: see
    "Security Notes" at the end of this document for caveats!

    The server process uses a configuration file.  This is typically
    located in "/etc/supervisord.conf".  This configuration file is an
    "Windows-INI" style config file.  It is important to keep this
    file secure via proper filesystem permissions because it may
    contain unencrypted usernames and passwords.

  Supervisorctl

    The command-line client piece of the supervisor is named
    "supervisorctl".  It provides a shell-like interface to the
    features provided by supervisord.  From supervisorctl, a user can
    connect to different supervisord processes, get status on the
    subprocesses controlled by a supervisord, stop and start
    subprocesses of a supervisord, and get lists of running processes
    of a supervisord.

    The command-line client talks to the server across a UNIX domain
    socket or an Internet socket.  The server can assert that the user
    of a client should present authentication credentials before it
    allows him to perform commands.  The client process may use the
    same configuration file as the server; any configuration file with
    a [supervisorctl] section in it will work.

  Web Server

    A (sparse) web user interface with functionality comparable to
    supervisorctl may be accessed via a browser if you start
    supervisord against an internet socket.  Visit the server URL
    (e.g. http://localhost:9001/) to view and control process status
    through the web interface after changing the configuration file's
    'http_port' parameter appropriately.

  XML-RPC Interface

    The same HTTP server which serves the web UI serves up an XML-RPC
    interface that can be used to interrogate and control supervisor
    and the programs it runs.  To use the XML-RPC interface, connect
    to supervisor's http port with any XML-RPC client library and run
    commands against it.  An example of doing this using Python's
    xmlrpclib client library::

      import xmlrpclib
      server = xmlrpclib.Server('http://localhost:9001')

    Call methods against the supervisor and its subprocesses by using
    the 'supervisor' namespace::

      server.supervisor.getState()

    You can get a list of methods supported by supervisor's XML-RPC
    interface by using the XML-RPC 'system.listMethods' API::

      server.system.listMethods()

    You can see help on a method by using the 'system.methodHelp' API
    against the method::

      print server.system.methodHelp('supervisor.shutdown')

    Supervisor's XML-RPC interface also supports the nascent XML-RPC
    multicall API described at
    http://www.xmlrpc.com/discuss/msgReader$1208.

    You can extend supervisor functionality with new XML-RPC API
    methods by adding new top-level RPC interfaces as necessary.  See
    "Configuration File ['rpcinterface:x] Section Settings" in this
    file.

Configuration File '[supervisord]' Section Settings

  The supervisord.conf log file contains a section named
  '[supervisord]' in which global settings for the supervisord process
  should be inserted.  These are:

  'http_port' -- Either a TCP host:port value or (e.g. 127.0.0.1:9001)
  or a path to a UNIX domain socket (e.g. /tmp/supervisord.sock) on
  which supervisor will listen for HTTP/XML-RPC requests.
  Supervisorctl itself uses XML-RPC to communicate with supervisord
  over this port.

  'sockchmod' -- Change the UNIX permission mode bits of the http_port
  UNIX domain socket to this value (ignored if using a TCP socket).
  Default: 0700.

  'sockchown' -- Change the user and group of the socket file to this
  value.  May be a username (e.g. chrism) or a username and group
  separated by a dot (e.g. chrism.wheel) Default: do not change.

  'umask' -- The umask of the supervisord process.  Default: 022.

  'logfile' -- The path to the activity log of the supervisord process.

  'logfile_maxbytes' -- The maximum number of bytes that may be
  consumed by the activity log file before it is rotated (suffix
  multipliers like "KB", "MB", and "GB" can be used in the value).
  Set this value to 0 to indicate an unlimited log size.  Default:
  50MB.

  'logfile_backups' -- The number of backups to keep around resulting
  from activity log file rotation.  Set this to 0 to indicate an
  unlimited number of backups.  Default: 10.

  'loglevel' -- The logging level, dictating what is written to the
  activity log.  One of 'critical', 'error', 'warn', 'info', 'debug'
  or 'trace'.  Note that at log level 'trace', the supervisord log
  file will record the stderr/stdout output of its child processes,
  which is useful for debugging.  Default: info.

  'pidfile' -- The location in which supervisord keeps its pid file.

  'nodaemon' -- If true, supervisord will start in the foreground
  instead of daemonizing.  Default: false.

  'minfds' -- The minimum number of file descriptors that must be
  available before supervisord will start successfully.  Default:
  1024.

  'minprocs' -- The minimum nymber of process descriptors that must be
  available before supervisord will start successfully.  Default: 200.

  'nocleanup' -- prevent supervisord from clearing any existing "AUTO"
  log files at startup time.  Default: false.

  'http_username' -- the username required for authentication to our
  HTTP server.  Default: none.

  'http_password' -- the password required for authentication to our
  HTTP server.  Default: none.

  'childlogdir' -- the directory used for AUTO log files.  Default:
  value of Python's tempfile.get_tempdir().

  'user' -- if supervisord is run as root, switch users to this UNIX
  user account before doing any meaningful processing.  This value has
  no effect if supervisord is not run as root.  Default: do not switch
  users.

  'directory' -- When supervisord daemonizes, switch to this
  directory.  Default: do not cd.

  'strip_ansi' -- Strip all ANSI escape sequences from process log
  files.

  'environment' -- A list of key/value pairs in the form
  "KEY=val,KEY2=val2" that will be placed in the supervisord process'
  environment (and as a result in all of its child process'
  environments).  Default: none.  **Note** that subprocesses will
  inherit the environment variables of the shell used to start
  "supervisord" except for the ones overridden here and within the
  program's "environment" configuration stanza.  See "Subprocess
  Environment" below.

  'identifier' -- The identifier for this supervisor server, used by
  the RPC interface.  Default: 'supervisor'.

Configuration File '[supervisorctl]' Section Settings

  The configuration file may contain settings for the supervisorctl
  interactive shell program.  These options are listed below.

  'serverurl' -- The URL that should be used to access the supervisord
  server, e.g. "http://localhost:9001".  For UNIX domain sockets, use
  "unix:///absolute/path/to/file.sock".

  'username' -- The username to pass to the supervisord server for use
  in authentication (should be same as 'http_username' in supervisord
  config).  Optional.

  'password' -- The password to pass to the supervisord server for use
  in authentication (should be the same as 'http_password' in
  supervisord config).  Optional.

  'prompt' -- String used as supervisorctl prompt.  Default: supervisor.

Configuration File '[program:x]' Section Settings

  The .INI file must contain one or more 'program' sections in order
  for supervisord to know which programs it should start and control.
  A sample program section has the following structure, the options of
  which are described below it::

    [program:foo]
    command=/path/to/foo
    process_name = %(program_name)s
    numprocs=1
    priority=1
    autostart=true
    autorestart=unexpected
    startsecs=1
    startretries=3
    exitcodes=0,2
    stopsignal=TERM
    stopwaitsecs=10
    user=nobody
    redirect_stderr=false
    stdout_logfile=AUTO
    stdout_logfile_maxbytes=50MB
    stdout_logfile_backups=10
    stdout_capturefile=NONE
    stderr_logfile=AUTO
    stderr_logfile_maxbytes=50MB
    stderr_logfile_backups=10
    stderr_capturefile=NONE
    environment=A=1,B=2

  '[program:foo]' -- the section header, required for each program.
  'programname' is a descriptive name (arbitrary) used to describe the
  program being run.  It must not include a colon character or a
  bracket character.

  'command' -- the command that will be run when this program is
  started.  The command can be either absolute,
  e.g. ('/path/to/programname') or relative ('programname').  If it is
  relative, the PATH will be searched for the executable.  Programs
  can accept arguments, e.g. ('/path/to/program foo bar').  The
  command line can used double quotes to group arguments with spaces
  in them to pass to the program, e.g. ('/path/to/program/name -p "foo
  bar"').  Note that the value of 'command' may include Python string
  expressions, e.g. "/path/to/programname --port=80%(process_num)02d"
  might expand to "/path/to/programname --port=8000" at runtime.
  String expressions are evaluated against a dictionary containing the
  keys "group_name", "process_num" and "program_name".  **Controlled
  programs should themselves not be daemons, as supervisord assumes it
  is responsible for daemonizing its subprocesses (see "Nondaemonizing
  of Subprocesses" later in this document).**

  'process_name' -- a Python string expression that is used to compose
  the supervisor process name for this process.  You usually don't
  need to worry about setting this unless you change 'numprocs'.  The
  string expression is evaluated against a dictionary that includes
  "group_name", "process_num" and "program_name".  Default:
  %(program_name)s.  (New in 3.0)

  'numprocs' -- Supervisor will start as many instances of this
  program as named by numprocs.  Note that if numprocs > 1, the
  'process_name' expression must include '%(process_num)s' (or any
  other valid Python string expression that includes 'process_num')
  within it.  Default: 1.  (New in 3.0)

  'priority' -- the relative priority of the program in the start and
  shutdown ordering.  Lower priorities indicate programs that start
  first and shut down last at startup and when aggregate commands are
  used in various clients (e.g. "start all"/"stop all").  Higher
  priorities indicate programs that start last and shut down first.
  Default: 999.

  'autostart' -- If true, this program will start automatically when
  supervisord is started.  Default: true.

  'autorestart' -- May be one of 'false', 'unexpected', or 'true'.  If
  'false', the process will never be autorestarted.  If 'unexpected',
  the process will be restart when the program exits with an exit code
  that is not one of the exit codes associated with this process'
  configuration (see 'exitcodes').  If 'true, the process will be
  unconditionally restarted when it exits, without regard to its exit
  code.  Default: unexpected.

  'startsecs' -- The total number of seconds which the program needs
  to stay running after a startup to consider the start successful.
  If the program does not stay up for this many seconds after it is
  started, even if it exits with an "expected" exit code (see
  "exitcodes"), the startup will be considered a failure.  Set to 0
  to indicate that the program needn't stay running for any particular
  amount of time.  Default: 1

  'startretries' -- The number of serial failure attempts that
  supervisord will allow when attempting to start the program before
  giving up and puting the process into an ERROR state. Default: 3.

  'exitcodes' -- The list of 'expected' exit codes for this program.
  If the 'autorestart' parameter is set to 'unexpected', and the
  process exits in any other way than as a result of a supervisor stop
  request, supervisor will restart the process if it exits with an
  exit code that is not defined in this list.  Default: 0,2.

  'stopsignal' -- The signal used to kill the program when a stop is
  requested.  This can be any of TERM, HUP, INT, QUIT, KILL, USR1, or
  USR2.  Default: TERM.

  'stopwaitsecs' -- The number of seconds to wait for the program to
  return a SIGCHILD to supervisord after the program has been sent a
  stopsignal.  If this number of seconds elapses before supervisord
  receives a SIGCHILD from the process, supervisord will attempt to
  kill it with a final SIGKILL.  Default: 10.

  'user' -- If supervisord is running as root, this UNIX user account
  will be used as the account which runs the program.  If supervisord
  is not running as root, this option has no effect.  Default: do not
  switch users.

  'redirect_stderr' -- If true, cause the process' stderr output to be
  sent back to supervisor on it's stdout file descriptor (in UNIX
  shell terms, this is the equivalent of executing "/the/program
  2>&1". Default: false.  (New in 3.0, replaces 2.0's "log_stdout" and
  "log_stderr")

  'stdout_logfile' -- Put process stdout output in this file (and if
  redirect_stderr is true, also place stderr output in this file).  If
  'stdout_logfile' is unset or set to 'AUTO', supervisor will
  automatically choose a file location.  If this is set to 'NONE',
  supervisord will create no log file.  AUTO log files and their
  backups will be deleted when supervisord restarts.  The
  stdout_logfile value can contain Python string expressions that will
  evaluated against a dictionary that contains the keys "process_num",
  "program_name" and "group_name".  Default: AUTO.  (New in 3.0,
  replaces 2.0's "logfile")

  'stdout_logfile_maxbytes' -- The maximum number of bytes that may be
  consumed by stdout_logfile before it is rotated (suffix multipliers
  like "KB", "MB", and "GB" can be used in the value).  Set this value
  to 0 to indicate an unlimited log size.  Default: 50MB.  (New in
  3.0, replaces 2.0's "logfile_maxbytes")

  'stdout_logfile_backups' -- The number of stdout_logfile backups to
  keep around resulting from process stdout log file rotation.  Set
  this to 0 to indicate an unlimited number of backups.  Default: 10.
  (New in 3.0, replaces "logfile_backups")

  'stdout_capturefile' -- file written to when process is in "stdout
  capture mode" (see "Capture Mode and Process Communication Events"
  later in this document).  May be a file path, NONE, or AUTO.  The
  stdout_capturefile value can contain Python string expressions that
  will evaluated against a dictionary that contains the keys
  "process_num", "program_name" and "group_name".  Default: NONE.
  (New in 3.0)

  'stderr_logfile' -- Put process stderr output in this file unless
  redirect_stderr is true.  Accepts the same value types as
  "stdout_logfile" and may contain the same Python string expressions.
  Default: AUTO.  (New in 3.0)

  'stderr_logfile_maxbytes' -- The maximum number of bytes before
  logfile rotation for stderr_logfile.  Accepts the same value types
  as "stdout_logfile_maxbytes".  Default: 50MB.  (New in 3.0)

  'stderr_logfile_backups' -- The number of backups to keep around
  resulting from process stderr log file rotation.  Default: 10.  (New
  in 3.0)

  'stderr_capturefile' -- file written to when process is in "stderr
  capture mode" (see "Capture Mode and Process Communication Events"
  later in this document).  May contain the same Python string
  expressions as "stdout_capturefile". May be a file path, NONE, or
  AUTO.  Default: NONE.  (New in 3.0)

  'environment' -- A list of key/value pairs in the form
  "KEY=val,KEY2=val2" that will be placed in the child process'
  environment.  The environment string may contain Python string
  expressions that will be evaluated against a dictionary containing
  "process_num", "program_name" and "group_name".  Default: none.
  **Note** that the subprocess will inherit the environment variables
  of the shell used to start "supervisord" except for the ones
  overridden here.  See "Subprocess Environment" below.

  Note that a '[program:x]' section actually represents a "homogeneous
  process group" to supervisor (new in 3.0).  The members of the group
  are defined by the combination of the 'numprocs and 'process_name'
  parameters in the configuration.  By default, if numprocs and
  process_name are left unchanged from their defaults, the group
  represented by '[program:x]' will be named 'x' and will have a
  single process named 'x' in it.  This provides a modicum of
  backwards compatibility with older supervisor releases, which did
  not treat program sections as homogeneous process group defnitions.

  But for instance, if you have a '[program:foo]' section with a
  'numprocs' of 3 and a 'process_name' expression of
  '%(program_name)s_%(process_num)02d', the "foo" group will contain
  three processes, named 'foo_00', 'foo_01', and 'foo_02'.  This makes
  it possible to start a number of very similar processes using a
  single '[program:x]' section.  All logfile names, all environment
  strings, and the command of programs can also contain similar Python
  string expressions, to pass slightly different parameters to each
  process.

Configuration File '[group:x]' Section Settings (New in 3.0)

  It is often useful to group "homogeneous" processes groups (aka
  "programs") together into a "heterogeneous" process group so they
  can be controlled as a unit from supervisor's various controller
  interfaces.

  To place programs into a group so you can treat them as a unit,
  define a '[group:x]' section in your configuration file, e.g.::

    [group:foo]
    programs=bar,baz
    priority=999

  For the example above to work, there must be two 'program' sections
  elsewhere in your configuration file: '[program:bar]' and
  '[program:baz]'.  If "homogeneous" program groups" (represented by
  program sections) are placed into a "heterogeneous" group via
  '[group:x]' section's "programs=" line, the homogeneous groups that
  are implied by the program section will not exist at runtime in
  supervisor.  Instead, all processes belonging to each of the
  homogeneous groups will be placed into the heterogeneous group.  In
  the above example, it means that the 'bar' and 'baz' homogeneous
  groups will not exist, and the processes that would have been under
  them will now be moved into the 'foo' group.

Configuration File '[eventlistener:x]' Section Settings (New in 3.0)

  Supervisor allows specialized homogeneous process groups ("event
  listener pools") to be defined within the configuration file.  These
  pools contain processes that are meant to receive and respond to
  event notifications from supervisor's event system.  See "Supervisor
  Events" elsewhere in this document for an explanation of how events
  work and how to implement event listener programs.

  An example of an eventlistener section defined within a supervisor
  configuration file, which creates a pool::

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

  Note that all the options available to '[program:x]' sections are
  respected by eventlistener sections except for "stdout_capturefile"
  and "stderr_capturefile" (event listeners cannot emit process
  communication events, see "Capture Mode and Process Communication
  Events" elsewhere in this document).

  '[eventlistener:x]' sections have two keys which '[program:x]'
  sections do not have:

  'buffer_size' -- The event listener pool's event queue buffer size.
  When a listener pool's event buffer is overflowed (as can happen
  when an event listener pool cannot keep up with all of the events
  sent to it), the oldest event in the buffer is discarded.

  'events' -- A comma-separated list of event type names that this
  listener is "interested" in receiving notifications for (see
  "Supervisor Events" elsewhere in this document for a list of valid
  event type names).

Configuration File '[rpcinterface:x]' Section Settings (ADVANCED, New in 3.0)

  Changing "rpcinterface:x" settings in the configuration file is only
  useful for people who wish to extend supervisor with additional
  behavior.

  In the sample config file, there is a section which is named
  "rpcinterface:supervisor".  By default it looks like this::

   [rpcinterface:supervisor]
   supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

  This section *must* remain in the configuration for the standard
  setup of supervisor to work properly.  If you don't want supervisor
  to do anything it doesn't already do out of the box, this is all you
  need to know about this type of section.

  However, if you wish to add rpc interface namespaces to a custom
  version of supervisor, you may add additional [rpcinterface:foo]
  sections, where "foo" represents the namespace of the interface
  (from the web root), and the value named by
  "supervisor.rpcinterface_factory" is a factory callable which should
  have a function signature that accepts a single positional argument
  "supervisord" and as many keyword arguments as required to perform
  configuration.  Any key/value pairs defined within the
  rpcinterface:foo section will be passed as keyword arguments to the
  factory.  Here's an example of a factory function, created in the
  package "my.package"::

   def make_another_rpcinterface(supervisord, **config):
       retries = int(config.get('retries', 0))
       another_rpc_interface = AnotherRPCInterface(supervisord, retries)
       return another_rpc_interface

   And a section in the config file meant to configure
   it::

    [rpcinterface:another]
    supervisor.rpcinterface_factory = my.package:make_another_rpcinterface
    retries = 1

Nondaemonizing of Subprocesses

  Programs run under supervisor *should not* daemonize themselves.
  Instead, they should run in the foreground and not detach from the
  "terminal" that starts them.  The easiest way to tell if a command
  will run in the foreground is to run the command from a shell
  prompt.  If it gives you control of the terminal back, it's
  daemonizing itself and that will be the wrong way to run it under
  supervisor.  You want to run a command that essentially requires you
  to press Ctrl-C to get control of the terminal back.  If it gives
  you a shell prompt back after running it without needing to press
  Ctrl-C, it's not useful under supervisor.  All programs have options
  to be run in the foreground but there's no standard way to do it;
  you'll need to read the documentation for each program you want to
  do this with.

Subprocess Environment

  Subprocesses will inherit the environment of the shell used to start
  the supervisord program.  Several environment variables will be set
  by supervisor itself in the child's environment also, including
  "SUPERVISOR_ENABLED" (a flag indicating the process is under
  supervisor control), "SUPERVISOR_PROCESS_NAME" (the
  config-file-specified process name for this process) and
  "SUPERVISOR_GROUP_NAME" (the config-file-specified process group name
  for the child process).

  These environment variables may be overridden within the
  "environment" global config option (applies to all subprocesses) or
  within the per-program "environment" config option (applies only to
  the subprocess specified within the "program" section).  These
  "environment" settings are additive.  In other words, each
  subprocess' environment will consist of::

    The environment variables set within the shell used to start
    supervisord...

    ... added-to/overridden-by ...

    ... the environment variables set within the "environment" global
    config option ...

    ... added-to/overridden-by ...

    ... supervisor-specific environment variables
     ("SUPERVISOR_ENABLED", "SUPERVISOR_PROCESS_NAME",
     "SUPERVISOR_GROUP_NAME") ..  (New in 3.0)

    ... added-to/overridden-by ...

    .. the environment variables set within the per-process
    "environment" config option.

  No shell is executed by supervisord when it runs a subprocess, so
  settings such as USER, PATH, HOME, SHELL, LOGNAME, etc. are not
  changed from their defaults or otherwise reassigned.  This is
  particularly important to note when you are running a program from a
  supervisord run as root with a "user=" stanza in the configuration.
  Unlike cron, supervisord does not attempt to divine and override
  "fundamental" environment variables like USER, PATH, HOME, and
  LOGNAME when it performs a setuid to the user defined within the
  "user=" program config option.  If you need to set environment
  variables for a particular program that might otherwise be set by a
  shell invocation for a particular user, you must do it explicitly
  within the "environment=" program config option.  For example::

    [program:apache]
    command=/home/chrism/bin/httpd -DNO_DETACH
    user=chrism
    environment=HOME=/home/chrism,USER=chrism

Examples of Program Configurations

  Apache 2.0.54::

    [program:apache]
    command=/usr/sbin/httpd -DNO_DETACH

  Postgres 8.14::

    [program:postgres]
    command=/path/to/postmaster
    ; we use the "fast" shutdown signal SIGINT
    stopsignal=INT
    redirect_stderr=true
 
  Zope 2.8 instances and ZEO::

    [program:zeo]
    command=/path/to/runzeo
    priority=1

    [program:zope1]
    command=/path/to/instance/home/bin/runzope
    priority=2
    redirect_stderr=true

    [program:zope2]
    command=/path/to/another/instance/home/bin/runzope
    priority=2
    redirect_stderr=true

  OpenLDAP slapd::

    [program:slapd]
    command=/path/to/slapd -f /path/to/slapd.conf -h ldap://0.0.0.0:8888

Process States

  A process controlled by supervisord will be in one of the below
  states at any given time.  You may see these state names in various
  user interface elements.

  STOPPED (0) -- The process has been stopped due to a stop request or
                 has never been started.

  STARTING  (10) -- The process is starting due to a start request.

  RUNNING  (20)  -- The process is running.

  BACKOFF (30) -- The process entered the STARTING state but
                  subsequently exited too quickly to move to the
                  RUNNING state.

  STOPPING (40) -- The process is stopping due to a stop request.

  EXITED  (100) -- The process exited from the RUNNING state (expectedly 
                   or unexpectedly).

  FATAL (200) -- The process could not be started successfully.

  UNKNOWN  (1000) -- The process is in an unknown state (programming error).

  Process progress through these states as per the following directed
  graph::

                            --> STOPPED
                          /       |
                         |        |
                         |        |
                   STOPPING       |
                     ^ ^          V
                     |  \--- STARTING <-----> BACKOFF
                     |      /     ^            |
                     |     V      |            |
                     \-- RUNNING / \           |
                           |    /   \          V
                           V   /     \ ----- FATAL
                         EXITED

  A process is in the STOPPED state if it has been stopped
  adminstratively or if it has never been started.

  When an autorestarting process is in the BACKOFF state, it will be
  automatically restarted by supervisord.  It will switch between
  STARTING and BACKOFF states until it becomes evident that it cannot
  be started because the number of startretries has exceeded the
  maximum, at which point it will transition to the FATAL state.  Each
  start retry will take progressively more time.

  When a process is in the EXITED state, it will automatically
  restart:

   - never if its 'autorestart' parameter is set to 'false'.

   - unconditionally if its 'autorestart' parameter is set to
     'true'.

   - conditionally if its 'autorestart' parameter is set to
     'unexpected'.  If it exited with an exit code that doesn't match
     one of the exit codes defined in the 'exitcodes' configuration
     parameter for the process, it will be restarted.

  A process automatically transitions from EXITED to RUNNING as a
  result of being configured to autorestart conditionally or
  unconditionally.  The number of transitions between RUNNING and
  EXITED is not limited in any way: it is possible to create a
  configuration that endlessly restarts an exited process.

  An autorestarted process will never be automtatically restarted if
  it ends up in the FATAL state (it must be manually restarted from
  this state).

  A process transitions into the STOPPING state via an administrative
  stop request, and will then end up in the STOPPED state.

  A process that cannot be stopped successfully will stay in the
  STOPPING state forever.  This situation should never be reached
  during normal operations as it implies that the process did not
  respond to a final SIGKILL, which is "impossible" under UNIX.

  State transitions which always require user action to invoke are
  these:

    FATAL   -> STARTING

    RUNNING -> STOPPING

  State transitions which typically, but not always, require user
  action to invoke are these, with exceptions noted:

    STOPPED -> STARTING (except at supervisord startup if process is
                         configured to autostart)

    EXITED  -> STARTING (except if process is configured to autorestart)

  All other state transitions are managed by supervisord
  automatically.

Supervisor Events (New in 3.0)

  At certain predefined points during supervisord's operation, "event
  notifications" are emitted.  An event notification implies that
  something potentially interesting happened.  Event listeners (see
  the "Event Listeners" section below) can be configured to subscribe
  to event notifications selectively, and may perform arbitrary
  actions based on an event notification (send email, make an HTTP
  request, etc).

  Event types that may be subscribed to by event listeners are
  predefined by supervisor and fall into several major categories,
  including "process state change", "process communication",
  "supervisor state change", and "event system meta" events.  These
  are described in detail below.

  EVENT -- The base event type.  This event type is abstract.  It will
  never be sent directly.  Subscribing to this event type will cause a
  subscriber to receive all event notifications emitted by supervisor.

  Subtypes of EVENT:

    PROCESS_STATE_CHANGE -- The value of this event type will be the
    process name.  This event type is abstract, it will never be sent
    directly.  Subscribing to this event type will cause a subscriber
    to receive event notifications of all the types listed below in
    "Subtypes of PROCESS_STATE_CHANGE".

    The serialized body of a PROCESS_STATE_CHANGE event (and all
    subtypes) is in the form::

      process_name: <name>
      group_name: <name>

    Subtypes of PROCESS_STATE_CHANGE:

      PROCESS_STATE_CHANGE_STARTING -- indicates a process has moved
      from a state to the STARTING state.  Subscribing to this event
      type will cause a subscriber to receive event notifications of
      all the types listed below in "Subtypes of
      PROCESS_STATE_CHANGE_STARTING".

      Subtypes of PROCESS_STATE_CHANGE_STARTING:

        PROCESS_STATE_CHANGE_STARTING_FROM_STOPPED -- subtype of
        PROCESS_STATE_CHANGE_STARTING, indicates a process has moved
        from the STOPPED state from the STARTING state.

        PROCESS_STATE_CHANGE_STARTING_FROM_BACKOFF -- subtype of
        PROCESS_STATE_CHANGE_STARTING, indicates a process has moved
        from BACKOFF state to the STARTING state.

        PROCESS_STATE_CHANGE_STARTING_FROM_EXITED -- subtype of
        PROCESS_STATE_CHANGE_STARTING, indicates a process has moved
        from the EXITED state to the STARTING state.

        PROCESS_STATE_CHANGE_STARTING_FROM_FATAL -- subtype of
        PROCESS_STATE_CHANGE_STARTING, indicates a process has moved
        to the FATAL state to the STARTING state.

      PROCESS_STATE_CHANGE_RUNNING_FROM_STARTING -- inidicates a
      process has moved from the STARTING state to the RUNNING state.

      PROCESS_STATE_CHANGE_BACKOFF_FROM_STARTING -- indicates a
      process has moved from the STARTING state to the BACKOFF state.

      PROCESS_STATE_CHANGE_STOPPING_FROM_RUNNING -- indicates a
      process has moved from the RUNNING state to the STOPPING state.

      PROCESS_STATE_CHANGE_STOPPING_FROM_STARTING -- indicates a
      process has moved from the RUNNING state to the STARTING state.

      PROCESS_STATE_CHANGE_EXITED_OR_STOPPED -- indicates a process
      has undergone a state change which caused it to move to the
      EXITED or STOPPED state.

      Subtypes of PROCESS_STATE_CHANGE_EXITED_OR_STOPPED:

        PROCESS_STATE_CHANGE_EXITED_FROM_RUNNNING -- indicates a
        process has moved from the RUNNING state to the EXITED state.

        PROCESS_STATE_CHANGE_STOPPED_FROM_STOPPING -- indicates a
        process has moved from the STOPPING state to the STOPPED
        state.

      PROCESS_STATE_CHANGE_FATAL_FROM_BACKOFF -- indicates a process
      has moved from the BACKOFF state to the FATAL state.

      PROCESS_STATE_CHANGE_TO_UNKNOWN -- indicates a process has moved
      from a state to the UNKNOWN state (indicates an error in
      supervisord).

    PROCESS_COMMUNICATION -- an event type raised when any process
    attempts to send information between <!--XSUPERVISOR:BEGIN--> and
    <!--XSUPERVISOR:END--> tags in its output.  This event type is
    abstract, it will never be sent directly.  Subscribing to this
    event type will cause a subscriber to receive event notifications
    of all the types listed below in "Subtypes of
    PROCESS_COMMUNICATION".

    The serialized body of a PROCESS_COMMUNICATION event (and all
    subtypes) is::

      process_name: <name>
      group_name: <name>
      <data>

    Subtypes of PROCESS_COMMUNICATION:

      PROCESS_COMMUNICATION_STDOUT -- indicates a process has sent a
      message to supervisor on its stdout file descriptor.

      PROCESS_COMMUNICATION_STDERR -- indicates a process has sent a
      message to supervisor on its stderr file descriptor.

    SUPERVISOR_STATE_CHANGE -- an event type raised when supervisor's
    state changes.  There is no value.  Subscribing to this event type
    will cause a subscriber to receive event notifications of all the
    types listed below in "Subtypes of SUPERVISOR_STATE_CHANGE".

    The serialization of a SUPERVISOR_STATE_CHANGE event is the empty
    string.

    Subtypes of SUPERVISOR_STATE_CHANGE:

      SUPERVISOR_STATE_CHANGE_RUNNING -- indicates that supervisor has
      started.

      SUPERVISOR_STATE_CHANGE_STOPPING -- indicates that supervisor is
      stopping or restarting.

    EVENT_BUFFER_OVERFLOW -- an event type raised when a listener
    pool's event buffer is overflowed (as can happen when an event
    listener pool cannot keep up with all of the events sent to it).
    When the pool's event buffer is overflowed, the oldest event in
    the buffer is thrown out.

    The serialization of an EVENT_BUFFER_OVERFLOW body
    is::

      group_name: <name>
      event_type: <type of discarded event>

Event Listeners (New in 3.0)

  Supervisor event listeners are subprocesses which are treated almost
  exactly like supervisor "programs" with the following differences:

  - They are defined using an [eventlistener:x] section in the config
    file instead of a [program:x] section in the configuration file.

  - Supervisor sends specially-formatted input to an event listener's
    stdin and expects specially-formatted output from an event
    listener's stdout in a request-response cycle.  A protocol agreed
    upon between supervisor and the listener's implementer allows
    listeners to process event notifications.

  - Supervisor does not respect "capture mode" output from event
    listener processes (see "Capture Mode and Process Communication
    Events" elsewhere in this document).

  When an [eventlistener:x] section is defined, it actually defines a
  "pool", where the number of event listeners in the pool is
  determined by the "numprocs" value within the section.  Every
  process in the event listener pool is treated equally by supervisor,
  and supervisor will choose one process from the pool to receive
  event notifications (filtered by the "events=" key in the
  eventlistener section).

  An event listener can send arbitrary output to its stderr, which
  will be logged or ignored by supervisord depending on the
  stderr-related configuration files in its [eventlistener:x] section.

  When an event notification is sent by the supervisor, all event
  listener pools which are subscribed to receive events for the
  event's type will be found.  One of the listeners in each listener
  pool will receive the event notification (any "available" listener).

  If the event cannot be sent because all listener in a pool are
  "busy", the event will be buffered and notification will be retried
  later.  "Later" is defined as "the next time that supervisord's
  select loop executes".

  A listener pool has an event buffer queue.  The queue is sized via
  the listener pool's "buffer_size" config file option.  If the queue
  is full and supervisor attempts to buffer an event, supervisor will
  throw away the oldest event in the buffer, log an error, and send an
  EVENT_BUFFER_OVERFLOW event.  EVENT_BUFFER_OVERFLOW events are never
  themselves buffered.

  Event listeners can be implemented in any language.  Event listeners
  can be long-running or may exit after a single request (depending on
  the implementation and the "autorestart" parameter in the
  eventlistener's configuration).

  An event listener implementation should operate in "unbuffered" mode
  or should flush its stdout every time it needs to communicate back
  to the supervisord process.

Event Listener States

  An event listener process has three possible states that are
  maintained by supervisord:

      ACKNOWLEDGED -- The event listener has acknowledged (accepted or
      rejected) an event send.

      READY -- Event notifications may be sent to this event listener.

      BUSY -- Event notifications may not be sent to this event
      listener.

  When an event listener process first starts, supervisor
  automatically places it into the ACKNOWLEDGED state to allow for
  startup activities or guard against startup failures (hangs).  Until
  the listener sends a READY token to its stdout, it will stay in this
  state.

  When supervisord sends an event notification to a listener in the
  READY state, the listener will be placed into the BUSY state until
  it receives an OK or FAILED response from the listener, at which
  time, the listener will be transitioned back into the ACKNOWLEDGED
  state.

Event Listener Notification Protocol

  Supervisord will notify an event listener in the READY state of an
  event by sending data to the stdin of the process.  Supervisord will
  never send anything to the stdin of an event listener process while
  that process is in the BUSY or ACKNOWLEDGED state.

  When supervisord sends a notification to an event listener process,
  the listener will first be sent a single "header" line on its
  stdin. The composition of the line is a set of four tokens separated
  by single spaces.  The line is terminated with a '\n' (linefeed)
  character.  The tokens on the line are:

  <PROTOCOL_VERSION> <EVENT_TYPE_NAME> <EVENT_SERIAL_NUM> <PAYLOAD_LENGTH>

  The PROTOCOL_VERSION always consists of "SUPERVISORD" followed
  immediately by numeric characters indicating the protocol version,
  with no whitespace in between.  An example: "SUPERVISOR3.0"

  The EVENT_TYPE_NAME is the specific event type name (see "Supervisor
  Events" elsewhere in this document). An example:
  "PROCESS_COMMUNICATION_STDOUT".

  The EVENT_SERIAL_NUM is an integer assigned to each event.  It is
  useful for functional testing.  An example: "30".

  The PAYLOAD_LENGTH is an integer indicating the number of bytes in
  the event payload.  An example: "22".

  An example of a complete header line:

  SUPERVISOR3.0 PROCESS_COMMUNICATION_STDOUT 30 22\n

  Directly following the linefeed character in the header is the event
  payload.  It consists of PAYLOAD_LENGTH bytes representing a
  serialization of the event data.  See "Supervisor Events" for the
  specific event data serialization definitions.  An example payload
  for a PROCESS_COMMUNICATION_STDOUT event notification is::

    process_name: foo
    group_name: bar
    This is the data that was sent between the tags

  Once it has processed the header, the event listener implementation
  should read PAYLOAD_LENGTH bytes from its stdin, perform an
  arbitrary action based on the values in the header and the data
  parsed out of the serialization.  It is free to block for an
  arbitrary amount of time while doing this.  Supervisor will continue
  processing normally as it waits for a response and it will send
  other events of the same type to other listener processes in the
  same pool as necessary.

  After the event listener has processed the event serialization, in
  order to notify supervisord about the result, it should send either
  an "OK" token or a "FAILED" token immediately followed by a carriage
  return character to its stdout.  If supervisord receives an "OK"
  token, it will assume that the listener processed the event
  notification successfully.  If it receives a "FAILED" token, it will
  assume that the listener has failed to process the event, and the
  event will be rebuffered and sent again at a later time.  The event
  listener may reject the event for any reason by returning a "FAILED"
  token.  This does not indicate a problem with the event data or the
  event listener.  Once an "OK" or "FAILED" token is received by
  supervisord, the event listener is placed into the ACKNOWLEDGED
  state.

  Once the listener is in the ACKNOWLEDGED state, it may either exit
  (and subsequently may be restarted by supervisor if its
  "autorestart" config parameter is 'true'), or it may continue
  running.  If it continues to run, in order to be placed back into
  the READY state by supervisord, it must send a "READY" token
  followed immediately by a carriage return to its stdout.

Example Event Listener Implementation

  A Python implementation of a "long-running" event listener which
  accepts an event notification, prints the header and a list of event
  serial numbers it has received to its stderr, and responds with an
  OK, and then subsequently a READY is as follows::

    import sys

    L = []

    def stdout_write(s):
        sys.stdout.write(s)
        sys.stdout.flush()

    def stderr_write(s):
        sys.stderr.write(s)
        sys.stderr.flush()
        
    while 1:
        stdout_write('READY\n')
        line = sys.stdin.readline()
        stderr_write(line)
        ver, event, serial, length = line.split(' ', 3)
        L.append(serial)
        data = sys.stdin.read(int(length))
        stderr_write(str(L))
        stdout_write('OK\n')

Event Listener Error Conditions

  If the event listener process dies while the event is being
  transmitted to its stdin, or if it dies before sending an OK/FAILED
  response back to supervisord, the event is assumed to not be
  processed and will be rebuffered by supervisord and sent again
  later.

  If an event listener sends data to its stdout which supervisor does
  not recognize as an appropriate response based on the state that the
  event listener is in, the event listener will be placed into the
  UNKNOWN state, and no further event notifications will be sent to
  it.  If an event was being processed by the listener during this
  time, it will be rebuffered and sent again later.

Capture Mode and Process Communication Events (New in 3.0)

  If a '[program:x]' section in the configuration file defines a
  "stdout_capturefile" or "stderr_capturefile" parameter, each process
  represented by the program section may emit special tokens on its
  stdout or stderr stream (respectively) which will effectively cause
  supervisor to emit a "PROCESS_COMMUNICATION" event type.

  The process communications protocol relies on two tags, one which
  commands supervisor to enter "capture mode" for the stream and one
  which commands it to exit.  When a process stream enters "capture
  mode", data sent to the stream will be sent to a separate logfile
  (the "capturefile").  When a process stream exits capture mode, the
  data in the capturefile is read into memory (a maximum of 2MB), and
  a PROCESS_COMMUNICATION event is emitted by supervisor, which may be
  intercepted by event listeners.

  The tag to begin "capture mode" in a process stream is
  '<!--XSUPERVISOR:BEGIN-->'.  The tag to exit capture mode is
  '<!--XSUPERVISOR:END-->'.  The data between these tags may be
  arbitrary, and forms the payload of the PROCESS_COMMUNICATION event.
  For example, if a program is set up with a stdout_capturefile, and
  it emits the following on its stdout stream::

    <!--XSUPERVISOR:BEGIN-->Hello!<!--XSUPERVISOR:END-->

  .. supervisor will emit a PROCESS_COMMUNICATIONS_STDOUT event with
  data in the payload of "Hello!".

Signals

  Killing supervisord with SIGHUP will stop all processes, reload the
  configuration from the config file, and restart all processes.

  Killing supervisord with SIGUSR2 will close and reopen the
  supervisord activity log and child log files.

Access Control

  The UNIX permissions on the socket effectively control who may send
  commands to the server.  HTTP basic authentication provides access
  control for internet and UNIX domain sockets as necessary.

Security Notes

  I have done my best to assure that use of a supervisord process
  running as root cannot lead to unintended privilege escalation, but
  caveat emptor.  Particularly, it is not as paranoid as something
  like DJ Bernstein's "daemontools", inasmuch as "supervisord" allows
  for arbitrary path specifications in its configuration file to which
  data may be written.  Allowing arbitrary path selections can create
  vulnerabilities from symlink attacks.  Be careful when specifying
  paths in your configuration.  Ensure that supervisord's
  configuration file cannot be read from or written to by unprivileged
  users and that all files installed by the supervisor package have
  "sane" file permission protection settings.  Additionally, ensure
  that your PYTHONPATH is sane and that all Python standard library
  files have adequate file permission protections.  Then, pray to the
  deity of your choice.

Other Notes

  Some examples of shell scripts to start services under supervisor
  can be found "here":http://www.thedjbway.org/services.html.  These
  examples are actually for daemontools but the premise is the same
  for supervisor.  Another collection of recipes for starting various
  programs in the foreground is
  "here":http://smarden.org/runit/runscripts.html .

  Some processes (like mysqld) ignore signals sent to the actual
  process/thread which is created by supervisord.  Instead, a
  "special" thread/process is created by these kinds of programs which
  is responsible for handling signals.  This is problematic, because
  supervisord can only kill a pid which it creates itself, not any
  child thread or process of the program it creates.  Fortunately,
  these programs typically write a pidfile which is meant to be read
  in order to kill the process.  As a workaround for this case, a
  special "pidproxy" program can handle startup of these kinds of
  processes.  The pidproxy program is a small shim that starts a
  process, and upon the receipt of a signal, sends the signal to the
  pid provided in a pidfile.  A sample supervisord configuration
  program entry for a pidproxy-enabled program is provided here::

   [program:mysql]
   command=/path/to/pidproxy /path/to/pidfile /path/to/mysqld_safe

  The pidproxy program is named 'pidproxy.py' and is in the
  supervisor distribution.

FAQ

  My program never starts and supervisor doesn't indicate any error:
  Make sure the "x" bit is set on the executable file you're using in
  the command= line.

  How can I tell if my program is running under supervisor? Supervisor
  and its subprocesses share an environment variable
  "SUPERVISOR_ENABLED".  When a process is run under supervisor, your
  program can check for the presence of this variable to determine
  whether it is running under supervisor (new in 2.0).

  My command line works fine when I invoke it by hand from a shell
  prompt, but when I use the same command line in a supervisor
  "command=" section, the program fails mysteriously.  Why?  This may
  be due to your process' dependence on environment variable settings.
  See "Subprocess Environment" in this document.

Maillist, Reporting Bugs, and Viewing the CVS Repository

  You may subscribe to the 'Supervisor-users'
  "maillist":http://lists.palladion.com/mailman/listinfo/supervisor-users

  Please report bugs at "the
  collector":http://www.plope.com/software/collector .

  You can view the CVS repository for supervisor at
  http://cvs.plope.com/viewcvs/Packages/supervisor2/ 

Contributing

  If you'd like to contribute to supervisor, please contact me (Chris
  McDonough, chrism@plope.com), and I'll arrange for you to have
  direct CVS access to the repository.

Author Information

  Chris McDonough (chrism@plope.com)
  "Agendaless Consulting":http://www.agendaless.com

    

