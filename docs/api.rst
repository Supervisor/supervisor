.. _xml_rpc:

XML-RPC API Documentation
=========================

To use the XML-RPC interface, first make sure you have configured the interface
factory properly by setting the default factory. See :ref:`rpcinterface_factories`.

Then you can connect to supervisor's HTTP port
with any XML-RPC client library and run commands against it.  An
example of doing this using Python's ``xmlrpclib`` client library
is as follows.

.. code-block:: python

    import xmlrpclib
    server = xmlrpclib.Server('http://localhost:9001/RPC2')

You may call methods against :program:`supervisord` and its
subprocesses by using the ``supervisor`` namespace.  An example is
provided below.

.. code-block:: python

    server.supervisor.getState()

You can get a list of methods supported by the
:program:`supervisord` XML-RPC interface by using the XML-RPC
``system.listMethods`` API:

.. code-block:: python

    server.system.listMethods()

You can see help on a method by using the ``system.methodHelp`` API
against the method:

.. code-block:: python

    server.system.methodHelp('supervisor.shutdown')

The :program:`supervisord` XML-RPC interface also supports the
`XML-RPC multicall API
<http://web.archive.org/web/20060824100531/http://www.xmlrpc.com/discuss/msgReader$1208>`_.

You can extend :program:`supervisord` functionality with new XML-RPC
API methods by adding new top-level RPC interfaces as necessary.
See :ref:`rpcinterface_factories`.

.. note::

  Any XML-RPC method call may result in a fault response.  This includes errors caused
  by the client such as bad arguments, and any errors that make :program:`supervisord`
  unable to fulfill the request.  Many XML-RPC client programs will raise an exception
  when a fault response is encountered.

.. automodule:: supervisor.rpcinterface

Status and Control
------------------

  .. autoclass:: SupervisorNamespaceRPCInterface

    .. automethod:: getAPIVersion

        This API is versioned separately from Supervisor itself. The API version
        returned by ``getAPIVersion`` only changes when the API changes. Its purpose
        is to help the client identify with which version of the Supervisor API it
        is communicating.

        When writing software that communicates with this API, it is highly
        recommended that you first test the API version for compatibility before
        making method calls.

        .. note::

          The ``getAPIVersion`` method replaces ``getVersion`` found in Supervisor
          versions prior to 3.0a1. It is aliased for compatibility but getVersion()
          is deprecated and support will be dropped from Supervisor in a future
          version.

    .. automethod:: getSupervisorVersion

    .. automethod:: getIdentification

        This method allows the client to identify with which Supervisor
        instance it is communicating in the case of environments where
        multiple Supervisors may be running.

        The identification is a string that must be set in Supervisor’s
        configuration file. This method simply returns that value back to the
        client.

    .. automethod:: getState

        This is an internal value maintained by Supervisor that determines what
        Supervisor believes to be its current operational state.

        Some method calls can alter the current state of the Supervisor. For
        example, calling the method supervisor.shutdown() while the station is
        in the RUNNING state places the Supervisor in the SHUTDOWN state while
        it is shutting down.

        The supervisor.getState() method provides a means for the client to check
        Supervisor's state, both for informational purposes and to ensure that the
        methods it intends to call will be permitted.

        The return value is a struct:

        .. code-block:: python

            {'statecode': 1,
             'statename': 'RUNNING'}

        The possible return values are:

        +---------+----------+----------------------------------------------+
        |statecode|statename |Description                                   |
        +=========+==========+==============================================+
        | 2       |FATAL     |Supervisor has experienced a serious error.   |
        +---------+----------+----------------------------------------------+
        | 1       |RUNNING   |Supervisor is working normally.               |
        +---------+----------+----------------------------------------------+
        | 0       |RESTARTING|Supervisor is in the process of restarting.   |
        +---------+----------+----------------------------------------------+
        | -1      |SHUTDOWN  |Supervisor is in the process of shutting down.|
        +---------+----------+----------------------------------------------+

        The ``FATAL`` state reports unrecoverable errors, such as internal
        errors inside Supervisor or system runaway conditions. Once set to
        ``FATAL``, the Supervisor can never return to any other state without
        being restarted.

        In the ``FATAL`` state, all future methods except
        supervisor.shutdown() and supervisor.restart() will automatically fail
        without being called and the fault ``FATAL_STATE`` will be raised.

        In the ``SHUTDOWN`` or ``RESTARTING`` states, all method calls are
        ignored and their possible return values are undefined.

    .. automethod:: getPID

    .. automethod:: readLog

        It can either return the entire log, a number of characters from the
        tail of the log, or a slice of the log specified by the offset and
        length parameters:

        +--------+---------+------------------------------------------------+
        | Offset | Length  | Behavior of ``readProcessLog``                 |
        +========+=========+================================================+
        |Negative|Not Zero | Bad arguments. This will raise the fault       |
        |        |         | ``BAD_ARGUMENTS``.                             |
        +--------+---------+------------------------------------------------+
        |Negative|Zero     | This will return the tail of the log, or offset|
        |        |         | number of characters from the end of the log.  |
        |        |         | For example, if ``offset`` = -4 and ``length`` |
        |        |         | = 0, then the last four characters will be     |
        |        |         | returned from the end of the log.              |
        +--------+---------+------------------------------------------------+
        |Zero or |Negative | Bad arguments. This will raise the fault       |
        |Positive|         | ``BAD_ARGUMENTS``.                             |
        +--------+---------+------------------------------------------------+
        |Zero or |Zero     | All characters will be returned from the       |
        |Positive|         | ``offset`` specified.                          |
        +--------+---------+------------------------------------------------+
        |Zero or |Positive | A number of characters length will be returned |
        |Positive|         | from the ``offset``.                           |
        +--------+---------+------------------------------------------------+

        If the log is empty and the entire log is requested, an empty string
        is returned.

        If either offset or length is out of range, the fault
        ``BAD_ARGUMENTS`` will be returned.

        If the log cannot be read, this method will raise either the
        ``NO_FILE`` error if the file does not exist or the ``FAILED`` error
        if any other problem was encountered.

        .. note::

          The readLog() method replaces readMainLog() found in Supervisor
          versions prior to 2.1. It is aliased for compatibility but
          readMainLog() is deprecated and support will be dropped from
          Supervisor in a future version.


    .. automethod:: clearLog

        If the log cannot be cleared because the log file does not exist, the
        fault ``NO_FILE`` will be raised. If the log cannot be cleared for any
        other reason, the fault ``FAILED`` will be raised.

    .. automethod:: shutdown

        This method shuts down the Supervisor daemon. If any processes are running,
        they are automatically killed without warning.

        Unlike most other methods, if Supervisor is in the ``FATAL`` state,
        this method will still function.

    .. automethod:: restart

        This method soft restarts the Supervisor daemon. If any processes are
        running, they are automatically killed without warning. Note that the
        actual UNIX process for Supervisor cannot restart; only Supervisor’s
        main program loop. This has the effect of resetting the internal
        states of Supervisor.

        Unlike most other methods, if Supervisor is in the ``FATAL`` state,
        this method will still function.


Process Control
---------------

  .. autoclass:: SupervisorNamespaceRPCInterface

    .. automethod:: getProcessInfo

        The return value is a struct:

        .. code-block:: python

            {'name':           'process name',
             'group':          'group name',
             'description':    'pid 18806, uptime 0:03:12'
             'start':          1200361776,
             'stop':           0,
             'now':            1200361812,
             'state':          1,
             'statename':      'RUNNING',
             'spawnerr':       '',
             'exitstatus':     0,
             'logfile':        '/path/to/stdout-log', # deprecated, b/c only
             'stdout_logfile': '/path/to/stdout-log',
             'stderr_logfile': '/path/to/stderr-log',
             'pid':            1}

        .. describe:: name

            Name of the process

        .. describe:: group

            Name of the process' group

        .. describe:: description

            If process state is running description's value is process_id
            and uptime. Example "pid 18806, uptime 0:03:12 ".
            If process state is stopped description's value is stop time.
            Example:"Jun 5 03:16 PM ".

        .. describe:: start

            UNIX timestamp of when the process was started

        .. describe:: stop

            UNIX timestamp of when the process last ended, or 0 if the process
            has never been stopped.

        .. describe:: now

            UNIX timestamp of the current time, which can be used to calculate
            process up-time.

        .. describe:: state

            State code, see :ref:`process_states`.

        .. describe:: statename

            String description of `state`, see :ref:`process_states`.

        .. describe:: logfile

            Deprecated alias for ``stdout_logfile``.  This is provided only
            for compatibility with clients written for Supervisor 2.x and
            may be removed in the future.  Use ``stdout_logfile`` instead.

        .. describe:: stdout_logfile

            Absolute path and filename to the STDOUT logfile

        .. describe:: stderr_logfile

            Absolute path and filename to the STDOUT logfile

        .. describe:: spawnerr

            Description of error that occurred during spawn, or empty string
            if none.

        .. describe:: exitstatus

            Exit status (errorlevel) of process, or 0 if the process is still
            running.

        .. describe:: pid

            UNIX process ID (PID) of the process, or 0 if the process is not
            running.


    .. automethod:: getAllProcessInfo

        Each element contains a struct, and this struct contains the exact
        same elements as the struct returned by ``getProcessInfo``. If the process
        table is empty, an empty array is returned.

    .. automethod:: startProcess

    .. automethod:: startAllProcesses

    .. automethod:: startProcessGroup

    .. automethod:: stopProcess

    .. automethod:: stopProcessGroup

    .. automethod:: stopAllProcesses

    .. automethod:: signalProcess

    .. automethod:: signalProcessGroup

    .. automethod:: signalAllProcesses

    .. automethod:: sendProcessStdin

    .. automethod:: sendRemoteCommEvent

    .. automethod:: reloadConfig

    .. automethod:: addProcessGroup

    .. automethod:: removeProcessGroup

Process Logging
---------------

  .. autoclass:: SupervisorNamespaceRPCInterface

    .. automethod:: readProcessStdoutLog

    .. automethod:: readProcessStderrLog

    .. automethod:: tailProcessStdoutLog

    .. automethod:: tailProcessStderrLog

    .. automethod:: clearProcessLogs

    .. automethod:: clearAllProcessLogs


.. automodule:: supervisor.xmlrpc

System Methods
--------------

  .. autoclass:: SystemNamespaceRPCInterface

    .. automethod:: listMethods

    .. automethod:: methodHelp

    .. automethod:: methodSignature

    .. automethod:: multicall
