# -*- Mode: Python -*-
#       $Id: filesys.py,v 1.9 2003/12/24 16:10:56 akuchling Exp $
#       Author: Sam Rushing <rushing@nightmare.com>
#
# Generic filesystem interface.
#

# We want to provide a complete wrapper around any and all
# filesystem operations.

# this class is really just for documentation,
# identifying the API for a filesystem object.

class abstract_filesystem:
    def __init__ (self):
        pass

    def open (self, path, mode):
        """Return an open file object"""
        pass

    def stat (self, path):
        """Return the equivalent of os.stat() on the given path."""
        pass

    def isdir (self, path):
        """Does the path represent a directory?"""
        pass

    def isfile (self, path):
        """Does the path represent a plain file?"""
        pass


# standard wrapper around a unix-like filesystem, with a 'false root'
# capability.

# security considerations: can symbolic links be used to 'escape' the
# root?  should we allow it?  if not, then we could scan the
# filesystem on startup, but that would not help if they were added
# later.

import os
import stat
import re

class os_filesystem:
    path_module = os.path

    def __init__ (self, root):
        self.root = root

    def isfile (self, path):
        return os.path.isfile(self.translate(path))

    def isdir (self, path):
        return os.path.isdir(self.translate(path))

    def stat (self, path):
        return os.stat(self.translate(path))

    def open (self, path, mode):
        return open(self.translate(path), mode)

    def translate (self, path):
        # we need to join together <real_root>/<path>, and do it safely.
        path = os.path.normpath('/' + path)
        return os.path.join(self.root, path[1:])

    def __repr__ (self):
        return '<unix-style fs root:%s>' % (self.root,)
