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

If your system does not have setuptools installed, you will need to
download the Supervisor distribution and install it by hand.  Current
and previous Supervisor releases may be downloaded from
`http://supervisord.org/dist/ <http://supervisord.org/dist/>`_.  After
unpacking the software archive, run ``python setup.py install``.  This
requires internet access.  It will download and install all
distributions depended upon by Supervisor and finally install
Supervisor itself.

.. note::

   Depending on the permissions of your system's Python, you might
   need to be the root user to sucessfully invoke ``python
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

- setuptools (latest) from `http://pypi.python.org/pypi/setuptools
  <http://pypi.python.org/pypi/setuptools>`_.

- meld3 (latest) from `http://www.plope.com/software/meld3/
  <http://www.plope.com/software/meld3/>`_.

- elementtree (latest) from `http://effbot.org/downloads#elementtree
  <http://effbot.org/downloads#elementtree>`_.
    
Copy these files to removable media and put them on the target
machine.  Install each onto the target machine as per its
instructions.  This typically just means unpacking each file and
invoking ``python setup.py install`` in the unpacked directory.
Finally, run supervisor's ``python setup.py install``.

.. note::
    
   Depending on the permissions of your system's Python, you might
   need to be the root user to invoke ``python setup.py install``
   sucessfully for each package.

Creating a Configuration File
-----------------------------

Once the Supervisor installation has completed, run
``echo_supervisord_conf``.  This will print a "sample" Supervisor
configuration file to your terminal's stdout.

Once you see the file echoed to your terminal, reinvoke the command as
``echo_supervisord_conf > /etc/supervisord.conf``. This won't work if
you do not have root access.

If you don't have root access, or you'd rather not put the
:file:`supervisord.conf` file in :file:`/etc/supervisord.conf``, you
can place it in the current directory (``echo_supervisord_conf >
supervisord.conf``) and start :program:`supervisord` with the
``-c`` flag in order to specify the configuration file
location.

For example, ``supervisord -c supervisord.conf``.  Using the ``-c``
flag actually is redundant in this case, because
:program:`supervisord` searches the current directory for a
:file:`supervisord.conf` before it searches any other locations for
the file, but it will work.  See :ref:`running_chapter` for more
information about the ``-c`` flag.

Once you have a configuration file on your filesystem, you can
begin modifying it to your liking.
