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

class Proxy:
    """ Class for wrapping a shared resource object and getting
        notified when it's deleted
    """
    
    def __init__(self, object, **kwargs):
        self.object = object
        self.on_delete = kwargs.get('on_delete', None)

    def __del__(self):
        if self.on_delete:
            self.on_delete()
    
    def __getattr__(self, name):
        return getattr(self.object, name)
        
    def _get(self):
        return self.object
        
class ReferenceCounter:
    """ Class for tracking references to a shared resource
    """
    
    def __init__(self, **kwargs):
        self.on_non_zero = kwargs['on_non_zero']
        self.on_zero = kwargs['on_zero']
        self.ref_count = 0
    
    def get_count(self):
        return self.ref_count
    
    def increment(self):
        if self.ref_count == 0:
            self.on_non_zero()
        self.ref_count = self.ref_count + 1
        
    def decrement(self):
        if self.ref_count <= 0:
            raise Exception('Illegal operation: cannot decrement below zero')
        self.ref_count -= 1
        if self.ref_count == 0:
            self.on_zero()

class SocketManager:
    """ Class for managing sockets in servers that create/bind/listen
        before forking multiple child processes to accept() 
        Sockets are managed at the process group level and referenced counted
        at the process level b/c that's really the only place to hook in
    """
    
    def __init__(self, socket_config, **kwargs):
        self.logger = kwargs.get('logger', None)
        self.socket = None
        self.prepared = False
        self.socket_config = socket_config
        self.ref_ctr = ReferenceCounter(on_zero=self._close, on_non_zero=self._prepare_socket)
        
    def __repr__(self):
        return '<%s at %s for %s>' % (self.__class__,
                                      id(self),
                                      self.socket_config.url)

    def config(self):
        return self.socket_config
        
    def is_prepared(self):
        return self.prepared

    def get_socket(self):
        self.ref_ctr.increment()
        self._require_prepared()
        return Proxy(self.socket, on_delete=self.ref_ctr.decrement)
        
    def get_socket_ref_count(self):
        self._require_prepared()
        return self.ref_ctr.get_count()
        
    def _require_prepared(self):
        if not self.prepared:
            raise Exception('Socket has not been prepared')
    
    def _prepare_socket(self):
        if not self.prepared:
            if self.logger:
                self.logger.info('Creating socket %s' % self.socket_config)
            self.socket = self.socket_config.create_and_bind()
            self.socket.listen(socket.SOMAXCONN)
            self.prepared = True

    def _close(self):
        self._require_prepared()
        if self.logger:
            self.logger.info('Closing socket %s' % self.socket_config)
        self.socket.close()
        self.prepared = False
