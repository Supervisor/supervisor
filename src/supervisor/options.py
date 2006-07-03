import ConfigParser
import getopt
import os
import datatypes
import logging
import sys
import tempfile
import socket
import errno
import signal
import re
import xmlrpclib
import httplib
import urllib

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
    AUTOMATIC = []
    
    def __init__(self):
        Options.__init__(self)
        self.configroot = Dummy()
        self.configroot.supervisord = Dummy()
        
        self.add("backofflimit", "supervisord.backofflimit",
                 "b:", "backofflimit=", int, default=3)
        self.add("nodaemon", "supervisord.nodaemon", "n", "nodaemon", flag=1,
                 default=0)
        self.add("forever", "supervisord.forever", "f", "forever",
                 flag=1, default=0)
        self.add("user", "supervisord.user", "u:", "user=")
        self.add("umask", "supervisord.umask", "m:", "umask=",
                 datatypes.octal_type, default='022')
        self.add("directory", "supervisord.directory", "d:", "directory=",
                 datatypes.existing_directory)
        self.add("logfile", "supervisord.logfile", "l:", "logfile=",
                 datatypes.existing_dirpath, default="supervisord.log")
        self.add("logfile_maxbytes", "supervisord.logfile_maxbytes",
                 "y:", "logfile_maxbytes=", datatypes.byte_size,
                 default=50 * 1024 * 1024) # 50MB
        self.add("logfile_backups", "supervisord.logfile_backups",
                 "z:", "logfile_backups=", datatypes.integer, default=10)
        self.add("loglevel", "supervisord.loglevel", "e:", "loglevel=",
                 datatypes.logging_level, default="info")
        self.add("pidfile", "supervisord.pidfile", "j:", "pidfile=",
                 datatypes.existing_dirpath, default="supervisord.pid")
        self.add("identifier", "supervisord.identifier", "i:", "identifier=",
                 datatypes.existing_dirpath, default="supervisor")
        self.add("childlogdir", "supervisord.childlogdir", "q:", "childlogdir=",
                 datatypes.existing_directory, default=tempfile.gettempdir())
        self.add("http_port", "supervisord.http_port", "w:", "http_port=",
                 datatypes.SocketAddress, default=None)
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
	self.add("sockchmod", "supervisord.sockchmod", "p:", "socket-mode=",
		 datatypes.octal_type, default=0700)
	self.add("sockchown", "supervisord.sockchown", "o:", "socket-owner=",
		 datatypes.dot_separated_user_group)

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
        import socket

        # Additional checking of user option; set uid and gid
        if self.user is not None:
            import pwd
	    uid = datatypes.name_to_uid(self.user)
            if uid is None:
                self.usage("No such user %s" % self.user)
            self.uid = uid
            self.gid = datatypes.gid_for_uid(uid)

        if not self.logfile:
            logfile = os.path.abspath(self.configroot.supervisord.logfile)
        else:
            logfile = os.path.abspath(self.logfile)

        self.logfile = logfile

        if not self.loglevel:
            self.loglevel = self.configroot.supervisord.loglevel

        if not self.pidfile:
            self.pidfile = os.path.abspath(self.configroot.supervisord.pidfile)
        else:
            self.pidfile = os.path.abspath(self.pidfile)

        self.programs = self.configroot.supervisord.programs

        if not self.sockchown:
            self.sockchown = self.configroot.supervisord.sockchown

        self.identifier = self.configroot.supervisord.identifier

        if self.nodaemon:
            self.daemon = False

    def convert_sockchown(self, sockchown):
        # Convert chown stuff to uid/gid
        user = sockchown[0]
        group = sockchown[1]
        uid = datatypes.name_to_uid(user)
        if uid is None:
            self.usage("No such sockchown user %s" % user)
        if group is None:
            gid = datatypes.gid_for_uid(uid)
        else:
            gid = datatypes.name_to_gid(group)
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
        config = UnhosedConfigParser()
        config.readfp(fp)
        sections = config.sections()
        if not 'supervisord' in sections:
            raise ValueError, '.ini file does not include supervisord section'
        minfds = config.getdefault('minfds', 1024)
        section.minfds = datatypes.integer(minfds)

        minprocs = config.getdefault('minprocs', 200)
        section.minprocs = datatypes.integer(minprocs)
        
        directory = config.getdefault('directory', None)
        if directory is None:
            section.directory = None
        else:
            directory = datatypes.existing_directory(directory)
            section.directory = directory

        backofflimit = config.getdefault('backofflimit', 3)
        try:
            limit = datatypes.integer(backofflimit)
        except:
            raise ValueError("backofflimit is not an integer: %s"
                             % backofflimit)
        section.backofflimit = limit
        forever = config.getdefault('forever', 'false')
        section.forever = datatypes.boolean(forever)
        user = config.getdefault('user', None)
        section.user = user

        umask = datatypes.octal_type(config.getdefault('umask', '022'))
        section.umask = umask

        logfile = config.getdefault('logfile', 'supervisord.log')
        logfile = datatypes.existing_dirpath(logfile)
        section.logfile = logfile

        logfile_maxbytes = config.getdefault('logfile_maxbytes', '50MB')
        logfile_maxbytes = datatypes.byte_size(logfile_maxbytes)
        section.logfile_maxbytes = logfile_maxbytes

        logfile_backups = config.getdefault('logfile_backups', 10)
        logfile_backups = datatypes.integer(logfile_backups)
        section.logfile_backups = logfile_backups

        loglevel = config.getdefault('loglevel', 'info')
        loglevel = datatypes.logging_level(loglevel)
        section.loglevel = loglevel

        pidfile = config.getdefault('pidfile', 'supervisord.pid')
        pidfile = datatypes.existing_dirpath(pidfile)
        section.pidfile = pidfile

        identifier = config.getdefault('identifier', 'supervisor')
        section.identifier = identifier

        nodaemon = config.getdefault('nodaemon', 'false')
        section.nodaemon = datatypes.boolean(nodaemon)

        childlogdir = config.getdefault('childlogdir', tempfile.gettempdir())
        childlogdir = datatypes.existing_directory(childlogdir)
        section.childlogdir = childlogdir

        http_port = config.getdefault('http_port', None)
        if http_port is None:
            section.http_port = None
        else:
            section.http_port = datatypes.SocketAddress(http_port)

        http_password = config.getdefault('http_password', None)
        http_username = config.getdefault('http_username', None)
        if http_password or http_username:
            if http_password is None:
                raise ValueError('Must specify http_password if '
                                 'http_username is specified')
            if http_username is None:
                raise ValueError('Must specify http_username if '
                                 'http_password is specified')
        section.http_password = http_password
        section.http_username = http_username

        nocleanup = config.getdefault('nocleanup', 'false')
        section.nocleanup = datatypes.boolean(nocleanup)

        sockchown = config.getdefault('sockchown', None)
        if sockchown is None:
            section.sockchown = (-1, -1)
        else:
            try:
                section.sockchown = datatypes.dot_separated_user_group(
                    sockchown)
            except ValueError:
                raise ValueError('Invalid sockchown value %s' % sockchown)

        sockchmod = config.getdefault('sockchmod', None)
        if sockchmod is None:
            section.sockchmod = 0700
        else:
            try:
                section.sockchmod = datatypes.octal_type(sockchmod)
            except (TypeError, ValueError):
                raise ValueError('Invalid sockchmod value %s' % sockchmod)

        section.programs = self.programs_from_config(config)
        return section

    def programs_from_config(self, config):
        programs = []

        for section in config.sections():
            if not section.startswith('program:'):
                continue
            name = section.split(':', 1)[1]
            command = config.saneget(section, 'command', None)
            if command is None:
                raise ValueError, (
                    'program section %s does not specify a command' )
            priority = config.saneget(section, 'priority', 999)
            priority = datatypes.integer(priority)
            autostart = config.saneget(section, 'autostart', 'true')
            autostart = datatypes.boolean(autostart)
            autorestart = config.saneget(section, 'autorestart', 'true')
            autorestart = datatypes.boolean(autorestart)
            uid = config.saneget(section, 'user', None)
            if uid is not None:
                uid = datatypes.name_to_uid(uid)
            logfile = config.saneget(section, 'logfile', None)
            if logfile in ('NONE', 'OFF'):
                logfile = None
            elif logfile in (None, 'AUTO'):
                logfile = self.AUTOMATIC
            else:
                logfile = datatypes.existing_dirpath(logfile)
            logfile_backups = config.saneget(section, 'logfile_backups', 1)
            logfile_backups = datatypes.integer(logfile_backups)
            logfile_maxbytes = config.saneget(section, 'logfile_maxbytes',
                                              datatypes.byte_size('5MB'))
            logfile_maxbytes = datatypes.integer(logfile_maxbytes)
            stopsignal = config.saneget(section, 'stopsignal', signal.SIGTERM)
            stopsignal = datatypes.signal(stopsignal)
            exitcodes = config.saneget(section, 'exitcodes', '0,2')
            try:
                exitcodes = datatypes.list_of_ints(exitcodes)
            except:
                raise ValueError("exitcodes must be a list of ints e.g. 1,2")
            log_stderr = config.saneget(section, 'log_stderr', 'false')
            log_stderr = datatypes.boolean(log_stderr)
            pconfig = ProcessConfig(name=name, command=command,
                                    priority=priority, autostart=autostart,
                                    autorestart=autorestart, uid=uid,
                                    logfile=logfile,
                                    logfile_backups=logfile_backups,
                                    logfile_maxbytes=logfile_maxbytes,
                                    stopsignal=stopsignal,
                                    exitcodes=exitcodes,
                                    log_stderr=log_stderr)
            programs.append(pconfig)

        programs.sort() # asc by priority
        return programs

    def clear_childlogdir(self):
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

    def make_logger(self, critical_messages, info_messages):
        # must be called after realize() and after supervisor does setuid()
        format =  '%(asctime)s %(levelname)s %(message)s\n'
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
                 datatypes.url,
                 default="http://localhost:9001")
        self.add("username", "supervisorctl.username", "u:", "username=")
        self.add("password", "supervisorctl.password", "p:", "password=")

    def realize(self, *arg, **kw):
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

class ProcessConfig:
    def __init__(self, name, command, priority, autostart, autorestart,
                 uid, logfile, logfile_backups, logfile_maxbytes, stopsignal,
                 exitcodes, log_stderr):
        self.name = name
        self.command = command
        self.priority = priority
        self.autostart = autostart
        self.autorestart = autorestart
        self.uid = uid
        self.logfile = logfile
        self.logfile_backups = logfile_backups
        self.logfile_maxbytes = logfile_maxbytes
        self.stopsignal = stopsignal
        self.exitcodes = exitcodes
        self.log_stderr = log_stderr

    def __cmp__(self, other):
        return cmp(self.priority, other.priority)
    
class BasicAuthTransport(xmlrpclib.Transport):
    """ A transport that understands basic auth and UNIX domain socket
    URLs """
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
