# Dockerfile 详解 (Dockerfile Reference)

> 本章系统讲解 Dockerfile 的所有指令、最佳实践、多阶段构建与镜像优化。

## 一、Dockerfile 概述

### 1.1 什么是 Dockerfile

**Dockerfile** 是构建 Docker 镜像的文本文件,包含了一系列指令,每个指令构建一层镜像。

```dockerfile
# 简单示例
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y nginx
COPY index.html /var/www/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```bash
# 构建镜像
docker build -t my-image:1.0 .

# 构建过程
# Step 1/4 : FROM ubuntu:22.04      ← 第 1 层
# Step 2/4 : RUN apt-get update     ← 第 2 层
# Step 3/4 : COPY index.html        ← 第 3 层
# Step 4/4 : CMD ["nginx", ...]     ← 元数据
```

### 1.2 Dockerfile 工作流程

```text
docker build 执行流程:

1. 解析 Dockerfile
2. 解析 FROM 基础镜像 (拉取/复用本地)
3. 按顺序执行每个指令:
   a. 每条指令在容器内执行
   b. 执行完后,容器生成一层镜像
   c. 提交为新镜像 (docker commit)
   d. 删除中间容器
4. 给最终镜像打标签

注意:
- 顺序很重要 (缓存复用)
- 每条 RUN/COPY/ADD 都是一层
- 多条命令可用 && 合并,减少层数
```

---

## 二、Dockerfile 完整指令

### 2.1 FROM (基础镜像)

```dockerfile
# 基本用法
FROM ubuntu:22.04

# 指定 digest (不可变,推荐生产)
FROM ubuntu:22.04@sha256:abc123...

# 多阶段构建 (多个 FROM)
FROM golang:1.21 AS builder
# ... 构建步骤 ...
FROM alpine:3.18
# ... 运行时镜像 ...
COPY --from=builder /app/bin /app/bin

# 特殊基础镜像
FROM scratch              # 空镜像 (最小)
FROM alpine:3.18         # 5 MB
FROM ubuntu:22.04        # 70 MB
FROM debian:bullseye-slim
```

### 2.2 RUN (执行命令)

```dockerfile
# shell 格式 (默认 /bin/sh -c)
RUN apt-get update && apt-get install -y nginx
# 注意:&& 连接,减少镜像层数

# exec 格式 (推荐,无需 shell 解析)
RUN ["apt-get", "install", "-y", "nginx"]

# 多行命令 (反斜杠换行)
RUN apt-get update && \
    apt-get install -y \
        nginx \
        curl \
        vim && \
    rm -rf /var/lib/apt/lists/*

# 关键最佳实践: 清理缓存
RUN apt-get update && \
    apt-get install -y nginx && \
    rm -rf /var/lib/apt/lists/*
# 上面一行 rm 与 install 在同一层, 减小镜像
```

### 2.3 CMD (默认命令)

```dockerfile
# shell 格式
CMD echo "hello world"

# exec 格式 (推荐)
CMD ["echo", "hello world"]

# 实际应用 (启动 nginx 前台运行)
CMD ["nginx", "-g", "daemon off;"]

# 作为 ENTRYPOINT 参数
CMD ["--port", "8080"]

# 注意:
# - 一个 Dockerfile 只有最后一个 CMD 生效
# - docker run <image> <command> 会覆盖 CMD
# - CMD 用于设置默认命令, ENTRYPOINT 用于固定入口
```

### 2.4 ENTRYPOINT (入口点)

```dockerfile
# exec 格式 (推荐)
ENTRYPOINT ["nginx", "-g", "daemon off;"]

# shell 格式
ENTRYPOINT echo "hello"

# 完整用法 (容器当作可执行文件)
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["--help"]                   # ENTRYPOINT 的参数

# 运行时:
# docker run myimage                 → /app/entrypoint.sh (默认)
# docker run myimage arg1            → /app/entrypoint.sh arg1
# docker run myimage --help          → /app/entrypoint.sh --help
# docker run --entrypoint=bash myimage  → bash (覆盖)
```

**ENTRYPOINT vs CMD 区别**:

```text
ENTRYPOINT:
- 镜像本身的入口 (固定)
- docker run 参数会作为 ENTRYPOINT 的参数

CMD:
- 镜像的默认命令
- docker run 参数会覆盖 CMD
- ENTRYPOINT 存在时, CMD 作为 ENTRYPOINT 的默认参数
```

### 2.5 LABEL (标签)

```dockerfile
# 元数据标签
LABEL maintainer="dev@example.com"
LABEL version="1.0"
LABEL description="My web application"
LABEL org.opencontainers.image.source="https://github.com/myorg/myapp"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.title="My Application"

# 多个标签合并为一行 (推荐)
LABEL maintainer="dev@example.com" \
      version="1.0" \
      description="My web application"
```

```bash
# 查看标签
docker inspect <image> --format='{{json .Config.Labels}}'
```

### 2.6 EXPOSE (声明端口)

```dockerfile
# 声明容器监听端口 (文档作用, 不实际发布)
EXPOSE 80
EXPOSE 443
EXPOSE 8080
EXPOSE 80/tcp
EXPOSE 53/udp

# 注意:
# - EXPOSE 只是声明, 实际访问需 -p 映射
# - 镜像使用者知道端口用途
# - docker run -P 时自动映射
```

### 2.7 ENV (环境变量)

```dockerfile
# 设置环境变量
ENV MYSQL_VERSION=8.0
ENV PATH=/usr/local/bin:$PATH
ENV JAVA_HOME=/usr/java/openjdk-11

# 多行写法
ENV MYSQL_VERSION_MAJOR=8 \
    MYSQL_VERSION_MINOR=0 \
    MYSQL_VERSION=$MYSQL_VERSION_MAJOR.$MYSQL_VERSION_MINOR
```

```bash
# 运行时查看
docker run my-image env

# 覆盖环境变量
docker run -e MYSQL_VERSION=5.7 my-image
```

### 2.8 COPY (复制文件)

```dockerfile
# 基本用法
COPY index.html /var/www/html/
COPY app.py /app/
COPY src/ /app/src/              # 复制整个目录

# 多个文件
COPY file1.txt file2.txt /data/

# 改变用户和权限
COPY --chown=user:group index.html /var/www/html/
COPY --chmod=755 entrypoint.sh /usr/local/bin/

# 从其他 stage 复制 (多阶段构建)
COPY --from=builder /app/build/ /app/build/
COPY --from=0 /some/dir /dest/    # 0 表示第一个 FROM
```

### 2.9 ADD (高级复制)

```dockerfile
# 与 COPY 类似, 但 ADD 支持:
# 1. 自动解压 tar
ADD archive.tar.gz /opt/        # 自动解压到 /opt/
ADD https://example.com/file.txt /data/  # 支持 URL

# 2. 自动识别目录
ADD src /dest/                  # 与 COPY 等价

# ⚠️ 最佳实践:
# 推荐用 COPY 而非 ADD (行为更明确)
# ADD 隐藏了自动解压等行为, 易踩坑
```

**COPY vs ADD**:

```text
COPY:
- 只复制文件/目录
- 行为明确
- 推荐用

ADD:
- 复制 + 自动解压 tar
- 复制 URL
- 隐藏行为, 易踩坑
- 除非必须, 用 COPY
```

### 2.10 WORKDIR (工作目录)

```dockerfile
# 设置工作目录 (后续 RUN, CMD, ENTRYPOINT, COPY, ADD 的相对路径基于此)
WORKDIR /app

# 不存在则创建
WORKDIR /app/src
WORKDIR /data

# 多层叠加 (相对路径)
WORKDIR /a
WORKDIR b      # 实际: /a/b
WORKDIR c      # 实际: /a/b/c

# 推荐:
WORKDIR /app
COPY app.py /app/    # 路径明确
```

### 2.11 USER (用户)

```dockerfile
# 设置后续命令的用户
USER nginx                       # 用户名
USER 1000                        # UID
USER 1000:1000                   # UID:GID
USER nobody:nogroup              # 用户名:组名

# 推荐:
# 1. 创建专用用户
RUN addgroup -S app && adduser -S -G app app
USER app
# 2. 不要用 root 运行应用
```

### 2.12 VOLUME (声明卷)

```dockerfile
# 声明匿名卷 (推荐)
VOLUME /data
VOLUME ["/data", "/logs"]

# 容器内 /data 自动成为匿名卷
# 即使容器删除, 数据保留
```

### 2.13 ARG (构建参数)

```dockerfile
# 声明构建参数 (只在构建时生效)
ARG VERSION=1.0
ARG NODE_VERSION=18

# 在 FROM 之前定义 ARG (用于 FROM)
ARG BASE_IMAGE=ubuntu:22.04
FROM $BASE_IMAGE

# 在 FROM 之后使用 ARG
ARG VERSION
RUN echo "Building version $VERSION"
```

```bash
# 构建时传入
docker build --build-arg VERSION=2.0 -t myapp:2.0 .
docker build --build-arg HTTP_PROXY=http://proxy:8080 .
```

### 2.14 ONBUILD (子镜像触发器)

```dockerfile
# 当前镜像被作为基础镜像时触发
ONBUILD RUN echo "Hello from child image"

# 适用场景:
# - 制作"基础应用镜像", 子镜像统一初始化
# - 不推荐 (难追踪, K8s/Helm 时代用其他方式)
```

### 2.15 STOPSIGNAL (停止信号)

```dockerfile
# 容器停止时发送的信号
STOPSIGNAL SIGTERM             # 默认
STOPSIGNAL SIGQUIT
```

### 2.16 HEALTHCHECK (健康检查)

```dockerfile
# 健康检查 (容器运行时定期执行)
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -f http://localhost/ || exit 1

# 参数:
# --interval=30s   检查间隔
# --timeout=3s    单次超时
# --start-period=40s  启动宽限期 (启动慢的应用)
# --retries=3      失败重试次数
```

### 2.17 SHELL (默认 shell)

```dockerfile
# 修改默认 shell (默认 /bin/sh -c)
SHELL ["powershell", "-command"]

# 用于 Windows 镜像
```

---

## 三、Dockerfile 完整示例

### 3.1 Node.js 应用

```dockerfile
# 多阶段构建
FROM node:18-alpine AS builder

# 设置工作目录
WORKDIR /app

# 复制 package 文件 (利用缓存)
COPY package*.json ./
RUN npm ci --only=production

# 复制源代码
COPY . .

# 构建
RUN npm run build

# ===== 运行时镜像 (小) =====
FROM node:18-alpine

LABEL maintainer="dev@example.com"

# 创建用户
RUN addgroup -g 1001 -S nodejs && \
    adduser -S -u 1001 -G nodejs nodejs

WORKDIR /app

# 从 builder 阶段复制构建产物
COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules

USER nodejs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -qO- http://localhost:3000/health || exit 1

CMD ["node", "dist/server.js"]
```

### 3.2 Go 应用 (最小镜像)

```dockerfile
# 构建阶段
FROM golang:1.21-alpine AS builder

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/myapp

# 运行时镜像 (仅 ~10MB)
FROM alpine:3.18

LABEL maintainer="dev@example.com"

# 安装 CA 证书 + 时区数据
RUN apk --no-cache add ca-certificates tzdata

# 创建用户
RUN addgroup -S app && adduser -S -G app app

WORKDIR /app

# 复制二进制
COPY --from=builder /app/myapp /app/myapp

# 复制配置
COPY config.yaml /app/

USER app

EXPOSE 8080

HEALTHCHECK --interval=30s \
  CMD wget -qO- http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/myapp"]
```

### 3.3 Python Flask

```dockerfile
FROM python:3.11-slim

LABEL maintainer="dev@example.com"

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先复制依赖文件 (利用缓存)
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制代码
COPY . .

# 创建用户
RUN useradd --create-home --shell /bin/bash app
USER app

EXPOSE 5000

HEALTHCHECK --interval=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

### 3.4 Java Spring Boot

```dockerfile
# 构建阶段
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /build
COPY pom.xml .
RUN mvn dependency:go-offline    # 缓存依赖

COPY src ./src
RUN mvn package -DskipTests

# 运行时
FROM eclipse-temurin:17-jre-alpine

LABEL maintainer="dev@example.com"

# 创建用户
RUN addgroup -S spring && adduser -S -G spring spring

WORKDIR /app

# 复制 jar
COPY --from=builder /build/target/*.jar app.jar

USER spring

EXPOSE 8080

HEALTHCHECK --interval=30s \
  CMD wget -qO- http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

---

## 四、多阶段构建

### 4.1 概念

```text
多阶段构建 = 多个 FROM, 每个阶段可独立使用

解决问题:
1. 构建工具 (gcc, maven, npm) 不应该出现在生产镜像
2. 源码/中间文件 不应该出现在生产镜像
3. 最终镜像最小, 最安全

最终镜像通常减少 50-90%
```

### 4.2 多阶段实战

```dockerfile
# ===== 阶段 1: 构建 =====
FROM golang:1.21-alpine AS builder

WORKDIR /build

# 缓存依赖层
COPY go.mod go.sum ./
RUN go mod download

# 复制源码 + 构建
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/myapp

# ===== 阶段 2: 运行时 =====
FROM alpine:3.18

# 拷贝构建产物
COPY --from=builder /out/myapp /usr/local/bin/myapp

# 运行时依赖
RUN apk add --no-cache ca-certificates

USER nobody
ENTRYPOINT ["/usr/local/bin/myapp"]
```

### 4.3 命名阶段

```dockerfile
# 命名阶段 (便于引用)
FROM golang:1.21 AS builder
...
FROM node:18 AS frontend-builder
...

FROM alpine
COPY --from=builder /out/myapp /app/
COPY --from=frontend-builder /dist /app/static/
```

---

## 五、镜像优化

### 5.1 镜像优化策略

```text
1. 基础镜像选择
   - alpine (5MB) - 推荐
   - distroless (20MB) - 最安全
   - scratch (0MB) - 仅 Go 等编译型语言

2. 多阶段构建
   - 减少最终镜像 50-90%

3. 层合并
   - RUN 命令合并 (&& \)
   - 清理缓存 (apt, yum)

4. .dockerignore
   - 排除不必要的文件

5. 选择合适的镜像变体
   - alpine/slim (小)
   - full (大, 功能全)

6. 减少 COPY 次数
   - 合并 COPY 命令
```

### 5.2 .dockerignore

```text
# .dockerignore 文件

# 版本控制
.git
.gitignore
.svn
.hg

# IDE 配置
.vscode
.idea
*.swp
*.swo

# Node
node_modules
npm-debug.log
yarn-error.log
yarn.lock
package-lock.json

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.tox
.coverage
htmlcov

# Go
vendor/
*.test
*.out

# Java
target/
*.class
*.jar
.gradle/
.mvn/

# 构建产物
dist/
build/
out/

# 日志和临时文件
*.log
*.tmp
.DS_Store

# 文档
README.md
docs/
*.md

# CI/CD 配置
.github/
.gitlab-ci.yml
Jenkinsfile

# 测试
tests/
test/
*_test.go
*.test.js
*.spec.ts

# 大文件
*.mp4
*.zip
*.tar.gz
*.iso

# 密钥 (绝不能放进镜像!)
.env
*.pem
*.key
```

### 5.3 镜像大小优化示例

```dockerfile
# ❌ 不优化 (500MB+)
FROM ubuntu:22.04
RUN apt-get update
RUN apt-get install -y nginx
RUN apt-get install -y curl
RUN apt-get install -y vim
COPY . /app/
RUN apt-get autoremove

# ✅ 优化 (50MB)
FROM nginx:alpine
COPY dist/ /usr/share/nginx/html/

# ✅ 多阶段构建 (15MB)
FROM node:18 AS builder
WORKDIR /build
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /build/dist /usr/share/nginx/html/
```

---

## 六、Dockerfile 实战模式

### 6.1 基础模式

```dockerfile
# 最小可运行镜像
FROM alpine:3.18
RUN apk add --no-cache curl
CMD ["curl", "--version"]
```

### 6.2 系统服务模式

```dockerfile
FROM ubuntu:22.04

# 安装服务
RUN apt-get update && apt-get install -y nginx && \
    rm -rf /var/lib/apt/lists/*

# 复制配置
COPY nginx.conf /etc/nginx/nginx.conf

# 前台运行 (容器需要前台进程)
CMD ["nginx", "-g", "daemon off;"]
```

### 6.3 Web 应用模式

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV FLASK_APP=app.py
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

### 6.4 数据库模式

```dockerfile
FROM postgres:15-alpine

# 初始化脚本
COPY init.sql /docker-entrypoint-initdb.d/

# 配置
ENV POSTGRES_DB=mydb \
    POSTGRES_USER=admin

# 持久化 (Volume 由运行时挂载)
VOLUME ["/var/lib/postgresql/data"]

EXPOSE 5432
```

### 6.5 初始化脚本模式

```dockerfile
FROM alpine:3.18

# 复制初始化脚本
COPY init.sh /usr/local/bin/
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh

# 容器启动时执行
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
```

---

## 七、Dockerfile 实战技巧

### 7.1 缓存优化

```text
Dockerfile 指令执行顺序影响镜像构建缓存:

COPY package.json ./
RUN npm install         # 这层不会变 (除非 package.json 改)
COPY . .               # 这层经常变

# 上面的写法: 只重新安装依赖当 package.json 变
# 下面的写法错: 任何文件改都会重新 npm install
COPY . .
RUN npm install
```

### 7.2 镜像瘦身

```dockerfile
FROM ubuntu:22.04

# 安装后清理
RUN apt-get update && \
    apt-get install -y nginx && \
    rm -rf /var/lib/apt/lists/*    # 关键: 清理 apt 缓存

# 链式清理
RUN apt-get update && apt-get install -y \
        nginx \
        curl \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean
```

### 7.3 安全强化

```dockerfile
# 1. 不要用 root
RUN adduser --system --no-create-home --uid 1001 app
USER app

# 2. 只读根文件系统
# docker run --read-only --tmpfs /tmp --tmpfs /run
# 或在 Dockerfile 中:
RUN chmod -R a-w / && \
    chmod a+w /tmp /var/tmp /var/log

# 3. 移除 setuid 二进制
RUN find / -perm -4000 -exec chmod u-s {} \; 2>/dev/null

# 4. 只读挂载数据
COPY --chmod=444 config.yaml /app/
```

### 7.4 构建参数化

```dockerfile
# ARG 参数
ARG VERSION=1.0
ARG ENVIRONMENT=production
ARG NPM_REGISTRY=https://registry.npmjs.org

LABEL version=$VERSION \
      environment=$ENVIRONMENT

RUN npm config set registry $NPM_REGISTRY
```

```bash
# 构建时
docker build \
  --build-arg VERSION=2.0 \
  --build-arg ENVIRONMENT=staging \
  --build-arg NPM_REGISTRY=https://npmmirror.com \
  -t myapp:2.0 .
```

---

## 八、Dockerfile 最佳实践

### 8.1 通用最佳实践

```text
1. 使用官方基础镜像
2. 使用具体 tag (不用 latest)
3. 多阶段构建
4. 合并 RUN 命令 (减少层)
5. 清理缓存 (apt, yum, pip)
6. 用 .dockerignore
7. 不要用 root 运行
8. COPY 优先于 ADD
9. WORKDIR 优先于 RUN cd
10. 添加 HEALTHCHECK
11. 合理 EXPOSE 端口
12. ENV 值用 ${VAR:-default} 提供默认
```

### 8.2 安全最佳实践

```text
1. 最小化基础镜像 (alpine / distroless)
2. 多阶段构建, 运行时不含构建工具
3. 非 root 用户
4. 不硬编码密钥
5. .dockerignore 排除密钥
6. 镜像扫描 (Trivy, Clair)
7. 镜像签名 (Cosign)
8. 只读根 FS
9. 移除不必要的 capability
10. 定期更新基础镜像
```

### 8.3 性能最佳实践

```text
1. 减少镜像层数 (合并 RUN)
2. 利用构建缓存 (COPY 顺序)
3. 选择 alpine/slim 基础镜像
4. 多阶段构建
5. 清理包管理器缓存
6. 使用 .dockerignore 排除
7. 预编译 (Go) / 运行时解释 (Python)
8. 镜像分层: 不变的层在前, 变化的层在后
```

---

## 核心要点速记

### Dockerfile 指令

```dockerfile
FROM      # 基础镜像
RUN       # 执行命令
COPY      # 复制文件 (推荐)
ADD       # 高级复制 (tar/URL)
CMD       # 默认命令
ENTRYPOINT# 入口点
LABEL     # 元数据
EXPOSE    # 声明端口
ENV       # 环境变量
ARG       # 构建参数
WORKDIR   # 工作目录
USER      # 用户
VOLUME    # 卷
HEALTHCHECK # 健康检查
```

### COPY vs ADD

```text
COPY: 复制文件, 推荐
ADD:  复制 + tar 解压 + URL, 易踩坑, 仅必要时用
```

### ENTRYPOINT vs CMD

```text
ENTRYPOINT: 镜像入口, 固定
CMD:        默认命令, 可覆盖
CMD 是 ENTRYPOINT 的默认参数
```

### 多阶段构建

```dockerfile
FROM golang AS builder    # 阶段 1
...
FROM alpine                # 阶段 2 (运行时)
COPY --from=builder /app/myapp /app/
```

### 镜像优化

```text
1. alpine/distroless 基础镜像
2. 多阶段构建
3. RUN 命令合并
4. 清理缓存 (apt/yum/pip)
5. .dockerignore 排除
6. 缓存优化 (COPY 顺序)
```

### 实战模式

```dockerfile
# Node.js
FROM node:18-alpine

# Go
FROM golang:1.21 AS builder
FROM alpine:3.18

# Python
FROM python:3.11-slim

# Java
FROM maven:3.9 AS builder
FROM eclipse-temurin:17-jre-alpine
```

---

## 参考

- **Dockerfile 参考**: https://docs.docker.com/engine/reference/builder/
- **Dockerfile 最佳实践**: https://docs.docker.com/develop/develop-images/dockerfile_best-practices/
- **多阶段构建**: https://docs.docker.com/build/building/multi-stage/
- **.dockerignore**: https://docs.docker.com/engine/reference/builder/#dockerignore-file
