from cgi import escape

def html_repr (object):
    so = escape (repr (object))
    if hasattr (object, 'hyper_respond'):
        return '<a href="/status/object/%d/">%s</a>' % (id (object), so)
    else:
        return so

    # for example, tera, giga, mega, kilo
# p_d (n, (1024, 1024, 1024, 1024))
# smallest divider goes first - for example
# minutes, hours, days
# p_d (n, (60, 60, 24))

def progressive_divide (n, parts):
    result = []
    for part in parts:
        n, rem = divmod (n, part)
        result.append (rem)
    result.append (n)
    return result

# b,k,m,g,t
def split_by_units (n, units, dividers, format_string):
    divs = progressive_divide (n, dividers)
    result = []
    for i in range(len(units)):
        if divs[i]:
            result.append (format_string % (divs[i], units[i]))
    result.reverse()
    if not result:
        return [format_string % (0, units[0])]
    else:
        return result

def english_bytes (n):
    return split_by_units (
            n,
            ('','K','M','G','T'),
            (1024, 1024, 1024, 1024, 1024),
            '%d %sB'
            )

def english_time (n):
    return split_by_units (
            n,
            ('secs', 'mins', 'hours', 'days', 'weeks', 'years'),
            (         60,     60,      24,     7,       52),
            '%d %s'
            )
