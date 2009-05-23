# -*- Mode: Python -*-

#       Author: Sam Rushing <rushing@nightmare.com>
#       Copyright 1996-2000 by Sam Rushing
#                                                All Rights Reserved.
#

RCS_ID =  '$Id: ftp_server.py,v 1.11 2003/12/24 16:05:28 akuchling Exp $'

# An extensible, configurable, asynchronous FTP server.
#
# All socket I/O is non-blocking, however file I/O is currently
# blocking.  Eventually file I/O may be made non-blocking, too, if it
# seems necessary.  Currently the only CPU-intensive operation is
# getting and formatting a directory listing.  [this could be moved
# into another process/directory server, or another thread?]
#
# Only a subset of RFC 959 is implemented, but much of that RFC is
# vestigial anyway.  I've attempted to include the most commonly-used
# commands, using the feature set of wu-ftpd as a guide.

import asyncore_25 as asyncore
import asynchat_25 as asynchat

import os
import socket
import stat
import string
import sys
import time

from medusa.producers import file_producer

# TODO: implement a directory listing cache.  On very-high-load
# servers this could save a lot of disk abuse, and possibly the
# work of computing emulated unix ls output.

# Potential security problem with the FTP protocol?  I don't think
# there's any verification of the origin of a data connection.  Not
# really a problem for the server (since it doesn't send the port
# command, except when in PASV mode) But I think a data connection
# could be spoofed by a program with access to a sniffer - it could
# watch for a PORT command to go over a command channel, and then
# connect to that port before the server does.

# Unix user id's:
# In order to support assuming the id of a particular user,
# it seems there are two options:
# 1) fork, and seteuid in the child
# 2) carefully control the effective uid around filesystem accessing
#    methods, using try/finally. [this seems to work]

VERSION = string.split(RCS_ID)[2]

from counter import counter
import producers
import status_handler
import logger

class ftp_channel (asynchat.async_chat):

    # defaults for a reliable __repr__
    addr = ('unknown','0')

    # unset this in a derived class in order
    # to enable the commands in 'self.write_commands'
    read_only = 1
    write_commands = ['appe','dele','mkd','rmd','rnfr','rnto','stor','stou']

    restart_position = 0

    # comply with (possibly troublesome) RFC959 requirements
    # This is necessary to correctly run an active data connection
    # through a firewall that triggers on the source port (expected
    # to be 'L-1', or 20 in the normal case).
    bind_local_minus_one = 0

    def __init__ (self, server, conn, addr):
        self.server = server
        self.current_mode = 'a'
        self.addr = addr
        asynchat.async_chat.__init__ (self, conn)
        self.set_terminator ('\r\n')

        # client data port.  Defaults to 'the same as the control connection'.
        self.client_addr = (addr[0], 21)

        self.client_dc = None
        self.in_buffer = ''
        self.closing = 0
        self.passive_acceptor = None
        self.passive_connection = None
        self.filesystem = None
        self.authorized = 0
        # send the greeting
        self.respond (
                '220 %s FTP server (Medusa Async V%s [experimental]) ready.' % (
                        self.server.hostname,
                        VERSION
                        )
                )

#       def __del__ (self):
#               print 'ftp_channel.__del__()'

    # --------------------------------------------------
    # async-library methods
    # --------------------------------------------------

    def handle_expt (self):
        # this is handled below.  not sure what I could
        # do here to make that code less kludgish.
        pass

    def collect_incoming_data (self, data):
        self.in_buffer = self.in_buffer + data
        if len(self.in_buffer) > 4096:
            # silently truncate really long lines
            # (possible denial-of-service attack)
            self.in_buffer = ''

    def found_terminator (self):

        line = self.in_buffer

        if not len(line):
            return

        sp = string.find (line, ' ')
        if sp != -1:
            line = [line[:sp], line[sp+1:]]
        else:
            line = [line]

        command = string.lower (line[0])
        # watch especially for 'urgent' abort commands.
        if string.find (command, 'abor') != -1:
            # strip off telnet sync chars and the like...
            while command and command[0] not in string.letters:
                command = command[1:]
        fun_name = 'cmd_%s' % command
        if command != 'pass':
            self.log ('<== %s' % repr(self.in_buffer)[1:-1])
        else:
            self.log ('<== %s' % line[0]+' <password>')
        self.in_buffer = ''
        if not hasattr (self, fun_name):
            self.command_not_understood (line[0])
            return
        if hasattr(self,'_rnfr_src') and fun_name!='cmd_rnto':
            del self._rnfr_src
            self.respond ('503 RNTO Command expected!')
            return

        fun = getattr (self, fun_name)
        if (not self.authorized) and (command not in ('user', 'pass', 'help', 'quit')):
            self.respond ('530 Please log in with USER and PASS')
        elif (not self.check_command_authorization (command)):
            self.command_not_authorized (command)
        else:
            try:
                result = apply (fun, (line,))
            except:
                self.server.total_exceptions.increment()
                (file, fun, line), t,v, tbinfo = asyncore.compact_traceback()
                if self.client_dc:
                    try:
                        self.client_dc.close()
                    except:
                        pass
                self.respond (
                        '451 Server Error: %s, %s: file: %s line: %s' % (
                                t,v,file,line,
                                )
                        )

    closed = 0
    def close (self):
        if not self.closed:
            self.closed = 1
            if self.passive_acceptor:
                self.passive_acceptor.close()
            if self.client_dc:
                self.client_dc.close()
            self.server.closed_sessions.increment()
            asynchat.async_chat.close (self)

    # --------------------------------------------------
    # filesystem interface functions.
    # override these to provide access control or perform
    # other functions.
    # --------------------------------------------------

    def cwd (self, line):
        return self.filesystem.cwd (line[1])

    def cdup (self, line):
        return self.filesystem.cdup()

    def open (self, path, mode):
        return self.filesystem.open (path, mode)

    # returns a producer
    def listdir (self, path, long=0):
        return self.filesystem.listdir (path, long)

    def get_dir_list (self, line, long=0):
        # we need to scan the command line for arguments to '/bin/ls'...
        args = line[1:]
        path_args = []
        for arg in args:
            if arg[0] != '-':
                path_args.append (arg)
            else:
                # ignore arguments
                pass
        if len(path_args) < 1:
            dir = '.'
        else:
            dir = path_args[0]
        return self.listdir (dir, long)

    # --------------------------------------------------
    # authorization methods
    # --------------------------------------------------

    def check_command_authorization (self, command):
        if command in self.write_commands and self.read_only:
            return 0
        else:
            return 1

    # --------------------------------------------------
    # utility methods
    # --------------------------------------------------

    def log (self, message):
        self.server.logger.log (
                self.addr[0],
                '%d %s' % (
                        self.addr[1], message
                        )
                )

    def respond (self, resp):
        self.log ('==> %s' % resp)
        self.push (resp + '\r\n')

    def command_not_understood (self, command):
        self.respond ("500 '%s': command not understood." % command)

    def command_not_authorized (self, command):
        self.respond (
                "530 You are not authorized to perform the '%s' command" % (
                        command
                        )
                )

    def make_xmit_channel (self):
        # In PASV mode, the connection may or may _not_ have been made
        # yet.  [although in most cases it is... FTP Explorer being
        # the only exception I've yet seen].  This gets somewhat confusing
        # because things may happen in any order...
        pa = self.passive_acceptor
        if pa:
            if pa.ready:
                # a connection has already been made.
                conn, addr = self.passive_acceptor.ready
                cdc = xmit_channel (self, addr)
                cdc.set_socket (conn)
                cdc.connected = 1
                self.passive_acceptor.close()
                self.passive_acceptor = None
            else:
                # we're still waiting for a connect to the PASV port.
                cdc = xmit_channel (self)
        else:
            # not in PASV mode.
            ip, port = self.client_addr
            cdc = xmit_channel (self, self.client_addr)
            cdc.create_socket (socket.AF_INET, socket.SOCK_STREAM)
            if self.bind_local_minus_one:
                cdc.bind (('', self.server.port - 1))
            try:
                cdc.connect ((ip, port))
            except socket.error, why:
                self.respond ("425 Can't build data connection")
        self.client_dc = cdc

    # pretty much the same as xmit, but only right on the verge of
    # being worth a merge.
    def make_recv_channel (self, fd):
        pa = self.passive_acceptor
        if pa:
            if pa.ready:
                # a connection has already been made.
                conn, addr = pa.ready
                cdc = recv_channel (self, addr, fd)
                cdc.set_socket (conn)
                cdc.connected = 1
                self.passive_acceptor.close()
                self.passive_acceptor = None
            else:
                # we're still waiting for a connect to the PASV port.
                cdc = recv_channel (self, None, fd)
        else:
            # not in PASV mode.
            ip, port = self.client_addr
            cdc = recv_channel (self, self.client_addr, fd)
            cdc.create_socket (socket.AF_INET, socket.SOCK_STREAM)
            try:
                cdc.connect ((ip, port))
            except socket.error, why:
                self.respond ("425 Can't build data connection")
        self.client_dc = cdc

    type_map = {
            'a':'ASCII',
            'i':'Binary',
            'e':'EBCDIC',
            'l':'Binary'
            }

    type_mode_map = {
            'a':'t',
            'i':'b',
            'e':'b',
            'l':'b'
            }

    # --------------------------------------------------
    # command methods
    # --------------------------------------------------

    def cmd_type (self, line):
        'specify data transfer type'
        # ascii, ebcdic, image, local <byte size>
        t = string.lower (line[1])
        # no support for EBCDIC
        # if t not in ['a','e','i','l']:
        if t not in ['a','i','l']:
            self.command_not_understood (string.join (line))
        elif t == 'l' and (len(line) > 2 and line[2] != '8'):
            self.respond ('504 Byte size must be 8')
        else:
            self.current_mode = t
            self.respond ('200 Type set to %s.' % self.type_map[t])


    def cmd_quit (self, line):
        'terminate session'
        self.respond ('221 Goodbye.')
        self.close_when_done()

    def cmd_port (self, line):
        'specify data connection port'
        info = string.split (line[1], ',')
        ip = string.join (info[:4], '.')
        port = string.atoi(info[4])*256 + string.atoi(info[5])
        # how many data connections at a time?
        # I'm assuming one for now...
        # TODO: we should (optionally) verify that the
        # ip number belongs to the client.  [wu-ftpd does this?]
        self.client_addr = (ip, port)
        self.respond ('200 PORT command successful.')

    def new_passive_acceptor (self):
        # ensure that only one of these exists at a time.
        if self.passive_acceptor is not None:
            self.passive_acceptor.close()
            self.passive_acceptor = None
        self.passive_acceptor = passive_acceptor (self)
        return self.passive_acceptor

    def cmd_pasv (self, line):
        'prepare for server-to-server transfer'
        pc = self.new_passive_acceptor()
        port = pc.addr[1]
        ip_addr = pc.control_channel.getsockname()[0]
        self.respond (
                '227 Entering Passive Mode (%s,%d,%d)' % (
                        string.replace(ip_addr, '.', ','),
                        port/256,
                        port%256
                        )
                )
        self.client_dc = None

    def cmd_nlst (self, line):
        'give name list of files in directory'
        # ncftp adds the -FC argument for the user-visible 'nlist'
        # command.  We could try to emulate ls flags, but not just yet.
        if '-FC' in line:
            line.remove ('-FC')
        try:
            dir_list_producer = self.get_dir_list (line, 0)
        except os.error, why:
            self.respond ('550 Could not list directory: %s' % why)
            return
        self.respond (
                '150 Opening %s mode data connection for file list' % (
                        self.type_map[self.current_mode]
                        )
                )
        self.make_xmit_channel()
        self.client_dc.push_with_producer (dir_list_producer)
        self.client_dc.close_when_done()

    def cmd_list (self, line):
        'give a list of files in a directory'
        try:
            dir_list_producer = self.get_dir_list (line, 1)
        except os.error, why:
            self.respond ('550 Could not list directory: %s' % why)
            return
        self.respond (
                '150 Opening %s mode data connection for file list' % (
                        self.type_map[self.current_mode]
                        )
                )
        self.make_xmit_channel()
        self.client_dc.push_with_producer (dir_list_producer)
        self.client_dc.close_when_done()

    def cmd_cwd (self, line):
        'change working directory'
        if self.cwd (line):
            self.respond ('250 CWD command successful.')
        else:
            self.respond ('550 No such directory.')

    def cmd_cdup (self, line):
        'change to parent of current working directory'
        if self.cdup(line):
            self.respond ('250 CDUP command successful.')
        else:
            self.respond ('550 No such directory.')

    def cmd_pwd (self, line):
        'print the current working directory'
        self.respond (
                '257 "%s" is the current directory.' % (
                        self.filesystem.current_directory()
                        )
                )

    # modification time
    # example output:
    # 213 19960301204320
    def cmd_mdtm (self, line):
        'show last modification time of file'
        filename = line[1]
        if not self.filesystem.isfile (filename):
            self.respond ('550 "%s" is not a file' % filename)
        else:
            mtime = time.gmtime(self.filesystem.stat(filename)[stat.ST_MTIME])
            self.respond (
                    '213 %4d%02d%02d%02d%02d%02d' % (
                            mtime[0],
                            mtime[1],
                            mtime[2],
                            mtime[3],
                            mtime[4],
                            mtime[5]
                            )
                    )

    def cmd_noop (self, line):
        'do nothing'
        self.respond ('200 NOOP command successful.')

    def cmd_size (self, line):
        'return size of file'
        filename = line[1]
        if not self.filesystem.isfile (filename):
            self.respond ('550 "%s" is not a file' % filename)
        else:
            self.respond (
                    '213 %d' % (self.filesystem.stat(filename)[stat.ST_SIZE])
                    )

    def cmd_retr (self, line):
        'retrieve a file'
        if len(line) < 2:
            self.command_not_understood (string.join (line))
        else:
            file = line[1]
            if not self.filesystem.isfile (file):
                self.log_info ('checking %s' % file)
                self.respond ('550 No such file')
            else:
                try:
                    # FIXME: for some reason, 'rt' isn't working on win95
                    mode = 'r'+self.type_mode_map[self.current_mode]
                    fd = self.open (file, mode)
                except IOError, why:
                    self.respond ('553 could not open file for reading: %s' % (repr(why)))
                    return
                self.respond (
                        "150 Opening %s mode data connection for file '%s'" % (
                                self.type_map[self.current_mode],
                                file
                                )
                        )
                self.make_xmit_channel()

                if self.restart_position:
                    # try to position the file as requested, but
                    # give up silently on failure (the 'file object'
                    # may not support seek())
                    try:
                        fd.seek (self.restart_position)
                    except:
                        pass
                    self.restart_position = 0

                self.client_dc.push_with_producer (
                        file_producer (fd)
                        )
                self.client_dc.close_when_done()

    def cmd_stor (self, line, mode='wb'):
        'store a file'
        if len (line) < 2:
            self.command_not_understood (string.join (line))
        else:
            if self.restart_position:
                restart_position = 0
                self.respond ('553 restart on STOR not yet supported')
                return
            file = line[1]
            # todo: handle that type flag
            try:
                fd = self.open (file, mode)
            except IOError, why:
                self.respond ('553 could not open file for writing: %s' % (repr(why)))
                return
            self.respond (
                    '150 Opening %s connection for %s' % (
                            self.type_map[self.current_mode],
                            file
                            )
                    )
            self.make_recv_channel (fd)

    def cmd_abor (self, line):
        'abort operation'
        if self.client_dc:
            self.client_dc.close()
        self.respond ('226 ABOR command successful.')

    def cmd_appe (self, line):
        'append to a file'
        return self.cmd_stor (line, 'ab')

    def cmd_dele (self, line):
        if len (line) != 2:
            self.command_not_understood (string.join (line))
        else:
            file = line[1]
            if self.filesystem.isfile (file):
                try:
                    self.filesystem.unlink (file)
                    self.respond ('250 DELE command successful.')
                except:
                    self.respond ('550 error deleting file.')
            else:
                self.respond ('550 %s: No such file.' % file)

    def cmd_mkd (self, line):
        if len (line) != 2:
            self.command_not_understood (string.join (line))
        else:
            path = line[1]
            try:
                self.filesystem.mkdir (path)
                self.respond ('257 MKD command successful.')
            except:
                self.respond ('550 error creating directory.')

    def cmd_rnfr (self, line):
        if not hasattr(self.filesystem,'rename'):
            self.respond('502 RNFR not implemented.' % src)
            return

        if len(line)!=2:
            self.command_not_understood (string.join (line))
        else:
            src = line[1]
            try:
                assert self.filesystem.isfile(src)
                self._rfnr_src = src
                self.respond('350 RNFR file exists, ready for destination name.')
            except:
                self.respond('550 %s: No such file.' % src)

    def cmd_rnto (self, line):
        src = getattr(self,'_rfnr_src',None)
        if not src:
            self.respond('503 RNTO command unexpected.')
            return

        if len(line)!=2:
            self.command_not_understood (string.join (line))
        else:
            dst = line[1]
            try:
                self.filesystem.rename(src,dst)
                self.respond('250 RNTO command successful.')
            except:
                t, v = sys.exc_info[:2]
                self.respond('550 %s: %s.' % (str(t),str(v)))
        try:
            del self._rfnr_src
        except:
            pass

    def cmd_rmd (self, line):
        if len (line) != 2:
            self.command_not_understood (string.join (line))
        else:
            path = line[1]
            try:
                self.filesystem.rmdir (path)
                self.respond ('250 RMD command successful.')
            except:
                self.respond ('550 error removing directory.')

    def cmd_user (self, line):
        'specify user name'
        if len(line) > 1:
            self.user = line[1]
            self.respond ('331 Password required.')
        else:
            self.command_not_understood (string.join (line))

    def cmd_pass (self, line):
        'specify password'
        if len(line) < 2:
            pw = ''
        else:
            pw = line[1]
        result, message, fs = self.server.authorizer.authorize (self, self.user, pw)
        if result:
            self.respond ('230 %s' % message)
            self.filesystem = fs
            self.authorized = 1
            self.log_info('Successful login: Filesystem=%s' % repr(fs))
        else:
            self.respond ('530 %s' % message)

    def cmd_rest (self, line):
        'restart incomplete transfer'
        try:
            pos = string.atoi (line[1])
        except ValueError:
            self.command_not_understood (string.join (line))
        self.restart_position = pos
        self.respond (
                '350 Restarting at %d. Send STORE or RETRIEVE to initiate transfer.' % pos
                )

    def cmd_stru (self, line):
        'obsolete - set file transfer structure'
        if line[1] in 'fF':
            # f == 'file'
            self.respond ('200 STRU F Ok')
        else:
            self.respond ('504 Unimplemented STRU type')

    def cmd_mode (self, line):
        'obsolete - set file transfer mode'
        if line[1] in 'sS':
            # f == 'file'
            self.respond ('200 MODE S Ok')
        else:
            self.respond ('502 Unimplemented MODE type')

# The stat command has two personalities.  Normally it returns status
# information about the current connection.  But if given an argument,
# it is equivalent to the LIST command, with the data sent over the
# control connection.  Strange.  But wuftpd, ftpd, and nt's ftp server
# all support it.
#
##      def cmd_stat (self, line):
##              'return status of server'
##              pass

    def cmd_syst (self, line):
        'show operating system type of server system'
        # Replying to this command is of questionable utility, because
        # this server does not behave in a predictable way w.r.t. the
        # output of the LIST command.  We emulate Unix ls output, but
        # on win32 the pathname can contain drive information at the front
        # Currently, the combination of ensuring that os.sep == '/'
        # and removing the leading slash when necessary seems to work.
        # [cd'ing to another drive also works]
        #
        # This is how wuftpd responds, and is probably
        # the most expected.  The main purpose of this reply is so that
        # the client knows to expect Unix ls-style LIST output.
        self.respond ('215 UNIX Type: L8')
        # one disadvantage to this is that some client programs
        # assume they can pass args to /bin/ls.
        # a few typical responses:
        # 215 UNIX Type: L8 (wuftpd)
        # 215 Windows_NT version 3.51
        # 215 VMS MultiNet V3.3
        # 500 'SYST': command not understood. (SVR4)

    def cmd_help (self, line):
        'give help information'
        # find all the methods that match 'cmd_xxxx',
        # use their docstrings for the help response.
        attrs = dir(self.__class__)
        help_lines = []
        for attr in attrs:
            if attr[:4] == 'cmd_':
                x = getattr (self, attr)
                if type(x) == type(self.cmd_help):
                    if x.__doc__:
                        help_lines.append ('\t%s\t%s' % (attr[4:], x.__doc__))
        if help_lines:
            self.push ('214-The following commands are recognized\r\n')
            self.push_with_producer (producers.lines_producer (help_lines))
            self.push ('214\r\n')
        else:
            self.push ('214-\r\n\tHelp Unavailable\r\n214\r\n')

class ftp_server (asyncore.dispatcher):
    # override this to spawn a different FTP channel class.
    ftp_channel_class = ftp_channel

    SERVER_IDENT = 'FTP Server (V%s)' % VERSION

    def __init__ (
            self,
            authorizer,
            hostname        =None,
            ip              ='',
            port            =21,
            resolver        =None,
            logger_object=logger.file_logger (sys.stdout)
            ):
        self.ip = ip
        self.port = port
        self.authorizer = authorizer

        if hostname is None:
            self.hostname = socket.gethostname()
        else:
            self.hostname = hostname

        # statistics
        self.total_sessions = counter()
        self.closed_sessions = counter()
        self.total_files_out = counter()
        self.total_files_in = counter()
        self.total_bytes_out = counter()
        self.total_bytes_in = counter()
        self.total_exceptions = counter()
        #
        asyncore.dispatcher.__init__ (self)
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)

        self.set_reuse_addr()
        self.bind ((self.ip, self.port))
        self.listen (5)

        if not logger_object:
            logger_object = sys.stdout

        if resolver:
            self.logger = logger.resolving_logger (resolver, logger_object)
        else:
            self.logger = logger.unresolving_logger (logger_object)

        self.log_info('FTP server started at %s\n\tAuthorizer:%s\n\tHostname: %s\n\tPort: %d' % (
                time.ctime(time.time()),
                repr (self.authorizer),
                self.hostname,
                self.port)
                )

    def writable (self):
        return 0

    def handle_read (self):
        pass

    def handle_connect (self):
        pass

    def handle_accept (self):
        conn, addr = self.accept()
        self.total_sessions.increment()
        self.log_info('Incoming connection from %s:%d' % (addr[0], addr[1]))
        self.ftp_channel_class (self, conn, addr)

    # return a producer describing the state of the server
    def status (self):

        def nice_bytes (n):
            return string.join (status_handler.english_bytes (n))

        return producers.lines_producer (
                ['<h2>%s</h2>'                          % self.SERVER_IDENT,
                 '<br>Listening on <b>Host:</b> %s' % self.hostname,
                 '<b>Port:</b> %d'                      % self.port,
                 '<br>Sessions',
                 '<b>Total:</b> %s'                     % self.total_sessions,
                 '<b>Current:</b> %d'           % (self.total_sessions.as_long() - self.closed_sessions.as_long()),
                 '<br>Files',
                 '<b>Sent:</b> %s'                      % self.total_files_out,
                 '<b>Received:</b> %s'          % self.total_files_in,
                 '<br>Bytes',
                 '<b>Sent:</b> %s'                      % nice_bytes (self.total_bytes_out.as_long()),
                 '<b>Received:</b> %s'          % nice_bytes (self.total_bytes_in.as_long()),
                 '<br>Exceptions: %s'           % self.total_exceptions,
                 ]
                )

# ======================================================================
#                                                Data Channel Classes
# ======================================================================

# This socket accepts a data connection, used when the server has been
# placed in passive mode.  Although the RFC implies that we ought to
# be able to use the same acceptor over and over again, this presents
# a problem: how do we shut it off, so that we are accepting
# connections only when we expect them?  [we can't]
#
# wuftpd, and probably all the other servers, solve this by allowing
# only one connection to hit this acceptor.  They then close it.  Any
# subsequent data-connection command will then try for the default
# port on the client side [which is of course never there].  So the
# 'always-send-PORT/PASV' behavior seems required.
#
# Another note: wuftpd will also be listening on the channel as soon
# as the PASV command is sent.  It does not wait for a data command
# first.

# --- we need to queue up a particular behavior:
#  1) xmit : queue up producer[s]
#  2) recv : the file object
#
# It would be nice if we could make both channels the same.  Hmmm..
#

class passive_acceptor (asyncore.dispatcher):
    ready = None

    def __init__ (self, control_channel):
        # connect_fun (conn, addr)
        asyncore.dispatcher.__init__ (self)
        self.control_channel = control_channel
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)
        # bind to an address on the interface that the
        # control connection is coming from.
        self.bind ((
                self.control_channel.getsockname()[0],
                0
                ))
        self.addr = self.getsockname()
        self.listen (1)

#       def __del__ (self):
#               print 'passive_acceptor.__del__()'

    def log (self, *ignore):
        pass

    def handle_accept (self):
        conn, addr = self.accept()
        dc = self.control_channel.client_dc
        if dc is not None:
            dc.set_socket (conn)
            dc.addr = addr
            dc.connected = 1
            self.control_channel.passive_acceptor = None
        else:
            self.ready = conn, addr
        self.close()


class xmit_channel (asynchat.async_chat):

    # for an ethernet, you want this to be fairly large, in fact, it
    # _must_ be large for performance comparable to an ftpd.  [64k] we
    # ought to investigate automatically-sized buffers...

    ac_out_buffer_size = 16384
    bytes_out = 0

    def __init__ (self, channel, client_addr=None):
        self.channel = channel
        self.client_addr = client_addr
        asynchat.async_chat.__init__ (self)

#       def __del__ (self):
#               print 'xmit_channel.__del__()'

    def log (self, *args):
        pass

    def readable (self):
        return not self.connected

    def writable (self):
        return 1

    def send (self, data):
        result = asynchat.async_chat.send (self, data)
        self.bytes_out = self.bytes_out + result
        return result

    def handle_error (self):
        # usually this is to catch an unexpected disconnect.
        self.log_info ('unexpected disconnect on data xmit channel', 'error')
        try:
            self.close()
        except:
            pass

    # TODO: there's a better way to do this.  we need to be able to
    # put 'events' in the producer fifo.  to do this cleanly we need
    # to reposition the 'producer' fifo as an 'event' fifo.

    def close (self):
        c = self.channel
        s = c.server
        c.client_dc = None
        s.total_files_out.increment()
        s.total_bytes_out.increment (self.bytes_out)
        if not len(self.producer_fifo):
            c.respond ('226 Transfer complete')
        elif not c.closed:
            c.respond ('426 Connection closed; transfer aborted')
        del c
        del s
        del self.channel
        asynchat.async_chat.close (self)

class recv_channel (asyncore.dispatcher):
    def __init__ (self, channel, client_addr, fd):
        self.channel = channel
        self.client_addr = client_addr
        self.fd = fd
        asyncore.dispatcher.__init__ (self)
        self.bytes_in = counter()

    def log (self, *ignore):
        pass

    def handle_connect (self):
        pass

    def writable (self):
        return 0

    def recv (*args):
        result = apply (asyncore.dispatcher.recv, args)
        self = args[0]
        self.bytes_in.increment(len(result))
        return result

    buffer_size = 8192

    def handle_read (self):
        block = self.recv (self.buffer_size)
        if block:
            try:
                self.fd.write (block)
            except IOError:
                self.log_info ('got exception writing block...', 'error')

    def handle_close (self):
        s = self.channel.server
        s.total_files_in.increment()
        s.total_bytes_in.increment(self.bytes_in.as_long())
        self.fd.close()
        self.channel.respond ('226 Transfer complete.')
        self.close()

import filesys

# not much of a doorman! 8^)
class dummy_authorizer:
    def __init__ (self, root='/'):
        self.root = root
    def authorize (self, channel, username, password):
        channel.persona = -1, -1
        channel.read_only = 1
        return 1, 'Ok.', filesys.os_filesystem (self.root)

class anon_authorizer:
    def __init__ (self, root='/'):
        self.root = root

    def authorize (self, channel, username, password):
        if username in ('ftp', 'anonymous'):
            channel.persona = -1, -1
            channel.read_only = 1
            return 1, 'Ok.', filesys.os_filesystem (self.root)
        else:
            return 0, 'Password invalid.', None

# ===========================================================================
# Unix-specific improvements
# ===========================================================================

if os.name == 'posix':

    class unix_authorizer:
        # return a trio of (success, reply_string, filesystem)
        def authorize (self, channel, username, password):
            import crypt
            import pwd
            try:
                info = pwd.getpwnam (username)
            except KeyError:
                return 0, 'No such user.', None
            mangled = info[1]
            if crypt.crypt (password, mangled[:2]) == mangled:
                channel.read_only = 0
                fs = filesys.schizophrenic_unix_filesystem (
                        '/',
                        info[5],
                        persona = (info[2], info[3])
                        )
                return 1, 'Login successful.', fs
            else:
                return 0, 'Password invalid.', None

        def __repr__ (self):
            return '<standard unix authorizer>'

    # simple anonymous ftp support
    class unix_authorizer_with_anonymous (unix_authorizer):
        def __init__ (self, root=None, real_users=0):
            self.root = root
            self.real_users = real_users

        def authorize (self, channel, username, password):
            if string.lower(username) in ['anonymous', 'ftp']:
                import pwd
                try:
                    # ok, here we run into lots of confusion.
                    # on some os', anon runs under user 'nobody',
                    # on others as 'ftp'.  ownership is also critical.
                    # need to investigate.
                    # linux: new linuxen seem to have nobody's UID=-1,
                    #    which is an illegal value.  Use ftp.
                    ftp_user_info = pwd.getpwnam ('ftp')
                    if string.lower(os.uname()[0]) == 'linux':
                        nobody_user_info = pwd.getpwnam ('ftp')
                    else:
                        nobody_user_info = pwd.getpwnam ('nobody')
                    channel.read_only = 1
                    if self.root is None:
                        self.root = ftp_user_info[5]
                    fs = filesys.unix_filesystem (self.root, '/')
                    return 1, 'Anonymous Login Successful', fs
                except KeyError:
                    return 0, 'Anonymous account not set up', None
            elif self.real_users:
                return unix_authorizer.authorize (
                        self,
                        channel,
                        username,
                        password
                        )
            else:
                return 0, 'User logins not allowed', None

# usage: ftp_server /PATH/TO/FTP/ROOT PORT
# for example:
# $ ftp_server /home/users/ftp 8021

if os.name == 'posix':
    def test (port='8021'):
        fs = ftp_server (
                unix_authorizer(),
                port=string.atoi (port)
                )
        try:
            asyncore.loop()
        except KeyboardInterrupt:
            fs.log_info('FTP server shutting down. (received SIGINT)', 'warning')
            # close everything down on SIGINT.
            # of course this should be a cleaner shutdown.
            asyncore.close_all()

    if __name__ == '__main__':
        test (sys.argv[1])
# not unix
else:
    def test ():
        fs = ftp_server (dummy_authorizer())
    if __name__ == '__main__':
        test ()

# this is the command list from the wuftpd man page
# '*' means we've implemented it.
# '!' requires write access
#
command_documentation = {
        'abor': 'abort previous command',                                                       #*
        'acct': 'specify account (ignored)',
        'allo': 'allocate storage (vacuously)',
        'appe': 'append to a file',                                                                     #*!
        'cdup': 'change to parent of current working directory',        #*
        'cwd':  'change working directory',                                                     #*
        'dele': 'delete a file',                                                                        #!
        'help': 'give help information',                                                        #*
        'list': 'give list files in a directory',                                       #*
        'mkd':  'make a directory',                                                                     #!
        'mdtm': 'show last modification time of file',                          #*
        'mode': 'specify data transfer mode',
        'nlst': 'give name list of files in directory',                         #*
        'noop': 'do nothing',                                                                           #*
        'pass': 'specify password',                                                                     #*
        'pasv': 'prepare for server-to-server transfer',                        #*
        'port': 'specify data connection port',                                         #*
        'pwd':  'print the current working directory',                          #*
        'quit': 'terminate session',                                                            #*
        'rest': 'restart incomplete transfer',                                          #*
        'retr': 'retrieve a file',                                                                      #*
        'rmd':  'remove a directory',                                                           #!
        'rnfr': 'specify rename-from file name',                                        #*!
        'rnto': 'specify rename-to file name',                                          #*!
        'site': 'non-standard commands (see next section)',
        'size': 'return size of file',                                                          #*
        'stat': 'return status of server',                                                      #*
        'stor': 'store a file',                                                                         #*!
        'stou': 'store a file with a unique name',                                      #!
        'stru': 'specify data transfer structure',
        'syst': 'show operating system type of server system',          #*
        'type': 'specify data transfer type',                                           #*
        'user': 'specify user name',                                                            #*
        'xcup': 'change to parent of current working directory (deprecated)',
        'xcwd': 'change working directory (deprecated)',
        'xmkd': 'make a directory (deprecated)',                                        #!
        'xpwd': 'print the current working directory (deprecated)',
        'xrmd': 'remove a directory (deprecated)',                                      #!
}


# debugging aid (linux)
def get_vm_size ():
    return string.atoi (string.split(open ('/proc/self/stat').readline())[22])

def print_vm():
    print 'vm: %8dk' % (get_vm_size()/1024)
