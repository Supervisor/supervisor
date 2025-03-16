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
        
        # 处理直接返回的 HTML 字符串
        if isinstance(body, str) or isinstance(body, unicode):
            headers['Content-Type'] = self.content_type
            headers['Pragma'] = 'no-cache'
            headers['Cache-Control'] = 'no-cache'
            headers['Expires'] = http_date.build_http_date(0)
            response['body'] = as_bytes(body)
            return response
        
        # 原有的处理逻辑
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

        title_text = '进程日志' if processname is None else '进程 %s 的日志' % processname
        refresh_url = ''
        if processname is not None:
            refresh_url = 'tail.html?processname=%s&limit=%s' % (
                    urllib.quote(processname), urllib.quote(str(abs(limit)))
                    )
            
        # 使用自定义 HTML 模板
        html = '''<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <title>%s</title>
  <style>
    body {
      font-family: 'Helvetica Neue', Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #f5f5f5;
      color: #333;
    }
    
    .log-container {
      max-width: 1200px;
      margin: 20px auto;
      background: #fff;
      border-radius: 6px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
      overflow: hidden;
    }
    
    .log-header {
      background: #2c3e50;
      color: white;
      padding: 15px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    
    .log-header h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 500;
    }
    
    .log-controls {
      display: flex;
      gap: 10px;
    }
    
    .log-controls button {
      background: #3498db;
      color: white;
      border: none;
      border-radius: 4px;
      padding: 8px 12px;
      cursor: pointer;
      font-size: 14px;
      transition: background 0.2s;
    }
    
    .log-controls button:hover {
      background: #2980b9;
    }
    
    .log-search {
      display: flex;
      padding: 10px;
      background: #f8f9fa;
      border-bottom: 1px solid #e9ecef;
    }
    
    .log-search input {
      flex: 1;
      padding: 8px 12px;
      border: 1px solid #ced4da;
      border-radius: 4px;
      font-size: 14px;
    }
    
    .log-content {
      position: relative;
      overflow: auto;
      max-height: 70vh;
      background: #282c34;
      color: #abb2bf;
      padding: 0;
      margin: 0;
    }
    
    .log-content pre {
      margin: 0;
      padding: 15px;
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
      font-size: 13px;
      line-height: 1.5;
      tab-size: 4;
      white-space: pre-wrap;
    }
    
    .log-footer {
      display: flex;
      justify-content: space-between;
      padding: 10px 20px;
      background: #f8f9fa;
      border-top: 1px solid #e9ecef;
    }
    
    .log-footer a {
      color: #3498db;
      text-decoration: none;
    }
    
    .log-footer a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="log-container">
    <div class="log-header">
      <h1>%s</h1>
      <div class="log-controls">
        <button id="toggle-wrap-btn">自动换行</button>
        <button id="copy-logs-btn">复制日志</button>
        <a href="%s"><button type="button">刷新</button></a>
      </div>
    </div>
    
    <div class="log-search">
      <input type="text" id="log-search-input" placeholder="搜索日志..." />
    </div>
    
    <div class="log-content">
      <pre id="log-pre">%s</pre>
    </div>
    
    <div class="log-footer">
      <span id="log-stats">行数: 0</span>
      <a href="index.html">返回首页</a>
    </div>
  </div>

  <script>
    document.addEventListener('DOMContentLoaded', function() {
      // 计算行数
      const pre = document.getElementById('log-pre');
      const logText = pre.textContent;
      const lines = logText.split('\\n').filter(line => line.trim());
      document.getElementById('log-stats').textContent = `行数: ${lines.length}`;
      
      // 复制日志
      document.getElementById('copy-logs-btn').addEventListener('click', function() {
        navigator.clipboard.writeText(pre.textContent).then(function() {
          const btn = document.getElementById('copy-logs-btn');
          const originalText = btn.textContent;
          btn.textContent = '已复制!';
          setTimeout(() => {
            btn.textContent = originalText;
          }, 2000);
        });
      });
      
      // 自动换行
      const toggleWrapBtn = document.getElementById('toggle-wrap-btn');
      toggleWrapBtn.addEventListener('click', function() {
        if (pre.style.whiteSpace === 'pre-wrap' || pre.style.whiteSpace === '') {
          pre.style.whiteSpace = 'pre';
          this.textContent = '开启自动换行';
        } else {
          pre.style.whiteSpace = 'pre-wrap';
          this.textContent = '关闭自动换行';
        }
      });
      
      // 搜索功能
      document.getElementById('log-search-input').addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const logContent = pre.innerHTML;
        
        if(searchTerm) {
          // 使用简单的高亮实现
          const regex = new RegExp(searchTerm, 'gi');
          pre.innerHTML = logContent.replace(regex, match => 
            `<span style="background-color:yellow;color:black">${match}</span>`
          );
        } else {
          pre.innerHTML = logText;
        }
      });
    });
  </script>
</body>
</html>
''' % (title_text, title_text, refresh_url, tail.replace('<', '&lt;').replace('>', '&gt;'))

        return html

class StatusView(MeldView):
    def actions_for_process(self, process):
        state = process['state']
        processname = urllib.quote(make_namespec(process['group'], process['name']))
        actions = []
        
        if state == ProcessStates.RUNNING:
            actions.extend([
                {
                    'name': '重启',
            'href': 'index.html?processname=%s&amp;action=restart' % processname,
                },
                {
                    'name': '停止',
            'href': 'index.html?processname=%s&amp;action=stop' % processname,
                },
                {
                    'name': '清除日志',
            'href': 'index.html?processname=%s&amp;action=clearlog' % processname,
                },
                {
                    'name': '查看输出',
            'href': 'logtail/%s' % processname,
            'target': '_blank'
        }
            ])
        elif state in (ProcessStates.STOPPED, ProcessStates.EXITED, ProcessStates.FATAL):
            actions.extend([
                {
                    'name': '启动',
                    'href': 'index.html?processname=%s&amp;action=start' % processname,
                },
                {
                    'name': '清除日志',
                    'href': 'index.html?processname=%s&amp;action=clearlog' % processname,
                },
                {
                    'name': '查看输出',
                    'href': 'logtail/%s' % processname,
            'target': '_blank'
        }
            ])
        else:
            actions.extend([
                {
                    'name': '清除日志',
                    'href': 'index.html?processname=%s&amp;action=clearlog' % processname,
                },
                {
                    'name': '查看输出',
                    'href': 'logtail/%s' % processname,
                    'target': '_blank'
                }
            ])
        return actions

    def css_class_for_state(self, state):
        if state == ProcessStates.RUNNING:
            return 'statusrunning'
        elif state in (ProcessStates.FATAL, ProcessStates.BACKOFF):
            return 'statuserror'
        elif state == ProcessStates.STOPPED:
            return 'statusstopped'
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
                
            elif action == 'startgroup':
                # 启动整个组
                return self.start_group(namespec)
            elif action == 'stopgroup':
                # 停止整个组
                return self.stop_group(namespec)
            elif action == 'restartgroup':
                # 重启整个组
                return self.restart_group(namespec)

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
                message = self.callback()
                if message is NOT_DONE_YET:
                    return NOT_DONE_YET
                if message is not None:
                    server_url = form['SERVER_URL']
                    location = server_url + "/" + '?message=%s' % urllib.quote(message)
                    response['headers']['Location'] = location

        supervisord = self.context.supervisord
        rpcinterface = RootRPCInterface(
            [('supervisor',
              SupervisorNamespaceRPCInterface(supervisord))]
            )

        # 按组和独立进程组织
        groups = {}  # 组名 -> 组下的进程名列表
        ungrouped = []  # 未分组的进程列表
        
        # 首先构建所有组名的集合
        group_names = set()
        for process_group in supervisord.process_groups.values():
            # 检查是否是真实的组（有多个进程）
            processes = process_group.processes
            if len(processes) > 1:
                # 可能是一个组
                group_names.add(process_group.config.name)
        
        # 现在判断进程是否属于组并分类
        for process_group in supervisord.process_groups.values():
            group_name = process_group.config.name
            
            if group_name in group_names and len(process_group.processes) > 1:
                # 这是一个组
                if group_name not in groups:
                    groups[group_name] = []
                
                for process in process_group.processes.values():
                    groups[group_name].append((group_name, process.config.name))
            else:
                # 未分组的独立进程
                for process in process_group.processes.values():
                    ungrouped.append((group_name, process.config.name))
        
        # 对所有组排序
        sorted_groups = sorted(groups.items())
        # 排序未分组进程
        ungrouped.sort()

        root = self.clone()
        if message is not None:
            statusarea = root.findmeld('statusmessage')
            statusarea.attrib['class'] = 'status_msg'
            statusarea.content(message)

        if not (sorted_groups or ungrouped):
            table = root.findmeld('statustable')
            table.replace('暂无进程')
        else:
            content_div = root.findmeld('content')
            process_groups = root.findmeld('process_groups')
            template_group = process_groups.findmeld('template_group')
            
            # 移除模板组
            template_group.deparent()
            
            # 处理未分组进程（如果有）
            if ungrouped:
                group_div = template_group.clone()
                group_title = group_div.findmeld('group_title')
                group_title.content('独立进程')
                
                # 隐藏组操作按钮 - 添加错误处理
                group_actions = group_div.findmeld('group_actions')
                if group_actions is not None:  # 确保元素存在
                    group_actions.attrib['style'] = 'display: none;'
                
                table = group_div.findmeld('statustable')
                template_row = table.findmeld('tr')
                
                # 移除模板行
                template_row.deparent()
                
                for i, (groupname, processname) in enumerate(ungrouped):
                    self._render_row(table, template_row, i, groupname, processname, rpcinterface)
                
                process_groups.append(group_div)
            
            # 处理每个分组
            for group_name, processes in sorted_groups:
                group_div = template_group.clone()
                group_title = group_div.findmeld('group_title')
                group_title.content('分组: ' + group_name)
                
                # 恢复组操作按钮设置，并添加错误处理
                group_stop = group_div.findmeld('group_stop_anchor')
                if group_stop is not None:
                    group_stop.attributes(href='index.html?action=stopgroup&amp;processname=' + group_name)
                
                group_restart = group_div.findmeld('group_restart_anchor')
                if group_restart is not None:
                    group_restart.attributes(href='index.html?action=restartgroup&amp;processname=' + group_name)
                
                table = group_div.findmeld('statustable')
                template_row = table.findmeld('tr')
                
                # 移除模板行
                template_row.deparent()
                
                for i, (groupname, processname) in enumerate(processes):
                    self._render_row(table, template_row, i, groupname, processname, rpcinterface)
                
                process_groups.append(group_div)

        root.findmeld('supervisor_version').content(VERSION)
        copyright_year = str(datetime.date.today().year)
        root.findmeld('copyright_date').content(copyright_year)

        return as_string(root.write_xhtmlstring())

    def _render_row(self, table, template_row, i, groupname, processname, rpcinterface):
        row = template_row.clone()
        sent_name = make_namespec(groupname, processname)
        info = rpcinterface.supervisor.getProcessInfo(sent_name)
        actions = self.actions_for_process(info)

        status_text = row.findmeld('status_text')
        info_text = row.findmeld('info_text')
        name_anchor = row.findmeld('name_anchor')

        if i % 2:
            row.attrib['class'] = 'shade'
        else:
            row.attrib['class'] = ''
            
        status_text.content(info['statename'])
        status_text.attrib['class'] = self.css_class_for_state(info['state'])
        info_text.content(info['description'])
        name_anchor.attributes(href='tail.html?processname=%s' % urllib.quote(sent_name))
        name_anchor.content(sent_name)

        actionitem_td = row.findmeld('actionitem_td')
        template_action = actionitem_td.findmeld('actionitem')
        
        # 移除模板操作项
        template_action.deparent()
        
        for action in actions:
            action_item = template_action.clone()
            action_anchor = action_item.findmeld('actionitem_anchor')
            action_anchor.attributes(href=action['href'])
            if 'target' in action:
                action_anchor.attributes(target=action['target'])
            action_anchor.content(action['name'])
            actionitem_td.append(action_item)
        
        table.append(row)

    def start_group(self, group_name):
        """启动整个组的所有进程"""
        supervisord = self.context.supervisord
        rpcinterface = SupervisorNamespaceRPCInterface(supervisord)
        
        # 先停止所有进程，然后再启动
        try:
            stop_callback = rpcinterface.stopProcessGroup(group_name)
        except RPCError as e:
            msg = '无法启动组 %s: [%d] %s' % (group_name, e.code, e.text)
            def startgrperr():
                return msg
            startgrperr.delay = 0.05
            return startgrperr
        
        def start_group_cont():
            if stop_callback() is NOT_DONE_YET:
                return NOT_DONE_YET
            
            # 停止完成，现在启动
            try:
                start_callback = rpcinterface.startProcessGroup(group_name)
            except RPCError as e:
                return '组 %s 已停止，但无法重新启动: [%d] %s' % (group_name, e.code, e.text)
            
            def start_group_cont():
                if start_callback() is NOT_DONE_YET:
                    return NOT_DONE_YET
                return '组 %s 的所有进程已重启' % group_name
            
            start_group_cont.delay = 0.05
            return start_group_cont()
        
        start_group_cont.delay = 0.05
        return start_group_cont
    
    def stop_group(self, group_name):
        """停止整个组的所有进程"""
        supervisord = self.context.supervisord
        rpcinterface = SupervisorNamespaceRPCInterface(supervisord)
        
        try:
            callback = rpcinterface.stopProcessGroup(group_name)
        except RPCError as e:
            msg = '无法停止组 %s: [%d] %s' % (group_name, e.code, e.text)
            def stopgrperr():
                return msg
            stopgrperr.delay = 0.05
            return stopgrperr
        
        def stopgroup():
            if callback() is NOT_DONE_YET:
                return NOT_DONE_YET
            return '组 %s 的所有进程已停止' % group_name
        stopgroup.delay = 0.05
        return stopgroup
    
    def restart_group(self, group_name):
        """重启整个组的所有进程"""
        supervisord = self.context.supervisord
        
        # 创建正确的RPC接口
        main = ('supervisor', SupervisorNamespaceRPCInterface(supervisord))
        system = ('system', SystemNamespaceRPCInterface([main]))
        rpcinterface = RootRPCInterface([main, system])
        
        # 使用multicall一次性执行停止和启动操作
        try:
            callback = rpcinterface.system.multicall([
                {'methodName': 'supervisor.stopProcessGroup', 'params': [group_name]},
                {'methodName': 'supervisor.startProcessGroup', 'params': [group_name]}
            ])
        except RPCError as e:
            msg = '无法重启组 %s: [%d] %s' % (group_name, e.code, e.text)
            def restartgrperr():
                return msg
            restartgrperr.delay = 0.05
            return restartgrperr
        
        def restart_result():
            result = callback()
            if result is NOT_DONE_YET:
                return NOT_DONE_YET
            
            # 检查结果
            stop_result, start_result = result
            if isinstance(stop_result, dict) and 'faultString' in stop_result:
                return '组 %s 重启失败: %s' % (group_name, stop_result['faultString'])
            
            if isinstance(start_result, dict) and 'faultString' in start_result:
                return '组 %s 已停止，但无法重新启动: %s' % (group_name, start_result['faultString'])
            
            return '组 %s 的所有进程已重启' % group_name
        
        restart_result.delay = 0.05
        return restart_result

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

