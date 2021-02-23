#!<<PYTHON>>
import os

for k, v in os.environ.items():
    print("%s=%s" % (k,v))
