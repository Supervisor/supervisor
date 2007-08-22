import sys
import unittest

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyRequest

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

    def test_render_noaction(self):
        context = DummyContext()
        context.supervisord = DummySupervisor()
        context.template = 'ui/status.html'
        context.request = DummyRequest('/foo', [], '', '')
        context.response = {}
        view = self._makeOne(context)
        data = view.render()
        self.assertTrue(data.startswith('<!DOCTYPE html PUBLIC'), data)

    def test_render_refresh(self):
        context = DummyContext()
        context.supervisord = DummySupervisor()
        context.template = 'ui/status.html'
        context.request = DummyRequest('/foo', [], '?action=refresh', '')
        context.response = {}
        view = self._makeOne(context)
        data = view.render()
        from supervisor.http import NOT_DONE_YET
        self.assertTrue(data is NOT_DONE_YET, data)

class DummyContext:
    pass

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
