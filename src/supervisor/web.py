import os
import re
import cgi
import meld3
import time
import traceback
from options import readFile
from medusa import default_handler
from medusa import producers
from medusa.http_server import http_date
from medusa.http_server import get_header
from medusa import producers
from supervisord import ProcessStates
from http import NOT_DONE_YET
import xmlrpc

class DeferredWebProducer:
    """ A medusa producer that implements a deferred callback; requires
    a subclass of asynchat.async_chat that handles NOT_DONE_YET sentinel """
    CONNECTION = re.compile ('Connection: (.*)', re.IGNORECASE)

    def __init__(self, request, callback):
        self.callback = callback
        self.request = request
        self.finished = False
        self.delay = float(callback.delay)

    def more(self):
        if self.finished:
            return ''
        try:
            response = self.callback()
            if response is NOT_DONE_YET:
                return NOT_DONE_YET
                
            self.finished = True

            return self.sendresponse(response)

        except:
            # report unexpected exception back to server
            traceback.print_exc()
            self.finished = True
            self.request.error(500)

    def sendresponse(self, response):
        body = response.get('body', '')
        content_type = response.get('content_type', 'text/html')
        self.request['Content-Type'] = content_type
        self.request['Content-Length'] = len(body)

        headers = response.get('headers', [])
        for header in headers:
            self.request[header] = headers[header]

        self.request.push(body)

        connection = get_header(self.CONNECTION, self.request.header)

        close_it = 0
        wrap_in_chunking = 0

        if self.request.version == '1.0':
            if connection == 'keep-alive':
                if not self.request.has_key('Content-Length'):
                    close_it = 1
                else:
                    self.request['Connection'] = 'Keep-Alive'
            else:
                close_it = 1
        elif self.request.version == '1.1':
            if connection == 'close':
                close_it = 1
            elif not self.request.has_key ('Content-Length'):
                if self.request.has_key ('Transfer-Encoding'):
                    if not self.request['Transfer-Encoding'] == 'chunked':
                        close_it = 1
                elif self.request.use_chunked:
                    self.request['Transfer-Encoding'] = 'chunked'
                    wrap_in_chunking = 1
                else:
                    close_it = 1
        elif self.request.version is None:
            close_it = 1

        outgoing_header = producers.simple_producer (
            self.request.build_reply_header())

        if close_it:
            self.request['Connection'] = 'close'

        if wrap_in_chunking:
            outgoing_producer = producers.chunked_producer (
                    producers.composite_producer (self.request.outgoing)
                    )
            # prepend the header
            outgoing_producer = producers.composite_producer(
                [outgoing_header, outgoing_producer]
                )
        else:
            # prepend the header
            self.request.outgoing.insert(0, outgoing_header)
            outgoing_producer = producers.composite_producer (
                self.request.outgoing)

        # apply a few final transformations to the output
        self.request.channel.push_with_producer (
                # globbing gives us large packets
                producers.globbing_producer (
                        # hooking lets us log the number of bytes sent
                        producers.hooked_producer (
                                outgoing_producer,
                                self.request.log
                                )
                        )
                )

        self.request.channel.current_request = None

        if close_it:
            self.request.channel.close_when_done()

class ViewContext:
    def __init__(self, **kw):
        self.__dict__.update(kw)

class MeldView:

    content_type = 'text/html'
    delay = .5

    def __init__(self, context):
        self.context = context
        template = self.context.template
        if not os.path.isabs(template):
            here = os.path.abspath(os.path.dirname(__file__))
            template = os.path.join(here, template)
        self.root = meld3.parse_xml(template)
        self.callback = None

    def __call__(self):
        body = self.render()
        if body is NOT_DONE_YET:
            return NOT_DONE_YET

        response = self.context.response
        headers = response['headers']
        headers['Content-Type'] = self.content_type
        headers['Pragma'] = 'no-cache'
        headers['Cache-Control'] = 'no-cache'
        headers['Expires'] = http_date.build_http_date(0)
        response['body'] = body
        return response

    def clone(self):
        return self.root.clone()

class TailView(MeldView):
    def render(self):
        supervisord = self.context.supervisord
        request = self.context.request

        path, params, query, fragment = request.split_uri()

        if not query:
            tail = 'No process name found'
            processname = None
        else:
            while query.startswith('?'):
                query = query[1:]
            params = cgi.parse_qs(query)
            processname = params.get('processname',[None])[0]

            if not processname:
                tail = 'No process name found'
            else:
                rpcinterface = xmlrpc.SupervisorNamespaceRPCInterface(
                    supervisord)
                try:
                    tail = rpcinterface.readProcessLog(processname, -1024, 0)
                except xmlrpc.RPCError, e:
                    if e.code == xmlrpc.Faults.NO_FILE:
                        tail = 'No file for %s' % processname
                    else:
                        raise

        root = self.clone()

        title = root.findmeld('title')
        title.content('Supervisor tail of process %s' % processname)
        tailbody = root.findmeld('tailbody')
        tailbody.content(tail)

        refresh_anchor = root.findmeld('refresh_anchor')
        if processname is not None:
            refresh_anchor.attributes(href='tail.html?processname=%s' %
                                      processname)
        else:
            refresh_anchor.deparent()

        return root.write_xhtmlstring()

class StatusView(MeldView):
    def actions_for_process(self, process):
        state = process.get_state()
        processname = process.config.name
        start = {
        'name':'Start',
        'href':'index.html?processname=%s&amp;action=start' % processname,
        'target':None,
        }
        restart = {
        'name':'Restart',
        'href':'index.html?processname=%s&amp;action=restart' % processname,
        'target':None,
        }
        stop = {
        'name':'Stop',
        'href':'index.html?processname=%s&amp;action=stop' % processname,
        'target':None,
        }
        clearlog = {
        'name':'Clear Log',
        'href':'index.html?processname=%s&amp;action=clearlog' % processname,
        'target':None,
        }
        tailf = {
        'name':'Tail -f',
        'href':'logtail/%s' % processname,
        'target':'_blank'
        }
        if state == ProcessStates.RUNNING:
            actions = [restart, stop, clearlog, tailf]
        elif state in (ProcessStates.STOPPED, ProcessStates.EXITED,
                       ProcessStates.FATAL):
            actions = [start, None, clearlog, tailf]
        else:
            actions = [None, None, clearlog, tailf]
        return actions

    def css_class_for_state(self, state):
        if state == ProcessStates.RUNNING:
            return 'statusrunning'
        elif state in (ProcessStates.FATAL, ProcessStates.BACKOFF):
            return 'statuserror'
        else:
            return 'statusnominal'

    def make_callback(self, query):
        message = None
        supervisord = self.context.supervisord

        while query.startswith('?'):
            query = query[1:]

        params = cgi.parse_qs(query)
        processname = params.get('processname',[None])[0]
        action = params.get('action', [None])[0]

        # the rpc interface code is already written to deal properly in a
        # deferred world, so just use it
        rpcinterface = xmlrpc.RPCInterface(supervisord)

        if action:

            if action == 'refresh':
                def donothing():
                    message = 'Page refreshed at %s' % time.ctime()
                    return message
                donothing.delay = 0.05
                return donothing

            elif action == 'stopall':
                callback = rpcinterface.supervisor.stopAllProcesses()
                def stopall():
                    if callback() is NOT_DONE_YET:
                        return NOT_DONE_YET
                    else:
                        return 'All stopped at %s' % time.ctime()
                stopall.delay = 0.05
                return stopall

            elif action == 'restartall':
                callback = rpcinterface.system.multicall(
                    [ {'methodName':'supervisor.stopAllProcesses'},
                      {'methodName':'supervisor.startAllProcesses'} ] )
                def restartall():
                    result = callback()
                    if result is NOT_DONE_YET:
                        return NOT_DONE_YET
                    return 'All restarted at %s' % time.ctime()
                restartall.delay = 0.05
                return restartall

            elif processname:
                if not supervisord.processes.get(processname):
                    def wrong():
                        return 'No such process named %s' % processname
                    wrong.delay = 0.05
                    return wrong
                
                elif action == 'stop':
                    callback = rpcinterface.supervisor.stopProcess(processname)
                    def stopprocess():
                        result = callback()
                        if result is NOT_DONE_YET:
                            return NOT_DONE_YET
                        return 'Process %s stopped' % processname
                    stopprocess.delay = 0.05
                    return stopprocess

                elif action == 'restart':
                    callback = rpcinterface.system.multicall(
                        [ {'methodName':'supervisor.stopProcess',
                           'params': [processname]},
                          {'methodName':'supervisor.startProcess',
                           'params': [processname]},
                          ]
                        )
                    def restartprocess():
                        if callback() is NOT_DONE_YET:
                            return NOT_DONE_YET
                        return 'Process %s restarted' % processname
                    restartprocess.delay = 0.05
                    return restartprocess

                elif action == 'start':
                    try:
                        callback = rpcinterface.supervisor.startProcess(
                            processname)
                    except xmlrpc.RPCError, e:
                        if e.code == xmlrpc.Faults.SPAWN_ERROR:
                            def spawnerr():
                                return 'Process %s spawn error' % processname
                            spawnerr.delay = 0.05
                            return spawnerr
                    def startprocess():
                        if callback() is NOT_DONE_YET:
                            return NOT_DONE_YET
                        return 'Process %s started' % processname
                    startprocess.delay = 0.05
                    return startprocess
                
                elif action == 'clearlog':
                    callback = rpcinterface.supervisor.clearProcessLog(
                        processname)
                    def clearlog():
                        return 'Log for %s cleared' % processname
                    clearlog.delay = 0.05
                    return clearlog

        raise ValueError(action)
    
    def render(self):
        request = self.context.request
        path, params, query, fragment = request.split_uri()

        message = None

        if query:
            if not self.callback:
                self.callback = self.make_callback(query)
                return NOT_DONE_YET

            else:
                message =  self.callback()
                if message is NOT_DONE_YET:
                    return NOT_DONE_YET

        supervisord = self.context.supervisord

        processnames = supervisord.processes.keys()
        processnames.sort()
        data = []
        for processname in processnames:
            process = supervisord.processes[processname]
            state = process.get_state()
            from supervisord import getProcessStateDescription
            statedesc = getProcessStateDescription(state)
            actions = self.actions_for_process(process)
            data.append({'status':statedesc, 'name':processname,
                         'actions':actions,
                         'state':state})
        
        root = self.clone()

        if message is not None:
            statusarea = root.findmeld('statusmessage')
            statusarea.attrib['class'] = 'statusmessage'
            statusarea.content(message)
            
        iterator = root.findmeld('tr').repeat(data)
        for element, item in iterator:
            status_text = element.findmeld('status_text')
            status_text.content(item['status'])
            status_text.attrib['class'] = self.css_class_for_state(
                item['state'])
            anchor = element.findmeld('name_anchor')
            processname = item['name']
            anchor.attributes(href='tail.html?processname=%s' % processname)
            anchor.content(processname)
            actions = item['actions']
            actionitem_td = element.findmeld('actionitem_td')
            for element, actionitem in actionitem_td.repeat(actions):
                if actionitem is None:
                    element.content('&nbsp;', structure=True)
                else:
                    anchor = element.findmeld('actionitem_anchor')
                    anchor.attributes(href=actionitem['href'])
                    anchor.content(actionitem['name'])
                    if actionitem['target']:
                        anchor.attributes(target=actionitem['target'])

        return root.write_xhtmlstring()

VIEWS = {
    'index.html': {
          'template':'ui/status.html',
          'view':StatusView
          },
    'tail.html': {
           'template':'ui/tail.html',
           'view':TailView,
           },
    }


class supervisor_ui_handler(default_handler.default_handler):
    IDENT = 'Supervisor Web UI HTTP Request Handler'

    def __init__(self, filesystem, supervisord):
        self.supervisord = supervisord
        default_handler.default_handler.__init__(self, filesystem)

    def get_view(self, request):
        path, params, query, fragment = request.split_uri()

        if '%' in path:
            path = cgi.unquote(path)

        # strip off all leading slashes
        while path and path[0] == '/':
            path = path[1:]

        if not path:
            path = 'index.html'

        viewdata = VIEWS.get(path)
        return viewdata

    def handle_request(self, request):
        viewdata = self.get_view(request)
        if viewdata:
            self.do_view_request(viewdata, request)
        else:
            return default_handler.default_handler.handle_request(self, request)

    def do_view_request(self, viewdata, request):
        response = {}
        response['headers'] = {}

        viewclass = viewdata['view']
        viewtemplate = viewdata['template']
        context = ViewContext(template=viewtemplate,
                              request=request,
                              response=response,
                              supervisord=self.supervisord)
        view = viewclass(context)
        pushproducer = request.channel.push_with_producer
        pushproducer(DeferredWebProducer(request, view))

