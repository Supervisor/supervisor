# -*- Mode: Python -*-

#
# Sample/Template Medusa Startup Script.
#
# This file acts as a configuration file and startup script for Medusa.
#
# You should make a copy of this file, then add, change or comment out
# appropriately.  Then you can start up the server by simply typing
#
# $ python start_medusa.py
#

import os
import sys

from supervisor.medusa import asyncore_25 as asyncore
from supervisor.medusa import http_server
from supervisor.medusa import filesys
from supervisor.medusa import default_handler
from supervisor.medusa import status_handler
from supervisor.medusa import logger

if len(sys.argv) > 1:
    # process a few convenient arguments
    [IP_ADDRESS, PUBLISHING_ROOT] = sys.argv[1:]
else:
    # This is the IP address of the network interface you want
    # your servers to be visible from.  This can be changed to ''
    # to listen on all interfaces.
    IP_ADDRESS                      = ''

    # Root of the http and ftp server's published filesystems.
    PUBLISHING_ROOT         = '/home/www'

HTTP_PORT               = 8080 # The standard port is 80

# ===========================================================================
# Logging.
# ===========================================================================

# There are several types of logging objects. Multiple loggers may be combined,
# See 'logger.py' for more details.

# This will log to stdout:
lg = logger.file_logger (sys.stdout)

# This will log to syslog:
#lg = logger.syslog_logger ('/dev/log')

# ===========================================================================
# Filesystem Object.
# ===========================================================================
# An abstraction for the file system.  Filesystem objects can be
# combined and implemented in interesting ways.  The default type
# simply remaps a directory to root.

fs = filesys.os_filesystem (PUBLISHING_ROOT)

# ===========================================================================
# Default HTTP handler
# ===========================================================================

# The 'default' handler for the HTTP server is one that delivers
# files normally - this is the expected behavior of a web server.
# Note that you needn't use it:  Your web server might not want to
# deliver files!

# This default handler uses the filesystem object we just constructed.

dh = default_handler.default_handler (fs)

# ===========================================================================
# HTTP Server
# ===========================================================================
hs = http_server.http_server (IP_ADDRESS, HTTP_PORT, None, lg)

# Here we install the default handler created above.
hs.install_handler (dh)

# become 'nobody'
try:
    if os.name == 'posix':
        if hasattr (os, 'seteuid'):
            import pwd
            [uid, gid] = pwd.getpwnam ('nobody')[2:4]
            os.setegid (gid)
            os.seteuid (uid)
except Exception:
    pass

# Finally, start up the server loop!  This loop will not exit until
# all clients and servers are closed.  You may cleanly shut the system
# down by sending SIGINT (a.k.a. KeyboardInterrupt).
asyncore.loop()
