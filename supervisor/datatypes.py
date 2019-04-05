import grp
import os
import pwd
import signal
import socket
import shlex

from supervisor.compat import urlparse
from supervisor.compat import long
from supervisor.loggers import getLevelNumByDescription

def process_or_group_name(name):
    """Ensures that a process or group name is not created with
       characters that break the eventlistener protocol or web UI URLs"""
    s = str(name).strip()
    for character in ' :/':
        if character in s:
            raise ValueError("Invalid name: %r because of character: %r" % (name, character))
    return s

def integer(value):
    try:
        return int(value)
    except (ValueError, OverflowError):
        return long(value) # why does this help ValueError? (CM)

TRUTHY_STRINGS = ('yes', 'true', 'on', '1')
FALSY_STRINGS  = ('no', 'false', 'off', '0')

def boolean(s):
    """Convert a string value to a boolean value."""
    ss = str(s).lower()
    if ss in TRUTHY_STRINGS:
        return True
    elif ss in FALSY_STRINGS:
        return False
    else:
        raise ValueError("not a valid boolean value: " + repr(s))

def list_of_strings(arg):
    if not arg:
        return []
    try:
        return [x.strip() for x in arg.split(',')]
    except:
        raise ValueError("not a valid list of strings: " + repr(arg))

def list_of_ints(arg):
    if not arg:
        return []
    else:
        try:
            return list(map(int, arg.split(",")))
        except:
            raise ValueError("not a valid list of ints: " + repr(arg))

def list_of_exitcodes(arg):
    try:
        vals = list_of_ints(arg)
        for val in vals:
            if (val > 255) or (val < 0):
                raise ValueError('Invalid exit code "%s"' % val)
        return vals
    except:
        raise ValueError("not a valid list of exit codes: " + repr(arg))

def dict_of_key_value_pairs(arg):
    """ parse KEY=val,KEY2=val2 into {'KEY':'val', 'KEY2':'val2'}
        Quotes can be used to allow commas in the value
    """
    lexer = shlex.shlex(str(arg))
    lexer.wordchars += '/.+-():'

    tokens = list(lexer)
    tokens_len = len(tokens)

    D = {}
    i = 0
    while i < tokens_len:
        k_eq_v = tokens[i:i+3]
        if len(k_eq_v) != 3 or k_eq_v[1] != '=':
            raise ValueError(
                "Unexpected end of key/value pairs in value '%s'" % arg)
        D[k_eq_v[0]] = k_eq_v[2].strip('\'"')
        i += 4
    return D

class Automatic:
    pass

LOGFILE_NONES = ('none', 'off', None)
LOGFILE_AUTOS = (Automatic, 'auto')

def logfile_name(val):
    if hasattr(val, 'lower'):
        coerced = val.lower()
    else:
        coerced = val

    if coerced in LOGFILE_NONES:
        return None
    elif coerced in LOGFILE_AUTOS:
        return Automatic
    else:
        return existing_dirpath(val)

class RangeCheckedConversion:
    """Conversion helper that range checks another conversion."""

    def __init__(self, conversion, min=None, max=None):
        self._min = min
        self._max = max
        self._conversion = conversion

    def __call__(self, value):
        v = self._conversion(value)
        if self._min is not None and v < self._min:
            raise ValueError("%s is below lower bound (%s)"
                             % (repr(v), repr(self._min)))
        if self._max is not None and v > self._max:
            raise ValueError("%s is above upper bound (%s)"
                             % (repr(v), repr(self._max)))
        return v

port_number = RangeCheckedConversion(integer, min=1, max=0xffff).__call__

def inet_address(s):
    # returns (host, port) tuple
    host = ''
    if ":" in s:
        host, s = s.split(":", 1)
        if not s:
            raise ValueError("no port number specified in %r" % s)
        port = port_number(s)
        host = host.lower()
    else:
        try:
            port = port_number(s)
        except ValueError:
            raise ValueError("not a valid port number: %r " %s)
    if not host or host == '*':
        host = ''
    return host, port

class SocketAddress:
    def __init__(self, s):
        # returns (family, address) tuple
        if "/" in s or s.find(os.sep) >= 0 or ":" not in s:
            self.family = getattr(socket, "AF_UNIX", None)
            self.address = s
        else:
            self.family = socket.AF_INET
            self.address = inet_address(s)

class SocketConfig:
    """ Abstract base class which provides a uniform abstraction
    for TCP vs Unix sockets """
    url = '' # socket url
    addr = None #socket addr
    backlog = None # socket listen backlog

    def __repr__(self):
        return '<%s at %s for %s>' % (self.__class__,
                                      id(self),
                                      self.url)

    def __str__(self):
        return str(self.url)

    def __eq__(self, other):
        if not isinstance(other, SocketConfig):
            return False

        if self.url != other.url:
            return False

        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def get_backlog(self):
        return self.backlog

    def addr(self): # pragma: no cover
        raise NotImplementedError

    def create_and_bind(self): # pragma: no cover
        raise NotImplementedError

class InetStreamSocketConfig(SocketConfig):
    """ TCP socket config helper """

    host = None # host name or ip to bind to
    port = None # integer port to bind to

    def __init__(self, host, port, **kwargs):
        self.host = host.lower()
        self.port = port_number(port)
        self.url = 'tcp://%s:%d' % (self.host, self.port)
        self.backlog = kwargs.get('backlog', None)

    def addr(self):
        return self.host, self.port

    def create_and_bind(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(self.addr())
        except:
            sock.close()
            raise
        return sock

class UnixStreamSocketConfig(SocketConfig):
    """ Unix domain socket config helper """

    path = None # Unix domain socket path
    mode = None # Unix permission mode bits for socket
    owner = None # Tuple (uid, gid) for Unix ownership of socket
    sock = None # socket object

    def __init__(self, path, **kwargs):
        self.path = path
        self.url = 'unix://%s' % path
        self.mode = kwargs.get('mode', None)
        self.owner = kwargs.get('owner', None)
        self.backlog = kwargs.get('backlog', None)

    def addr(self):
        return self.path

    def create_and_bind(self):
        if os.path.exists(self.path):
            os.unlink(self.path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(self.addr())
            self._chown()
            self._chmod()
        except:
            sock.close()
            if os.path.exists(self.path):
                os.unlink(self.path)
            raise
        return sock

    def get_mode(self):
        return self.mode

    def get_owner(self):
        return self.owner

    def _chmod(self):
        if self.mode is not None:
            try:
                os.chmod(self.path, self.mode)
            except Exception as e:
                raise ValueError("Could not change permissions of socket "
                                    + "file: %s" % e)

    def _chown(self):
        if self.owner is not None:
            try:
                os.chown(self.path, self.owner[0], self.owner[1])
            except Exception as e:
                raise ValueError("Could not change ownership of socket file: "
                                    + "%s" % e)

def colon_separated_user_group(arg):
    """ Find a user ID and group ID from a string like 'user:group'.  Returns
        a tuple (uid, gid).  If the string only contains a user like 'user'
        then (uid, -1) will be returned.  Raises ValueError if either
        the user or group can't be resolved to valid IDs on the system. """
    try:
        parts = arg.split(':', 1)
        if len(parts) == 1:
            uid = name_to_uid(parts[0])
            gid = -1
        else:
            uid = name_to_uid(parts[0])
            gid = name_to_gid(parts[1])
        return (uid, gid)
    except:
        raise ValueError('Invalid user:group definition %s' % arg)

def name_to_uid(name):
    """ Find a user ID from a string containing a user name or ID.
        Raises ValueError if the string can't be resolved to a valid
        user ID on the system. """
    try:
        uid = int(name)
    except ValueError:
        try:
            pwdrec = pwd.getpwnam(name)
        except KeyError:
            raise ValueError("Invalid user name %s" % name)
        uid = pwdrec[2]
    else:
        try:
            pwd.getpwuid(uid) # check if uid is valid
        except KeyError:
            raise ValueError("Invalid user id %s" % name)
    return uid

def name_to_gid(name):
    """ Find a group ID from a string containing a group name or ID.
        Raises ValueError if the string can't be resolved to a valid
        group ID on the system. """
    try:
        gid = int(name)
    except ValueError:
        try:
            grprec = grp.getgrnam(name)
        except KeyError:
            raise ValueError("Invalid group name %s" % name)
        gid = grprec[2]
    else:
        try:
            grp.getgrgid(gid) # check if gid is valid
        except KeyError:
            raise ValueError("Invalid group id %s" % name)
    return gid

def gid_for_uid(uid):
    pwrec = pwd.getpwuid(uid)
    return pwrec[3]

def octal_type(arg):
    try:
        return int(arg, 8)
    except (TypeError, ValueError):
        raise ValueError('%s can not be converted to an octal type' % arg)

def existing_directory(v):
    nv = os.path.expanduser(v)
    if os.path.isdir(nv):
        return nv
    raise ValueError('%s is not an existing directory' % v)

def existing_dirpath(v):
    nv = os.path.expanduser(v)
    dir = os.path.dirname(nv)
    if not dir:
        # relative pathname with no directory component
        return nv
    if os.path.isdir(dir):
        return nv
    raise ValueError('The directory named as part of the path %s '
                     'does not exist' % v)

def logging_level(value):
    s = str(value).lower()
    level = getLevelNumByDescription(s)
    if level is None:
        raise ValueError('bad logging level name %r' % value)
    return level

class SuffixMultiplier:
    # d is a dictionary of suffixes to integer multipliers.  If no suffixes
    # match, default is the multiplier.  Matches are case insensitive.  Return
    # values are in the fundamental unit.
    def __init__(self, d, default=1):
        self._d = d
        self._default = default
        # all keys must be the same size
        self._keysz = None
        for k in d.keys():
            if self._keysz is None:
                self._keysz = len(k)
            else:
                assert self._keysz == len(k)

    def __call__(self, v):
        v = v.lower()
        for s, m in self._d.items():
            if v[-self._keysz:] == s:
                return int(v[:-self._keysz]) * m
        return int(v) * self._default

byte_size = SuffixMultiplier({'kb': 1024,
                              'mb': 1024*1024,
                              'gb': 1024*1024*long(1024),})

def url(value):
    # earlier Python 2.6 urlparse (2.6.4 and under) can't parse unix:// URLs,
    # later ones can but we need to straddle
    uri = value.replace('unix://', 'http://', 1).strip()
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(uri)
    if scheme and (netloc or path):
        return value
    raise ValueError("value %r is not a URL" % value)

# all valid signal numbers
SIGNUMS = [ getattr(signal, k) for k in dir(signal) if k.startswith('SIG') ]

def signal_number(value):
    try:
        num = int(value)
    except (ValueError, TypeError):
        name = value.strip().upper()
        if not name.startswith('SIG'):
            name = 'SIG' + name
        num = getattr(signal, name, None)
        if num is None:
            raise ValueError('value %r is not a valid signal name' % value)
    if num not in SIGNUMS:
        raise ValueError('value %r is not a valid signal number' % value)
    return num

class RestartWhenExitUnexpected:
    pass

class RestartUnconditionally:
    pass

def auto_restart(value):
    value = str(value.lower())
    computed_value  = value
    if value in TRUTHY_STRINGS:
        computed_value = RestartUnconditionally
    elif value in FALSY_STRINGS:
        computed_value = False
    elif value == 'unexpected':
        computed_value = RestartWhenExitUnexpected
    if computed_value not in (RestartWhenExitUnexpected,
                              RestartUnconditionally, False):
        raise ValueError("invalid 'autorestart' value %r" % value)
    return computed_value

def profile_options(value):
    options = [x.lower() for x in list_of_strings(value) ]
    sort_options = []
    callers = False
    for thing in options:
        if thing != 'callers':
            sort_options.append(thing)
        else:
            callers = True
    return sort_options, callers
