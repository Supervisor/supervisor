Supervisor
==========

Supervisor is a client/server system that allows its users to
control a number of processes on UNIX-like operating systems.

Supported Platforms
-------------------

Supervisor has been tested and is known to run on Linux (Ubuntu), Mac OS X
(10.4, 10.5, 10.6), and Solaris (10 for Intel) and FreeBSD 6.1.  It will
likely work fine on most UNIX systems.

Supervisor will not run at all under any version of Windows.

**Supervisor does not work on Python 3.**  This is the master branch,
which has work-in-progress support for Python 3.  Supervisor is very likely
to crash, cause subprocesses to hang, or otherwise behave unexpectedly
when run on Python 3.  See
`issues running Supervisor on Python 3 <https://github.com/Supervisor/supervisor/labels/python%203>`_.
It may also have regressions on Python 2 as a result of attempts to
add Python 3 support.  Help from developers with Python 3 porting
experience is needed.  **Do not use this branch on any production system.**

Supervisor 4.0 (unreleased) is planned to work under Python 3 version 3.4
or greater and on Python 2 version 2.7.  See note above about the
current state of Python 3 support.

Documentation
-------------

You can view the current Supervisor documentation online `in HTML format
<http://supervisord.org/>`_ .  This is where you should go for detailed
installation and configuration documentation.

Mailing list, Reporting Bugs, and Viewing the Source Repository
---------------------------------------------------------------

You may subscribe to the `Supervisor-users mailing list
<http://lists.supervisord.org/mailman/listinfo/supervisor-users>`_.

Please report bugs in the `Github issue tracker
<https://github.com/Supervisor/supervisor/issues>`_.

You can view the source repository for supervisor via
`https://github.com/Supervisor/supervisor
<https://github.com/Supervisor/supervisor>`_.

Contributing
------------

If you'd like to contribute to supervisor directly, please contact the
`Supervisor-users mailing list
<http://lists.supervisord.org/mailman/listinfo/supervisor-users>`_.

