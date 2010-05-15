Frequently Asked Questions
==========================

Q
  My program never starts and supervisor doesn't indicate any error?

A 
  Make sure the ``x`` bit is set on the executable file you're using in
  the ``command=`` line of your program section.

Q
  I am a software author and I want my program to behave differently
  when it's running under :program:`supervisord`.  How can I tell if
  my program is running under :program:`supervisord`?

A
  Supervisor and its subprocesses share an environment variable
  :envvar:`SUPERVISOR_ENABLED`.  When your program is run under
  :program:`supervisord`, it can check for the presence of this
  environment variable to determine whether it is running as a
  :program:`supervisord` subprocess.

Q
  My command works fine when I invoke it by hand from a shell prompt,
  but when I use the same command line in a supervisor program
  ``command=`` section, the program fails mysteriously.  Why?

A
  This may be due to your process' dependence on environment variable
  settings.  See :ref:`subprocess_environment`.

Q
  How can I make Supervisor restart a process that's using "too much"
  memory automatically?

A
  The :term:`superlance` package contains a console script that can be
  used as a Supervisor event listener named ``memmon`` which helps
  with this task.  It works on Linux and Mac OS X.
