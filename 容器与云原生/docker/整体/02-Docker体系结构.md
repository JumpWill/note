# Docker 体系结构与核心组件 (Docker Architecture)

> 本章深入讲解 Docker 整体架构、daemon 与 client 通信、容器运行时 (containerd/runc)、Linux 内核机制 (namespace/cgroup/UnionFS)。

## 一、Docker 整体架构

### 1.1 分层架构

```text
┌────────────────────────────────────────────────────┐
│                   Docker 架构                        │
│                                                     │
│  ┌─────────────────────────────────────────────┐ │
│  │           Docker CLI (docker 命令)            │ │
│  └─────────────┬───────────────────────────────┘ │
│                │ REST API (Unix Socket / TCP)       │
│  ┌─────────────▼───────────────────────────────┐ │
│  │           Docker Daemon (dockerd)            │ │
│  │   - 镜像管理                                 │ │
│  │   - 容器生命周期                              │ │
│  │   - 网络管理                                  │ │
│  │   - 卷管理                                    │ │
│  └─────────────┬───────────────────────────────┘ │
│                │ gRPC                                │
│  ┌─────────────▼───────────────────────────────┐ │
│  │      containerd (容器运行时)                  │ │
│  │   - 镜像管理 (快照)                          │ │
│  │   - 容器执行                                  │ │
│  └─────────────┬───────────────────────────────┘ │
│                │ OCI Runtime Spec                   │
│  ┌─────────────▼───────────────────────────────┐ │
│  │         runc (OCI 参考实现)                  │ │
│  │   - 创建容器                                  │ │
│  │   - 配置 namespace/cgroup                    │ │
│  │   - 启动容器进程                              │ │
│  └─────────────┬───────────────────────────────┘ │
│                │ syscall                            │
│  ┌─────────────▼───────────────────────────────┐ │
│  │        Linux Kernel                          │ │
│  │   - namespace (隔离)                         │ │
│  │   - cgroup (资源)                            │ │
│  │   - UnionFS (文件系统)                       │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 1.2 Docker vs OCI 标准

```text
OCI (Open Container Initiative):
- OCI Runtime Spec    - 容器运行时规范 (runc 实现)
- OCI Image Spec       - 镜像格式规范
- OCI Distribution Spec - 镜像分发规范

关系:
- Docker 主导制定 OCI 标准
- Docker 镜像兼容 OCI 镜像
- runc 是 OCI 参考实现
- Docker 贡献 containerd (CNCF)
```

---

## 二、Docker Daemon

### 2.1 daemon 职责

```text
dockerd 是 Docker 守护进程,核心职责:
1. 镜像管理 (拉取、构建、删除)
2. 容器生命周期 (创建、启动、停止)
3. 网络管理 (bridge、host、overlay)
4. 卷管理 (volume、bind mount)
5. API 服务 (REST API, 默认 2375/2376)
6. 与 containerd 通信 (gRPC)
```

### 2.2 daemon 配置

```bash
# /etc/docker/daemon.json
{
  "registry-mirrors": ["https://mirror.example.com"],
  "data-root": "/var/lib/docker",
  "exec-opts": ["native.cgroupdriver=cgroupfs"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true,
  "features": {
    "buildkit": true
  },
  "default-address-pools": [
    {"base": "172.30.0.0/16", "size": 24}
  ]
}
```

### 2.3 daemon 操作

```bash
# 查看 daemon 状态
sudo systemctl status docker

# 启动/停止/重启
sudo systemctl start docker
sudo systemctl stop docker
sudo systemctl restart docker

# 重新加载配置
sudo systemctl reload docker

# daemon 日志
sudo journalctl -u docker.service -f

# 查看 docker 系统信息
docker info

# 远程访问 daemon
docker -H tcp://0.0.0.0:2375 ps
```

---

## 三、containerd 与 runc

### 3.1 containerd

```text
containerd 是 CNCF 毕业项目,工业级容器运行时

功能:
- 镜像管理 (拉取、推送、快照)
- 容器生命周期
- 存储管理
- 网络管理 (CNI)
- gRPC API 给 Docker daemon / K8s kubelet

架构:
- containerd (主进程)
  - shim (管理容器生命周期)
  - runc (OCI 参考实现)

docker → containerd → runc → 容器
       (shim 负责单容器生命周期)
```

### 3.2 runc

```text
runc 是 OCI Runtime 参考实现 (Go)

功能:
- 创建容器 (clone/fork)
- 配置 namespace (Mount/PID/Network/...)
- 设置 cgroup
- 启动容器进程

工作流程:
1. Docker daemon 收到 docker run 命令
2. dockerd → containerd (gRPC)
3. containerd → runc (OCI Runtime Spec)
4. runc:
   a. 创建 OCI Bundle (config.json + rootfs)
   b. clone() 创建子进程
   c. 子进程调用 pivot_root 切换 rootfs
   d. 配置 namespace
   e. exec() 启动用户命令
```

### 3.3 docker/containerd/runc 关系

```text
┌─────────────────────────────────────────┐
│        Docker 客户端 (CLI)              │
└─────────────┬───────────────────────────┘
              │ HTTP/REST
┌─────────────▼───────────────────────────┐
│        Docker Daemon (dockerd)          │
│  - 处理用户请求                          │
│  - 镜像管理 (与 registry 通信)            │
│  - 与 containerd 通信 (gRPC)             │
└─────────────┬───────────────────────────┘
              │ gRPC
┌─────────────▼───────────────────────────┐
│            containerd                   │
│  - 接收 dockerd 指令                    │
│  - 管理镜像快照                          │
│  - 管理容器进程 (shim)                  │
│  - 调用 runc                             │
└─────────────┬───────────────────────────┘
              │ OCI Runtime Spec
┌─────────────▼───────────────────────────┐
│              runc                       │
│  - 创建容器                              │
│  - 调用 Linux 内核 (namespace/cgroup)   │
│  - 启动容器进程                          │
└─────────────────────────────────────────┘
```

---

## 四、Linux 内核机制

### 4.1 Namespace (资源隔离)

```text
Namespace 是 Linux 内核提供的资源隔离机制
Docker 用 namespace 实现容器间的隔离

6 种 namespace (Docker 使用):
1. PID namespace    - 进程 ID 隔离
2. Network namespace - 网络隔离 (网卡、IP、路由)
3. Mount namespace   - 挂载点隔离 (文件系统)
4. UTS namespace     - 主机名/域名隔离
5. IPC namespace     - 进程间通信隔离
6. User namespace    - 用户 ID 隔离 (Docker 1.10+)

User namespace (K8s 1.25+):
- 容器 root 映射到宿主普通用户
- 增强安全性
```

```bash
# 查看进程的 namespace
ls -la /proc/<pid>/ns/

# 进入进程的 namespace
nsenter -t <pid> -n bash    # 进入网络 namespace
nsenter -t <pid> -p bash    # 进入 PID namespace
```

### 4.2 cgroup (资源限制)

```text
cgroup (Control Groups) 是 Linux 内核的资源限制机制
Docker 用 cgroup 限制容器的 CPU、内存、磁盘 IO、网络

两种版本:
- cgroup v1 - 传统
- cgroup v2 - 统一层级,新一代

cgroup v1 子系统:
- cpu      - CPU 限制
- memory   - 内存限制
- blkio    - 块设备 IO
- net_cls  - 网络分类
- pids     - 进程数限制
- freezer - 冻结/恢复

cgroup v2 统一:
- 单一层级
- 统一资源管理
```

```bash
# 查看 cgroup
cat /proc/<pid>/cgroup

# 查看内存限制
cat /sys/fs/cgroup/memory/docker/<container-id>/memory.limit_in_bytes

# 设置 Docker daemon 使用 cgroup v2
# /etc/docker/daemon.json
{
  "exec-opts": ["native.cgroupdriver=cgroupfs"]
}
# 或 systemd cgroup driver
{
  "exec-opts": ["native.cgroupdriver=systemd"]
}
```

### 4.3 UnionFS (联合文件系统)

```text
UnionFS 是 Docker 镜像分层的基础

Docker 支持的存储驱动:
- overlay2 (推荐,Linux 4.x+)
- btrfs
- zfs
- devicemapper (CentOS/RHEL)
- vfs (低性能,不推荐)

overlay2 工作原理:
┌─────────────────┐
│   Upper (读写)   │  ← 容器运行时修改
├─────────────────┤
│   Lower (只读)   │  ← 镜像层(只读)
└─────────────────┘

每个 Docker 镜像 = 多个只读层
每个容器 = 一个可写 Upper 层 + 镜像层
```

```bash
# 查看存储驱动
docker info | grep Storage

# 修改存储驱动
# /etc/docker/daemon.json
{
  "storage-driver": "overlay2"
}
sudo systemctl restart docker
```

### 4.4 capabilities (Linux 权限)

```text
传统 Unix: root 用户权限过大
Linux capabilities: 把 root 权限拆分成 40+ 个细粒度权限

Docker 默认:
- 保留: CAP_CHOWN, CAP_DAC_OVERRIDE, CAP_FSETID, CAP_FOWNER,
        CAP_MKNOD, CAP_NET_RAW, CAP_SETGID, CAP_SETUID,
        CAP_SETFCAP, CAP_SETPCAP, CAP_NET_BIND_SERVICE,
        CAP_SYS_CHROOT, CAP_KILL, CAP_AUDIT_WRITE
- 移除: SYS_ADMIN, SYS_MODULE, SYS_RAWIO 等危险权限

# 添加 capability
docker run --cap-add=NET_ADMIN ubuntu

# 移除 capability
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE nginx

# 特权模式 (几乎所有权限)
docker run --privileged ubuntu   # ⚠️ 不推荐
```

---

## 五、Docker 镜像架构

### 5.1 镜像分层

```text
Docker 镜像 = 一系列只读层 (UnionFS)

例: nginx:1.25 镜像
┌─────────────────┐  Layer 7 (CMD)
├─────────────────┤  Layer 6 (EXPOSE)
├─────────────────┤  Layer 5 (COPY)
├─────────────────┤  Layer 4 (RUN apt install)
├─────────────────┤  Layer 3 (COPY config)
├─────────────────┤  Layer 2 (RUN yum install nginx)
├─────────────────┤  Layer 1 (FROM centos:7)
└─────────────────┘  基础镜像层

特点:
- 每层都是只读
- 上层覆盖下层 (CoW)
- 镜像共享,节省存储
```

### 5.2 镜像构建

```dockerfile
# Dockerfile
FROM ubuntu:22.04              # 基础层

RUN apt-get update             # 第 2 层
RUN apt-get install -y nginx   # 第 3 层

COPY index.html /var/www/      # 第 4 层
COPY nginx.conf /etc/nginx/    # 第 5 层

EXPOSE 80                      # 元数据,不占层
CMD ["nginx", "-g", "daemon off;"]   # 元数据
```

```bash
# 构建镜像
docker build -t my-nginx:1.0 .

# 查看镜像分层
docker history my-nginx:1.0
# 层级从下往上叠加
```

### 5.3 镜像存储

```text
镜像内容:
- manifest.json      - 镜像清单 (层信息)
- config.json        - 容器配置
- <layer-digest>/    - 镜像层 (tar + json)

存储位置:
- /var/lib/docker/overlay2/
  ├── <layer-id>/   - 镜像层 (只读)
  └── <container-id>/
      ├── diff/      - 容器可写层
      └── merged/    - 联合挂载点

示例:
/var/lib/docker/overlay2/
├── abc123.../diff/         # 镜像层 (共享)
├── def456.../diff/         # 容器层 (独有)
└── ghi789.../merged/       # 容器运行时挂载点
```

---

## 六、Docker 网络架构

### 6.1 容器网络接口 (CNI)

```text
Docker 用 libnetwork + CNI 实现网络:

Docker 网络驱动:
- bridge    - 默认 (NAT)
- host      - 共享宿主网络
- overlay   - Swarm 集群
- macvlan   - 物理网卡虚拟
- ipvlan    - 类似 macvlan
- none      - 无网络

第三方驱动 (CNI 插件):
- calico
- flannel
- weave
- cilium
```

### 6.2 Bridge 网络详解

```text
默认 Bridge 网络 (docker0):
- 网桥: 172.17.0.1/16
- 容器 IP: 172.17.0.x
- 容器间可通过 IP 互通
- 容器到外网通过 NAT

用户自定义 Bridge (推荐):
- 容器间可通过 name 互通 (Docker DNS)
- 默认在 172.18.0.0/16 段
- 容器名解析: <container-name>.<network-name>

示例:
docker network create my-net
docker run -d --name web --network my-net nginx
docker run -d --name api --network my-net my-api
# 在 api 容器内:
curl http://web/    # Docker DNS 自动解析
```

### 6.3 网络命名空间

```text
每个 Docker 容器有自己的网络命名空间:

容器内网络栈:
- lo (127.0.0.1)
- eth0 (veth pair 一端, 连接到网桥)
- 网关: 172.17.0.1 (docker0)

veth pair:
- 一端在容器内 (eth0)
- 另一端在宿主 (vethXXX)
- 连接到 docker0 网桥
```

---

## 七、Docker 数据卷架构

### 7.1 卷 vs bind mount vs tmpfs

```text
三种数据持久化方式:

1. Volume (卷) - Docker 管理
   - /var/lib/docker/volumes/
   - 推荐方式
   - 支持跨平台

2. Bind Mount - 挂载宿主目录
   - 任意宿主目录
   - 开发调试用

3. tmpfs - 内存文件系统
   - 容器停止数据丢失
   - 敏感数据 (密码)
```

### 7.2 Volume 工作原理

```text
docker volume create mydata
# 创建在 /var/lib/docker/volumes/mydata/_data

docker run -v mydata:/data ubuntu
# 容器内 /data → /var/lib/docker/volumes/mydata/_data

特点:
- 由 Docker 管理
- 跨主机迁移方便 (volume drivers)
- 推荐生产使用
```

---

## 八、Docker 启动容器完整流程

### 8.1 时序图

```text
用户: docker run -d nginx
   ↓
Docker CLI: 解析参数,调用 REST API
   ↓
Docker Daemon: 接收 POST /containers/create
   ↓
1. 验证参数
2. 检查镜像是否存在
   ↓ 不存在则 pull (通过 registry)
3. 创建 OCI Bundle
   ↓
4. 调用 containerd (gRPC)
   ↓
5. containerd 创建 snapshot (overlay2)
   ↓
6. containerd 调用 runc (OCI Runtime Spec)
   ↓
7. runc:
   a. 创建 runtime spec (config.json)
   b. 准备 rootfs
   c. clone() 创建子进程 (容器进程)
   d. 子进程:
      - 创建各种 namespace (Mount/PID/Network/...)
      - 配置 cgroup
      - pivot_root 切换文件系统
      - 启动用户命令 (nginx)
8. 容器进程启动
   ↓
9. runc 退出, containerd shim 继续管理容器
   ↓
10. Docker daemon 接收运行状态
   ↓
11. CLI 返回 container-id
```

### 8.2 容器进程关系

```text
容器进程模型 (重要):

dockerd (PID 1)
├── containerd (PID x)
│   └── containerd-shim-<container-id> (PID y)  ← 容器代理
│       └── nginx (PID z)  ← 容器实际进程
```

```bash
# 查看进程关系
ps -ef --forest | grep -A 2 dockerd

# 关键点:
# - containerd-shim 是每个容器的"中间人"
# - shim 负责容器进程生命周期
# - 即使 dockerd 重启,容器仍可继续运行 (live-restore)
```

---

## 九、Docker 安全架构

### 9.1 多层安全防护

```text
Docker 安全层次:

1. Namespace 隔离     - 进程、网络、文件系统
2. Cgroup 资源限制    - CPU/内存/IO
3. Capability 限制    - 细粒度权限
4. Seccomp 系统调用过滤 - 限制危险系统调用
5. AppArmor / SELinux - MAC 访问控制
6. 用户命名空间        - 容器内 root 映射到普通用户

应用层:
- 镜像扫描 (Trivy)
- 镜像签名 (Cosign)
- 密钥管理 (Vault / External Secrets)
```

### 9.2 Docker Content Trust (DCT)

```text
Docker Content Trust:
- 使用 Notary 签名镜像
- 确保镜像未被篡改

启用:
export DOCKER_CONTENT_TRUST=1
docker pull nginx:1.25
# 验证签名,失败则拒绝

签名镜像:
docker trust sign myregistry/myapp:1.0
```

---

## 十、Docker 实战命令

### 10.1 调试容器

```bash
# 1. 查看容器进程
docker top <container>

# 2. 查看资源使用
docker stats
docker stats <container>

# 3. 查看容器详情
docker inspect <container>

# 4. 查看容器日志
docker logs -f <container>
docker logs --tail 100 <container>

# 5. 进入容器
docker exec -it <container> bash
docker exec -u root -it <container> bash

# 6. 从容器复制文件
docker cp <container>:/path ./local

# 7. 查看容器资源限制
docker inspect <container> | grep -A 5 Resources
```

### 10.2 性能分析

```bash
# 容器资源使用
docker stats --no-stream

# 容器进程详情
docker top <container>

# 容器文件系统占用
docker system df
docker system df -v

# 容器日志大小
docker inspect <container> | grep LogPath

# 镜像层大小分析
docker history <image> --no-trunc
```

---

## 核心要点速记

### Docker 架构

```text
Docker CLI → Docker Daemon (dockerd)
              ↓ gRPC
              containerd
              ↓ OCI Runtime Spec
              runc
              ↓
              Linux Kernel (namespace/cgroup/UnionFS)
```

### Docker vs OCI

```text
OCI = 开放容器倡议
- OCI Runtime Spec (runc 实现)
- OCI Image Spec
- OCI Distribution Spec

Docker 兼容 OCI 标准
Docker 镜像 = OCI 镜像
```

### Linux 内核三大机制

```text
Namespace: 资源隔离 (进程、网络、文件系统)
cgroup:   资源限制 (CPU、内存、IO)
UnionFS:  分层镜像 (overlay2 推荐)
```

### Docker vs 虚拟机

```text
Docker: 容器共享内核,MB 级,秒级启动
虚拟机: 独占内核,GB 级,分钟级启动
```

### containerd vs dockerd vs runc

```text
dockerd:    Docker 主进程,管理镜像/容器/网络/卷
containerd: 容器运行时,管理容器生命周期
runc:       OCI 参考实现,创建容器进程
```

### 容器进程关系

```text
dockerd
└── containerd
    └── containerd-shim-<id>
        └── <用户进程>
```

### Docker 镜像分层

```text
镜像 = 多个只读层 + 配置
容器 = 镜像层 + 可写层 (Copy-on-Write)
共享底层 → 节省存储
```

---

## 参考

- **Docker 架构**: https://docs.docker.com/get-started/overview/
- **containerd**: https://containerd.io/
- **OCI 标准**: https://opencontainers.org/
- **Docker 源码**: https://github.com/moby/moby
- **runc**: https://github.com/opencontainers/runc
- **Linux Namespace**: https://man7.org/linux/man-pages/man7/namespaces.7.html
