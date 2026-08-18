# Docker 镜像仓库 (Registry & Repository)

> 本章详解 Docker 镜像仓库:Docker Hub 公共仓库、Harbor 私有仓库、镜像分发、签名验证。

## 一、镜像仓库概述

### 1.1 什么是 Registry

**Registry** 是存储和分发 Docker 镜像的服务。

```text
Registry 分类:

1. 公共 Registry
   - Docker Hub (官方, 最大)
   - Quay.io (CoreOS, Red Hat)
   - GitHub Container Registry (ghcr.io)
   - Google Container Registry (gcr.io)
   - 阿里云容器镜像服务 (cr.console.aliyun.com)

2. 私有 Registry
   - 自建 Registry (官方)
   - Harbor (CNCF, 最流行)
   - GitLab Container Registry
   - Nexus / Artifactory
   - 云厂商仓库 (AWS ECR, 阿里云 ACR)

3. 本地 Registry
   - 开发测试用
   - 内网部署
```

### 1.2 镜像仓库组件

```text
Registry 仓库生态:

OCI Distribution Spec (规范):
- 镜像分发协议
- 镜像格式标准
- 内容寻址 (SHA256 digest)

核心组件:
- Registry Server    - HTTP API 服务
- Storage Backend    - S3 / OSS / 存储
- Database           - 元数据 (PostgreSQL/MySQL)
- Auth               - Token / OAuth
- Web UI             - 管理界面 (Harbor 等)
```

---

## 二、Docker Hub 公共仓库

### 2.1 Docker Hub 介绍

```text
Docker Hub:
- 官方公共仓库
- 域名: docker.io 或 registry-1.docker.io
- 默认匿名访问
- 免费/付费计划
- 镜像丰富 (官方镜像、社区镜像)

官方镜像 (Official Images):
- Docker 官方维护
- 安全扫描
- 高质量保证

热门官方镜像:
- nginx, apache, httpd
- mysql, postgres, redis, mongodb
- node, python, golang, openjdk
- alpine, ubuntu, debian
- kubernetes, prometheus
```

### 2.2 Docker Hub 使用

```bash
# 搜索镜像
docker search nginx
docker search --filter is-official=true nginx  # 只搜官方

# 拉取镜像 (默认 Docker Hub)
docker pull nginx
docker pull nginx:1.25
docker pull library/nginx   # 显式指定命名空间

# 推送 (需登录)
docker login                      # Docker Hub
docker login registry.example.com  # 其他 Registry

docker tag myapp:1.0 myusername/myapp:1.0
docker push myusername/myapp:1.0

# 自动构建 (GitHub/Bitbucket)
# https://hub.docker.com → Account Settings → Linked Accounts
```

### 2.3 Docker Hub 速率限制

```text
匿名用户:
  - 100 pulls / 6 小时 (per IP)

认证用户 (免费):
  - 200 pulls / 6 小时 (per user)

付费用户:
  - 无限制

解决:
  1. 注册 Docker Hub 账号
  2. 使用国内镜像加速器
  3. 自建私有仓库
```

---

## 三、私有仓库

### 3.1 自建 Registry

```bash
# 运行官方 Registry 镜像
docker run -d \
  --name my-registry \
  -p 5000:5000 \
  -v /data/registry:/var/lib/registry \
  -e REGISTRY_STORAGE_DELETE_ENABLED=true \
  registry:2

# 配置 TLS (生产必需)
docker run -d \
  --name my-registry \
  -p 443:5000 \
  -v /data/registry:/var/lib/registry \
  -v /certs:/certs \
  -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/domain.crt \
  -e REGISTRY_HTTP_TLS_KEY=/certs/domain.key \
  registry:2

# 推送镜像
docker tag myapp:1.0 my-registry.local/myapp:1.0
docker push my-registry.local/myapp:1.0

# 拉取
docker pull my-registry.local/myapp:1.0
```

### 3.2 Harbor (推荐生产私有仓库)

```text
Harbor:
- CNCF 毕业项目
- 企业级 Docker Registry
- 基于官方 Registry, 加了企业级功能
- 核心功能:
  - RBAC 权限控制
  - 镜像复制 (多仓库同步)
  - 镜像签名 (Cosign/Notary)
  - 漏洞扫描 (Trivy/Clair)
  - 镜像标签保留策略
  - Web UI 管理
  - AD/LDAP 集成
  - 审计日志
```

### 3.3 Harbor 部署

```bash
# 1. 下载 Harbor
wget https://github.com/goharbor/harbor/releases/download/v2.10.0/harbor-offline-installer-v2.10.0.tgz
tar xzf harbor-offline-installer-v2.10.0.tgz
cd harbor

# 2. 配置 harbor.yml
hostname: harbor.example.com
http:
  port: 80
https:
  port: 443
  certificate: /etc/certs/harbor.crt
  private_key: /etc/certs/harbor.key
harbor_admin_password: Harbor12345
database:
  password: root123
data_volume: /data/harbor
trivy:
  enabled: true
notary:
  enabled: true    # 镜像签名

# 3. 安装
./install.sh

# 4. 访问 https://harbor.example.com
#    默认账号: admin / Harbor12345
```

### 3.4 Harbor 使用

```bash
# 1. 配置 docker 信任 Harbor
mkdir -p /etc/docker/certs.d/harbor.example.com
cp harbor.crt /etc/docker/certs.d/harbor.example.com/ca.crt

# 2. 登录
docker login harbor.example.com
# Username: admin
# Password: Harbor12345

# 3. 推送镜像
docker tag myapp:1.0 harbor.example.com/library/myapp:1.0
docker push harbor.example.com/library/myapp:1.0

# 4. 创建项目
# Harbor UI → New Project
# 设置访问级别 (Public / Private)
# 添加成员 (RBAC)

# 5. 拉取镜像
docker pull harbor.example.com/library/myapp:1.0
```

### 3.5 Harbor 高可用

```text
Harbor HA 架构:

方案 1: 双 Harbor 实例 + 共享存储
- 主 Harbor + 备 Harbor
- S3/OSS 共享存储
- DNS 切换或负载均衡

方案 2: Harbor + 镜像复制
- 主 Harbor → 备 Harbor 同步
- 主备 Harbor 同步镜像

方案 3: 多 Harbor 实例 + 统一入口
- 多个 Harbor 实例
- 全局负载均衡
- 客户端配置多个 endpoint

方案 4: Harbor Operator (K8s)
- 使用 Operator 部署
- 自动伸缩
- 高可用内置
```

---

## 四、镜像分发与缓存

### 4.1 Docker Pull 流程

```text
docker pull nginx:1.25 流程:

1. 联系 Registry (默认 docker.io)
2. 验证认证 (匿名或登录)
3. 获取镜像 manifest
4. 计算所有需要的层 (layers)
5. 检查本地已有层 (镜像复用)
6. 下载缺失的层 (并发下载)
7. 验证 SHA256 digest (内容校验)
8. 解压层到本地存储 (/var/lib/docker/overlay2)
9. 创建镜像元数据
```

### 4.2 镜像层复用

```text
Docker 镜像层 (Layer):

nginx:1.25
├── Layer 1: base debian
├── Layer 2: apt-get update
├── Layer 3: apt-get install nginx
└── Layer 4: CMD ["nginx"]

myapp:1.0 (基于 nginx)
├── Layer 1: base debian  ← 复用
├── Layer 2: apt-get update  ← 复用
├── Layer 3: apt-get install nginx  ← 复用
├── Layer 4: COPY myapp files  ← 独有
└── Layer 5: CMD ["myapp"]
```

```bash
# 查看镜像分层
docker history nginx:1.25

# 查看层大小
docker history --no-trunc nginx:1.25

# 查看磁盘使用
docker system df
```

### 4.3 Registry 缓存与代理

```bash
# 配置镜像加速器 (国内推荐)
/etc/docker/daemon.json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}

sudo systemctl restart docker

# 验证
docker info | grep -A 3 Registry
```

### 4.4 P2P 分发 (Kraken / Dragonfly)

```text
P2P 镜像分发:
- 大规模集群镜像分发加速
- Kraken (Uber 开源)
- Dragonfly (eBay 开源)

原理:
- 节点间 P2P 共享镜像层
- 减少 Registry 中心节点压力
- 加速大规模部署
```

---

## 五、镜像安全

### 5.1 镜像签名 (Cosign / Notary)

```bash
# 1. 安装 cosign
brew install cosign  # macOS

# 2. 生成密钥对
cosign generate-key-pair

# 3. 签名镜像
cosign sign --key cosign.key myregistry/myapp:1.0

# 4. 验证签名
cosign verify --key cosign.pub myregistry/myapp:1.0

# 5. 验证 (无密钥, 用 keyless / OIDC)
cosign verify \
  --certificate-identity-regexp 'https://github.com/myorg' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  myregistry/myapp:1.0
```

### 5.2 Docker Content Trust (DCT)

```bash
# 启用 DCT
export DOCKER_CONTENT_TRUST=1

# 推送 (自动签名)
docker push myregistry/myapp:1.0

# 拉取 (自动验证签名)
docker pull myregistry/myapp:1.0
# 签名失败则拒绝

# 禁用 DCT
export DOCKER_CONTENT_TRUST=0
```

### 5.3 镜像漏洞扫描

```bash
# Trivy 扫描
trivy image nginx:1.25
trivy image --severity HIGH,CRITICAL myapp:1.0

# Trivy 扫描文件系统
trivy fs /path/to/project

# 集成到 CI/CD
# GitHub Action, GitLab CI, Jenkins

# 与 Harbor 集成
# Harbor 内置 Trivy 扫描
```

---

## 六、生产实战

### 6.1 多 Registry 部署策略

```text
推荐架构:

1. 国内镜像加速器 (Docker Hub)
   - 阿里云 / 网易 / 中科大
   - 提升拉取速度

2. 私有仓库 (Harbor)
   - 公司内统一镜像分发
   - 安全扫描 + 签名

3. CDN 缓存 (Cloudflare/AWS CloudFront)
   - 全球分发
   - 减少 Registry 压力

4. 多 Harbor 实例
   - 主备或多活
   - 容灾
```

### 6.2 镜像标签策略

```text
推荐标签:
- v1.0.0          # SemVer
- v1.0.0-alpine   # 变体
- v1.0.0-arm64    # 架构
- stable          # 稳定版
- latest          # 默认 (避免生产用)

不要:
- latest (生产)
- 模糊标签 (test, latest-feature)
- 相同 tag 多次推送 (不可变原则)

CI/CD 流水线:
1. Git tag → 自动构建镜像
2. 镜像标签 = Git tag (如 v1.0.0)
3. 同一 commit 只能产生一个镜像
4. 镜像不可变 (digest 唯一)
```

### 6.3 镜像保留策略

```bash
# 1. Harbor 标签保留策略
#    UI → 项目 → 配置 → 标签保留
#    - 保留最近 10 个标签
#    - 保留 30 天内创建的标签

# 2. 手动清理
docker image prune -a --filter "until=720h"   # 清理 30 天前
docker image prune -a --filter "label=deprecated=true"

# 3. 自动清理脚本
0 3 * * 0 docker image prune -a --filter "until=720h" -f
```

### 6.4 镜像复制

```bash
# 跨 Registry 同步镜像
# 工具: skopeo (推荐)

# skopeo 安装
yum install -y skopeo

# 同步镜像
skopeo copy \
  --src-creds username:password \
  --dest-creds admin:Harbor12345 \
  docker://docker.io/myorg/myapp:1.0 \
  docker://harbor.example.com/library/myapp:1.0

# Harbor 镜像复制 (UI)
# 项目 → 镜像仓库 → 复制

# crane (Go 写的镜像工具)
crane copy myregistry/myapp:1.0 harbor.example.com/library/myapp:1.0
```

---

## 七、Registry API

### 7.1 REST API

```bash
# Registry V2 API

# 1. 获取认证 token
curl -X GET "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/nginx:pull"

# 2. 列出镜像 tags
curl -H "Authorization: Bearer $TOKEN" \
  "https://registry-1.docker.io/v2/library/nginx/tags/list"

# 3. 获取 manifest
curl -H "Authorization: Bearer $TOKEN" \
  "https://registry-1.docker.io/v2/library/nginx/manifests/1.25"

# 4. 列出所有 layer
curl -H "Authorization: Bearer $TOKEN" \
  "https://registry-1.docker.io/v2/library/nginx/manifests/1.25" | jq

# 5. 删除镜像 (需开启)
curl -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "https://registry-1.docker.io/v2/library/nginx/manifests/1.25"
```

### 7.2 监控 Registry

```bash
# Registry 自带指标 (Prometheus 格式)
curl http://localhost:5000/metrics

# 关键指标:
# - 拉取次数
# - 推送次数
# - 错误次数
# - 存储使用

# Harbor 监控
# - Web UI 系统管理
# - Prometheus 集成 (harbor-exporter)
# - Grafana Dashboard
```

---

## 八、Registry 选型决策

### 8.1 各 Registry 对比

| Registry | 适用场景 | 特点 |
|----------|---------|------|
| **Docker Hub** | 公开镜像, 个人项目 | 全球最大, 限速 |
| **Harbor** | 企业私有仓库 | 功能全, CNCF |
| **AWS ECR** | AWS 用户 | 无缝集成 |
| **阿里云 ACR** | 阿里云用户 | 国内访问快 |
| **GCP Artifact Registry** | GCP 用户 | 与 GCP 集成 |
| **GitHub Container Registry** | GitHub 项目 | 与 GitHub Actions 集成 |
| **GitLab Container Registry** | GitLab 用户 | 与 GitLab CI 集成 |
| **自建 Registry** | 简单场景 | 仅基础功能 |

### 8.2 选型决策

```text
小团队 / 个人 → Docker Hub
中大型企业 / 私有部署 → Harbor
AWS 用户 → ECR
阿里云用户 → ACR
GitHub 项目 → ghcr.io
GitLab 项目 → GitLab Registry

混合策略 (推荐):
- 公开镜像 → Docker Hub / 阿里云 ACR
- 私有镜像 → 自建 Harbor
- 跨云分发 → 多 Registry 镜像复制
```

---

## 核心要点速记

### Registry 类型

```text
公共: Docker Hub, Quay.io, ghcr.io
私有: Harbor, GitLab Registry, ECR
本地: 官方 Registry 镜像
```

### Docker Hub 速记

```bash
docker pull <image>           # 默认从 Docker Hub
docker push <image>           # 需登录
docker login                  # 登录
```

### Harbor 速记

```text
功能:
  RBAC / 镜像复制 / 漏洞扫描 / 镜像签名 / Web UI / AD 集成
部署:
  ./install.sh
访问:
  https://harbor.example.com
推送:
  docker tag myapp:1.0 harbor.example.com/library/myapp:1.0
  docker push harbor.example.com/library/myapp:1.0
```

### 镜像标签策略

```text
推荐:
- v1.0.0 (SemVer)
- v1.0.0-alpine (变体)
- v1.0.0-arm64 (架构)

避免:
- latest (生产)
- 重复推送同一 tag
- 模糊标签
```

### 镜像安全

```text
1. 签名 (Cosign / Notary)
2. 漏洞扫描 (Trivy)
3. 镜像认证 (DOCKER_CONTENT_TRUST)
4. RBAC 权限控制 (Harbor)
5. 审计日志
```

### 镜像复制

```bash
# skopeo
skopeo copy \
  --src-creds user:pass \
  --dest-creds user:pass \
  docker://src/myapp:1.0 \
  docker://dst/myapp:1.0

# Harbor 内置复制 (UI)
# Crane (Google)
crane copy src/img dst/img
```

### 镜像加速器

```json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
```

---

## 参考

- **Docker Hub**: https://hub.docker.com/
- **Harbor 文档**: https://goharbor.io/docs/
- **Registry 官方**: https://docs.docker.com/registry/
- **OCI Distribution Spec**: https://github.com/opencontainers/distribution-spec
- **Cosign 签名**: https://github.com/sigstore/cosign
- **Trivy 扫描**: https://github.com/aquasecurity/trivy
- **skopeo**: https://github.com/containers/skopeo
