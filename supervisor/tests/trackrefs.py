##############################################################################
#
# Copyright (c) 2007 Zope Corporation and Contributors.
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

""" Code from the zope.testing module to help track down memory leaks

TrackRefs works only in a python compiled with the --with-pydebug flag.
An example of how to use TrackRefs in a function is below.

glen = 0
rc = 0

def doit():
    newglen = gc.collect()
    global glen
    if newglen > glen:
        print
        print "-------------------------------------"
        print "more garbage", newglen - glen
        glen = newglen
        print "-------------------------------------"
        print
    if refs:
        newrc = sys.gettotalrefcount()
        global rc
        if newrc > rc:
            refs.update()
            refs.detailed_refcounts(newrc, rc)
        rc = newrc
"""

import sys
import gc
import types

class TrackRefs(object):
    """Object to track reference counts across test runs."""

    def __init__(self):
        self.type2count = {}
        self.type2all = {}
        self.delta = None
        self.n = 0
        self.update()
        self.delta = None

    def update(self):
        gc.collect()
        obs = sys.getobjects(0)
        type2count = {}
        type2all = {}
        n = 0
        for o in obs:
            if type(o) is str and o == '<dummy key>':
                # avoid dictionary madness
                continue

            all = sys.getrefcount(o) - 3
            n += all

            t = type(o)
            if t is types.InstanceType:
                t = o.__class__

            if t in type2count:
                type2count[t] += 1
                type2all[t] += all
            else:
                type2count[t] = 1
                type2all[t] = all


        ct = [(
               type_or_class_title(t),
               type2count[t] - self.type2count.get(t, 0),
               type2all[t] - self.type2all.get(t, 0),
               )
              for t in type2count.iterkeys()]
        ct += [(
                type_or_class_title(t),
                - self.type2count[t],
                - self.type2all[t],
                )
               for t in self.type2count.iterkeys()
               if t not in type2count]
        ct.sort()
        self.delta = ct
        self.type2count = type2count
        self.type2all = type2all
        self.n = n


    def output(self):
        printed = False
        s1 = s2 = 0
        for t, delta1, delta2 in self.delta:
            if delta1 or delta2:
                if not printed:
                    print (
                        '    Leak details, changes in instances and refcounts'
                        ' by type/class:')
                    print "    %-55s %6s %6s" % ('type/class', 'insts', 'refs')
                    print "    %-55s %6s %6s" % ('-' * 55, '-----', '----')
                    printed = True
                print "    %-55s %6d %6d" % (t, delta1, delta2)
                s1 += delta1
                s2 += delta2

        if printed:
            print "    %-55s %6s %6s" % ('-' * 55, '-----', '----')
            print "    %-55s %6s %6s" % ('total', s1, s2)


        self.delta = None

    def detailed_refcounts(self, rc, prev):
        """Report a change in reference counts, with extra detail."""
        print ("  sum detail refcount=%-8d"
               " sys refcount=%-8d"
               " change=%-6d"
               % (self.n, rc, rc - prev))
        self.output()

def type_or_class_title(t):
    module = getattr(t, '__module__', '__builtin__')
    if module == '__builtin__':
        return t.__name__
    return "%s.%s" % (module, t.__name__)

