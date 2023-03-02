import sys
from supervisor.compat import as_string

if sys.version_info >= (3, 9):
    from importlib.resources import files as resource_files
else:
    from importlib_resources import files as resource_files


def main(out=sys.stdout):
    config = resource_files(__package__).joinpath('skel/sample.conf').read_text(encoding='utf-8')
    out.write(as_string(config))
