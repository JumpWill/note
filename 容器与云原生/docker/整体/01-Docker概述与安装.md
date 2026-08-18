# Docker 概述与安装 (Docker Overview & Installation)

> 本章系统讲解 Docker 的起源、特点、应用场景、与虚拟机对比、各种安装方式与第一个容器。

## 一、Docker 简介

### 1.1 起源

```text
Docker 是 2013 年由 Solomon Hykes 在 dotCloud 公司发布的开源容器引擎
2014 年 Docker 1.0 发布
2015 年 Docker Compose 1.0 发布 (多容器编排)
2016 年 Docker Swarm 1.0 发布 (集群)
2017 年推出企业版 (Docker EE) 与社区版 (Docker CE) 分化
2020 年后逐步整合到 Mirantis, Docker 公司专注开发者体验

历史里程碑:
2013.03  - Docker 开源
2014.06  - Docker 1.0
2015.11  - Docker Compose 1.0
2016.11  - Docker Swarm 1.0
2017.03  - Docker 企业版
2018.01  - Docker CE/EE 分化
2020.11  - Mirantis 收购 Docker Enterprise
```

### 1.2 Docker 是什么

**Docker** 是一个开源的应用容器引擎,基于 Go 语言开发,基于 Linux 内核的 namespace、cgroup、union FS 等技术。

```text
Docker 的核心思想:
1. 标准化 - 一次构建,到处运行
2. 轻量化 - 容器共享内核,秒级启动
3. 隔离性 - namespace + cgroup
4. 高效部署 - 秒级启动,毫秒级停止
```

### 1.3 Docker 三大核心概念

```text
1. 镜像 (Image)
   - 只读模板
   - 类似 ISO 镜像
   - 分层构建 (UnionFS)

2. 容器 (Container)
   - 镜像的运行实例
   - 类比对象与类
   - 轻量、可移植

3. 仓库 (Registry)
   - 镜像存储中心
   - Docker Hub (官方公共)
   - 私有仓库 (Harbor 等)
```

### 1.4 Docker 版本

```text
Docker CE (Community Edition):
  - 免费、社区维护
  - 季度更新 (Edge) / 半年更新 (Stable)

Docker EE (Enterprise Edition):
  - 商业认证、长期支持
  - 现已转给 Mirantis

当前最新版本: 25.0+ (2024)
维护版本: 24.x (LTS)
```

---

## 二、Docker 特点

### 2.1 核心优势

```text
1. 标准化
   - 应用打包标准化 (镜像)
   - 一次构建,处处运行
   - dev/test/prod 一致

2. 轻量化
   - 秒级启动 (vs 虚拟机分钟级)
   - 镜像 MB 级 (vs 虚拟机 GB)
   - 共享内核,资源占用少

3. 隔离性
   - 进程隔离 (namespace)
   - 资源隔离 (cgroup)
   - 文件系统隔离 (chroot/unionfs)

4. 可移植
   - Linux/Windows/Mac 全平台
   - 跨云部署
   - 镜像统一格式

5. 生态丰富
   - Docker Hub 镜像丰富
   - Compose / Swarm / Kubernetes
   - 与 CI/CD 集成 (Jenkins、GitLab)
```

### 2.2 Docker vs 虚拟机

| 维度 | Docker 容器 | 虚拟机 |
|------|------------|--------|
| 启动 | 秒级 | 分钟级 |
| 镜像大小 | MB 级 | GB 级 |
| 性能 | 接近原生 | 虚拟化损耗 5-15% |
| 隔离 | 进程级 (较弱) | 系统级 (强) |
| 资源占用 | 共享内核 | 独占内核 |
| 密度 | 单机 100+ 容器 | 单机 10+ 虚拟机 |
| 启动开销 | 无 | 需要 BIOS、引导 |
| 安全 | 共享内核风险 | 硬件隔离 |

### 2.3 Docker 适用场景

```text
✅ 适合:
- 微服务架构
- CI/CD 流水线
- 开发环境一致性
- 测试环境快速部署
- 云原生应用
- 持续部署
- 微服务架构
- 批处理任务

❌ 不适合:
- 对安全隔离要求极高 (金融核心)
- 高性能计算 (HPC)
- 需要 Windows 内核特性
- 单机性能敏感型应用
```

---

## 三、Docker 架构

### 3.1 Docker 三大组件

```text
┌────────────────────────────────────────┐
│            Docker 架构                  │
│                                         │
│  ┌─────────┐  ┌─────────┐  ┌────────┐│
│  │  Docker │  │  REST   │  │Docker  ││
│  │   CLI   │  │   API   │  │ Daemon ││
│  └────┬────┘  └────┬────┘  └───┬────┘│
│       │              │            │     │
│       └──────────────┴────────────┘     │
│                      │                   │
│                      ↓                   │
│  ┌─────────────────────────────────┐    │
│  │      containerd (容器运行时)        │    │
│  │      runc (OCI 参考实现)          │    │
│  └─────────────────────────────────┘    │
└────────────────────────────────────────┘
```

### 3.2 Docker Daemon (dockerd)

```text
Docker Daemon (dockerd):
- 后台核心进程
- 监听 REST API
- 管理镜像、容器、网络、卷
- 与 containerd 通信
- 默认监听 unix:///var/run/docker.sock
```

### 3.3 Docker 客户端

```text
docker CLI:
- 与 daemon 通过 REST API 通信
- 也可通过 TCP 远程连接

# 客户端配置
docker -H tcp://192.168.1.10:2375 ps
```

---

## 四、安装 Docker

### 4.1 Linux 安装 (Ubuntu/Debian)

```bash
# 1. 卸载旧版本
sudo apt-get remove docker docker-engine docker.io containerd runc

# 2. 更新包索引
sudo apt-get update

# 3. 安装依赖
sudo apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  lsb-release

# 4. 添加 Docker 官方 GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 5. 设置仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 6. 安装 Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 7. 验证
sudo docker run hello-world
```

### 4.2 Linux 安装 (CentOS/RHEL)

```bash
# 1. 卸载旧版本
sudo yum remove docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine

# 2. 安装依赖
sudo yum install -y yum-utils

# 3. 添加仓库
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 4. 安装
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. 启动并设置开机启动
sudo systemctl start docker
sudo systemctl enable docker

# 6. 验证
sudo docker run hello-world
```

### 4.3 macOS 安装

```bash
# 方式 1: Docker Desktop (推荐)
# 下载安装: https://www.docker.com/products/docker-desktop
# 包含 Docker Engine + Compose + Kubernetes

# 方式 2: OrbStack (轻量替代)
brew install orbstack

# 方式 3: Colima (命令行)
brew install colima
colima start
```

### 4.4 Windows 安装

```text
推荐: Docker Desktop
下载: https://www.docker.com/products/docker-desktop

要求:
- Windows 10/11 64-bit
- WSL 2 (推荐) 或 Hyper-V
- 启用虚拟化 (BIOS)
```

### 4.5 配置免 sudo

```bash
# 1. 创建 docker 用户组 (一般已存在)
sudo groupadd docker

# 2. 添加当前用户到 docker 组
sudo usermod -aG docker $USER

# 3. 刷新组 (或重新登录)
newgrp docker

# 4. 验证 (无需 sudo)
docker run hello-world
```

### 4.6 配置镜像加速器

```bash
# 国内常用镜像加速器
# /etc/docker/daemon.json
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
EOF

sudo systemctl restart docker
```

---

## 五、第一个容器

### 5.1 Hello World

```bash
# 运行 hello-world 镜像
docker run hello-world

# 输出:
# Unable to find image 'hello-world:latest' locally
# latest: Pulling from library/hello-world
# Status: Downloaded newer image for hello-world:latest
#
# Hello from Docker!
# This message shows that your installation appears to be working correctly.
```

### 5.2 交互式容器

```bash
# 运行 Ubuntu 容器并进入 bash
docker run -it --rm ubuntu:latest bash

# 容器内
# root@<container-id>:/# ls /
# bin  boot  dev  etc  home  lib  media  mnt  opt  proc  root  run  sbin  srv  sys  tmp  usr  var
# root@<container-id>:/# exit
```

参数说明:
- `-i` - interactive (保持 STDIN 打开)
- `-t` - tty (分配伪终端)
- `--rm` - 容器退出后自动删除
- `ubuntu:latest` - 镜像名:标签
- `bash` - 容器启动命令

### 5.3 后台运行容器

```bash
# 启动 nginx 后台运行
docker run -d --name my-nginx -p 8080:80 nginx:alpine

# -d: detached (后台)
# --name: 容器名
# -p: 端口映射 (host:container)

# 查看运行中的容器
docker ps

# 查看日志
docker logs my-nginx

# 进入容器
docker exec -it my-nginx sh

# 停止
docker stop my-nginx

# 删除
docker rm my-nginx
```

---

## 六、Docker 基本命令速查

### 6.1 镜像命令

```bash
docker search <keyword>           # 搜索镜像
docker pull <image>:<tag>       # 拉取镜像
docker images                   # 列出本地镜像
docker rmi <image>              # 删除镜像
docker tag <src> <dst>          # 打标签
docker image ls                 # 等同 docker images
docker image prune              # 清理未用镜像
docker save -o file.tar <image>  # 导出镜像
docker load -i file.tar         # 导入镜像
docker history <image>          # 查看镜像层历史
docker inspect <image>          # 查看镜像详情
```

### 6.2 容器命令

```bash
docker run [options] <image> [command]  # 创建并启动
docker ps                          # 列出运行中
docker ps -a                       # 列出所有 (含已停止)
docker start <container>           # 启动已停止
docker stop <container>            # 优雅停止
docker kill <container>            # 强制停止 (SIGKILL)
docker restart <container>
docker pause <container>           # 暂停
docker unpause <container>         # 恢复
docker rm <container>              # 删除
docker logs <container>            # 查看日志
docker logs -f <container>         # 跟踪日志
docker exec -it <container> bash   # 进入容器
docker exec <container> <cmd>     # 执行命令
docker cp <container>:/path ./local  # 复制文件
docker top <container>             # 查看进程
docker stats                       # 资源使用
docker inspect <container>         # 查看详情
```

### 6.3 网络命令

```bash
docker network ls                  # 列出网络
docker network create <name>       # 创建网络
docker network rm <name>           # 删除网络
docker network inspect <name>      # 查看详情
docker network connect <net> <container>  # 连接容器
```

### 6.4 卷命令

```bash
docker volume ls                  # 列出卷
docker volume create <name>       # 创建卷
docker volume rm <name>           # 删除卷
docker volume inspect <name>      # 查看详情
docker volume prune               # 清理未用卷
```

### 6.5 系统命令

```bash
docker system df                  # 查看磁盘使用
docker system prune               # 清理所有未用资源
docker system info                # 显示系统信息
docker system events              # 实时事件
docker version                    # 版本信息
```

---

## 七、Docker 配置详解

### 7.1 配置文件位置

```text
Linux:
  /etc/docker/daemon.json      # Docker daemon 配置

Windows:
  %ProgramData%\docker\config\daemon.json

macOS (Docker Desktop):
  ~/Library/Group Containers/group.com.docker/settings.json
```

### 7.2 daemon.json 完整配置

```json
{
  "registry-mirrors": ["https://mirror.example.com"],
  "insecure-registries": ["registry.local:5000"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "data-root": "/var/lib/docker",
  "exec-opts": ["native.cgroupdriver=cgroupfs"],
  "bip": "172.17.0.1/16",
  "mtu": 1500,
  "default-runtime": "runc",
  "features": {
    "buildkit": true
  },
  "experimental": false,
  "debug": false,
  "live-restore": true
}
```

---

## 核心要点速记

### Docker 三大概念

```text
镜像 (Image)   - 只读模板,分层构建
容器 (Container) - 镜像的运行实例
仓库 (Registry) - 镜像存储中心 (Docker Hub)
```

### Docker vs 虚拟机

```text
Docker:  秒级启动、MB 镜像、进程隔离、共享内核、密度高
虚拟机: 分钟级启动、GB 镜像、系统隔离、独占内核、密度低
```

### 安装方式

```text
- Linux: apt/yum + docker-ce
- macOS: Docker Desktop / OrbStack / Colima
- Windows: Docker Desktop
- 生产: 容器化部署 (k3s 等)
```

### 必会命令

```bash
docker run -d -p 8080:80 --name web nginx     # 启动
docker ps                                    # 查看运行中
docker logs -f web                           # 查看日志
docker exec -it web bash                     # 进入容器
docker stop web && docker rm web            # 停止并删除
docker images                                # 查看镜像
docker pull nginx:1.25                      # 拉取镜像
```

### 第一个容器

```bash
docker run -d --name my-nginx -p 8080:80 nginx:alpine
curl http://localhost:8080
```

### 核心特点

```text
✅ 标准化 - 一次构建,处处运行
✅ 轻量 - 秒级启动,MB 镜像
✅ 隔离 - namespace + cgroup
✅ 生态 - Hub/Compose/Swarm/K8s
```

---

## 参考

- **Docker 官方文档**: https://docs.docker.com/
- **Docker Hub**: https://hub.docker.com/
- **Docker 安装**: https://docs.docker.com/engine/install/
- **Docker 命令参考**: https://docs.docker.com/engine/reference/run/
- **Dockerfile 参考**: https://docs.docker.com/engine/reference/builder/
