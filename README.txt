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
     "restart" and "status" commands from a simple shell.

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

Components

  The server piece of the supervisor is named "supervisord".  It is
  responsible for responding to commands from the client process as
  well as restarting crashed processes.  It is meant to be run as the
  root user in most production setups.  NOTE: see "Security Notes" at
  the end of this document for caveats!

  The server process uses a configuration file.  This is typically
  located in "/etc/supervisord.conf".  This configuration file is an
  "Windows-INI" style config file.  Full documentation of the schema
  of the configuration file is currently only available via the
  source.

  The command-line client piece of the supervisor is named
  "supervisorctl".  It provides a shell-like interface to the features
  provided by supervisord.  From supervisorctl, a user can connect to
  different supervisord processes, get status on the subprocesses
  controlled by a supervisord, stop and start subprocesses of a
  supervisord, and get lists of running processes of a supervisord.

  The command-line client talks to the server across a UNIX domain
  socket or an Internet socket.  The server can assert that the user
  of a client should present authentication credentials before it
  allows him to perform commands.  The client process may use the same
  configuration file as the server.

  A (sparse) web user interface with functionality comparable to
  supervisorctl may be accessed via a browser if you start supervisord
  against an internet socket.  Visit the server URL
  (e.g. http://localhost:9001) to see the web interface.

Installing

  Run "python setup.py install", then copy the sample.conf file
  to /etc/supervisord.conf.

Running Supervisord

  To start supervisord, run $PYDIR/bin/supervisord.  The resulting
  process will daemonize itself and detach from the terminal.  It
  keeps an operations log at "$PYDIR/var/supervisor.log" by default.

  At log level "debug", the supervisord log file will record the
  stderr/stdout output of its child processes, which is useful for
  debugging.  Each child processes may additionally be configured to
  send its stderr/stdout to a separate log file.

  To change the set of programs controlled by supervisord, edit the
  $/etc/supervisord.conf file and HUP or restart the supervisord
  process.  This file has several example program definitions.
  Controlled programs should themselves not be daemons, as supervisord
  assumes it is responsible for daemonizing its subprocesses.

  Supervisord accepts a number of command-line overrides.  Type
  supervisord -h for an overview.

  Killing supervisord with HUP will stop all processes, reload the
  configuration from the config file, and restart all processes.

  Killing supervisord with USR2 will rotate the supervisord and child
  stdout/stderr log files.

Running Supervisorctl

  To start supervisorctl, run $PYDIR/bin/supervisorctl.  A shell will
  be presented that will allow you to control the processes that are
  currently managed by supervisord.  Type "help" at the prompt to get
  information about the supported commands.

  supervisorctl may be invoked with "one time" commands when invoked
  with arguments from a command line.  An example: "supervisorctl stop
  all".  If arguments are present on the supervisorctl command-line,
  it will prevent the interactive shell from being invoked.  Instead,
  the command will be executed and supervisorctl will exit.

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

  Some processes (like mysqld) ignore signals sent to the actual
  process/thread which is created by supervisord.  Instead, a
  "special" thread/process is created by these kinds of programs which
  is responsible for handling signals.  This is problematic, because
  supervisord can only kill a pid which it creates itself.
  Fortunately, these programs typically write a pidfile which is meant
  to be read in order to kill the proces.  To service a workaround for
  this case, a special "pidproxy" program can handle startup of these
  kinds of processes.  The pidproxy program is a small shim that
  starts a process, and upon the receipt of a signal, sends the signal
  to the pid provided in a pidfile.  A sample supervisord
  configuration program entry for a pidproxy-enabled program is
  provided here:

   [program:mysql]
   command=/path/to/pidproxy /path/to/pidfile /path/to/mysqld_safe


  The pidproxy program is named 'pidproxy.py' and is in the
  distribution.

  - Chris McDonough (chrism@plope.com), http://www.plope.com
  

