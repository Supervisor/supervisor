# Supervisor 打包与发布指南

## 打包过程

### 1. 环境准备

确保安装了必要的打包工具：

```bash
pip install setuptools wheel twine
```

### 2. 修改版本号

1. 编辑 `supervisor/version.txt` 文件，设置正确的版本号
2. 修改配置文件中的端口设置（如需要）

### 3. 构建包

运行打包脚本生成分发包：

```bash
./build_package.sh
```

打包完成后，会在 `dist/` 目录下生成以下文件：
- `supervisor-4.3.0.tar.gz` - 源码分发包
- `supervisor-4.3.0-py2.py3-none-any.whl` - Python wheel 包

### 4. 测试安装包

在测试环境中测试生成的包：

```bash
# 从源码包安装
pip install dist/supervisor-4.3.0.tar.gz

# 或从 wheel 包安装
pip install dist/supervisor-4.3.0-py2.py3-none-any.whl
```

### 5. 上传到 PyPI（可选）

如果你有 PyPI 帐号并想公开发布，可以使用：

```bash
python -m twine upload dist/*
```

## 文档结构

发布版本应包含以下文档：

- `README_CN.md` - 中文项目说明
- `INSTALL_CN.md` - 中文安装指南
- `RELEASE_NOTES_CN.md` - 中文发布说明
- `PACKAGING_GUIDE_CN.md` - 中文打包指南（本文档）

## 本地部署

如果只需要本地部署，可以将打包好的分发包复制到目标机器并安装：

```bash
# 在目标机器上
pip install supervisor-4.3.0.tar.gz
```

## 打包脚本说明

`build_package.sh` 脚本执行以下操作：

1. 清理之前的构建文件
2. 构建源码分发包和 wheel 包
3. 显示生成的包文件列表
4. 提供上传到 PyPI 的命令提示

## 故障排除

如果在打包过程中遇到问题：

1. 检查 Python 版本是否兼容
2. 确认所有依赖已正确安装
3. 检查文件权限和路径是否正确 