import sys
import unittest

from supervisor.tests.base import DummySupervisor
from supervisor.tests.base import DummyRequest

class DeferredWebProducerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.web import DeferredWebProducer
        return DeferredWebProducer

    def _makeOne(self, request, callback):
        producer = self._getTargetClass()(request, callback)
        return producer

    def test_ctor(self):
        request = DummyRequest('/index.html', [], '', '')
        callback = lambda *x: None
        callback.delay = 1
        producer = self._makeOne(request, callback)
        self.assertEqual(producer.callback, callback)
        self.assertEqual(producer.request, request)
        self.assertEqual(producer.finished, False)
        self.assertEqual(producer.delay, 1)

    def test_more_not_done_yet(self):
        request = DummyRequest('/index.html', [], '', '')
        from supervisor.http import NOT_DONE_YET
        callback = lambda *x: NOT_DONE_YET
        callback.delay = 1
        producer = self._makeOne(request, callback)
        self.assertEqual(producer.more(), NOT_DONE_YET)

    def test_more_exception_caught(self):
        request = DummyRequest('/index.html', [], '', '')
        def callback(*arg):
            raise ValueError('foo')
        callback.delay = 1
        producer = self._makeOne(request, callback)
        self.assertEqual(producer.more(), None)
        logdata = request.channel.server.logger.logged
        self.assertEqual(len(logdata), 1)
        logged = logdata[0]
        self.assertEqual(logged[0], 'Web interface error')
        self.assertTrue(logged[1].startswith('Traceback'), logged[1])
        self.assertEqual(producer.finished, True)
        self.assertEqual(request._error, 500)

    def test_sendresponse_redirect(self):
        request = DummyRequest('/index.html', [], '', '')
        callback = lambda *arg: None
        callback.delay = 1
        producer = self._makeOne(request, callback)
        response = {'headers': {'Location':'abc'}}
        result = producer.sendresponse(response)
        self.assertEqual(result, None)
        self.assertEqual(request._error, 301)
        self.assertEqual(request.headers['Content-Type'], 'text/plain')
        self.assertEqual(request.headers['Content-Length'], 0)

    def test_sendresponse_withbody_and_content_type(self):
        request = DummyRequest('/index.html', [], '', '')
        callback = lambda *arg: None
        callback.delay = 1
        producer = self._makeOne(request, callback)
        response = {'body': 'abc', 'headers':{'Content-Type':'text/html'}}
        result = producer.sendresponse(response)
        self.assertEqual(result, None)
        self.assertEqual(request.headers['Content-Type'], 'text/html')
        self.assertEqual(request.headers['Content-Length'], 3)
        self.assertEqual(request.producers[0], 'abc')

class UIHandlerTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.web import supervisor_ui_handler
        return supervisor_ui_handler

    def _makeOne(self):
        filesystem = DummyFilesystem()
        supervisord = DummySupervisor()
        handler = self._getTargetClass()(filesystem, supervisord)
        return handler

    def test_get_view_index_html(self):
        request = DummyRequest('/index.html', [], '', '')
        handler = self._makeOne()
        viewdata = handler.get_view(request)
        from supervisor.web import StatusView
        self.assertEqual(viewdata['template'], 'ui/status.html')
        self.assertEqual(viewdata['view'], StatusView)

    def test_get_view_tail_html(self):
        request = DummyRequest('/tail.html', [], '', '')
        handler = self._makeOne()
        viewdata = handler.get_view(request)
        from supervisor.web import TailView
        self.assertEqual(viewdata['template'], 'ui/tail.html')
        self.assertEqual(viewdata['view'], TailView)

    def test_get_view_default(self):
        request = DummyRequest('/', [], '', '')
        handler = self._makeOne()
        viewdata = handler.get_view(request)
        from supervisor.web import StatusView
        self.assertEqual(viewdata['template'], 'ui/status.html')
        self.assertEqual(viewdata['view'], StatusView)

    def test_handle_request_no_view_method(self):
        request = DummyRequest('/foo.css', [], '', '')
        handler = self._makeOne()
        data = handler.handle_request(request)
        self.assertEqual(data, None)
        
    def test_handle_request_view_method(self):
        request = DummyRequest('/index.html', [], '', '')
        handler = self._makeOne()
        data = handler.handle_request(request)
        self.assertEqual(data, None)
        self.assertEqual(request.channel.producer.request, request)
        from supervisor.web import StatusView
        self.assertEqual(request.channel.producer.callback.__class__,StatusView)

    def test_do_view_request(self):
        request = DummyRequest('/index.html', [], '', '')
        handler = self._makeOne()
        from supervisor.web import StatusView
        viewdata = {'template':'ui/status.html', 'view':StatusView}
        handler.do_view_request(viewdata, request)
        self.assertEqual(request.channel.producer.request, request)
        self.assertEqual(request.channel.producer.callback.__class__,StatusView)

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

class DummyFilesystem:
    def __init__(self):
        self.stat_return = (16877, 12515682L, 234881026L, 24, 501, 501,
                            816L, 1187846057, 1187819244, 1187819244)
        import StringIO
        self.file = StringIO.StringIO()
    def isdir(self, path):
        return False
    def isfile(self, path):
        return True
    def stat(self, path):
        return self.stat_return
    def open(self, *arg, **kw):
        return self.file

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
