import sys
import unittest

from supervisor.tests.base import DummySupervisor

class StatusViewTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.web import StatusView
        return StatusView

    def _makeOne(self, context):
        klass = self._getTargetClass()
        return klass(context)

    def test_make_callback_noaction(self):
        context = DummyContext()
        context.supervisord = DummySupervisor()
        context.template = 'ui/status.html'
        view = self._makeOne(context)
        self.assertRaises(ValueError, view.make_callback, 'process', None)

class DummyContext:
    pass

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
