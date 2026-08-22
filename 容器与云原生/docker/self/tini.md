# tini 在 Docker 中的作用详解 (Tini in Docker)

> 本文档系统讲解 tini 是什么、为什么 Docker 需要 tini、tini 的工作原理以及如何使用。

## 一、Tini 是什么

### 1.1 简介

**Tini** (Tiny Init) 是 [Kubernetes](https://github.com/krallin/tini) 项目维护的一个**轻量级 init 系统**,专门为容器环境设计。

```text
Tini 的核心特点:
  - 二进制体积: ~30KB (极小)
  - 内存占用: 几乎为零
  - 依赖: 零依赖 (静态链接)
  - 功能: 僵尸进程回收 + 信号转发
  - 用途: 容器 PID 1 进程
```

### 1.2 项目背景

```text
- 项目地址: https://github.com/krallin/tini
- 维护方: Kubernetes SIG (后由独立维护)
- 起源: 解决 Docker 容器中 PID 1 问题
- 语言: C
- 集成: Docker 内置 (Docker 1.13+)
```

---

## 二、为什么 Docker 需要 tini

### 2.1 PID 1 的问题

```text
Linux 中 PID 1 的特殊性:

1. 不会响应普通信号
   - 默认忽略 SIGTERM/SIGINT 等
   - 只有少数信号 (SIGKILL) 能终止

2. 负责收养孤儿进程
   - 当父进程退出,子进程被 init 收养
   - 孤儿进程由 PID 1 回收

3. 容器中的 PID 1
   - 容器的 ENTRYPOINT 进程就是 PID 1
   - 继承了 init 的特殊地位
```

### 2.2 没有 tini 会发生什么

```text
问题 1: 僵尸进程 (Zombie)
  ┌────────────────────────────────────────┐
  │  容器主进程 (PID 1 = shell script)         │
  │  ├─ App (子进程)                         │
  │  │  └─ 启动子子进程                       │
  │  └─ ...                                  │
  │                                          │
  │  App 退出后, 它的子进程没被回收           │
  │  变成孤儿进程或僵尸进程                   │
  │  占用进程表 slot, 最终系统卡死             │
  └────────────────────────────────────────┘

问题 2: 信号不传递
  ┌────────────────────────────────────────┐
  │  Docker 发送 SIGTERM 给 PID 1            │
  │  PID 1 是 shell script                    │
  │  shell script 不会将信号转发给 App!      │
  │  App 收不到 SIGTERM, 无法优雅关闭        │
  │                                          │
  │  后果: docker stop 卡住 10 秒             │
  │         然后强制 SIGKILL 杀死            │
  │  (数据可能丢失)                           │
  └────────────────────────────────────────┘

问题 3: 资源清理
  - 没有 init 帮忙清理临时文件
  - 内存泄漏难发现
  - 文件句柄未关闭
```

### 2.3 示例: 没有 tini 的场景

```dockerfile
# 不使用 tini 的 Dockerfile
FROM node:18-alpine
COPY app.js .
CMD ["node", "app.js"]
```

```text
docker run --name myapp myimage
# PID 1 = node 进程

docker exec myapp sh -c "ps aux"
# PID   USER  COMMAND
# 1     root  node app.js  ← PID 1
# 10    root  /bin/sh     ← exec 进入的进程

docker stop myapp
# Docker 发送 SIGTERM 到 PID 1 (node)
# node 进程不主动捕获 SIGTERM?
# → 等待 10 秒, 然后 SIGKILL
# → 进程没机会清理资源
```

---

## 三、Tini 的工作原理

### 3.1 Tini 的核心功能

```text
Tini 作为 PID 1 运行时, 提供三大功能:

1. 僵尸进程回收
   - 自动 wait() 子进程
   - 回收退出的子进程资源

2. 信号转发
   - 接收 SIGTERM, 转发给子进程
   - 接收 SIGINT, 转发给子进程
   - 接收其他信号, 透传

3. PID 1 接管
   - 作为容器内第一个进程
   - 收养孤儿进程
   - 处理僵尸进程
```

### 3.2 Tini 工作流程

```text
容器启动流程 (使用 tini):

  Docker daemon
       │
       ├── 启动 tini (PID 1)
       │    │
       │    ├── fork() shell 脚本
       │    │    │
       │    │    ├── exec node app.js (替换 shell)
       │    │    │
       │    │    │   业务进程运行中
       │    │    │
       │    ├── wait() 监控子进程
       │    │    │
       │    │    └── 当子进程退出, 回收资源
       │    │
       │    └── 处理信号:
       │         SIGTERM  → 转发给子进程
       │         SIGINT   → 转发给子进程
       │         SIGKILL  → 强制终止子进程
       │
       └── Docker stop 时:
            发送 SIGTERM
              ↓
            tini 收到 SIGTERM
              ↓
            转发给子进程 (node)
              ↓
            node 收到 SIGTERM, 优雅关闭
              ↓
            tini wait() 收到子进程退出
              ↓
            tini 也退出
              ↓
            Docker 检测到 PID 1 退出
              ↓
            容器停止
```

### 3.3 Tini vs 没有 Tini 对比

```text
场景: 容器内有 shell 脚本 + Java 进程

没有 tini:
  ┌──────────────────────────────────┐
  │  PID 1: /bin/sh /start.sh        │
  │  ├─ Java (后台进程)              │
  │  └─ ...                          │
  │                                  │
  │  docker stop:                    │
  │  → SIGTERM 给 PID 1 (sh)        │
  │  → sh 收到 SIGTERM, 默认行为?    │
  │  → sh 退出, 但子进程变孤儿      │
  │  → 等待 10 秒, SIGKILL          │
  │  → 容器内残留孤儿进程被 OOM Kill│
  └──────────────────────────────────┘

有 tini:
  ┌──────────────────────────────────┐
  │  PID 1: tini                     │
  │  ├─ exec /start.sh               │
  │  │   └─ sh 启动 Java             │
  │  └─ tini wait() 监控所有子进程  │
  │                                  │
  │  docker stop:                    │
  │  → SIGTERM 给 tini              │
  │  → tini 转发给 sh                │
  │  → sh 退出, Java 变孤儿?        │
  │  → tini 收养 Java, 等待它退出   │
  │  → Java 退出                      │
  │  → tini wait() 回收              │
  │  → tini 干净退出                  │
  └──────────────────────────────────┘
```

---

## 四、Docker 中 tini 的集成方式

### 4.1 Docker 内置 tini (推荐)

```bash
# Docker 1.13+ 内置 tini, 自动作为 PID 1
# 默认行为: ENTRYPOINT 进程作为 PID 1

# 但 Docker 提供了 --init 参数来使用 tini
docker run --init myimage

# 此时容器内:
# PID 1 = tini
# PID 2+ = ENTRYPOINT 进程
```

### 4.2 在 Dockerfile 中手动集成

```dockerfile
# 方式 1: 官方镜像内置 (推荐)
# Node 官方镜像已包含 tini (作为 ENTRYPOINT 包装)
FROM node:18-alpine
COPY app.js .
# ENTRYPOINT 已经被设置为 ["tini", "--", "node", "app.js"]
CMD ["node", "app.js"]
```

```dockerfile
# 方式 2: Alpine 镜像中手动安装 tini
FROM alpine:3.18
RUN apk add --no-cache tini
# 设置 tini 为 ENTRYPOINT
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["./start.sh"]
```

```dockerfile
# 方式 3: 自定义编译 (debian/ubuntu)
FROM debian:bookworm-slim
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["./start.sh"]
```

### 4.3 tini 在官方镜像中的默认行为

```bash
# 验证 tini 是否已集成
docker pull node:18-alpine
docker run --rm node:18-alpine cat /sbin/tini
# 输出: ELF binary (tini 二进制)

docker run --rm node:18-alpine ls -la /sbin/tini
# -rwxr-xr-x 1 root root  22888 ... /sbin/tini

# 官方镜像 ENTRYPOINT 检查
docker inspect node:18-alpine --format '{{.Config.Entrypoint}}'
# 输出: [tini -- node]

# 说明 Node 官方镜像已经设置了 tini 作为 ENTRYPOINT
```

---

## 五、Docker 中 tini 的使用

### 5.1 启动容器时启用 tini

```bash
# 推荐: 始终使用 --init 参数
docker run -d --init --name myapp myimage

# 不使用 --init (不推荐)
docker run -d --name myapp myimage

# 验证 tini 是否运行
docker exec myapp ps aux
# PID 1 应是 tini
# USER  PID  COMMAND
# root    1  /sbin/tini -- /start.sh
# root   10  /start.sh
# root   20  node app.js
```

### 5.2 通过环境变量配置 tini

```bash
# TINI_VERBOSITY: 控制日志详细度
docker run --init -e TINI_VERBOSITY=7 myimage

# TINI_KILL_PROCESS_GROUP_TIMEOUT: 子进程组超时
docker run --init \
  -e TINI_KILL_PROCESS_GROUP_TIMEOUT=10 \
  myimage

# 验证环境变量
docker exec myapp env | grep TINI
```

### 5.3 tini 与 ENTRYPOINT 的关系

```dockerfile
# 错误方式 1: 多次包装 tini
FROM alpine
RUN apk add tini
ENTRYPOINT ["/sbin/tini", "--", "/sbin/tini", "--", "./start.sh"]
# ❌ 启动了两个 tini, 冗余

# 正确方式 1: 镜像内手动包装一次
FROM alpine
RUN apk add tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["./start.sh"]

# 正确方式 2: 使用 --init 参数
FROM alpine
# 不安装 tini
ENTRYPOINT ["./start.sh"]
CMD ["./start.sh"]
# docker run --init myimage
# Docker 自动加 tini 在前面

# 错误方式 3: shell 脚本 exec 后, tini 失去信号转发
FROM alpine
RUN apk add tini
COPY start.sh /
RUN chmod +x /start.sh
ENTRYPOINT ["/sbin/tini", "--", "/bin/sh", "/start.sh"]
# start.sh 内部:
# !/bin/sh
# node app.js
# ❌ tini 与 node 之间隔了 shell, 信号可能无法正确传递
```

### 5.4 Compose 中使用 tini

```yaml
# docker-compose.yml
services:
  app:
    image: myapp:1.0
    init: true    # 对应 docker run --init
    command: ["./start.sh"]
    environment:
      TINI_VERBOSITY: 5
```

```bash
# Compose CLI
docker compose up -d
# 自动应用 init: true 配置
```

---

## 六、tini 在 K8s 中的应用

### 6.1 K8s Pod 中使用 tini

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  # 共享进程命名空间
  shareProcessNamespace: true
  containers:
  - name: app
    image: myapp:1.0
    env:
    - name: TINI_VERBOSITY
      value: "5"
```

```yaml
# K8s 方式: 让 Sidecar 容器能回收主容器进程
apiVersion: v1
kind: Pod
metadata:
  name: my-app-with-sidecar
spec:
  shareProcessNamespace: true
  containers:
  - name: app
    image: myapp:1.0
  - name: sidecar
    image: log-collector:1.0
    command: ["/sbin/tini", "--", "/bin/sh", "-c", "while true; do ps aux; sleep 10; done"]
    # tini 作为 PID 1 收养所有进程
    # Sidecar 能通过共享 PID namespace 看到其他容器进程
```

### 6.2 K8s 中 tini 的限制

```text
K8s 与 Docker 的区别:
  - Docker 中 ENTRYPOINT 进程就是 PID 1
  - K8s 中 Pod 内多个容器, 每个容器有自己的 PID namespace

默认行为:
  - 共享 PID namespace: 每个容器有独立 PID 1
  - shareProcessNamespace: true 后, 一个 PID namespace, 一个 PID 1
```

### 6.3 K8s 中处理 PID 1 的其他方式

```yaml
# K8s 1.28+ 引入 Sidecar Containers (原生支持)
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  initContainers:
  - name: log-shipper
    image: log-shipper:1.0
    restartPolicy: Always    # 关键: sidecar 行为
    command: ["/bin/sh", "-c", "while true; do tail -F /var/log/app.log; done"]
  containers:
  - name: app
    image: myapp:1.0
    volumeMounts:
    - name: log
      mountPath: /var/log
  volumes:
  - name: log
    emptyDir: {}
```

```text
Sidecar Container vs Init Container:
  - Init Container: 启动时运行, 完成后退出
  - Sidecar Container: 与主容器并行运行, 长期存活
  - 共享生命周期
```

---

## 七、tini 实战示例

### 7.1 Node.js 应用 + shell 启动脚本

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

# 创建启动脚本
COPY <<EOF /start.sh
#!/bin/sh
echo "Starting app..."
exec node server.js
EOF
RUN chmod +x /start.sh

# 必须用 tini 包装
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/start.sh"]
```

```bash
# 不使用 tini 的问题
docker run --name app myapp
docker stop app
# 卡 10 秒, 然后强杀
# 进程没机会清理资源

# 使用 tini
docker run --init --name app myapp
docker stop app
# tini 收到 SIGTERM, 转发给 start.sh
# start.sh exec node, node 收到 SIGTERM, 优雅退出
# 几秒内完成
```

### 7.2 Java Spring Boot 应用

```dockerfile
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app
COPY target/app.jar .

# 使用 tini 包装
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["java", "-jar", "app.jar"]
```

```bash
# 验证
docker run --init my-java-app
docker exec my-java-app ps aux
# PID 1 是 /sbin/tini -- java -jar app.jar
# java 进程是 PID 2
```

### 7.3 Python Flask 应用

```dockerfile
FROM python:3.11-slim

# 安装 tini
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# 重要: tini 包装
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "app.py"]
```

```bash
# 不用 tini 时的典型问题:
docker run --name flask myapp
docker exec flask ps aux
# PID 1 是 python app.py

# 当 app 创建子进程 (如 gunicorn worker):
# PID 1 不回收子进程
# 子进程变僵尸, PID 表满

# 用 tini:
docker run --init --name flask myapp
docker exec flask ps aux
# PID 1 是 /usr/bin/tini -- python app.py
# tini 回收所有子进程
```

---

## 八、tini 与其他 init 方案对比

### 8.1 常见 init 方案

```text
方案 1: tini (推荐, 轻量)
  - 体积: 30KB
  - 依赖: 无
  - 功能: 基础 init
  - 集成: Docker 内置, 多数官方镜像含 tini

方案 2: dumb-init
  - 体积: 100KB
  - 依赖: 无
  - 功能: 基础 init + 信号转发增强
  - 集成: 部分官方镜像

方案 3: s6-overlay
  - 体积: 几 MB
  - 依赖: 无
  - 功能: 完整 init 系统
  - 集成: 需要自己安装
  - 适用: 复杂启动场景

方案 4: tini + supervisord
  - 复杂进程管理
  - 自动重启子进程
  - 适用: 多进程应用

方案 5: Docker 内置 init (--init)
  - Docker 1.13+ 自动加 tini
  - 最简单的方式
  - 推荐使用
```

### 8.2 对比表

| 特性 | tini | dumb-init | s6-overlay |
|------|------|-----------|------------|
| **体积** | 30KB | 100KB | 几 MB |
| **依赖** | 无 | 无 | 无 |
| **信号转发** | ✓ | ✓✓ | ✓✓ |
| **僵尸回收** | ✓ | ✓ | ✓ |
| **进程组** | ✓ | ✓✓ | ✓✓ |
| **多进程管理** | ✗ | ✗ | ✓ |
| **Docker 集成** | 内置 | 部分 | 需自己 |
| **推荐场景** | 通用 | 多进程组 | 复杂启动 |

---

## 九、tini 最佳实践

### 9.1 使用原则

```text
1. 始终使用 tini
   - docker run --init
   - 或 ENTRYPOINT ["/sbin/tini", "--", ...]
   - 永远不要让 ENTRYPOINT 进程直接做 PID 1 (除非用 tini 包装)

2. 信号处理
   - 应用应注册 SIGTERM handler
   - 收到 SIGTERM 时做清理工作
   - 主动调用 exit(0)

3. 日志输出
   - 应用日志重定向到 stdout/stderr
   - Docker 自动收集
   - 不要写日志到文件

4. 健康检查
   - 使用 HEALTHCHECK 指令
   - 区分 liveness (重启) 和 readiness (流量)
```

### 9.2 优雅关闭流程

```text
完整的优雅关闭流程:

1. Docker 收到 docker stop
   ↓
2. Docker 发送 SIGTERM 到容器 PID 1
   ↓
3. tini (PID 1) 收到 SIGTERM
   ↓
4. tini 转发 SIGTERM 给 ENTRYPOINT 进程
   ↓
5. 应用收到 SIGTERM, 触发 handler
   ↓
6. 应用做清理:
   - 关闭 HTTP 服务器 (停止接受新请求)
   - 等待处理中的请求完成
   - 关闭数据库连接
   - 刷新日志
   - 关闭文件句柄
   ↓
7. 应用调用 exit(0)
   ↓
8. tini wait() 收到子进程退出
   ↓
9. tini 也 exit
   ↓
10. Docker 检测 PID 1 退出
   ↓
11. 容器停止

如果步骤 5-7 超过 grace period (默认 10s):
  - Docker 发送 SIGKILL
  - 进程被强制终止
  - 数据可能丢失

最佳实践:
  - 应用实现 SIGTERM handler
  - 清理工作能在 grace period 内完成
  - 监控容器关闭时间, 调优 grace period
```

### 9.3 实战技巧

```bash
# 1. 设置容器停止 grace period
docker run --stop-timeout 30 myapp
# K8s 等价:
spec:
  terminationGracePeriodSeconds: 30

# 2. 验证 tini 接管进程
docker exec myapp cat /proc/1/comm
# 输出: tini

# 3. 监控僵尸进程
docker exec myapp ps -e -o pid,ppid,stat,comm
# STAT 列 Z 表示 zombie
# 应为 0 个

# 4. 调试 tini 行为
docker run --init -e TINI_VERBOSITY=7 myapp
# TINI_VERBOSITY:
#   0 = silent
#   1 = errors
#   2 = warnings
#   3 = notices
#   5 = info
#   7 = debug
```

---

## 十、tini 完整工作流程示例

### 10.1 完整时序图

```text
完整的 docker stop 流程 (使用 tini):

  T0: 用户执行 docker stop myapp
  T0: Docker daemon 收到请求
  T0: Docker 发送 SIGTERM 到容器 PID 1
  T0: tini 进程 (PID 1) 收到 SIGTERM
       │
       ↓
  T0: tini 转发 SIGTERM 给 ENTRYPOINT 进程
       │
  T0: ENTRYPOINT 进程收到 SIGTERM
       │
       ↓
  T0: 应用触发 SIGTERM handler
       │
       ├── HTTP 服务器停止接受新连接
       ├── 等待处理中的请求完成
       ├── 数据库连接关闭
       ├── 日志 flush 到磁盘
       └── 准备退出
       │
  T5: 5 秒后, 应用完成清理, 调用 exit(0)
       │
  T5: 应用进程退出
  T5: tini wait() 检测到子进程退出
       │
  T5: tini 释放所有资源
       │
  T5: tini exit(0)
       │
  T5: 容器 PID 1 (tini) 退出
       │
  T5: Docker 检测到容器停止
       │
  T5: Docker daemon 清理容器
       │
  T5: Docker 删除容器文件系统

如果 T5 超过 10 秒 (grace period) 才发生:
  T10: Docker 发送 SIGKILL 到容器
  T10: 所有进程被强制终止
```

### 10.2 信号传递详解

```text
信号传递路径 (使用 tini):

外部信号 → Docker → tini → ENTRYPOINT 进程

例子: docker stop
  1. Docker 进程:
     kill -SIGTERM <container-pid-1>
  2. 信号进入容器命名空间
  3. PID 1 (tini) 收到 SIGTERM
  4. tini 处理: 转发给子进程
     - 默认: 转发 SIGTERM/SIGINT/SIGQUIT/SIGHUP/SIGINT/SIGTERM
     - 配置: tini -s SIGKILL ...
  5. 子进程收到 SIGTERM
  6. 应用处理
  7. 应用退出
  8. tini wait() 返回
  9. tini 退出

默认转发信号:
  - SIGTERM (kill)
  - SIGINT (Ctrl+C)
  - SIGQUIT (Ctrl+\)
  - SIGHUP (重读配置)
  - SIGUSR1/SIGUSR2 (用户信号)
  - 其他: 透传 (不处理, 让子进程处理)

自定义 tini 信号:
  docker run --init -e TINI_VERBOSITY=7 ...
  # 不推荐覆盖默认行为
```

---

## 十一、调试与排错

### 11.1 验证 tini 是否在运行

```bash
# 方法 1: 查看 PID 1
docker exec myapp cat /proc/1/comm
# 输出: tini (使用了 tini)
# 输出: node (没使用 tini, ENTRYPOINT 进程是 PID 1)

# 方法 2: 查看进程树
docker exec myapp ps aux
# 输出示例 (有 tini):
# USER  PID  COMMAND
# root    1  /sbin/tini -- /start.sh
# root   10  /start.sh
# root   20  node app.js

# 方法 3: 查看 PID 1 的状态
docker exec myapp cat /proc/1/status
# Name: tini
# State: S (sleeping)

# 方法 4: docker inspect
docker inspect myapp | grep Pid
# "Pid": 12345,  (容器在宿主的 PID)

# 方法 5: 进入容器看启动命令
docker inspect myapp --format '{{.Config.Entrypoint}}'
# 输出: [tini -- node app.js]
```

### 11.2 调试 tini 行为

```bash
# 启用详细日志
docker run --init -e TINI_VERBOSITY=7 myapp

# 或在 ENTRYPOINT 中显式
ENTRYPOINT ["/sbin/tini", "-v", "--"]
CMD ["./start.sh"]

# TINI_VERBOSITY 级别:
# 0 = silent
# 1 = errors
# 2 = warnings
# 3 = notices (default)
# 5 = info
# 7 = debug

# 查看 tini 帮助
docker run --rm -it krallin/tini --help
```

### 11.3 常见问题

```text
Q1: 应用启动慢, tini 启动慢?
A: tini 启动极快 (< 10ms), 检查应用本身

Q2: docker stop 卡住?
A: 应用没实现 SIGTERM handler 或清理时间过长
   解决: 实现 SIGTERM handler, 减少清理时间
   或: 增加 grace period (--stop-timeout 或 terminationGracePeriodSeconds)

Q3: 容器内有僵尸进程?
A: 没用 tini, 或 ENTRYPOINT 是 shell 脚本
   解决: 用 tini, 或用 exec 形式 ENTRYPOINT

Q4: K8s 中 Sidecar 容器看不到主容器进程?
A: K8s 默认每个容器有独立 PID namespace
   解决: 设置 shareProcessNamespace: true

Q5: tini 与 K8s liveness probe 冲突?
A: tini 在 ENTRYPOINT 前, liveness probe 直接访问应用
   两者不冲突
```

---

## 十二、核心要点速记

### Tini 的三大作用

```text
1. 僵尸进程回收
   - PID 1 自动 wait() 子进程
   - 防止进程表满

2. 信号转发
   - 收到 SIGTERM 转发给子进程
   - 应用能优雅关闭

3. 孤儿进程收养
   - 父进程退出后, 子进程被收养
   - 避免孤儿进程泄漏
```

### Docker 中使用 tini

```text
# 方式 1: docker run --init (推荐)
docker run --init myapp

# 方式 2: Dockerfile 包装
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["./start.sh"]

# 不要: ENTRYPOINT 直接是 shell 脚本 (会变僵尸)
ENTRYPOINT ["/bin/sh", "start.sh"]  # ❌
```

### K8s 中使用 tini

```text
# 1. 镜像内置 tini (推荐)
# 多数官方镜像 (node, python, golang) 已含 tini

# 2. 自定义镜像加 tini
RUN apk add tini
ENTRYPOINT ["/sbin/tini", "--"]

# 3. shareProcessNamespace
# 共享 PID namespace, 适合 sidecar 收集进程信息
```

### 信号流程速记

```text
docker stop
  → SIGTERM → tini (PID 1) → ENTRYPOINT 进程
  → 应用清理 (关闭连接, flush 日志)
  → exit(0)
  → tini 退出
  → 容器停止

如果 10 秒未退出:
  → SIGKILL → 进程被强杀
```

### 关键命令

```bash
# 验证 tini
docker exec myapp cat /proc/1/comm

# 启用调试
docker run --init -e TINI_VERBOSITY=7 myapp

# 强制不用 tini
docker run --init=false myapp  # ❌ 不推荐
```

---

## 附录: 关键参考

```text
- tini GitHub: https://github.com/krallin/tini
- Docker --init 文档: https://docs.docker.com/engine/reference/run/#init
- Docker 信号处理: https://docs.docker.com/engine/reference/run/#stop-grace-period
- K8s Pod lifecycle: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/
- K8s shareProcessNamespace: https://kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/
- Docker ENTRYPOINT 最佳实践: https://docs.docker.com/engine/reference/builder/#entrypoint
- Signal handling 最佳实践: https://docs.docker.com/develop/develop-images/dockerfile_best-practices/#entrypoint
- Linux PID 命名空间: https://man7.org/linux/man-pages/man7/pid_namespaces.7.html
- K8s Sidecar Containers: https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/

## 二、推荐组合与最佳实践
```

## 快速参考卡

```text
✅ 推荐:  docker run --init myapp
✅ 推荐:  ENTRYPOINT ["/sbin/tini", "--", "./app"]
❌ 不要:  ENTRYPOINT ["/bin/sh", "./start.sh"]
❌ 不要:  不用 tini 让 shell 脚本做 PID 1

# 验证
docker exec myapp cat /proc/1/comm
# 期望: tini

# 优雅关闭
docker stop myapp     # 等待应用清理, 几秒内停止
# vs
docker stop myapp     # 卡 10 秒, 然后 SIGKILL
```
