# -*- Mode: Python -*-

# [reworking of the version in Python-1.5.1/Demo/scripts/pi.py]

# Print digits of pi forever.
#
# The algorithm, using Python's 'long' integers ("bignums"), works
# with continued fractions, and was conceived by Lambert Meertens.
#
# See also the ABC Programmer's Handbook, by Geurts, Meertens & Pemberton,
# published by Prentice-Hall (UK) Ltd., 1990.

import string

StopException = "Stop!"

def go (file):
    try:
        k, a, b, a1, b1 = 2L, 4L, 1L, 12L, 4L
        while 1:
            # Next approximation
            p, q, k = k*k, 2L*k+1L, k+1L
            a, b, a1, b1 = a1, b1, p*a+q*a1, p*b+q*b1
            # Print common digits
            d, d1 = a/b, a1/b1
            while d == d1:
                if file.write (str(int(d))):
                    raise StopException
                a, a1 = 10L*(a%b), 10L*(a1%b1)
                d, d1 = a/b, a1/b1
    except StopException:
        return

class line_writer:

    "partition the endless line into 80-character ones"

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
            self.count = self.count + 80
        if self.count > self.digit_limit:
            return 1
        else:
            return 0

def main (env, stdin, stdout):
    parts = string.split (env['REQUEST_URI'], '/')
    if len(parts) >= 3:
        ndigits = string.atoi (parts[2])
    else:
        ndigits = 5000
    stdout.write ('Content-Type: text/plain\r\n\r\n')
    go (line_writer (stdout, ndigits))
