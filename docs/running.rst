Running Supervisor
==================

This section makes reference to a :envvar:`BINDIR` when explaining how
to run the :command:`supervisord` and :command:`supervisorctl`
commands.  This is the "bindir" directory that your Python
installation has been configured with.  For example, for an
installation of Python installed via ``./configure
--prefix=/usr/local/py; make; make install``, :envvar:`BINDIR` would
be :file:`/usr/local/py/bin`. Python interpreters on different
platforms use a different :envvar:`BINDIR`.  Look at the output of
``setup.py install`` if you can't figure out where yours is.

Adding a Program
----------------

Before :program:`supervisord` will do anything useful for you, you'll
need to add at least one ``program`` section to its configuration.
The ``program`` section will define a program that is run and managed
when you invoke the :command:`supervisord` command.  To add a program,
you'll need to edit the :file:`supervisord.conf` file.

One of the simplest possible programs to run is the UNIX
:program:`cat` program.  A ``program`` section that will run ``cat``
when the :program:`supervisord` process starts up is shown below.

.. code-block:: ini

   [program:foo]
   command=/bin/cat

This stanza may be cut and pasted into the :file:`supervisord.conf`
file.  This is the simplest possible program configuration, because it
only names a command.  Program configuration sections have many other
configuration options which aren't shown here.  See
:ref:`program_configuration` for more information.

Running :program:`supervisord`
------------------------------
    
To start :program:`supervisord`, run :file:`$BINDIR/supervisord`.  The
resulting process will daemonize itself and detach from the terminal.
It keeps an operations log at :file:`$CWD/supervisor.log` by default.
      
You may start the :command:`supervisord` executable in the foreground
by passing the ``-n`` flag on its command line.  This is useful to
debug startup problems.

To change the set of programs controlled by :program:`supervisord`,
edit the :file:`supervisord.conf` file and ``kill -HUP`` or otherwise
restart the :program:`supervisord` process.  This file has several
example program definitions.

The :command:`supervisord` command accepts a number of command-line
options.  Each of thsese command line options overrides any equivalent
value in the configuration file.

:command:`supervisord` Command-Line Options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-c FILE, --configuration=FILE

   The path to a :program:`supervisord` configuration file.

-n, --nodaemon

   Run :program:`supervisord` in the foreground.

-h, --help

   Show :command:`supervisord` command help.

-u USER, --user=USER

   UNIX username or numeric user id.  If :program:`supervisord` is
   started as the root user, setuid to this user as soon as possible
   during startup.

-m OCTAL, --umask=OCTAL

   Octal number (e.g. 022) representing the :term:`umask` that should
   be used by :program:`supervisord` after it starts.

-d PATH, --directory=PATH

   When supervisord is run as a daemon, cd to this directory before
   daemonizing.

-l FILE, --logfile=FILE

   Filename path to use as the supervisord activity log.

-y BYTES, --logfile_maxbytes=BYTES

   Max size of the supervisord activity log file before a rotation
   occurs.  The value is suffix-multiplied, e.g "1" is one byte, "1MB"
   is 1 megabyte, "1GB" is 1 gigabyte.

-y NUM, --logfile_backups=NUM

   Number of backup copies of the supervisord activity log to keep
   around.  Each logfile will be of size ``logfile_maxbytes``.

-e LEVEL, --loglevel=LEVEL

   The logging level at which supervisor should write to the activity
   log.  Valid levels are ``trace``, ``debug``, ``info``, ``warn``,
   ``error``, and ``critical``.

-j FILE, --pidfile=FILE

   The filename to which supervisord should write its pid file.

-i STRING, --identifier=STRING

   Arbitrary string identifier exposed by various client UIs for this
   instance of supervisor.

-q PATH, --childlogdir=PATH

   A path to a directory (it must already exist) where supervisor will
   write its ``AUTO`` -mode child process logs.

-k, --nocleanup

   Prevent :program:`supervisord` from performing cleanup (removal of
   old ``AUTO`` process log files) at startup.

-a NUM, --minfds=NUM

   The minimum number of file descriptors that must be available to
   the supervisord process before it will start successfully.

-t, --strip_ansi

   Strip ANSI escape sequences from all child log process.

--profile_options=LIST

   Comma-separated options list for profiling.  Causes
   :program:`supervisord` to run under a profiler, and output results
   based on the options, which is a comma-separated list of the
   following: ``cumulative``, ``calls``, ``callers``.
   E.g. ``cumulative,callers``.

--minprocs=NUM 

   The minimum number of OS process slots that must be available to
   the supervisord process before it will start successfully.

Running :program:`supervisorctl`
--------------------------------

To start :program:`supervisorctl`, run ``$BINDIR/supervisorctl``.  A
shell will be presented that will allow you to control the processes
that are currently managed by :program:`supervisord`.  Type "help" at
the prompt to get information about the supported commands.

The :command:supervisorctl` executable may be invoked with "one time"
commands when invoked with arguments from a command line.  An example:
``supervisorctl stop all``.  If arguments are present on the
command-line, it will prevent the interactive shell from being
invoked.  Instead, the command will be executed and
``supervisorctl`` will exit.

If :command:`supervisorctl` is invoked in interactive mode against a
:program:`supervisord` that requires authentication, you will be asked
for authentication credentials.

Signals
-------

The :program:`supervisord` program may be sent signals which cause it
to perform certain actions while it's running.

You can send any of these signals to the single :program:`supervisord`
process id.  This process id can be found in the file represented by
the ``pidfile`` parameter in the ``[supervisord]`` section of the
configuration file (by default it's :file:`$CWD/supervisord.pid`).

Signal Handlers
~~~~~~~~~~~~~~~

``SIGTERM``

  :program:`supervisord` and all its subprocesses will shut down.
  This may take several seconds.

``SIGINT``

  :program:`supervisord` and all its subprocesses will shut down.
  This may take several seconds.

``SIGQUIT``

  :program:`supervisord` and all its subprocesses will shut down.
  This may take several seconds.

``SIGHUP``

  :program:`supervisord` will stop all processes, reload the
  configuration from the first config file it finds, and restart all
  processes.

``SIGUSR2``

  :program:`supervisord` will close and reopen the main activity log
  and all child log files.

Runtime Security
----------------

The developers have done their best to assure that use of a
:program:`supervisord` process running as root cannot lead to
unintended privilege escalation.  But **caveat emptor**.  Supervisor
is not as paranoid as something like DJ Bernstein's
:term:`daemontools`, inasmuch as :program:`supervisord` allows for
arbitrary path specifications in its configuration file to which data
may be written.  Allowing arbitrary path selections can create
vulnerabilities from symlink attacks.  Be careful when specifying
paths in your configuration.  Ensure that the :program:`supervisord`
configuration file cannot be read from or written to by unprivileged
users and that all files installed by the supervisor package have
"sane" file permission protection settings.  Additionally, ensure that
your ``PYTHONPATH`` is sane and that all Python standard
library files have adequate file permission protections.

