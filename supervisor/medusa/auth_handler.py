# -*- Mode: Python -*-
#
#       Author: Sam Rushing <rushing@nightmare.com>
#       Copyright 1996-2000 by Sam Rushing
#                                                All Rights Reserved.
#

RCS_ID =  '$Id: auth_handler.py,v 1.6 2002/11/25 19:40:23 akuchling Exp $'

# support for 'basic' authenticaion.

import base64
try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
import re
import string
import time
import counter

import default_handler

get_header = default_handler.get_header

import producers

# This is a 'handler' that wraps an authorization method
# around access to the resources normally served up by
# another handler.

# does anyone support digest authentication? (rfc2069)

class auth_handler:
    def __init__ (self, dict, handler, realm='default'):
        self.authorizer = dictionary_authorizer (dict)
        self.handler = handler
        self.realm = realm
        self.pass_count = counter.counter()
        self.fail_count = counter.counter()

    def match (self, request):
        # by default, use the given handler's matcher
        return self.handler.match (request)

    def handle_request (self, request):
        # authorize a request before handling it...
        scheme = get_header (AUTHORIZATION, request.header)

        if scheme:
            scheme = string.lower (scheme)
            if scheme == 'basic':
                cookie = get_header (AUTHORIZATION, request.header, 2)
                try:
                    decoded = base64.decodestring (cookie)
                except:
                    print 'malformed authorization info <%s>' % cookie
                    request.error (400)
                    return
                auth_info = string.split (decoded, ':')
                if self.authorizer.authorize (auth_info):
                    self.pass_count.increment()
                    request.auth_info = auth_info
                    self.handler.handle_request (request)
                else:
                    self.handle_unauthorized (request)
            #elif scheme == 'digest':
            #       print 'digest: ',AUTHORIZATION.group(2)
            else:
                print 'unknown/unsupported auth method: %s' % scheme
                self.handle_unauthorized(request)
        else:
            # list both?  prefer one or the other?
            # you could also use a 'nonce' here. [see below]
            #auth = 'Basic realm="%s" Digest realm="%s"' % (self.realm, self.realm)
            #nonce = self.make_nonce (request)
            #auth = 'Digest realm="%s" nonce="%s"' % (self.realm, nonce)
            #request['WWW-Authenticate'] = auth
            #print 'sending header: %s' % request['WWW-Authenticate']
            self.handle_unauthorized (request)

    def handle_unauthorized (self, request):
        # We are now going to receive data that we want to ignore.
        # to ignore the file data we're not interested in.
        self.fail_count.increment()
        request.channel.set_terminator (None)
        request['Connection'] = 'close'
        request['WWW-Authenticate'] = 'Basic realm="%s"' % self.realm
        request.error (401)

    def make_nonce (self, request):
        "A digest-authentication <nonce>, constructed as suggested in RFC 2069"
        ip = request.channel.server.ip
        now = str(long(time.time()))
        if now[-1:] == 'L':
            now = now[:-1]
        private_key = str (id (self))
        nonce = string.join ([ip, now, private_key], ':')
        return self.apply_hash (nonce)

    def apply_hash (self, s):
        "Apply MD5 to a string <s>, then wrap it in base64 encoding."
        m = md5()
        m.update (s)
        d = m.digest()
        # base64.encodestring tacks on an extra linefeed.
        return base64.encodestring (d)[:-1]

    def status (self):
        # Thanks to mwm@contessa.phone.net (Mike Meyer)
        r = [
                producers.simple_producer (
                        '<li>Authorization Extension : '
                        '<b>Unauthorized requests:</b> %s<ul>' % self.fail_count
                        )
                ]
        if hasattr (self.handler, 'status'):
            r.append (self.handler.status())
        r.append (
                producers.simple_producer ('</ul>')
                )
        return producers.composite_producer(r)

class dictionary_authorizer:
    def __init__ (self, dict):
        self.dict = dict

    def authorize (self, auth_info):
        [username, password] = auth_info
        if (self.dict.has_key (username)) and (self.dict[username] == password):
            return 1
        else:
            return 0

AUTHORIZATION = re.compile (
        #               scheme  challenge
        'Authorization: ([^ ]+) (.*)',
        re.IGNORECASE
        )
