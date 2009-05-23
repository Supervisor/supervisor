# -*- Mode: Python -*-

from medusa import asyncore_25 as asyncore
from medusa import ftp_server

# create a 'dummy' authorizer (one that lets everyone in) that returns
# a read-only filesystem rooted at '/home/ftp'

authorizer = ftp_server.dummy_authorizer('/home/ftp')

# Create an ftp server using this authorizer, running on port 8021
# [the standard port is 21, but you are probably already running
#  a server there]

fs = ftp_server.ftp_server(authorizer, port=8021)

# Run the async main loop
asyncore.loop()

# to test this server, try
# $ ftp myhost 8021
# when using the standard bsd ftp client,
# $ ncftp -p 8021 myhost
# when using ncftp, and
# ftp://myhost:8021/
# from a web browser.

