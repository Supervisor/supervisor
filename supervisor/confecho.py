import sys
from supervisor.compat import as_string
from supervisor.compat import resource_file


def main(out=sys.stdout):
    with open(resource_file(__package__, 'skel/sample.conf'), 'r') as f:
        out.write(as_string(f.read()))
