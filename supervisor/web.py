import os
import re
import time
import traceback
import datetime

from supervisor import templating

from supervisor.compat import urllib
from supervisor.compat import urlparse
from supervisor.compat import as_bytes
from supervisor.compat import as_string
from supervisor.compat import PY2
from supervisor.compat import unicode

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
            tb = traceback.format_exc()
            # this should go to the main supervisor log file
            self.request.channel.server.logger.log('Web interface error', tb)
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
            if PY2 and (len(self.request.outgoing) > 0):
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

    content_type = 'text/html;charset=utf-8'
    delay = .5

    def __init__(self, context):
        self.context = context
        template = self.context.template
        if not os.path.isabs(template):
            here = os.path.abspath(os.path.dirname(__file__))
            template = os.path.join(here, template)
        self.root = templating.parse_xml(template)
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
        response['body'] = as_bytes(body)
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
                    tail = rpcinterface.readProcessStdoutLog(processname,
                                                             limit, offset)
                except RPCError as e:
                    if e.code == Faults.NO_FILE:
                        tail = 'No file for %s' % processname
                    else:
                        tail = 'ERROR: unexpected rpc fault [%d] %s' % (
                            e.code, e.text)

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
            'name': 'Start',
            'href': 'index.html?processname=%s&amp;action=start' % processname,
            'target': None,
        }
        restart = {
            'name': 'Restart',
            'href': 'index.html?processname=%s&amp;action=restart' % processname,
            'target': None,
        }
        stop = {
            'name': 'Stop',
            'href': 'index.html?processname=%s&amp;action=stop' % processname,
            'target': None,
        }
        clearlog = {
            'name': 'Clear Log',
            'href': 'index.html?processname=%s&amp;action=clearlog' % processname,
            'target': None,
        }
        tailf_stdout = {
            'name': 'Tail -f Stdout',
            'href': 'logtail/%s' % processname,
            'target': '_blank'
        }
        tailf_stderr = {
            'name': 'Tail -f Stderr',
            'href': 'logtail/%s/stderr' % processname,
            'target': '_blank'
        }
        if state == ProcessStates.RUNNING:
            actions = [restart, stop, clearlog, tailf_stdout, tailf_stderr]
        elif state in (ProcessStates.STOPPED, ProcessStates.EXITED,
                       ProcessStates.FATAL):
            actions = [start, None, clearlog, tailf_stdout, tailf_stderr]
        else:
            actions = [None, None, clearlog, tailf_stdout, tailf_stderr]
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
                
            elif action == 'startProcessGroup':
                try:
                    callback = rpcinterface.supervisor.startProcessGroup(namespec)
                except RPCError as e:
                    msg = 'unexpected rpc fault [%d] %s' % (e.code, e.text)
                    def startgrperr():
                        return msg
                    startgrperr.delay = 0.05
                    return startgrperr
                
                def startgroup():
                    if callback() is NOT_DONE_YET:
                        return NOT_DONE_YET
                    return '组 %s 的所有进程已启动' % namespec
                startgroup.delay = 0.05
                return startgroup
                
            elif action == 'stopProcessGroup':
                try:
                    callback = rpcinterface.supervisor.stopProcessGroup(namespec)
                except RPCError as e:
                    msg = 'unexpected rpc fault [%d] %s' % (e.code, e.text)
                    def stopgrperr():
                        return msg
                    stopgrperr.delay = 0.05
                    return stopgrperr
                
                def stopgroup():
                    if callback() is NOT_DONE_YET:
                        return NOT_DONE_YET
                    return '组 %s 的所有进程已停止' % namespec
                stopgroup.delay = 0.05
                return stopgroup

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

                if action == 'start':
                    try:
                        bool_or_callback = (
                            rpcinterface.supervisor.startProcess(namespec)
                            )
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
                            msg = 'unexpected rpc fault [%d] %s' % (
                                e.code, e.text)
                        def starterr():
                            return 'ERROR: Process %s: %s' % (namespec, msg)
                        starterr.delay = 0.05
                        return starterr

                    if callable(bool_or_callback):
                        def startprocess():
                            try:
                                result = bool_or_callback()
                            except RPCError as e:
                                if e.code == Faults.SPAWN_ERROR:
                                    msg = 'spawn error'
                                elif e.code == Faults.ABNORMAL_TERMINATION:
                                    msg = 'abnormal termination'
                                else:
                                    msg = 'unexpected rpc fault [%d] %s' % (
                                        e.code, e.text)
                                return 'ERROR: Process %s: %s' % (namespec, msg)

                            if result is NOT_DONE_YET:
                                return NOT_DONE_YET
                            return 'Process %s started' % namespec
                        startprocess.delay = 0.05
                        return startprocess
                    else:
                        def startdone():
                            return 'Process %s started' % namespec
                        startdone.delay = 0.05
                        return startdone

                elif action == 'stop':
                    try:
                        bool_or_callback = (
                            rpcinterface.supervisor.stopProcess(namespec)
                            )
                    except RPCError as e:
                        msg = 'unexpected rpc fault [%d] %s' % (e.code, e.text)
                        def stoperr():
                            return msg
                        stoperr.delay = 0.05
                        return stoperr

                    if callable(bool_or_callback):
                        def stopprocess():
                            try:
                                result = bool_or_callback()
                            except RPCError as e:
                                return 'unexpected rpc fault [%d] %s' % (
                                    e.code, e.text)
                            if result is NOT_DONE_YET:
                                return NOT_DONE_YET
                            return 'Process %s stopped' % namespec
                        stopprocess.delay = 0.05
                        return stopprocess
                    else:
                        def stopdone():
                            return 'Process %s stopped' % namespec
                        stopdone.delay = 0.05
                        return stopdone

                elif action == 'restart':
                    results_or_callback = rpcinterface.system.multicall(
                        [ {'methodName':'supervisor.stopProcess',
                           'params': [namespec]},
                          {'methodName':'supervisor.startProcess',
                           'params': [namespec]},
                          ]
                        )
                    if callable(results_or_callback):
                        callback = results_or_callback
                        def restartprocess():
                            results = callback()
                            if results is NOT_DONE_YET:
                                return NOT_DONE_YET
                            return 'Process %s restarted' % namespec
                        restartprocess.delay = 0.05
                        return restartprocess
                    else:
                        def restartdone():
                            return 'Process %s restarted' % namespec
                        restartdone.delay = 0.05
                        return restartdone

                elif action == 'clearlog':
                    try:
                        callback = rpcinterface.supervisor.clearProcessLogs(
                            namespec)
                    except RPCError as e:
                        msg = 'unexpected rpc fault [%d] %s' % (e.code, e.text)
                        def clearerr():
                            return msg
                        clearerr.delay = 0.05
                        return clearerr

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
                    location = server_url + "/" + '?message=%s' % urllib.quote(
                        message)
                    response['headers']['Location'] = location

        supervisord = self.context.supervisord
        rpcinterface = RootRPCInterface(
            [('supervisor',
              SupervisorNamespaceRPCInterface(supervisord))]
            )

        # 按组收集进程
        groups = {}
        for groupname, group in supervisord.process_groups.items():
            groups[groupname] = []
            for process_name in group.processes.keys():
                sent_name = make_namespec(groupname, process_name)
                info = rpcinterface.supervisor.getProcessInfo(sent_name)
                process = group.processes[process_name]
                actions = self.actions_for_process(process)
                groups[groupname].append({
                    'status': info['statename'],
                    'name': process_name,
                    'group': groupname,
                    'actions': actions,
                    'state': info['state'],
                    'description': info['description'],
                })
        
        # 按照组名称排序
        sorted_groups = sorted(groups.items())

        root = self.clone()

        if message is not None:
            statusarea = root.findmeld('statusmessage')
            statusarea.attrib['class'] = 'status_msg'
            statusarea.content(message)

        # 处理分组显示
        if sorted_groups:
            process_groups_div = root.findmeld('process-groups')
            
            for groupname, processes in sorted_groups:
                # 计算组的整体状态
                running_count = sum(1 for p in processes if p['state'] == ProcessStates.RUNNING)
                error_count = sum(1 for p in processes if p['state'] in (ProcessStates.FATAL, ProcessStates.BACKOFF))
                total_count = len(processes)
                
                # 创建组容器
                group_div = templating.Element('div')
                group_div.attrib['class'] = 'process-group'
                
                # 创建组标题栏
                header_div = templating.Element('div')
                header_div.attrib['class'] = 'group-header'
                
                # 添加折叠图标
                icon = templating.Element('i')
                icon.attrib['class'] = 'fas fa-angle-down group-icon'
                header_div.append(icon)
                
                # 添加组名称
                group_name = templating.Element('div')
                group_name.attrib['class'] = 'group-name'
                group_name.content(groupname)
                header_div.append(group_name)
                
                # 添加组状态摘要
                summary_div = templating.Element('div')
                summary_div.attrib['class'] = 'group-summary'
                
                # 状态标签
                status_span = templating.Element('div')
                if error_count > 0:
                    status_class = 'group-status error'
                    status_text = '%d/%d 错误' % (error_count, total_count)
                elif running_count == total_count:
                    status_class = 'group-status running'
                    status_text = '全部运行 (%d)' % total_count
                elif running_count == 0:
                    status_class = 'group-status'
                    status_text = '全部停止 (%d)' % total_count
                else:
                    status_class = 'group-status partial'
                    status_text = '%d/%d 运行中' % (running_count, total_count)
                
                status_span.attrib['class'] = status_class
                status_span.content(status_text)
                summary_div.append(status_span)
                
                # 组操作按钮
                actions_div = templating.Element('div')
                actions_div.attrib['class'] = 'group-actions'
                
                # 启动全部按钮
                start_a = templating.Element('a')
                start_a.attrib['href'] = 'index.html?action=startProcessGroup&amp;processname=%s' % urllib.quote(groupname)
                start_a.content('启动全部')
                actions_div.append(start_a)
                
                # 停止全部按钮
                stop_a = templating.Element('a')
                stop_a.attrib['href'] = 'index.html?action=stopProcessGroup&amp;processname=%s' % urllib.quote(groupname)
                stop_a.content('停止全部')
                actions_div.append(stop_a)
                
                summary_div.append(actions_div)
                header_div.append(summary_div)
                
                group_div.append(header_div)
                
                # 创建组内容区域
                content_div = templating.Element('div')
                content_div.attrib['class'] = 'group-content'
                
                # 创建进程表格
                table = templating.Element('table')
                
                # 表头
                thead = templating.Element('thead')
                tr = templating.Element('tr')
                
                th_state = templating.Element('th')
                th_state.attrib['class'] = 'state'
                th_state.content('状态')
                tr.append(th_state)
                
                th_desc = templating.Element('th')
                th_desc.attrib['class'] = 'desc'
                th_desc.content('描述')
                tr.append(th_desc)
                
                th_name = templating.Element('th')
                th_name.attrib['class'] = 'name'
                th_name.content('名称')
                tr.append(th_name)
                
                th_action = templating.Element('th')
                th_action.attrib['class'] = 'action'
                th_action.content('操作')
                tr.append(th_action)
                
                thead.append(tr)
                table.append(thead)
                
                # 表内容
                tbody = templating.Element('tbody')
                
                for i, process in enumerate(processes):
                    tr = templating.Element('tr')
                    if i % 2:
                        tr.attrib['class'] = 'shade'
                    
                    # 状态列
                    td_status = templating.Element('td')
                    td_status.attrib['class'] = 'status'
                    
                    status_span = templating.Element('span')
                    status_span.attrib['class'] = self.css_class_for_state(process['state'])
                    status_span.content(process['status'].lower())
                    td_status.append(status_span)
                    tr.append(td_status)
                    
                    # 描述列
                    td_info = templating.Element('td')
                    info_span = templating.Element('span')
                    info_span.content(process['description'])
                    td_info.append(info_span)
                    tr.append(td_info)
                    
                    # 名称列
                    td_name = templating.Element('td')
                    name_a = templating.Element('a')
                    processname = make_namespec(process['group'], process['name'])
                    name_a.attrib['href'] = 'tail.html?processname=%s' % urllib.quote(processname)
                    name_a.attrib['target'] = '_blank'
                    name_a.content(processname)
                    td_name.append(name_a)
                    tr.append(td_name)
                    
                    # 操作列
                    td_action = templating.Element('td')
                    td_action.attrib['class'] = 'action'
                    ul = templating.Element('ul')
                    
                    for action in process['actions']:
                        li = templating.Element('li')
                        if action is None:
                            li.attrib['class'] = 'hidden'
                            a = templating.Element('a')
                            a.attrib['href'] = '#'
                            li.append(a)
                        else:
                            a = templating.Element('a')
                            a.attrib['href'] = action['href']
                            a.content(action['name'])
                            if action['target']:
                                a.attrib['target'] = action['target']
                            li.append(a)
                        ul.append(li)
                    
                    td_action.append(ul)
                    tr.append(td_action)
                    
                    tbody.append(tr)
                
                table.append(tbody)
                content_div.append(table)
                group_div.append(content_div)
                
                process_groups_div.append(group_div)
        else:
            process_groups_div = root.findmeld('process-groups')
            process_groups_div.content('没有程序可以管理')

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
        form_urlencoded = urlparse.parse_qsl(data)
        query_data = urlparse.parse_qs(query)

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

