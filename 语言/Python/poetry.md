## poetry

poetry是一个Python虚拟环境和依赖管理的工具，之前用pipenv，最近学习httprunner时，接触了poetry。poetry和pipenv类似，另外还提供了打包和发布的功能。

### 安装

```shell
pip install  poetry

poetry --version
```

### 使用

``` shell

# new demo
poetry new demo_name

# 在已有项目使用poetry
poerty init

# 添加依赖
poetry add fastapi

# 删除依赖
poetry remove fastapi

# 查看poetry的配置
poetry config --list

# 修改config的配置信息
poetry config virtualenvs.create false

# 安装依赖
poetry install
```

### 修改下载源，修改pyproject.toml文件

```
[[tool.poetry.source]]
name = "aliyun"
url = "https://mirrors.aliyun.com/pypi/simple/"
default ="true"
```

ps:<https://python-poetry.org/docs/cli/>
