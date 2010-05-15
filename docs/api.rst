XML-RPC API Documentation
=========================

.. automodule:: supervisor.rpcinterface

Status and Control
------------------

  .. autoclass:: SupervisorNamespaceRPCInterface

    .. automethod:: getAPIVersion

    .. automethod:: getSupervisorVersion

    .. automethod:: getIdentification
    
    .. automethod:: getState
    
    .. automethod:: getPID
    
    .. automethod:: readLog
    
    .. automethod:: clearLog
    
    .. automethod:: shutdown
    
    .. automethod:: restart
  
Process Control
---------------

  .. autoclass:: SupervisorNamespaceRPCInterface

    .. automethod:: getProcessInfo
    
    .. automethod:: getAllProcessInfo
    
    .. automethod:: startProcess
    
    .. automethod:: startAllProcesses
    
    .. automethod:: startProcessGroup
    
    .. automethod:: stopProcessGroup
    
    .. automethod:: sendProcessStdin
    
    .. automethod:: sendRemoteCommEvent
    
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
                    
