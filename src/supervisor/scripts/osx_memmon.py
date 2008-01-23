#!/usr/bin/env python -u
##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the BSD-like license at
# http://www.repoze.org/LICENSE.txt.  A copy of the license should accompany
# this distribution.  THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL
# EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND
# FITNESS FOR A PARTICULAR PURPOSE
#
##############################################################################

# A event listener meant to be subscribed to TICK_60 (or TICK_5)
# events, which restarts any processes that are children of
# supervisord that consume "too much" memory.  Performs horrendous
# screenscrapes of Mac OS X (Tiger/Leopard) ps output.

# A supervisor config snippet that tells supervisor to use this script
# as a listener is below.
#
# [eventlistener:memmon]
# command=python osx_memmon.py [options]
# events=TICK_60

doc = """osx_memmon.py [-p processname=byte_size] | [-g groupname=byte_size] |
              [-a byte_size] [-s sendmail_program] [-m email_address]

Options:

-p -- specify a process_name=byte_size pair.  Restart the supervisor
      process named 'process_name' when it uses more than byte_size
      RSS.  If this process is in a group, it can be specified using
      the 'process_name:group_name' syntax.
      
-g -- specify a group_name=byte_size pair.  Restart any process in this group
      when it uses more than byte_size RSS.
      
-a -- specify a global byte_size.  Restart any child of the supervisord
      under which this runs if it uses more than byte_size RSS.

-s -- the sendmail program to use to send email
      (e.g. /usr/sbin/sendmail).  Must be a full path.  Default is
      /usr/sbin/sendmail.

-m -- specify an email address.  The script will send mail to this
      address when any process is restarted.  If no email address is
      specified, email will not be sent.

The -p and -g options may be specified more than once, allowing for
specification of multiple groups and processes.

Any byte_size can be specified as a plain integer (10000) or a
suffix-multiplied integer (e.g. 1GB).  Valid suffixes are 'KB', 'MB'
and 'GB'.

A sample invocation:

osx_memmon.py -p program1=200MB -p theprog:thegroup=100MB -g thegroup=100MB -a 1GB -s /usr/sbin/sendmail -m chrism@plope.com
"""

import os
import sys
import time

from supervisor import childutils
from supervisor.datatypes import byte_size

def usage():
    print doc
    sys.exit(255)

def shell(cmd):
    return os.popen(cmd).read()

def wait(programs, groups, any, sendmail, email):
    rpc = childutils.getRPCInterface(os.environ)

    while 1:
        headers, payload = childutils.listener.wait()

        if not headers['eventname'].startswith('TICK'):
            # do nothing with non-TICK events
            childutils.listener.ok()
            continue

        sys.stderr.write(
            'Checking programs %r, groups %r, any %r' %
            (programs, groups, any)
            )
        
        infos = rpc.supervisor.getAllProcessInfo()

        for info in infos:
            pid = info['pid']
            name = info['name']
            group = info['group']
            pname = '%s:%s' % (group, name)

            data = shell('ps -orss -p %s' % pid)
            dlines = data.split('\n')
            if len(dlines) < 2:
                # no data
                continue

            line = dlines[1]
            try:
                rss = line.lstrip().rstrip()
                rss = int(rss) * 1024 # rss is in KB
            except ValueError:
                # line doesn't contain any data, or rss cant be intified
                continue

            sys.stderr.write('RSS of %s is %s\n' % (pname, rss))

            for n in name, pname:
                if n in programs:
                    if  rss > programs[name]:
                        restart(rpc, pname, sendmail, email)
                        continue

            if group in groups:
                if rss > groups[group]:
                    restart(rpc, pname, sendmail, email)
                    continue

            if any:
                if rss > any:
                    restart(rpc, pname, sendmail, email)
                    continue
            
        sys.stderr.flush()
        childutils.listener.ok()

def restart(rpc, name, sendmail, email):
    sys.stderr.write('Restarting %s\n' % name)
    rpc.supervisor.stopProcess(name)
    rpc.supervisor.startProcess(name)

    if email:
        msg = ('osx_memmon.py restarted the process named %s at %s because'
               'it was consuming too much memory\n' % (name, time.asctime()))
        subject = 'memmon: process %s restarted' % name
        mail(sendmail, subject, email, msg)

def mail(sendmail, subject, to, message):
    m = os.popen('%s -t -i' % sendmail, 'w')
    m.write('To: %s\n' % to)
    m.write('Subject: %s\n' % subject)
    m.write('\n')
    m.write(message)
    m.close()
        
def parse_namesize(option, value):
    try:
        name, size = value.split('=')
    except ValueError:
        print 'Unparseable value %r for %r' % (value, option)
        usage()
    size = parse_size(option, size)
    return name, size

def parse_size(option, value):
    try:
        size = byte_size(value)
    except:
        print 'Unparseable byte_size in %r for %r' % (value, option)
        usage()
        
    return size

def main():
    import getopt
    short_args="hp:g:a:s:m:"
    long_args=[
        "help",
        "program=",
        "group=",
        "any=",
        "sendmail_program=",
        "email=",
        ]
    try:
        opts, args=getopt.getopt(sys.argv[1:], short_args, long_args)
    except:
        print __doc__
        sys.exit(2)

    programs = {}
    groups = {}
    any = None
    sendmail = '/usr/sbin/sendmail'
    email = None

    for option, value in opts:

        if option in ('-h', '--help'):
            usage()

        if option in ('-p', '--program'):
            name, size = parse_namesize(option, value)
            programs[name] = size

        if option in ('-g', '--group'):
            name, size = parse_namesize(option, value)
            groups[name] = size

        if option in ('-a', '--any'):
            size = parse_size(option, value)
            any = size

        if option in ('-s', '--sendmail_program'):
            sendmail = value

        if option in ('-m', '--email'):
            email = value

    wait(programs, groups, any, sendmail, email)

if __name__ == '__main__':
    main()
    
    
    
