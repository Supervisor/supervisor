# -*- Mode: Python -*-

# [reworking of the version in Python-1.5.1/Demo/scripts/pi.py]

# Print digits of pi forever.
#
# The algorithm, using Python's 'long' integers ("bignums"), works
# with continued fractions, and was conceived by Lambert Meertens.
#
# See also the ABC Programmer's Handbook, by Geurts, Meertens & Pemberton,
# published by Prentice-Hall (UK) Ltd., 1990.

from supervisor.py3compat import *

StopException = "Stop!"

def go (file):
    try:
        k, a, b, a1, b1 = long(2), long(4), long(1), long(12), long(4)
        while 1:
            # Next approximation
            p, q, k = k*k, long(2)*k+long(1), k+long(1)
            a, b, a1, b1 = a1, b1, p*a+q*a1, p*b+q*b1
            # Print common digits
            d, d1 = a/b, a1/b1
            while d == d1:
                if file.write (str(int(d))):
                    raise StopException
                a, a1 = long(10)*(a%b), long(10)*(a1%b1)
                d, d1 = a/b, a1/b1
    except StopException:
        return

class line_writer:
    """partition the endless line into 80-character ones"""

    def __init__ (self, file, digit_limit=10000):
        self.file = file
        self.buffer = ''
        self.count = 0
        self.digit_limit = digit_limit

    def write (self, data):
        self.buffer = self.buffer + data
        if len(self.buffer) > 80:
            line, self.buffer = self.buffer[:80], self.buffer[80:]
            self.file.write (line+'\r\n')
            self.count += 80
        if self.count > self.digit_limit:
            return 1
        else:
            return 0

#noinspection PyUnusedLocal
def main (env, stdin, stdout):
    parts = env['REQUEST_URI'].split('/')
    if len(parts) >= 3:
        ndigits = int(parts[2])
    else:
        ndigits = 5000
    stdout.write ('Content-Type: text/plain\r\n\r\n')
    go (line_writer (stdout, ndigits))
