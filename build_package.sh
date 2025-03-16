#!/bin/bash
# 打包和发布Supervisor
set -e

# 清理之前的构建
echo "清理之前的构建..."
rm -rf build/ dist/ *.egg-info/

# 构建源码包和wheel包
echo "构建源码包和wheel包..."
python setup.py sdist bdist_wheel

echo "构建完成!"
echo "生成的包在dist/目录下"
ls -la dist/

echo ""
echo "如需上传到PyPI，请运行:"
echo "python -m twine upload dist/*" 