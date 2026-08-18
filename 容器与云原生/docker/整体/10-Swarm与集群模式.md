# Docker Swarm 与集群模式 (Swarm Mode)

> 本章详解 Docker Swarm 集群编排:Swarm 架构、服务部署、栈管理、密钥与配置。

## 一、Docker Swarm 概述

### 1.1 什么是 Swarm

**Docker Swarm** 是 Docker 官方提供的**原生集群编排工具**(2016 年 Docker 1.12 GA)。

```text
Docker Swarm 特点:
1. 与 Docker Engine 集成 (原生)
2. 使用 Docker API (与单机兼容)
3. 内置服务发现 (DNS)
4. 内置负载均衡 (Ingress)
5. 内置密钥与配置管理
6. 滚动更新
7. 多主机网络 (overlay)

K8s vs Swarm:
- Swarm: 简单, 适合中小规模, 与 Docker 集成好
- K8s: 复杂, 适合大规模生产, 生态丰富
```

### 1.2 Swarm 模式 vs Swarm Classic

```text
Swarm Classic (1.12 之前):
  - 独立工具
  - 与 Docker Engine 分离

Swarm Mode (1.12+, 当前):
  - Docker Engine 内置
  - 命令: docker swarm / docker service / docker stack
  - 推荐使用
```

---

## 二、Swarm 架构

### 2.1 角色与节点

```text
Swarm 集群节点:

1. Manager 节点 (Manager)
   - 集群管理 (Raft 共识)
   - 调度服务
   - API 入口
   - 推荐 3 或 5 个 (奇数)

2. Worker 节点 (Worker)
   - 运行实际服务
   - 接受 Manager 调度
   - 可伸缩

3. 角色转换
   - docker node promote <node>    # Worker → Manager
   - docker node demote <node>      # Manager → Worker
```

### 2.2 Raft 共识

```text
Manager 节点间用 Raft 协议:

- N 个 Manager 节点
- 容忍 N/2 节点故障
- 推荐 3 或 5 个 Manager

例:
1 Manager  : 不容忍故障 (单点)
3 Manager: 容忍 1 故障
5 Manager: 容忍 2 故障
7 Manager: 容忍 3 故障 (通常足够)
```

### 2.3 Swarm 服务发现

```text
Swarm 内置 DNS:
- 每个服务有 VIP (Virtual IP)
- 容器内可解析: <service-name>
- 自动负载均衡

例:
- service "web" 创建 → VIP 10.0.0.10
- service "api" 创建 → VIP 10.0.0.11
- web 容器内 ping api → 解析到 api VIP

External DNS (Nginx Ingress):
- Swarm 内置 Nginx Ingress
- 路由外部流量到服务
- 自动配置
```

### 2.4 完整架构

```text
┌────────────────────────────────────────────────�
│          Docker Swarm 集群                       │
│                                                │
│  ┌─────────────�  ┌─────────────┐             │
│  │  Manager-1  │←→│  Manager-2  │  (Raft)    │
│  └─────────────�  └─────────────┘             │
│         ↓                  ↓                   │
│  ┌─────────────┐                            │
│  │  Manager-3  │                            │
│  └─────────────┘                            │
│         ↓                                       │
│  ┌─────────────┐  ┌─────────────┐           │
│  │   Worker-1  │  │   Worker-2  │           │
│  │  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐│          │
│  │  │Task1│  │Task2│  │Task3│  │Task4││          │
│  │  └─────┘  └─────┘  └─────┘  └─────┘│          │
│  └─────────────┘  └─────────────┘           │
│                                                │
│  Overlay Network (跨主机容器通信)               │
└────────────────────────────────────────────────┘
```

---

## 三、初始化 Swarm

### 3.1 初始化集群

```bash
# 1. 在第一个节点初始化 Manager
docker swarm init --advertise-addr 10.0.0.10

# 输出:
# Swarm initialized: current node (xxx) is now a manager.
#
# To add a worker to this swarm, run the following command:
#   docker swarm join --token SWMTKN-xxx... 10.0.0.10:2377
#
# To add a manager to this swarm, run 'docker swarm join-token manager'

# 2. 获取加入 token
docker swarm join-token manager
docker swarm join-token worker
```

### 3.2 加入集群

```bash
# Worker 节点加入
docker swarm join --token SWMTKN-xxx... 10.0.0.10:2377

# Manager 节点加入
docker swarm join --token SWMTKN-xxx... 10.0.0.10:2377

# 查看集群节点
docker node ls
```

### 3.3 Swarm 模式管理命令

```bash
# 查看 Swarm 状态
docker info | grep -A 5 Swarm

# 查看 Manager 节点 (含 Raft 状态)
docker node ls
docker node inspect self --pretty

# 查看集群令牌
docker swarm join-token manager
docker swarm join-token worker

# 离开 Swarm
docker swarm leave        # Worker 离开
docker swarm leave --force  # Manager 离开 (强制)

# 在 Manager 上移除离开的节点
docker node rm <node-id>

# 更新 Swarm 配置
docker swarm update \
  --task-history-limit 5 \
  --snapshot-interval 10000 \
  --heartbeat-interval 5
```

---

## 四、Swarm 服务

### 4.1 服务 vs 容器

```text
容器 (Container):
- 单机运行
- 直接 docker run

服务 (Service):
- Swarm 中定义
- 自动伸缩
- 滚动更新
- 多副本

转换:
- docker run 命令 → 等同于 Swarm 中的一个 task
- docker service create → 服务 (含伸缩、更新策略等)
```

### 4.2 创建服务

```bash
# 基础创建
docker service create --name web nginx:alpine

# 指定副本数
docker service create --name web --replicas 3 nginx:alpine

# 端口映射 (Ingress 模式)
docker service create --name web --publish 80:80 nginx:alpine

# 自定义网络
docker network create --driver overlay my-net
docker service create --name web --network my-net nginx:alpine

# 环境变量
docker service create --name web \
  -e DEBUG=false \
  -e DB_HOST=db \
  nginx:alpine

# 挂载卷
docker service create --name web \
  --mount type=volume,source=mydata,target=/data \
  nginx:alpine

# 命令覆盖
docker service create --name web \
  --entrypoint "nginx" \
  --command "-g 'daemon off;'" \
  nginx:alpine

# 资源限制
docker service create --name web \
  --limit-cpu 0.5 \
  --limit-memory 512M \
  nginx:alpine

# 完整示例
docker service create \
  --name web \
  --replicas 3 \
  --publish 80:80 \
  --network my-net \
  --env NODE_ENV=production \
  --mount type=volume,source=appdata,target=/app/data \
  --limit-cpu 0.5 \
  --limit-memory 512M \
  --update-parallelism 1 \
  --update-delay 10s \
  --restart-condition on-failure \
  myapp:1.0
```

### 4.3 服务操作

```bash
# 列出服务
docker service ls
docker service ps web        # 服务任务列表
docker service ps --no-trunc web

# 查看服务详情
docker service inspect web
docker service inspect --pretty web

# 服务日志
docker service logs web
docker service logs -f web   # 跟踪
docker service logs --tail 100 web

# 扩缩服务
docker service scale web=5
docker service scale web=2 db=3

# 更新服务 (滚动更新)
docker service update \
  --image myapp:2.0 \
  --update-parallelism 2 \
  --update-delay 30s \
  web

# 回滚
docker service update --rollback web

# 删除服务
docker service rm web
```

### 4.4 滚动更新策略

```bash
# 创建时指定
docker service create --name web \
  --update-parallelism 2 \
  --update-delay 10s \
  --update-failure-action rollback \
  --update-max-failure-ratio 0.3 \
  myapp:1.0

# 参数说明:
# --update-parallelism 2     # 同时更新 2 个 task
# --update-delay 10s         # 每个批次间隔 10s
# --update-failure-action rollback  # 失败回滚
# --update-max-failure-ratio 0.3  # 失败率 > 30% 暂停
```

### 4.5 限制与预留

```bash
# 创建时设置
docker service create --name web \
  --limit-cpu 1.0 \
  --limit-memory 1G \
  --reserve-cpu 0.5 \
  --reserve-memory 512M \
  myapp:1.0

# 更新限制
docker service update --limit-cpu 2.0 web

# 资源类型:
# CPU: --limit-cpu (单位: 核)
# 内存: --limit-memory (单位: B/K/M/G)
# 预留: --reserve-cpu / --reserve-memory (调度时保证)
```

---

## 五、Stack (多服务编排)

### 5.1 Stack 概念

**Stack** 是 Compose 文件在 Swarm 模式下的部署单位。

```text
Stack = docker-compose.yml + Swarm 集群

对比:
docker compose up        # 单机
docker stack deploy     # Swarm 集群
```

### 5.2 docker-compose.yml 部署到 Swarm

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    image: nginx:alpine
    ports:
      - "80:80"
    networks:
      - frontend
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  api:
    image: my-api:latest
    networks:
      - frontend
      - backend
    deploy:
      replicas: 2

  db:
    image: postgres:15-alpine
    networks:
      - backend
    environment:
      POSTGRES_PASSWORD: secret
    volumes:
      - dbdata:/var/lib/postgresql/data
    deploy:
      placement:
        constraints:
          - node.role == worker

volumes:
  dbdata:

networks:
  frontend:
  backend:

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

```bash
# 部署
docker stack deploy -c docker-compose.yml myapp

# 查看 stack
docker stack ls

# 查看服务
docker stack services myapp

# 查看任务
docker stack ps myapp

# 删除
docker stack rm myapp
```

---

## 六、Swarm 网络

### 6.1 Overlay 网络

```bash
# 创建 overlay 网络
docker network create -d overlay --attachable my-overlay

# 服务加入网络
docker service create --name web --network my-overlay nginx

# 跨主机容器通信
# service "web" 创建 VIP 10.0.0.10
# service "api" 创建 VIP 10.0.0.11
# api 容器内可访问 web (通过 VIP)
```

### 6.2 加密 Overlay 网络

```bash
# Swarm 默认开启 IPSEC 加密
docker network create -d overlay \
  --opt encrypted \
  my-secure-overlay
```

### 6.3 服务发现

```bash
# Swarm 内置 DNS
docker service create --name web nginx

# 任何 swarm 容器内都可解析 "web"
docker exec <container> nslookup web
```

---

## 七、密钥与配置 (Secrets & Configs)

### 7.1 Secrets

```bash
# 创建 secret
echo "secret_password" | docker secret create db_password -

# 从文件创建
docker secret create db_password ./password.txt

# 列出 secrets
docker secret ls

# 服务使用 secret
docker service create --name db \
  --secret db_password \
  -e POSTGRES_PASSWORD_FILE=/run/secrets/db_password \
  postgres

# 容器内 secret 挂载到 /run/secrets/<secret-name>
# 文件权限 0440, gid 0 (root)
```

### 7.2 Configs

```bash
# 创建 config
docker config create nginx.conf ./nginx.conf

# 服务使用
docker service create --name web \
  --config source=nginx.conf,target=/etc/nginx/nginx.conf \
  nginx

# 支持环境变量注入
docker service create --name web \
  --config source=app.properties,target=/app/app.properties \
  my-app
```

---

## 八、生产实战

### 8.1 高可用 Swarm 集群

```text
推荐生产架构:
- 5 个 Manager 节点 (跨 3 AZ)
- 10+ 个 Worker 节点
- 内部负载均衡 (HAProxy/Nginx)
- 外部负载均衡 (云 LB)
```

### 8.2 多服务完整部署

```bash
# 1. 初始化 Swarm
docker swarm init --advertise-addr 10.0.0.10

# 2. 加入其他节点
# Manager 节点
for host in manager-2 manager-3; do
  ssh $host "docker swarm join --token $(docker swarm join-token -q manager) 10.0.0.10:2377"
done

# Worker 节点
for host in worker-1 worker-2 worker-3; do
  ssh $host "docker swarm join --token $(docker swarm join-token -q worker) 10.0.0.10:2377"
done

# 3. 创建 overlay 网络
docker network create --driver overlay --attachable backend
docker network create --driver overlay --attachable frontend

# 4. 部署服务
docker service create --name db \
  --network backend \
  --replicas 1 \
  --constraint 'node.role==worker' \
  -e POSTGRES_PASSWORD=secret \
  postgres:15-alpine

docker service create --name api \
  --network frontend \
  --network backend \
  --replicas 3 \
  my-api:latest

docker service create --name web \
  --network frontend \
  --replicas 3 \
  --publish 80:80 \
  nginx:alpine

# 5. 验证
docker service ls
docker stack services
```

### 8.3 灰度发布

```bash
# 创建主版本
docker service create --name web-v1 \
  --replicas 9 \
  --publish 80:80 \
  nginx:1.25

# 加入新版本 (少量副本)
docker service create --name web-v2 \
  --replicas 1 \
  nginx:1.26

# Ingress 路由 10% 到 web-v2 (需自定义 Ingress)
# 或者直接删除 web-v1, 用 web-v2 替代
docker service update --image nginx:1.26 web-v1
```

### 8.4 监控 Swarm

```bash
# 查看 Swarm 节点状态
docker node ls
docker node inspect <node-id>

# 查看服务状态
docker service ls
docker service ps <service>

# 日志
docker service logs <service>

# Prometheus 集成
# - Swarm 节点指标 (需 cAdvisor)
# - 服务指标 (需 docker-exporter)

# 推荐工具:
# - cAdvisor (容器指标)
# - Portainer (Swarm Web UI)
# - Swarmpit (Swarm 管理 UI)
```

---

## 九、Swarm 实战技巧

### 9.1 Stack 文件示例

```yaml
# stack-monitor.yml (监控系统 stack)
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    networks:
      - monitor

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: secret
    volumes:
      - grafana-data:/var/lib/grafana
    ports:
      - "3000:3000"
    networks:
      - monitor

  node-exporter:
    image: prom/node-exporter:latest
    pid: host
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - monitor
    deploy:
      mode: global    # 每节点一个

volumes:
  grafana-data:

networks:
  monitor:
    driver: overlay
```

```bash
docker stack deploy -c stack-monitor.yml monitor
```

### 9.2 节点标签与约束

```bash
# 节点加标签
docker node update --label-add environment=production node-1
docker node update --label-add disk=ssd node-1

# 服务使用节点约束
docker service create --name web \
  --constraint 'node.labels.environment == production' \
  --constraint 'node.labels.disk == ssd' \
  nginx

# 节点选择 (placement)
docker service create --name web \
  --placement-pref spread=node.labels.zone \
  nginx
```

### 9.3 调试 Swarm 服务

```bash
# 查看服务任务详情
docker service ps --no-trunc <service>

# 进入任务容器
docker exec -it <task-container> bash

# 服务日志
docker service logs --tail 200 <service>

# 查看服务配置
docker service inspect --pretty <service>

# 调度约束
docker service update --constraint-add 'node.role==worker' <service>
```

---

## 核心要点速记

### Swarm 架构

```text
Manager 节点 (≥3):  Raft 共识, 调度
Worker 节点:        运行任务
Overlay 网络:       跨主机容器通信
Ingress 网络:      外部流量入口
```

### Swarm vs K8s

```text
Swarm: 简单, 与 Docker 集成, 中小规模
K8s:   复杂, 生态丰富, 大规模生产
```

### Swarm 命令速查

```bash
docker swarm init                    # 初始化
docker swarm join --token ...        # 加入
docker node ls                       # 节点列表
docker service create ...            # 创建服务
docker service ls                    # 服务列表
docker service scale <s>=3           # 伸缩
docker service update --image ...    # 更新
docker stack deploy -c file.yml      # 部署 stack
```

### docker service create 关键参数

```text
--name      服务名
--replicas  副本数
--publish   端口映射
--network   网络
--env       环境变量
--mount     挂载卷
--secret    密钥
--config    配置
--limit-cpu    CPU 限制
--limit-memory 内存限制
--update-parallelism  滚动并发
--update-delay        滚动间隔
--restart-condition   重启策略
```

### Stack vs Compose

```text
docker compose: 单机多容器
docker stack:  Swarm 集群多服务

格式相同 (docker-compose.yml), 但有 Swarm 专属字段 (deploy, secrets, configs)
```

### 高可用架构

```text
- 5 个 Manager 节点 (跨 3 AZ)
- 10+ 个 Worker 节点
- 外部 LB → Swarm Ingress → 服务
```

---

## 参考

- **Swarm 模式**: https://docs.docker.com/engine/swarm/
- **docker service**: https://docs.docker.com/engine/reference/commandline/service/
- **docker stack**: https://docs.docker.com/engine/reference/commandline/stack/
- **Swarm 网络**: https://docs.docker.com/network/overlay/
- **Swarm 密钥**: https://docs.docker.com/engine/swarm/secrets/
- **Portainer** (Swarm UI): https://www.portainer.io/
