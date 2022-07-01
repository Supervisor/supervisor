import errno
from supervisor.medusa.asynchat_25 import find_prefix_at_end
from supervisor.medusa.asyncore_25 import compact_traceback

from supervisor.compat import as_string
from supervisor.events import notify
from supervisor.events import EventRejectedEvent
from supervisor.events import ProcessLogStderrEvent
from supervisor.events import ProcessLogStdoutEvent
from supervisor.states import EventListenerStates
from supervisor.states import getEventListenerStateDescription
from supervisor import loggers

class PDispatcher:
    """ Asyncore dispatcher for mainloop, representing a process channel
    (stdin, stdout, or stderr).  This class is abstract. """

    closed = False # True if close() has been called

    def __init__(self, process, channel, fd):
        self.process = process  # process which "owns" this dispatcher
        self.channel = channel  # 'stderr' or 'stdout'
        self.fd = fd
        self.closed = False     # True if close() has been called

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
    """
    Dispatcher for one channel (stdout or stderr) of one process.
    Serves several purposes:

    - capture output sent within <!--XSUPERVISOR:BEGIN--> and
      <!--XSUPERVISOR:END--> tags and signal a ProcessCommunicationEvent
      by calling notify(event).
    - route the output to the appropriate log handlers as specified in the
      config.
    """

    childlog = None # the current logger (normallog or capturelog)
    normallog = None # the "normal" (non-capture) logger
    capturelog = None # the logger used while we're in capturemode
    capturemode = False # are we capturing process event data
    output_buffer = b'' # data waiting to be logged

    def __init__(self, process, event_type, fd):
        """
        Initialize the dispatcher.

        `event_type` should be one of ProcessLogStdoutEvent or
        ProcessLogStderrEvent
        """
        self.process = process
        self.event_type = event_type
        self.fd = fd
        self.channel = self.event_type.channel

        self._init_normallog()
        self._init_capturelog()

        self.childlog = self.normallog

        # all code below is purely for minor speedups
        begintoken = self.event_type.BEGIN_TOKEN
        endtoken = self.event_type.END_TOKEN
        self.begintoken_data = (begintoken, len(begintoken))
        self.endtoken_data = (endtoken, len(endtoken))
        self.mainlog_level = loggers.LevelsByName.DEBG
        config = self.process.config
        self.log_to_mainlog = config.options.loglevel <= self.mainlog_level
        self.stdout_events_enabled = config.stdout_events_enabled
        self.stderr_events_enabled = config.stderr_events_enabled

    def _init_normallog(self):
        """
        Configure the "normal" (non-capture) log for this channel of this
        process.  Sets self.normallog if logging is enabled.
        """
        config = self.process.config
        channel = self.channel

        logfile = getattr(config, '%s_logfile' % channel)
        maxbytes = getattr(config, '%s_logfile_maxbytes' % channel)
        backups = getattr(config, '%s_logfile_backups' % channel)
        to_syslog = getattr(config, '%s_syslog' % channel)

        if logfile or to_syslog:
            self.normallog = config.options.getLogger()

        if logfile:
            loggers.handle_file(
                self.normallog,
                filename=logfile,
                fmt='%(message)s',
                rotating=not not maxbytes, # optimization
                maxbytes=maxbytes,
                backups=backups
            )

        if to_syslog:
            loggers.handle_syslog(
                self.normallog,
                fmt=config.name + ' %(message)s'
            )

    def _init_capturelog(self):
        """
        Configure the capture log for this process.  This log is used to
        temporarily capture output when special output is detected.
        Sets self.capturelog if capturing is enabled.
        """
        capture_maxbytes = getattr(self.process.config,
                                   '%s_capture_maxbytes' % self.channel)
        if capture_maxbytes:
            self.capturelog = self.process.config.options.getLogger()
            loggers.handle_boundIO(
                self.capturelog,
                fmt='%(message)s',
                maxbytes=capture_maxbytes,
                )

    def removelogs(self):
        for log in (self.normallog, self.capturelog):
            if log is not None:
                for handler in log.handlers:
                    handler.remove()
                    handler.reopen()

    def reopenlogs(self):
        for log in (self.normallog, self.capturelog):
            if log is not None:
                for handler in log.handlers:
                    handler.reopen()

    def _log(self, data):
        if data:
            config = self.process.config
            if config.options.strip_ansi:
                data = stripEscapes(data)
            if self.childlog:
                self.childlog.info(data)
            if self.log_to_mainlog:
                if not isinstance(data, bytes):
                    text = data
                else:
                    try:
                        text = data.decode('utf-8')
                    except UnicodeDecodeError:
                        text = 'Undecodable: %r' % data
                msg = '%(name)r %(channel)s output:\n%(data)s'
                config.options.logger.log(
                    self.mainlog_level, msg, name=config.name,
                    channel=self.channel, data=text)
            if self.channel == 'stdout':
                if self.stdout_events_enabled:
                    notify(
                        ProcessLogStdoutEvent(self.process,
                            self.process.pid, data)
                    )
            else: # channel == stderr
                if self.stderr_events_enabled:
                    notify(
                        ProcessLogStderrEvent(self.process,
                            self.process.pid, data)
                    )

    def record_output(self):
        if self.capturelog is None:
            # shortcut trying to find capture data
            data = self.output_buffer
            self.output_buffer = b''
            self._log(data)
            return

        if self.capturemode:
            token, tokenlen = self.endtoken_data
        else:
            token, tokenlen = self.begintoken_data

        if len(self.output_buffer) <= tokenlen:
            return # not enough data

        data = self.output_buffer
        self.output_buffer = b''

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
                for handler in self.capturelog.handlers:
                    handler.flush()
                data = self.capturelog.getvalue()
                channel = self.channel
                procname = self.process.config.name
                event = self.event_type(self.process, self.process.pid, data)
                notify(event)

                msg = "%(procname)r %(channel)s emitted a comm event"
                self.process.config.options.logger.debug(msg,
                                                         procname=procname,
                                                         channel=channel)
                for handler in self.capturelog.handlers:
                    handler.remove()
                    handler.reopen()
                self.childlog = self.normallog

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
    """ An output dispatcher that monitors and changes a process'
    listener_state """
    childlog = None # the logger
    state_buffer = b''  # data waiting to be reviewed for state changes

    READY_FOR_EVENTS_TOKEN = b'READY\n'
    RESULT_TOKEN_START = b'RESULT '
    READY_FOR_EVENTS_LEN = len(READY_FOR_EVENTS_TOKEN)
    RESULT_TOKEN_START_LEN = len(RESULT_TOKEN_START)

    def __init__(self, process, channel, fd):
        PDispatcher.__init__(self, process, channel, fd)
        # the initial state of our listener is ACKNOWLEDGED; this is a
        # "busy" state that implies we're awaiting a READY_FOR_EVENTS_TOKEN
        self.process.listener_state = EventListenerStates.ACKNOWLEDGED
        self.process.event = None
        self.result = b''
        self.resultlen = None

        logfile = getattr(process.config, '%s_logfile' % channel)

        if logfile:
            maxbytes = getattr(process.config, '%s_logfile_maxbytes' % channel)
            backups = getattr(process.config, '%s_logfile_backups' % channel)
            self.childlog = process.config.options.getLogger()
            loggers.handle_file(
                self.childlog,
                logfile,
                '%(message)s',
                rotating=not not maxbytes, # optimization
                maxbytes=maxbytes,
                backups=backups,
            )

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
            self.process.config.options.logger.debug(msg)

            if self.childlog:
                if self.process.config.options.strip_ansi:
                    data = stripEscapes(data)
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
            self.state_buffer = b''
            return

        if state == EventListenerStates.ACKNOWLEDGED:
            if len(data) < self.READY_FOR_EVENTS_LEN:
                # not enough info to make a decision
                return
            elif data.startswith(self.READY_FOR_EVENTS_TOKEN):
                self._change_listener_state(EventListenerStates.READY)
                tokenlen = self.READY_FOR_EVENTS_LEN
                self.state_buffer = self.state_buffer[tokenlen:]
                process.event = None
            else:
                self._change_listener_state(EventListenerStates.UNKNOWN)
                self.state_buffer = b''
                process.event = None
            if self.state_buffer:
                # keep going til its too short
                self.handle_listener_state_change()
            else:
                return

        elif state == EventListenerStates.READY:
            # the process sent some spurious data, be strict about it
            self._change_listener_state(EventListenerStates.UNKNOWN)
            self.state_buffer = b''
            process.event = None
            return

        elif state == EventListenerStates.BUSY:
            if self.resultlen is None:
                # we haven't begun gathering result data yet
                pos = data.find(b'\n')
                if pos == -1:
                    # we can't make a determination yet, we dont have a full
                    # results line
                    return

                result_line = self.state_buffer[:pos]
                self.state_buffer = self.state_buffer[pos+1:] # rid LF
                resultlen = result_line[self.RESULT_TOKEN_START_LEN:]
                try:
                    self.resultlen = int(resultlen)
                except ValueError:
                    try:
                        result_line = as_string(result_line)
                    except UnicodeDecodeError:
                        result_line = 'Undecodable: %r' % result_line
                    process.config.options.logger.warn(
                        '%s: bad result line: \'%s\'' % (procname, result_line)
                        )
                    self._change_listener_state(EventListenerStates.UNKNOWN)
                    self.state_buffer = b''
                    notify(EventRejectedEvent(process, process.event))
                    process.event = None
                    return

            else:
                needed = self.resultlen - len(self.result)

                if needed:
                    self.result += self.state_buffer[:needed]
                    self.state_buffer = self.state_buffer[needed:]
                    needed = self.resultlen - len(self.result)

                if not needed:
                    self.handle_result(self.result)
                    self.process.event = None
                    self.result = b''
                    self.resultlen = None

            if self.state_buffer:
                # keep going til its too short
                self.handle_listener_state_change()

    def handle_result(self, result):
        process = self.process
        procname = process.config.name
        logger = process.config.options.logger

        try:
            self.process.group.config.result_handler(process.event, result)
            logger.debug('%s: event was processed' % procname)
            self._change_listener_state(EventListenerStates.ACKNOWLEDGED)
        except RejectEvent:
            logger.warn('%s: event was rejected' % procname)
            self._change_listener_state(EventListenerStates.ACKNOWLEDGED)
            notify(EventRejectedEvent(process, process.event))
        except:
            logger.warn('%s: event caused an error' % procname)
            self._change_listener_state(EventListenerStates.UNKNOWN)
            notify(EventRejectedEvent(process, process.event))

    def _change_listener_state(self, new_state):
        process = self.process
        procname = process.config.name
        old_state = process.listener_state

        msg = '%s: %s -> %s' % (
            procname,
            getEventListenerStateDescription(old_state),
            getEventListenerStateDescription(new_state)
            )
        process.config.options.logger.debug(msg)

        process.listener_state = new_state
        if new_state == EventListenerStates.UNKNOWN:
            msg = ('%s: has entered the UNKNOWN state and will no longer '
                   'receive events, this usually indicates the process '
                   'violated the eventlistener protocol' % procname)
            process.config.options.logger.warn(msg)

class PInputDispatcher(PDispatcher):
    """ Input (stdin) dispatcher """

    def __init__(self, process, channel, fd):
        PDispatcher.__init__(self, process, channel, fd)
        self.input_buffer = b''

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
            except OSError as why:
                if why.args[0] == errno.EPIPE:
                    self.input_buffer = b''
                    self.close()
                else:
                    raise

ANSI_ESCAPE_BEGIN = b'\x1b['
ANSI_TERMINATORS = (b'H', b'f', b'A', b'B', b'C', b'D', b'R', b's', b'u', b'J',
                    b'K', b'h', b'l', b'p', b'm')

def stripEscapes(s):
    """
    Remove all ANSI color escapes from the given string.
    """
    result = b''
    show = 1
    i = 0
    L = len(s)
    while i < L:
        if show == 0 and s[i:i + 1] in ANSI_TERMINATORS:
            show = 1
        elif show:
            n = s.find(ANSI_ESCAPE_BEGIN, i)
            if n == -1:
                return result + s[i:]
            else:
                result = result + s[i:n]
                i = n
                show = 0
        i += 1
    return result

class RejectEvent(Exception):
    """ The exception type expected by a dispatcher when a handler wants
    to reject an event """

def default_handler(event, response):
    if response != b'OK':
        raise RejectEvent(response)
