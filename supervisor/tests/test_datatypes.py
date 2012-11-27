"""Test suite for supervisor.datatypes"""

import sys
import os
import unittest
import supervisor.medusa.text_socket as socket
import tempfile
from mock import Mock, patch, sentinel
from supervisor import datatypes
from supervisor.py3compat import *
if PY3:
    maxint = sys.maxsize
else:
    #noinspection PyUnresolvedReferences
    maxint = sys.maxint

class DatatypesTest(unittest.TestCase):
    def test_boolean_returns_true_for_truthy_values(self):
        for s in datatypes.TRUTHY_STRINGS:
            actual = datatypes.boolean(s)
            self.assertEqual(actual, True)

    def test_boolean_returns_true_for_upper_truthy_values(self):
        for s in map(str.upper, datatypes.TRUTHY_STRINGS):
            actual = datatypes.boolean(s)
            self.assertTrue(actual)

    def test_boolean_returns_false_for_falsy_values(self):
        for s in datatypes.FALSY_STRINGS:
            actual = datatypes.boolean(s)
            self.assertEqual(actual, False)

    def test_boolean_returns_false_for_upper_falsy_values(self):
        for s in map(str.upper, datatypes.FALSY_STRINGS):
            actual = datatypes.boolean(s)
            self.assertEqual(actual, False)

    def test_boolean_raises_value_error_for_bad_value(self):
        self.assertRaises(ValueError,
                          datatypes.boolean, 'not-a-value')

    def test_list_of_strings_returns_empty_list_for_empty_string(self):
        actual = datatypes.list_of_strings('')
        self.assertEqual(actual, [])

    def test_list_of_strings_returns_list_of_strings_by_comma_split(self):
        actual = datatypes.list_of_strings('foo,bar')
        self.assertEqual(actual, ['foo', 'bar'])

    def test_list_of_strings_returns_strings_with_whitespace_stripped(self):
        actual = datatypes.list_of_strings(' foo , bar ')
        self.assertEqual(actual, ['foo', 'bar'])

    def test_list_of_strings_raises_value_error_when_comma_split_fails(self):
        self.assertRaises(ValueError,
                          datatypes.list_of_strings, 42)

    def test_list_of_ints_returns_empty_list_for_empty_string(self):
        actual = datatypes.list_of_ints('')
        self.assertEqual(actual, [])

    def test_list_of_ints_returns_list_of_ints_by_comma_split(self):
        actual = datatypes.list_of_ints('1,42')
        self.assertEqual(actual, [1,42])

    def test_list_of_ints_returns_ints_even_if_whitespace_in_string(self):
        actual = datatypes.list_of_ints(' 1 , 42 ')
        self.assertEqual(actual, [1,42])

    def test_list_of_ints_raises_value_error_when_comma_split_fails(self):
        self.assertRaises(ValueError,
                          datatypes.list_of_ints, 42)

    def test_list_of_ints_raises_value_error_when_one_value_is_bad(self):
        self.assertRaises(ValueError,
                          datatypes.list_of_ints, '1, bad, 42')

    def test_list_of_exitcodes(self):
        vals = datatypes.list_of_exitcodes('1,2,3')
        self.assertEqual(vals, [1,2,3])
        vals = datatypes.list_of_exitcodes('1')
        self.assertEqual(vals, [1])
        self.assertRaises(ValueError, datatypes.list_of_exitcodes, 'a,b,c')
        self.assertRaises(ValueError, datatypes.list_of_exitcodes, '1024')
        self.assertRaises(ValueError, datatypes.list_of_exitcodes, '-1,1')

    def test_hasattr_automatic(self):
        datatypes.Automatic

    def test_dict_of_key_value_pairs_returns_empty_dict_for_empty_str(self):
        actual = datatypes.dict_of_key_value_pairs('')
        self.assertEqual({}, actual)

    def test_dict_of_key_value_pairs_returns_dict_from_single_pair_str(self):
        actual = datatypes.dict_of_key_value_pairs('foo=bar')
        expected = {'foo': 'bar'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_returns_dict_from_multi_pair_str(self):
        actual = datatypes.dict_of_key_value_pairs('foo=bar,baz=qux')
        expected = {'foo': 'bar', 'baz': 'qux'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_returns_dict_even_if_whitespace(self):
        actual = datatypes.dict_of_key_value_pairs(' foo = bar , baz = qux ')
        expected = {'foo': 'bar', 'baz': 'qux'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_returns_dict_even_if_newlines(self):
        actual = datatypes.dict_of_key_value_pairs('foo\n=\nbar\n,\nbaz\n=\nqux')
        expected = {'foo': 'bar', 'baz': 'qux'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_handles_commas_inside_apostrophes(self):
        actual = datatypes.dict_of_key_value_pairs("foo='bar,baz',baz='q,ux'")
        expected = {'foo': 'bar,baz', 'baz': 'q,ux'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_handles_commas_inside_quotes(self):
        actual = datatypes.dict_of_key_value_pairs('foo="bar,baz",baz="q,ux"')
        expected = {'foo': 'bar,baz', 'baz': 'q,ux'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_handles_unquoted_non_alphanum(self):
        actual = datatypes.dict_of_key_value_pairs(
            'HOME=/home/auser,FOO=/.foo+(1.2)-_/,'
            'SUPERVISOR_SERVER_URL=http://127.0.0.1:9001')
        expected = {'HOME': '/home/auser', 'FOO': '/.foo+(1.2)-_/',
                    'SUPERVISOR_SERVER_URL': 'http://127.0.0.1:9001'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_allows_trailing_comma(self):
        actual = datatypes.dict_of_key_value_pairs('foo=bar,')
        expected = {'foo': 'bar'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_raises_value_error_on_too_short(self):
        self.assertRaises(ValueError,
                          datatypes.dict_of_key_value_pairs, 'foo')
        self.assertRaises(ValueError,
                          datatypes.dict_of_key_value_pairs, 'foo=')
        self.assertRaises(ValueError,
                          datatypes.dict_of_key_value_pairs, 'foo=bar,baz')
        self.assertRaises(ValueError,
                          datatypes.dict_of_key_value_pairs, 'foo=bar,baz=')

    def test_dict_of_key_value_pairs_raises_when_comma_is_missing(self):
        kvp = 'KEY1=no-comma KEY2=ends-with-comma,'
        self.assertRaises(ValueError,
                          datatypes.dict_of_key_value_pairs, kvp)

    def test_logfile_name_returns_none_for_none_values(self):
        for thing in datatypes.LOGFILE_NONES:
            actual = datatypes.logfile_name(thing)
            self.assertEqual(actual, None)

    def test_logfile_name_returns_none_for_uppered_none_values(self):
        for thing in datatypes.LOGFILE_NONES:
            if hasattr(thing, 'upper'):
                thing = thing.upper()
            actual = datatypes.logfile_name(thing)
            self.assertEqual(actual, None)

    def test_logfile_name_returns_automatic_for_auto_values(self):
        for thing in datatypes.LOGFILE_AUTOS:
            actual = datatypes.logfile_name(thing)
            self.assertEqual(actual, datatypes.Automatic)

    def test_logfile_name_returns_automatic_for_uppered_auto_values(self):
        for thing in datatypes.LOGFILE_AUTOS:
            if hasattr(thing, 'upper'):
                thing = thing.upper()
            actual = datatypes.logfile_name(thing)
            self.assertEqual(actual, datatypes.Automatic)

    def test_logfile_name_returns_existing_dirpath_for_other_values(self):
        func = datatypes.existing_dirpath
        datatypes.existing_dirpath = lambda path: path
        try:
            path = '/path/to/logfile/With/Case/Preserved'
            actual = datatypes.logfile_name(path)
            self.assertEqual(actual, path)
        finally:
            datatypes.existing_dirpath = func

    def test_integer(self):
        from supervisor.datatypes import integer
        self.assertRaises(ValueError, integer, 'abc')
        self.assertEqual(integer('1'), 1)
        self.assertEqual(integer(str(maxint+1)), maxint+1)

    def test_url_accepts_urlparse_recognized_scheme_with_netloc(self):
        good_url = 'http://localhost:9001'
        self.assertEqual(datatypes.url(good_url), good_url)

    def test_url_rejects_urlparse_recognized_scheme_but_no_netloc(self):
        bad_url = 'http://'
        self.assertRaises(ValueError, datatypes.url, bad_url)

    def test_url_accepts_unix_scheme_with_path(self):
        good_url = "unix://somepath"
        self.assertEqual(good_url, datatypes.url(good_url))

    def test_url_rejects_unix_scheme_with_no_slashes_or_path(self):
        bad_url = "unix:"
        self.assertRaises(ValueError, datatypes.url, bad_url)

    def test_url_rejects_unix_scheme_with_slashes_but_no_path(self):
        bad_url = "unix://"
        self.assertRaises(ValueError, datatypes.url, bad_url)

class InetStreamSocketConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        return datatypes.InetStreamSocketConfig

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_url(self):
        conf = self._makeOne('127.0.0.1', 8675)
        self.assertEqual(conf.url, 'tcp://127.0.0.1:8675')

    def test___str__(self):
        cfg = self._makeOne('localhost', 65531)
        self.assertEqual(str(cfg), 'tcp://localhost:65531')

    def test_repr(self):
        conf = self._makeOne('127.0.0.1', 8675)
        s = repr(conf)
        self.assertTrue('supervisor.datatypes.InetStreamSocketConfig' in s)
        self.assertTrue(s.endswith('for tcp://127.0.0.1:8675>'), s)

    def test_addr(self):
        conf = self._makeOne('127.0.0.1', 8675)
        addr = conf.addr()
        self.assertEqual(addr, ('127.0.0.1', 8675))

    def test_port_as_string(self):
        conf = self._makeOne('localhost', '5001')
        addr = conf.addr()
        self.assertEqual(addr, ('localhost', 5001))

    def test_create_and_bind(self):
        conf = self._makeOne('127.0.0.1', 8675)
        sock = conf.create_and_bind()
        reuse = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        self.assertTrue(reuse)
        self.assertEqual(conf.addr(), sock.getsockname()) #verifies that bind was called
        sock.close()

    def test_same_urls_are_equal(self):
        conf1 = self._makeOne('localhost', 5001)
        conf2 = self._makeOne('localhost', 5001)
        self.assertTrue(conf1 == conf2)
        self.assertFalse(conf1 != conf2)

    def test_diff_urls_are_not_equal(self):
        conf1 = self._makeOne('localhost', 5001)
        conf2 = self._makeOne('localhost', 5002)
        self.assertTrue(conf1 != conf2)
        self.assertFalse(conf1 == conf2)

    def test_diff_objs_are_not_equal(self):
        conf1 = self._makeOne('localhost', 5001)
        conf2 = 'blah'
        self.assertTrue(conf1 != conf2)
        self.assertFalse(conf1 == conf2)

class UnixStreamSocketConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        return datatypes.UnixStreamSocketConfig

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_url(self):
        conf = self._makeOne('/tmp/foo.sock')
        self.assertEqual(conf.url, 'unix:///tmp/foo.sock')

    def test___str__(self):
        cfg = self._makeOne('foo/bar')
        self.assertEqual(str(cfg), 'unix://foo/bar')

    def test_repr(self):
        conf = self._makeOne('/tmp/foo.sock')
        s = repr(conf)
        self.assertTrue('supervisor.datatypes.UnixStreamSocketConfig' in s)
        self.assertTrue(s.endswith('for unix:///tmp/foo.sock>'), s)

    def test_get_addr(self):
        conf = self._makeOne('/tmp/foo.sock')
        addr = conf.addr()
        self.assertEqual(addr, '/tmp/foo.sock')

    def test_create_and_bind(self):
        (tf_fd, tf_name) = tempfile.mkstemp()
        owner = (sentinel.uid, sentinel.gid)
        mode = sentinel.mode
        conf = self._makeOne(tf_name, owner=owner, mode=mode)

        #Patch os.chmod and os.chown functions with mocks
        #objects so that the test does not depend on
        #any specific system users or permissions
        chown_mock = Mock()
        chmod_mock = Mock()
        @patch('os.chown', chown_mock)
        @patch('os.chmod', chmod_mock)
        def call_create_and_bind(conf):
            return conf.create_and_bind()

        sock = call_create_and_bind(conf)
        self.assertTrue(os.path.exists(tf_name))
        self.assertEqual(conf.addr(), sock.getsockname()) #verifies that bind was called
        sock.close()
        self.assertTrue(os.path.exists(tf_name))
        os.unlink(tf_name)
        #Verify that os.chown was called with correct args
        self.assertEqual(1, chown_mock.call_count)
        path_arg = chown_mock.call_args[0][0]
        uid_arg = chown_mock.call_args[0][1]
        gid_arg = chown_mock.call_args[0][2]
        self.assertEqual(tf_name, path_arg)
        self.assertEqual(owner[0], uid_arg)
        self.assertEqual(owner[1], gid_arg)
        #Verify that os.chmod was called with correct args
        self.assertEqual(1, chmod_mock.call_count)
        path_arg = chmod_mock.call_args[0][0]
        mode_arg = chmod_mock.call_args[0][1]
        self.assertEqual(tf_name, path_arg)
        self.assertEqual(mode, mode_arg)

    def test_same_paths_are_equal(self):
        conf1 = self._makeOne('/tmp/foo.sock')
        conf2 = self._makeOne('/tmp/foo.sock')
        self.assertTrue(conf1 == conf2)
        self.assertFalse(conf1 != conf2)

    def test_diff_paths_are_not_equal(self):
        conf1 = self._makeOne('/tmp/foo.sock')
        conf2 = self._makeOne('/tmp/bar.sock')
        self.assertTrue(conf1 != conf2)
        self.assertFalse(conf1 == conf2)

    def test_diff_objs_are_not_equal(self):
        conf1 = self._makeOne('/tmp/foo.sock')
        conf2 = 'blah'
        self.assertTrue(conf1 != conf2)
        self.assertFalse(conf1 == conf2)

class RangeCheckedConversionTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.datatypes import RangeCheckedConversion
        return RangeCheckedConversion

    def _makeOne(self, conversion, min=None, max=None):
        return self._getTargetClass()(conversion, min, max)

    def test_below_lower_bound(self):
        conversion = self._makeOne(lambda *arg: -1, 0)
        self.assertRaises(ValueError, conversion, None)

    def test_above_upper_lower_bound(self):
        conversion = self._makeOne(lambda *arg: 1, 0, 0)
        self.assertRaises(ValueError, conversion, None)

    def test_passes(self):
        conversion = self._makeOne(lambda *arg: 0, 0, 0)
        self.assertEqual(conversion(0), 0)

class InetAddressTests(unittest.TestCase):
    def _callFUT(self, s):
        from supervisor.datatypes import inet_address
        return inet_address(s)

    def test_no_port_number(self):
        self.assertRaises(ValueError, self._callFUT, 'a:')

    def test_bad_port_number(self):
        self.assertRaises(ValueError, self._callFUT, 'a')

    def test_default_host(self):
        host, port = self._callFUT('*:8080')
        self.assertEqual(host, '')
        self.assertEqual(port, 8080)

    def test_boring(self):
        host, port = self._callFUT('localhost:80')
        self.assertEqual(host, 'localhost')
        self.assertEqual(port, 80)

class TestSocketAddress(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.datatypes import SocketAddress
        return SocketAddress

    def _makeOne(self, s):
        return self._getTargetClass()(s)

    def test_unix_socket(self):
        addr = self._makeOne('/foo/bar')
        self.assertEqual(addr.family, socket.AF_UNIX)
        self.assertEqual(addr.address, '/foo/bar')

    def test_inet_socket(self):
        addr = self._makeOne('localhost:8080')
        self.assertEqual(addr.family, socket.AF_INET)
        self.assertEqual(addr.address, ('localhost', 8080))

class TestColonSeparatedUserGroup(unittest.TestCase):
    def _callFUT(self, arg):
        from supervisor.datatypes import colon_separated_user_group
        return colon_separated_user_group(arg)

    def test_ok_username(self):
        self.assertEqual(self._callFUT('root')[0], 0)

    def test_missinguser_username(self):
        self.assertRaises(ValueError,
                          self._callFUT, 'godihopethisuserdoesntexist')

    def test_missinguser_username_and_groupname(self):
        self.assertRaises(ValueError,
                          self._callFUT, 'godihopethisuserdoesntexist:foo')

class TestOctalType(unittest.TestCase):
    def _callFUT(self, arg):
        from supervisor.datatypes import octal_type
        return octal_type(arg)

    def test_it_success(self):
        self.assertEqual(self._callFUT('10'), 8)

    def test_test_it_failure(self):
        self.assertRaises(ValueError, self._callFUT, 'noo')
