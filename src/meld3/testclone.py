import meld3
import time
import timeit

parent = meld3._MeldElementInterface('parent', {})
clonable = meld3._MeldElementInterface('root', {})
child1 = clonable.makeelement('child1', {})
child2 = clonable.makeelement('child2', {})
clonable.append(child1)
child1.append(child2)

for x in range(0, 10):
    new = child2.makeelement('tag%s'%x, {'x'+str(x):1})
    child2.append(new)

for x in range(0, 10):
    new = child1.makeelement('tag%s'%x, {'x'+str(x):1})
    child1.append(new)

NUM = 1000

def dotimeit(timer, name):
    repeat = 100
    number = 100
    result = timer.repeat(repeat, number)
    best = min(result)
    usec = best * 1e6 / number
    msec = usec / 1000
    print "%s best of %d: %.*g msec per loop" % (name, repeat, 8, msec)

t = timeit.Timer("meld3.chelper.clone(clonable, parent)",
                 "from __main__ import meld3, clonable, parent")
dotimeit(t, "C DF")

t = timeit.Timer("meld3.chelper.bfclone(clonable, parent)",
                 "from __main__ import meld3, clonable, parent")
dotimeit(t, "C BF")

t = timeit.Timer("meld3.pyhelper.clone(clonable, parent)",
                 "from __main__ import meld3, clonable, parent")
dotimeit(t, "Py DF")

t = timeit.Timer("meld3.pyhelper.bfclone(clonable, parent)",
                 "from __main__ import meld3, clonable, parent")
dotimeit(t, "Py BF")


