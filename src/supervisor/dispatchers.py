import logging
import errno
from asyncore import compact_traceback

from supervisor.events import notify
from supervisor.events import EventRejectedEvent
from supervisor.states import EventListenerStates

def find_prefix_at_end(haystack, needle):
    l = len(needle) - 1
    while l and not haystack.endswith(needle[:l]):
        l -= 1
    return l

class PDispatcher:
    """ Asyncore dispatcher for mainloop, representing a process channel
    (stdin, stdout, or stderr).  This class is abstract. """

    closed = False # True if close() has been called

    def __repr__(self):
        return '<%s at %s for %s (%s)>' % (self.__class__.__name__,
                                           id(self),
                                           self.process,
                                           self.channel)

    def readable(self):
        raise NotImplementedError

    def writable(self):
        raise NotImplementedError

    def handle_read_event(self):
        raise NotImplementedError

    def handle_write_event(self):
        raise NotImplementedError

    def handle_error(self):
        nil, t, v, tbinfo = compact_traceback()

        self.process.config.options.logger.critical(
            'uncaptured python exception, closing channel %s (%s:%s %s)' % (
                repr(self),
                t,
                v,
                tbinfo
                )
            )
        self.close()

    def close(self):
        if not self.closed:
            self.process.config.options.logger.debug(
                'fd %s closed, stopped monitoring %s' % (self.fd, self))
            self.closed = True

    def flush(self):
        pass

class POutputDispatcher(PDispatcher):
    """ Output (stdout/stderr) dispatcher, capture output sent within
    <!--XSUPERVISOR:BEGIN--><!--XSUPERVISOR:END--> tags and notify
    with a ProcessCommunicationEvent """

    process = None # process which "owns" this dispatcher
    channel = None # 'stderr' or 'stdout'
    capturemode = False # are we capturing process event data
    mainlog = None #  the process' "normal" logger
    capturelog = None # the logger while we're in capturemode
    capturefile = None # the capture file name
    childlog = None # the current logger (event or main)
    output_buffer = '' # data waiting to be logged

    def __init__(self, process, event_type, fd):
        self.process = process
        self.event_type = event_type
        self.fd = fd
        self.channel = channel = self.event_type.channel

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
                rotating=True,
                maxbytes=1 << 21, #2MB
                backups=10)

        self.childlog = self.mainlog

        # this is purely for a minor speedup
        begintoken = self.event_type.BEGIN_TOKEN
        endtoken = self.event_type.END_TOKEN
        self.begintoken_data = (begintoken, len(begintoken))
        self.endtoken_data = (endtoken, len(endtoken))

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

    def _log(self, data):
        if data:
            config = self.process.config
            if config.options.strip_ansi:
                data = config.options.stripEscapes(data)
            if self.childlog:
                self.childlog.info(data)
            msg = '%r %s output:\n%s' % (config.name, self.channel, data)
            self.process.config.options.logger.trace(msg)

    def record_output(self):
        if self.capturelog is None:
            # shortcut trying to find capture data
            data = self.output_buffer
            self.output_buffer = ''
            self._log(data)
            return
            
        if self.capturemode:
            token, tokenlen = self.endtoken_data
        else:
            token, tokenlen = self.begintoken_data

        data = self.output_buffer
        self.output_buffer = ''

        if len(data) <= tokenlen:
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
            self._log(data)
        else:
            self._log(before)
            self.toggle_capturemode()
            self.output_buffer = after

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
                event = self.event_type(self.process, self.process.pid, data)
                notify(event)
                                        
                msg = "%r %s emitted a comm event" % (procname, channel)
                self.process.config.options.logger.trace(msg)
                                        
                for handler in self.capturelog.handlers:
                    handler.remove()
                    handler.reopen()
                self.childlog = self.mainlog

    def writable(self):
        return False
    
    def readable(self):
        if self.closed:
            return False
        return True

    def handle_read_event(self):
        data = self.process.config.options.readfd(self.fd)
        self.output_buffer += data
        self.record_output()
        if not data:
            # if we get no data back from the pipe, it means that the
            # child process has ended.  See
            # mail.python.org/pipermail/python-dev/2004-August/046850.html
            self.close()

class PEventListenerDispatcher(PDispatcher):
    """ An output dispatcher that monitors and changes listener_states """
    process = None # process which "owns" this dispatcher
    channel = None # 'stderr' or 'stdout'
    childlog = None # the logger
    state_buffer = ''  # data waiting to be reviewed for state changes

    READY_FOR_EVENTS_TOKEN = 'READY\n'
    EVENT_PROCESSED_TOKEN = 'OK\n'
    EVENT_REJECTED_TOKEN = 'FAIL\n'

    def __init__(self, process, channel, fd):
        self.process = process
        # the initial state of our listener is ACKNOWLEDGED; this is a
        # "busy" state that implies we're awaiting a READY_FOR_EVENTS_TOKEN
        self.process.listener_state = EventListenerStates.ACKNOWLEDGED
        self.process.event = None
        self.channel = channel
        self.fd = fd

        logfile = getattr(process.config, '%s_logfile' % channel)

        if logfile:
            maxbytes = getattr(process.config, '%s_logfile_maxbytes' % channel)
            backups = getattr(process.config, '%s_logfile_backups' % channel)
            self.childlog = process.config.options.getLogger(
                logfile,
                logging.INFO,
                '%(message)s',
                rotating=not not maxbytes, # optimization
                maxbytes=maxbytes,
                backups=backups)
    
    def removelogs(self):
        if self.childlog is not None:
            for handler in self.childlog.handlers:
                handler.remove()
                handler.reopen()

    def reopenlogs(self):
        if self.childlog is not None:
            for handler in self.childlog.handlers:
                handler.reopen()


    def writable(self):
        return False
    
    def readable(self):
        if self.closed:
            return False
        return True

    def handle_read_event(self):
        data = self.process.config.options.readfd(self.fd)
        if data:
            self.state_buffer += data
            procname = self.process.config.name
            msg = '%r %s output:\n%s' % (procname, self.channel, data)
            self.process.config.options.logger.trace(msg)

            if self.childlog:
                if self.process.config.options.strip_ansi:
                    data = self.process.config.options.stripEscapes(data)
                self.childlog.info(data)
        else:
            # if we get no data back from the pipe, it means that the
            # child process has ended.  See
            # mail.python.org/pipermail/python-dev/2004-August/046850.html
            self.close()

        self.handle_listener_state_change()

    def handle_listener_state_change(self):
        data = self.state_buffer

        if not data:
            return

        process = self.process
        procname = process.config.name
        state = process.listener_state

        if state == EventListenerStates.UNKNOWN:
            # this is a fatal state
            self.state_buffer = ''
            return

        if state == EventListenerStates.ACKNOWLEDGED:
            tokenlen = len(self.READY_FOR_EVENTS_TOKEN)
            if len(data) < tokenlen:
                # not enough info to make a decision
                return
            elif data.startswith(self.READY_FOR_EVENTS_TOKEN):
                msg = '%s: ACKNOWLEDGED -> READY' % procname
                process.config.options.logger.trace(msg)
                process.listener_state = EventListenerStates.READY
                self.state_buffer = self.state_buffer[tokenlen:]
                process.event = None
            else:
                msg = '%s: ACKNOWLEDGED -> UNKNOWN' % procname
                process.config.options.logger.trace(msg)
                process.listener_state = EventListenerStates.UNKNOWN
                self.state_buffer = ''
                process.event = None
            if self.state_buffer:
                # keep going til its too short
                self.handle_listener_state_change()
            else:
                return

        elif state == EventListenerStates.READY:
            # the process sent some spurious data, be a hardass about it
            msg = '%s: READY -> UNKNOWN' % procname
            process.config.options.logger.trace(msg)
            process.listener_state = EventListenerStates.UNKNOWN
            self.state_buffer = ''
            process.event = None
            return
                
        elif state == EventListenerStates.BUSY:
            if data.find('\n') == -1:
                # we can't make a determination yet
                return
            elif data.startswith(self.EVENT_PROCESSED_TOKEN):
                msg = '%s: BUSY -> ACKNOWLEDGED (processed)' % procname
                process.config.options.logger.trace(msg)
                tokenlen = len(self.EVENT_PROCESSED_TOKEN)
                self.state_buffer = self.state_buffer[tokenlen:]
                process.listener_state = EventListenerStates.ACKNOWLEDGED
                process.event = None
            elif data.startswith(self.EVENT_REJECTED_TOKEN):
                msg = '%s: BUSY -> ACKNOWLEDGED (rejected)' % procname
                process.config.options.logger.trace(msg)
                tokenlen = len(self.EVENT_REJECTED_TOKEN)
                self.state_buffer = self.state_buffer[tokenlen:]
                process.listener_state = EventListenerStates.ACKNOWLEDGED
                notify(EventRejectedEvent(process, process.event))
                process.event = None
            else:
                msg = '%s: BUSY -> UNKNOWN' % procname
                process.config.options.logger.trace(msg)
                process.listener_state = EventListenerStates.UNKNOWN
                self.state_buffer = ''
                notify(EventRejectedEvent(process, process.event))
                process.event = None
            if self.state_buffer:
                # keep going til its too short
                self.handle_listener_state_change()
            else:
                return

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
        if self.input_buffer and not self.closed:
            return True
        return False

    def readable(self):
        return False

    def flush(self):
        # other code depends on this raising EPIPE if the pipe is closed
        sent = self.process.config.options.write(self.fd,
                                                 self.input_buffer)
        self.input_buffer = self.input_buffer[sent:]
    
    def handle_write_event(self):
        if self.input_buffer:
            try:
                self.flush()
            except OSError, why:
                if why[0] == errno.EPIPE:
                    self.input_buffer = ''
                    self.close()
                else:
                    raise

