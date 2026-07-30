# CI/CD (持续集成/持续部署)

## 一、CI/CD 概述

### 什么是 CI/CD

**CI (Continuous Integration, 持续集成)**:
- 频繁合并代码到主分支
- 每次合并触发自动化构建和测试
- 早期发现集成问题

**CD (Continuous Delivery/Deployment, 持续交付/部署)**:
- **Continuous Delivery**:自动化部署到预发布环境,生产部署需手动
- **Continuous Deployment**:自动化部署到生产环境

### CI/CD 的好处

- **快速反馈**: 几秒/几分钟得到测试结果
- **减少集成问题**: 小批量合并
- **自动化**: 减少重复劳动
- **质量提升**: 强制测试
- **快速发布**: 几小时/几天,而非几周
- **可追溯**: 所有变更记录
- **回滚容易**: 每次发布可回滚

### CI/CD 流水线阶段

```
代码提交 → 触发构建 → 编译 → 单元测试 → 静态分析
    → 集成测试 → 打包 → 镜像 → 部署预发 → 部署生产
    → 监控
```

### CI/CD vs DevOps vs SRE

- **CI/CD**: 工具 + 流程
- **DevOps**: 文化 + 自动化 + 协作
- **SRE (Site Reliability Engineering)**: Google 提出,运维工程师

---

## 二、CI/CD 工具链

### 1. 主流 CI/CD 平台

| 平台               | 类型 | 自托管 | 特点                  |
|--------------------|------|--------|-----------------------|
| **GitHub Actions** | SaaS | 否     | GitHub 集成最佳       |
| **GitLab CI**      | 自带 | 是     | GitLab 全栈           |
| **Jenkins**        | 自带 | 是     | 老牌,可扩展,生态丰富  |
| **CircleCI**       | SaaS | 否     | 快速,易用             |
| **Travis CI**      | SaaS | 否     | 开源项目老朋友        |
| **GitLab CI**      | 自带 | 是     | 完整 DevOps 平台      |
| **Drone**          | 自带 | 是     | 容器化 CI             |
| **Argo CD**        | 自带 | 是     | K8s GitOps            |
| **Argo Workflows** | 自带 | 是     | K8s 工作流            |
| **Tekton**         | 自带 | 是     | K8s 原生 CI/CD        |
| **Buildkite**      | SaaS | 否     | 快速,本地执行         |
| **Drone**          | 自带 | 是     | 容器原生              |
| **Concourse**      | 自带 | 是     | 管道可视化            |

### 2. 部署工具

- **Ansible**: 推送式
- **SaltStack**: 推送式
- **Chef / Puppet**: 拉取式
- **Terraform**: 基础设施即代码
- **Ansible Vault**: 密钥管理

### 3. GitOps 工具

- **Argo CD**: K8s 上的 GitOps
- **Flux CD**: 轻量 GitOps
- **Jenkins X**: Jenkins 的 GitOps
- **Spinnaker**: 多云 CD
- **Octopus Deploy**: 商业 CD

---

## 三、GitHub Actions

### 1. 概述

**GitHub Actions**:GitHub 内置的 CI/CD 平台

- 集成 GitHub 仓库
- YAML 配置
- 大量 Marketplace Actions
- 免费额度:2000 分钟/月

### 2. 工作流文件

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:           # 手动触发

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20]
    steps:
    - uses: actions/checkout@v4

    - name: Set up Node.js
      uses: actions/setup-node@v4
      with:
        node-version: ${{ matrix.node-version }}
        cache: 'npm'

    - name: Install dependencies
      run: npm ci

    - name: Run linter
      run: npm run lint

    - name: Run tests
      run: npm test

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Login to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
          ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://example.com
    steps:
    - name: Deploy to K8s
      run: |
        echo "${{ secrets.KUBECONFIG }}" | base64 -d > /tmp/kubeconfig
        export KUBECONFIG=/tmp/kubeconfig
        kubectl set image deployment/web web=${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
        kubectl rollout status deployment/web
```

### 3. 常用 Actions

- `actions/checkout@v4`: 检出代码
- `actions/setup-node@v4`: 设置 Node
- `actions/setup-python@v5`: 设置 Python
- `actions/setup-go@v5`: 设置 Go
- `actions/setup-java@v4`: 设置 Java
- `actions/cache@v4`: 缓存
- `actions/upload-artifact@v4`: 上传产物
- `actions/download-artifact@v4`: 下载产物
- `docker/build-push-action@v5`: Docker 构建推送
- `docker/setup-buildx-action@v3`: Buildx
- `docker/login-action@v3`: Docker 登录

### 4. 触发器

```yaml
on:
  push:
    branches: [main, develop]
    tags: ['v*']
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'    # 定时任务
  workflow_dispatch:         # 手动
  release:
    types: [published]      # 发布时
```

### 5. 最佳实践

- **缓存依赖**:`actions/cache`
- **矩阵测试**:多版本
- **多作业**:测试 / 构建 / 部署
- **环境**:dev / staging / prod
- **密钥**:`secrets.XXX` (不打印)
- **并行作业**:`needs` 关系
- **复用**:`workflow_call` 触发
- **失败时保留**:`actions/upload-artifact` 上传日志

---

## 四、GitLab CI

### 1. .gitlab-ci.yml

```yaml
stages:
  - test
  - build
  - deploy

variables:
  DOCKER_IMAGE: registry.gitlab.com/mygroup/myapp

# 全局
default:
  image: alpine:latest
  before_script:
    - apk add --no-cache git

# 作业
test:
  stage: test
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - pytest
  coverage: '/(?i)total.*? (100(?:\.0+)?\%|[1-9]?\d(?:\.\d+)?\%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml

build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $DOCKER_IMAGE:$CI_COMMIT_SHA .
    - docker push $DOCKER_IMAGE:$CI_COMMIT_SHA
  only:
    - main
    - develop

deploy_staging:
  stage: deploy
  script:
    - kubectl set image deployment/web web=$DOCKER_IMAGE:$CI_COMMIT_SHA -n staging
  environment:
    name: staging
    url: https://staging.example.com
  only:
    - develop

deploy_production:
  stage: deploy
  script:
    - kubectl set image deployment/web web=$DOCKER_IMAGE:$CI_COMMIT_SHA
  environment:
    name: production
    url: https://example.com
  when: manual
  only:
    - main
```

### 2. GitLab CI 特性

- **共享 Runner**: gitlab.com 提供
- **私有 Runner**: 自托管
- **缓存**:`cache:`
- **制品**:`artifacts:`
- **触发**: `include:` 子流水线
- **Multi-project**: 跨项目
- **环境**: 一键回滚
- **手动部署**: `when: manual`

### 3. GitLab Auto DevOps

- 零配置 CI/CD
- 内置:build, test, deploy, monitoring
- 自动检测语言

---

## 五、Jenkins

### 1. Jenkins 概述

**Jenkins**:老牌开源 CI/CD 工具

- 自托管
- 插件丰富(1500+)
- Pipeline 即代码
- 主从架构
- 适合复杂流程

### 2. 安装

```bash
# RHEL/CentOS
yum install java-11-openjdk
wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo
rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io.key
yum install jenkins
systemctl enable --now jenkins

# 访问
http://localhost:8080
```

### 3. Jenkinsfile (Pipeline)

**Declarative Pipeline**:

```groovy
pipeline {
    agent any

    options {
        timeout(time: 30, unit: 'MINUTES')
        timestamps()
        ansiColor('xterm')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Test') {
            parallel {
                stage('Unit Tests') {
                    steps {
                        sh 'npm test'
                    }
                }
                stage('Lint') {
                    steps {
                        sh 'npm run lint'
                    }
                }
            }
        }

        stage('Build') {
            steps {
                sh 'npm run build'
                archiveArtifacts artifacts: 'dist/**', allowEmptyArchive: false
            }
        }

        stage('Docker Build') {
            steps {
                script {
                    docker.build("myapp:${env.BUILD_ID}")
                }
            }
        }

        stage('Deploy Staging') {
            when {
                branch 'develop'
            }
            steps {
                sh 'kubectl apply -f k8s/staging/'
            }
        }

        stage('Deploy Production') {
            when {
                branch 'main'
              }
            steps {
                input 'Deploy to production?'
                sh 'kubectl apply -f k8s/production/'
            }
        }
    }

    post {
        always {
            junit 'test-results/**/*.xml'
        }
        success {
            slackSend(channel: '#deploys', message: "✅ ${env.JOB_NAME} #${env.BUILD_NUMBER}")
        }
        failure {
            mail to: 'team@example.com', subject: "Build failed: ${env.BUILD_URL}"
        }
    }
}
```

### 4. 常用 Jenkins 插件

- **Pipeline**: Pipeline
- **Blue Ocean**: Pipeline 可视化
- **Git / GitHub**: Git 集成
- **Docker / Docker Pipeline**: Docker
- **Kubernetes**: K8s 集成
- **Pipeline Stage View**: 可视化
- **Credentials Binding**: 密钥
- **SSH Agent**: SSH
- **Ansible**: 部署
- **SonarQube Scanner**: 代码质量
- **JUnit / Cobertura**: 测试
- **Slack Notification**: 通知

### 5. Jenkins 分布式

- **Master / Agent (Slave)**
- 静态 agent
- 动态 agent (K8s, Docker)
- **Jenkins Configuration as Code (JCasC)**
- **Jenkins on Kubernetes**

---

## 六、构建工具

### 1. 编译构建

| 工具       | 语言               |
|------------|--------------------|
| Make       | C/C++              |
| CMake      | C/C++              |
| Make       | C                  |
| Gradle     | Java/Kotlin/Groovy |
| Maven      | Java               |
| SBT        | Scala              |
| Bazel      | 多语言(Google)     |
| Buck       | 多语言(Facebook)   |
| Ant        | Java               |
| MSBuild    | .NET               |
| Cargo      | Rust               |
| Go build   | Go                 |
| npm/yarn   | Node.js            |
| pip        | Python             |
| bundler    | Ruby               |

### 2. 镜像构建

- **Docker Buildx**: 高级构建
- **BuildKit**: Docker 新构建后端
- **Kaniko**: 容器内构建容器镜像(无 daemon)
- **Buildah**: 替代 Docker build
- **img**: 无特权构建
- **Podman build**: 同 Docker 语法
- **JIB** (Google): Java 镜像构建
- **ko** (Google): Go 镜像构建
- **Bazel rules_docker**
- **makisu** (Uber)

### 3. 多架构构建

```bash
# 启用多架构
docker buildx create --use --name multi

# 构建多架构
docker buildx build \
    --platform linux/amd64,linux/arm64,linux/arm/v7 \
    --tag myapp:latest \
    --push .

# 验证
docker buildx imagetools inspect myapp:latest
```

---

## 七、CI/CD 流水线模式

### 1. 基础流水线

```text
代码提交 → 单元测试 → 集成测试 → 构建 → 部署预发 → 部署生产
```

### 2. Git Flow

```text
main (生产)  ←  hotfix
  ↑
release/xxx  ←  release
  ↑
develop  ←  feature/*
  ↑
feature/xxx
```

### 3. Trunk-based Development

```text
main
  ↑
short-lived feature branches (1-2 天)
```

### 4. 部署策略

**蓝绿部署 (Blue-Green)**:
- 准备两套环境
- 切换流量
- 零停机

**金丝雀发布 (Canary)**:
- 切 1% 流量到新版本
- 监控正常,逐步加
- 异常立即回滚

**滚动更新 (Rolling Update)**:
- K8s 默认
- 逐个替换 Pod
- 适合无状态服务

**A/B 测试**:
- 不同用户看不同版本
- 数据驱动决策

### 5. GitOps

**GitOps**:用 Git 作为**单一事实源**(Single Source of Truth)

- 声明式: 仓库里写期望状态
- 自动同步: 工具同步到实际环境
- 可追溯: Git 提交即变更记录
- 易回滚: git revert

**工具**:
- **Argo CD**: K8s GitOps 标杆
- **Flux CD**: CNCF
- **Jenkins X**: Jenkins GitOps

**Argo CD 示例**:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/myorg/myapp-config.git
    targetRevision: HEAD
    path: manifests/
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

---

## 八、测试自动化

### 1. 测试金字塔

```text
        /\        E2E (少量)
       /  \       集成测试 (适量)
      /----\      单元测试 (大量)
```

### 2. 单元测试

```bash
# Python
pytest
pytest -v
pytest --cov=mymodule --cov-report=html

# JavaScript
npm test
npm run test:coverage
jest
mocha

# Go
go test ./...
go test -v -cover
```

### 3. 集成测试

- API 测试:Postman, Newman, REST Assured
- 数据库测试:Testcontainers
- 端到端:Selenium, Cypress, Playwright

### 4. 性能测试

- **JMeter**: Java 压测
- **k6**: 现代 JS 压测
- **Locust**: Python
- **wrk / ab**: 简单 HTTP
- **Gatling**: Scala
- **Vegeta**: Go

### 5. 代码质量

- **SonarQube**: 静态分析
- **CodeQL**: GitHub 静态分析
- **ESLint / Pylint / Checkstyle**

---

## 九、制品管理 (Artifact Management)

### 1. 制品仓库

- **Nexus Repository**: Sonatype, 通用
- **Artifactory**: JFrog, 商业
- **Docker Registry**: Harbor, Quay
- **PyPI / npm / Maven Central**: 公共
- **Cloudsmith**: SaaS

### 2. 制品类型

- 二进制 (JAR, WAR, EXE)
- 镜像
- 包 (deb, rpm, npm)
- 文档
- 报告

### 3. 版本管理

- **语义化版本**: vMAJOR.MINOR.PATCH
- **Git Hash**: commit SHA
- **时间戳**: v2024.01.15
- **构建号**: Jenkins BUILD_ID

---

## 十、CI/CD 最佳实践

### 1. 流水线设计

- **快**: < 10 分钟,反馈快
- **可靠**: 不稳定流水线比没流水线更糟
- **可观察**: 状态可看
- **可回滚**: 一键回滚
- **分级**: lint / unit / integration / e2e
- **缓存**: 依赖缓存、构建缓存
- **并发**: 能并行的并行
- **幂等**: 多次运行结果一致

### 2. 安全

- **密钥管理**:用 Secrets,不入代码
- **扫描**:Trivy、Snyk、SonarQube
- **签名**:Cosign 镜像签名
- **SBOM**:软件物料清单
- **最小权限**:Jenkins agent 权限
- **审计**:谁跑了什么

### 3. 性能

- **缓存**:依赖、镜像、Docker 层
- **并行**:多 job 并行
- **增量**:只测改动的
- **测试选择**:lint 必跑,e2e 关键
- **资源**:合适的 runner
- **Runner 池**:分布式

### 4. 监控

- **构建时长**:SLO
- **成功率**:> 95%
- **测试覆盖率**:> 80%
- **回滚率**:< 5%
- **Lead Time**: < 1 天
- **MTTR**: < 1 小时

### 5. 文化

- **小批量**:频繁集成
- **主干开发**:减少长分支
- **代码审查**:每个 PR 必审
- **配对编程**:复杂任务
- **故障复盘**:每次故障都学
- **知识共享**:文档、培训

### 6. 度量 (DORA 指标)

Google DORA 4 个关键指标:
- **部署频率** (Deployment Frequency)
- **变更前置时间** (Lead Time for Changes)
- **变更失败率** (Change Failure Rate)
- **平均恢复时间** (MTTR - Mean Time To Recovery)

精英 (Elite) 表现:
- 部署:每天多次
- Lead Time: < 1 小时
- 失败率: < 15%
- MTTR: < 1 小时

---

## 十一、CI/CD 实战案例

### 1. Web 应用标准流水线

```yaml
# GitHub Actions
name: Web App CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: 20
        cache: 'npm'
    - run: npm ci
    - run: npm run lint
    - run: npm test
    - run: npm run build
    - name: Trivy scan
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: 'node:20'
        exit-code: '1'
        ignore-unfixed: true
        vuln-type: 'os,library'
        severity: 'CRITICAL,HIGH'

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    - uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ghcr.io/${{ github.repository }}:latest
        cache-from: type=gha
        cache-to: type=gha,mode=max
        provenance: false

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up K8s
      uses: azure/setup-kubectl@v4
    - name: Configure K8s
      run: |
        mkdir -p ~/.kube
        echo "${{ secrets.KUBECONFIG }}" | base64 -d > ~/.kube/config
    - name: Deploy
      run: |
        kubectl set image deployment/web web=ghcr.io/${{ github.repository }}:latest -n prod
        kubectl rollout status deployment/web -n prod
    - name: Smoke test
      run: |
        sleep 30
        curl -f https://example.com/health || exit 1
```

### 2. 微服务流水线 (多服务)

```yaml
# .github/workflows/api.yml
name: API Service

on:
  push:
    paths: ['services/api/**']

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Build & Test
      working-directory: services/api
      run: |
        go test ./...
        go build -o api .
    - name: Build & Push
      uses: docker/build-push-action@v5
      with:
        context: services/api
        push: true
        tags: ghcr.io/myorg/api:${{ github.sha }}
    - name: Deploy
      run: |
        kubectl set image deployment/api api=ghcr.io/myorg/api:${{ github.sha }} -n prod
```

### 3. 蓝绿部署

```bash
# K8s nginx ingress 蓝绿
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "10"   # 10% 流量
spec:
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-v2
            port:
              number: 80
```

### 4. 数据库迁移

```yaml
# 迁移作为流水线的一步
deploy:
  steps:
  - name: Backup DB
    run: mysqldump -h db -u root -p$DB_PASS > backup.sql
  - name: Run migrations
    run: ./migrate.sh
  - name: Deploy
    run: ./deploy.sh
  - name: Smoke test
    run: ./smoke-test.sh
  - name: Rollback on failure
    if: failure()
    run: ./rollback.sh
```

---

## 十二、CI/CD 工具对比

| 维度       | GitHub Actions | GitLab CI | Jenkins      | CircleCI |
|------------|----------------|-----------|--------------|----------|
| 托管       | SaaS/自托管    | 自带      | 自托管       | SaaS     |
| 配置       | YAML           | YAML      | Groovy       | YAML     |
| 学习曲线   | 低             | 低        | 高           | 中       |
| 生态       | 丰富           | 丰富      | 极丰富       | 中       |
| 集成       | GitHub         | GitLab    | 通用         | 通用     |
| K8s 集成   | 中             | 好        | 好           | 中       |
| 性能       | 中             | 中        | 取决于       | 高       |
| 价格       | 免费 2000 分钟 | 免费 SaaS | 免费(自托管) | 商业     |
| 调试       | 中             | 好        | 差           | 好       |

---

## 十三、安全扫描

### 1. 镜像扫描

```bash
# Trivy
trivy image myapp:1.0
trivy image --severity HIGH,CRITICAL myapp:1.0
trivy fs .
trivy k8s cluster
trivy repo https://github.com/myorg/myapp

# Grype
grype myapp:1.0

# Snyk (商业)
snyk container myapp:1.0
snyk code

# Clair
clair-scanner myapp:1.0
```

### 2. 代码扫描

- **CodeQL**: GitHub 自带
- **SonarQube**: 商业, 强大
- **Snyk Code**: 商业
- **Semgrep**: 静态分析

### 3. 依赖扫描

- **npm audit**: Node.js
- **pip-audit / safety**: Python
- **Trivy**: 多语言
- **Dependabot**: GitHub 自动 PR
- **Renovate**: 跨平台

### 4. 密钥扫描

- **git-secrets**: 防止密钥入仓
- **gitleaks**: 扫描历史
- **TruffleHog**: 深度扫描
- **detect-secrets**: 灵活

```bash
# 预提交钩子
pip install pre-commit
pre-commit install

# .pre-commit-config.yaml
repos:
- repo: https://github.com/gitleaks/gitleaks
  rev: v8.18.0
  hooks:
  - id: gitleaks
```

---

## 十四、关键概念速查

| 概念                  | 含义                             |
|-----------------------|----------------------------------|
| **CI**                | Continuous Integration, 持续集成 |
| **CD**                | Continuous Delivery/Deployment   |
| **Pipeline**          | 流水线                           |
| **Stage**             | 阶段                             |
| **Step**              | 步骤                             |
| **Artifact**          | 制品                             |
| **Runner/Agent**      | 执行器                           |
| **Cache**             | 缓存                             |
| **Matrix**            | 矩阵测试                         |
| **Service Container** | 服务的容器(测试 DB)              |
| **GitOps**            | 仓库即真理                       |
| **Argo CD**           | K8s GitOps                       |
| **Flux CD**           | K8s GitOps                       |
| **Blue-Green**        | 蓝绿部署                         |
| **Canary**            | 金丝雀发布                       |
| **Rolling Update**    | 滚动更新                         |
| **Trunk-based**       | 主干开发                         |
| **Git Flow**          | Git 分支模型                     |
| **SBOM**              | 软件物料清单                     |
| **Cosign**            | 镜像签名                         |
| **DORA**              | 4 个 DevOps 指标                 |
| **Lead Time**         | 变更前置时间                     |
| **MTTR**              | 平均恢复时间                     |

---

## 十五、核心要点速记

- **CI** = 持续集成,频繁合并+自动测试
- **CD** = 持续部署,自动发布
- **GitHub Actions** = GitHub 集成最佳
- **GitLab CI** = 全栈,自带 Runner
- **Jenkins** = 老牌,插件最多
- **Argo CD** = K8s GitOps 标杆
- **流水线** = stages + jobs + steps
- **缓存** = 依赖、构建、Docker 层
- **多架构构建** = buildx + platform
- **金丝雀** = 切 1% 流量测试
- **蓝绿** = 两套环境切换
- **滚动** = K8s 默认
- **GitOps** = 仓库即真理,自动同步
- **Trivy** = 镜像扫描
- **Cosign** = 镜像签名
- **SBOM** = 软件清单
- **DORA 4 指标**: 部署频率/Lead Time/失败率/MTTR
- **精英水平**: 每天多次部署,Lead Time < 1h
- **小批量** = 频繁集成,减少分支
- **快速失败** = 10 分钟内反馈
- **幂等** = 多次执行结果相同
- **密钥管理** = 用 Secrets,不入代码
- **Trunk-based** = 主干开发,短分支
- **依赖更新** = Dependabot / Renovate
- **pre-commit** = 提交前扫描
- **gitleaks** = 密钥扫描
- **容器镜像** = 推 ghcr.io / 私有 Harbor
- **环境分层** = dev / staging / prod
- **手动批准** = 生产部署
