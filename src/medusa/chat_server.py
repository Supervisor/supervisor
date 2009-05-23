# -*- Mode: Python -*-
#
#       Author: Sam Rushing <rushing@nightmare.com>
#       Copyright 1997-2000 by Sam Rushing
#                                                All Rights Reserved.
#

RCS_ID = '$Id: chat_server.py,v 1.4 2002/03/20 17:37:48 amk Exp $'

import string

VERSION = string.split(RCS_ID)[2]

import socket
import asyncore_25 as asyncore
import asynchat_25 as asynchat
import status_handler

class chat_channel (asynchat.async_chat):

    def __init__ (self, server, sock, addr):
        asynchat.async_chat.__init__ (self, sock)
        self.server = server
        self.addr = addr
        self.set_terminator ('\r\n')
        self.data = ''
        self.nick = None
        self.push ('nickname?: ')

    def collect_incoming_data (self, data):
        self.data = self.data + data

    def found_terminator (self):
        line = self.data
        self.data = ''
        if self.nick is None:
            self.nick = string.split (line)[0]
            if not self.nick:
                self.nick = None
                self.push ('huh? gimmee a nickname: ')
            else:
                self.greet()
        else:
            if not line:
                pass
            elif line[0] != '/':
                self.server.push_line (self, line)
            else:
                self.handle_command (line)

    def greet (self):
        self.push ('Hello, %s\r\n' % self.nick)
        num_channels = len(self.server.channels)-1
        if num_channels == 0:
            self.push ('[Kinda lonely in here... you\'re the only caller!]\r\n')
        else:
            self.push ('[There are %d other callers]\r\n' % (len(self.server.channels)-1))
            nicks = map (lambda x: x.get_nick(), self.server.channels.keys())
            self.push (string.join (nicks, '\r\n  ') + '\r\n')
            self.server.push_line (self, '[joined]')

    def handle_command (self, command):
        import types
        command_line = string.split(command)
        name = 'cmd_%s' % command_line[0][1:]
        if hasattr (self, name):
            # make sure it's a method...
            method = getattr (self, name)
            if type(method) == type(self.handle_command):
                method (command_line[1:])
            else:
                self.push ('unknown command: %s' % command_line[0])

    def cmd_quit (self, args):
        self.server.push_line (self, '[left]')
        self.push ('Goodbye!\r\n')
        self.close_when_done()

    # alias for '/quit' - '/q'
    cmd_q = cmd_quit

    def push_line (self, nick, line):
        self.push ('%s: %s\r\n' % (nick, line))

    def handle_close (self):
        self.close()

    def close (self):
        del self.server.channels[self]
        asynchat.async_chat.close (self)

    def get_nick (self):
        if self.nick is not None:
            return self.nick
        else:
            return 'Unknown'

class chat_server (asyncore.dispatcher):

    SERVER_IDENT = 'Chat Server (V%s)' % VERSION

    channel_class = chat_channel

    spy = 1

    def __init__ (self, ip='', port=8518):
        asyncore.dispatcher.__init__(self)
        self.port = port
        self.create_socket (socket.AF_INET, socket.SOCK_STREAM)
        self.bind ((ip, port))
        print '%s started on port %d' % (self.SERVER_IDENT, port)
        self.listen (5)
        self.channels = {}
        self.count = 0

    def handle_accept (self):
        conn, addr = self.accept()
        self.count = self.count + 1
        print 'client #%d - %s:%d' % (self.count, addr[0], addr[1])
        self.channels[self.channel_class (self, conn, addr)] = 1

    def push_line (self, from_channel, line):
        nick = from_channel.get_nick()
        if self.spy:
            print '%s: %s' % (nick, line)
        for c in self.channels.keys():
            if c is not from_channel:
                c.push ('%s: %s\r\n' % (nick, line))

    def status (self):
        lines = [
                '<h2>%s</h2>'                                           % self.SERVER_IDENT,
                '<br>Listening on Port: %d'                     % self.port,
                '<br><b>Total Sessions:</b> %d'         % self.count,
                '<br><b>Current Sessions:</b> %d'       % (len(self.channels))
                ]
        return status_handler.lines_producer (lines)

    def writable (self):
        return 0

if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        port = string.atoi (sys.argv[1])
    else:
        port = 8518

    s = chat_server ('', port)
    asyncore.loop()
