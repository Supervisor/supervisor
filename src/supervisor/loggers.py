##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################

# this module must not depend on any non-stdlib modules to avoid circular
# import problems

import logging
import os
import errno
import sys

TRACE = 5
_initialized = False

def initialize():
    global _initialized
    if not _initialized:
        logging.addLevelName(logging.CRITICAL, 'CRIT')
        logging.addLevelName(logging.DEBUG, 'DEBG')
        logging.addLevelName(logging.INFO, 'INFO')
        logging.addLevelName(logging.WARN, 'WARN')
        logging.addLevelName(logging.ERROR, 'ERRO')
        logging.addLevelName(TRACE, 'TRAC')
        _initialized = True
    
class FileHandler(logging.StreamHandler):
    """File handler which supports reopening of logs.

    Re-opening should be used instead of the 'rollover' feature of
    the FileHandler from the standard library's logging package.
    """

    def __init__(self, filename, mode="a"):
        logging.StreamHandler.__init__(self, open(filename, mode))
        self.baseFilename = filename
        self.mode = mode

    def close(self):
        # logging module can be none at shutdown sys.exithook time (sigh),
        # see my rant in test_loggers.py
        if logging is not None: 
            logging.StreamHandler(self).close()
        self.stream.close()

    def reopen(self):
        self.close()
        self.stream = open(self.baseFilename, self.mode)

    def remove(self):
        if os.path.exists(self.baseFilename):
            os.remove(self.baseFilename)

class RawHandler:
    def emit(self, record):
        """
        Override the handler to not insert a linefeed during emit.
        """
        try:
            msg = self.format(record)
            try:
                self.stream.write(msg)
            except UnicodeError:
                self.stream.write(msg.encode("UTF-8"))
            self.flush()
        except:
            self.handleError(record)

class RawFileHandler(RawHandler, FileHandler):
    pass

class RawStreamHandler(RawHandler, logging.StreamHandler):
    def remove(self):
        pass

class RotatingRawFileHandler(RawFileHandler):
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
        RawFileHandler.__init__(self, filename, mode)
        self.maxBytes = maxBytes
        self.backupCount = backupCount

    def emit(self, record):
        """
        Emit a record.

        Output the record to the file, catering for rollover as described
        in doRollover().
        """
        try:
            if self.shouldRollover(record):
                self.doRollover()
            RawFileHandler.emit(self, record)
        except:
            self.handleError(record)

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """

        self.stream.close()
        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                sfn = "%s.%d" % (self.baseFilename, i)
                dfn = "%s.%d" % (self.baseFilename, i + 1)
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.baseFilename + ".1"
            if os.path.exists(dfn):
                os.remove(dfn)
            os.rename(self.baseFilename, dfn)
        self.stream = open(self.baseFilename, 'w')

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.
        """
        if self.maxBytes > 0:                   # are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  #due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        return 0
    
def getLogger(filename, level, fmt, rotating=False, maxbytes=0, backups=0,
              stdout=False):
    logger = logging.getLogger(filename)
    handlers = []

    if rotating is False:
        handlers.append(RawFileHandler(filename))
    else:
        handlers.append(RotatingRawFileHandler(filename,'a',maxbytes,backups))

    if stdout:
        handlers.append(RawStreamHandler(sys.stdout))

    logger.handlers = []
    logger.setLevel(level)
    formatter = logging.Formatter(fmt)
    
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.setLevel(level)
        logger.addHandler(handler)

    return logger

