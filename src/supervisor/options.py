##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

import ConfigParser
import asyncore
import socket
import getopt
import os
import sys
import logging
import tempfile
import errno
import signal
import re
import xmlrpclib
import httplib
import urllib
import pwd
import grp
import resource
import stat
import pkg_resources
import select

from fcntl import fcntl
from fcntl import F_SETFL, F_GETFL

from supervisor.datatypes import boolean
from supervisor.datatypes import integer
from supervisor.datatypes import name_to_uid
from supervisor.datatypes import name_to_gid
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
from supervisor.datatypes import dot_separated_user_group
from supervisor.datatypes import SocketAddress
from supervisor.datatypes import url
from supervisor.datatypes import Automatic

here = os.path.abspath(os.path.dirname(__file__))
version_txt = os.path.join(here, 'version.txt')
VERSION = open(version_txt).read().strip()

class FileHandler(logging.StreamHandler):
    """File handler which supports reopening of logs.

    Re-opening should be used instead of the 'rollover' feature of
    the FileHandler from the standard library's logging package.
    """

    def __init__(self, filename, mode="a"):
        logging.StreamHandler.__init__(self, open(filename, mode))
        self.baseFilename = filename
        self.mode = mode

    def close(self):
        try:
            self.stream.close()
        except IOError:
            pass

    def reopen(self):
        self.close()
        self.stream = open(self.baseFilename, self.mode)

    def remove(self):
        try:
            os.remove(self.baseFilename)
        except (IOError, OSError):
            pass

class RawHandler:
    def emit(self, record):
        """
        Override the handler to not insert a linefeed during emit.
        """
        try:
            msg = self.format(record)
            try:
                self.stream.write(msg)
            except UnicodeError:
                self.stream.write(msg.encode("UTF-8"))
            except IOError, why:
                if why[0] == errno.EINTR:
                    pass
            else:
                self.flush()
        except:
            self.handleError(record)

class RawFileHandler(RawHandler, FileHandler):
    pass

class RawStreamHandler(RawHandler, logging.StreamHandler):
    def remove(self):
        pass

class RotatingRawFileHandler(RawFileHandler):
    def __init__(self, filename, mode='a', maxBytes=512*1024*1024,
                 backupCount=10):
        """
        Open the specified file and use it as the stream for logging.

        By default, the file grows indefinitely. You can specify particular
        values of maxBytes and backupCount to allow the file to rollover at
        a predetermined size.

        Rollover occurs whenever the current log file is nearly maxBytes in
        length. If backupCount is >= 1, the system will successively create
        new files with the same pathname as the base file, but with extensions
        ".1", ".2" etc. appended to it. For example, with a backupCount of 5
        and a base file name of "app.log", you would get "app.log",
        "app.log.1", "app.log.2", ... through to "app.log.5". The file being
        written to is always "app.log" - when it gets filled up, it is closed
        and renamed to "app.log.1", and if files "app.log.1", "app.log.2" etc.
        exist, then they are renamed to "app.log.2", "app.log.3" etc.
        respectively.

        If maxBytes is zero, rollover never occurs.
        """
        if maxBytes > 0:
            mode = 'a' # doesn't make sense otherwise!
        RawFileHandler.__init__(self, filename, mode)
        self.maxBytes = maxBytes
        self.backupCount = backupCount

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().
        """
        try:
            if self.shouldRollover(record):
                self.doRollover()
            RawFileHandler.emit(self, record)
        except:
            self.handleError(record)

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(self.baseFilename, dfn)
        self.stream = open(self.baseFilename, 'w')

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.
        """
        if self.maxBytes > 0:                   # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        return 0
    
def getLogger(filename, level, fmt, rotating=False,
              maxbytes=0, backups=0):
    import logging
    logger = logging.getLogger(filename)
    if rotating is False:
        hdlr = RawFileHandler(filename)
    else:
        hdlr = RotatingRawFileHandler(filename, 'a', maxbytes, backups)
    formatter = logging.Formatter(fmt)
    hdlr.setFormatter(formatter)
    logger.handlers = []
    logger.addHandler(hdlr)
    logger.setLevel(level)
    return logger

class Dummy:
    pass

class Options:

    uid = gid = None

    progname = sys.argv[0]
    configfile = None
    schemadir = None
    configroot = None

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
        self.add(None, None, "h", "help", self.help)
        self.add("configfile", None, "c:", "configure=")

    def help(self, dummy):
        """Print a long help message to stdout and exit(0).

        Occurrences of "%s" in are replaced by self.progname.
        """
        help = self.doc
        if help.find("%s") > 0:
            help = help.replace("%s", self.progname)
        print help,
        sys.exit(0)

    def usage(self, msg):
        """Print a brief error message to stderr and exit(2)."""
        sys.stderr.write("Error: %s\n" % str(msg))
        sys.stderr.write("For help, use %s -h\n" % self.progname)
        sys.exit(2)

    def remove(self,
               name=None,               # attribute name on self
               confname=None,           # dotted config path name
               short=None,              # short option name
               long=None,               # long option name
               ):
        """Remove all traces of name, confname, short and/or long."""
        if name:
            for n, cn in self.names_list[:]:
                if n == name:
                    self.names_list.remove((n, cn))
            if self.default_map.has_key(name):
                del self.default_map[name]
            if self.required_map.has_key(name):
                del self.required_map[name]
        if confname:
            for n, cn in self.names_list[:]:
                if cn == confname:
                    self.names_list.remove((n, cn))
        if short:
            key = "-" + short[0]
            if self.options_map.has_key(key):
                del self.options_map[key]
        if long:
            key = "--" + long
            if key[-1] == "=":
                key = key[:-1]
            if self.options_map.has_key(key):
                del self.options_map[key]

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
                setattr(self, name, arg)

        # Process environment variables
        for envvar in self.environ_map.keys():
            name, handler = self.environ_map[envvar]
            if name and getattr(self, name, None) is not None:
                continue
            if os.environ.has_key(envvar):
                value = os.environ[envvar]
                if handler is not None:
                    try:
                        value = handler(value)
                    except ValueError, msg:
                        self.usage("invalid environment value for %s %r: %s"
                                   % (envvar, value, msg))
                if name and value is not None:
                    setattr(self, name, value)

        if self.configfile is None:
            self.configfile = self.default_configfile()
        if self.configfile is not None:
            # Process config file
            try:
                self.read_config(self.configfile)
            except ValueError, msg:
                self.usage(str(msg))

        # Copy config options to attributes of self.  This only fills
        # in options that aren't already set from the command line.
        for name, confname in self.names_list:
            if confname and getattr(self, name) is None:
                parts = confname.split(".")
                obj = self.configroot
                for part in parts:
                    if obj is None:
                        break
                    # Here AttributeError is not a user error!
                    obj = getattr(obj, part)
                setattr(self, name, obj)

        # Process defaults
        for name, value in self.default_map.items():
            if getattr(self, name) is None:
                setattr(self, name, value)

        # Process required options
        for name, message in self.required_map.items():
            if getattr(self, name) is None:
                self.usage(message)

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
    httpserver = None
    unlink_socketfile = True
    TRACE = 5
    
    ANSI_ESCAPE_BEGIN = '\x1b['
    ANSI_TERMINATORS = ('H', 'f', 'A', 'B', 'C', 'D', 'R', 's', 'u', 'J', 
                        'K', 'h', 'l', 'p', 'm')    
    
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
                 existing_dirpath, default="supervisor")
        self.add("childlogdir", "supervisord.childlogdir", "q:", "childlogdir=",
                 existing_directory, default=tempfile.gettempdir())
        self.add("http_port", "supervisord.http_port", "w:", "http_port=",
                 SocketAddress, default=None)
        self.add("http_username", "supervisord.http_username", "g:",
                 "http_username=", str, default=None)
        self.add("http_password", "supervisord.http_password", "r:",
                 "http_password=", str, default=None)
        self.add("minfds", "supervisord.minfds",
                 "a:", "minfds=", int, default=1024)
        self.add("minprocs", "supervisord.minprocs",
                 "", "minprocs=", int, default=200)
        self.add("nocleanup", "supervisord.nocleanup",
                 "k", "nocleanup", flag=1, default=0)
        self.add("strip_ansi", "supervisord.strip_ansi",
                 "t", "strip_ansi", flag=1, default=0)
        self.add("sockchmod", "supervisord.sockchmod", "p:", "socket-mode=",
                 octal_type, default=0700)
        self.add("sockchown", "supervisord.sockchown", "o:", "socket-owner=",
                 dot_separated_user_group)
        self.add("environment", "supervisord.environment", "b:", "environment=",
                 dict_of_key_value_pairs)
        self.pidhistory = {}

    def getLogger(self, filename, level, fmt, rotating=False,
                  maxbytes=0, backups=0):
        return getLogger(filename, level, fmt, rotating, maxbytes,
                         backups)

    def default_configfile(self):
        """Return the name of the default config file, or None."""
        # This allows a default configuration file to be used without
        # affecting the -c command line option; setting self.configfile
        # before calling realize() makes the -C option unusable since
        # then realize() thinks it has already seen the option.  If no
        # -c is used, realize() will call this method to try to locate
        # a configuration file.
        config = '/etc/supervisord.conf'
        if not os.path.exists(config):
            self.usage('No config file found at default path "%s"; create '
                       'this file or use the -c option to specify a config '
                       'file at a different path' % config)
        return config

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

        if not self.logfile:
            logfile = os.path.abspath(section.logfile)
        else:
            logfile = os.path.abspath(self.logfile)

        self.logfile = logfile

        if not self.loglevel:
            self.loglevel = section.loglevel

        if not self.pidfile:
            self.pidfile = os.path.abspath(section.pidfile)
        else:
            self.pidfile = os.path.abspath(self.pidfile)

        self.process_group_configs = section.process_group_configs

        if not self.sockchown:
            self.sockchown = section.sockchown

        self.identifier = section.identifier

    def convert_sockchown(self, sockchown):
        # Convert chown stuff to uid/gid
        user = sockchown[0]
        group = sockchown[1]
        uid = name_to_uid(user)
        if uid is None:
            self.usage("No such sockchown user %s" % user)
        if group is None:
            gid = gid_for_uid(uid)
        else:
            gid = name_to_gid(group)
            if gid is None:
                self.usage("No such sockchown group %s" % group)
        return uid, gid

    def read_config(self, fp):
        section = self.configroot.supervisord
        if not hasattr(fp, 'read'):
            try:
                fp = open(fp, 'r')
            except (IOError, OSError):
                raise ValueError("could not find config file %s" % fp)
        parser = UnhosedConfigParser()
        parser.readfp(fp)

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

        http_port = get('http_port', None)
        if http_port is None:
            section.http_port = None
        else:
            section.http_port = SocketAddress(http_port)

        http_password = get('http_password', None)
        http_username = get('http_username', None)
        if http_password or http_username:
            if http_password is None:
                raise ValueError('Must specify http_password if '
                                 'http_username is specified')
            if http_username is None:
                raise ValueError('Must specify http_username if '
                                 'http_password is specified')
        section.http_password = http_password
        section.http_username = http_username

        section.nocleanup = boolean(get('nocleanup', 'false'))

        section.strip_ansi = boolean(get('strip_ansi', 'false'))
        
        sockchown = get('sockchown', None)
        if sockchown is None:
            section.sockchown = (-1, -1)
        else:
            try:
                section.sockchown = dot_separated_user_group(sockchown)
            except ValueError:
                raise ValueError('Invalid sockchown value %s' % sockchown)

        sockchmod = get('sockchmod', None)
        if sockchmod is None:
            section.sockchmod = 0700
        else:
            try:
                section.sockchmod = octal_type(sockchmod)
            except (TypeError, ValueError):
                raise ValueError('Invalid sockchmod value %s' % sockchmod)

        section.environment = dict_of_key_value_pairs(get('environment', ''))
        section.process_group_configs = self.process_groups_from_parser(parser)
        section.rpcinterface_factories = self.rpcinterfaces_from_parser(parser)
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
                                                        group_name)
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
            processes=self.processes_from_section(parser, section, program_name)
            groups.append(
                ProcessGroupConfig(self, program_name, priority, processes)
                )

        # process "event listener" homogeneous groups
        for section in all_sections:
            if not section.startswith('eventlistener:'):
                 continue
            pool_name = section.split(':', 1)[1]
            priority = integer(get(section, 'priority', 999))
            buffer_size = integer(get(section, 'buffer_size', 10))
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
                                                  listener=True)
            groups.append(
                EventListenerPoolConfig(self, pool_name, priority, processes,
                                        buffer_size, pool_events)
                )

        groups.sort()
        return groups

    def processes_from_section(self, parser, section, group_name,
                               listener=False):
        programs = []
        get = parser.saneget
        program_name = section.split(':', 1)[1]

        priority = integer(get(section, 'priority', 999))
        autostart = boolean(get(section, 'autostart', 'true'))
        autorestart = boolean(get(section, 'autorestart', 'true'))
        startsecs = integer(get(section, 'startsecs', 1))
        startretries = integer(get(section, 'startretries', 3))
        uid = name_to_uid(get(section, 'user', None))
        stopsignal = signal_number(get(section, 'stopsignal', 'TERM'))
        stopwaitsecs = integer(get(section, 'stopwaitsecs', 10))
        exitcodes = list_of_exitcodes(get(section, 'exitcodes', '0,2'))
        redirect_stderr = boolean(get(section, 'redirect_stderr','false'))
        numprocs = integer(get(section, 'numprocs', 1))
        process_name = get(section, 'process_name', '%(program_name)s')
        environment_str = get(section, 'environment', '')

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

        for n in ('stdout_logfile', 'stderr_logfile'):
            lf_name = logfile_name(get(section, n, None))
            mb_key = '%s_maxbytes' % n
            maxbytes = byte_size(get(section, mb_key, '50MB'))
            if not maxbytes and lf_name is Automatic:
                self.logger.warn(
                    'For [%s], AUTO logging used for %s without '
                    'rollover, set maxbytes > 0 to avoid filling up '
                    'filesystem unintentionally' % (section, n))
                
        for process_num in range(0, numprocs):

            expansions = {'process_num':process_num,
                          'program_name':program_name,
                          'group_name':group_name}

            environment = dict_of_key_value_pairs(
                expand(environment_str, expansions, 'environment'))

            logfiles = {}

            for k in ('stdout', 'stderr'):
                for n in ('%s_logfile' % k, '%s_capturefile' % k):
                    val = logfile_name(get(section, n, None))
                    if isinstance(val, basestring):
                        val = expand(val, expansions, n)
                        
                    logfiles[n] = val

                bu_key = '%s_logfile_backups' % k
                backups = integer(get(section, bu_key, 10))
                logfiles[bu_key] = backups

                mb_key = '%s_logfile_maxbytes' % k
                maxbytes = byte_size(get(section, mb_key, '50MB'))
                logfiles[mb_key] = maxbytes

            if listener:
                klass = EventListenerConfig
            else:
                klass = ProcessConfig

            pconfig = klass(
                self,
                name=expand(process_name, expansions, 'process_name'),
                command=expand(command, expansions, 'command'),
                priority=priority,
                autostart=autostart,
                autorestart=autorestart,
                startsecs=startsecs,
                startretries=startretries,
                uid=uid,
                stdout_logfile=logfiles['stdout_logfile'],
                stdout_capturefile=logfiles['stdout_capturefile'],
                stdout_logfile_backups=logfiles['stdout_logfile_backups'],
                stdout_logfile_maxbytes=logfiles['stdout_logfile_maxbytes'],
                stderr_logfile=logfiles['stderr_logfile'],
                stderr_capturefile=logfiles['stderr_capturefile'],
                stderr_logfile_backups=logfiles['stderr_logfile_backups'],
                stderr_logfile_maxbytes=logfiles['stderr_logfile_maxbytes'],
                stopsignal=stopsignal,
                stopwaitsecs=stopwaitsecs,
                exitcodes=exitcodes,
                redirect_stderr=redirect_stderr,
                environment=environment)

            programs.append(pconfig)

        programs.sort() # asc by priority
        return programs

    def rpcinterfaces_from_parser(self, parser):
        factories = []
        factory_key = 'supervisor.rpcinterface_factory'

        for section in parser.sections():
            if not section.startswith('rpcinterface:'):
                continue
            options = parser.options(section)
            name = section.split(':', 1)[1]
            realoptions = []
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
            self.logger.debug("supervisord forked; parent exiting")
            os._exit(0)
        # Child
        self.logger.info("daemonizing the process")
        if self.directory:
            try:
                os.chdir(self.directory)
            except os.error, err:
                self.logger.warn("can't chdir into %r: %s"
                                 % (self.directory, err))
            else:
                self.logger.info("set current directory: %r"
                                 % self.directory)
        os.close(0)
        sys.stdin = sys.__stdin__ = open("/dev/null")
        os.close(1)
        sys.stdout = sys.__stdout__ = open("/dev/null", "w")
        os.close(2)
        sys.stderr = sys.__stderr__ = open("/dev/null", "w")
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
        except (IOError, os.error):
            self.logger.critical('could not write pidfile %s' % self.pidfile)
        else:
            self.logger.info('supervisord started with pid %s' % pid)
                
    def cleanup(self):
        try:
            if self.http_port is not None:
                if self.http_port.family == socket.AF_UNIX:
                    if self.httpserver is not None:
                        if self.unlink_socketfile:
                            socketname = self.http_port.address
                            try:
                                os.unlink(socketname)
                            except os.error:
                                pass
        except os.error:
            pass
        try:
            os.unlink(self.pidfile)
        except os.error:
            pass

    def setsignals(self):
        signal.signal(signal.SIGTERM, self.sigreceiver)
        signal.signal(signal.SIGINT, self.sigreceiver)
        signal.signal(signal.SIGQUIT, self.sigreceiver)
        signal.signal(signal.SIGHUP, self.sigreceiver)
        signal.signal(signal.SIGCHLD, self.sigreceiver)
        signal.signal(signal.SIGUSR2, self.sigreceiver)

    def sigreceiver(self, sig, frame):
        self.signal = sig

    def openhttpserver(self, supervisord):
        from http import make_http_server
        try:
            self.httpserver = make_http_server(self, supervisord)
        except socket.error, why:
            if why[0] == errno.EADDRINUSE:
                port = str(self.http_port.address)
                self.usage('Another program is already listening on '
                           'the port that our HTTP server is '
                           'configured to use (%s).  Shut this program '
                           'down first before starting supervisord. ' %
                           port)
            self.unlink_socketfile = False
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
            self.logger.info('Could not clear childlog dir')
            return
        
        for filename in filenames:
            if fnre.match(filename):
                pathname = os.path.join(childlogdir, filename)
                try:
                    os.remove(pathname)
                except (os.error, IOError):
                    self.logger.info('Failed to clean up %r' % pathname)

    def get_socket_map(self):
        return asyncore.socket_map

    def cleanup_fds(self):
        # try to close any unused file descriptors to prevent leakage.
        # we start at the "highest" descriptor in the asyncore socket map
        # because this might be called remotely and we don't want to close
        # the internet channel during this call.
        asyncore_fds = asyncore.socket_map.keys()
        start = 5
        if asyncore_fds:
            start = max(asyncore_fds) + 1
        for x in range(start, self.minfds):
            try:
                os.close(x)
            except os.error:
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

    def stripEscapes(self, string):
        """
        Remove all ANSI color escapes from the given string.
        """
        result = ''
        show = 1
        i = 0
        L = len(string)
        while i < L:
            if show == 0 and string[i] in self.ANSI_TERMINATORS:
                show = 1
            elif show:
                n = string.find(self.ANSI_ESCAPE_BEGIN, i)
                if n == -1:
                    return result + string[i:]
                else:
                    result = result + string[i:n]
                    i = n
                    show = 0
            i = i + 1
        return result

    def waitpid(self):
        # need pthread_sigmask here to avoid concurrent sigchild, but
        # Python doesn't offer it as it's not standard across UNIX versions.
        # there is still a race condition here; we can get a sigchild while
        # we're sitting in the waitpid call.
        try:
            pid, sts = os.waitpid(-1, os.WNOHANG)
        except os.error, why:
            err = why[0]
            if err not in (errno.ECHILD, errno.EINTR):
                self.logger.info(
                    'waitpid error; a process may not be cleaned up properly')
            if err == errno.EINTR:
                self.logger.debug('EINTR during reap')
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

    def make_logger(self, critical_messages, info_messages):
        # must be called after realize() and after supervisor does setuid()
        format =  '%(asctime)s %(levelname)s %(message)s\n'
        logging.addLevelName(logging.CRITICAL, 'CRIT')
        logging.addLevelName(logging.DEBUG, 'DEBG')
        logging.addLevelName(logging.INFO, 'INFO')
        logging.addLevelName(logging.WARN, 'WARN')
        logging.addLevelName(logging.ERROR, 'ERRO')
        logging.addLevelName(self.TRACE, 'TRAC')
        self.logger = self.getLogger(
            self.logfile,
            self.loglevel,
            format,
            rotating=True,
            maxbytes=self.logfile_maxbytes,
            backups=self.logfile_backups,
            )
        if self.nodaemon:
            stdout_handler = RawStreamHandler(sys.stdout)
            formatter = logging.Formatter(format)
            stdout_handler.setFormatter(formatter)
            self.logger.addHandler(stdout_handler)
        for msg in critical_messages:
            self.logger.critical(msg)
        for msg in info_messages:
            self.logger.info(msg)

    def close_fd(self, fd):
        try:
            os.close(fd)
        except os.error:
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
        fd, filename = tempfile.mkstemp(suffix, prefix, dir)
        os.close(fd)
        return filename

    def remove(self, path):
        os.remove(path)

    def exists(self, path):
        return os.path.exists(path)

    def _exit(self, code):
        os._exit(code)

    def get_path(self):
        """Return a list corresponding to $PATH, or a default."""
        path = ["/bin", "/usr/bin", "/usr/local/bin"]
        if os.environ.has_key("PATH"):
            p = os.environ["PATH"]
            if p:
                path = p.split(os.pathsep)
        return path

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

    def __init__(self):
        Options.__init__(self)
        self.configroot = Dummy()
        self.configroot.supervisorctl = Dummy()
        self.configroot.supervisorctl.interactive = None
        self.configroot.supervisorctl.prompt = None
        self.configroot.supervisorctl.serverurl = None
        self.configroot.supervisorctl.username = None
        self.configroot.supervisorctl.password = None


        self.add("interactive", "supervisorctl.interactive", "i",
                 "interactive", flag=1, default=0)
        self.add("prompt", "supervisorctl.prompt", default="supervisor")
        self.add("serverurl", "supervisorctl.serverurl", "s:", "serverurl=",
                 url, default="http://localhost:9001")
        self.add("username", "supervisorctl.username", "u:", "username=")
        self.add("password", "supervisorctl.password", "p:", "password=")

    def realize(self, *arg, **kw):
        os.environ['SUPERVISOR_ENABLED'] = '1'
        Options.realize(self, *arg, **kw)
        if not self.args:
            self.interactive = 1

    def default_configfile(self):
        """Return the name of the default config file, or None."""
        config = '/etc/supervisord.conf'
        if not os.path.exists(config):
            self.usage('No config file found at default path "%s"; create '
                       'this file or use the -c option to specify a config '
                       'file at a different path' % config)
        return config

    def read_config(self, fp):
        section = self.configroot.supervisorctl
        if not hasattr(fp, 'read'):
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
        section.serverurl = config.getdefault('serverurl',
                                              'http://localhost:9001')
        section.prompt = config.getdefault('prompt', 'supervisor')
        section.username = config.getdefault('username', None)
        section.password = config.getdefault('password', None)
        
        return section

    def getServerProxy(self):
        # mostly put here for unit testing
        return xmlrpclib.ServerProxy(
            # dumbass ServerProxy won't allow us to pass in a non-HTTP url,
            # so we fake the url we pass into it and always use the transport's
            # 'serverurl' to figure out what to attach to
            'http://127.0.0.1',
            transport = BasicAuthTransport(self.username,
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
    def __init__(self, options, name, command, priority, autostart,
                 autorestart, startsecs, startretries, uid,
                 stdout_logfile, stdout_capturefile,
                 stdout_logfile_backups, stdout_logfile_maxbytes,
                 stderr_logfile, stderr_capturefile,
                 stderr_logfile_backups, stderr_logfile_maxbytes,
                 stopsignal, stopwaitsecs, exitcodes, redirect_stderr,
                 environment=None):
        self.options = options
        self.name = name
        self.command = command
        self.priority = priority
        self.autostart = autostart
        self.autorestart = autorestart
        self.startsecs = startsecs
        self.startretries = startretries
        self.uid = uid
        self.stdout_logfile = stdout_logfile
        self.stdout_capturefile = stdout_capturefile
        self.stdout_logfile_backups = stdout_logfile_backups
        self.stdout_logfile_maxbytes = stdout_logfile_maxbytes
        self.stderr_logfile = stderr_logfile
        self.stderr_capturefile = stderr_capturefile
        self.stderr_logfile_backups = stderr_logfile_backups
        self.stderr_logfile_maxbytes = stderr_logfile_maxbytes
        self.stopsignal = stopsignal
        self.stopwaitsecs = stopwaitsecs
        self.exitcodes = exitcodes
        self.redirect_stderr = redirect_stderr
        self.environment = environment

    def create_autochildlogs(self):
        # temporary logfiles which are erased at start time
        get_autoname = self.options.get_autochildlog_name
        sid = self.options.identifier
        name = self.name
        if self.stdout_logfile is Automatic:
            self.stdout_logfile = get_autoname(name, sid, 'stdout')
        if self.stderr_logfile is Automatic:
            self.stderr_logfile = get_autoname(name, sid, 'stderr')
        if self.stdout_capturefile is Automatic:
            self.stdout_capturefile = get_autoname(name, sid, 'stdout_capture')
        if self.stderr_capturefile is Automatic:
            self.stderr_capturefile = get_autoname(name, sid, 'stderr_capture')
            
    def make_process(self):
        from supervisor.process import Subprocess
        return Subprocess(self)

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
        from supervisor import events
        if stdout_fd is not None:
            etype = events.ProcessCommunicationStdoutEvent
            dispatchers[stdout_fd] = PEventListenerDispatcher(proc, 'stdout',
                                                              stdout_fd)
        if stderr_fd is not None:
            etype = events.ProcessCommunicationStderrEvent
            dispatchers[stderr_fd] = PEventListenerDispatcher(proc, 'stderr',
                                                              stderr_fd)
        if stdin_fd is not None:
            dispatchers[stdin_fd] = PInputDispatcher(proc, 'stdin', stdin_fd)
        return dispatchers, p

class ProcessGroupConfig(Config):
    def __init__(self, options, name, priority, process_configs):
        self.options = options
        self.name = name
        self.priority = priority
        self.process_configs = process_configs

    def after_setuid(self):
        for config in self.process_configs:
            config.create_autochildlogs()

    def make_group(self):
        from supervisor.process import ProcessGroup
        return ProcessGroup(self)

class EventListenerPoolConfig(Config):
    def __init__(self, options, name, priority, process_configs, buffer_size,
                 pool_events):
        self.options = options
        self.name = name
        self.priority = priority
        self.process_configs = process_configs
        self.buffer_size = buffer_size
        self.pool_events = pool_events

    def after_setuid(self):
        for config in self.process_configs:
            config.create_autochildlogs()

    def make_group(self):
        from supervisor.process import EventListenerPool
        return EventListenerPool(self)

class BasicAuthTransport(xmlrpclib.Transport):
    """ A transport that understands basic auth and UNIX domain socket
    URLs """
    _use_datetime = 0 # python 2.5 fwd compatibility
    def __init__(self, username=None, password=None, serverurl=None):
        self.username = username
        self.password = password
        self.verbose = False
        self.serverurl = serverurl

    def request(self, host, handler, request_body, verbose=False):
        # issue XML-RPC request

        h = self.make_connection(host)
        if verbose:
            h.set_debuglevel(1)

        h.putrequest("POST", handler)

        # required by HTTP/1.1
        h.putheader("Host", host)

        # required by XML-RPC
        h.putheader("User-Agent", self.user_agent)
        h.putheader("Content-Type", "text/xml")
        h.putheader("Content-Length", str(len(request_body)))

        # basic auth
        if self.username is not None and self.password is not None:
            unencoded = "%s:%s" % (self.username, self.password)
            encoded = unencoded.encode('base64')
            encoded = encoded.replace('\012', '')
            h.putheader("Authorization", "Basic %s" % encoded)

        h.endheaders()

        if request_body:
            h.send(request_body)

        errcode, errmsg, headers = h.getreply()

        if errcode != 200:
            raise xmlrpclib.ProtocolError(
                host + handler,
                errcode, errmsg,
                headers
                )

        return self.parse_response(h.getfile())

    def make_connection(self, host):
        serverurl = self.serverurl
        if not serverurl.startswith('http'):
            if serverurl.startswith('unix://'):
                serverurl = serverurl[7:]
            http = UnixStreamHTTP(serverurl)
            return http
        else:            
            type, uri = urllib.splittype(serverurl)
            host, path = urllib.splithost(uri)
            hostpath = host+path
            return xmlrpclib.Transport.make_connection(self, hostpath)
            
class UnixStreamHTTPConnection(httplib.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # we abuse the host parameter as the socketname
        self.sock.connect(self.host)

class UnixStreamHTTP(httplib.HTTP):
    _connection_class = UnixStreamHTTPConnection

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
    except (os.error, IOError):
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

    except (os.error, IOError):
        return ['', offset, False]

def gettags(comment):
    """ Parse documentation strings into JavaDoc-like tokens """

    tags = []

    tag = None
    datatype = None
    name = None
    tag_lineno = lineno = 0
    tag_text = []

    for line in comment.split('\n'):
        line = line.strip()
        if line.startswith("@"):
            tags.append((tag_lineno, tag, datatype, name, '\n'.join(tag_text)))
            parts = line.split(None, 3)
            if len(parts) == 1:
                datatype = ''
                name = ''
                tag_text = []
            elif len(parts) == 2:
                datatype = parts[1]
                name = ''
                tag_text = []
            elif len(parts) == 3:
                datatype = parts[1]
                name = parts[2]
                tag_text = []
            elif len(parts) == 4:
                datatype = parts[1]
                name = parts[2]
                tag_text = [parts[3].lstrip()]
            tag = parts[0][1:]
            tag_lineno = lineno
        else:
            if line:
                tag_text.append(line)
        lineno = lineno + 1

    tags.append((tag_lineno, tag, datatype, name, '\n'.join(tag_text)))

    return tags


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

