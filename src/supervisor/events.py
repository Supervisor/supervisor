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

callbacks = []

def subscribe(type, callback):
    callbacks.append((type, callback))
    
def notify(event):
    for type, callback in callbacks:
        if isinstance(event, type):
            callback(event)

class ProcessCommunicationEvent:
    # event mode tokens
    BEGIN_TOKEN = '<!--XSUPERVISOR:BEGIN-->'
    END_TOKEN   = '<!--XSUPERVISOR:END-->'
    def __init__(self, process_name, channel, data):
        self.process_name = process_name
        self.channel = channel
        self.data = data
