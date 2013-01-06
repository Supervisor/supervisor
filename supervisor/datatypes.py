import grp
import os
import pwd
import signal
import sys
import socket
import shlex
import urlparse
from supervisor.loggers import getLevelNumByDescription

# I dont know why we bother, this doesn't run on Windows, but just
# in case it ever does, avoid this bug magnet by leaving it.
if sys.platform[:3] == "win": # pragma: no cover
    DEFAULT_HOST = "localhost"
else:
    DEFAULT_HOST = ""

here = None

def set_here(v):
    global here
    here = v

def integer(value):
    try:
        return int(value)
    except ValueError:
        return long(value) # why does this help? (CM)
    except OverflowError:
        return long(value)

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
            return map(int, arg.split(","))
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
    lexer = shlex.shlex(arg)
    lexer.wordchars += '/.+-():'

    tokens = list(lexer)
    tokens_len = len(tokens)

    D = {}
    i = 0
    while i < tokens_len:
        k_eq_v = tokens[i:i+3]
        if len(k_eq_v) != 3 or k_eq_v[1] != '=':
            raise ValueError, "Unexpected end of key/value pairs"
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
                             % (`v`, `self._min`))
        if self._max is not None and v > self._max:
            raise ValueError("%s is above upper bound (%s)"
                             % (`v`, `self._max`))
        return v

port_number = RangeCheckedConversion(integer, min=1, max=0xffff).__call__

def inet_address(s):
    # returns (host, port) tuple
    host = ''
    port = None
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
        host = DEFAULT_HOST
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

    def addr(self): # pragma: no cover
        raise NotImplementedError

    def create_and_bind(self): # pragma: no cover
        raise NotImplementedError

class InetStreamSocketConfig(SocketConfig):
    """ TCP socket config helper """

    host = None # host name or ip to bind to
    port = None # integer port to bind to

    def __init__(self, host, port):
        self.host = host.lower()
        self.port = port_number(port)
        self.url = 'tcp://%s:%d' % (self.host, self.port)

    def addr(self):
        return (self.host, self.port)

    def create_and_bind(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(self.addr())
        return sock

class UnixStreamSocketConfig(SocketConfig):
    """ Unix domain socket config helper """

    path = None # Unix domain socket path
    mode = None # Unix permission mode bits for socket
    owner = None # Tuple (uid, gid) for Unix ownership of socket
    sock = None # socket object

    def __init__(self, path, **kwargs):
        self.path = path
        self.url = 'unix://%s' % (path)
        self.mode = kwargs.get('mode', None)
        self.owner = kwargs.get('owner', None)

    def addr(self):
        return self.path

    def create_and_bind(self):
        if os.path.exists(self.path):
            os.unlink(self.path)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(self.addr())
        try:
            self._chown()
            self._chmod()
        except:
            sock.close()
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
            except Exception, e:
                raise ValueError("Could not change permissions of socket "
                                    + "file: %s" % (e))

    def _chown(self):
        if self.owner is not None:
            try:
                os.chown(self.path, self.owner[0], self.owner[1])
            except Exception, e:
                raise ValueError("Could not change ownership of socket file: "
                                    + "%s" % (e))


def colon_separated_user_group(arg):
    try:
        result = arg.split(':', 1)
        if len(result) == 1:
            username = result[0]
            uid = name_to_uid(username)
            if uid is None:
                raise ValueError('Invalid user name %s' % username)
            return (uid, -1)
        else:
            username = result[0]
            groupname = result[1]
            uid = name_to_uid(username)
            gid = name_to_gid(groupname)
            if uid is None:
                raise ValueError('Invalid user name %s' % username)
            if gid is None:
                raise ValueError('Invalid group name %s' % groupname)
            return (uid, gid)
        return result
    except:
        raise ValueError, 'Invalid user.group definition %s' % arg

def octal_type(arg):
    try:
        return int(arg, 8)
    except TypeError:
        raise ValueError('%s is not convertable to an octal type' % arg)

def name_to_uid(name):
    if name is None:
        return None

    try:
        uid = int(name)
    except ValueError:
        try:
            pwrec = pwd.getpwnam(name)
        except KeyError:
            return None
        uid = pwrec[2]
    else:
        try:
            pwrec = pwd.getpwuid(uid)
        except KeyError:
            return None
    return uid

def name_to_gid(name):
    try:
        gid = int(name)
    except ValueError:
        try:
            pwrec = grp.getgrnam(name)
        except KeyError:
            return None
        gid = pwrec[2]
    else:
        try:
            pwrec = grp.getgrgid(gid)
        except KeyError:
            return None
    return gid

def gid_for_uid(uid):
    pwrec = pwd.getpwuid(uid)
    return pwrec[3]

def existing_directory(v):
    nv = v % {'here':here}
    nv = os.path.expanduser(nv)
    if os.path.isdir(nv):
        return nv
    raise ValueError('%s is not an existing directory' % v)

def existing_dirpath(v):
    nv = v % {'here':here}
    nv = os.path.expanduser(nv)
    dir = os.path.dirname(nv)
    if not dir:
        # relative pathname with no directory component
        return nv
    if os.path.isdir(dir):
        return nv
    raise ValueError, ('The directory named as part of the path %s '
                       'does not exist.' % v)

def logging_level(value):
    level = getLevelNumByDescription(value)
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
                              'gb': 1024*1024*1024L,})

def url(value):
    # earlier Python 2.6 urlparse (2.6.4 and under) can't parse unix:// URLs,
    # later ones can but we need to straddle
    uri = value.replace('unix://', 'http://', 1).strip()
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(uri)
    if scheme and (netloc or path):
        return value
    raise ValueError("value %s is not a URL" % value)

def signal_number(value):
    result = None
    try:
        result = int(value)
    except (ValueError, TypeError):
        result = getattr(signal, 'SIG'+value, None)
    try:
        result = int(result)
        return result
    except (ValueError, TypeError):
        raise ValueError('value %s is not a signal name/number' % value)

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
