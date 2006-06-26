# -*- Mode: Python -*-

# This is an alternative event loop that supports 'schedulable events'.
# You can specify an event callback to take place after <n> seconds.

# Important usage note: The granularity of the time-check is limited
# by the <timeout> argument to 'go()'; if there is little or no
# activity and you specify a 30-second timeout interval, then the
# schedule of events may only be checked at those 30-second intervals.
# In other words, if you need 1-second resolution, you will have to
# poll at 1-second intervals.  This facility is more useful for longer
# timeouts ("if the channel doesn't close in 5 minutes, then forcibly
# close it" would be a typical usage).

import asyncore
import bisect
import time

socket_map = asyncore.socket_map

class event_loop:

    def __init__ (self):
        self.events = []
        self.num_channels = 0
        self.max_channels = 0

    def go (self, timeout=30.0, granularity=15):
        global socket_map
        last_event_check = 0
        while socket_map:
            now = int(time.time())
            if (now - last_event_check) >= granularity:
                last_event_check = now
                fired = []
                # yuck. i want my lisp.
                i = j = 0
                while i < len(self.events):
                    when, what = self.events[i]
                    if now >= when:
                        fired.append (what)
                        j = i + 1
                    else:
                        break
                    i = i + 1
                if fired:
                    self.events = self.events[j:]
                    for what in fired:
                        what (self, now)
            # sample the number of channels
            n = len(asyncore.socket_map)
            self.num_channels = n
            if n > self.max_channels:
                self.max_channels = n
            asyncore.poll (timeout)

    def schedule (self, delta, callback):
        now = int (time.time())
        bisect.insort (self.events, (now + delta, callback))

    def __len__ (self):
        return len(self.events)

class test (asyncore.dispatcher):

    def __init__ (self):
        asyncore.dispatcher.__init__ (self)

    def handle_connect (self):
        print 'Connected!'

    def writable (self):
        return not self.connected

    def connect_timeout_callback (self, event_loop, when):
        if not self.connected:
            print 'Timeout on connect'
            self.close()

    def periodic_thing_callback (self, event_loop, when):
        print 'A Periodic Event has Occurred!'
        # re-schedule it.
        event_loop.schedule (self, 15, self.periodic_thing_callback)

if __name__ == '__main__':
    import socket
    el = event_loop()
    t = test ()
    t.create_socket (socket.AF_INET, socket.SOCK_STREAM)
    el.schedule (10, t.connect_timeout_callback)
    el.schedule (15, t.periodic_thing_callback)
    t.connect (('squirl', 80))
    el.go(1.0)
