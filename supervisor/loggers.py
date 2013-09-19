"""
Logger implementation loosely modeled on PEP 282.  We don't use the
PEP 282 logger implementation in the stdlib ('logging') because it's
idiosyncratic and a bit slow for our purposes (we don't use threads).
"""

# This module must not depend on any non-stdlib modules to
# avoid circular import problems

import os
import errno
import sys
import time
import traceback
import types

from supervisor.compat import syslog
from supervisor.compat import long

class LevelsByName:
    CRIT = 50   # messages that probably require immediate user attention
    ERRO = 40   # messages that indicate a potentially ignorable error condition
    WARN = 30   # messages that indicate issues which aren't errors
    INFO = 20   # normal informational output
    DEBG = 10   # messages useful for users trying to debug configurations
    TRAC = 5    # messages useful to developers trying to debug plugins
    BLAT = 3    # messages useful for developers trying to debug supervisor

class LevelsByDescription:
    critical = LevelsByName.CRIT
    error = LevelsByName.ERRO
    warn = LevelsByName.WARN
    info = LevelsByName.INFO
    debug = LevelsByName.DEBG
    trace = LevelsByName.TRAC
    blather = LevelsByName.BLAT

def _levelNumbers():
    bynumber = {}
    for name, number in LevelsByName.__dict__.items():
        if not name.startswith('_'):
            bynumber[number] = name
    return bynumber

LOG_LEVELS_BY_NUM = _levelNumbers()

def getLevelNumByDescription(description):
    num = getattr(LevelsByDescription, description, None)
    return num

class Handler:
    fmt = '%(message)s'
    level = LevelsByName.INFO

    def __init__(self, stream=None):
        self.stream = stream
        self.closed = False

    def setFormat(self, fmt):
        self.fmt = fmt

    def setLevel(self, level):
        self.level = level

    def flush(self):
        try:
            self.stream.flush()
        except IOError as why:
            # if supervisor output is piped, EPIPE can be raised at exit
            if why.args[0] != errno.EPIPE:
                raise

    def close(self):
        if not self.closed:
            if hasattr(self.stream, 'fileno'):
                try:
                    fd = self.stream.fileno()
                except IOError:
                    # on python 3, io.IOBase objects always have fileno()
                    # but calling it may raise io.UnsupportedOperation
                    pass
                else:
                    if fd < 3: # don't ever close stdout or stderr
                        return
            self.stream.close()
            self.closed = True

    def emit(self, record):
        try:
            msg = self.fmt % record.asdict()
            try:
                self.stream.write(msg)
            except UnicodeError:
                self.stream.write(msg.encode("UTF-8"))
            self.flush()
        except:
            self.handleError()

    def handleError(self):
        ei = sys.exc_info()
        traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)
        del ei

class StreamHandler(Handler):
    def __init__(self, strm=None):
        Handler.__init__(self, strm)

    def remove(self):
        if hasattr(self.stream, 'clear'):
            self.stream.clear()

    def reopen(self):
        pass

class BoundIO:
    def __init__(self, maxbytes, buf=''):
        self.maxbytes = maxbytes
        self.buf = buf

    def flush(self):
        pass

    def close(self):
        self.clear()

    def write(self, s):
        slen = len(s)
        if len(self.buf) + slen > self.maxbytes:
            self.buf = self.buf[slen:]
        self.buf += s

    def getvalue(self):
        return self.buf

    def clear(self):
        self.buf = ''

class FileHandler(Handler):
    """File handler which supports reopening of logs.
    """

    def __init__(self, filename, mode="a"):
        Handler.__init__(self)
        self.stream = open(filename, mode)
        self.baseFilename = filename
        self.mode = mode

    def reopen(self):
        self.close()
        self.stream = open(self.baseFilename, self.mode)
        self.closed = False

    def remove(self):
        self.close()
        try:
            os.remove(self.baseFilename)
        except OSError as why:
            if why.args[0] != errno.ENOENT:
                raise

class RotatingFileHandler(FileHandler):
    def __init__(self, filename, mode='a', maxBytes=512*1024*1024,
                 backupCount=10):
        """
        Open the specified file and use it as the stream for logging.

        By default, the file grows indefinitely. You can specify particular
        values of maxBytes and backupCount to allow the file to rollover at
        a predetermined size.

        Rollover occurs whenever the current log file is nearly maxBytes in
        length. If backupCount is >= 1, the system will successively create
        new files with the same pathname as the base file, but with extensions
        ".1", ".2" etc. appended to it. For example, with a backupCount of 5
        and a base file name of "app.log", you would get "app.log",
        "app.log.1", "app.log.2", ... through to "app.log.5". The file being
        written to is always "app.log" - when it gets filled up, it is closed
        and renamed to "app.log.1", and if files "app.log.1", "app.log.2" etc.
        exist, then they are renamed to "app.log.2", "app.log.3" etc.
        respectively.

        If maxBytes is zero, rollover never occurs.
        """
        if maxBytes > 0:
            mode = 'a' # doesn't make sense otherwise!
        FileHandler.__init__(self, filename, mode)
        self.maxBytes = maxBytes
        self.backupCount = backupCount
        self.counter = 0
        self.every = 10

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().
        """
        FileHandler.emit(self, record)
        self.doRollover()

    def _remove(self, fn): # pragma: no cover
        # this is here to service stubbing in unit tests
        return os.remove(fn)

    def _rename(self, src, tgt): # pragma: no cover
        # this is here to service stubbing in unit tests
        return os.rename(src, tgt)

    def _exists(self, fn): # pragma: no cover
        # this is here to service stubbing in unit tests
        return os.path.exists(fn)

    def removeAndRename(self, sfn, dfn):
        if self._exists(dfn):
            try:
                self._remove(dfn)
            except OSError as why:
                # catch race condition (destination already deleted)
                if why.args[0] != errno.ENOENT:
                    raise
        try:
            self._rename(sfn, dfn)
        except OSError as why:
            # catch exceptional condition (source deleted)
            # E.g. cleanup script removes active log.
            if why.args[0] != errno.ENOENT:
                raise

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.maxBytes <= 0:
            return

        if not (self.stream.tell() >= self.maxBytes):
            return

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    self.removeAndRename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            self.removeAndRename(self.baseFilename, dfn)
        self.stream = open(self.baseFilename, 'w')

class LogRecord:
    def __init__(self, level, msg, **kw):
        self.level = level
        self.msg = msg
        self.kw = kw
        self.dictrepr = None

    def asdict(self):
        if self.dictrepr is None:
            now = time.time()
            msecs = (now - long(now)) * 1000
            part1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
            asctime = '%s,%03d' % (part1, msecs)
            levelname = LOG_LEVELS_BY_NUM[self.level]
            if self.kw:
                msg = self.msg % self.kw
            else:
                msg = self.msg
            self.dictrepr = {'message':msg, 'levelname':levelname,
                             'asctime':asctime}
        return self.dictrepr

class Logger:
    def __init__(self, level=None, handlers=None):
        if level is None:
            level = LevelsByName.INFO
        self.level = level

        if handlers is None:
            handlers = []
        self.handlers = handlers

    def close(self):
        for handler in self.handlers:
            handler.close()

    def blather(self, msg, **kw):
        if LevelsByName.BLAT >= self.level:
            self.log(LevelsByName.BLAT, msg, **kw)

    def trace(self, msg, **kw):
        if LevelsByName.TRAC >= self.level:
            self.log(LevelsByName.TRAC, msg, **kw)

    def debug(self, msg, **kw):
        if LevelsByName.DEBG >= self.level:
            self.log(LevelsByName.DEBG, msg, **kw)

    def info(self, msg, **kw):
        if LevelsByName.INFO >= self.level:
            self.log(LevelsByName.INFO, msg, **kw)

    def warn(self, msg, **kw):
        if LevelsByName.WARN >= self.level:
            self.log(LevelsByName.WARN, msg, **kw)

    def error(self, msg, **kw):
        if LevelsByName.ERRO >= self.level:
            self.log(LevelsByName.ERRO, msg, **kw)

    def critical(self, msg, **kw):
        if LevelsByName.CRIT >= self.level:
            self.log(LevelsByName.CRIT, msg, **kw)

    def log(self, level, msg, **kw):
        record = LogRecord(level, msg, **kw)
        for handler in self.handlers:
            if level >= handler.level:
                handler.emit(record)

    def addHandler(self, hdlr):
        self.handlers.append(hdlr)

    def getvalue(self):
        raise NotImplementedError


level_to_syslog = {
    LevelsByName.CRIT: syslog.LOG_CRIT,
    LevelsByName.ERRO: syslog.LOG_ERR,
    LevelsByName.WARN: syslog.LOG_WARNING,
    LevelsByName.INFO: syslog.LOG_NOTICE,
    LevelsByName.DEBG: syslog.LOG_DEBUG,
}


class SyslogHandler(Handler):
    def __init__(self, tag=None, pid=False, facility="daemon", priority=None):
        self.tag = tag or "supervisord"
        def _int_string_or_none(val):
            return val if isinstance(val, (int, type(None))) else (
                getattr(syslog, "LOG_" + val.upper(), None)
            )

        self.priority = _int_string_or_none(priority)
        self.facility = _int_string_or_none(facility)
        self.options = syslog.LOG_PID if pid else 0
        assert 'syslog' in globals(), "Syslog module not present"

    def close(self):
        pass

    def reopen(self):
        pass

    def _syslog(self, priority, msg): # pragma: no cover
        # this exists only for unit test stubbing
        syslog.syslog(priority, msg)

    def emit(self, record):
        try:
            params = record.asdict()
            priority = self.priority or level_to_syslog.get(
                record.level, syslog.LOG_WARNING
            )
            message = params['message']
            syslog.openlog(self.tag, self.options, self.facility)
            for line in message.rstrip('\n').split('\n'):
                params['message'] = line
                msg = self.fmt % params
                try:
                    self._syslog(priority, msg)
                except UnicodeError:
                    self._syslog(priority, msg.encode("UTF-8"))
        except:
            self.handleError()

def getLogger(level=None):
    return Logger(level)

_2MB = 1<<21

def handle_boundIO(logger, fmt, maxbytes=_2MB):
    io = BoundIO(maxbytes)
    handler = StreamHandler(io)
    handler.setLevel(logger.level)
    handler.setFormat(fmt)
    logger.addHandler(handler)
    logger.getvalue = io.getvalue

    return logger

def handle_stdout(logger, fmt):
    handler = StreamHandler(sys.stdout)
    handler.setFormat(fmt)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

def handle_syslog(logger, fmt, tag=None, show_pid=None, facility=None,
                  priority=None):
    handler = SyslogHandler(tag, show_pid, facility, priority)
    handler.setFormat(fmt)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

def handle_file(logger, filename, fmt, rotating=False, maxbytes=0, backups=0):
    if rotating is False:
        handler = FileHandler(filename)
    else:
        handler = RotatingFileHandler(filename, 'a', maxbytes, backups)

    handler.setFormat(fmt)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

    return logger
