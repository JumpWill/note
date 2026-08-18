# Docker Compose (Multi-Container Orchestration)

> 本章详解 Docker Compose:多容器编排工具的完整用法、docker-compose.yml 语法与实战案例。

## 一、Docker Compose 概述

### 1.1 什么是 Compose

**Docker Compose** 是 Docker 官方提供的**多容器编排工具**,通过 YAML 文件定义多容器应用。

```text
解决的问题:
1. 单个 docker run 命令只能启动一个容器
2. 复杂应用涉及多个容器 (Web + DB + Cache + ...)
3. 需要统一编排、配置、网络、依赖

传统方式:
   docker run -d --name web nginx
   docker run -d --name db postgres
   docker run -d --network backend --link db my-app
   # 复杂、容易出错

Compose 方式:
   docker compose up -d    # 一键启动所有容器
```

### 1.2 Compose V2 vs V1

```text
Compose V1 (Python):
  - 二进制: docker-compose
  - 独立命令
  - 已停止维护

Compose V2 (Go):
  - Docker CLI 插件
  - 命令: docker compose (无横线)
  - 推荐使用

安装:
  # Docker Desktop 自带
  # Linux 手动安装
  apt install docker-compose-plugin
  # 或
  curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
```

### 1.3 Compose vs 其他编排工具

| 工具 | 适用场景 |
|------|---------|
| **Docker Compose** | 单机多容器, 开发/测试 |
| **Docker Swarm** | Docker 原生集群编排 |
| **Kubernetes** | 生产级大规模编排 |
| **Nomad** | HashiCorp 通用编排 |

---

## 二、docker-compose.yml 文件

### 2.1 完整结构

```yaml
# docker-compose.yml
version: '3.8'        # Compose 文件版本 (3.8+)
name: my-project      # 项目名 (Compose V2+)

services:              # 服务定义 (必填)
  web:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./html:/usr/share/nginx/html
    networks:
      - frontend
    depends_on:
      - api
    environment:
      - DEBUG=true

  api:
    build: ./api
    ports:
      - "8080:8080"
    environment:
      DB_HOST: db
      DB_PASSWORD: secret
    depends_on:
      - db
    networks:
      - frontend
      - backend

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: secret
    volumes:
      - dbdata:/var/lib/postgresql/data
    networks:
      - backend

volumes:                # 卷定义
  dbdata:

networks:               # 网络定义
  frontend:
  backend:
```

### 2.2 核心配置项

```yaml
services:
  <service-name>:       # 服务名 (唯一)
    image: <image>      # 镜像
    build: <path>       # 构建路径
    container_name: <name>  # 容器名 (可选, 默认 <project>_<service>_<n>)
    
    # 端口
    ports:
      - "8080:80"           # 短格式
      - "127.0.0.1:8080:80" # 指定 IP
      - target: 80           # 长格式
        published: 8080
        protocol: tcp
    
    # 环境变量
    environment:
      KEY: VALUE              # 字典格式
      - KEY=VALUE             # 列表格式
    env_file:
      - .env
    
    # 卷
    volumes:
      - ./data:/data         # 短格式
      - type: bind           # 长格式
        source: ./data
        target: /data
    
    # 网络
    networks:
      - frontend
    
    # 依赖 (启动顺序, 但不等就绪)
    depends_on:
      - db
    
    # 重启策略
    restart: always | unless-stopped | on-failure | no
    
    # 资源限制
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    
    # 命令覆盖
    command: ["nginx", "-g", "daemon off;"]
    entrypoint: /init.sh
    
    # 健康检查
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    
    # 用户
    user: "1000:1000"
    
    # 端口 (expose 不映射)
    expose:
      - "80"
    
    # 日志驱动
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    
    # DNS
    dns:
      - 8.8.8.8
    dns_search:
      - example.com
```

---

## 三、Compose 完整命令

### 3.1 服务生命周期

```bash
# 启动服务 (前台, Ctrl+C 停止)
docker compose up

# 启动服务 (后台)
docker compose up -d

# 启动 + 强制重建
docker compose up -d --build --force-recreate

# 仅构建镜像
docker compose build

# 不启动容器, 仅验证配置
docker compose config

# 停止服务 (但保留容器)
docker compose stop

# 停止并删除容器、网络
docker compose down

# 停止并删除容器、网络、卷
docker compose down -v

# 停止并删除容器、网络、卷、镜像
docker compose down -v --rmi all

# 重启服务
docker compose restart

# 暂停/恢复服务
docker compose pause
docker compose unpause
```

### 3.2 服务查看

```bash
# 列出服务
docker compose ps

# 查看服务日志
docker compose logs
docker compose logs -f                  # 跟踪
docker compose logs --tail 100 web      # 指定服务
docker compose logs -t                  # 时间戳

# 查看进程
docker compose top

# 查看配置 (渲染后)
docker compose config

# 查看某个服务详情
docker compose ps web
docker compose port web 80             # 端口映射
```

### 3.3 服务操作

```bash
# 启动某个服务
docker compose up -d web

# 停止某个服务
docker compose stop web

# 重启某个服务
docker compose restart web

# 进入容器
docker compose exec web bash
docker compose exec web sh

# 在容器中运行命令
docker compose run web env
docker compose run --rm web bash    # 用完即删容器

# 查看日志
docker compose logs -f web
```

### 3.4 其他命令

```bash
# 拉取镜像
docker compose pull

# 查看镜像
docker compose images

# 查看卷
docker compose volumes

# 扩展服务
docker compose up -d --scale web=3

# 执行一次性命令
docker compose run --rm web python manage.py migrate

# 查看帮助
docker compose --help
```

---

## 四、Compose 实战案例

### 4.1 WordPress 完整部署

```yaml
# docker-compose.yml
version: '3.8'

services:
  wordpress:
    image: wordpress:latest
    container_name: wordpress
    ports:
      - "8080:80"
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: wordpress
      WORDPRESS_DB_PASSWORD: changeme
      WORDPRESS_DB_NAME: wordpress
    volumes:
      - wordpress_data:/var/www/html
    depends_on:
      - db
    networks:
      - wordpress-net
    restart: unless-stopped

  db:
    image: mysql:8.0
    container_name: wordpress-db
    environment:
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wordpress
      MYSQL_PASSWORD: changeme
      MYSQL_ROOT_PASSWORD: rootpass
    volumes:
      - db_data:/var/lib/mysql
    networks:
      - wordpress-net
    restart: unless-stopped

volumes:
  wordpress_data:
  db_data:

networks:
  wordpress-net:
    driver: bridge
```

```bash
# 启动
docker compose up -d

# 访问 http://localhost:8080

# 查看日志
docker compose logs -f wordpress

# 停止 (保留数据)
docker compose down

# 完全清理
docker compose down -v --rmi all
```

### 4.2 微服务应用

```yaml
# docker-compose.yml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
    depends_on:
      - frontend
      - backend
    networks:
      - frontend
      - backend
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      API_URL: http://backend:8080
    networks:
      - frontend
    restart: unless-stopped

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      REDIS_HOST: redis
    depends_on:
      - postgres
      - redis
    networks:
      - backend
    restart: unless-stopped

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    networks:
      - backend
    restart: unless-stopped

volumes:
  pgdata:

networks:
  frontend:
  backend:
```

### 4.3 开发环境

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  app:
    build:
      context: .
      target: dev    # 多阶段构建的 dev 阶段
    volumes:
      - .:/app                       # 源码热更新
      - /app/node_modules            # 排除 node_modules 覆盖
      - /app/.git
    command: npm run dev
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: development
      DEBUG: "*"
    networks:
      - dev

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: devdb
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"     # 暴露到宿主方便调试
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - dev

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - dev

  mailhog:        # 测试邮件服务
    image: mailhog/mailhog:latest
    ports:
      - "1025:1025"   # SMTP
      - "8025:8025"   # Web UI
    networks:
      - dev

volumes:
  pgdata:

networks:
  dev:
    driver: bridge
```

### 4.4 生产级 (含健康检查、资源限制)

```yaml
version: '3.8'

services:
  web:
    image: myapp:1.0
    deploy:
      replicas: 3                    # Compose V2+ 支持
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    environment:
      - NODE_ENV=production
    volumes:
      - app-data:/app/data
    networks:
      - app-net
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  app-data:

networks:
  app-net:
    driver: bridge
```

---

## 五、多文件 Compose

### 5.1 多环境配置

```bash
# 基础配置
docker-compose.yml        # 公共配置

# 覆盖配置 (可选,优先级高)
docker-compose.override.yml    # 本地开发 (默认加载)
docker-compose.prod.yml        # 生产
docker-compose.test.yml        # 测试

# 使用指定文件
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 5.2 项目命名

```bash
# 默认项目名: 当前目录名
# 自定义项目名
docker compose -p myproject up -d

# 或在文件中指定 (Compose V2+)
# docker-compose.yml
name: my-project
```

---

## 六、Compose 高级特性

### 6.1 健康检查与 depends_on

```yaml
services:
  api:
    image: my-api
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s

  db:
    image: postgres
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin"]
      interval: 10s
      timeout: 5s
      retries: 5

  cache:
    image: redis
    depends_on:
      api:
        condition: service_healthy    # 等 api healthy 才启动
      db:
        condition: service_healthy
```

### 6.2 Profiles (按需启动)

```yaml
version: '3.8'

services:
  web:
    image: nginx
    ports:
      - "80:80"

  debug-tools:
    image: nicolaka/netshoot
    profiles:
      - debug                    # 只在 --profile debug 启动

  monitoring:
    image: prom/prometheus
    profiles:
      - monitoring               # 只在 --profile monitoring 启动
```

```bash
# 默认启动 (不包含 debug 和 monitoring)
docker compose up -d

# 启动 debug profile
docker compose --profile debug up

# 启动多个 profile
docker compose --profile debug --profile monitoring up
```

### 6.3 Config (配置注入)

```yaml
# docker-compose.yml
services:
  web:
    image: nginx
    configs:
      - source: nginx-config
        target: /etc/nginx/nginx.conf

configs:
  nginx-config:
    file: ./nginx.conf    # 从文件加载

# 或从内容生成
configs:
  app-config:
    content: |
      DEBUG=true
      LOG_LEVEL=info
```

### 6.4 Secrets (密钥)

```yaml
services:
  db:
    image: postgres
    secrets:
      - db_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt    # 从文件

# 或外部 Secret (Docker Swarm)
  db_password:
    external: true
```

### 6.5 扩展 (deploy)

```yaml
version: '3.8'

services:
  web:
    image: nginx
    deploy:
      replicas: 3                # 3 个副本
      placement:
        constraints:
          - node.role == worker   # 部署到 worker 节点
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
      update_config:
        parallelism: 2           # 滚动更新时同时更新 2 个
        delay: 10s
        order: start-first       # 先启动新版本,再停止旧的
```

---

## 七、Compose 部署策略

### 7.1 单机部署

```text
适用场景:
- 开发环境
- 小型生产应用 (单台服务器)
- CI/CD 测试环境

特点:
- 所有容器在一台机器
- 性能受限于单机资源
- 无高可用 (单机故障)
```

### 7.2 Swarm 模式 (Compose V2)

```bash
# 初始化 Swarm
docker swarm init

# 部署 stack
docker compose -f docker-compose.yml up -d
# 实际调用 docker stack deploy

# 查看服务
docker stack services
docker stack ps
```

### 7.3 与 Kubernetes 的转换

```bash
# Kompose: Compose 转 K8s YAML
# https://github.com/kubernetes/kompose

# 安装
curl -L https://github.com/kubernetes/kompose/releases/latest/download/kompose-linux-amd64 -o /usr/local/bin/kompose
chmod +x /usr/local/bin/kompose

# 转换
kompose convert -f docker-compose.yml -o k8s/
# 生成 K8s manifests
```

---

## 八、实战技巧

### 8.1 .env 文件

```bash
# .env 文件 (项目根目录)
COMPOSE_PROJECT_NAME=my-app
POSTGRES_USER=admin
POSTGRES_PASSWORD=secret
TAG=1.0
```

```yaml
# docker-compose.yml 中使用
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    image: myapp:${TAG:-latest}    # 带默认值
```

### 8.2 模板与扩展 (.yml 复用)

```yaml
# base.yml (基础配置, 不可直接用)
services:
  app:
    image: myapp
    environment:
      LOG_LEVEL: info

# dev.yml (扩展基础)
services:
  app:
    extends:
      file: base.yml
      service: app
    environment:
      LOG_LEVEL: debug
    ports:
      - "3000:3000"
```

### 8.3 x-default 环境变量

```yaml
# x- 开头是 Compose 内部配置
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"

services:
  web:
    image: nginx
    logging: *default-logging    # 引用上面的定义

  api:
    image: my-api
    logging: *default-logging
```

---

## 九、生产最佳实践

### 9.1 Compose 设计原则

```text
1. 一个项目 = 一个 docker-compose.yml
2. 服务命名清晰 (web, api, db)
3. 用环境变量配置 (不要硬编码密钥)
4. 用 .env 管理环境变量
5. 用 volume 持久化数据
6. 用 network 隔离服务
7. 用 healthcheck 保证服务健康
8. 用 restart 策略保证自动恢复
9. 用 profiles 区分环境
```

### 9.2 性能优化

```yaml
services:
  api:
    image: my-api
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### 9.3 安全最佳实践

```yaml
services:
  db:
    image: postgres
    user: "999:999"             # 非 root
    read_only: true              # 根 FS 只读
    tmpfs:
      - /tmp
      - /run
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

---

## 核心要点速记

### Compose vs docker run

```text
docker run: 单容器, 命令复杂
docker compose: 多容器, 配置式, 一键启停
```

### 核心命令

```bash
docker compose up -d           # 启动
docker compose down          # 停止并清理
docker compose logs -f       # 日志
docker compose ps            # 状态
docker compose exec <s> bash # 进入
docker compose restart       # 重启
```

### docker-compose.yml 结构

```yaml
services:     # 服务定义
volumes:      # 卷定义
networks:     # 网络定义
configs:      # 配置 (V2+)
secrets:      # 密钥 (V2+)
```

### 实战模式

```text
生产: 多服务 + 网络隔离 + 健康检查 + restart
开发: bind mount 热更新 + 暴露调试端口
测试: profiles 分组 + 临时容器
```

### Profiles 速记

```bash
docker compose --profile debug up    # 启动 debug 组
docker compose --profile monitoring up # 启动监控组
```

### Kompose 转换

```bash
kompose convert -f docker-compose.yml -o k8s/
```

---

## 参考

- **Compose 文档**: https://docs.docker.com/compose/
- **Compose 文件参考**: https://docs.docker.com/compose/compose-file/
- **Kompose**: https://kompose.io/
- **Compose V2**: https://docs.docker.com/compose/releases/migration/
