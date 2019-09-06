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

# opening files for reading, and listing directories, should
# return a producer.

from supervisor.compat import long

class abstract_filesystem:
    def __init__ (self):
        pass

    def current_directory (self):
        """Return a string representing the current directory."""
        pass

    def listdir (self, path, long=0):
        """Return a listing of the directory at 'path' The empty string
        indicates the current directory.  If 'long' is set, instead
        return a list of (name, stat_info) tuples
        """
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

    def cwd (self, path):
        """Change the working directory."""
        pass

    def cdup (self):
        """Change to the parent of the current directory."""
        pass


    def longify (self, path):
        """Return a 'long' representation of the filename
        [for the output of the LIST command]"""
        pass

# standard wrapper around a unix-like filesystem, with a 'false root'
# capability.

# security considerations: can symbolic links be used to 'escape' the
# root?  should we allow it?  if not, then we could scan the
# filesystem on startup, but that would not help if they were added
# later.  We will probably need to check for symlinks in the cwd method.

# what to do if wd is an invalid directory?

import os
import stat
import re

def safe_stat (path):
    try:
        return path, os.stat (path)
    except:
        return None

class os_filesystem:
    path_module = os.path

    # set this to zero if you want to disable pathname globbing.
    # [we currently don't glob, anyway]
    do_globbing = 1

    def __init__ (self, root, wd='/'):
        self.root = root
        self.wd = wd

    def current_directory (self):
        return self.wd

    def isfile (self, path):
        p = self.normalize (self.path_module.join (self.wd, path))
        return self.path_module.isfile (self.translate(p))

    def isdir (self, path):
        p = self.normalize (self.path_module.join (self.wd, path))
        return self.path_module.isdir (self.translate(p))

    def cwd (self, path):
        p = self.normalize (self.path_module.join (self.wd, path))
        translated_path = self.translate(p)
        if not self.path_module.isdir (translated_path):
            return 0
        else:
            old_dir = os.getcwd()
            # temporarily change to that directory, in order
            # to see if we have permission to do so.
            can = 0
            try:
                try:
                    os.chdir (translated_path)
                    can = 1
                    self.wd = p
                except:
                    pass
            finally:
                if can:
                    os.chdir (old_dir)
            return can

    def cdup (self):
        return self.cwd ('..')

    def listdir (self, path, long=0):
        p = self.translate (path)
        # I think we should glob, but limit it to the current
        # directory only.
        ld = os.listdir (p)
        if not long:
            return list_producer (ld, None)
        else:
            old_dir = os.getcwd()
            try:
                os.chdir (p)
                # if os.stat fails we ignore that file.
                result = [_f for _f in map (safe_stat, ld) if _f]
            finally:
                os.chdir (old_dir)
            return list_producer (result, self.longify)

    # TODO: implement a cache w/timeout for stat()
    def stat (self, path):
        p = self.translate (path)
        return os.stat (p)

    def open (self, path, mode):
        p = self.translate (path)
        return open (p, mode)

    def unlink (self, path):
        p = self.translate (path)
        return os.unlink (p)

    def mkdir (self, path):
        p = self.translate (path)
        return os.mkdir (p)

    def rmdir (self, path):
        p = self.translate (path)
        return os.rmdir (p)

    def rename(self, src, dst):
        return os.rename(self.translate(src),self.translate(dst))

    # utility methods
    def normalize (self, path):
        # watch for the ever-sneaky '/+' path element
        path = re.sub('/+', '/', path)
        p = self.path_module.normpath (path)
        # remove 'dangling' cdup's.
        if len(p) > 2 and p[:3] == '/..':
            p = '/'
        return p

    def translate (self, path):
        # we need to join together three separate
        # path components, and do it safely.
        # <real_root>/<current_directory>/<path>
        # use the operating system's path separator.
        path = os.sep.join(path.split('/'))
        p = self.normalize (self.path_module.join (self.wd, path))
        p = self.normalize (self.path_module.join (self.root, p[1:]))
        return p

    def longify (self, path_stat_info_tuple):
        (path, stat_info) = path_stat_info_tuple
        return unix_longify (path, stat_info)

    def __repr__ (self):
        return '<unix-style fs root:%s wd:%s>' % (
                self.root,
                self.wd
                )

if os.name == 'posix':

    class unix_filesystem (os_filesystem):
        pass

    class schizophrenic_unix_filesystem (os_filesystem):
        PROCESS_UID     = os.getuid()
        PROCESS_EUID    = os.geteuid()
        PROCESS_GID     = os.getgid()
        PROCESS_EGID    = os.getegid()

        def __init__ (self, root, wd='/', persona=(None, None)):
            os_filesystem.__init__ (self, root, wd)
            self.persona = persona

        def become_persona (self):
            if self.persona != (None, None):
                uid, gid = self.persona
                # the order of these is important!
                os.setegid (gid)
                os.seteuid (uid)

        def become_nobody (self):
            if self.persona != (None, None):
                os.seteuid (self.PROCESS_UID)
                os.setegid (self.PROCESS_GID)

        # cwd, cdup, open, listdir
        def cwd (self, path):
            try:
                self.become_persona()
                return os_filesystem.cwd (self, path)
            finally:
                self.become_nobody()

        def cdup (self):
            try:
                self.become_persona()
                return os_filesystem.cdup (self)
            finally:
                self.become_nobody()

        def open (self, filename, mode):
            try:
                self.become_persona()
                return os_filesystem.open (self, filename, mode)
            finally:
                self.become_nobody()

        def listdir (self, path, long=0):
            try:
                self.become_persona()
                return os_filesystem.listdir (self, path, long)
            finally:
                self.become_nobody()

# For the 'real' root, we could obtain a list of drives, and then
# use that.  Doesn't win32 provide such a 'real' filesystem?
# [yes, I think something like this "\\.\c\windows"]

class msdos_filesystem (os_filesystem):
    def longify (self, path_stat_info_tuple):
        (path, stat_info) = path_stat_info_tuple
        return msdos_longify (path, stat_info)

# A merged filesystem will let you plug other filesystems together.
# We really need the equivalent of a 'mount' capability - this seems
# to be the most general idea.  So you'd use a 'mount' method to place
# another filesystem somewhere in the hierarchy.

# Note: this is most likely how I will handle ~user directories
# with the http server.

class merged_filesystem:
    def __init__ (self, *fsys):
        pass

# this matches the output of NT's ftp server (when in
# MSDOS mode) exactly.

def msdos_longify (file, stat_info):
    if stat.S_ISDIR (stat_info[stat.ST_MODE]):
        dir = '<DIR>'
    else:
        dir = '     '
    date = msdos_date (stat_info[stat.ST_MTIME])
    return '%s       %s %8d %s' % (
            date,
            dir,
            stat_info[stat.ST_SIZE],
            file
            )

def msdos_date (t):
    try:
        info = time.gmtime (t)
    except:
        info = time.gmtime (0)
    # year, month, day, hour, minute, second, ...
    hour = info[3]
    if hour > 11:
        merid = 'PM'
        hour -= 12
    else:
        merid = 'AM'
    return '%02d-%02d-%02d  %02d:%02d%s' % (
            info[1],
            info[2],
            info[0]%100,
            hour,
            info[4],
            merid
            )

months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

mode_table = {
        '0':'---',
        '1':'--x',
        '2':'-w-',
        '3':'-wx',
        '4':'r--',
        '5':'r-x',
        '6':'rw-',
        '7':'rwx'
        }

import time

def unix_longify (file, stat_info):
    # for now, only pay attention to the lower bits
    mode = ('%o' % stat_info[stat.ST_MODE])[-3:]
    mode = ''.join([mode_table[x] for x in mode])
    if stat.S_ISDIR (stat_info[stat.ST_MODE]):
        dirchar = 'd'
    else:
        dirchar = '-'
    date = ls_date (long(time.time()), stat_info[stat.ST_MTIME])
    return '%s%s %3d %-8d %-8d %8d %s %s' % (
            dirchar,
            mode,
            stat_info[stat.ST_NLINK],
            stat_info[stat.ST_UID],
            stat_info[stat.ST_GID],
            stat_info[stat.ST_SIZE],
            date,
            file
            )

# Emulate the unix 'ls' command's date field.
# it has two formats - if the date is more than 180
# days in the past, then it's like this:
# Oct 19  1995
# otherwise, it looks like this:
# Oct 19 17:33

def ls_date (now, t):
    try:
        info = time.gmtime (t)
    except:
        info = time.gmtime (0)
    # 15,600,000 == 86,400 * 180
    if (now - t) > 15600000:
        return '%s %2d  %d' % (
                months[info[1]-1],
                info[2],
                info[0]
                )
    else:
        return '%s %2d %02d:%02d' % (
                months[info[1]-1],
                info[2],
                info[3],
                info[4]
                )

# ===========================================================================
# Producers
# ===========================================================================

class list_producer:
    def __init__ (self, list, func=None):
        self.list = list
        self.func = func

    # this should do a pushd/popd
    def more (self):
        if not self.list:
            return ''
        else:
            # do a few at a time
            bunch = self.list[:50]
            if self.func is not None:
                bunch = map (self.func, bunch)
            self.list = self.list[50:]
            return '\r\n'.join(bunch) + '\r\n'

