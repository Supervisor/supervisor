# Supervisor 安装指南

## 安装方法

### 1. 使用 pip 安装（推荐）

```bash
pip install supervisor
```

### 2. 从源码安装

```bash
# 克隆仓库
git clone https://github.com/你的用户名/supervisor.git
cd supervisor

# 安装
pip install -e .
```

## 基本配置

1. 生成默认配置文件：

```bash
echo_supervisord_conf > supervisord.conf
```

2. 编辑配置文件，根据需要修改：

```bash
# 设置HTTP服务器端口
[inet_http_server]
port=0.0.0.0:9001
username=admin
password=123456

# 添加您的程序
[program:yourapp]
command=/path/to/your/program
```

## 启动 Supervisor

```bash
# 启动 Supervisor
supervisord -c supervisord.conf

# 使用 supervisorctl 控制进程
supervisorctl status
supervisorctl start all
supervisorctl stop all
supervisorctl restart all
```

## Web 界面

安装成功后，访问 http://localhost:9001 即可打开 Supervisor 的 Web 界面。

用户名：admin
密码：123456 (根据您的配置)

## 组操作

本版本支持对进程组进行操作：

- 重启组：点击组名旁边的"重启组"按钮
- 停止组：点击组名旁边的"停止组"按钮

## 日志查看

点击进程名后的"查看日志"按钮，可以查看该进程的日志输出。 