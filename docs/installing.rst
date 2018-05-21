Installing
==========

Installation instructions depend whether the system on which
you're attempting to install Supervisor has internet access.

Installing to A System With Internet Access
-------------------------------------------

If your system has internet access, you can get Supervisor
installed in two ways:

- Using ``easy_install``, which is a feature of `setuptools
  <http://peak.telecommunity.com/DevCenter/setuptools>`_.  This is the
  preferred method of installation.

- By downloading the Supervisor package and invoking
  a command.

Internet-Installing With Setuptools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the Python interpreter you're using has Setuptools installed, and
the system has internet access, you can download and install
supervisor in one step using ``easy_install``.

.. code-block:: bash

   easy_install supervisor

Depending on the permissions of your system's Python, you might need
to be the root user to install Supervisor successfully using
``easy_install``.

Internet-Installing Without Setuptools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your system does not have setuptools installed, you will need to download
the Supervisor distribution and install it by hand.  Current and previous
Supervisor releases may be downloaded from `PyPi
<http://pypi.python.org/pypi/supervisor>`_.  After unpacking the software
archive, run ``python setup.py install``.  This requires internet access.  It
will download and install all distributions depended upon by Supervisor and
finally install Supervisor itself.

.. note::

   Depending on the permissions of your system's Python, you might
   need to be the root user to successfully invoke ``python
   setup.py install``.

Installing To A System Without Internet Access
----------------------------------------------

If the system that you want to install Supervisor to does not have
Internet access, you'll need to perform installation slightly
differently.  Since both ``easy_install`` and ``python setup.py
install`` depend on internet access to perform downloads of dependent
software, neither will work on machines without internet access until
dependencies are installed.  To install to a machine which is not
internet-connected, obtain the following dependencies on a machine
which is internet-connected:

- setuptools (latest) from `https://pypi.python.org/pypi/setuptools
  <https://pypi.python.org/pypi/setuptools>`_.

- meld3 (latest) from `https://pypi.python.org/pypi/meld3
  <https://pypi.python.org/pypi/meld3>`_.

Copy these files to removable media and put them on the target
machine.  Install each onto the target machine as per its
instructions.  This typically just means unpacking each file and
invoking ``python setup.py install`` in the unpacked directory.
Finally, run supervisor's ``python setup.py install``.

.. note::

   Depending on the permissions of your system's Python, you might
   need to be the root user to invoke ``python setup.py install``
   successfully for each package.

Installing a Distribution Package
---------------------------------

Some Linux distributions offer a version of Supervisor that is installable
through the system package manager.  These packages are made by third parties,
not the Supervisor developers, and often include distribution-specific changes
to Supervisor.

Use the package management tools of your distribution to check availability;
e.g. on Ubuntu you can run ``apt-cache show supervisor``, and on CentOS
you can run ``yum info supervisor``.

A feature of distribution packages of Supervisor is that they will usually
include integration into the service management infrastructure of the
distribution, e.g. allowing ``supervisord`` to automatically start when
the system boots.

.. note::

    Distribution packages of Supervisor can lag considerably behind the
    official Supervisor packages released to PyPI.  For example, Ubuntu
    12.04 (released April 2012) offered a package based on Supervisor 3.0a8
    (released January 2010).

.. note::

    Users reported that the distribution package of Supervisor for Ubuntu 16.04
    had different behavior than previous versions.  On Ubuntu 10.04, 12.04, and
    14.04, installing the package will configure the system to start
    ``supervisord`` when the system boots.  On Ubuntu 16.04, this was not done
    by the initial release of the package.  The package was fixed later.  See
    `Ubuntu Bug #1594740 <https://bugs.launchpad.net/ubuntu/+source/supervisor/+bug/1594740>`_
    for more information.

Installing via pip
------------------

Supervisor can be installed with ``pip install``:

.. code-block:: bash

    pip install supervisor

Creating a Configuration File
-----------------------------

Once the Supervisor installation has completed, run
``echo_supervisord_conf``.  This will print a "sample" Supervisor
configuration file to your terminal's stdout.

Once you see the file echoed to your terminal, reinvoke the command as
``echo_supervisord_conf > /etc/supervisord.conf``. This won't work if
you do not have root access.

If you don't have root access, or you'd rather not put the
:file:`supervisord.conf` file in :file:`/etc/supervisord.conf`, you
can place it in the current directory (``echo_supervisord_conf >
supervisord.conf``) and start :program:`supervisord` with the
``-c`` flag in order to specify the configuration file
location.

For example, ``supervisord -c supervisord.conf``.  Using the ``-c``
flag actually is redundant in this case, because
:program:`supervisord` searches the current directory for a
:file:`supervisord.conf` before it searches any other locations for
the file, but it will work.  See :ref:`running` for more information
about the ``-c`` flag.

Once you have a configuration file on your filesystem, you can
begin modifying it to your liking.
