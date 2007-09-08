#!/usr/bin/env python -u

##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

# An process which emits PROCESS_COMMUNICATION_EVENTS every few
# seconds.  The event body contains XML that represents the current
# state of the processes running under Mac OSX on supervisor (process
# size, cpu usage, etc) as well as a global health section.  This
# example only works on Mac OS X because it perform horrendous
# screenscrapes of Tiger ps and top output. An example XML
# serialization follows:
#
# <status>
#   <process name="foo:bar">
#     <uid>501</uid>
#     <pid>10719</pid>
#     <ppid>72</ppid>
#     <cpu>0</cpu>
#     <pri>62</pri>
#     <ni>0</ni>
#     <vsz>1491620</vsz>
#     <rss>581344</rss>
#   </process>
#   <process name="fuz:baz">
#     <uid>501</uid>
#     <pid>13602</pid>
#     <ppid>72</ppid>
#     <cpu>0</cpu>
#     <pri>46</pri>
#     <ni>0</ni>
#     <vsz>888944</vsz>
#     <rss>15744</rss>
#   </process>
#   <global>
#     <procinfo>
#       <total>82</total>
#       <running>3</running>
#       <sleeping>79</sleeping>
#     </procinfo>
#     <load>
#       <loadavg_one>0.74</loadavg_one>
#       <loadavg_five>0.74</loadavg_five>
#       <loadavg_ten>0.59</loadavg_ten>
#       <usercpu_percent>17.4</usercpu_percent>
#       <syscpu_percent>78.3</syscpu_percent>
#       <idlecpu_percent>4.3</idlecpu_percent>
#     </load>
#     <memory>
#       <used>2093796556</used>
#       <free>52428800</free>
#     </memory>
#   </global>
# </status>

#
# This process is meant to be put into a supervisor config like this one
# (along with the listener):
#
# [eventlistener:memlistener]
# command=python osx_memmon_listener.py 200MB
# events=PROCESS_COMMUNICATION
#
# [program:monitor]
# command=python osx_memmon_eventgen.py 5
# stdout_capture_maxbytes=1MB

from supervisor import childutils

import os
import re
import sys
import time

from StringIO import StringIO
try:
    import xml.etree.ElementTree as etree
except ImportError:
    import elementtree.ElementTree as etree

class SuffixMultiplier:
    # d is a dictionary of suffixes to integer multipliers.  If no suffixes
    # match, default is the multiplier.  Matches are case insensitive.  Return
    # values are in the fundamental unit.
    def __init__(self, d, default=1):
        self._d = d
        self._default = default
        # all keys must be the same size
        self._keysz = None
        for k in d.keys():
            if self._keysz is None:
                self._keysz = len(k)
            else:
                assert self._keysz == len(k)

    def __call__(self, v):
        v = v.lower()
        for s, m in self._d.items():
            if v[-self._keysz:] == s:
                return str(int(float(v[:-self._keysz]) * m))
        return str(int(float(v) * self._default))

byte_size = SuffixMultiplier({'k': 1024,
                              'm': 1024*1024,
                              'g': 1024*1024*1024L,})

PROC_INFO = re.compile(r"""
    Processes:
    \s*
    (?P<total>\d+)\s*total,
    \s*
    (?P<running>\d+)\s*running,
    \s*
    (?P<sleeping>\d+)
    .*
    """,
    re.VERBOSE|re.IGNORECASE|re.DOTALL)

LOADAVG_AND_CPU_INFO = re.compile(r"""
    Load\s*Avg:
     \s*
    (?P<loadavg_one>[\d\.]+),
    \s*
    (?P<loadavg_five>[\d\.]+),
    \s*
    (?P<loadavg_ten>[\d\.]+)
    \s*
    CPU\s*usage:
    \s*
    (?P<usercpu_percent>[\d\.]+)%
    \s*
    user,
    \s*
    (?P<syscpu_percent>[\d\.]+)%
    \s*
    sys,
    \s*
    (?P<idlecpu_percent>[\d\.]+)%
    .*
    """,
    re.VERBOSE|re.IGNORECASE|re.DOTALL)

MEM_INFO = re.compile(r"""
    PhysMem:
    \s*
    (?P<wired>[\d\.MGK]+)\s*wired,
    \s*
    (?P<active>[\d\.MGK]+)\s*active,
    \s*
    (?P<inactive>[\d\.MGK]+)\s*inactive,
    \s*
    (?P<used>[\d\.MGK]+)\s*used,
    \s*
    (?P<free>[\d\.MGK]+)\s*free
    .*
    """,
    re.VERBOSE|re.IGNORECASE|re.DOTALL)

def shell(cmd):
    return os.popen(cmd).read()

def add_proc_elements(root, info):
    pid = info['pid']
    name = info['name']
    group = info['group']
    pname = '%s:%s' % (name, group)
    data = shell('ps -l -p %s' % pid)
    dlines = data.split('\n')
    if len(dlines) > 1:
        line = dlines[1]
        try:
            uid, pid, ppid, cpu, pri, ni, vsz, rss, rest = line.split(None, 8)
        except ValueError:
            # line doesn't contain any data
            return
        proc = etree.SubElement(root, 'process', {'name':pname})
        for name in ('uid', 'pid', 'ppid', 'cpu', 'pri', 'ni', 'vsz',
                     'rss'):
            element = etree.SubElement(proc, name)
            element.text = locals()[name]
            
def add_global_elements(root):
    global_el = etree.SubElement(root, 'global')
    lines = shell('top -l1 -n0').split('\n')
    for line in lines:
        if line.startswith('Processes:'):
            match = PROC_INFO.match(line)
            procinfo_el = etree.SubElement(global_el, 'procinfo')
            for name in ('total', 'running', 'sleeping'):
                element = etree.SubElement(procinfo_el, name)
                element.text = match.group(name)
            
        elif line.startswith('Load Avg:'):
            match = LOADAVG_AND_CPU_INFO.match(line)
            load_el = etree.SubElement(global_el, 'load')
            for name in (
                'loadavg_one', 'loadavg_five', 'loadavg_ten',
                'usercpu_percent', 'syscpu_percent', 'idlecpu_percent'
                ):
                element = etree.SubElement(load_el, name)
                element.text = match.group(name)

        elif line.startswith('PhysMem:'):
            match = MEM_INFO.match(line)
            memory_el = etree.SubElement(global_el, 'memory')
            for name in ('used', 'free'):
                element = etree.SubElement(memory_el, name)
                element.text = byte_size(match.group(name))

def main(every):
    rpc = childutils.getRPCInterface(os.environ)
    while 1:
        infos = rpc.supervisor.getAllProcessInfo()
        result = do(infos)
        childutils.send_proc_comm_stdout(result)
        time.sleep(every)

def do(infos):
    root = etree.Element('status')
    for info in infos:
        add_proc_elements(root, info)
    add_global_elements(root)
    tree = etree.ElementTree(root)
    io = StringIO()
    tree.write(io)
    return io.getvalue()

def test():
    pids = filter(None, os.popen("ps ax|cut -f1 -d' '").read().split('\n'))
    infos = [ {'group':pid, 'name':pid, 'pid':pid} for pid in pids ]
    print do(infos)

if __name__ == '__main__':
    every = 5
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            test()
            sys.exit(0)
        else:
            every = int(sys.argv[1])
    main(every)
    
    
    
