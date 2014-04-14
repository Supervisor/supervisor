Supervisor: A Process Control System
====================================

Supervisor is a client/server system that allows its users to monitor
and control a number of processes on UNIX-like operating systems.

It shares some of the same goals of programs like :term:`launchd`,
:term:`daemontools`, and :term:`runit`. Unlike some of these programs,
it is not meant to be run as a substitute for ``init`` as "process id
1". Instead it is meant to be used to control processes related to a
project or a customer, and is meant to start like any other program at
boot time.

Narrative Documentation
-----------------------

.. toctree::
   :maxdepth: 2

   introduction.rst
   installing.rst
   running.rst
   configuration.rst
   subprocess.rst
   logging.rst
   events.rst
   xmlrpc.rst
   upgrading.rst
   faq.rst
   development.rst
   glossary.rst

API Documentation
-----------------

.. toctree::
   :maxdepth: 2

   api.rst

Plugins
-------

.. toctree::
   :maxdepth: 2

   plugins.rst

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
