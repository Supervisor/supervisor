import pkg_resources
import sys
from supervisor.py3compat import *

def main(out=sys.stdout):
    config = pkg_resources.resource_string(__name__, 'skel/sample.conf')
    out.write(as_string(config))
