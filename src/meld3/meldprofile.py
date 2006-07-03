#!/Users/chrism/projects/revelation/bin/python
import profile as profiler
import pstats
import meld3
# get rid of the noise of setting up an encoding
# in profile output
'.'.encode('utf-8')

template = """<html xmlns:meld="http://www.plope.com/software/meld3">
  <head>
    <title meld:id="title">This is the title</title>
    <div meld:id="headslot">This is the head slot</div>
  </head>
  <body>
   <div>
     <form action="." method="POST">
     <table border="0" meld:id="table1">
       <tbody meld:id="tbody">
         <tr meld:id="tr" class="foo">
           <td meld:id="td1">Name</td>
           <td meld:id="td2">Description</td>
         </tr>
       </tbody>
     </table>
     </form>
    </div>
  </body>
</html>"""

values = []
for thing in range(0, 20):
    values.append((str(thing), str(thing)))

def run(root):
    clone = root.clone()
    ob = clone.findmeld('tr')
    for tr, (name, desc) in ob.repeat(values):
        tr.findmeld('td1').content(name)
        tr.findmeld('td2').content(desc)
    foo = clone.write_htmlstring()

def profile(num):
##     import cProfile
##     profiler = cProfile
    profiler.run("[run(root) for x in range(0,100)]", 'logfile.dat')
    stats = pstats.Stats('logfile.dat')
    stats.strip_dirs()
    stats.sort_stats('cumulative', 'calls')
    #stats.sort_stats('calls')
    stats.print_stats(num)

if __name__ == '__main__':
    root = meld3.parse_xmlstring(template)
    run(root)
    profile(30)
    import timeit
    t = timeit.Timer("run(root)", "from __main__ import run, root")
    repeat = 50
    number = 50
    result = t.repeat(repeat, number)
    best = min(result)
    print "%d loops " % repeat
    usec = best * 1e6 / number
    msec = usec / 1000
    print "best of %d: %.*g msec per loop" % (repeat, 8, msec)
        
    #run(root, trace=True)

