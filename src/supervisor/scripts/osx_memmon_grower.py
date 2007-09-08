# a process which leaks on purpose so we can test the memmon killer

import sys
import time
L = []

while 1:
    L.append('x'*1024*1024)
    time.sleep(2)
    
