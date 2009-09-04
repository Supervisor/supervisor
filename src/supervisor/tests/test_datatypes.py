"""Test suite for supervisor.datatypes"""

import sys
import os
import unittest
import socket
import tempfile
from supervisor import datatypes

class DatatypesTest(unittest.TestCase):
    def test_boolean_returns_true_for_truthy_values(self):
        for s in datatypes.TRUTHY_STRINGS:    
            actual = datatypes.boolean(s)
            self.assertEqual(actual, True)

    def test_boolean_returns_true_for_upper_truthy_values(self):
        for s in map(str.upper, datatypes.TRUTHY_STRINGS):
            actual = datatypes.boolean(s)
            self.assert_(actual, True)

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

    def test_dict_of_key_value_pairs_handles_commas_inside_apostrophes(self):
        actual = datatypes.dict_of_key_value_pairs("foo='bar,baz',baz='q,ux'")
        expected = {'foo': 'bar,baz', 'baz': 'q,ux'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_handles_commas_inside_quotes(self):
        actual = datatypes.dict_of_key_value_pairs('foo="bar,baz",baz="q,ux"')
        expected = {'foo': 'bar,baz', 'baz': 'q,ux'}
        self.assertEqual(actual, expected)

    def test_dict_of_key_value_pairs_raises_value_error_on_weird_input(self):
        self.assertRaises(ValueError, 
                          datatypes.dict_of_key_value_pairs, 'foo')

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
    

class InetStreamSocketConfigTests(unittest.TestCase):
    def _getTargetClass(self):
        return datatypes.InetStreamSocketConfig
        
    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test_url(self):
        conf = self._makeOne('127.0.0.1', 8675)
        self.assertEqual(conf.url, 'tcp://127.0.0.1:8675')
                
    def test_repr(self):
        conf = self._makeOne('127.0.0.1', 8675)
        s = repr(conf)
        self.assertTrue(s.startswith(
            '<supervisor.datatypes.InetStreamSocketConfig at'), s)
        self.assertTrue(s.endswith('for tcp://127.0.0.1:8675>'), s)

    def test_addr(self):
        conf = self._makeOne('127.0.0.1', 8675)
        addr = conf.addr()
        self.assertEqual(addr, ('127.0.0.1', 8675))

    def test_port_as_string(self):
        conf = self._makeOne('localhost', '5001')
        addr = conf.addr()
        self.assertEqual(addr, ('localhost', 5001))
        
    def test_create(self):
        conf = self._makeOne('127.0.0.1', 8675)
        sock = conf.create()
        reuse = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)
        self.assertTrue(reuse)
        sock.close
        
    def test_same_urls_are_equal(self):
        conf1 = self._makeOne('localhost', '5001')
        conf2 = self._makeOne('localhost', '5001')
        self.assertTrue(conf1 == conf2)
        self.assertFalse(conf1 != conf2)

    def test_diff_urls_are_not_equal(self):
        conf1 = self._makeOne('localhost', '5001')
        conf2 = self._makeOne('localhost', '5002')
        self.assertTrue(conf1 != conf2)
        self.assertFalse(conf1 == conf2)

    def test_diff_objs_are_not_equal(self):
        conf1 = self._makeOne('localhost', '5001')
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
            
    def test_repr(self):
        conf = self._makeOne('/tmp/foo.sock')
        s = repr(conf)
        self.assertTrue(s.startswith(
            '<supervisor.datatypes.UnixStreamSocketConfig at'), s)
        self.assertTrue(s.endswith('for unix:///tmp/foo.sock>'), s)

    def test_get_addr(self):
        conf = self._makeOne('/tmp/foo.sock')
        addr = conf.addr()
        self.assertEqual(addr, '/tmp/foo.sock')
        
    def test_create(self):
        (tf_fd, tf_name) = tempfile.mkstemp()
        conf = self._makeOne(tf_name)
        os.close(tf_fd)
        sock = conf.create()
        self.assertFalse(os.path.exists(tf_name))
        sock.close
        
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

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
