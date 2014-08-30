# -*- Mode: Python -*-

# The 'standard' interface to a logging object is simply
# log_object.log (message)
#

# a file-like object that captures output, and
# makes sure to flush it always...  this could
# be connected to:
#  o    stdio file
#  o    low-level file
#  o    socket channel
#  o    syslog output...

class file_logger:
    def __init__ (self, file, flush=1):
        self.file = file
        self.do_flush = flush

    def log (self, message):
        if message[-1] not in ('\r', '\n'):
            message = message + '\n'

        self.file.write (data)
        if self.do_flush:
            self.file.flush()

class unresolving_logger:
    def __init__ (self, logger):
        self.logger = logger

    def log (self, ip, message):
        self.logger.log ('%s:%s' % (ip, message))
