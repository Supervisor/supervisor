import os
import cgi
import meld3
import time
from options import readFile
from medusa import default_handler
from medusa.http_server import http_date
from medusa import producers

class ViewContext:
    def __init__(self, **kw):
        self.__dict__.update(kw)

class MeldView:
    content_type = 'text/html'
    def __init__(self, context):
        self.context = context
        template = self.context.template
        if not os.path.isabs(template):
            here = os.path.abspath(os.path.dirname(__file__))
            template = os.path.join(here, template)
        self.root = meld3.parse_xml(template)

    def clone(self):
        return self.root.clone()

class TailView(MeldView):
    def handle_query(self, query):
        while query.startswith('?'):
            query = query[1:]

        params = cgi.parse_qs(query)
        processname = params.get('processname',[None])[0]
        return processname

    def render(self):
        supervisord = self.context.supervisord
        request = self.context.request

        path, params, query, fragment = request.split_uri()

        if not query:
            tail = 'No process name found'
            processname = None
        else:
            processname = self.handle_query(query)
            if not processname:
                tail = 'No process name found'
            else:
                process = supervisord.processes.get(processname)
                if process is None:
                    tail = 'No such process %s' % processname
                else:
                    try:
                        data = readFile(process.config.logfile, -1024, 0)
                    except ValueError, e:
                        tail = e.args[0]
                    else:
                        tail = data

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
        from supervisord import ProcessStates
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
        elif state in (ProcessStates.STOPPED, ProcessStates.KILLED,
                       ProcessStates.NOTSTARTED, ProcessStates.EXITED,
                       ProcessStates.ERROR):
            actions = [start, None, clearlog, tailf]
        else:
            actions = [None, None, clearlog, tailf]
        return actions

    def css_class_for_state(self, state):
        from supervisord import ProcessStates
        if state == ProcessStates.RUNNING:
            return 'statusrunning'
        elif state in (ProcessStates.KILLED, ProcessStates.ERROR):
            return 'statuserror'
        else:
            return 'statusnominal'

    def handle_query(self, query):
        message = None
        supervisord = self.context.supervisord

        while query.startswith('?'):
            query = query[1:]

        params = cgi.parse_qs(query)
        processname = params.get('processname',[None])[0]
        action = params.get('action', [None])[0]

        if action:
            t = time.ctime()
            if action == 'refresh':
                message = 'Page refreshed at %s' % t

            elif processname:
                process = supervisord.processes.get(processname)
                if process is None:
                    message = 'No such process %s at %s' % (processname, t)
                else:
                    if action == 'stop':
                        process.stop()
                        message = 'Stopped %s at %s' % (processname, t)
                    if action == 'restart':
                        msg = process.stop()
                        if not msg:
                            # XXX busywait
                            while not process.reportstatusmsg:
                                supervisord.reap()
                                supervisord.handle_procs_with_waitstatus()
                            process.spawn()
                            message = 'Restarted %s at %s' % (processname, t)
                        else:
                            message = msg
                    if action == 'start':
                        process.spawn()
                        print "process pid", process.pid
                        # XXX busywait
                        time.sleep(.5)
                        supervisord.reap()
                        supervisord.handle_procs_with_waitstatus()
                        message = 'Started %s at %s' % (processname, t)
                    if action == 'clearlog':
                        process.removelogs()
                        message = 'Cleared log of %s at %s' % (processname, t)

        return message
    
    def render(self):
        supervisord = self.context.supervisord
        request = self.context.request
        message = None
        path, params, query, fragment = request.split_uri()

        if query:
            message = self.handle_query(query)
        
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

    def handle_request(self, request):
        if request.command not in self.valid_commands:
            request.error (400) # bad request
            return

        path, params, query, fragment = request.split_uri()

        if '%' in path:
            path = cgi.unquote (path)

        # strip off all leading slashes
        while path and path[0] == '/':
            path = path[1:]

        if not path:
            path = 'index.html'

        viewdata = VIEWS.get(path)

        if viewdata is not None:
            context = ViewContext(template=viewdata['template'],
                                  request=request,
                                  supervisord=self.supervisord)
            view = viewdata['view'](context)
            rendering = view.render()
            request['Last-Modified'] = http_date.build_http_date(time.time())
            request['Content-Type'] = view.content_type
            request['Pragma'] = 'no-cache'
            request['Cache-Control'] = 'no-cache'
            request['Expires'] = http_date.build_http_date(0)
            request['Content-Length'] = len(rendering)
            if request.command == 'GET':
                request.push(producers.simple_producer(rendering))
                request.done()
                return

        return default_handler.default_handler.handle_request(self, request)

