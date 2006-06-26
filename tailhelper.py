class TailHelper:

    MAX_BUFFSIZE = 1024 * 1024

    def __init__(self, fname):
        self.f = open(fname, 'r')

    def tailf(self, size):
        sz, lines = self.tail(size)
        for line in lines:
            sys.stdout.write(line)
            sys.stdout.flush()
        while 1:
            newsz = self.fsize()
            bytes_added = newsz - sz
            if bytes_added < 0:
                sz = 0
                print "==> File truncated <=="
                bytes_added = newsz
            if bytes_added > 0:
                self.f.seek(-bytes_added, 2)
                bytes = self.f.read(bytes_added)
                sys.stdout.write(bytes)
                sys.stdout.flush()
                sz = newsz
            time.sleep(1)

    def tail(self, max=10):
        self.f.seek(0, 2)
        pos = sz = self.f.tell()

        lines = []
        bytes = []
        num_bytes = 0

        while 1:
            if pos == 0:
                break
            self.f.seek(pos)
            byte = self.f.read(1)
            if byte == '\n':
                if len(lines) == max:
                    break
                bytes.reverse()
                line = ''.join(bytes)
                line and lines.append(line)
                bytes = []
            bytes.append(byte)
            num_bytes = num_bytes + 1
            if num_bytes > self.MAX_BUFFSIZE:
                break
            pos = pos - 1
        lines.reverse()
        return sz, lines

    def fsize(self):
        return os.fstat(self.f.fileno())[stat.ST_SIZE]


