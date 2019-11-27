#!<<PYTHON>>
import sys
import time

counter = 0

while counter < 30000:
    sys.stdout.write("more spewage %d\n" % counter)
    sys.stdout.flush()
    time.sleep(0.01)
    counter += 1
