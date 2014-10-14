import os
import re
import time
import traceback
import datetime

import meld3

from supervisor.compat import StringIO
from supervisor.compat import urllib
from supervisor.compat import parse_qs
from supervisor.compat import parse_qsl
from supervisor.compat import as_string
from supervisor.compat import PY3

from supervisor.medusa import producers
from supervisor.medusa.http_server import http_date
from supervisor.medusa.http_server import get_header
from supervisor.medusa.xmlrpc_handler import collector

from supervisor.process import ProcessStates
from supervisor.http import NOT_DONE_YET

from supervisor.options import VERSION
from supervisor.options import make_namespec
from supervisor.options import split_namespec

from supervisor.xmlrpc import SystemNamespaceRPCInterface
from supervisor.xmlrpc import RootRPCInterface
from supervisor.xmlrpc import Faults
from supervisor.xmlrpc import RPCError

from supervisor.rpcinterface import SupervisorNamespaceRPCInterface

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
            io = StringIO()
            traceback.print_exc(file=io)
            # this should go to the main supervisor log file
            self.request.channel.server.logger.log('Web interface error',
                                                  io.getvalue())
            self.finished = True
            self.request.error(500)

    def sendresponse(self, response):

        headers = response.get('headers', {})
        for header in headers:
            self.request[header] = headers[header]

        if 'Content-Type' not in self.request:
            self.request['Content-Type'] = 'text/plain'

        if headers.get('Location'):
            self.request['Content-Length'] = 0
            self.request.error(301)
            return

        body = response.get('body', '')
        self.request['Content-Length'] = len(body)

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
            elif 'Content-Length' not in self.request:
                if 'Transfer-Encoding' in self.request:
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
            # fix AttributeError: 'unicode' object has no attribute 'more'
            if (not PY3) and (len(self.request.outgoing) > 0):
                body = self.request.outgoing[0]
                if isinstance(body, unicode):
                    self.request.outgoing[0] = producers.simple_producer (body)

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
        response['body'] = as_string(body)
        return response

    def render(self):
        pass

    def clone(self):
        return self.root.clone()

class TailView(MeldView):
    def render(self):
        supervisord = self.context.supervisord
        form = self.context.form

        if not 'processname' in form:
            tail = 'No process name found'
            processname = None
        else:
            processname = form['processname']
            offset = 0
            limit = form.get('limit', '1024')
            limit = min(-1024, int(limit)*-1 if limit.isdigit() else -1024)
            if not processname:
                tail = 'No process name found'
            else:
                rpcinterface = SupervisorNamespaceRPCInterface(supervisord)
                try:
                    tail = rpcinterface.readProcessLog(processname, limit, offset)
                    tail = rpcinterface.readProcessLog(processname, -1024, 0)
                except RPCError as e:
                    if e.code == Faults.NO_FILE:
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
            refresh_anchor.attributes(
                href='tail.html?processname=%s&limit=%s' % (
                    urllib.quote(processname), urllib.quote(str(abs(limit)))
                    )
            )
        else:
            refresh_anchor.deparent()

        return as_string(root.write_xhtmlstring())

class StatusView(MeldView):
    def actions_for_process(self, process):
        state = process.get_state()
        processname = urllib.quote(make_namespec(process.group.config.name,
                                                 process.config.name))
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

    def make_callback(self, namespec, action):
        supervisord = self.context.supervisord

        # the rpc interface code is already written to deal properly in a
        # deferred world, so just use it
        main =   ('supervisor', SupervisorNamespaceRPCInterface(supervisord))
        system = ('system', SystemNamespaceRPCInterface([main]))

        rpcinterface = RootRPCInterface([main, system])

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

            elif namespec:
                def wrong():
                    return 'No such process named %s' % namespec
                wrong.delay = 0.05
                group_name, process_name = split_namespec(namespec)
                group = supervisord.process_groups.get(group_name)
                if group is None:
                    return wrong
                process = group.processes.get(process_name)
                if process is None:
                    return wrong

                elif action == 'stop':
                    callback = rpcinterface.supervisor.stopProcess(namespec)
                    def stopprocess():
                        result = callback()
                        if result is NOT_DONE_YET:
                            return NOT_DONE_YET
                        return 'Process %s stopped' % namespec
                    stopprocess.delay = 0.05
                    return stopprocess

                elif action == 'restart':
                    callback = rpcinterface.system.multicall(
                        [ {'methodName':'supervisor.stopProcess',
                           'params': [namespec]},
                          {'methodName':'supervisor.startProcess',
                           'params': [namespec]},
                          ]
                        )
                    def restartprocess():
                        result = callback()
                        if result is NOT_DONE_YET:
                            return NOT_DONE_YET
                        return 'Process %s restarted' % namespec
                    restartprocess.delay = 0.05
                    return restartprocess

                elif action == 'start':
                    try:
                        callback = rpcinterface.supervisor.startProcess(
                            namespec)
                    except RPCError as e:
                        if e.code == Faults.NO_FILE:
                            msg = 'no such file'
                        elif e.code == Faults.NOT_EXECUTABLE:
                            msg = 'file not executable'
                        elif e.code == Faults.ALREADY_STARTED:
                            msg = 'already started'
                        elif e.code == Faults.SPAWN_ERROR:
                            msg = 'spawn error'
                        elif e.code == Faults.ABNORMAL_TERMINATION:
                            msg = 'abnormal termination'
                        else:
                            msg = 'unexpected rpc fault code %d' % e.code
                        def starterr():
                            return 'ERROR: Process %s: %s' % (namespec, msg)
                        starterr.delay = 0.05
                        return starterr

                    def startprocess():
                        try:
                            result = callback()
                        except RPCError as e:
                            if e.code == Faults.SPAWN_ERROR:
                                msg = 'spawn error'
                            elif e.code == Faults.ABNORMAL_TERMINATION:
                                msg = 'abnormal termination'
                            else:
                                msg = 'unexpected rpc fault code %d' % e.code
                            return 'ERROR: Process %s: %s' % (namespec, msg)

                        if result is NOT_DONE_YET:
                            return NOT_DONE_YET
                        return 'Process %s started' % namespec
                    startprocess.delay = 0.05
                    return startprocess

                elif action == 'clearlog':
                    callback = rpcinterface.supervisor.clearProcessLog(
                        namespec)
                    def clearlog():
                        return 'Log for %s cleared' % namespec
                    clearlog.delay = 0.05
                    return clearlog

        raise ValueError(action)

    def render(self):
        form = self.context.form
        response = self.context.response
        processname = form.get('processname')
        action = form.get('action')
        message = form.get('message')

        if action:
            if not self.callback:
                self.callback = self.make_callback(processname, action)
                return NOT_DONE_YET

            else:
                message =  self.callback()
                if message is NOT_DONE_YET:
                    return NOT_DONE_YET
                if message is not None:
                    server_url = form['SERVER_URL']
                    location = server_url + '?message=%s' % urllib.quote(
                        message)
                    response['headers']['Location'] = location

        supervisord = self.context.supervisord
        rpcinterface = RootRPCInterface(
            [('supervisor',
              SupervisorNamespaceRPCInterface(supervisord))]
            )

        processnames = []
        for group in supervisord.process_groups.values():
            for gprocname in group.processes.keys():
                processnames.append((group.config.name, gprocname))

        processnames.sort()

        data = []
        for groupname, processname in processnames:
            actions = self.actions_for_process(
                supervisord.process_groups[groupname].processes[processname])
            sent_name = make_namespec(groupname, processname)
            info = rpcinterface.supervisor.getProcessInfo(sent_name)
            data.append({
                'status':info['statename'],
                'name':processname,
                'group':groupname,
                'actions':actions,
                'state':info['state'],
                'description':info['description'],
                })

        root = self.clone()

        if message is not None:
            statusarea = root.findmeld('statusmessage')
            statusarea.attrib['class'] = 'status_msg'
            statusarea.content(message)

        if data:
            iterator = root.findmeld('tr').repeat(data)
            shaded_tr = False

            for tr_element, item in iterator:
                status_text = tr_element.findmeld('status_text')
                status_text.content(item['status'].lower())
                status_text.attrib['class'] = self.css_class_for_state(
                    item['state'])

                info_text = tr_element.findmeld('info_text')
                info_text.content(item['description'])

                anchor = tr_element.findmeld('name_anchor')
                processname = make_namespec(item['group'], item['name'])
                anchor.attributes(href='tail.html?processname=%s' %
                                  urllib.quote(processname))
                anchor.content(processname)

                actions = item['actions']
                actionitem_td = tr_element.findmeld('actionitem_td')

                for li_element, actionitem in actionitem_td.repeat(actions):
                    anchor = li_element.findmeld('actionitem_anchor')
                    if actionitem is None:
                        anchor.attrib['class'] = 'hidden'
                    else:
                        anchor.attributes(href=actionitem['href'],
                                          name=actionitem['name'])
                        anchor.content(actionitem['name'])
                        if actionitem['target']:
                            anchor.attributes(target=actionitem['target'])
                if shaded_tr:
                    tr_element.attrib['class'] = 'shade'
                shaded_tr = not shaded_tr
        else:
            table = root.findmeld('statustable')
            table.replace('No programs to manage')

        root.findmeld('supervisor_version').content(VERSION)
        copyright_year = str(datetime.date.today().year)
        root.findmeld('copyright_date').content(copyright_year)

        return as_string(root.write_xhtmlstring())

class OKView:
    delay = 0
    def __init__(self, context):
        self.context = context

    def __call__(self):
        return {'body':'OK'}

VIEWS = {
    'index.html': {
          'template':'ui/status.html',
          'view':StatusView
          },
    'tail.html': {
           'template':'ui/tail.html',
           'view':TailView,
           },
    'ok.html': {
           'template':None,
           'view':OKView,
           },
    }


class supervisor_ui_handler:
    IDENT = 'Supervisor Web UI HTTP Request Handler'

    def __init__(self, supervisord):
        self.supervisord = supervisord

    def match(self, request):
        if request.command not in ('POST', 'GET'):
            return False

        path, params, query, fragment = request.split_uri()

        while path.startswith('/'):
            path = path[1:]

        if not path:
            path = 'index.html'

        for viewname in VIEWS.keys():
            if viewname == path:
                return True

    def handle_request(self, request):
        if request.command == 'POST':
            request.collector = collector(self, request)
        else:
            self.continue_request('', request)

    def continue_request (self, data, request):
        form = {}
        cgi_env = request.cgi_environment()
        form.update(cgi_env)
        if 'QUERY_STRING' not in form:
            form['QUERY_STRING'] = ''

        query = form['QUERY_STRING']

        # we only handle x-www-form-urlencoded values from POSTs
        form_urlencoded = parse_qsl(data)
        query_data = parse_qs(query)

        for k, v in query_data.items():
            # ignore dupes
            form[k] = v[0]

        for k, v in form_urlencoded:
            # ignore dupes
            form[k] = v

        form['SERVER_URL'] = request.get_server_url()

        path = form['PATH_INFO']
        # strip off all leading slashes
        while path and path[0] == '/':
            path = path[1:]
        if not path:
            path = 'index.html'

        viewinfo = VIEWS.get(path)
        if viewinfo is None:
            # this should never happen if our match method works
            return

        response = {'headers': {}}

        viewclass = viewinfo['view']
        viewtemplate = viewinfo['template']
        context = ViewContext(template=viewtemplate,
                              request = request,
                              form = form,
                              response = response,
                              supervisord=self.supervisord)
        view = viewclass(context)
        pushproducer = request.channel.push_with_producer
        pushproducer(DeferredWebProducer(request, view))

