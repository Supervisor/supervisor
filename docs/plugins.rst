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

`cesi <https://github.com/Gamegos/cesi>`_
    Web-based dashboard written in Python.

`Django-Dashvisor <https://github.com/aleszoulek/django-dashvisor>`_
    Web-based dashboard written in Python.  Requires Django 1.3 or 1.4.

`Nodervisor <https://github.com/TAKEALOT/nodervisor>`_
    Web-based dashboard written in Node.js.

`Supervisord-Monitor <https://github.com/mlazarov/supervisord-monitor>`_
    Web-based dashboard written in PHP.

`SupervisorUI <https://github.com/luxbet/supervisorui>`_
    Another Web-based dashboard written in PHP.

`supervisorclusterctl <https://github.com/RobWin/supervisorclusterctl>`_
    Command line tool for controlling multiple Supervisor instances
    using Ansible.

`suponoff <https://github.com/GambitResearch/suponoff>`_
    Web-based dashboard written in Python 3.  Requires Django 1.7 or later.

`Supvisors <https://github.com/julien6387/supvisors>`_
    Designed for distributed applications, written in Python 2.7. Includes an extended XML-RPC API and a Web-based dashboard.

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
    Implements start/stop/restart commands with wildcard support for
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
`supervisor-quick <http://lxyu.github.io/supervisor-quick/>`_
    Adds ``quickstart``, ``quickstop``, and ``quickrestart`` commands to
    ``supervisorctl`` that can be faster than the built-in commands.  It
    works by using the non-blocking mode of the XML-RPC methods and then
    polling ``supervisord``.  The built-in commands use the blocking mode,
    which can be slower due to ``supervisord`` implementation details.
`supervisor-logging <https://github.com/infoxchange/supervisor-logging>`_
    An event listener that sends process log events to an external
    Syslog instance (e.g. Logstash).
`supervisor-logstash-notifier <https://github.com/dohop/supervisor-logstash-notifier>`_
    An event listener plugin to stream state events to a Logstash instance.
`supervisor_cgroups <https://github.com/htch/supervisor_cgroups>`_
    An event listener that enables tying Supervisor processes to a cgroup
    hierarchy.  It is intended to be used as a replacement for
    `cgrules.conf <http://linux.die.net/man/5/cgrules.conf>`_.
`supervisor_checks <https://github.com/vovanec/supervisor_checks>`_
    Framework to build health checks for Supervisor-based services. Health
    check applications are supposed to run as event listeners in Supervisor
    environment. On check failure Supervisor will attempt to restart
    monitored process.

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
`puppet-supervisord <https://github.com/ajcrowe/puppet-supervisord>`_
    Puppet module to manage the supervisord process control system.
`ngx_supervisord <https://github.com/FRiCKLE/ngx_supervisord>`_
    An nginx module providing API to communicate with supervisord and
    manage (start/stop) backends on-demand.
`Supervisord-Nagios-Plugin <https://github.com/Level-Up/Supervisord-Nagios-Plugin>`_
    A Nagios/Icinga plugin written in Python to monitor individual supervisord processes.
`nagios-supervisord-processes <https://github.com/blablacar/nagios-supervisord-processes>`_
    A Nagios/Icinga plugin written in PHP to monitor individual supervisord processes.
`supervisord-nagios <https://github.com/3dna/supervisord-nagios>`_
    A plugin for supervisorctl to allow one to perform nagios-style checks
    against supervisord-managed processes.
`php-supervisor-event <https://github.com/mtdowling/php-supervisor-event>`_
    PHP classes for interacting with Supervisor event notifications.
`PHP5 Supervisor wrapper <https://github.com/yzalis/Supervisor>`_
    PHP 5 library to manage Supervisor instances as object.
`Symfony2 SupervisorBundle <https://github.com/yzalis/SupervisorBundle>`_
    Provide full integration of Supervisor multiple servers management into Symfony2 project.
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
`capistrano-supervisor <https://github.com/glooby/capistrano-supervisor>`_
    Another package to control supervisord from `Capistrano <https://github.com/capistrano/capistrano>`_.
`chef-supervisor <https://github.com/opscode-cookbooks/supervisor>`_
    `Chef <http://www.opscode.com/chef/>`_ cookbook install and configure supervisord.
`SupervisorPHP <http://supervisorphp.com>`_
    Complete Supervisor suite in PHP: Client using XML-RPC interface, event listener and configuration builder implementation, console application and monitor UI.
`Supervisord-Client <http://search.cpan.org/~skaufman/Supervisord-Client>`_
    Perl client for the supervisord XML-RPC interface.
`supervisord4j <https://github.com/satifanie/supervisord4j>`_
    Java client for Supervisor's XML-RPC interface.
`Supermann <https://github.com/borntyping/supermann>`_
    Supermann monitors processes running under Supervisor and sends metrics
    to `Riemann <http://riemann.io/>`_.
`gulp-supervisor <https://github.com/leny/gulp-supervisor>`_
    Run Supervisor as a `Gulp <http://gulpjs.com/>`_ task.
`Yeebase.Supervisor <https://github.com/yeebase/Yeebase.Supervisor>`_
    Control and monitor Supervisor from a TYPO3 Flow application.
`dokku-supervisord <https://github.com/statianzo/dokku-supervisord>`_
    `Dokku <https://github.com/progrium/dokku>`_ plugin that injects ``supervisord`` to run
    applications.
`dokku-logging-supervisord <https://github.com/sehrope/dokku-logging-supervisord>`_
    `Dokku <https://github.com/progrium/dokku>`_ plugin that injects ``supervisord`` to run
    applications.  It also redirects ``stdout`` and ``stderr`` from processes to log files
    (rather than the Docker default per-container JSON files).
`superslacker <https://github.com/MTSolutions/superslacker>`_
    Send Supervisor event notifications to `Slack <https://slack.com>`_.
`supervisor-alert <https://github.com/rahiel/supervisor-alert>`_
    Send event notifications over `Telegram <https://telegram.org>`_ or to an
    arbitrary command.
