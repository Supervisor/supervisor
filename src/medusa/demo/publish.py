# -*- Mode: Python -*-

# Demonstrates use of the auth and put handlers to support publishing
# web pages via HTTP.

# It is also possible to set up the ftp server to do essentially the
# same thing.

# Security Note: Using HTTP with the 'Basic' authentication scheme is
# only slightly more secure than using FTP: both techniques involve
# sending a unencrypted password of the network (http basic auth
# base64-encodes the username and password).  The 'Digest' scheme is
# much more secure, but not widely supported yet. <sigh>

from medusa import asyncore_25 as asyncore
from medusa import default_handler
from medusa import http_server
from medusa import put_handler
from medusa import auth_handler
from medusa import filesys

# For this demo, we'll just use a dictionary of usernames/passwords.
# You can of course use anything that supports the mapping interface,
# and it would be pretty easy to set this up to use the crypt module
# on unix.

users = { 'mozart' : 'jupiter', 'beethoven' : 'pastoral' }

# The filesystem we will be giving access to
fs = filesys.os_filesystem('/home/medusa')

# The 'default' handler - delivers files for the HTTP GET method.
dh = default_handler.default_handler(fs)

# Supports the HTTP PUT method...
ph = put_handler.put_handler(fs, '/.*')

# ... but be sure to wrap it with an auth handler:
ah = auth_handler.auth_handler(users, ph)

# Create a Web Server
hs = http_server.http_server(ip='', port=8080)

# install the handlers we created:

hs.install_handler(dh) # for GET
hs.install_handler(ah) # for PUT

asyncore.loop()
