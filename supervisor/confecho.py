import pkg_resources
import sys

def main(out=sys.stdout):
    config = pkg_resources.resource_string(__name__, 'skel/sample.conf')
    out.write(config)
