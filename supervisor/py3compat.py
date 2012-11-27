__author__ = 'Scott Maxwell'

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
else:
    def as_bytes(s): return str(s)
    def as_string(s): return str(s)

def print_function(*args,**kwargs): sys.stdout.write(' '.join(str(i) for i in args)+kwargs.get('end','\n'))
