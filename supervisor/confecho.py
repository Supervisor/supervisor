import sys
from supervisor.compat import as_string
from supervisor.compat import resource_filename


def main(out=sys.stdout):
    with open(resource_filename(__package__, 'skel/sample.conf'), 'r') as f:
        out.write(as_string(f.read()))
