Supervisor: A Process Control System
====================================

Overview
--------

``supervisor`` is a client/server system that allows its users to
monitor and control a number of processes on UNIX-like operating
systems.

It shares some of the same goals of programs like :term:`launchd`,
:term:`daemontools`, and :term:`runit`. Unlike some of these programs,
it is not meant to be run as a substitute for ``init`` as "process id
1". Instead it is meant to be used to control processes related to a
project or a customer, and is meant to start like any other program at
boot time.

Features
--------

Simple

  Supervisor is configured through a simple INI-style config file
  that’s easy to learn. It provides many per-process options that make
  your life easier like restarting failed processes and automatic log
  rotation.

Centralized

  Supervisor provides you with one place to start, stop, and monitor
  your processes. Processes can be controlled individually or in
  groups. You can configure Supervisor to provide a local or remote
  command line and web interface.

Efficient

  Supervisor starts its subprocesses via fork/exec and subprocesses
  don’t daemonize. The operating system signals Supervisor immediately
  when a process terminates, unlike some solutions that rely on
  troublesome PID files and periodic polling to restart failed
  processes.

Extensible

  Supervisor has a simple event notification protocol that programs
  written in any language can use to monitor it, and an XML-RPC
  interface for control. It is also built with extension points that
  can be leveraged by Python developers.

Compatible

  Supervisor works on just about everything except for Windows. It is
  tested and supported on Linux, Mac OS X, Solaris, and FreeBSD. It is
  written entirely in Python, so installation does not require a C
  compiler.

Proven

  While Supervisor is very actively developed today, it is not new
  software. Supervisor has been around for years and is already in use
  on many servers.

Narrative Documentation
-----------------------

.. toctree::
   :maxdepth: 2

   introduction.rst
   installing.rst
   running.rst
   configuration.rst
   subprocess.rst

API Documentation
-----------------

.. toctree::
   :maxdepth: 2

   api.rst

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
