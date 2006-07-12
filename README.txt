Supervisor: A System for Allowing the Control of Process State on UNIX

History

  7/3/2006: updated for version 2.0

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

Supported Platforms

  Supervisor has been tested and is known to run on Linux (Fedora Core
  5, Ubuntu 6), Mac OS X (10.4), and Solaris (10 for Intel) and
  FreeBSD 6.1.  It will likely work fine on most UNIX systems.

  Supervisor will not run at all under any version of Windows.

  Supervisor requires Python 2.3 or better.

Installing

  Run "python setup.py install", then copy the "sample.conf" file to
  /etc/supervisord.conf and modify to your liking.  If you'd rather
  not put the supervisord.conf file in /etc, you can place it anywhere
  and start supervisord and point it at the configuration file via the
  -c flag, e.g. "python supervisord.py -c /path/to/sample/conf" or, if
  you use the shell script named "supervisord", "supervisord -c
  /path/to/sample.conf".

  I make reference below to a "$BINDIR" when explaining how to run
  supervisord and supervisorctl.  This is the "bindir" directory that
  your Python installation has been configured with.  For example, for
  an installation of Python installed via "./configure
  --prefix=/usr/local/python; make; make install", $BINDIR would be
  "/usr/local/python/bin".  Python interpreters on different platforms
  use different $BINDIRs.  Look at the output of "setup.py install" if
  you can't figure out where yours is.
  
Running Supervisord

  To start supervisord, run $BINDIR/supervisord.  The resulting
  process will daemonize itself and detach from the terminal.  It
  keeps an operations log at "/tmp/supervisor.log" by default.

  You can start supervisord in the foreground by passing the "-n" flag
  on its command line.  This is useful to debug startup problems.

  To change the set of programs controlled by supervisord, edit the
  supervisord.conf file and kill -HUP or otherwise restart the
  supervisord process.  This file has several example program
  definitions.  Controlled programs should themselves not be daemons,
  as supervisord assumes it is responsible for daemonizing its
  subprocesses.

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
    well as restarting crashed processes.  It is meant to be run as
    the root user in most production setups.  NOTE: see "Security
    Notes" at the end of this document for caveats!

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
    interface by using the XML-RPC 'system.listMethods' API:

      server.system.listMethods()

    You can see help on a method by using the 'system.methodHelp' API
    against the method::

      print server.system.methodHelp('supervisor.shutdown')

    Supervisor's XML-RPC interface also supports the nascent
    "XML-RPC multicall API":http://www.xmlrpc.com/discuss/msgReader$1208 .

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
  or 'trace'.  At log level 'trace', the supervisord log file will
  record the stderr/stdout output of its child processes, which is
  useful for debugging.  Default: info.

  'pidfile' -- The location in which supervisord keeps its pid file.

  'nodaemon' -- If true, supervisord will start in the foreground
  instead of daemonizing.  Default: false.

  'minfds' -- The minimum number of file descriptors that must be
  available before supervisord will start successfully.  Default:
  1024.

  'minprocs' -- The minimum nymber of process descriptors that must be
  available before supervisord will start successfully.  Default: 200.

  'nocleanup' -- prevent supervisord from clearing old "AUTO" log
  files at startup time.  Default: false.

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

    [program:programname]
    command=/path/to/programname
    priority=1
    autostart=true
    autorestart=true
    startsecs=10
    startretries=3
    exitcodes=0,2
    stopsignal=TERM
    stopwaitsecs=10
    user=nobody
    log_stdout=true
    log_stderr=false
    logfile=/tmp/programname.log
    logfile_maxbytes=10MB
    logfile_backups=2

  '[program:programname]' -- the section header, required for each
  program.  'programname' is a descriptive name (arbitrary) used to
  describe the program being run.

  'command' -- the command that will be run when this program is
  started.  The command can be either absolute,
  e.g. ('/path/to/programname') or relative ('programname').  If it is
  relative, the PATH will be searched for the executable.  Programs
  can accept arguments, e.g. ('/path/to/program foo bar').  The
  command line can used double quotes to group arguments with spaces
  in them to pass to the program, e.g. ('/path/to/program/name -p "foo
  bar"').

  'priority' -- the relative priority of the program in the start and
  shutdown ordering.  Lower priorities indicate programs that start
  first and shut down last at startup and when aggregate commands are
  used in various clients (e.g. "start all"/"stop all").  Higher
  priorities indicate programs that start last and shut down first.
  Default: 999.

  'autostart' -- If true, this program will start automatically when
  supervisord is started.  Default: true.

  'autorestart' -- If true, when the program exits "unexpectedly",
  supervisor will restart it automatically.  "unexpected" exits are
  those which happen when the program exits with an "unexpected" exit
  code (see 'exitcodes').  Default: true.

  'startsecs' -- The total number of seconds which the program needs
  to stay running after a startup to consider the start successful.
  If the program does not stay up for this many seconds after it is
  started, even if it exits with an "expected" exit code, the startup
  will be considered a failure.  Set to 0 to indicate that the program
  needn't stay running for any particular amount of time.  Default: 1.

  'startretries' -- The number of serial failure attempts that
  supervisord will allow when attempting to start the program before
  giving up and puting the process into an ERROR state. Default: 3.

  'exitcodes' -- The list of 'expected' exit codes for this program.
  A program is considered 'failed' (and will be restarted, if
  autorestart is set true) if it exits with an exit code which is not
  in this list and a stop of the program has not been explicitly
  requested.  Default: 0,2.

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
  is not running as root, this option has no effect.  Defaut: do not
  switch users.

  'log_stdout' -- Send process stdout output to the process logfile.
  Default: true.

  'log_stderr' -- Send process stderr output to the process logfile.
  Default: false.

  'logfile' -- Keep process output as determined by log_stdout and
  log_stderr in this file.  NOTE: if both log_stderr and log_stdout
  are true, chunks of output from the process' stderr and stdout will
  be intermingled more or less randomly in the log.  If 'logfile' is
  unset or set to 'AUTO', supervisor will automatically choose a file
  location.  If this is set to 'NONE', supervisord will create no log
  file.  AUTO log files and their backups will be deleted when
  supervisord restarts.  Default: AUTO.

  'logfile_maxbytes' -- The maximum number of bytes that may be
  consumed by the process log file before it is rotated (suffix
  multipliers like "KB", "MB", and "GB" can be used in the value).
  Set this value to 0 to indicate an unlimited log size.  Default:
  50MB.

  'logfile_backups' -- The number of backups to keep around resulting
  from process log file rotation.  Set this to 0 to indicate an
  unlimited number of backups.  Default: 10.

Examples of Program Configurations

  Postgres 8.14::

    [program:postgres]
    command=/path/to/postmaster
    ; we use the "fast" shutdown signal SIGINT
    stopsignal=INT
 
  Zope 2.8 instances and ZEO::

    [program:zeo]
    command=/path/to/runzeo
    priority=1

    [program:zope1]
    command=/path/to/instance/home/bin/runzope
    priority=2
    log_stderr=true

    [program:zope2]
    command=/path/to/another/instance/home/bin/runzope
    priority=2
    log_stderr=true

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

  BACKOFF (30) -- The process is waiting to restart after a nonfatal error.

  STOPPING (40) -- The process is stopping due to a stop request.

  EXITED  (100) -- The process exited with an expected exit code.

  FATAL  (200) -- The process could not be started successfully.

  UNKNOWN  (1000) -- The process is in an unknown state (programming error).

  Process progress through these states as per the following directed
  graph::

                           STOPPED
                           ^     |
                          /      |
                    STOPPING     |
                     ^           V
                     |       STARTING <-----> BACKOFF
                     |      /        \
                     |     V          V
                     \-- RUNNING    FATAL
                           |
                           V
                         EXITED

  A process is in the STOPPED state if it has been stopped
  adminstratively or if it has never been started.

  When an autorestarting process is in the BACKOFF state, it will be
  automatically restarted by supervisord.  It will switch between
  STARTING and BACKOFF states until it becomes evident that it cannot
  be started because the number of startretries has exceeded the
  maximum, at which point it will transition to the FATAL state.  Each
  start retry will take progressively more time.

  An autorestarted process will never be automtatically restarted if
  it ends up in the FATAL state (it must be manually restarted from
  this state).

  A process transitions into the STOPPING state via an administrative
  stop request, and will then end up in the STOPPED state.

  A process that cannot be stopped successfully will stay in the
  STOPPING state forever.  This situation should never be reached
  during normal operations as it implies that the process did not
  respond to a final SIGKILL, which is "impossible" under UNIX.

  Terminal states are "STOPPED", "FATAL", "EXITED", and "UNKNOWN".
  All other states are transitional.

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
  for supervisor.

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
  program entry for a pidproxy-enabled program is provided here:

   [program:mysql]
   command=/path/to/pidproxy /path/to/pidfile /path/to/mysqld_safe

  The pidproxy program is named 'pidproxy.py' and is in the
  distribution.

FAQ

  My program never starts and supervisor doesn't indicate any error:
  Make sure the "x" bit is set on the executable file you're using in
  the command= line.

  How can I tell if my program is running under supervisor? Supervisor
  and its subprocesses share an environment variable
  "SUPERVISOR_ENABLED".  When a process is run under supervisor, your
  program can check for the presence of this variable to determine
  whether it is running under supervisor (new in 2.0).

Reporting Bugs

  Please report bugs at http://www.plope.com/software/collector .

Author Information

  Chris McDonough (chrism@plope.com)
  http://www.plope.com
  

