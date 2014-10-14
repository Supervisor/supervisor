# -*- Mode: Python -*-

# It is tempting to add an __int__ method to this class, but it's not
# a good idea.  This class tries to gracefully handle integer
# overflow, and to hide this detail from both the programmer and the
# user.  Note that the __str__ method can be relied on for printing out
# the value of a counter:
#
# >>> print 'Total Client: %s' % self.total_clients
#
# If you need to do arithmetic with the value, then use the 'as_long'
# method, the use of long arithmetic is a reminder that the counter
# will overflow.

from supervisor.compat import long

class counter:
    """general-purpose counter"""

    def __init__ (self, initial_value=0):
        self.value = initial_value

    def increment (self, delta=1):
        result = self.value
        try:
            self.value = self.value + delta
        except OverflowError:
            self.value = long(self.value) + delta
        return result

    def decrement (self, delta=1):
        result = self.value
        try:
            self.value = self.value - delta
        except OverflowError:
            self.value = long(self.value) - delta
        return result

    def as_long (self):
        return long(self.value)

    def __nonzero__ (self):
        return self.value != 0

    __bool__ = __nonzero__

    def __repr__ (self):
        return '<counter value=%s at %x>' % (self.value, id(self))

    def __str__ (self):
        s = str(long(self.value))
        if s[-1:] == 'L':
            s = s[:-1]
        return s

