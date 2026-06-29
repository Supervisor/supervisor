"""Test suite for supervisor.compat"""

import unittest

from supervisor.compat import as_bytes, as_string


class AsStringTests(unittest.TestCase):
    def test_decodes_valid_utf8(self):
        self.assertEqual(as_string(b'hello'), 'hello')

    def test_returns_string_unchanged(self):
        self.assertEqual(as_string('hello'), 'hello')

    def test_replaces_invalid_bytes_instead_of_raising(self):
        # Incomplete multi-byte sequence (e.g. truncated Korean character)
        broken = b'\xec\x95'  # incomplete 3-byte UTF-8 sequence
        result = as_string(broken)
        self.assertIn('�', result)

    def test_decodes_korean_utf8(self):
        korean = '안녕하세요'.encode('utf-8')
        self.assertEqual(as_string(korean), '안녕하세요')


class AsBytesTests(unittest.TestCase):
    def test_encodes_valid_string(self):
        self.assertEqual(as_bytes('hello'), b'hello')

    def test_returns_bytes_unchanged(self):
        self.assertEqual(as_bytes(b'hello'), b'hello')

    def test_encodes_korean_string(self):
        result = as_bytes('안녕하세요')
        self.assertEqual(result, '안녕하세요'.encode('utf-8'))
