from __future__ import absolute_import

import sys

PY3 = sys.version_info[0] == 3

if PY3: # pragma: no cover
    long = int
    basestring = str
    raw_input = input
    class unicode(str):
        def __init__(self, string, encoding, errors):
            str.__init__(self, string)
    def as_bytes(s): return s if isinstance(s,bytes) else s.encode('utf8')
    def as_string(s): return s if isinstance(s,str) else s.decode('utf8')

else: # pragma: no cover
    long = long
    raw_input = raw_input
    unicode = unicode
    basestring = basestring
    def as_bytes(s): return s if isinstance(s, str) else s.encode('utf-8')
    def as_string(s): return s if isinstance(s, unicode) else s.decode('utf-8')

def total_ordering(cls): # pragma: no cover
    """Class decorator that fills in missing ordering methods"""
    convert = {
        '__lt__': [
            ('__gt__', lambda self, other: not (self < other or self == other)),
            ('__le__', lambda self, other: self < other or self == other),
            ('__ge__', lambda self, other: not self < other)],
        '__le__': [
            ('__ge__', lambda self, other: not self <= other or self == other),
            ('__lt__', lambda self, other: self <= other and not self == other),
            ('__gt__', lambda self, other: not self <= other)],
        '__gt__': [
            ('__lt__', lambda self, other: not (self > other or self == other)),
            ('__ge__', lambda self, other: self > other or self == other),
            ('__le__', lambda self, other: not self > other)],
        '__ge__': [
            ('__le__', lambda self, other: (not self>= other) or self == other),
            ('__gt__', lambda self, other: self >= other and not self == other),
            ('__lt__', lambda self, other: not self >= other)]
    }
    roots = set(dir(cls)) & set(convert)
    if not roots:
        raise ValueError(
            'must define at least one ordering operation: < > <= >=')
    root = max(roots)       # prefer __lt__ to __le__ to __gt__ to __ge__
    for opname, opfunc in convert[root]:
        if opname not in roots:
            opfunc.__name__ = opname
            try:
                op = getattr(int, opname)
            except AttributeError: # py25 int has no __gt__
                pass
            else:
                opfunc.__doc__ = op.__doc__
            setattr(cls, opname, opfunc)
    return cls

try: # pragma: no cover
    import xmlrpc.client as xmlrpclib
except ImportError: # pragma: no cover
    import xmlrpclib

try: # pragma: no cover
    import urllib.parse as urlparse
    import urllib.parse as urllib
except ImportError: # pragma: no cover
    import urlparse
    import urllib

try: # pragma: no cover
    from hashlib import sha1
except ImportError: # pragma: no cover
    from sha import new as sha1

try: # pragma: no cover
    import syslog
except ImportError: # pragma: no cover
    syslog = None

try: # pragma: no cover
    import configparser as ConfigParser
except ImportError: # pragma: no cover
   import ConfigParser

try: # pragma: no cover
    from StringIO import StringIO
except ImportError: # pragma: no cover
    from io import StringIO

try: # pragma: no cover
    from sys import maxint
except ImportError: # pragma: no cover
    from sys import maxsize as maxint

try: # pragma: no cover
    from urllib.parse import parse_qs, parse_qsl
except ImportError: # pragma: no cover
    from cgi import parse_qs, parse_qsl

try: # pragma: no cover
    import http.client as httplib
except ImportError: # pragma: no cover
    import httplib

try: # pragma: no cover
    from base64 import decodebytes as decodestring, encodebytes as encodestring
except ImportError: # pragma: no cover
    from base64 import decodestring, encodestring


if PY3: # pragma: no cover
    func_attribute = '__func__'
else: # pragma: no cover
    func_attribute = 'im_func'

try: # pragma: no cover
    from xmlrpc.client import Fault
except ImportError: # pragma: no cover
    from xmlrpclib import Fault

try: # pragma: no cover
    from string import ascii_letters as letters
except ImportError: # pragma: no cover
    from string import letters

try: # pragma: no cover
    from hashlib import md5
except ImportError: # pragma: no cover
    from md5 import md5

try: # pragma: no cover
    import thread
except ImportError: # pragma: no cover
    import _thread as thread
