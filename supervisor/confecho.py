import sys
from supervisor import resources
from supervisor.compat import as_string


def main(out=sys.stdout):
    config = resources.read_text(__package__, 'skel/sample.conf')
    out.write(as_string(config))
