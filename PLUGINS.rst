Third Party Applications and Libraries
======================================

There are a number of third party applications that can be useful together
with Supervisor. This list aims to summarize them and make them easier
to find.

See README.rst for information on how to contribute to this list.
Obviously, you can always also send an e-mail to the Supervisor mailing
list to inform about missing plugins or libraries for/using Supervisor.

Dashboards and Tools for Multiple Supervisor Instances
------------------------------------------------------

These are tools that can monitor or control a number of Supervisor
instances running on different servers.

`Nodervisor <https://github.com/TAKEALOT/nodervisor>`_
    Web-based dashboard written in Node.js.

`Supervisord-Monitor <https://github.com/mlazarov/supervisord-monitor>`_
    Web-based dashboard written in PHP.

`SupervisorUI <https://github.com/luxbet/supervisorui>`_
    Another Web-based dashboard written in PHP.


Third Party Plugins and Libraries for Supervisor
------------------------------------------------

These are plugins and libraries that add new functionality to Supervisor.
These also includes various event listeners.

`superlance <http://pypi.python.org/pypi/superlance>`_
    Provides set of common eventlisteners that can be used to monitor
    and, for example, restart when it uses too much memory etc.
`mr.rubber <https://github.com/collective/mr.rubber>`_
    An event listener that makes it possible to scale the number of
    processes to the number of cores on the supervisor host.
`supervisor-wildcards <https://github.com/aleszoulek/supervisor-wildcards>`_
    Implemenents start/stop/restart commands with wildcard support for
    Supervisor.  These commands run in parallel and can be much faster
    than the built-in start/stop/restart commands.
`mr.laforge <https://github.com/fschulze/mr.laforge>`_
    Lets you easily make sure that ``supervisord`` and specific
    processes controlled by it are running from within shell and
    Python scripts. Also adds a ``kill`` command to supervisor that
    makes it possible to send arbitrary signals to child processes.
`supervisor_cache <https://github.com/mnaberez/supervisor_cache>`_
    An extension for Supervisor that provides the ability to cache
    arbitrary data directly inside a Supervisor instance as key/value
    pairs. Also serves as a reference for how to write Supervisor
    extensions.
`supervisor_twiddler <https://github.com/mnaberez/supervisor_twiddler>`_
    An RPC extension for Supervisor that allows Supervisor's
    configuration and state to be manipulated in ways that are not
    normally possible at runtime.
`supervisor-stdout <https://github.com/coderanger/supervisor-stdout>`_
    An event listener that sends process output to supervisord's stdout.
`supervisor-serialrestart <https://github.com/native2k/supervisor-serialrestart>`_
    Adds a ``serialrestart`` command to ``supervisorctl`` that restarts
    processes one after another rather than all at once.


Libraries that integrate Third Party Applications with Supervisor
-----------------------------------------------------------------

These are libraries and plugins that makes it easier to use Supervisor
with third party applications:

`django-supervisor <http://pypi.python.org/pypi/django-supervisor/>`_
    Easy integration between djangocl and supervisord.
`collective.recipe.supervisor <http://pypi.python.org/pypi/collective.recipe.supervisor>`_
    A buildout recipe to install supervisor.
`puppet-module-supervisor <https://github.com/plathrop/puppet-module-supervisor>`_
    Puppet module for configuring the supervisor daemon tool.
`ngx_supervisord <https://github.com/FRiCKLE/ngx_supervisord>`_
    An nginx module providing API to communicate with supervisord and
    manage (start/stop) backends on-demand.
`Supervisord-Nagios-Plugin <https://github.com/Level-Up/Supervisord-Nagios-Plugin>`_
    A Nagios/Icinga plugin written in Python to monitor individual supervisord processes.
`nagios-supervisord-processes <https://github.com/blablacar/nagios-supervisord-processes>`_
    A Nagios/Icinga plugin written in PHP to monitor individual supervisord processes.
`php-supervisor-event <https://github.com/mtdowling/php-supervisor-event>`_
    PHP classes for interacting with Supervisor event notifications.
`PHP5 Supervisor wrapper <https://github.com/yzalis/Supervisor>`_
    PHP 5 library to manage Supervisor instances as object.
`Symfony2 SupervisorBundle <https://github.com/yzalis/SupervisorBundle>`_
    Provide full integration of Supervisor multiple servers management into Symfony2 project.
`supervisord-php-client <https://github.com/mondalaci/supervisord-php-client>`_
    PHP client for the supervisord XML-RPC interface.
`sd-supervisord <https://github.com/robcowie/sd-supervisord>`_
    `Server Density <http://www.serverdensity.com>`_ plugin for
    supervisor.
`node-supervisord <https://github.com/crcn/node-supervisord>`_
    Node.js client for Supervisor's XML-RPC interface.
`node-supervisord-eventlistener <https://github.com/sugendran/node-supervisord-eventlistener>`_
    Node.js implementation of an event listener for Supervisor.
`ruby-supervisor <https://github.com/schmurfy/ruby-supervisor>`_
    Ruby client library for Supervisor's XML-RPC interface.
`Sulphite <https://github.com/jib/sulphite>`_
    Sends supervisord events to `Graphite <https://github.com/graphite-project/graphite-web>`_.
`supervisord.tmbundle <https://github.com/countergram/supervisord.tmbundle>`_
    `TextMate <http://macromates.com/>`_ bundle for supervisord.conf.
`capistrano-supervisord <https://github.com/yyuu/capistrano-supervisord>`_
    `Capistrano <https://github.com/capistrano/capistrano>`_ recipe to deploy supervisord based services.
`chef-supervisor <https://github.com/opscode-cookbooks/supervisor>`_
    `Chef <http://www.opscode.com/chef/>`_ cookbook install and configure supervisord.
