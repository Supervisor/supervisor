#!<<PYTHON>>
import time
import signal
signal.signal(signal.SIGTERM, signal.SIG_IGN)

counter = 0

while 1:
   time.sleep(0.01)
   print "more spewage %s" % counter
   counter += 1
   
