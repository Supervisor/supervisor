# -*- Mode: Python -*-
#
#       Author: Sam Rushing <rushing@nightmare.com>
#       Copyright 1996-2000 by Sam Rushing
#                                                All Rights Reserved.
#

RCS_ID =  '$Id$'

import re
import counter

class redirecting_handler:

    def __init__ (self, pattern, redirect, regex_flag=re.IGNORECASE):
        self.pattern = pattern
        self.redirect = redirect
        self.patreg = re.compile (pattern, regex_flag)
        self.hits = counter.counter()

    def match (self, request):
        m = self.patreg.match (request.uri)
        return (m and (m.end() == len(request.uri)))

    def handle_request (self, request):
        self.hits.increment()
        m = self.patreg.match (request.uri)
        part = m.group(1)

        request['Location'] = self.redirect % part
        request.error (302) # moved temporarily

    def __repr__ (self):
        return '<Redirecting Handler at %08x [%s => %s]>' % (
                id(self),
                repr(self.pattern),
                repr(self.redirect)
                )

    def status (self):
        import producers
        return producers.simple_producer (
                '<li> Redirecting Handler %s => %s <b>Hits</b>: %s' % (
                        self.pattern, self.redirect, self.hits
                        )
                )
