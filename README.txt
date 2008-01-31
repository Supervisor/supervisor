Supervisor: A System for Allowing the Control of Process State on UNIX

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

  Supervisor has been tested and is known to run on Linux (Ubuntu
  Dapper), Mac OS X (10.4), and Solaris (10 for Intel) and FreeBSD
  6.1.  It will likely work fine on most UNIX systems.

  Supervisor will not run at all under any version of Windows.

  Supervisor is known to work with Python 2.3.3 or better, and it may
  work with Python 2.3.0, Python 2.3.1 and Python 2.3.2 (although
  these have not been tested).  It will not work under Python versions
  2.2 or before.

Documentation

  You can view the current Supervisor documentation online "in html
  format":http://supervisord.org/manual/ .  This is where you should
  go for detailed installation and configuration documentation.

  XXX We need some way of getting people the entire docs set without
  needing to read it via HTML online.

Maillist, Reporting Bugs, and Viewing the CVS Repository

  You may subscribe to the 'Supervisor-users'
  "maillist":http://supervisord.org/mailman/listinfo/supervisor-users

  Please report bugs at "the
  collector":http://www.plope.com/software/collector .

  XXX get a better bugtracker

  You can view the Subversion repository for supervisor via
  http://svn.supervisord.org:"http://svn.supervisord.org"

Contributing

  If you'd like to contribute to supervisor directly, please contact
  the "supervisor-users
  maillist":http://supervisord.org/mailman/listinfo/supervisor-users

Author Information

  Chris McDonough (chrism@plope.com)
  "Agendaless Consulting":http://www.agendaless.com

  Mike Naberezny (mike@maintainable.com)
  "Maintainable Software":http://www.maintainable.com

    

