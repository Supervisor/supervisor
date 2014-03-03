import contextlib
import inspect
import os
import subprocess
import sys


@contextlib.contextmanager
def assert_no_leaks():
    def get_lsof_lines():
        lsof_output = subprocess.Popen(
            'lsof -p %d' % os.getpid(),
            shell=True,
            stdout=subprocess.PIPE).communicate()[0]
        lines = [line for line in lsof_output.splitlines() if '/tmp' in line]
        return set(lines)

    lsof_lines_before = get_lsof_lines()
    yield
    lsof_lines_after = get_lsof_lines()

    if len(lsof_lines_after) > len(lsof_lines_before):
        func = inspect.stack()[2][3]
        sys.stderr.write("*** assert_no_leaks: leaks found in %s:\n" % func)
        for line in lsof_lines_after - lsof_lines_before:
            sys.stderr.write("    %s\n" % line.decode('ascii'))
