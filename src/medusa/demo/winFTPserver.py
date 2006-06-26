#
# winFTPServer.py -- FTP server that uses Win32 user API
#
# Contributed by John Abel
#
# For it to authenticate users correctly, the user running the
# script must be added to the security policy "Act As Part Of The OS".
# This is needed for the LogonUser to work.  A pain, but something that MS
# forgot to mention in the API.


import win32security, win32con, win32api, win32net
import ntsecuritycon, pywintypes
import asyncore
from medusa import ftp_server, filesys

class Win32Authorizer:


    def authorize (self, channel, userName, passWord):
        self.AdjustPrivilege( ntsecuritycon.SE_CHANGE_NOTIFY_NAME )
        self.AdjustPrivilege( ntsecuritycon.SE_ASSIGNPRIMARYTOKEN_NAME )
        self.AdjustPrivilege( ntsecuritycon.SE_TCB_NAME )
        try:
            logonHandle = win32security.LogonUser( userName,
                                                   None,
                                                   passWord,
                                                    win32con.LOGON32_LOGON_INTERACTIVE,
                                                    win32con.LOGON32_PROVIDER_DEFAULT )
        except pywintypes.error, ErrorMsg:
            return 0, ErrorMsg[ 2 ], None

        userInfo = win32net.NetUserGetInfo( None, userName, 1 )

        return 1, 'Login successful', filesys.os_filesystem( userInfo[ 'home_dir' ] )

    def AdjustPrivilege( self, priv ):
        flags = ntsecuritycon.TOKEN_ADJUST_PRIVILEGES | ntsecuritycon.TOKEN_QUERY
        htoken =  win32security.OpenProcessToken(win32api.GetCurrentProcess(), flags)
        id = win32security.LookupPrivilegeValue(None, priv)
        newPrivileges = [(id, ntsecuritycon.SE_PRIVILEGE_ENABLED)]
        win32security.AdjustTokenPrivileges(htoken, 0, newPrivileges)

def start_Server():
#    ftpServ = ftp_server.ftp_server( ftp_server.anon_authorizer( "D:\MyDocuments\MyDownloads"), port=21 )
    ftpServ = ftp_server.ftp_server( Win32Authorizer(), port=21 )
    asyncore.loop()

if __name__ == "__main__":
    print "Starting FTP Server"
    start_Server()
