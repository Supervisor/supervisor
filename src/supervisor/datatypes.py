import os
import sys

if sys.platform[:3] == "win":
    DEFAULT_HOST = "localhost"
else:
    DEFAULT_HOST = ""


def integer(value):
    try:
        return int(value)
    except ValueError:
        return long(value)
    except OverflowError:
        return long(value)

def boolean(s):
    """Convert a string value to a boolean value."""
    ss = str(s).lower()
    if ss in ('yes', 'true', 'on', '1'):
        return True
    elif ss in ('no', 'false', 'off', '0'):
        return False
    else:
        raise ValueError("not a valid boolean value: " + repr(s))

def list_of_ints(arg):
    if not arg:
        return []
    else:
        return map(int, arg.split(","))

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
        if s:
            port = port_number(s)
        host = host.lower()
    else:
        try:
            port = port_number(s)
        except ValueError:
            if len(s.split()) != 1:
                raise ValueError("not a valid host name: " + repr(s))
            host = s.lower()
    if not host:
        host = DEFAULT_HOST
    return host, port

class SocketAddress:
    def __init__(self, s):
        # returns (family, address) tuple
        import socket
        if "/" in s or s.find(os.sep) >= 0:
            self.family = getattr(socket, "AF_UNIX", None)
            self.address = s
        else:
            self.family = socket.AF_INET
            self.address = inet_address(s)

def dot_separated_user_group(arg):
    if not arg:
        return
    try:
        result = arg.split('.', 1)
        if len(result) == 1:
            return (result[0], None)
        return result
    except:
        raise ValueError, 'invalid user.group definition %s' % arg

def octal_type(arg):
    return int(arg, 8)

def name_to_uid(name):
    import pwd
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
    import grp
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
    import pwd
    pwrec = pwd.getpwuid(uid)
    return pwrec[3]

def existing_directory(v):
    import os
    nv = os.path.expanduser(v)
    if os.path.isdir(nv):
        return nv
    raise ValueError('%s is not an existing directory' % v)

def existing_dirpath(v):
    import os
    nv = os.path.expanduser(v)
    dir = os.path.dirname(nv)
    if not dir:
        # relative pathname with no directory component
        return nv
    if os.path.isdir(dir):
        return nv
    raise ValueError, ('The directory named as part of the path %s '
                       'does not exist.' % v)

_logging_levels = {
    "critical": 50,
    "fatal": 50,
    "error": 40,
    "warn": 30,
    "warning": 30,
    "info": 20,
    "blather": 15,
    "debug": 10,
    "trace": 5,
    "all": 1,
    "notset": 0,
    }

def logging_level(value):
    s = str(value).lower()
    if _logging_levels.has_key(s):
        return _logging_levels[s]
    else:
        v = int(s)
        if v < 0 or v > 50:
            raise ValueError("log level not in range: " + `v`)
        return v

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
    import urlparse
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(value)
    if scheme and netloc:
        return value
    raise ValueError("value %s is not a URL" % value)

def signal(value):
    import signal
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
        
        
