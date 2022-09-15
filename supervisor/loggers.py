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
import logging
import json
import re

from supervisor.compat import syslog
from supervisor.compat import long
from supervisor.compat import is_text_stream
from supervisor.compat import as_string
from supervisor.compat import as_bytes
from supervisor.jsonformatter import JsonFormatter
from string import Template
from string import Formatter as StrFormatter
from collections import OrderedDict


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
_str_formatter = StrFormatter()
del StrFormatter

def getLevelNumByDescription(description):
    num = getattr(LevelsByDescription, description, None)
    return num

class PercentStyle(logging.PercentStyle):
    validation_pattern = re.compile(r'%\(\w+\)[#0+ -]*(\*|\d+)?(\.(\*|\d+))?[diouxefgcrsa%]', re.I)

    def validate(self):
        """Validate the input format, ensure it matches the correct style"""
        if not self.validation_pattern.search(self._fmt):
            raise ValueError("Invalid format '%s' for '%s' style" % (self._fmt, self.default_format[0]))

class StrFormatStyle(logging.StrFormatStyle):
    fmt_spec = re.compile(r'^(.?[<>=^])?[+ -]?#?0?(\d+|{\w+})?[,_]?(\.(\d+|{\w+}))?[bcdefgnosx%]?$', re.I)
    field_spec = re.compile(r'^(\d+|\w+)(\.\w+|\[[^]]+\])*$')

    def _format(self, record):
        return self._fmt.format(**record.__dict__)

    def validate(self):
        """Validate the input format, ensure it is the correct string formatting style"""
        fields = set()
        try:
            for _, fieldname, spec, conversion in _str_formatter.parse(self._fmt):
                if fieldname:
                    if not self.field_spec.match(fieldname):
                        raise ValueError('invalid field name/expression: %r' % fieldname)
                    fields.add(fieldname)
                if conversion and conversion not in 'rsa':
                    raise ValueError('invalid conversion: %r' % conversion)
                if spec and not self.fmt_spec.match(spec):
                    raise ValueError('bad specifier: %r' % spec)
        except ValueError as e:
            raise ValueError('invalid format: %s' % e)
        if not fields:
            raise ValueError('invalid format: no fields')


class StringTemplateStyle(logging.StringTemplateStyle):
    def validate(self):
        pattern = Template.pattern
        fields = set()
        for m in pattern.finditer(self._fmt):
            d = m.groupdict()
            if d['named']:
                fields.add(d['named'])
            elif d['braced']:
                fields.add(d['braced'])
            elif m.group(0) == '$':
                raise ValueError('invalid format: bare \'$\' not allowed')
        if not fields:
            raise ValueError('invalid format: no fields')

BASIC_FORMAT = "%(message)s"
_STYLES = {
    '%': (PercentStyle, BASIC_FORMAT),
    '$': (StringTemplateStyle, '${message}'),
    '{': (StrFormatStyle, '{message}')
}

class PlainTextFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        """Constructor."""
        self.fields_with_default_value = kwargs.pop('fields_with_default_value', {})
        self.fmt_terminator = ''

        fmt = args[0]
        if fmt.endswith('\n'):
            self.fmt_terminator = '\n'
            fmt = fmt.rstrip('\n')
        elif fmt.endswith('\\n'):
            self.fmt_terminator = '\n'
            fmt = fmt.rstrip('\\n')
        args = (fmt,) + args[1:]

        super().__init__(*args, **kwargs)


    def format(self, record):
        # Add the fields with the default values first and then
        # overwrite the default values with the existing LogReocrd fields.
        _record = self.fields_with_default_value.copy()
        _record.update(record.__dict__)
        record.__dict__ = _record

        record.message = record.getMessage()

        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        return self.formatMessage(record) + self.fmt_terminator

class CustomJsonFormatter(JsonFormatter):
    def __init__(self, *args, **kwargs):
        """Constructor."""
        self.fields_with_default_value = kwargs.pop('fields_with_default_value', {})
        super().__init__(*args, **kwargs)
        reserved_attrs = ('level', 'levelname', 'msg', 'kw', 'dictrepr', 'created', 'msecs')
        self._skip_fields.update((v, v) for v in reserved_attrs)
        self.fmt_terminator = '\n'

    def parse(self):
        """
        Parses format string looking for substitutions
        This method is responsible for returning a list of fields (as strings)
        to include in all log messages.
        """
        if isinstance(self._style, logging.StringTemplateStyle):
            formatter_style_pattern = re.compile(r'\$\{(.+?)\}', re.IGNORECASE)
        elif isinstance(self._style, logging.StrFormatStyle):
            formatter_style_pattern = re.compile(r'\{(.+?)\}', re.IGNORECASE)
        # PercentStyle is parent class of StringTemplateStyle and StrFormatStyle so
        # it needs to be checked last.
        elif isinstance(self._style, logging.PercentStyle):
            formatter_style_pattern = re.compile(r'%\((.+?)\)s', re.IGNORECASE)
        else:
            raise ValueError('Invalid format: %s' % self._fmt)
        return formatter_style_pattern.findall(self._fmt)

    def serialize_log_record(self, log_record):
        """Returns the final representation of the log record."""
        return "%s%s" % (self.prefix, self.jsonify_log_record(log_record))

    def format(self, record):
        """Formats a log record and serializes to json"""
        # Add the fields with the default values first and then
        # overwrite the default values with the existing LogReocrd fields.
        _record = self.fields_with_default_value.copy()
        _record.update(record.__dict__)
        record.__dict__ = _record

        message_dict = {}
        if isinstance(record.msg, dict):
            message_dict = record.msg
            record.message = None
        else:
            message = record.getMessage()
            try:
                json_message = json.loads(message)
                # The json parser accepts numbers as a valid json.
                # But we want json objects only.
                if isinstance(json_message, dict):
                    message_dict = json_message
                    record.message = None
                else:
                    del json_message
                    record.message = as_string(message).rstrip('\n')
            except json.decoder.JSONDecodeError:
                record.message = as_string(message).rstrip('\n')

        # only format time if needed
        if "asctime" in self._required_fields:
            record.asctime = self.formatTime(record, self.datefmt)

        try:
            log_record = OrderedDict()
        except NameError:
            log_record = {}

        self.add_fields(log_record, record, message_dict)
        log_record = self.process_log_record(log_record)
        return self.serialize_log_record(log_record) + self.fmt_terminator


class FormatterFactory:
    def get_formatter(self, name=None, fmt=None, style=None):
        if name is None:
            name = 'plaintext'

        if fmt is None:
            fmt = '%(asctime)s %(levelname)s %(message)s'

        fmt, fields_with_default_value = self.get_fields_default_values(fmt)

        if style is None:
            style = self.get_logformat_style(fmt)

        if name == 'plaintext':
            return PlainTextFormatter(fmt, style=style, fields_with_default_value=fields_with_default_value)
        if name == 'json':
            return CustomJsonFormatter(fmt, style=style, fields_with_default_value=fields_with_default_value)
        raise ValueError('Invalid formatter name: %s' % name)

    def get_logformat_style(self, fmt):
        """Determine the string format style based on the logformat."""
        for style in _STYLES:
            _style = _STYLES[style][0](fmt)
            try:
                _style.validate()
                return style # return style if fmt passes style validation
            except ValueError:
                style = None
        else:
            raise ValueError('Invalid logging format: %s (%s)' % (fmt, type(fmt)))

    def get_fields_default_values(self, fmt):
        fields_with_default_value = {}
        placeholder_pattern = re.compile(r'[\{\(](.+?)[\}\)]', re.IGNORECASE)
        for placeholder in placeholder_pattern.findall(fmt):
            kv = placeholder.split(':', 1)
            if len(kv) == 2:
                key, val = kv
                fields_with_default_value[key] = val
                # remove the default value from the format string
                fmt = fmt.replace(placeholder, key)
        return fmt, fields_with_default_value


_formatter_factory = FormatterFactory().get_formatter
BASIC_FORMATTER = _formatter_factory(name='plaintext', fmt=BASIC_FORMAT)

class Handler:
    level = LevelsByName.INFO
    terminator = ''

    def __init__(self, stream=None):
        self.stream = stream
        self.closed = False
        self.formatter = BASIC_FORMATTER

    def setFormatter(self, formatter):
        if type(formatter) not in [PlainTextFormatter, CustomJsonFormatter]:
            raise ValueError('Invalid formatter: %s (%s)' % (formatter, type(formatter)))
        self.formatter = formatter

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
            msg = self.formatter.format(record)
            try:
                self.stream.write(msg)
            except UnicodeError:
                # TODO sort out later
                # this only occurs because of a test stream type
                # which deliberately raises an exception the first
                # time it's called. So just do it again
                self.stream.write(msg + self.terminator)
            self.flush()
        except:
            self.handleError()

    def handleError(self):
        ei = sys.exc_info()
        traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)
        del ei

class StreamHandler(Handler):
    terminator = ''

    def __init__(self, strm=None):
        Handler.__init__(self, strm)

    def remove(self):
        if hasattr(self.stream, 'clear'):
            self.stream.clear()

    def reopen(self):
        pass

class BoundIO:
    def __init__(self, maxbytes, buf=b''):
        self.maxbytes = maxbytes
        self.buf = buf

    def flush(self):
        pass

    def close(self):
        self.clear()

    def write(self, b):
        blen = len(b)
        if len(self.buf) + blen > self.maxbytes:
            self.buf = self.buf[blen:]
        self.buf += as_bytes(b)

    def getvalue(self):
        return self.buf

    def clear(self):
        self.buf = b''

class FileHandler(Handler):
    """File handler which supports reopening of logs.
    """
    terminator = ''

    def __init__(self, filename, mode='ab'):
        Handler.__init__(self)

        try:
            self.stream = open(filename, mode)
        except OSError as e:
            if mode == 'ab' and e.errno == errno.ESPIPE:
                # Python 3 can't open special files like
                # /dev/stdout in 'a' mode due to an implicit seek call
                # that fails with ESPIPE. Retry in 'w' mode.
                # See: http://bugs.python.org/issue27805
                mode = 'wb'
                self.stream = open(filename, mode)
            else:
                raise

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

    def emit(self, record):
        try:
            msg = self.formatter.format(record)
            if 'b' in self.mode:
                msg = as_bytes(msg + self.terminator)
                self.stream.write(msg)
            else:
                self.stream.write(msg + self.terminator)
            self.flush()
        except:
            self.handleError()

class RotatingFileHandler(FileHandler):
    def __init__(self, filename, mode='ab', maxBytes=512*1024*1024,
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
            mode = 'ab' # doesn't make sense otherwise!
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
        self.stream = open(self.baseFilename, 'wb')

class LogRecord:
    def __init__(self, level, msg, **kw):
        self.level = level
        self.levelname = LOG_LEVELS_BY_NUM[level]
        self.msg = msg
        self.kw = kw
        self.dictrepr = None
        self.created = time.time()
        self.msecs = (self.created - int(self.created)) * 1000

    def asdict(self):
        if self.dictrepr is None:
            ct = self.created
            msecs = (ct - long(ct)) * 1000
            part1 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ct))
            asctime = '%s,%03d' % (part1, msecs)
            levelname = LOG_LEVELS_BY_NUM[self.level]
            msg = as_string(self.msg)
            if self.kw:
                msg = msg % self.kw
            self.dictrepr = {'message':msg, 'levelname':levelname,
                             'asctime':asctime}
        return self.dictrepr

    def getMessage(self):
        if self.kw:
            try:
                return as_string(self.msg) % self.kw
            except ValueError as e:
                # Skip string interpolation when string
                # formatting charcaters are not escaped.
                return as_string(self.msg)
        else:
            return as_string(self.msg)

class Logger:
    def __init__(self, level=None, handlers=None):
        if level is None:
            level = LevelsByName.INFO
        elif isinstance(level, str):
            level = getLevelNumByDescription(level)
        if not (LevelsByName.BLAT <= level <= LevelsByName.CRIT):
            raise ValueError("Bad logger level value: '%s'" % level)
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

class SyslogHandler(Handler):
    def __init__(self):
        self.fmt = '%(message)s'
        Handler.__init__(self)
        assert syslog is not None, "Syslog module not present"

    def close(self):
        pass

    def reopen(self):
        pass

    def _syslog(self, msg): # pragma: no cover
        # this exists only for unit test stubbing
        syslog.syslog(msg)

    def emit(self, record):
        try:
            params = record.asdict()
            message = params['message']
            for line in message.rstrip('\n').split('\n'):
                params['message'] = line
                msg = self.fmt % params # TODO: Use parent Handler formatter.
                try:
                    self._syslog(msg)
                except UnicodeError:
                    self._syslog(msg.encode("UTF-8"))
        except:
            self.handleError()

def getLogger(level=None):
    return Logger(level)

_2MB = 1<<21

def handle_boundIO(logger, fmt, formatter=None, maxbytes=_2MB):
    """Attach a new BoundIO handler to an existing Logger"""
    io = BoundIO(maxbytes)
    handler = StreamHandler(io)
    handler.setLevel(logger.level)
    _formatter = _formatter_factory(name=formatter, fmt=fmt)
    handler.setFormatter(_formatter)
    logger.addHandler(handler)
    logger.getvalue = io.getvalue

def handle_stdout(logger, fmt, formatter=None):
    """Attach a new StreamHandler with stdout handler to an existing Logger"""
    handler = StreamHandler(sys.stdout)
    _formatter = _formatter_factory(name=formatter, fmt=fmt)
    handler.setFormatter(_formatter)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

def handle_syslog(logger, fmt, formatter=None):
    """Attach a new Syslog handler to an existing Logger"""
    handler = SyslogHandler()
    _formatter = _formatter_factory(name=formatter, fmt=fmt)
    handler.setFormatter(_formatter)
    handler.setLevel(logger.level)
    logger.addHandler(handler)

def handle_file(logger, filename, fmt, formatter=None, rotating=False, maxbytes=0, backups=0):
    """Attach a new file handler to an existing Logger. If the filename
    is the magic name of 'syslog' then make it a syslog handler instead."""
    if filename == 'syslog': # TODO remove this
        handler = SyslogHandler()
    else:
        if rotating is False:
            handler = FileHandler(filename)
        else:
            handler = RotatingFileHandler(filename, 'a', maxbytes, backups)

    _formatter = _formatter_factory(name=formatter, fmt=fmt)
    handler.setFormatter(_formatter)
    handler.setLevel(logger.level)
    logger.addHandler(handler)
