# this is a package
from unittest import TestCase
def assertTrue(self, value, extra=None):
    if not value:
        raise AssertionError(extra)
def assertFalse(self, value, extra=None):
    if value:
        raise AssertionError(extra)

if not hasattr(TestCase, 'assertTrue'): # Python 2.3.3
    TestCase.assertTrue = assertTrue

if not hasattr(TestCase, 'assertFalse'): # Pytthon 2.3.3
    TestCase.assertFalse = assertFalse
