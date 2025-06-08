#!/bin/bash

# 激活 conda base 环境
export PATH="/Users/$USER/opt/miniconda3/bin:$PATH"
source activate base

# 启动 supervisor
supervisord -c /Users/feiwentao/tianhei_projects/python_projests/supervisor/supervisord.conf

exit 0