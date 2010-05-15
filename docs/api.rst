XML-RPC API Documentation
=========================

Status and Control
------------------

.. automodule:: supervisor.rpcinterface

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

.. automodule:: supervisor.rpcinterface

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

.. automodule:: supervisor.rpcinterface

  .. autoclass:: SupervisorNamespaceRPCInterface

    .. automethod:: readProcessStdoutLog

    .. automethod:: readProcessStderrLog

    .. automethod:: tailProcessStdoutLog

    .. automethod:: tailProcessStderrLog

    .. automethod:: clearProcessLogs

    .. automethod:: clearAllProcessLogs


System Methods
--------------

.. automodule:: supervisor.xmlrpc

  .. autoclass:: SystemNamespaceRPCInterface

    .. automethod:: listMethods

    .. automethod:: methodHelp

    .. automethod:: methodSignature

    .. automethod:: multicall
                    
