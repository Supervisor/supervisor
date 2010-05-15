Extending Supervisor's XML-RPC API
==================================

Supervisor can be extended with new XML-RPC APIs.  Several third-party
plugins already exist that can be wired into your Supervisor
configuration.  You may additionally write your own.  Extensible
XML-RPC interfaces is an advanced feature, introduced in version 3.0.
You needn't understand it unless you wish to use an existing
third-party RPC interface plugin or if you wish to write your own RPC
interface plugin.

.. _rpcinterface_factories:

Configuring XML-RPC Interface Factories
---------------------------------------

An additional RPC interface is configured into a supervisor
installation by adding a ``[rpcinterface:x]`` section in the
Supervisor configuration file.

In the sample config file, there is a section which is named
``[rpcinterface:supervisor]``.  By default it looks like this:

.. code-block:: ini
    
   [rpcinterface:supervisor]
   supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

This section *must* remain in the configuration for the standard setup
of supervisor to work properly.  If you don't want supervisor to do
anything it doesn't already do out of the box, this is all you need to
know about this type of section.

However, if you wish to add additional XML-RPC interface namespaces to
a configuration of supervisor, you may add additional
``[rpcinterface:foo]`` sections, where "foo" represents the namespace
of the interface (from the web root), and the value named by
``supervisor.rpcinterface_factory`` is a factory callable written in
Python which should have a function signature that accepts a single
positional argument ``supervisord`` and as many keyword arguments as
required to perform configuration.  Any key/value pairs defined within
the ``rpcinterface:foo`` section will be passed as keyword arguments
to the factory.  Here's an example of a factory function, created in
the package ``my.package``.

.. code-block:: python

   def make_another_rpcinterface(supervisord, **config):
       retries = int(config.get('retries', 0))
       another_rpc_interface = AnotherRPCInterface(supervisord, retries)
       return another_rpc_interface

And a section in the config file meant to configure it.

.. code-block:: ini

   [rpcinterface:another]
   supervisor.rpcinterface_factory = my.package:make_another_rpcinterface
   retries = 1

