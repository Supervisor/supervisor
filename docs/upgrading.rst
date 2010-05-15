Upgrading Supervisor 2 to 3
===========================

The following is true when upgrading an installation from Supervisor
2.X to Supervisor 3.X:

#.  In ``[program:x]`` sections, the keys ``logfile``,
    ``logfile_backups``, ``logfile_maxbytes``, ``log_stderr`` and
    ``log_stdout`` are no longer valid.  Supervisor2 logged both
    stderr and stdout to a single log file.  Supervisor 3 logs stderr
    and stdout to separate log files.  You'll need to rename
    ``logfile`` to ``stdout_logfile``, ``logfile_backups`` to
    ``stdout_logfile_backups``, and ``logfile_maxbytes`` to
    ``stdout_logfile_maxbytes`` at the very least to preserve your
    configuration.  If you created program sections where
    ``log_stderr`` was true, to preserve the behavior of sending
    stderr output to the stdout log, use the ``redirect_stderr``
    boolean in the program section instead.

#.  The supervisor configuration file must include the following
    section verbatim for the XML-RPC interface (and thus the web
    interface and :program:`supervisorctl`) to work properly:

    .. code-block:: ini

       [rpcinterface:supervisor]
       supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

#.  The semantics of the ``autorestart`` parameter within
    ``[program:x]`` sections has changed.  This parameter used to
    accept only ``true`` or ``false``.  It now accepts an additional
    value, ``unexpected``, which indicates that the process should
    restart from the ``EXITED`` state only if its exit code does not
    match any of those represented by the ``exitcode`` parameter in
    the process' configuration (implying a process crash).  In
    addition, the default for ``autorestart`` is now ``unexpected``
    (it used to be ``true``, which meant restart unconditionally).

#.  We now allow :program:`supervisord` to listen on both a UNIX
    domain socket and an inet socket instead of making listening on
    one mutually exclusive with listening on the other.  As a result,
    the options ``http_port``, ``http_username``, ``http_password``,
    ``sockchmod`` and ``sockchown`` are no longer part of
    the ``[supervisord]`` section configuration. These have been
    supplanted by two other sections: ``[unix_http_server]`` and
    ``[inet_http_server]``.  You'll need to insert one or the other
    (depending on whether you want to listen on a UNIX domain socket
    or a TCP socket respectively) or both into your
    :file:`supervisord.conf` file.  These sections have their own
    options (where applicable) for ``port``, ``username``,
    ``password``, ``chmod``, and ``chown``.

#.  All supervisord command-line options related to ``http_port``,
    ``http_username``, ``http_password``, ``sockchmod`` and
    ``sockchown`` have been removed (see above point for rationale).

#. The option that used to be ``sockchown`` within the
   ``[supervisord]`` section (and is now named ``chown`` within the
   ``[unix_http_server]`` section) used to accept a dot-separated
   (``user.group``) value.  The separator now must be a
   colon, e.g. ``user:group``.  Unices allow for dots in
   usernames, so this change is a bugfix.
