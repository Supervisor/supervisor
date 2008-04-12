##############################################################################
#
# Copyright (c) 2007 Agendaless Consulting and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the BSD-like license at
# http://www.repoze.org/LICENSE.txt.  A copy of the license should accompany
# this distribution.  THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL
# EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND
# FITNESS FOR A PARTICULAR PURPOSE
#
##############################################################################

import socket

class SocketManager:
    """ Class for managing sockets in servers that create/bind/listen
        before forking multiple child processes to accept() """
        
    socket_config = None #SocketConfig object
    socket = None #Socket being managed
    prepared = False
    
    def __init__(self, socket_config):
        self.socket_config = socket_config
        
    def __repr__(self):
        return '<%s at %s for %s>' % (self.__class__,
                                      id(self),
                                      self.socket_config.url)

    def config(self):
        return self.socket_config
        
    def prepare_socket(self):
        self.socket = self.socket_config.create()
        self.socket.bind(self.socket_config.addr())
        self.socket.listen(socket.SOMAXCONN)
        self.prepared = True
        
    def get_socket(self):
        if not self.prepared:
            self.prepare_socket()
        return self.socket
        
    def close(self):
        self.socket.close()
        self.prepared = False
