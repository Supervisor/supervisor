# -*- Mode: Python -*-
#
#       Author: Sam Rushing <rushing@nightmare.com>
#       Copyright 1996, 1997 by Sam Rushing
#                                                All Rights Reserved.
#

RCS_ID =  '$Id: unix_user_handler.py,v 1.4 2002/11/25 00:09:23 akuchling Exp $'

# support for `~user/public_html'.

import re
import string
import default_handler
import filesys
import os
import pwd

get_header = default_handler.get_header

user_dir = re.compile ('/~([^/]+)(.*)')

class unix_user_handler (default_handler.default_handler):

    def __init__ (self, public_html = 'public_html'):
        self.public_html = public_html
        default_handler.default_handler.__init__ (self, None)

    # cache userdir-filesystem objects
    fs_cache = {}

    def match (self, request):
        m = user_dir.match (request.uri)
        return m and (m.end() == len (request.uri))

    def handle_request (self, request):
        # get the user name
        m = user_dir.match (request.uri)
        user = m.group(1)
        rest = m.group(2)

        # special hack to catch those lazy URL typers
        if not rest:
            request['Location'] = '/~%s/' % user
            request.error (301)
            return

        # have we already built a userdir fs for this user?
        if self.fs_cache.has_key (user):
            fs = self.fs_cache[user]
        else:
            # no, well then, let's build one.
            # first, find out where the user directory is
            try:
                info = pwd.getpwnam (user)
            except KeyError:
                request.error (404)
                return
            ud = info[5] + '/' + self.public_html
            if os.path.isdir (ud):
                fs = filesys.os_filesystem (ud)
                self.fs_cache[user] = fs
            else:
                request.error (404)
                return

        # fake out default_handler
        self.filesystem = fs
        # massage the request URI
        request.uri = '/' + rest
        return default_handler.default_handler.handle_request (self, request)

    def __repr__ (self):
        return '<Unix User Directory Handler at %08x [~user/%s, %d filesystems loaded]>' % (
                id(self),
                self.public_html,
                len(self.fs_cache)
                )
