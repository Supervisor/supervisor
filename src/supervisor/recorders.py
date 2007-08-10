import logging
from supervisor.events import ProcessCommunicationEvent
from supervisor.events import notify

class LoggingRecorder:
    options = None # reference to options.ServerOptions instance
    procname = '' # process name which "owns" this logger
    channel = None # 'stdin' or 'stdout'
    capturemode = False # are we capturing process event data
    mainlog = None #  the process' "normal" log file
    capturelog = None # the log file while we're in capturemode
    childlog = None # the current logger (event or main)
    output_buffer = '' # data waiting to be logged
    
    def __init__(self, options, procname, channel, logfile, logfile_backups,
                 logfile_maxbytes, capturefile):
        self.procname = procname
        self.channel = channel
        self.options = options
        self.mainlog = options.getLogger(
                logfile, logging.INFO,
                '%(message)s',
                rotating=not not logfile_maxbytes,
                maxbytes=logfile_maxbytes,
                backups=logfile_backups)
        self.childlog = self.mainlog

        self.capturefile = capturefile
        if capturefile:
            self.capturelog = options.getLogger(
                capturefile,
                logging.INFO,
                '%(message)s',
                rotating=False)

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
            if self.options.strip_ansi:
                data = self.options.stripEscapes(data)
            self.childlog.info(data)

        if data:
            msg = '%r %s output:\n%s' % (self.procname, self.channel, data)
            self.options.logger.log(self.options.TRACE, msg)

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
                f = self.options.open(capturefile, 'r')
                while 1:
                    new = f.read(1<<20) # 1MB
                    data += new
                    if not new:
                        break
                    if len(data) > (1 << 21): #2MB
                        data = data[:1<<21]
                        # DWIM: don't overrun memory
                        self.options.logger.info(
                            'Truncated oversized EVENT mode log to 2MB')
                        break 

                channel = self.channel
                procname = self.procname
                notify(ProcessCommunicationEvent(procname, channel, data))
                                        
                msg = "%r %s emitted a comm event" % (procname, channel)
                self.options.logger.log(self.options.TRACE, msg)
                                        
                for handler in self.capturelog.handlers:
                    handler.remove()
                    handler.reopen()
                self.childlog = self.mainlog
        
def find_prefix_at_end(haystack, needle):
    l = len(needle) - 1
    while l and not haystack.endswith(needle[:l]):
        l -= 1
    return l

