# Docker 生产实践与生态 (Production Practices & Ecosystem)

> 本章讲解 Docker 生产部署实践、CI/CD 集成、容器编排生态对比、迁移到 Kubernetes 与未来趋势。

## 一、生产部署最佳实践

### 1.1 镜像选择

```text
镜像选择优先级:

1. 官方镜像 (Docker Hub Official)
   - 高质量保证
   - 定期安全更新
   - 完整文档
   例: nginx, mysql, postgres, redis, node, python, golang

2. 认证镜像 (Docker Hub Verified)
   - 商业维护
   - 例: bitnami, linuxserver.io, mysql/mysql-server

3. 社区镜像 (普通)
   - 需评估后使用
   - 检查下载量、stars、更新时间

4. 自建镜像
   - 推荐用于业务镜像
   - 基于官方基础镜像
   - 多阶段构建
```

### 1.2 镜像标签策略

```text
推荐 tag 命名:
- v1.0.0 (SemVer 严格版本)
- v1.0.0-alpine (变体)
- v1.0.0-arm64 (架构)
- 1.0.0 (纯版本)
- stable (稳定版)

避免:
- latest (生产环境)
- test, dev, debug (开发版本)
- 相同 tag 重复推送 (违反不可变原则)

CI/CD 流水线:
1. Git tag (v1.0.0)
   ↓
2. 触发构建
   ↓
3. 生成镜像 myapp:v1.0.0
   ↓
4. 同一 commit 只能生成一个镜像 (digest 唯一)
   ↓
5. 推送镜像
```

### 1.3 镜像保留策略

```bash
# Harbor 标签保留策略 (推荐)
# Harbor UI → 项目 → 配置 → 标签保留

# 推荐策略:
# - 保留最近 10 个标签
# - 保留 30 天内创建的标签
# - 永不删除有 latest 标签的镜像 (可选)

# 手动清理
docker image prune -a --filter "until=720h"   # 清理 30 天前

# 自动清理 (crontab)
0 3 * * 0 docker image prune -af
```

### 1.4 容器运行配置

```bash
# 生产标准配置
docker run -d \
  --name myapp \
  --restart unless-stopped \           # 自动重启
  --user 1000:1000 \                   # 非 root
  --read-only \                       # 根 FS 只读
  --tmpfs /tmp:rw,size=100m \         # 临时目录
  --cap-drop=ALL \                    # 删除所有 capability
  --cap-add=NET_BIND_SERVICE \         # 只加必要
  --security-opt no-new-privileges \   # 禁止提权
  --memory 1g \                        # 内存限制
  --cpus 1.0 \                         # CPU 限制
  --pids-limit 100 \                  # 进程数限制
  --log-driver json-file \             # JSON 日志
  --log-opt max-size=10m \             # 日志大小
  --log-opt max-file=3 \              # 日志备份数
  --health-cmd "curl -f http://localhost:8080/health || exit 1" \
  --health-interval 30s \              # 健康检查
  --health-timeout 5s \
  --health-retries 3 \
  myapp:1.0
```

### 1.5 资源限制策略

```text
资源限制原则:
1. requests 必须设 (调度依据)
2. limits 推荐设 (防止资源耗尽)
3. CPU 限流 (throttled, 不杀进程)
4. 内存超限 → OOMKilled
5. requests + limits = 1:1~1:2 比较合理

资源预留 (生产):
- Web 服务: requests 50%, limits 100%
- 批处理:  无 limits (用完所有资源)
- 数据库: requests = limits (避免抖动)
```

---

## 二、CI/CD 集成

### 2.1 完整 CI/CD 流水线

```text
┌─────────────────────────────────────────────────────────┐
│                     CI/CD 流水线                          │
│                                                          │
│  1. 代码提交 (Git Push)                                  │
│     ↓                                                    │
│  2. 触发 CI (GitHub Actions / GitLab CI / Jenkins)      │
│     ↓                                                    │
│  3. 代码检查 (Lint, Type Check)                          │
│     ↓                                                    │
│  4. 单元测试 + 集成测试                                  │
│     ↓                                                    │
│  5. 构建 Docker 镜像                                    │
│     ↓                                                    │
│  6. 镜像扫描 (Trivy)                                    │
│     ↓                                                    │
│  7. 镜像签名 (Cosign)                                   │
│     ↓                                                    │
│  8. 推送 Registry (Harbor / Docker Hub)                 │
│     ↓                                                    │
│  9. 触发 CD (ArgoCD / Jenkins)                          │
│     ↓                                                    │
│  10. 部署到 Staging 环境                                 │
│     ↓ 自动化测试通过                                     │
│  11. 部署到 Production 环境 (蓝绿/灰度)                  │
│     ↓                                                    │
│  12. 监控告警 (Prometheus + Alertmanager)               │
└─────────────────────────────────────────────────────────┘
```

### 2.2 GitLab CI/CD 完整示例

```yaml
# .gitlab-ci.yml
stages:
  - lint
  - test
  - build
  - scan
  - sign
  - deploy

variables:
  DOCKER_REGISTRY: harbor.example.com/library
  APP_NAME: myapp

# 1. Lint
lint:
  stage: lint
  image: golang:1.21
  script:
    - golangci-lint run

# 2. Test
test:
  stage: test
  image: golang:1.21
  services:
    - postgres:15
  variables:
    POSTGRES_DB: test
    POSTGRES_USER: test
    POSTGRES_PASSWORD: test
  script:
    - go test -v -cover ./...

# 3. Build
build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $DOCKER_REGISTRY
    - docker build -t ${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA} .
    - docker push ${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA}
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# 4. Scan (Trivy)
scan:
  stage: scan
  image: aquasec/trivy:latest
  script:
    - trivy image --exit-code 1 --severity HIGH,CRITICAL ${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA}
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# 5. Sign (Cosign)
sign:
  stage: sign
  image: sigstore/cosign:latest
  script:
    - cosign sign --keyless ${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA}
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# 6. Deploy to staging
deploy:staging:
  stage: deploy
  script:
    - ssh deploy@staging "kubectl set image deployment/myapp myapp=${DOCKER_REGISTRY}:${CI_COMMIT_SHORT_SHA} -n staging"
    - ssh deploy@staging "kubectl rollout status deployment/myapp -n staging"
  environment:
    name: staging
  rules:
    - if: $CI_COMMIT_BRANCH == "main"

# 7. Deploy to production (manual)
deploy:production:
  stage: deploy
  script:
    - ssh deploy@prod "kubectl set image deployment/myapp myapp=${DOCKER_REGISTRY}:${CI_COMMIT_TAG} -n production"
    - ssh deploy@prod "kubectl rollout status deployment/myapp -n production"
  environment:
    name: production
  when: manual
  rules:
    - if: $CI_COMMIT_TAG
```

### 2.3 GitHub Actions 示例

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Login to Harbor
      uses: docker/login-action@v3
      with:
        registry: harbor.example.com
        username: ${{ secrets.HARBOR_USER }}
        password: ${{ secrets.HARBOR_PASS }}

    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          harbor.example.com/library/myapp:${{ github.sha }}
          harbor.example.com/library/myapp:latest
        cache-from: type=registry,ref=harbor.example.com/library/myapp:buildcache
        cache-to: type=registry,ref=harbor.example.com/library/myapp:buildcache,mode=max

    - name: Scan with Trivy
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: harbor.example.com/library/myapp:${{ github.sha }}
        severity: HIGH,CRITICAL
        exit-code: '1'

    - name: Sign with Cosign
      uses: sigstore/cosign-installer@main

    - name: Sign image
      env:
        COSIGN_EXPERIMENTAL: 1
      run: |
        cosign sign --yes harbor.example.com/library/myapp@${{ steps.build.outputs.digest }}

    - name: Deploy
      if: github.ref == 'refs/heads/main'
      run: |
        ssh deploy@prod "kubectl set image deployment/myapp myapp=harbor.example.com/library/myapp:${{ github.sha }} -n production"
```

---

## 三、容器编排生态对比

### 3.1 主流编排工具

| 工具 | 类型 | 适用规模 | 复杂度 | 特点 |
|------|------|---------|--------|------|
| **Docker Compose** | 单机 | 小 | 低 | 简单, 开发测试 |
| **Docker Swarm** | 集群 | 中小 | 中 | 与 Docker 集成好 |
| **Kubernetes** | 集群 | 大 | 高 | 业界标准, 生态丰富 |
| **Nomad** | 集群 | 中 | 中 | HashiCorp 通用编排 |
| **Mesos** | 集群 | 大 | 极高 | 大数据生态 |

### 3.2 Kubernetes vs Docker Swarm

```text
┌────────────────────┬─────────────────────┐
│   Kubernetes        │   Docker Swarm      │
├────────────────────┼─────────────────────┤
│ CNCF 毕业项目       │ Docker 原生          │
│ 市场份额 80%+        │ 市场份额 5%         │
│ 生态最丰富           │ 生态有限             │
│ 学习曲线陡           │ 简单易用             │
│ 自动伸缩/自愈        │ 基础伸缩             │
│ 多集群管理           │ 单集群               │
│ Service Mesh 集成   │ 有限                 │
│ 持久化存储丰富       │ 基础                 │
│ 网络策略 (NetworkPolicy) | 无内置         │
│ 完整安全体系         │ 基础                 │
│ 适合: 大规模生产     │ 适合: 中小规模        │
└────────────────────┴─────────────────────┘
```

### 3.3 Kubernetes 核心概念

```text
K8s vs Docker:

Docker:
- 容器 (Container) - 运行单元
- 镜像 (Image) - 应用打包
- 仓库 (Registry) - 镜像存储
- 网络 (Network) - 容器网络

K8s 在 Docker 之上:
- Pod - 1+ 容器组
- Deployment - 部署管理
- Service - 服务发现
- Ingress - 入口路由
- ConfigMap - 配置
- Secret - 密钥
- PVC - 存储声明
- StatefulSet - 有状态
- DaemonSet - 节点服务
- Namespace - 隔离
```

---

## 四、从 Docker 迁移到 Kubernetes

### 4.1 迁移路径

```text
阶段 1: Docker (单机)
   ↓
阶段 2: Docker Compose (单机多服务)
   ↓
阶段 3: Docker Swarm (小集群)
   ↓
阶段 4: Kubernetes (生产)
```

### 4.2 Kompose 转换

```bash
# 1. 安装 Kompose
curl -L https://github.com/kubernetes/kompose/releases/download/v1.31.0/kompose-linux-amd64 -o /usr/local/bin/kompose
chmod +x /usr/local/bin/kompose

# 2. 转换 docker-compose.yml
kompose convert -f docker-compose.yml -o k8s/

# 生成:
# - deployment.yaml
# - service.yaml
# - configmap.yaml
# - persistentvolumeclaim.yaml

# 3. 部署到 K8s
kubectl apply -f k8s/
```

### 4.3 转换示例

```yaml
# docker-compose.yml
services:
  web:
    image: nginx:alpine
    ports:
      - "80:80"

# 转换后 k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 1
  selector:
    matchLabels:
      io.kompose.service: web
  template:
    metadata:
      labels:
        io.kompose.service: web
    spec:
      containers:
      - name: web
        image: nginx:alpine
        ports:
        - containerPort: 80
---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: NodePort
  ports:
  - port: 80
    targetPort: 80
  selector:
    io.kompose.service: web
```

### 4.4 迁移注意事项

```text
迁移时需要调整:

1. 数据卷
   - Docker: /var/lib/docker/volumes/
   - K8s: PV/PVC + StorageClass
   - 注意 hostPath → NFS/CSI

2. 网络
   - Docker: 自动 DNS (用户网络)
   - K8s: Service + Ingress
   - 容器名 → Service 名

3. 配置
   - Docker: 环境变量
   - K8s: ConfigMap + Secret

4. 伸缩
   - Docker: 手动 docker run
   - K8s: HPA / VPA / Cluster Autoscaler

5. 健康检查
   - Docker: HEALTHCHECK
   - K8s: readinessProbe + livenessProbe

6. 日志
   - Docker: docker logs
   - K8s: kubectl logs / 集中收集
```

---

## 五、Docker 与 CI/CD 工具

### 5.1 CI/CD 工具对比

| 工具 | 类型 | 优势 | 适用 |
|------|------|------|------|
| **GitLab CI** | 集成 CI | 与 Git 集成好, Kubernetes Runner | 中大型团队 |
| **GitHub Actions** | SaaS CI | 与 GitHub 集成 | GitHub 用户 |
| **Jenkins** | 自建 CI | 灵活, 插件丰富 | 大型企业 |
| **CircleCI** | SaaS CI | 快速 | 海外团队 |
| **Drone** | 容器化 CI | 容器原生 | 容器优先团队 |
| **Tekton** | K8s CI | K8s 原生 | K8s 生态 |
| **Argo Workflows** | K8s CI | K8s 原生 | GitOps |

### 5.2 Jenkins 完整 Pipeline (Docker)

```groovy
// Jenkinsfile
pipeline {
    agent {
        docker {
            image 'maven:3.9-eclipse-temurin-17'
            args '-v /var/run/docker.sock:/var/run/docker.sock'
        }
    }
    
    environment {
        DOCKER_REGISTRY = 'harbor.example.com'
        APP_NAME = 'myapp'
    }
    
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main', url: 'https://github.com/myorg/myapp.git'
            }
        }
        
        stage('Test') {
            steps {
                sh 'mvn test'
            }
        }
        
        stage('Build & Push') {
            steps {
                script {
                    docker.withRegistry("https://${DOCKER_REGISTRY}", 'harbor-creds') {
                        def img = docker.build("${DOCKER_REGISTRY}/${APP_NAME}:${BUILD_NUMBER}")
                        img.push()
                        img.push('latest')
                    }
                }
            }
        }
        
        stage('Deploy to Staging') {
            steps {
                sh "ssh deploy@staging 'docker service update --image ${DOCKER_REGISTRY}/${APP_NAME}:${BUILD_NUMBER} myapp'"
            }
        }
        
        stage('Deploy to Prod') {
            when {
                branch 'main'
            }
            steps {
                input 'Deploy to production?'
                sh "ssh deploy@prod 'docker service update --image ${DOCKER_REGISTRY}/${APP_NAME}:${BUILD_NUMBER} myapp'"
            }
        }
    }
    
    post {
        always {
            junit '**/target/surefire-reports/*.xml'
        }
        failure {
            mail to: 'devops@example.com',
                 subject: "Build Failed: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                 body: "Check ${env.BUILD_URL}"
        }
    }
}
```

---

## 六、Docker 与 K8s 迁移策略

### 6.1 渐进式迁移

```text
阶段 1: 评估
- 现有 Docker 应用清单
- 依赖分析
- 兼容性测试

阶段 2: 准备
- K8s 集群搭建
- 监控 / 日志 / CI/CD 适配
- 团队培训

阶段 3: 新应用先上 K8s
- 新服务用 K8s 部署
- 旧服务保持 Docker

阶段 4: 迁移核心服务
- 状态服务优先
  (数据库, 缓存)
- 无状态服务次之
  (API, 前端)

阶段 5: 全面迁移
- 所有服务 K8s
- 旧 Swarm / 独立 Docker 退役
```

### 6.2 兼容性注意事项

```bash
# 1. 镜像兼容性
- Docker 镜像 = K8s 镜像 (OCI 标准)
- 基础镜像需支持 K8s runtime (containerd)

# 2. 网络兼容性
- Docker bridge 网络 → K8s Service
- 容器名 → Service 名
- IP 地址 → K8s Service ClusterIP

# 3. 存储兼容性
- hostPath → PV/PVC
- NFS → PV/NFS PVC
- 卷名 → PVC name

# 4. 配置兼容性
- env → ConfigMap / Secret
- 命令 → args
- 入口 → command
```

---

## 七、Docker 在 AI/ML 中的应用

### 7.1 AI 训练环境

```dockerfile
# 深度学习训练环境
FROM nvidia/cuda:12.2.0-cudnn8-runtime-ubuntu22.04

# 安装 Python + 深度学习框架
RUN apt-get update && apt-get install -y python3.10 python3-pip git
RUN pip3 install torch torchvision transformers accelerate

WORKDIR /workspace

# 复制训练代码
COPY . .

# 数据挂载点
VOLUME ["/data", "/models"]

# 训练命令
CMD ["python3", "train.py", "--data", "/data", "--output", "/models"]
```

```bash
# 启动训练
docker run --rm -d \
  --name training \
  --gpus all \                    # 使用所有 GPU
  -v /data/host:/data \
  -v /models/host:/models \
  ai-training:latest
```

### 7.2 AI 模型服务

```dockerfile
# Triton Inference Server (NVIDIA)
FROM nvcr.io/nvidia/tritonserver:23.10-py3

# 复制模型
COPY models /models

EXPOSE 8000 8001 8002

CMD ["tritonserver", "--model-repository=/models"]
```

```yaml
# docker-compose.yml
services:
  triton:
    image: nvcr.io/nvidia/tritonserver
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: all
    volumes:
      - ./models:/models:ro
    ports:
      - "8000:8000"     # HTTP
      - "8001:8001"     # gRPC
      - "8002:8002"     # Metrics
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    networks:
      - ai-net

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    networks:
      - ai-net

networks:
  ai-net:
```

---

## 八、Docker 在 DevOps 中的最佳实践

### 8.1 Dockerfile 优化技巧

```dockerfile
# 1. 缓存优化 (最常变在前, 最常变在后, 顺序敏感)
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# 2. 多阶段构建
FROM golang:1.21 AS builder
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /app/myapp

FROM alpine:3.18
COPY --from=builder /app/myapp /usr/local/bin/

# 3. 最小化层数
RUN apt-get update && \
    apt-get install -y nginx && \
    rm -rf /var/lib/apt/lists/*

# 4. 非 root 用户
RUN adduser -D app
USER app

# 5. HEALTHCHECK
HEALTHCHECK --interval=30s \
  CMD curl -f http://localhost/ || exit 1

# 6. .dockerignore 排除
# .dockerignore
.git
node_modules
*.md
.env
```

### 8.2 镜像签名与扫描集成

```yaml
# GitHub Actions 完整示例
name: Build, Scan, Sign

on: [push]

jobs:
  build-scan-sign:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    # 1. BuildKit 构建 (并行, 缓存)
    - uses: docker/setup-buildx-action@v3

    # 2. 构建并推送
    - name: Build and Push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: harbor.example.com/myapp:${{ github.sha }}
        cache-from: type=gha
        provenance: true
        sbom: true

    # 3. 漏洞扫描
    - name: Trivy Scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: harbor.example.com/myapp:${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'
        severity: 'CRITICAL,HIGH'

    # 4. SBOM 上传
    - name: Upload Trivy Scan
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: trivy-results.sarif

    # 5. 镜像签名
    - name: Install Cosign
      uses: sigstore/cosign-installer@main

    - name: Sign Image
      env:
        COSIGN_EXPERIMENTAL: 1
      run: |
        cosign sign --yes harbor.example.com/myapp@${{ steps.build.outputs.digest }}
```

### 8.3 Helm Chart 最佳实践

```yaml
# Chart.yaml
apiVersion: v2
name: myapp
version: 1.0.0
appVersion: 1.0.0
type: application
maintainers:
  - name: DevOps Team
    email: devops@example.com
```

```yaml
# values.yaml
replicaCount: 3
image:
  repository: harbor.example.com/myapp
  tag: latest
  pullPolicy: IfNotPresent

resources:
  limits:
    cpu: 1000m
    memory: 1Gi
  requests:
    cpu: 200m
    memory: 256M
```

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Chart.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Chart.Name }}
  template:
    metadata:
      labels:
        app: {{ .Chart.Name }}
    spec:
      containers:
      - name: {{ .Chart.Name }}
        image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
        imagePullPolicy: {{ .Values.image.pullPolicy }}
        resources:
          {{- toYaml .Values.resources | nindent 12 }}
```

---

## 九、Docker 未来趋势

### 9.1 容器运行时趋势

```text
Docker 运行时生态:

1. containerd (CNCF, 当前主流)
   - K8s 默认
   - Docker 也用

2. CRI-O
   - Red Hat 主推
   - OpenShift 默认

3. runc (OCI 参考实现)
   - 低层 runtime

4. Podman
   - daemonless
   - 与 Docker 命令兼容
   - RHEL/Fedora 默认

5. nerdctl
   - containerd 命令行
   - Docker 兼容

6. Podman Compose
   - 替代 docker compose
```

### 9.2 Docker Desktop 替代

```text
Docker Desktop 替代品:

1. OrbStack (macOS)
   - 比 Docker Desktop 快 3-5 倍
   - 资源占用少
   - 商业但便宜

2. Colima
   - macOS + Linux
   - 开源免费

3. Rancher Desktop
   - SUSE 出品
   - 集成 K8s

4. Podman Desktop
   - Red Hat
   - daemonless
```

### 9.3 WebAssembly 容器

```text
WebAssembly (Wasm) 容器:
- Spin (Fermyon)
- WasmEdge (Linux Foundation)
- wasmCloud

优势:
- 启动毫秒级
- 极小资源占用
- 多语言支持 (Rust, Go, JS, Python)

挑战:
- 生态不如 Docker
- 仍在早期阶段
```

---

## 十、最终总结

### 10.1 Docker 适用场景

```text
✅ 适合:
- 微服务架构
- CI/CD 流水线
- 开发测试环境
- 传统应用容器化
- 中小规模生产
- 云原生应用

❌ 不适合:
- 高性能计算 (HPC)
- 强安全隔离 (金融核心)
- 单机性能敏感
- 大规模生产 (用 K8s)
```

### 10.2 完整生态

```text
Docker 完整技术栈:

基础层:
  Linux Kernel (namespace, cgroup, UnionFS)
  容器运行时 (containerd, runc)

Docker Engine:
  Docker Daemon (dockerd)
  Docker CLI
  Docker Compose
  Docker Swarm

工具链:
  Build: Docker Buildx (BuildKit)
  Registry: Docker Hub, Harbor
  监控: cAdvisor, Prometheus, Grafana
  日志: ELK, Loki
  编排: Swarm, Kubernetes
  服务网格: Istio, Linkerd
  安全: Trivy, Cosign, Falco

CI/CD:
  GitLab CI, GitHub Actions, Jenkins, Tekton

云平台:
  Docker Desktop
  AWS ECS
  Google Cloud Run
  Azure Container Instances
```

### 10.3 迁移路径建议

```text
小项目 / 个人:    Docker + Compose
中小规模生产:    Docker + Swarm
中大规模生产:    K8s (从 Docker 迁移)
超大规模:        K8s + Service Mesh (Istio)
云原生:          K8s + ArgoCD + 完整生态
```

---

## 核心要点速记

### Docker 三大核心

```text
镜像 (Image)   - 标准化应用打包
容器 (Container) - 镜像的运行实例
仓库 (Registry) - 镜像存储中心
```

### Docker vs K8s

```text
Docker:
  - 单机 / 小集群
  - 简单, 学习曲线低
  - 与 Docker 集成好
  - 适合: 开发 / 测试 / 中小生产

K8s:
  - 大规模生产
  - 复杂, 生态丰富
  - 自动伸缩 / 自愈
  - 适合: 大规模生产 / 云原生
```

### CI/CD 流水线

```text
代码提交 → Lint → Test → Build → Scan → Sign → Push → Deploy
   ↓        ↓      ↓       ↓      ↓      ↓      ↓      ↓
  Git    ESLint  Jest  BuildKit  Trivy  Cosign  Harbor  Staging
                                                                ↓
                                                            Production
```

### 容器编排选型

```text
小项目 → Docker Compose
中小集群 → Docker Swarm
大规模生产 → Kubernetes
多云 / 混合云 → K8s + Cluster API
```

### 迁移路径

```text
Docker → Compose → Swarm → K8s (Kompose 转换)
```

### 生产最佳实践

```text
镜像:  官方 + 最小 + 签名 + 扫描
构建:  多阶段 + 缓存 + .dockerignore
运行:  非 root + 限资源 + 健康检查
注册:  私有 + RBAC + 漏洞扫描
监控:  cAdvisor + Prometheus + Grafana
日志:  Loki/ELK + 日志驱动
```

### 安全最佳实践

```text
镜像: 签名 (Cosign) + 扫描 (Trivy) + 最小基础
容器: 非 root + 只读 + capability 限制
网络: 用户网络 + TLS + 最小化端口
注册: RBAC + 审计 + 加密
运行时: Falco + 审计日志
```

### 未来趋势

```text
- 容器运行时: containerd / Podman
- Wasm 容器: Spin, WasmEdge
- 替代 Docker Desktop: OrbStack, Colima
- K8s 主导: Docker 作为底层 runtime
```

---

## 参考

- **Docker 官方**: https://docs.docker.com/
- **Docker Hub**: https://hub.docker.com/
- **Awesome Docker**: https://github.com/veggiemonk/awesome-docker
- **Docker GitHub**: https://github.com/moby/moby
- **生产 Dockerfile**: https://docs.docker.com/develop/develop-images/dockerfile_best-practices/
- **Awesome Compose**: https://github.com/docker/awesome-compose
- **K8s vs Docker**: https://kubernetes.io/docs/setup/production-environment/container-runtimes/
