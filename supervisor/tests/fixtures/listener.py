
import sys

def write_and_flush(stream, s):
    stream.write(s)
    stream.flush()

def write_stdout(s):
    # only eventlistener protocol messages may be sent to stdout
    sys.stdout.write(s)
    sys.stdout.flush()

def write_stderr(s):
    sys.stderr.write(s)
    sys.stderr.flush()

def main():
    stdin = sys.stdin
    stdout = sys.stdout
    stderr = sys.stderr
    while True:
        # transition from ACKNOWLEDGED to READY
        write_and_flush(stdout, 'READY\n')

        # read header line and print it to stderr
        line = stdin.readline()
        write_and_flush(stderr, line)

        # read event payload and print it to stderr
        headers = dict([ x.split(':') for x in line.split() ])
        data = stdin.read(int(headers['len']))
        write_and_flush(stderr, data)

        # transition from READY to ACKNOWLEDGED
        write_and_flush(stdout, 'RESULT 2\nOK')

if __name__ == '__main__':
    main()
