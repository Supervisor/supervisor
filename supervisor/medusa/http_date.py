# -*- Mode: Python -*-

import re
import string
import time

def concat (*args):
    return ''.join (args)

def join (seq, field=' '):
    return field.join (seq)

def group (s):
    return '(' + s + ')'

short_days = ['sun','mon','tue','wed','thu','fri','sat']
long_days = ['sunday','monday','tuesday','wednesday','thursday','friday','saturday']

short_day_reg = group (join (short_days, '|'))
long_day_reg = group (join (long_days, '|'))

daymap = {}
for i in range(7):
    daymap[short_days[i]] = i
    daymap[long_days[i]] = i

hms_reg = join (3 * [group('[0-9][0-9]')], ':')

months = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']

monmap = {}
for i in range(12):
    monmap[months[i]] = i+1

months_reg = group (join (months, '|'))

# From draft-ietf-http-v11-spec-07.txt/3.3.1
#       Sun, 06 Nov 1994 08:49:37 GMT  ; RFC 822, updated by RFC 1123
#       Sunday, 06-Nov-94 08:49:37 GMT ; RFC 850, obsoleted by RFC 1036
#       Sun Nov  6 08:49:37 1994       ; ANSI C's asctime() format

# rfc822 format
rfc822_date = join (
        [concat (short_day_reg,','),    # day
         group('[0-9][0-9]?'),          # date
         months_reg,                    # month
         group('[0-9]+'),               # year
         hms_reg,                       # hour minute second
         'gmt'
         ],
        ' '
        )

rfc822_reg = re.compile (rfc822_date)

def unpack_rfc822(m):
    g = m.group
    i = int
    return (
            i(g(4)),        # year
            monmap[g(3)],   # month
            i(g(2)),        # day
            i(g(5)),        # hour
            i(g(6)),        # minute
            i(g(7)),        # second
            0,
            0,
            0
            )

# rfc850 format
rfc850_date = join (
        [concat (long_day_reg,','),
         join (
                 [group ('[0-9][0-9]?'),
                  months_reg,
                  group ('[0-9]+')
                  ],
                 '-'
                 ),
         hms_reg,
         'gmt'
         ],
        ' '
        )

rfc850_reg = re.compile (rfc850_date)
# they actually unpack the same way
def unpack_rfc850(m):
    g = m.group
    i = int
    return (
            i(g(4)),        # year
            monmap[g(3)],   # month
            i(g(2)),        # day
            i(g(5)),        # hour
            i(g(6)),        # minute
            i(g(7)),        # second
            0,
            0,
            0
            )

# parsdate.parsedate    - ~700/sec.
# parse_http_date       - ~1333/sec.

def build_http_date (when):
    return time.strftime ('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(when))

def parse_http_date (d):
    d = d.lower()
    tz = time.timezone
    m = rfc850_reg.match (d)
    if m and m.end() == len(d):
        retval = int (time.mktime (unpack_rfc850(m)) - tz)
    else:
        m = rfc822_reg.match (d)
        if m and m.end() == len(d):
            retval = int (time.mktime (unpack_rfc822(m)) - tz)
        else:
            return 0
    # Thanks to Craig Silverstein <csilvers@google.com> for pointing
    # out the DST discrepancy
    if time.daylight and time.localtime(retval)[-1] == 1: # DST correction
        retval = retval + (tz - time.altzone)
    return retval
