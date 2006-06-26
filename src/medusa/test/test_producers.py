#!/usr/bin/env python

#
# Test script for producers.py
#

__revision__ = "$Id$"

import StringIO, zlib
from sancho.unittest import TestScenario, parse_args, run_scenarios

tested_modules = ["medusa.producers"]


from medusa import producers

test_string = ''
for i in range(16385):
    test_string += chr(48 + (i%10))

class ProducerTest (TestScenario):

    def setup (self):
        pass
    
    def shutdown (self):
        pass

    def _check_all (self, p, expected_string):
        # Check that a producer returns all of the string,
        # and that it's the unchanged string.
        count = 0
        data = ""
        while 1:
            s = p.more()
            if s == "":
                break
            count += len(s)
            data += s
        self.test_val('count', len(expected_string))
        self.test_val('data', expected_string)
        self.test_val('p.more()', '')
        return data
        
    def check_simple (self):
        p = producers.simple_producer(test_string)
        self.test_val('p.more()', test_string[:1024])

        p = producers.simple_producer(test_string, buffer_size = 5)
        self._check_all(p, test_string)

    def check_scanning (self):
        p = producers.scanning_producer(test_string)
        self.test_val('p.more()', test_string[:1024])

        p = producers.scanning_producer(test_string, buffer_size = 5)
        self._check_all(p, test_string)

    def check_lines (self):
        p = producers.lines_producer(['a']* 65)
        self._check_all(p, 'a\r\n'*65)

    def check_buffer (self):
        p = producers.buffer_list_producer(['a']* 1027)
        self._check_all(p, 'a'*1027)

    def check_file (self):
        f = StringIO.StringIO(test_string)
        p = producers.file_producer(f)
        self._check_all(p, test_string)

    def check_output (self):
        p = producers.output_producer()
        for i in range(0,66):
            p.write('a')
        for i in range(0,65):
            p.write('b\n')
        self._check_all(p, 'a'*66 + 'b\r\n'*65)

    def check_composite (self):
        p1 = producers.simple_producer('a'*66, buffer_size = 5)
        p2 = producers.lines_producer(['b']*65)
        p = producers.composite_producer([p1, p2])
        self._check_all(p, 'a'*66 + 'b\r\n'*65)

    def check_glob (self):
        p1 = producers.simple_producer(test_string, buffer_size = 5)
        p = producers.globbing_producer(p1, buffer_size = 1024)
        self.test_true('1024 <= len(p.more())')

    def check_hooked (self):
        def f (num_bytes):
            self.test_val('num_bytes', len(test_string))
        p1 = producers.simple_producer(test_string, buffer_size = 5)
        p = producers.hooked_producer(p1, f)
        self._check_all(p, test_string)

    def check_chunked (self):
        p1 = producers.simple_producer('the quick brown fox', buffer_size = 5)
        p = producers.chunked_producer(p1, footers=['FOOTER'])
        self._check_all(p, """5\r
the q\r
5\r
uick \r
5\r
brown\r
4\r
 fox\r
0\r
FOOTER\r
\r\n""")

    def check_compressed (self):
        p1 = producers.simple_producer(test_string, buffer_size = 5)
        p = producers.compressed_producer(p1)
        compr_data = self._check_all(p, zlib.compress(test_string, 5))
        self.test_val('zlib.decompress(compr_data)', test_string)

    def check_escaping (self):
        p1 = producers.simple_producer('the quick brown fox', buffer_size = 5)
        p = producers.escaping_producer(p1,
                                        esc_from = ' ',
                                        esc_to = '_')
        self._check_all(p, 'the_quick_brown_fox')
        
# class ProducerTest


if __name__ == "__main__":
    (scenarios, options) = parse_args()
    run_scenarios(scenarios, options)
