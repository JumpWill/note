# Docker 实战案例集 (Real-World Case Studies)

> 本章通过 12 个真实场景的完整案例,展示 Docker 在生产中的典型应用。

## 一、案例总览

| # | 案例 | 行业 | 核心亮点 |
|---|------|------|---------|
| 1 | Web 应用部署 (Nginx + Node.js) | 通用 | 完整 Compose |
| 2 | 数据库容器化 (MySQL/Postgres) | 通用 | 数据持久化 |
| 3 | Redis 集群部署 | 通用 | Sentinel 集群 |
| 4 | ELK 日志系统 | 运维 | 日志聚合 |
| 5 | CI/CD 流水线 (GitLab/Jenkins) | DevOps | 自动化构建部署 |
| 6 | 微服务应用 | SaaS | 多服务编排 |
| 7 | WordPress 博客 | 内容 | LAMP 容器化 |
| 8 | GitLab 自托管 | DevOps | 完整 GitLab 平台 |
| 9 | Prometheus + Grafana 监控栈 | 运维 | 完整监控 |
| 10 | Spring Boot 微服务 | Java | JVM 调优 |
| 11 | Python Flask + PostgreSQL | Python | Web 应用 |
| 12 | AI 模型部署 (GPU) | AI/ML | GPU 容器化 |

---

## 二、案例 1:Web 应用完整部署

### 场景

```text
需求:
- Nginx 反向代理
- Node.js 后端 API
- PostgreSQL 数据库
- Redis 缓存
- 一键启动
```

### 完整 docker-compose.yml

```yaml
version: '3.8'
name: webapp

services:
  nginx:
    image: nginx:alpine
    container_name: nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./html:/usr/share/nginx/html:ro
      - nginx_logs:/var/log/nginx
    depends_on:
      - api
    networks:
      - frontend
    restart: unless-stopped

  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    image: myapi:1.0
    container_name: api
    environment:
      NODE_ENV: production
      DB_HOST: postgres
      DB_PORT: 5432
      DB_USER: app
      DB_PASSWORD_FILE: /run/secrets/db_password
      REDIS_HOST: redis
      REDIS_PORT: 6379
    secrets:
      - db_password
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - frontend
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M

  postgres:
    image: postgres:15-alpine
    container_name: postgres
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: app
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
      PGDATA: /var/lib/postgresql/data/pgdata
    secrets:
      - db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: redis
    command: redis-server --appendonly yes --requirepass "${REDIS_PASSWORD}"
    environment:
      REDIS_PASSWORD_FILE: /run/secrets/redis_password
    secrets:
      - redis_password
    volumes:
      - redisdata:/data
    networks:
      - backend
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 5
    restart: unless-stopped

volumes:
  nginx_logs:
  pgdata:
  redisdata:

secrets:
  db_password:
    file: ./secrets/db_password.txt
  redis_password:
    file: ./secrets/redis_password.txt

networks:
  frontend:
  backend:
```

### 启动

```bash
# 一键启动
docker compose up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f api

# 测试
curl http://localhost/
```

---

## 三、案例 2:数据库容器化

### MySQL 8.0 生产配置

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: mysql-prod
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --max-connections=1000
      - --innodb-buffer-pool-size=2G
      - --slow-query-log=ON
      - --long-query-time=2
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    ports:
      - "3306:3306"
    volumes:
      - mysqldata:/var/lib/mysql
      - ./mysql/conf.d:/etc/mysql/conf.d:ro
      - mysql-logs:/var/log/mysql
    networks:
      - db-net
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 4G
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  mysqldata:
  mysql-logs:

networks:
  db-net:
    driver: bridge
    internal: false    # 需要的话可设 true (不暴露端口)
```

### PostgreSQL 高可用

```yaml
version: '3.8'

services:
  pg-primary:
    image: postgres:15-alpine
    container_name: pg-primary
    environment:
      POSTGRES_PASSWORD: secret
      PGDATA: /var/lib/postgresql/data/pgdata
      REPLICATION_MODE: master
      REPLICATION_USER: replicator
      REPLICATION_PASSWORD: replicator_secret
    volumes:
      - pg-primary-data:/var/lib/postgresql/data
    networks:
      - pg-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      retries: 5

  pg-replica:
    image: postgres:15-alpine
    container_name: pg-replica
    environment:
      POSTGRES_PASSWORD: secret
      PGDATA: /var/lib/postgresql/data/pgdata
      REPLICATION_MODE: slave
      REPLICATION_HOST: pg-primary
      REPLICATION_USER: replicator
      REPLICATION_PASSWORD: replicator_secret
    volumes:
      - pg-replica-data:/var/lib/postgresql/data
    networks:
      - pg-net
    depends_on:
      - pg-primary

volumes:
  pg-primary-data:
  pg-replica-data:

networks:
  pg-net:
```

---

## 四、案例 3:Redis 集群

### Redis Sentinel 高可用

```yaml
version: '3.8'

services:
  redis-master:
    image: redis:7-alpine
    container_name: redis-master
    command: redis-server /usr/local/etc/redis/redis.conf
    volumes:
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
      - redis-data:/data
    ports:
      - "6379:6379"
    networks:
      - redis-net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 3

  redis-replica-1:
    image: redis:7-alpine
    container_name: redis-replica-1
    command: redis-server /usr/local/etc/redis/redis.conf --replicaof redis-master 6379
    volumes:
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    networks:
      - redis-net
    depends_on:
      redis-master:
        condition: service_healthy

  redis-replica-2:
    image: redis:7-alpine
    container_name: redis-replica-2
    command: redis-server /usr/local/etc/redis/redis.conf --replicaof redis-master 6379
    volumes:
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    networks:
      - redis-net
    depends_on:
      redis-master:
        condition: service_healthy

  redis-sentinel-1:
    image: redis:7-alpine
    container_name: redis-sentinel-1
    command: redis-sentinel /usr/local/etc/redis/sentinel.conf
    volumes:
      - ./redis/sentinel.conf:/usr/local/etc/redis/sentinel.conf:ro
    networks:
      - redis-net

volumes:
  redis-data:

networks:
  redis-net:
```

### Redis Cluster (官方集群方案)

```bash
# 启动 6 节点 Redis Cluster
for port in 7000 7001 7002 7003 7004 7005; do
  docker run -d \
    --name redis-$port \
    -p $port:$port \
    -v $(pwd)/redis-cluster.conf:/usr/local/etc/redis/redis.conf:ro \
    redis:7-alpine \
    redis-server /usr/local/etc/redis/redis.conf \
    --cluster-enabled yes \
    --cluster-config-file nodes.conf \
    --cluster-node-timeout 5000 \
    --appendonly yes
done

# 创建集群
docker exec -it redis-7000 \
  redis-cli --cluster create \
  127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 \
  127.0.0.1:7003 127.0.0.1:7004 127.0.0.1:7005 \
  --cluster-replicas 1
```

---

## 五、案例 4:ELK 日志系统

### 完整 ELK Stack

```yaml
version: '3.8'

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: elasticsearch
    environment:
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms512m -Xmx512m
      - xpack.security.enabled=false
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - es-data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
    networks:
      - elk

  logstash:
    image: docker.elastic.co/logstash/logstash:8.11.0
    container_name: logstash
    depends_on:
      - elasticsearch
    volumes:
      - ./logstash/pipeline:/usr/share/logstash/pipeline:ro
      - ./logstash/config/logstash.yml:/usr/share/logstash/config/logstash.yml:ro
    ports:
      - "5044:5044"
    networks:
      - elk

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    container_name: kibana
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch
    ports:
      - "5601:5601"
    networks:
      - elk

  app:
    image: myapp:1.0
    depends_on:
      - logstash
    logging:
      driver: gelf
      options:
        gelf-address: tcp://logstash:5044
        tag: myapp

volumes:
  es-data:

networks:
  elk:
```

### Filebeat 收集应用日志

```yaml
version: '3.8'

services:
  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    container_name: filebeat
    user: root
    volumes:
      - ./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - elk
```

```yaml
# filebeat.yml
filebeat.inputs:
- type: container
  paths:
    - /var/lib/docker/containers/*/*.log

processors:
- add_docker_metadata: ~

output.logstash:
  hosts: ["logstash:5044"]
```

---

## 六、案例 5:CI/CD 流水线

### GitLab CI/CD + Docker

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

variables:
  DOCKER_REGISTRY: registry.gitlab.com/mygroup/myapp
  DOCKER_HOST: registry.gitlab.com
  APP_NAME: myapp

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $DOCKER_HOST
    - docker build -t ${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA} -t ${DOCKER_REGISTRY}:latest .
    - docker push ${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA}
    - docker push ${DOCKER_REGISTRY}:latest

deploy:
  stage: deploy
  image: alpine
  script:
    - apk add --no-cache openssh-client
    - ssh -o StrictHostKeyChecking=no deploy@prod "cd /app && \
        docker pull ${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA} && \
        docker compose up -d"
  environment:
    name: production
  only:
    - main
```

### Jenkins Pipeline

```groovy
// Jenkinsfile
pipeline {
    agent any

    stages {
        stage('Build') {
            steps {
                sh 'docker build -t myapp:${BUILD_NUMBER} .'
            }
        }
        stage('Test') {
            steps {
                sh 'docker run --rm myapp:${BUILD_NUMBER} npm test'
            }
        }
        stage('Push') {
            steps {
                sh 'docker login -u $DOCKER_USER -p $DOCKER_PASS'
                sh 'docker push myregistry/myapp:${BUILD_NUMBER}'
            }
        }
        stage('Deploy') {
            steps {
                sh 'ssh deploy@prod "docker service update --image myregistry/myapp:${BUILD_NUMBER} myapp"'
            }
        }
    }
}
```

---

## 七、案例 6:微服务完整部署

### Spring Cloud 微服务

```yaml
version: '3.8'

services:
  # 1. Eureka 服务发现
  eureka:
    image: myregistry/spring-cloud-eureka:1.0
    ports:
      - "8761:8761"
    networks:
      - backend
    deploy:
      replicas: 1

  # 2. 配置中心
  config:
    image: myregistry/spring-cloud-config:1.0
    depends_on:
      - eureka
    ports:
      - "8888:8888"
    networks:
      - backend

  # 3. 网关
  gateway:
    image: myregistry/spring-cloud-gateway:1.0
    depends_on:
      - eureka
    ports:
      - "8080:8080"
    networks:
      - frontend
      - backend
    deploy:
      replicas: 2

  # 4. 业务服务
  user-service:
    image: myregistry/user-service:1.0
    depends_on:
      - eureka
      - mysql
    environment:
      EUREKA_SERVER: http://eureka:8761/eureka
    networks:
      - backend
    deploy:
      replicas: 3

  order-service:
    image: myregistry/order-service:1.0
    depends_on:
      - eureka
      - mysql
      - redis
    networks:
      - backend
    deploy:
      replicas: 3

  # 5. 数据库
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: secret
    volumes:
      - mysqldata:/var/lib/mysql
    networks:
      - backend

  redis:
    image: redis:7-alpine
    networks:
      - backend

volumes:
  mysqldata:

networks:
  frontend:
  backend:
```

---

## 八、案例 7:WordPress 部署

```yaml
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
      WORDPRESS_DB_PASSWORD: ${WORDPRESS_DB_PASSWORD}
      WORDPRESS_DB_NAME: wordpress
      WORDPRESS_TABLE_PREFIX: wp_
    volumes:
      - wordpress_data:/var/www/html
      - ./uploads.ini:/usr/local/etc/php/conf.d/uploads.ini
    depends_on:
      db:
        condition: service_healthy
    networks:
      - wordpress-net
    restart: unless-stopped

  db:
    image: mysql:8.0
    container_name: wordpress-db
    environment:
      MYSQL_DATABASE: wordpress
      MYSQL_USER: wordpress
      MYSQL_PASSWORD: ${WORDPRESS_DB_PASSWORD}
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}
    volumes:
      - db_data:/var/lib/mysql
    networks:
      - wordpress-net
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      retries: 5
    restart: unless-stopped

volumes:
  wordpress_data:
  db_data:

networks:
  wordpress-net:
```

```bash
# .env
WORDPRESS_DB_PASSWORD=secretpassword

# 启动
docker compose up -d

# 访问 http://localhost:8080
```

---

## 九、案例 8:GitLab 自托管

```yaml
version: '3.8'

services:
  gitlab:
    image: gitlab/gitlab-ce:latest
    container_name: gitlab
    hostname: gitlab.example.com
    environment:
      GITLAB_OMNIBUS_CONFIG: |
        external_url 'https://gitlab.example.com'
        # 邮件配置
        gitlab_rails['smtp_enable'] = true
        gitlab_rails['smtp_address'] = "smtp.example.com"
        # SSH
        gitlab_rails['gitlab_shell_ssh_port'] = 2222
    ports:
      - "443:443"     # HTTPS
      - "80:80"       # HTTP
      - "2222:22"     # SSH
    volumes:
      - gitlab-config:/etc/gitlab
      - gitlab-logs:/var/log/gitlab
      - gitlab-data:/var/opt/gitlab
    networks:
      - gitlab-net
    restart: unless-stopped
    shm_size: '256m'

volumes:
  gitlab-config:
  gitlab-logs:
  gitlab-data:

networks:
  gitlab-net:
```

---

## 十、案例 9:Prometheus + Grafana 监控栈

### 完整监控

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.enable-lifecycle'
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - monitor
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    ports:
      - "3000:3000"
    networks:
      - monitor
    depends_on:
      - prometheus
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:v0.26.0
    container_name: alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
    volumes:
      - ./alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    ports:
      - "9093:9093"
    networks:
      - monitor
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    privileged: true
    networks:
      - monitor
    deploy:
      mode: global    # Swarm 每节点一个

  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    pid: host
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
    networks:
      - monitor
    deploy:
      mode: global

volumes:
  prometheus-data:
  grafana-data:

networks:
  monitor:
    driver: overlay
```

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: node-exporter
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: cadvisor
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: docker
    static_configs:
      - targets: ['host.docker.internal:9323']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - "alerts/*.yml"
```

---

## 十一、案例 10:Spring Boot 应用完整部署

### 多阶段 Dockerfile

```dockerfile
# 构建阶段
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /build

# 缓存依赖
COPY pom.xml .
RUN mvn dependency:go-offline

COPY src ./src
RUN mvn package -DskipTests

# 运行时
FROM eclipse-temurin:17-jre-alpine

LABEL maintainer="devops@example.com"

# 创建非 root 用户
RUN addgroup -S spring && adduser -S -G spring spring

WORKDIR /app

# 复制构建产物
COPY --from=builder /build/target/*.jar app.jar

# JVM 调优
ENV JAVA_OPTS="-XX:+UseContainerSupport \
                -XX:MaxRAMPercentage=75.0 \
                -XX:+UseG1GC \
                -XX:+HeapDumpOnOutOfMemoryError"

USER spring

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -qO- http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar app.jar"]
```

### docker-compose 部署

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    image: myapp:1.0
    environment:
      SPRING_PROFILES_ACTIVE: production
      SPRING_DATASOURCE_URL: jdbc:postgresql://db:5432/mydb
      SPRING_DATASOURCE_USERNAME: app
      SPRING_DATASOURCE_PASSWORD_FILE: /run/secrets/db_password
      JAVA_OPTS: "-Xmx768m -Xms512m"
    secrets:
      - db_password
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app-net
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8080/actuator/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: mydb
      POSTGRES_USER: app
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - app-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 10s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - app
    networks:
      - app-net

secrets:
  db_password:
    file: ./secrets/db_password.txt

volumes:
  pgdata:

networks:
  app-net:
```

---

## 十二、案例 11:Python Flask + PostgreSQL

### Dockerfile

```dockerfile
FROM python:3.11-slim

LABEL maintainer="devops@example.com"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 先复制依赖文件 (利用缓存)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY . .

# 创建用户
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

EXPOSE 5000

HEALTHCHECK --interval=30s \
  CMD curl -f http://localhost:5000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--access-logfile", "-", "app:app"]
```

### docker-compose

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      DATABASE_URL: postgresql://app:secret@db:5432/myapp
      FLASK_ENV: production
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app-net

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: app
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - app-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d myapp"]
      interval: 10s

  redis:
    image: redis:7-alpine
    networks:
      - app-net

volumes:
  pgdata:

networks:
  app-net:
```

---

## 十三、案例 12:AI 模型 GPU 容器化

### GPU 推理服务

```dockerfile
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

LABEL maintainer="ai@example.com"

# 安装 Python 和依赖
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制代码
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# 模型下载 (生产建议挂载)
# RUN python3 download_model.py

EXPOSE 8000

HEALTHCHECK --interval=30s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose GPU 支持

```yaml
version: '3.8'

services:
  ai-inference:
    build: .
    image: ai-model:1.0
    runtime: nvidia              # NVIDIA 运行时
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: compute,utility
    volumes:
      - ./models:/app/models:ro
      - ./logs:/app/logs
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    ports:
      - "8000:8000"
    networks:
      - ai-net

  ai-loadbalancer:
    image: nginx:alpine
    ports:
      - "80:80"
    depends_on:
      - ai-inference
    networks:
      - ai-net

networks:
  ai-net:
```

```bash
# 启动
docker compose up -d

# 测试
curl http://localhost/predict

# 查看 GPU 使用
docker exec ai-inference nvidia-smi
```

---

## 十四、生产最佳实践总结

### 14.1 镜像最佳实践

```text
1. 使用最小基础镜像 (alpine / distroless)
2. 多阶段构建
3. 合并 RUN, 清理缓存
4. .dockerignore 排除
5. HEALTHCHECK 必须
6. 镜像签名 + 扫描
7. 不可变 tag (不用 latest)
```

### 14.2 Compose 最佳实践

```text
1. 一个项目一个 docker-compose.yml
2. 用 .env 管理配置
3. 用 secrets 管理密钥
4. 用 networks 隔离服务
5. 用 healthcheck + depends_on
6. 用 restart 策略
7. 用 deploy.resources 限资源
```

### 14.3 安全最佳实践

```text
1. 非 root 用户
2. 只读根 FS
3. 最小 capability
4. no-new-privileges
5. 自定义网络隔离
6. 镜像签名 + 漏洞扫描
7. 日志审计
```

### 14.4 监控最佳实践

```text
1. cAdvisor + Prometheus + Grafana
2. 关键告警规则
3. 日志集中收集 (Loki/ELK)
4. 节点 + 容器 + 应用三层监控
5. 定期 review Dashboard
```

---

## 核心要点速记

### 案例选型速记

```text
Web 应用  → Nginx + Node.js + PostgreSQL + Redis
数据库    → MySQL/Postgres + 数据卷 + 主从
缓存      → Redis Cluster / Sentinel
日志      → ELK / Loki + Promtail
监控      → Prometheus + Grafana + cAdvisor
CI/CD    → GitLab CI + Docker-in-Docker
微服务    → Spring Cloud + 服务网格
WordPress → 官方镜像 + MySQL
GitLab   → 官方镜像 + 大量存储
Spring Boot → 多阶段 + JVM 调优
Python Flask → slim + gunicorn
AI/ML    → CUDA + GPU runtime
```

### 实战模板

```yaml
# 标准 web app template
services:
  web:
    image: nginx:alpine
    ports: ["80:80"]
    networks: [frontend]
  api:
    build: ./api
    depends_on: [db]
    networks: [frontend, backend]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
  db:
    image: postgres:15-alpine
    volumes: [dbdata:/var/lib/postgresql/data]
    networks: [backend]

volumes:
  dbdata:

networks:
  frontend:
  backend:
```

### 关键配置

```text
- healthcheck 全部服务
- depends_on + condition: service_healthy
- networks 隔离
- secrets 管理密钥
- volumes 持久化
- resources 限制
- restart unless-stopped
```

---

## 参考

- **Docker Hub**: https://hub.docker.com/
- **Docker Compose 示例**: https://github.com/docker/awesome-compose
- **Awesome Docker**: https://github.com/veggiemonk/awesome-docker
- **Docker 官方文档**: https://docs.docker.com/
- **生产 Dockerfile**: https://docs.docker.com/develop/develop-images/dockerfile_best-practices/
