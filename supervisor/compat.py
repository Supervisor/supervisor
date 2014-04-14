from __future__ import absolute_import

import sys
PY3 = sys.version>'3'
if PY3:
    long = int
    basestring = str
    unichr = chr
    raw_input = input
    class unicode(str):
        def __init__(self, string, encoding, errors):
            str.__init__(self, string)
    def as_bytes(s): return s if isinstance(s,bytes) else s.encode('utf8')
    def as_string(s): return s if isinstance(s,str) else s.decode('utf8')
    from functools import reduce

else:
    long = long
    raw_input = raw_input
    unicode = unicode
    basestring = basestring
    def as_bytes(s): return s if isinstance(s, str) else s.encode('utf-8')
    def as_string(s): return s if isinstance(s, unicode) else s.decode('utf-8')
    reduce = reduce

def print_function(*args,**kwargs): sys.stdout.write(' '.join(str(i) for i in args)+kwargs.get('end','\n'))

def total_ordering(cls): # pragma: no cover
    """Class decorator that fills in missing ordering methods"""
    convert = {
        '__lt__': [('__gt__', lambda self, other: not (self < other or self == other)),
                   ('__le__', lambda self, other: self < other or self == other),
                   ('__ge__', lambda self, other: not self < other)],
        '__le__': [('__ge__', lambda self, other: not self <= other or self == other),
                   ('__lt__', lambda self, other: self <= other and not self == other),
                   ('__gt__', lambda self, other: not self <= other)],
        '__gt__': [('__lt__', lambda self, other: not (self > other or self == other)),
                   ('__ge__', lambda self, other: self > other or self == other),
                   ('__le__', lambda self, other: not self > other)],
        '__ge__': [('__le__', lambda self, other: (not self >= other) or self == other),
                   ('__gt__', lambda self, other: self >= other and not self == other),
                   ('__lt__', lambda self, other: not self >= other)]
    }
    roots = set(dir(cls)) & set(convert)
    if not roots:
        raise ValueError('must define at least one ordering operation: < > <= >=')
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

try:
    import xmlrpc.client as xmlrpclib
except ImportError:
    import xmlrpclib

try:
    import urllib.parse as urlparse
    import urllib.parse as urllib
except ImportError:
    import urlparse
    import urllib

if PY3:
    from base64 import encodebytes as encodestring
else:
    from base64 import encodestring

try:
    from hashlib import sha1
except ImportError:
    from sha import new as sha1

try:
    import syslog
except ImportError:
    syslog = None

try:
    import configparser as ConfigParser
except ImportError:
   import ConfigParser

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

try:
    from sys import maxint
except ImportError:
    from sys import maxsize as maxint

try:
    from urllib.parse import parse_qs, parse_qsl
except ImportError:
    from cgi import parse_qs, parse_qsl

try:
    import http.client as httplib
except ImportError:
    import httplib

try:
    from base64 import decodebytes as decodestring, encodebytes as encodestring
except ImportError:
    from base64 import decodestring, encodestring


if PY3:
    func_attribute = '__func__'
else:
    func_attribute = 'im_func'

try:
    # Python 2.6 contains a version of cElementTree inside it.
    from xml.etree.ElementTree import iterparse
except ImportError:
    try:
        # Failing that, try cElementTree instead.
        from cElementTree import iterparse
    except ImportError:
        iterparse = None


try:
    from unittest.mock import Mock, patch, sentinel
except ImportError:
    from mock import Mock, patch, sentinel

try:
    import unittest.mock as mock
except ImportError:
    import mock

try:
    from xmlrpc.client import Fault
except ImportError:
    from xmlrpclib import Fault

try:
    from string import ascii_letters as letters
except ImportError:
    from string import letters

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

try:
    import thread
except ImportError:
    import _thread as thread
