## 为什么需要Poetry

python的pip+虚拟环境能基本解决项目依赖和环境隔离，pip移除模块，pip 就不会进行管理了，而是直接把指定的模块移除，留下一堆依赖。

```shell
# install
curl -sSL https://install.python-poetry.org | python3 -
# add path
echo 'export PATH="~/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 使用

### 初始化项目

```shell
poetry init
# 生成pyproject.toml
```

### 修改源

```shell
poetry source add --priority=default mirrors https://pypi.tuna.tsinghua.edu.cn/simple/

# pyproject.toml里新增
# [[tool.poetry.source]]
# name = "mirrors"
# url = "https://pypi.tuna.tsinghua.edu.cn/simple/"
# priority = "default"

# 一般不需要手动去修改pyproject.toml
# 而是通过命令区修改
```

### 虚拟环境

```shell

# 配置虚拟环境生成在项目文件中
poetry config virtualenvs.in-project true
# 生成虚拟环境 会生成.env文件夹
poetry env use python3
# 进入虚拟环境
poetry shell
```

### 管理包

```shell
# 新增包
poetry add package-name
# 删除
poetry remove package-name
```

### run

```shell
poetry run python3 xxx.py
```

### group

可以定义不同的gruop，例如 test里面需要加pytest，文档的需要加mkdocs

```shell
poetry add  httpx  --group test
```
