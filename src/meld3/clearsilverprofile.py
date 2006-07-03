import sys
import profile as profiler
import pstats


import neo_cgi  # XXX yuck, must import before neo_util even though not used.
import neo_util
import neo_cs

template = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
  <head>
    <title>This is the title</title>
    <div>This is the head slot</div>
  </head>
  <body>
   <div>
     <form action="." method="POST">
     <table border="0">
       <tbody>
         <?cs each:itemz = values ?><tr class="foo">
           <td><?cs var:itemz.0 ?></td>
           <td><?cs var:itemz.1 ?></td>
         </tr>
         <?cs /each ?>
       </tbody>
     </table>
     </form>
    </div>
  </body>
</html>"""


hdf = neo_util.HDF()
for i in range(0, 20):
    hdf.setValue('values.%d.0' % i, str(i))
    hdf.setValue('values.%d.1' % i, str(i))

def test(cs):
    this_cs = cs(hdf)
    this_cs.parseStr(template)
    foo = this_cs.render()

def profile(num):
##     import cProfile
##     profiler = cProfile
    profiler.run("[test(cs) for x in range(0,100)]", 'logfile.dat')
    stats = pstats.Stats('logfile.dat')
    stats.strip_dirs()
    stats.sort_stats('cumulative', 'calls')
    #stats.sort_stats('calls')
    stats.print_stats(num)

if __name__ == '__main__':
    cs = neo_cs.CS
    test(cs)
    profile(30)
    import timeit
    t = timeit.Timer("test(cs)", "from __main__ import test, cs")
    repeat = 50
    number = 50
    result = t.repeat(repeat, number)
    best = min(result)
    print "%d loops " % repeat
    usec = best * 1e6 / number
    msec = usec / 1000
    print "best of %d: %.*g msec per loop" % (repeat, 8, msec)

