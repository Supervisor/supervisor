# -*- Mode: Python -*-

# ======================================================================
# Copyright 1997 by Sam Rushing
#
#                         All Rights Reserved
#
# Permission to use, copy, modify, and distribute this software and
# its documentation for any purpose and without fee is hereby
# granted, provided that the above copyright notice appear in all
# copies and that both that copyright notice and this permission
# notice appear in supporting documentation, and that the name of Sam
# Rushing not be used in advertising or publicity pertaining to
# distribution of the software without specific, written prior
# permission.
#
# SAM RUSHING DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN
# NO EVENT SHALL SAM RUSHING BE LIABLE FOR ANY SPECIAL, INDIRECT OR
# CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
# OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
# CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
# ======================================================================

"""socket interface to unix syslog.
On Unix, there are usually two ways of getting to syslog: via a
local unix-domain socket, or via the TCP service.

Usually "/dev/log" is the unix domain socket.  This may be different
for other systems.

>>> my_client = syslog_client ('/dev/log')

Otherwise, just use the UDP version, port 514.

>>> my_client = syslog_client (('my_log_host', 514))

On win32, you will have to use the UDP version.  Note that
you can use this to log to other hosts (and indeed, multiple
hosts).

This module is not a drop-in replacement for the python
<syslog> extension module - the interface is different.

Usage:

>>> c = syslog_client()
>>> c = syslog_client ('/strange/non_standard_log_location')
>>> c = syslog_client (('other_host.com', 514))
>>> c.log ('testing', facility='local0', priority='debug')

"""

# TODO: support named-pipe syslog.
# [see ftp://sunsite.unc.edu/pub/Linux/system/Daemons/syslog-fifo.tar.z]

# from <linux/sys/syslog.h>:
# ===========================================================================
# priorities/facilities are encoded into a single 32-bit quantity, where the
# bottom 3 bits are the priority (0-7) and the top 28 bits are the facility
# (0-big number).  Both the priorities and the facilities map roughly
# one-to-one to strings in the syslogd(8) source code.  This mapping is
# included in this file.
#
# priorities (these are ordered)

LOG_EMERG               = 0             #  system is unusable
LOG_ALERT               = 1             #  action must be taken immediately
LOG_CRIT                = 2             #  critical conditions
LOG_ERR                 = 3             #  error conditions
LOG_WARNING             = 4             #  warning conditions
LOG_NOTICE              = 5             #  normal but significant condition
LOG_INFO                = 6             #  informational
LOG_DEBUG               = 7             #  debug-level messages

#  facility codes
LOG_KERN                = 0             #  kernel messages
LOG_USER                = 1             #  random user-level messages
LOG_MAIL                = 2             #  mail system
LOG_DAEMON              = 3             #  system daemons
LOG_AUTH                = 4             #  security/authorization messages
LOG_SYSLOG              = 5             #  messages generated internally by syslogd
LOG_LPR                 = 6             #  line printer subsystem
LOG_NEWS                = 7             #  network news subsystem
LOG_UUCP                = 8             #  UUCP subsystem
LOG_CRON                = 9             #  clock daemon
LOG_AUTHPRIV    = 10    #  security/authorization messages (private)

#  other codes through 15 reserved for system use
LOG_LOCAL0              = 16            #  reserved for local use
LOG_LOCAL1              = 17            #  reserved for local use
LOG_LOCAL2              = 18            #  reserved for local use
LOG_LOCAL3              = 19            #  reserved for local use
LOG_LOCAL4              = 20            #  reserved for local use
LOG_LOCAL5              = 21            #  reserved for local use
LOG_LOCAL6              = 22            #  reserved for local use
LOG_LOCAL7              = 23            #  reserved for local use

priority_names = {
        "alert":        LOG_ALERT,
        "crit":         LOG_CRIT,
        "debug":        LOG_DEBUG,
        "emerg":        LOG_EMERG,
        "err":          LOG_ERR,
        "error":        LOG_ERR,                #  DEPRECATED
        "info":         LOG_INFO,
        "notice":       LOG_NOTICE,
        "panic":        LOG_EMERG,              #  DEPRECATED
        "warn":         LOG_WARNING,            #  DEPRECATED
        "warning":      LOG_WARNING,
        }

facility_names = {
        "auth":         LOG_AUTH,
        "authpriv":     LOG_AUTHPRIV,
        "cron":         LOG_CRON,
        "daemon":       LOG_DAEMON,
        "kern":         LOG_KERN,
        "lpr":          LOG_LPR,
        "mail":         LOG_MAIL,
        "news":         LOG_NEWS,
        "security":     LOG_AUTH,               #  DEPRECATED
        "syslog":       LOG_SYSLOG,
        "user":         LOG_USER,
        "uucp":         LOG_UUCP,
        "local0":       LOG_LOCAL0,
        "local1":       LOG_LOCAL1,
        "local2":       LOG_LOCAL2,
        "local3":       LOG_LOCAL3,
        "local4":       LOG_LOCAL4,
        "local5":       LOG_LOCAL5,
        "local6":       LOG_LOCAL6,
        "local7":       LOG_LOCAL7,
        }

import socket

class syslog_client:
    def __init__ (self, address='/dev/log'):
        self.address = address
        self.stream = 0
        if isinstance(address, type('')):
            try:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                self.socket.connect(address)
            except socket.error:
                # Some Linux installations have /dev/log
                # a stream socket instead of a datagram socket.
                self.socket = socket.socket (socket.AF_UNIX,
                                             socket.SOCK_STREAM)
                self.stream = 1
        else:
            self.socket = socket.socket (socket.AF_INET, socket.SOCK_DGRAM)

    # curious: when talking to the unix-domain '/dev/log' socket, a
    #   zero-terminator seems to be required.  this string is placed
    #   into a class variable so that it can be overridden if
    #   necessary.

    log_format_string = '<%d>%s\000'

    def log (self, message, facility=LOG_USER, priority=LOG_INFO):
        message = self.log_format_string % (
                self.encode_priority (facility, priority),
                message
                )
        if self.stream:
            self.socket.send (message)
        else:
            self.socket.sendto (message, self.address)

    def encode_priority (self, facility, priority):
        if type(facility) == type(''):
            facility = facility_names[facility]
        if type(priority) == type(''):
            priority = priority_names[priority]
        return (facility<<3) | priority

    def close (self):
        if self.stream:
            self.socket.close()
