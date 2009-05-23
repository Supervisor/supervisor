##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the BSD-like license at
# http://www.repoze.org/LICENSE.txt.  A copy of the license should accompany
# this distribution.  THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL
# EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND
# FITNESS FOR A PARTICULAR PURPOSE
#
##############################################################################

import ConfigParser
import socket
import getopt
import os
import sys
import tempfile
import errno
import signal
import re
import xmlrpclib
import pwd
import grp
import resource
import stat
import pkg_resources
import select
import glob

from fcntl import fcntl
from fcntl import F_SETFL, F_GETFL

from medusa import asyncore_25 as asyncore

from supervisor.datatypes import boolean
from supervisor.datatypes import integer
from supervisor.datatypes import name_to_uid
from supervisor.datatypes import gid_for_uid
from supervisor.datatypes import existing_dirpath
from supervisor.datatypes import byte_size
from supervisor.datatypes import signal_number
from supervisor.datatypes import list_of_exitcodes
from supervisor.datatypes import dict_of_key_value_pairs
from supervisor.datatypes import logfile_name
from supervisor.datatypes import list_of_strings
from supervisor.datatypes import octal_type
from supervisor.datatypes import existing_directory
from supervisor.datatypes import logging_level
from supervisor.datatypes import colon_separated_user_group
from supervisor.datatypes import inet_address
from supervisor.datatypes import InetStreamSocketConfig
from supervisor.datatypes import UnixStreamSocketConfig
from supervisor.datatypes import url
from supervisor.datatypes import Automatic
from supervisor.datatypes import auto_restart
from supervisor.datatypes import profile_options
from supervisor.datatypes import set_here

from supervisor.socket_manager import SocketManager

from supervisor import loggers
from supervisor import states
from supervisor import xmlrpc

mydir = os.path.abspath(os.path.dirname(__file__))
version_txt = os.path.join(mydir, 'version.txt')
VERSION = open(version_txt).read().strip()

def normalize_path(v):
    return os.path.normpath(os.path.abspath(os.path.expanduser(v)))

class Dummy:
    pass

class Options:
    stderr = sys.stderr
    stdout = sys.stdout
    exit = sys.exit

    uid = gid = None

    progname = sys.argv[0]
    configfile = None
    schemadir = None
    configroot = None
    here = None

    # Class variable deciding whether positional arguments are allowed.
    # If you want positional arguments, set this to 1 in your subclass.
    positional_args_allowed = 0

    def __init__(self):
        self.names_list = []
        self.short_options = []
        self.long_options = []
        self.options_map = {}
        self.default_map = {}
        self.required_map = {}
        self.environ_map = {}
        self.attr_priorities = {}
        self.add(None, None, "h", "help", self.help)
        self.add("configfile", None, "c:", "configuration=")

    def default_configfile(self):
        """Return the name of the found config file or raise. """
        paths = ['supervisord.conf', 'etc/supervisord.conf',
                 '/etc/supervisord.conf']
        config = None
        for path in paths:
            if os.path.exists(path):
                config = path
                break
        if config is None:
            self.usage('No config file found at default paths (%s); '
                       'use the -c option to specify a config file '
                       'at a different path' % ', '.join(paths))
        return config

    def help(self, dummy):
        """Print a long help message to stdout and exit(0).

        Occurrences of "%s" in are replaced by self.progname.
        """
        help = self.doc
        if help.find("%s") > 0:
            help = help.replace("%s", self.progname)
        print help,
        self.exit(0)

    def usage(self, msg):
        """Print a brief error message to stderr and exit(2)."""
        self.stderr.write("Error: %s\n" % str(msg))
        self.stderr.write("For help, use %s -h\n" % self.progname)
        self.exit(2)

    def add(self,
            name=None,                  # attribute name on self
            confname=None,              # dotted config path name
            short=None,                 # short option name
            long=None,                  # long option name
            handler=None,               # handler (defaults to string)
            default=None,               # default value
            required=None,              # message if not provided
            flag=None,                  # if not None, flag value
            env=None,                   # if not None, environment variable
            ):
        """Add information about a configuration option.

        This can take several forms:

        add(name, confname)
            Configuration option 'confname' maps to attribute 'name'
        add(name, None, short, long)
            Command line option '-short' or '--long' maps to 'name'
        add(None, None, short, long, handler)
            Command line option calls handler
        add(name, None, short, long, handler)
            Assign handler return value to attribute 'name'

        In addition, one of the following keyword arguments may be given:

        default=...  -- if not None, the default value
        required=... -- if nonempty, an error message if no value provided
        flag=...     -- if not None, flag value for command line option
        env=...      -- if not None, name of environment variable that
                        overrides the configuration file or default
        """

        if flag is not None:
            if handler is not None:
                raise ValueError, "use at most one of flag= and handler="
            if not long and not short:
                raise ValueError, "flag= requires a command line flag"
            if short and short.endswith(":"):
                raise ValueError, "flag= requires a command line flag"
            if long and long.endswith("="):
                raise ValueError, "flag= requires a command line flag"
            handler = lambda arg, flag=flag: flag

        if short and long:
            if short.endswith(":") != long.endswith("="):
                raise ValueError, "inconsistent short/long options: %r %r" % (
                    short, long)

        if short:
            if short[0] == "-":
                raise ValueError, "short option should not start with '-'"
            key, rest = short[:1], short[1:]
            if rest not in ("", ":"):
                raise ValueError, "short option should be 'x' or 'x:'"
            key = "-" + key
            if self.options_map.has_key(key):
                raise ValueError, "duplicate short option key '%s'" % key
            self.options_map[key] = (name, handler)
            self.short_options.append(short)

        if long:
            if long[0] == "-":
                raise ValueError, "long option should not start with '-'"
            key = long
            if key[-1] == "=":
                key = key[:-1]
            key = "--" + key
            if self.options_map.has_key(key):
                raise ValueError, "duplicate long option key '%s'" % key
            self.options_map[key] = (name, handler)
            self.long_options.append(long)

        if env:
            self.environ_map[env] = (name, handler)

        if name:
            if not hasattr(self, name):
                setattr(self, name, None)
            self.names_list.append((name, confname))
            if default is not None:
                self.default_map[name] = default
            if required:
                self.required_map[name] = required

    def _set(self, attr, value, prio):
        current = self.attr_priorities.get(attr, -1)
        if prio >= current:
            setattr(self, attr, value)
            self.attr_priorities[attr] = prio

    def realize(self, args=None, doc=None,
                progname=None, raise_getopt_errs=True):
        """Realize a configuration.

        Optional arguments:

        args     -- the command line arguments, less the program name
                    (default is sys.argv[1:])

        doc      -- usage message (default is __main__.__doc__)
        """
         # Provide dynamic default method arguments
        if args is None:
            args = sys.argv[1:]
        if progname is None:
            progname = sys.argv[0]
        if doc is None:
            import __main__
            doc = __main__.__doc__
        self.progname = progname
        self.doc = doc

        self.options = []
        self.args = []

        # Call getopt
        try:
            self.options, self.args = getopt.getopt(
                args, "".join(self.short_options), self.long_options)
        except getopt.error, msg:
            if raise_getopt_errs:
                self.usage(msg)

        # Check for positional args
        if self.args and not self.positional_args_allowed:
            self.usage("positional arguments are not supported")

        # Process options returned by getopt
        for opt, arg in self.options:
            name, handler = self.options_map[opt]
            if handler is not None:
                try:
                    arg = handler(arg)
                except ValueError, msg:
                    self.usage("invalid value for %s %r: %s" % (opt, arg, msg))
            if name and arg is not None:
                if getattr(self, name) is not None:
                    self.usage("conflicting command line option %r" % opt)
                self._set(name, arg, 2)

        # Process environment variables
        for envvar in self.environ_map.keys():
            name, handler = self.environ_map[envvar]
            if os.environ.has_key(envvar):
                value = os.environ[envvar]
                if handler is not None:
                    try:
                        value = handler(value)
                    except ValueError, msg:
                        self.usage("invalid environment value for %s %r: %s"
                                   % (envvar, value, msg))
                if name and value is not None:
                    self._set(name, value, 1)

        if self.configfile is None:
            self.configfile = self.default_configfile()

        self.process_config_file()

    def process_config_file(self, do_usage=True):
        # Process config file
        if not hasattr(self.configfile, 'read'):
            self.here = os.path.abspath(os.path.dirname(self.configfile))
            set_here(self.here)
        try:
            self.read_config(self.configfile)
        except ValueError, msg:
            if do_usage:
                # if this is not called from an RPC method, run usage and exit.
                self.usage(str(msg))
            else:
                # if this is called from an RPC method, raise an error
                raise ValueError(msg)

        # Copy config options to attributes of self.  This only fills
        # in options that aren't already set from the command line.
        for name, confname in self.names_list:
            if confname:
                parts = confname.split(".")
                obj = self.configroot
                for part in parts:
                    if obj is None:
                        break
                    # Here AttributeError is not a user error!
                    obj = getattr(obj, part)
                self._set(name, obj, 0)

        # Process defaults
        for name, value in self.default_map.items():
            if getattr(self, name) is None:
                setattr(self, name, value)

        # Process required options
        for name, message in self.required_map.items():
            if getattr(self, name) is None:
                self.usage(message)

    def get_plugins(self, parser, factory_key, section_prefix):
        factories = []

        for section in parser.sections():
            if not section.startswith(section_prefix):
                continue
            name = section.split(':', 1)[1]
            factory_spec = parser.saneget(section, factory_key, None)
            if factory_spec is None:
                raise ValueError('section [%s] does not specify a %s'  %
                                 (section, factory_key))
            try:
                factory = self.import_spec(factory_spec)
            except ImportError:
                raise ValueError('%s cannot be resolved within [%s]' % (
                    factory_spec, section))
            items = parser.items(section)
            items.remove((factory_key, factory_spec))
            factories.append((name, factory, dict(items)))

        return factories

    def import_spec(self, spec):
        return pkg_resources.EntryPoint.parse("x="+spec).load(False)


class ServerOptions(Options):
    user = None
    sockchown = None
    sockchmod = None
    logfile = None
    loglevel = None
    pidfile = None
    passwdfile = None
    nodaemon = None
    signal = None
    environment = None
    httpservers = ()
    unlink_socketfiles = True
    mood = states.SupervisorStates.RUNNING
    
    def __init__(self):
        Options.__init__(self)
        self.configroot = Dummy()
        self.configroot.supervisord = Dummy()
        
        self.add("nodaemon", "supervisord.nodaemon", "n", "nodaemon", flag=1,
                 default=0)
        self.add("user", "supervisord.user", "u:", "user=")
        self.add("umask", "supervisord.umask", "m:", "umask=",
                 octal_type, default='022')
        self.add("directory", "supervisord.directory", "d:", "directory=",
                 existing_directory)
        self.add("logfile", "supervisord.logfile", "l:", "logfile=",
                 existing_dirpath, default="supervisord.log")
        self.add("logfile_maxbytes", "supervisord.logfile_maxbytes",
                 "y:", "logfile_maxbytes=", byte_size,
                 default=50 * 1024 * 1024) # 50MB
        self.add("logfile_backups", "supervisord.logfile_backups",
                 "z:", "logfile_backups=", integer, default=10)
        self.add("loglevel", "supervisord.loglevel", "e:", "loglevel=",
                 logging_level, default="info")
        self.add("pidfile", "supervisord.pidfile", "j:", "pidfile=",
                 existing_dirpath, default="supervisord.pid")
        self.add("identifier", "supervisord.identifier", "i:", "identifier=",
                 str, default="supervisor")
        self.add("childlogdir", "supervisord.childlogdir", "q:", "childlogdir=",
                 existing_directory, default=tempfile.gettempdir())
        self.add("minfds", "supervisord.minfds",
                 "a:", "minfds=", int, default=1024)
        self.add("minprocs", "supervisord.minprocs",
                 "", "minprocs=", int, default=200)
        self.add("nocleanup", "supervisord.nocleanup",
                 "k", "nocleanup", flag=1, default=0)
        self.add("strip_ansi", "supervisord.strip_ansi",
                 "t", "strip_ansi", flag=1, default=0)
        self.add("profile_options", "supervisord.profile_options",
                 "", "profile_options=", profile_options, default=None)
        self.pidhistory = {}
        self.process_group_configs = []
        self.parse_warnings = []

    def getLogger(self, filename, level, fmt, rotating=False, maxbytes=0,
                  backups=0, stdout=False):
        return loggers.getLogger(filename, level, fmt, rotating, maxbytes,
                                 backups, stdout)

    def realize(self, *arg, **kw):
        Options.realize(self, *arg, **kw)
        section = self.configroot.supervisord

        # Additional checking of user option; set uid and gid
        if self.user is not None:
            uid = name_to_uid(self.user)
            if uid is None:
                self.usage("No such user %s" % self.user)
            self.uid = uid
            self.gid = gid_for_uid(uid)

        if not self.loglevel:
            self.loglevel = section.loglevel

        if self.logfile:
            logfile = self.logfile
        else:
            logfile = section.logfile

        self.logfile = normalize_path(logfile)

        if self.pidfile:
            pidfile = self.pidfile
        else:
            pidfile = section.pidfile

        self.pidfile = normalize_path(pidfile)

        self.rpcinterface_factories = section.rpcinterface_factories

        self.serverurl = None

        self.server_configs = sconfigs = section.server_configs

        # we need to set a fallback serverurl that process.spawn can use

        # prefer a unix domain socket
        for config in [ config for config in sconfigs if
                        config['family'] is socket.AF_UNIX ]:
            path = config['file']
            self.serverurl = 'unix://%s' % path
            break

        # fall back to an inet socket
        if self.serverurl is None:
            for config in [ config for config in sconfigs if
                            config['family'] is socket.AF_INET]:
                host = config['host']
                port = config['port']
                if not host:
                    host = 'localhost'
                self.serverurl = 'http://%s:%s' % (host, port)

        # self.serverurl may still be None if no servers at all are
        # configured in the config file

        self.identifier = section.identifier

    def process_config_file(self, do_usage=True):
        Options.process_config_file(self, do_usage=do_usage)

        new = self.configroot.supervisord.process_group_configs
        self.process_group_configs = new

    def read_config(self, fp):
        section = self.configroot.supervisord
        if not hasattr(fp, 'read'):
            try:
                fp = open(fp, 'r')
            except (IOError, OSError):
                raise ValueError("could not find config file %s" % fp)
        parser = UnhosedConfigParser()
        try:
            parser.readfp(fp)
        except ConfigParser.ParsingError, why:
            raise ValueError(str(why))

        if parser.has_section('include'):
            if not parser.has_option('include', 'files'):
                raise ValueError(".ini file has [include] section, but no "
                "files setting")
            files = parser.get('include', 'files')
            files = files.split()
            if hasattr(fp, 'name'):
                base = os.path.dirname(os.path.abspath(fp.name))
            else:
                base = '.'
            for pattern in files:
                pattern = os.path.join(base, pattern)
                for filename in glob.glob(pattern):
                    self.parse_warnings.append(
                        'Included extra file "%s" during parsing' % filename)
                    try:
                        parser.read(filename)
                    except ConfigParser.ParsingError, why:
                        raise ValueError(str(why))

        sections = parser.sections()
        if not 'supervisord' in sections:
            raise ValueError, '.ini file does not include supervisord section'
        get = parser.getdefault
        section.minfds = integer(get('minfds', 1024))
        section.minprocs = integer(get('minprocs', 200))
        
        directory = get('directory', None)
        if directory is None:
            section.directory = None
        else:
            section.directory = existing_directory(directory)

        section.user = get('user', None)
        section.umask = octal_type(get('umask', '022'))
        section.logfile = existing_dirpath(get('logfile', 'supervisord.log'))
        section.logfile_maxbytes = byte_size(get('logfile_maxbytes', '50MB'))
        section.logfile_backups = integer(get('logfile_backups', 10))
        section.loglevel = logging_level(get('loglevel', 'info'))
        section.pidfile = existing_dirpath(get('pidfile', 'supervisord.pid'))
        section.identifier = get('identifier', 'supervisor')
        section.nodaemon = boolean(get('nodaemon', 'false'))

        tempdir = tempfile.gettempdir()
        section.childlogdir = existing_directory(get('childlogdir', tempdir))
        section.nocleanup = boolean(get('nocleanup', 'false'))
        section.strip_ansi = boolean(get('strip_ansi', 'false'))

        environ_str = get('environment', '')
        environ_str = expand(environ_str, {'here':self.here}, 'environment')
        section.environment = dict_of_key_value_pairs(environ_str)
        section.process_group_configs = self.process_groups_from_parser(parser)
        section.rpcinterface_factories = self.get_plugins(
            parser,
            'supervisor.rpcinterface_factory',
            'rpcinterface:'
            )
        section.server_configs = self.server_configs_from_parser(parser)
        section.profile_options = None
        return section

    def process_groups_from_parser(self, parser):
        groups = []
        all_sections = parser.sections()
        homogeneous_exclude = []
        get = parser.saneget

        # process heterogeneous groups
        for section in all_sections:
            if not section.startswith('group:'):
                continue
            group_name = section.split(':', 1)[1]
            programs = list_of_strings(get(section, 'programs', None))
            priority = integer(get(section, 'priority', 999))
            group_processes = []
            for program in programs:
                program_section = "program:%s" % program
                if not program_section in all_sections:
                    raise ValueError(
                        '[%s] names unknown program %s' % (section, program))
                homogeneous_exclude.append(program_section)
                processes = self.processes_from_section(parser, program_section,
                                                        group_name,
                                                        ProcessConfig)
                group_processes.extend(processes)
            groups.append(
                ProcessGroupConfig(self, group_name, priority, group_processes)
                )

        # process "normal" homogeneous groups
        for section in all_sections:
            if ( (not section.startswith('program:') )
                 or section in homogeneous_exclude ):
                continue
            program_name = section.split(':', 1)[1]
            priority = integer(get(section, 'priority', 999))
            processes=self.processes_from_section(parser, section, program_name,
                                                  ProcessConfig)
            groups.append(
                ProcessGroupConfig(self, program_name, priority, processes)
                )

        # process "event listener" homogeneous groups
        for section in all_sections:
            if not section.startswith('eventlistener:'):
                 continue
            pool_name = section.split(':', 1)[1]
            # give listeners a "high" default priority so they are started first
            # and stopped last at mainloop exit
            priority = integer(get(section, 'priority', -1)) 
            buffer_size = integer(get(section, 'buffer_size', 10))
            result_handler = get(section, 'result_handler',
                                       'supervisor.dispatchers:default_handler')
            try:
                result_handler = self.import_spec(result_handler)
            except ImportError:
                raise ValueError('%s cannot be resolved within [%s]' % (
                    result_handler, section))
            pool_event_names = [x.upper() for x in
                                list_of_strings(get(section, 'events', ''))]
            pool_event_names = dedupe(pool_event_names)
            if not pool_event_names:
                raise ValueError('[%s] section requires an "events" line' %
                                 section)
            from supervisor.events import EventTypes
            pool_events = []
            for pool_event_name in pool_event_names:
                pool_event = getattr(EventTypes, pool_event_name, None)
                if pool_event is None:
                    raise ValueError('Unknown event type %s in [%s] events' %
                                     (pool_event_name, section))
                pool_events.append(pool_event)
            processes=self.processes_from_section(parser, section, pool_name,
                                                  EventListenerConfig)

            groups.append(
                EventListenerPoolConfig(self, pool_name, priority, processes,
                                        buffer_size, pool_events,
                                        result_handler)
                )

        # process fastcgi homogeneous groups
        for section in all_sections:
            if ( (not section.startswith('fcgi-program:') )
                 or section in homogeneous_exclude ):
                continue
            program_name = section.split(':', 1)[1]
            priority = integer(get(section, 'priority', 999))
            socket = get(section, 'socket', None)
            if not socket:
                raise ValueError('[%s] section requires a "socket" line' %
                                 section)

            expansions = {'here':self.here,
                          'program_name':program_name}
            socket = expand(socket, expansions, 'socket')
            try:
                socket_config = self.parse_fcgi_socket(socket)
            except ValueError, e:
                raise ValueError('%s in [%s] socket' % (str(e), section))
            
            processes=self.processes_from_section(parser, section, program_name,
                                                  FastCGIProcessConfig)
            groups.append(
                FastCGIGroupConfig(self, program_name, priority, processes,
                                   SocketManager(socket_config))
                )
        

        groups.sort()
        return groups

    def parse_fcgi_socket(self, sock):
        if sock.startswith('unix://'):
            path = sock[7:]
            #Check it's an absolute path
            if not os.path.isabs(path):
                raise ValueError("Unix socket path %s is not an absolute path",
                                 path)
            path = normalize_path(path)
            return UnixStreamSocketConfig(path)
        
        tcp_re = re.compile(r'^tcp://([^\s:]+):(\d+)$')
        m = tcp_re.match(sock)
        if m:
            host = m.group(1)
            port = int(m.group(2))
            return InetStreamSocketConfig(host, port)
        
        raise ValueError("Bad socket format %s", sock)

    def processes_from_section(self, parser, section, group_name,
                               klass=None):
        if klass is None:
            klass = ProcessConfig
        programs = []
        get = parser.saneget
        program_name = section.split(':', 1)[1]

        priority = integer(get(section, 'priority', 999))
        autostart = boolean(get(section, 'autostart', 'true'))
        autorestart = auto_restart(get(section, 'autorestart', 'unexpected'))
        startsecs = integer(get(section, 'startsecs', 1))
        startretries = integer(get(section, 'startretries', 3))
        uid = name_to_uid(get(section, 'user', None))
        stopsignal = signal_number(get(section, 'stopsignal', 'TERM'))
        stopwaitsecs = integer(get(section, 'stopwaitsecs', 10))
        exitcodes = list_of_exitcodes(get(section, 'exitcodes', '0,2'))
        redirect_stderr = boolean(get(section, 'redirect_stderr','false'))
        numprocs = integer(get(section, 'numprocs', 1))
        numprocs_start = integer(get(section, 'numprocs_start', 0))
        process_name = get(section, 'process_name', '%(program_name)s')
        environment_str = get(section, 'environment', '')
        stdout_cmaxbytes = byte_size(get(section,'stdout_capture_maxbytes','0'))
        stdout_events = boolean(get(section, 'stdout_events_enabled','false'))
        stderr_cmaxbytes = byte_size(get(section,'stderr_capture_maxbytes','0'))
        stderr_events = boolean(get(section, 'stderr_events_enabled','false'))
        directory = get(section, 'directory', None)
        serverurl = get(section, 'serverurl', None)
        if serverurl and serverurl.strip().upper() == 'AUTO':
            serverurl = None

        umask = get(section, 'umask', None)
        if umask is not None:
            umask = octal_type(umask)

        command = get(section, 'command', None)
        if command is None:
            raise ValueError, (
                'program section %s does not specify a command' % section)

        if numprocs > 1:
            if process_name.find('%(process_num)') == -1:
                # process_name needs to include process_num when we
                # represent a group of processes
                raise ValueError(
                    '%(process_num) must be present within process_name when '
                    'numprocs > 1')

        for process_num in range(numprocs_start, numprocs + numprocs_start):
            expansions = {'here':self.here,
                          'process_num':process_num,
                          'program_name':program_name,
                          'group_name':group_name}

            environment = dict_of_key_value_pairs(
                expand(environment_str, expansions, 'environment'))

            if directory:
                directory = expand(directory, expansions, 'directory')

            logfiles = {}

            for k in ('stdout', 'stderr'):
                n = '%s_logfile' % k
                lf_val = get(section, n, Automatic)
                if isinstance(lf_val, basestring):
                    lf_val = expand(lf_val, expansions, n)
                lf_val = logfile_name(lf_val)
                logfiles[n] = lf_val

                bu_key = '%s_logfile_backups' % k
                backups = integer(get(section, bu_key, 10))
                logfiles[bu_key] = backups

                mb_key = '%s_logfile_maxbytes' % k
                maxbytes = byte_size(get(section, mb_key, '50MB'))
                logfiles[mb_key] = maxbytes

                if lf_val is Automatic and not maxbytes:
                    self.parse_warnings.append(
                        'For [%s], AUTO logging used for %s without '
                        'rollover, set maxbytes > 0 to avoid filling up '
                        'filesystem unintentionally' % (section, n))

            pconfig = klass(
                self,
                name=expand(process_name, expansions, 'process_name'),
                command=expand(command, expansions, 'command'),
                directory=directory,
                umask=umask,
                priority=priority,
                autostart=autostart,
                autorestart=autorestart,
                startsecs=startsecs,
                startretries=startretries,
                uid=uid,
                stdout_logfile=logfiles['stdout_logfile'],
                stdout_capture_maxbytes = stdout_cmaxbytes,
                stdout_events_enabled = stdout_events,
                stdout_logfile_backups=logfiles['stdout_logfile_backups'],
                stdout_logfile_maxbytes=logfiles['stdout_logfile_maxbytes'],
                stderr_logfile=logfiles['stderr_logfile'],
                stderr_capture_maxbytes = stderr_cmaxbytes,
                stderr_events_enabled = stderr_events,
                stderr_logfile_backups=logfiles['stderr_logfile_backups'],
                stderr_logfile_maxbytes=logfiles['stderr_logfile_maxbytes'],
                stopsignal=stopsignal,
                stopwaitsecs=stopwaitsecs,
                exitcodes=exitcodes,
                redirect_stderr=redirect_stderr,
                environment=environment,
                serverurl=serverurl)

            programs.append(pconfig)

        programs.sort() # asc by priority
        return programs

    def _parse_servernames(self, parser, stype):
        options = []
        for section in parser.sections():
            if section.startswith(stype):
                parts = section.split(':', 1)
                if len(parts) > 1:
                    name = parts[1]
                else:
                    name = None # default sentinel
                options.append((name, section))
        return options

    def _parse_username_and_password(self, parser, section):
        get = parser.saneget
        username = get(section, 'username', None)
        password = get(section, 'password', None)
        if username is None and password is not None:
            raise ValueError(
                'Must specify username if password is specified in [%s]'
                % section)
        return {'username':username, 'password':password}

    def server_configs_from_parser(self, parser):
        configs = []
        inet_serverdefs = self._parse_servernames(parser, 'inet_http_server')
        for name, section in inet_serverdefs:
            config = {}
            get = parser.saneget
            config.update(self._parse_username_and_password(parser, section))
            config['name'] = name
            config['family'] = socket.AF_INET
            port = get(section, 'port', None)
            if port is None:
                raise ValueError('section [%s] has no port value' % section)
            host, port = inet_address(port)
            config['host'] = host
            config['port'] = port
            config['section'] = section
            configs.append(config)

        unix_serverdefs = self._parse_servernames(parser, 'unix_http_server')
        for name, section in unix_serverdefs:
            config = {}
            get = parser.saneget
            sfile = get(section, 'file', None)
            if sfile is None:
                raise ValueError('section [%s] has no file value' % section)
            sfile = sfile.strip()
            config['name'] = name
            config['family'] = socket.AF_UNIX
            sfile = expand(sfile, {'here':self.here}, 'socket file')
            config['file'] = normalize_path(sfile)
            config.update(self._parse_username_and_password(parser, section))
            chown = get(section, 'chown', None)
            if chown is not None:
                try:
                    chown = colon_separated_user_group(chown)
                except ValueError:
                    raise ValueError('Invalid sockchown value %s' % chown)
            else:
                chown = (-1, -1)
            config['chown'] = chown
            chmod = get(section, 'chmod', None)
            if chmod is not None:
                try:
                    chmod = octal_type(chmod)
                except (TypeError, ValueError):
                    raise ValueError('Invalid chmod value %s' % chmod)
            else:
                chmod = 0700
            config['chmod'] = chmod
            config['section'] = section
            configs.append(config)

        return configs

    def daemonize(self):
        # To daemonize, we need to become the leader of our own session
        # (process) group.  If we do not, signals sent to our
        # parent process will also be sent to us.   This might be bad because
        # signals such as SIGINT can be sent to our parent process during
        # normal (uninteresting) operations such as when we press Ctrl-C in the
        # parent terminal window to escape from a logtail command.
        # To disassociate ourselves from our parent's session group we use
        # os.setsid.  It means "set session id", which has the effect of
        # disassociating a process from is current session and process group
        # and setting itself up as a new session leader.
        #
        # Unfortunately we cannot call setsid if we're already a session group
        # leader, so we use "fork" to make a copy of ourselves that is
        # guaranteed to not be a session group leader.
        #
        # We also change directories, set stderr and stdout to null, and
        # change our umask.
        #
        # This explanation was (gratefully) garnered from
        # http://www.hawklord.uklinux.net/system/daemons/d3.htm

        pid = os.fork()
        if pid != 0:
            # Parent
            self.logger.blather("supervisord forked; parent exiting")
            os._exit(0)
        # Child
        self.logger.info("daemonizing the supervisord process")
        if self.directory:
            try:
                os.chdir(self.directory)
            except OSError, err:
                self.logger.critical("can't chdir into %r: %s"
                                     % (self.directory, err))
            else:
                self.logger.info("set current directory: %r"
                                 % self.directory)
        os.close(0)
        self.stdin = sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        self.stdout = sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        self.stderr = sys.stderr = sys.__stderr__ = open("/dev/null", "w")
        os.setsid()
        os.umask(self.umask)
        # XXX Stevens, in his Advanced Unix book, section 13.3 (page
        # 417) recommends calling umask(0) and closing unused
        # file descriptors.  In his Network Programming book, he
        # additionally recommends ignoring SIGHUP and forking again
        # after the setsid() call, for obscure SVR4 reasons.

    def write_pidfile(self):
        pid = os.getpid()
        try:
            f = open(self.pidfile, 'w')
            f.write('%s\n' % pid)
            f.close()
        except (IOError, OSError):
            self.logger.critical('could not write pidfile %s' % self.pidfile)
        else:
            self.logger.info('supervisord started with pid %s' % pid)
                
    def cleanup(self):
        try:
            for config, server in self.httpservers:
                if config['family'] == socket.AF_UNIX:
                    if self.unlink_socketfiles:
                        socketname = config['file']
                        try:
                            os.unlink(socketname)
                        except OSError:
                            pass
        except OSError:
            pass
        try:
            os.unlink(self.pidfile)
        except OSError:
            pass

    def close_httpservers(self):
        for config, server in self.httpservers:
            server.close()
            map = self.get_socket_map()
            # server._map is a reference to the asyncore socket_map
            for dispatcher in map.values():
                # For unknown reasons, sometimes an http_channel
                # dispatcher in the socket map related to servers
                # remains open *during a reload*.  If one of these
                # exists at this point, we need to close it by hand
                # (thus removing it from the asyncore.socket_map).  If
                # we don't do this, 'cleanup_fds' will cause its file
                # descriptor to be closed, but it will still remain in
                # the socket_map, and eventually its file descriptor
                # will be passed to # select(), which will bomb.  See
                # also http://www.plope.com/software/collector/253
                dispatcher_server = getattr(dispatcher, 'server', None)
                if dispatcher_server is server:
                    dispatcher.close()

    def close_logger(self):
        self.logger.close()

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.sigreceiver)
        signal.signal(signal.SIGINT, self.sigreceiver)
        signal.signal(signal.SIGQUIT, self.sigreceiver)
        signal.signal(signal.SIGHUP, self.sigreceiver)
        signal.signal(signal.SIGCHLD, self.sigreceiver)
        signal.signal(signal.SIGUSR2, self.sigreceiver)

    def sigreceiver(self, sig, frame):
        self.signal = sig

    def openhttpservers(self, supervisord):
        try:
            self.httpservers = self.make_http_servers(supervisord)
        except socket.error, why:
            if why[0] == errno.EADDRINUSE:
                self.usage('Another program is already listening on '
                           'a port that one of our HTTP servers is '
                           'configured to use.  Shut this program '
                           'down first before starting supervisord.')
            else:
                help = 'Cannot open an HTTP server: socket.error reported'
                errorname = errno.errorcode.get(why[0])
                if errorname is None:
                    self.usage('%s %s' % (help, why[0]))
                else:
                    self.usage('%s errno.%s (%d)' % 
                               (help, errorname, why[0]))
            self.unlink_socketfiles = False
        except ValueError, why:
            self.usage(why[0])

    def get_autochildlog_name(self, name, identifier, channel):
        prefix='%s-%s---%s-' % (name, channel, identifier)
        logfile = self.mktempfile(
            suffix='.log',
            prefix=prefix,
            dir=self.childlogdir)
        return logfile

    def clear_autochildlogdir(self):
        # must be called after realize()
        childlogdir = self.childlogdir
        fnre = re.compile(r'.+?---%s-\S+\.log\.{0,1}\d{0,4}' % self.identifier)
        try:
            filenames = os.listdir(childlogdir)
        except (IOError, OSError):
            self.logger.warn('Could not clear childlog dir')
            return
        
        for filename in filenames:
            if fnre.match(filename):
                pathname = os.path.join(childlogdir, filename)
                try:
                    os.remove(pathname)
                except (OSError, IOError):
                    self.logger.warn('Failed to clean up %r' % pathname)

    def get_socket_map(self):
        return asyncore.socket_map

    def cleanup_fds(self):
        # try to close any leaked file descriptors (for reload)
        start = 5
        for x in range(start, self.minfds):
            try:
                os.close(x)
            except OSError:
                pass

    def select(self, r, w, x, timeout):
        return select.select(r, w, x, timeout)

    def kill(self, pid, signal):
        os.kill(pid, signal)

    def set_uid(self):
        if self.uid is None:
            if os.getuid() == 0:
                return 'Supervisor running as root (no user in config file)'
            return None
        msg = self.dropPrivileges(self.uid)
        if msg is None:
            return 'Set uid to user %s' % self.uid
        return msg

    def dropPrivileges(self, user):
        # Drop root privileges if we have them
        if user is None:
            return "No used specified to setuid to!"
        if os.getuid() != 0:
            return "Can't drop privilege as nonroot user"
        try:
            uid = int(user)
        except ValueError:
            try:
                pwrec = pwd.getpwnam(user)
            except KeyError:
                return "Can't find username %r" % user
            uid = pwrec[2]
        else:
            try:
                pwrec = pwd.getpwuid(uid)
            except KeyError:
                return "Can't find uid %r" % uid
        if hasattr(os, 'setgroups'):
            user = pwrec[0]
            groups = [grprec[2] for grprec in grp.getgrall() if user in
                      grprec[3]]
            try:
                os.setgroups(groups)
            except OSError:
                return 'Could not set groups of effective user'
        gid = pwrec[3]
        try:
            os.setgid(gid)
        except OSError:
            return 'Could not set group id of effective user'
        os.setuid(uid)

    def waitpid(self):
        # need pthread_sigmask here to avoid concurrent sigchild, but
        # Python doesn't offer it as it's not standard across UNIX versions.
        # there is still a race condition here; we can get a sigchild while
        # we're sitting in the waitpid call.
        try:
            pid, sts = os.waitpid(-1, os.WNOHANG)
        except OSError, why:
            err = why[0]
            if err not in (errno.ECHILD, errno.EINTR):
                self.logger.critical(
                    'waitpid error; a process may not be cleaned up properly')
            if err == errno.EINTR:
                self.logger.blather('EINTR during reap')
            pid, sts = None, None
        return pid, sts

    def set_rlimits(self):
        limits = []
        if hasattr(resource, 'RLIMIT_NOFILE'):
            limits.append(
                {
                'msg':('The minimum number of file descriptors required '
                       'to run this process is %(min)s as per the "minfds" '
                       'command-line argument or config file setting. '
                       'The current environment will only allow you '
                       'to open %(hard)s file descriptors.  Either raise '
                       'the number of usable file descriptors in your '
                       'environment (see README.txt) or lower the '
                       'minfds setting in the config file to allow '
                       'the process to start.'),
                'min':self.minfds,
                'resource':resource.RLIMIT_NOFILE,
                'name':'RLIMIT_NOFILE',
                })
        if hasattr(resource, 'RLIMIT_NPROC'):
            limits.append(
                {
                'msg':('The minimum number of available processes required '
                       'to run this program is %(min)s as per the "minprocs" '
                       'command-line argument or config file setting. '
                       'The current environment will only allow you '
                       'to open %(hard)s processes.  Either raise '
                       'the number of usable processes in your '
                       'environment (see README.txt) or lower the '
                       'minprocs setting in the config file to allow '
                       'the program to start.'),
                'min':self.minprocs,
                'resource':resource.RLIMIT_NPROC,
                'name':'RLIMIT_NPROC',
                })

        msgs = []
            
        for limit in limits:

            min = limit['min']
            res = limit['resource']
            msg = limit['msg']
            name = limit['name']

            soft, hard = resource.getrlimit(res)
            
            if (soft < min) and (soft != -1): # -1 means unlimited 
                if (hard < min) and (hard != -1):
                    self.usage(msg % locals())

                try:
                    resource.setrlimit(res, (min, hard))
                    msgs.append('Increased %(name)s limit to %(min)s' %
                                locals())
                except (resource.error, ValueError):
                    self.usage(msg % locals())
        return msgs

    def make_logger(self, critical_messages, warn_messages, info_messages):
        # must be called after realize() and after supervisor does setuid()
        format =  '%(asctime)s %(levelname)s %(message)s\n'
        self.logger = loggers.getLogger(
            self.logfile,
            self.loglevel,
            format,
            rotating=True,
            maxbytes=self.logfile_maxbytes,
            backups=self.logfile_backups,
            stdout = self.nodaemon,
            )
        for msg in critical_messages:
            self.logger.critical(msg)
        for msg in warn_messages:
            self.logger.warn(msg)
        for msg in info_messages:
            self.logger.info(msg)

    def make_http_servers(self, supervisord):
        from supervisor.http import make_http_servers
        return make_http_servers(self, supervisord)

    def close_fd(self, fd):
        try:
            os.close(fd)
        except OSError:
            pass

    def fork(self):
        return os.fork()

    def dup2(self, frm, to):
        return os.dup2(frm, to)

    def setpgrp(self):
        return os.setpgrp()

    def stat(self, filename):
        return os.stat(filename)

    def write(self, fd, data):
        return os.write(fd, data)

    def execve(self, filename, argv, env):
        return os.execve(filename, argv, env)

    def mktempfile(self, suffix, prefix, dir):
        # set os._urandomfd as a hack around bad file descriptor bug
        # seen in the wild, see
        # http://www.plope.com/software/collector/252
        os._urandomfd = None 
        fd, filename = tempfile.mkstemp(suffix, prefix, dir)
        os.close(fd)
        return filename

    def remove(self, path):
        os.remove(path)

    def exists(self, path):
        return os.path.exists(path)

    def _exit(self, code):
        os._exit(code)

    def setumask(self, mask):
        os.umask(mask)

    def get_path(self):
        """Return a list corresponding to $PATH, or a default."""
        path = ["/bin", "/usr/bin", "/usr/local/bin"]
        if os.environ.has_key("PATH"):
            p = os.environ["PATH"]
            if p:
                path = p.split(os.pathsep)
        return path

    def get_pid(self):
        return os.getpid()

    def check_execv_args(self, filename, argv, st):
        if st is None:
            raise NotFound("can't find command %r" % filename)

        elif stat.S_ISDIR(st[stat.ST_MODE]):
            raise NotExecutable("command at %r is a directory" % filename)

        elif not (stat.S_IMODE(st[stat.ST_MODE]) & 0111):
            raise NotExecutable("command at %r is not executable" % filename)

        elif not os.access(filename, os.X_OK):
            raise NoPermission("no permission to run command %r" % filename)

    def reopenlogs(self):
        self.logger.info('supervisord logreopen')
        for handler in self.logger.handlers:
            if hasattr(handler, 'reopen'):
                handler.reopen()

    def readfd(self, fd):
        try:
            data = os.read(fd, 2 << 16) # 128K
        except OSError, why:
            if why[0] not in (errno.EWOULDBLOCK, errno.EBADF, errno.EINTR):
                raise
            data = ''
        return data

    def process_environment(self):
        os.environ.update(self.environment or {})

    def open(self, fn, mode='r'):
        return open(fn, mode)

    def chdir(self, dir):
        os.chdir(dir)
        
    def make_pipes(self, stderr=True):
        """ Create pipes for parent to child stdin/stdout/stderr
        communications.  Open fd in nonblocking mode so we can read them
        in the mainloop without blocking.  If stderr is False, don't
        create a pipe for stderr. """

        pipes = {'child_stdin':None,
                 'stdin':None,
                 'stdout':None,
                 'child_stdout':None,
                 'stderr':None,
                 'child_stderr':None}
        try:
            stdin, child_stdin = os.pipe()
            pipes['child_stdin'], pipes['stdin'] = stdin, child_stdin
            stdout, child_stdout = os.pipe()
            pipes['stdout'], pipes['child_stdout'] = stdout, child_stdout
            if stderr:
                stderr, child_stderr = os.pipe()
                pipes['stderr'], pipes['child_stderr'] = stderr, child_stderr
            for fd in (pipes['stdout'], pipes['stderr'], pipes['stdin']):
                if fd is not None:
                    fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | os.O_NDELAY)
            return pipes
        except OSError:
            for fd in pipes.values():
                if fd is not None:
                    self.close_fd(fd)

    def close_parent_pipes(self, pipes):
        for fdname in ('stdin', 'stdout', 'stderr'):
            fd = pipes[fdname]
            if fd is not None:
                self.close_fd(fd)

    def close_child_pipes(self, pipes):
        for fdname in ('child_stdin', 'child_stdout', 'child_stderr'):
            fd = pipes[fdname]
            if fd is not None:
                self.close_fd(fd)

class ClientOptions(Options):
    positional_args_allowed = 1

    interactive = None
    prompt = None
    serverurl = None
    username = None
    password = None
    history_file = None

    def __init__(self):
        Options.__init__(self)
        self.configroot = Dummy()
        self.configroot.supervisorctl = Dummy()
        self.configroot.supervisorctl.interactive = None
        self.configroot.supervisorctl.prompt = None
        self.configroot.supervisorctl.serverurl = None
        self.configroot.supervisorctl.username = None
        self.configroot.supervisorctl.password = None
        self.configroot.supervisorctl.history_file = None


        self.add("interactive", "supervisorctl.interactive", "i",
                 "interactive", flag=1, default=0)
        self.add("prompt", "supervisorctl.prompt", default="supervisor")
        self.add("serverurl", "supervisorctl.serverurl", "s:", "serverurl=",
                 url, default="http://localhost:9001")
        self.add("username", "supervisorctl.username", "u:", "username=")
        self.add("password", "supervisorctl.password", "p:", "password=")
        self.add("history", "supervisorctl.history_file", "r:", "history_file=")

    def realize(self, *arg, **kw):
        Options.realize(self, *arg, **kw)
        if not self.args:
            self.interactive = 1

    def read_config(self, fp):
        section = self.configroot.supervisorctl
        if not hasattr(fp, 'read'):
            self.here = os.path.dirname(normalize_path(fp))
            try:
                fp = open(fp, 'r')
            except (IOError, OSError):
                raise ValueError("could not find config file %s" % fp)
        config = UnhosedConfigParser()
        config.mysection = 'supervisorctl'
        config.readfp(fp)
        sections = config.sections()
        if not 'supervisorctl' in sections:
            raise ValueError,'.ini file does not include supervisorctl section' 
        serverurl = config.getdefault('serverurl', 'http://localhost:9001')
        if serverurl.startswith('unix://'):
            sf = serverurl[7:]
            path = expand(sf, {'here':self.here}, 'serverurl')
            path = normalize_path(path)
            serverurl = 'unix://%s' % path
        section.serverurl = serverurl
        section.prompt = config.getdefault('prompt', 'supervisor')
        section.username = config.getdefault('username', None)
        section.password = config.getdefault('password', None)
        history_file = config.getdefault('history_file', None)

        if history_file:
            history_file = normalize_path(history_file)
            section.history_file = history_file
            self.history_file = history_file
        else:
            section.history_file = None
            self.history_file = None

        from supervisor.supervisorctl import DefaultControllerPlugin
        self.plugin_factories = self.get_plugins(
            config,
            'supervisor.ctl_factory',
            'ctlplugin:'
            )
        default_factory = ('default', DefaultControllerPlugin, {})
        # if you want to a supervisorctl without the default plugin,
        # please write your own supervisorctl.
        self.plugin_factories.insert(0, default_factory)

        return section

    def getServerProxy(self):
        # mostly put here for unit testing
        return xmlrpclib.ServerProxy(
            # dumbass ServerProxy won't allow us to pass in a non-HTTP url,
            # so we fake the url we pass into it and always use the transport's
            # 'serverurl' to figure out what to attach to
            'http://127.0.0.1',
            transport = xmlrpc.SupervisorTransport(self.username,
                                                   self.password,
                                                   self.serverurl)
            )

_marker = []

class UnhosedConfigParser(ConfigParser.RawConfigParser):
    mysection = 'supervisord'
    def read_string(self, s):
        from StringIO import StringIO
        s = StringIO(s)
        return self.readfp(s)
    
    def getdefault(self, option, default=_marker):
        try:
            return self.get(self.mysection, option)
        except ConfigParser.NoOptionError:
            if default is _marker:
                raise
            else:
                return default

    def saneget(self, section, option, default=_marker):
        try:
            return self.get(section, option)
        except ConfigParser.NoOptionError:
            if default is _marker:
                raise
            else:
                return default

class Config:
    def __cmp__(self, other):
        return cmp(self.priority, other.priority)

    def __repr__(self):
        return '<%s instance at %s named %s>' % (self.__class__, id(self),
                                                 self.name)
    
class ProcessConfig(Config):
    req_param_names = [
        'name', 'uid', 'command', 'directory', 'umask', 'priority',
        'autostart', 'autorestart', 'startsecs', 'startretries',
        'stdout_logfile', 'stdout_capture_maxbytes',
        'stdout_events_enabled',
        'stdout_logfile_backups', 'stdout_logfile_maxbytes',
        'stderr_logfile', 'stderr_capture_maxbytes', 
        'stderr_logfile_backups', 'stderr_logfile_maxbytes',
        'stderr_events_enabled',
        'stopsignal', 'stopwaitsecs', 'exitcodes', 'redirect_stderr' ]
    optional_param_names = [ 'environment', 'serverurl' ]

    def __init__(self, options, **params):
        self.options = options
        for name in self.req_param_names:
            setattr(self, name, params[name])
        for name in self.optional_param_names:
            setattr(self, name, params.get(name, None))

    def __eq__(self, other):
        if not isinstance(other, ProcessConfig):
            return False

        for name in self.req_param_names + self.optional_param_names:
            if Automatic in [getattr(self, name), getattr(other, name)] :
                continue
            if getattr(self, name) != getattr(other, name):
                return False

        return True

    def create_autochildlogs(self):
        # temporary logfiles which are erased at start time
        get_autoname = self.options.get_autochildlog_name
        sid = self.options.identifier
        name = self.name
        if self.stdout_logfile is Automatic:
            self.stdout_logfile = get_autoname(name, sid, 'stdout')
        if self.stderr_logfile is Automatic:
            self.stderr_logfile = get_autoname(name, sid, 'stderr')
            
    def make_process(self, group=None):
        from supervisor.process import Subprocess
        process = Subprocess(self)
        process.group = group
        return process

    def make_dispatchers(self, proc):
        use_stderr = not self.redirect_stderr
        p = self.options.make_pipes(use_stderr)
        stdout_fd,stderr_fd,stdin_fd = p['stdout'],p['stderr'],p['stdin']
        dispatchers = {}
        from supervisor.dispatchers import POutputDispatcher
        from supervisor.dispatchers import PInputDispatcher
        from supervisor import events
        if stdout_fd is not None:
            etype = events.ProcessCommunicationStdoutEvent
            dispatchers[stdout_fd] = POutputDispatcher(proc, etype, stdout_fd)
        if stderr_fd is not None:
            etype = events.ProcessCommunicationStderrEvent
            dispatchers[stderr_fd] = POutputDispatcher(proc,etype, stderr_fd)
        if stdin_fd is not None:
            dispatchers[stdin_fd] = PInputDispatcher(proc, 'stdin', stdin_fd)
        return dispatchers, p

class EventListenerConfig(ProcessConfig):
    def make_dispatchers(self, proc):
        use_stderr = not self.redirect_stderr
        p = self.options.make_pipes(use_stderr)
        stdout_fd,stderr_fd,stdin_fd = p['stdout'],p['stderr'],p['stdin']
        dispatchers = {}
        from supervisor.dispatchers import PEventListenerDispatcher
        from supervisor.dispatchers import PInputDispatcher
        from supervisor.dispatchers import POutputDispatcher
        from supervisor import events
        if stdout_fd is not None:
            dispatchers[stdout_fd] = PEventListenerDispatcher(proc, 'stdout',
                                                              stdout_fd)
        if stderr_fd is not None:
            etype = events.ProcessCommunicationStderrEvent
            dispatchers[stderr_fd] = POutputDispatcher(proc, etype, stderr_fd)
        if stdin_fd is not None:
            dispatchers[stdin_fd] = PInputDispatcher(proc, 'stdin', stdin_fd)
        return dispatchers, p

class FastCGIProcessConfig(ProcessConfig):
    def make_process(self, group=None):
        if group is None:
            raise NotImplementedError('FastCGI programs require a group')
        from supervisor.process import FastCGISubprocess
        process = FastCGISubprocess(self)
        process.group = group
        return process

    def make_dispatchers(self, proc):
        dispatchers, p = ProcessConfig.make_dispatchers(self, proc)
        #FastCGI child processes expect the FastCGI socket set to
        #file descriptor 0, so supervisord cannot use stdin
        #to communicate with the child process
        stdin_fd = p['stdin']
        if stdin_fd is not None:
            dispatchers[stdin_fd].close()
        return dispatchers, p

class ProcessGroupConfig(Config):
    def __init__(self, options, name, priority, process_configs):
        self.options = options
        self.name = name
        self.priority = priority
        self.process_configs = process_configs

    def __eq__(self, other):
        if not isinstance(other, ProcessGroupConfig):
            return False

        if self.name != other.name:
            return False
        if self.priority != other.priority:
            return False
        if self.process_configs != other.process_configs:
            return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def after_setuid(self):
        for config in self.process_configs:
            config.create_autochildlogs()

    def make_group(self):
        from supervisor.process import ProcessGroup
        return ProcessGroup(self)

class EventListenerPoolConfig(Config):
    def __init__(self, options, name, priority, process_configs, buffer_size,
                 pool_events, result_handler):
        self.options = options
        self.name = name
        self.priority = priority
        self.process_configs = process_configs
        self.buffer_size = buffer_size
        self.pool_events = pool_events
        self.result_handler = result_handler

    def after_setuid(self):
        for config in self.process_configs:
            config.create_autochildlogs()

    def make_group(self):
        from supervisor.process import EventListenerPool
        return EventListenerPool(self)

class FastCGIGroupConfig(ProcessGroupConfig):        
    def __init__(self, options, name, priority, process_configs,
                 socket_manager):
        self.options = options
        self.name = name
        self.priority = priority
        self.process_configs = process_configs
        self.socket_manager = socket_manager

    def after_setuid(self):
        ProcessGroupConfig.after_setuid(self)
        self.socket_manager.prepare_socket()
    
def readFile(filename, offset, length):
    """ Read length bytes from the file named by filename starting at
    offset """

    absoffset = abs(offset)
    abslength = abs(length)

    try:
        f = open(filename, 'rb')
        if absoffset != offset:
            # negative offset returns offset bytes from tail of the file
            if length:
                raise ValueError('BAD_ARGUMENTS')
            f.seek(0, 2)
            sz = f.tell()
            pos = int(sz - absoffset)
            if pos < 0:
                pos = 0
            f.seek(pos)
            data = f.read(absoffset)
        else:
            if abslength != length:
                raise ValueError('BAD_ARGUMENTS')
            if length == 0:
                f.seek(offset)
                data = f.read()
            else:
                sz = f.seek(offset)
                data = f.read(length)
    except (OSError, IOError):
        raise ValueError('FAILED')

    return data

def tailFile(filename, offset, length):
    """ 
    Read length bytes from the file named by filename starting at
    offset, automatically increasing offset and setting overflow
    flag if log size has grown beyond (offset + length).  If length
    bytes are not available, as many bytes as are available are returned.
    """

    overflow = False
    try:
        f = open(filename, 'rb')
        f.seek(0, 2)
        sz = f.tell()

        if sz > (offset + length):
            overflow = True
            offset   = sz - 1

        if (offset + length) > sz:
            if (offset > (sz - 1)):
                length = 0
            offset = sz - length

        if offset < 0: offset = 0
        if length < 0: length = 0

        if length == 0:
            data = ''
        else:
            f.seek(offset)
            data = f.read(length)

        offset = sz
        return [data, offset, overflow]

    except (OSError, IOError):
        return ['', offset, False]

# Helpers for dealing with signals and exit status

def decode_wait_status(sts):
    """Decode the status returned by wait() or waitpid().

    Return a tuple (exitstatus, message) where exitstatus is the exit
    status, or -1 if the process was killed by a signal; and message
    is a message telling what happened.  It is the caller's
    responsibility to display the message.
    """
    if os.WIFEXITED(sts):
        es = os.WEXITSTATUS(sts) & 0xffff
        msg = "exit status %s" % es
        return es, msg
    elif os.WIFSIGNALED(sts):
        sig = os.WTERMSIG(sts)
        msg = "terminated by %s" % signame(sig)
        if hasattr(os, "WCOREDUMP"):
            iscore = os.WCOREDUMP(sts)
        else:
            iscore = sts & 0x80
        if iscore:
            msg += " (core dumped)"
        return -1, msg
    else:
        msg = "unknown termination cause 0x%04x" % sts
        return -1, msg

_signames = None

def signame(sig):
    """Return a symbolic name for a signal.

    Return "signal NNN" if there is no corresponding SIG name in the
    signal module.
    """

    if _signames is None:
        _init_signames()
    return _signames.get(sig) or "signal %d" % sig

def _init_signames():
    global _signames
    d = {}
    for k, v in signal.__dict__.items():
        k_startswith = getattr(k, "startswith", None)
        if k_startswith is None:
            continue
        if k_startswith("SIG") and not k_startswith("SIG_"):
            d[v] = k
    _signames = d

# miscellaneous utility functions

def expand(s, expansions, name):
    try:
        return s % expansions
    except KeyError:
        raise ValueError(
            'Format string %r for %r contains names which cannot be '
            'expanded' % (s, name))
    except:
        raise ValueError(
            'Format string %r for %r is badly formatted' % (s, name)
            )

def make_namespec(group_name, process_name):
    # we want to refer to the process by its "short name" (a process named
    # process1 in the group process1 has a name "process1").  This is for
    # backwards compatibility
    if group_name == process_name:
        name = process_name
    else:
        name = '%s:%s' % (group_name, process_name)
    return name

def split_namespec(namespec):
    names = namespec.split(':', 1)
    if len(names) == 2:
        # group and and process name differ
        group_name, process_name = names
        if not process_name or process_name == '*':
            process_name = None
    else:
        # group name is same as process name
        group_name, process_name = namespec, namespec
    return group_name, process_name

def dedupe(L):
    # cant use sets, they dont exist in 2.3
    D = {}
    for thing in L:
        D[thing] = 1
    return D.keys()

# exceptions

class ProcessException(Exception):
    """ Specialized exceptions used when attempting to start a process """

class NotExecutable(ProcessException):
    """ Indicates that the filespec cannot be executed because its path
    resolves to a file which is not executable, or which is a directory. """

class NotFound(ProcessException):
    """ Indicates that the filespec cannot be executed because it could not
    be found """

class NoPermission(ProcessException):
    """ Indicates that the file cannot be executed because the supervisor
    process does not possess the appropriate UNIX filesystem permission
    to execute the file. """

