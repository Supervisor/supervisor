"""Test suite for supervisor.confecho"""

import sys
import unittest
from supervisor.compat import StringIO
from supervisor import confecho

class TopLevelFunctionTests(unittest.TestCase):
    def test_main_writes_data_out_that_looks_like_a_config_file(self):
        sio = StringIO()
        confecho.main(out=sio)

        output = sio.getvalue()
        self.assertTrue("[supervisord]" in output)


def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
