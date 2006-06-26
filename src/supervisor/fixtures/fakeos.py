from os import *
from os import _exit
import os

class FakeOS:
    def __init__(self):
        self.orig_uid = os.getuid()
        self.orig_gid = os.getgid()

    def setgroups(*args):
        return

    def getuid():
        return 0

    def setuid(arg):
        self.uid = arg
        self.setuid_called = 1

    def setgid(arg):
        self.gid = arg
        self.setgid_called = 1

    def clear():
        self.uid = orig_uid
        self.gid = orig_gid
        self.setuid_called = 0
        self.setgid_called = 0

fake = FakeOS()

setgroups = fake.setgroups
getuid = fake.getuid
setuid = fake.setuid
setgid = fake.setgid
clear = fake.clear
