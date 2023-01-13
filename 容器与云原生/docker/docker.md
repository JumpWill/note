### 镜像

|             命令              |      释义      |
| :---------------------------: | :------------: |
|     docker search 镜像名      |    搜索镜像    |
|         docker images         | 查看本地的镜像 |
|  docker pull 镜像名:version   | 拉取镜像到本地 |
|   docker rmi 镜像名:version   |    删除镜像    |
| docker rmi -f 镜像名1 镜像名2 |  删除多个镜像  |
| docker export 容器id> 文件名  |    导出容器    |
|                               |                |

### 运行一个容器

```
docker run 镜像名
# 参数 
#  -p 主机端口:容器端口  端口映射
# --name 指定容器名称 
# -d 后台运行
# -v 将宿主机文件挂载到容器中，如果宿主机文件变化会影响容器的对应文件的变化。
# -m 指容器的最大使用内存
# -e username="ritchie": 设置环境变量
docker run --name redis -d -p 6379:6379 redis:lastest 
```

### 容器

|               命令                |        释义        |
| :-------------------------------: | :----------------: |
|        docker stop 容器名         |      停止容器      |
|     docker restart 重启容器名     |      重启容器      |
|         docker rm 容器名          |      删除容器      |
| docker exec -it 容器名  /bin/bash |    进入容器内部    |
|        docker logs 容器名         |    查看容器日志    |
|             docker ps             | 查看正在运行的容器 |
|           docker ps -a            |    查看所有容器    |

### Docker file

|               命令               |     释义     |
| :------------------------------: | :----------: |
| docker build -t 镜像名:version . | 构建一个镜像 |

Dockerfile编写：

|    命令     |                             释义                             |
| :---------: | :----------------------------------------------------------: |
| FROM 镜像名 |                      基于某一个镜像构建                      |
| MAINTAINER  |                          镜像构建者                          |
|     RUN     |                 指定的命令，换行加\多个用&&                  |
|     ENV     |                         设置环境变量                         |
|    COPY     |                    将宿主机文件加到容器中                    |
|   WORKDIR   |                           工作目录                           |
|     CMD     |                运行的命令，如['yum','update']                |
|   VOLUME    |                   将宿主机目录挂载到容器中                   |
|   EXPOSE    |                       容器内应用的端口                       |
| ENTRYPOINT  | docker run时候执行的，且一个dockerfile中有多个，仅最后一个有效 |

举个例子：

```dockerfile
# 1、从官方 Python 基础镜像开始，这是个fastapi的dockerfile
FROM python:3.8-slim

# 2、将当前工作目录设置为 /code
# 这是放置 requirements.txt 文件和应用程序目录的地方
WORKDIR /code
EXPOSE 80
# 设置容器内的时间为东八区
RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai'>/etc/timezone
RUN pip install -U pip
RUN pip config set global.index-url http://mirrors.aliyun.com/pypi/simple
RUN pip config set install.trusted-host mirrors.aliyun.com
COPY ./  /code
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 6、运行服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
# cmd执行多命令
# CMD /bin/bash -c  "command1 && command2"


#举例多个run
RUN set -evx -o pipefail                \
    && apk update                       \
    && apk add --no-cache apache2-utils \
    && rm -rf /var/cache/apk/*          \
    && ab -V |grep Version
```

### Docker Compose

xxx

### 其他

##### 删除所用停止的容器

```shell
docker rm $(docker ps -a -q)

```

##### Dockerfile中配置docker时区

```dockerfile
RUN cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo 'Asia/Shanghai'>/etc/timezone
```

##### Dockerfile中配置Python的pip

```dockerfile
RUN pip install -U pip
RUN pip config set global.index-url http://mirrors.aliyun.com/pypi/simple
RUN pip config set install.trusted-host mirrors.aliyun.com
```

##### Dockerfile配置将dockerfile所在文件夹的文件复制到容器内

```dockerfile
COPY ./  /code
```





