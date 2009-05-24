# -*- Mode: Python -*-

import socket
import select

# several factors here we might want to test:
# 1) max we can create
# 2) max we can bind
# 3) max we can listen on
# 4) max we can connect

def max_server_sockets():
    sl = []
    while 1:
        try:
            s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
            s.bind (('',0))
            s.listen(5)
            sl.append (s)
        except:
            break
    num = len(sl)
    for s in sl:
        s.close()
    del sl
    return num

def max_client_sockets():
    # make a server socket
    server = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
    server.bind (('', 9999))
    server.listen (5)
    sl = []
    while 1:
        try:
            s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
            s.connect (('', 9999))
            conn, addr = server.accept()
            sl.append ((s,conn))
        except:
            break
    num = len(sl)
    for s,c in sl:
        s.close()
        c.close()
    del sl
    return num

def max_select_sockets():
    sl = []
    while 1:
        try:
            s = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
            s.bind (('',0))
            s.listen(5)
            sl.append (s)
            select.select(sl,[],[],0)
        except:
            break
    num = len(sl) - 1
    for s in sl:
        s.close()
    del sl
    return num
