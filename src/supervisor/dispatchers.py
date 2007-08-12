import logging
import errno

from supervisor.events import ProcessCommunicationEvent
from supervisor.events import notify

def find_prefix_at_end(haystack, needle):
    l = len(needle) - 1
    while l and not haystack.endswith(needle[:l]):
        l -= 1
    return l

class PDispatcher:
    """ Asyncore dispatcher for mainloop, representing a process channel
    (stdin, stdout, or stderr).  This class is abstract. """

    def readable(self):
        raise NotImplementedError

    def writable(self):
        raise NotImplementedError

    def handle_read_event(self):
        raise NotImplementedError

    def handle_write_event(self):
        raise NotImplementedError

    def handle_error(self):
        raise NotImplementedError

class POutputDispatcher(PDispatcher):
    """ Output (stdout/stderr) dispatcher """

    process = None # process which "owns" this dispatcher
    channel = None # 'stderr' or 'stdout'
    capturemode = False # are we capturing process event data
    mainlog = None #  the process' "normal" logger
    capturelog = None # the logger while we're in capturemode
    capturefile = None # the capture file name
    childlog = None # the current logger (event or main)
    output_buffer = '' # data waiting to be logged

    def __init__(self, process, channel, fd):
        self.process = process
        self.channel = channel
        self.fd = fd

        logfile = getattr(process.config, '%s_logfile' % channel)
        capturefile = getattr(process.config, '%s_capturefile' % channel)

        if logfile:
            maxbytes = getattr(process.config, '%s_logfile_maxbytes' % channel)
            backups = getattr(process.config, '%s_logfile_backups' % channel)
            self.mainlog = process.config.options.getLogger(
                logfile,
                logging.INFO,
                '%(message)s',
                rotating=not not maxbytes, # optimization
                maxbytes=maxbytes,
                backups=backups)

        if capturefile:
            self.capturefile = capturefile
            self.capturelog = self.process.config.options.getLogger(
                capturefile,
                logging.INFO,
                '%(message)s',
                rotating=False)

        self.childlog = self.mainlog


    def removelogs(self):
        for log in (self.mainlog, self.capturelog):
            if log is not None:
                for handler in log.handlers:
                    handler.remove()
                    handler.reopen()

    def reopenlogs(self):
        for log in (self.mainlog, self.capturelog):
            if log is not None:
                for handler in log.handlers:
                    handler.reopen()

    def record_output(self):
        if self.capturemode:
            token = ProcessCommunicationEvent.END_TOKEN
        else:
            token = ProcessCommunicationEvent.BEGIN_TOKEN

        data = self.output_buffer
        self.output_buffer = ''

        if len(data) <= len(token):
            self.output_buffer = data
            return # not enough data

        try:
            before, after = data.split(token, 1)
        except ValueError:
            after = None
            index = find_prefix_at_end(data, token)
            if index:
                self.output_buffer = self.output_buffer + data[-index:]
                data = data[:-index]
        else:
            data = before
            self.toggle_capturemode()
            self.output_buffer = after

        if self.childlog and data:
            if self.process.config.options.strip_ansi:
                data = self.process.config.options.stripEscapes(data)
            self.childlog.info(data)

        if data:
            procname = self.process.config.name
            msg = '%r %s output:\n%s' % (procname, self.channel, data)
            TRACE = self.process.config.options.TRACE
            self.process.config.options.logger.log(TRACE, msg)

        if after:
            self.record_output()

    def toggle_capturemode(self):
        self.capturemode = not self.capturemode

        if self.capturelog is not None:
            if self.capturemode:
                self.childlog = self.capturelog
            else:
                capturefile = self.capturefile
                for handler in self.capturelog.handlers:
                    handler.flush()
                data = ''
                f = self.process.config.options.open(capturefile, 'r')
                while 1:
                    new = f.read(1<<20) # 1MB
                    data += new
                    if not new:
                        break
                    if len(data) > (1 << 21): #2MB
                        data = data[:1<<21]
                        # DWIM: don't overrun memory
                        self.process.config.options.logger.info(
                            'Truncated oversized EVENT mode log to 2MB')
                        break 

                channel = self.channel
                procname = self.process.config.name
                notify(ProcessCommunicationEvent(procname, channel, data))
                                        
                msg = "%r %s emitted a comm event" % (procname, channel)
                TRACE = self.process.config.options.TRACE
                self.process.config.options.logger.log(TRACE, msg)
                                        
                for handler in self.capturelog.handlers:
                    handler.remove()
                    handler.reopen()
                self.childlog = self.mainlog

    def writable(self):
        return False
    
    def readable(self):
        return True

    def handle_read_event(self):
        data = self.process.config.options.readfd(self.fd)
        self.output_buffer += data
        self.record_output()

class PInputDispatcher(PDispatcher):
    """ Input (stdin) dispatcher """
    process = None # process which "owns" this dispatcher
    channel = None # 'stdin'
    input_buffer = '' # data waiting to be sent to the child process

    def __init__(self, process, channel, fd):
        self.process = process
        self.channel = channel
        self.fd = fd
        self.input_buffer = ''

    def writable(self):
        if self.input_buffer:
            return True
        return False

    def readable(self):
        return False
    
    def handle_write_event(self):
        if self.input_buffer:
            try:
                sent = self.process.config.options.write(self.fd,
                                                         self.input_buffer)
                self.input_buffer = self.input_buffer[sent:]
            except OSError, why:
                if why[0] == errno.EPIPE:
                    msg = ('failed write to process %r stdin' %
                           self.process.config.name)
                    self.input_buffer = ''
                    self.process.config.options.logger.info(msg)
                else:
                    raise

