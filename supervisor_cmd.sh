#!/bin/bash
# Supervisor 命令辅助脚本

# 如果没有提供参数，则显示帮助
if [ $# -eq 0 ]; then
  echo "Supervisor 命令辅助脚本"
  echo "用法: $0 <命令>"
  echo ""
  echo "常用命令:"
  echo "  status         - 查看所有进程状态"
  echo "  start <name>   - 启动进程"
  echo "  stop <name>    - 停止进程"
  echo "  restart <name> - 重启进程"
  echo "  shutdown       - 关闭 Supervisor"
  echo "  reread         - 重新读取配置"
  echo "  update         - 更新配置"
  echo "  help           - 显示更多命令"
  exit 1
fi

# 使用配置文件路径运行 supervisorctl
supervisorctl -c $(pwd)/supervisord.conf "$@" 