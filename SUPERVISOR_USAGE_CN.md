# Supervisor 使用说明

## 配置文件位置

当前项目使用的配置文件位于：
```
/Users/feiwentao/tianhei_projects/python_projests/supervisor/supervisord.conf
```

## 常用命令

为了更方便地操作 Supervisor，我们创建了一个命令辅助脚本 `supervisor_cmd.sh`。使用此脚本可以避免认证错误和路径问题。

### 基本命令

```bash
# 查看所有进程状态
./supervisor_cmd.sh status

# 启动特定进程
./supervisor_cmd.sh start <进程名>

# 停止特定进程
./supervisor_cmd.sh stop <进程名>

# 重启特定进程
./supervisor_cmd.sh restart <进程名>

# 关闭 Supervisor
./supervisor_cmd.sh shutdown
```

### 组操作命令

```bash
# 启动整个组
./supervisor_cmd.sh start <组名>:*

# 停止整个组
./supervisor_cmd.sh stop <组名>:*

# 重启整个组
./supervisor_cmd.sh restart <组名>:*
```

### 配置管理命令

```bash
# 重新读取配置文件
./supervisor_cmd.sh reread

# 更新配置（应用新的配置）
./supervisor_cmd.sh update

# 显示所有命令帮助
./supervisor_cmd.sh help
```

## 修改配置文件

使用文本编辑器打开配置文件：

```bash
vim supervisord.conf
# 或者
open -a TextEdit supervisord.conf
```

### 配置文件主要部分

1. **HTTP 服务器设置**:
   ```ini
   [inet_http_server]         
   port=0.0.0.0:9001        # 端口设置
   username=admin           # 登录用户名
   password=123456          # 登录密码
   ```

2. **进程配置**:
   ```ini
   [program:程序名称]
   command=要执行的命令        # 必填，程序启动命令
   directory=工作目录         # 程序的工作目录
   autostart=true           # 是否自动启动
   autorestart=true         # 是否自动重启
   redirect_stderr=true     # 是否重定向错误输出
   stdout_logfile=日志路径    # 日志文件位置
   ```

3. **进程组配置**:
   ```ini
   [group:组名]
   programs=程序1,程序2        # 组内的程序列表
   priority=999              # 启动优先级
   ```

### 添加新程序

1. 在配置文件末尾添加新的程序段：
   ```ini
   [program:新程序名]
   command=python /path/to/your/script.py
   directory=/path/to/working/dir
   autostart=true
   autorestart=true
   redirect_stderr=true
   stdout_logfile=./logs/新程序名.log
   environment=变量1="值1",变量2="值2"
   ```

2. 如果要将程序添加到组中，先添加程序配置，然后添加或修改组配置：
   ```ini
   [group:组名]
   programs=现有程序1,现有程序2,新程序名
   priority=999
   ```

### 修改现有程序配置

找到对应的 `[program:xxx]` 部分，修改相应的参数。常用参数包括：

- **command**: 启动命令
- **directory**: 工作目录
- **autostart**: 是否自动启动（true/false）
- **autorestart**: 自动重启（true/false/unexpected）
- **redirect_stderr**: 是否将错误输出重定向到标准输出（true/false）
- **stdout_logfile**: 标准输出日志文件路径
- **environment**: 环境变量设置

## Web 界面

Supervisor 提供了一个 Web 界面来管理您的进程：

- 地址：http://localhost:9001
- 用户名：admin
- 密码：123456 (根据配置文件设置)

通过 Web 界面，您可以：
- 查看所有进程的状态
- 启动/停止/重启单个进程
- 启动/停止/重启整个进程组
- 查看进程日志

## 常见问题解决

### 1. 认证错误
问题：`Server requires authentication: error: 401 Unauthorized`
解决：使用 `./supervisor_cmd.sh` 脚本执行命令，或指定配置文件路径：
```bash
supervisorctl -c $(pwd)/supervisord.conf -u admin -p 123456 status
```

### 2. 无法连接到 Supervisor
问题：`unix:///tmp/supervisor.sock no such file`
解决：确保 Supervisor 已启动，并且 socket 文件路径正确。

### 3. 进程启动后立即退出
问题：进程状态显示为 `FATAL` 或 `BACKOFF`
解决：
- 检查命令是否正确
- 查看进程日志了解详细错误信息
- 确保工作目录正确
- 检查环境变量设置 