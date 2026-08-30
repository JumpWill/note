# Helm 完全指南（K8s 包管理工具）

> 本章系统讲解 Helm 的原理、Chart 开发、命令使用与生产最佳实践。

## 一、为什么需要 Helm

### 1.1 K8s 资源管理痛点

```text
K8s 原生资源管理的痛点：

  1. YAML 文件散落
     - Deployment、Service、ConfigMap 等
     - 几十个文件，关系复杂
     - 版本管理困难

  2. 环境差异
     - dev / staging / prod 配置不同
     - 手动修改容易出错
     - 复用困难

  3. 缺乏模板化
     - 相同应用多次部署
     - 需要复制粘贴
     - 修改一处忘记另一处

  4. 缺乏依赖管理
     - 多个应用有依赖
     - 部署顺序重要
     - 手动管理复杂

  5. 缺乏发布机制
     - 没有版本控制
     - 没有回滚机制
     - 升级风险高
```

### 1.2 Helm 解决的核心问题

```text
Helm = K8s 的包管理工具（类似 apt/yum/npm）

解决问题：
  1. Chart 打包：把 K8s 资源打包成 Chart
  2. 模板化：参数化部署
  3. 版本管理：版本化 + 仓库
  4. 依赖管理：requirements.yaml
  5. 生命周期：install/upgrade/rollback
  6. 复用：Chart 仓库（公开/私有）
```

### 1.3 Helm vs Kustomize 对比

| 维度 | Helm | Kustomize |
|------|------|-----------|
| 方式 | 模板（Templating） | 覆盖（Overlay） |
| 语言 | Go template | Kustomize YAML |
| 仓库 | Chart 仓库（OCI） | 无（Git） |
| 复用 | Chart 共享 | Patch 复用 |
| 复杂度 | 中等 | 简单 |
| 适用 | 复杂应用、参数多 | 简单应用、定制多 |
| 推荐 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

---

## 二、Helm 核心概念

### 2.1 三大核心概念

```text
Helm 三大核心：

  1. Chart
     - K8s 资源的打包格式
     - 包含模板 + 默认配置 + 元数据
     - 类似 Debian 包或 RPM

  2. Release
     - Chart 的运行实例
     - 一次 install 就是一个 release
     - 类似"安装了 nginx v1.0"

  3. Repository
     - Chart 的存储仓库
     - 公开：Artifact Hub、GitHub Pages
     - 私有：Harbor、ChartMuseum、OCI
     - 类似 Docker Hub
```

### 2.2 Helm 架构

```text
Helm 架构：

  ┌──────────────────────────────────────┐
  │  Helm CLI 客户端                      │
  │  - 解析 chart                        │
  │  - 渲染模板                        │
  │  - 与 K8s API 通信                  │
  │  - 维护 release 状态                │
  └──────────────┬───────────────────────┘
                 │ HTTPS
  ┌──────────────▼───────────────────────┐
  │  K8s API Server                     │
  │  - 存储 release 状态（Secrets）     │
  │  - 应用 YAML 到集群                │
  └──────────────────────────────────────┘

  注意：
  - Helm 3+ 不需要 Tiller（服务端组件）
  - Helm 2 才有 Tiller（已废弃）
  - 所有逻辑在 CLI 客户端
  - 状态存储在 K8s Secrets 中
```

### 2.3 Helm 3 vs Helm 2 关键变化

```text
Helm 3 vs Helm 2：

  移除 Tiller：
    Helm 2：需要 Tiller（RBAC 复杂）
    Helm 3：无 Tiller（用 K8s 权限）
    升级影响：需要重新设计 RBAC

  Release 存储：
    Helm 2：默认 ConfigMap
    Helm 3：默认 Secret（更安全）
    影响：需要迁移旧 release

  依赖管理：
    Helm 2：requirements.yaml
    Helm 3：Chart.yaml dependencies
    语法变化大

  其他变化：
    - go template 函数更新
    - lookup 函数行为改变
    - 删除 crds 目录
    - 新的库（library）支持
```

---

## 三、Chart 结构详解

### 3.1 完整 Chart 目录结构

```text
mychart/
├── Chart.yaml              # 必需：Chart 元数据
├── values.yaml             # 必需：默认配置值
├── values.schema.json     # 可选：values 验证
├── charts/                 # 依赖的子 chart
│   └── postgresql-12.x.x.tgz
├── crds/                   # 自定义资源定义
│   └── mycrd.yaml
├── templates/              # 必需：模板目录
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── serviceaccount.yaml
│   ├── hpa.yaml
│   ├── ingressclass.yaml
│   ├── _helpers.tpl         # 模板辅助函数
│   └── NOTES.txt            # 使用说明
├── files/                  # 非模板文件
│   └── application.properties
├── templates/tests/         # 测试
│   └── test-connection.yaml
├── .helmignore             # 排除文件
├── LICENSE                 # 许可证
└── README.md               # 说明文档
```

### 3.2 Chart.yaml 详解

```yaml
apiVersion: v2              # 必需：v2（Helm 3）/ v1（Helm 2）
name: mychart              # 必需：Chart 名称
version: 1.2.3            # 必需：SemVer 格式
appVersion: "2.1.0"       # 包含的应用版本

# 可选字段
description: A Helm chart for Kubernetes
type: application         # chart 类型：application 或 library
home: https://example.com
icon: https://example.com/logo.png
sources:
  - https://github.com/example/mychart
keywords:
  - web
  - nginx
maintainers:
  - name: John Doe
    email: john@example.com
  - name: Jane Smith
    email: jane@example.com
keywords:
  - example
  - production

# K8s 版本约束
kubeVersion: ">=1.24.0-0"

# 依赖（Helm 3）
dependencies:
- name: postgresql
  version: "12.x.x"
  repository: "https://charts.bitnami.com/bitnami"
  condition: postgresql.enabled
  tags:
    - database
- name: redis
  version: "17.x.x"
  repository: "https://charts.bitnami.com/bitnami"
  condition: redis.enabled

# 标签
icon: https://example.com/icon.png
kubeVersion: ">=1.24.0-0"

# Annotations
annotations:
  category: Application
  licenses: Apache-2.0
```

### 3.3 values.yaml 详解

```yaml
# 默认配置值（可被 --set 覆盖）
replicaCount: 3

image:
  repository: nginx
  tag: 1.25.0
  pullPolicy: IfNotPresent

imagePullSecrets: []

nameOverride: ""
fullnameOverride: ""

serviceAccount:
  create: true
  annotations: {}
  name: ""

podAnnotations: {}
podSecurityContext: {}
  fsGroup: 2000

securityContext: {}
  allowPrivilegeEscalation: false
  runAsNonRoot: true
  runAsUser: 1000

service:
  type: ClusterIP
  port: 80
  targetPort: 8080

ingress:
  enabled: false
  className: ""
  annotations: {}
  hosts:
    - host: chart-example.local
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls: []

resources:
  limits:
    cpu: 100m
    memory: 128Mi
  requests:
    cpu: 100m
    memory: 128Mi

autoscaling:
  enabled: false
  minReplicas: 1
  maxReplicas: 100
  targetCPUUtilizationPercentage: 80

nodeSelector: {}
tolerations: []
affinity: {}
```

### 3.4 templates 模板详解

#### deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "mychart.fullname" . }}
  labels:
    {{- include "mychart.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "mychart.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "mychart.selectorLabels" . | nindent 8 }}
    spec:
      serviceAccountName: {{ include "mychart.serviceAccountName" . }}
      {{- with .Values.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      securityContext:
        {{- toYaml .Values.podSecurityContext | nindent 8 }}
      containers:
        - name: {{ .Chart.Name }}
          securityContext:
            {{- toYaml .Values.securityContext | nindent 12 }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8080
              protocol: TCP
          livenessProbe:
            httpGet:
              path: /healthz
              port: http
          readinessProbe:
            httpGet:
              path: /
              port: http
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
      {{- with .Values.nodeSelector }}
      nodeSelector:
        {{- toYaml . | nindent 8 }}
      {{- with .Values.affinity }}
      affinity:
        {{- toYaml . | nindent 8 }}
      {{- with .Values.tolerations }}
      tolerations:
        {{- toYaml . | nindent 8 }}
```

#### _helpers.tpl（辅助函数）

```yaml
{{/*
Common labels
*/}}
{{- define "mychart.labels" -}}
helm.sh/chart: {{ include "mychart.chart" . }}
{{ include "mychart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "mychart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "mychart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "mychart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "mychart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Fullname
*/}}
{{- define "mychart.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}
```

---

## 四、Helm 命令详解

### 4.1 Chart 管理命令

```bash
# 1. 创建 Chart
helm create mychart
# 生成完整 Chart 目录结构

# 2. 验证 Chart
helm lint mychart
# 检查 Chart 语法和错误

# 3. 渲染 Chart（不安装）
helm template mychart ./mychart
helm template mychart ./mychart --set replicaCount=3
helm template mychart ./mychart --values my-values.yaml

# 4. 打包 Chart
helm package mychart
# 生成 mychart-1.0.0.tgz

# 5. 查看 Chart 元数据
helm show chart mychart
helm show all mychart
helm show values mychart
helm show readme mychart

# 6. 依赖管理
helm dependency list mychart
helm dependency update mychart
helm dependency build mychart
```

### 4.2 Release 管理命令

```bash
# 1. 安装 Release
helm install my-release mychart
helm install my-release mychart -n production
helm install my-release mychart -f values.yaml
helm install my-release mychart --set replicaCount=5
helm install my-release mychart --version 1.2.3
helm install my-release mychart --dry-run   # 测试，不实际安装
helm install my-release mychart --namespace prod --create-namespace

# 2. 查看 Release
helm list
helm list -A                   # 所有命名空间
helm list -n production
helm list --filter 'mychart'
helm status my-release -n production

# 3. 升级 Release
helm upgrade my-release mychart
helm upgrade my-release mychart -f new-values.yaml
helm upgrade my-release mychart --set image.tag=2.0.0
helm upgrade my-release mychart --version 2.0.0
helm upgrade my-release mychart --install  # 缺失时安装
helm upgrade my-release mychart --atomic    # 失败时回滚
helm upgrade my-release mychart --cleanup-on-fail

# 4. 回滚 Release
helm history my-release -n production
helm rollback my-release 1 -n production

# 5. 卸载 Release
helm uninstall my-release
helm uninstall my-release -n production
helm uninstall my-release --keep-history  # 保留历史
```

### 4.3 仓库管理命令

```bash
# 1. 添加仓库
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus https://prometheus-community.github.io/helm-charts
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx

# 2. 列出仓库
helm repo list

# 3. 更新仓库
helm repo update

# 4. 搜索 Chart
helm search repo nginx
helm search repo nginx --version 1.0.0
helm search hub wordpress

# 5. 移除仓库
helm repo remove bitnami
```

### 4.4 高级命令

```bash
# 1. 插件管理
helm plugin install <url>
helm plugin list
helm plugin uninstall <name>

# 2. 模板函数调试
helm template mychart ./mychart --debug

# 3. 模拟升级（dry-run）
helm upgrade my-release mychart --dry-run --debug

# 4. 跳值参数文件
helm install my-release mychart --values values-prod.yaml --values additional.yaml

# 5. Kubeconfig 指定
helm list --kubeconfig /path/to/kubeconfig
```

---

## 五、values 覆盖机制详解

### 5.1 values 覆盖优先级

```text
values 覆盖优先级（从低到高）：

  1. defaults 区域
     ↓
  2. values.yaml 文件
     ↓
  3. --values 指定文件
     ↓
  4. --set 指定参数
     ↓
  5. --set-string 指定字符串
     ↓
  6. --set-json 指定 JSON
     ↓（最高）
  7. --force-replace 强制覆盖
```

### 5.2 各种覆盖方式示例

```bash
# 方式 1：默认值
# 在 values.yaml 中定义
# replicaCount: 1

# 方式 2：--values 覆盖整个文件
helm install my-release mychart -f prod-values.yaml
# prod-values.yaml 中：
# replicaCount: 5
# image:
#   tag: 2.0.0

# 方式 3：--set 单个值
helm install my-release mychart --set replicaCount=5
helm install my-release mychart --set image.tag=2.0.0

# 方式 4：--set 嵌套值（点号分隔）
helm install my-release mychart --set image.tag=2.0.0
helm install my-release mychart --set ingress.enabled=true

# 方式 5：--set-string 强制字符串
helm install my-release mychart --set-string password="My P@ssw0rd"

# 方式 6：--set-json 设置复杂对象
helm install my-release mychart --set-json 'resources={"limits":{"cpu":"500m","memory":"1Gi"}}'

# 方式 7：--set-file 读取文件
echo "my-secret-value" > secret.txt
helm install my-release mychart --set-file secret=secret.txt
```

### 5.3 覆盖注意事项

```bash
# 1. 嵌套覆盖
# 原始：
# resources:
#   limits:
#     cpu: 100m
#     memory: 128Mi

# 覆盖 cpu（不影响 memory）：
helm install my-release mychart --set resources.limits.cpu=500m
# 结果：
# resources:
#   limits:
#     cpu: 500m  ← 覆盖
#     memory: 128Mi  ← 保持

# 2. 数组覆盖
# 原始：
# ingress:
#   hosts:
#   - host: a.example.com
#   - host: b.example.com

# 覆盖整个数组：
helm install my-release mychart --set ingress.hosts[0].host=new.example.com
# ⚠️ 危险：只覆盖第一个

# 3. 完整替换
# 推荐使用 --values 文件完整覆盖
# 避免数组索引陷阱
```

---

## 六、Chart 开发实战

### 6.1 创建第一个 Chart

```bash
# 1. 创建 Chart
helm create my-nginx
# 生成：
# my-nginx/
# ├── Chart.yaml
# ├── values.yaml
# ├── templates/
# │   ├── deployment.yaml
# │   ├── service.yaml
# │   ├── ingress.yaml
# │   ├── serviceaccount.yaml
# │   ├── hpa.yaml
# │   ├── _helpers.tpl
# │   └── NOTES.txt
# ├── .helmignore
# └── ci/
#     └── ingress-values.yaml

# 2. 验证 Chart
helm lint my-nginx
# 输出：1 chart(s) linted, 0 failed

# 3. 本地测试
helm install test-release my-nginx/ --dry-run
helm template my-release my-nginx/

# 4. 实际部署
helm install my-release my-nginx/
```

### 6.2 完整 Chart 实战（多组件应用）

```bash
# 场景：电商应用
# - frontend（Deployment + Service）
# - backend（Deployment + Service + ConfigMap）
# - database（StatefulSet + Service + Secret）
# - ingress（Ingress + TLS）
```

```yaml
# Chart.yaml
apiVersion: v2
name: e-commerce
version: 1.0.0
appVersion: "2.0.0"
description: E-commerce application chart
maintainers:
  - name: DevOps Team
    email: devops@example.com
dependencies:
- name: postgresql
  version: 14.x.x
  repository: https://charts.bitnami.com/bitnami
  condition: postgresql.enabled
- name: redis
  version: 18.x.x
  repository: https://charts.bitnami.com/bitnami
  condition: redis.enabled
```

```yaml
# values.yaml
# 默认配置
frontend:
  enabled: true
  replicaCount: 3
  image:
    repository: example/frontend
    tag: 1.0.0

backend:
  enabled: true
  replicaCount: 3
  image:
    repository: example/backend
    tag: 1.0.0
  env:
    - name: DB_HOST
      value: e-commerce-postgresql
    - name: REDIS_HOST
      value: e-commerce-redis

database:
  enabled: true
  postgresql:
    auth:
      username: app
      password: secret123
      database: ecomm
  persistence:
    enabled: true
    size: 10Gi

cache:
  enabled: true
  redis:
    auth:
      password: redispass

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: shop.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - hosts:
        - shop.example.com
      secretName: shop-tls
```

```yaml
# templates/frontend-deployment.yaml
{{- if .Values.frontend.enabled }}
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}-frontend
  labels:
    {{- include "e-commerce.labels" . | nindent 4 }}
    app: frontend
spec:
  replicas: {{ .Values.frontend.replicaCount }}
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: "{{ .Values.frontend.image.repository }}:{{ .Values.frontend.image.tag }}"
        ports:
        - containerPort: 80
---
{{- end }}
```

### 6.3 使用条件渲染和循环

```yaml
# templates/configmap.yaml
{{- if .Values.config.enabled }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "e-commerce.fullname" . }}-config
data:
  {{- range $key, $value := .Values.config.data }}
  {{ $key }}: {{ $value | quote }}
  {{- end }}
{{- end }}
---
# templates/ingress.yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "e-commerce.fullname" . }}
  annotations:
    {{- range $key, $value := .Values.ingress.annotations }}
    {{ $key }}: {{ $value | quote }}
    {{- end }}
spec:
  ingressClassName: {{ .Values.ingress.className }}
  {{- with .Values.ingress.tls }}
  tls:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  rules:
    {{- range .Values.ingress.hosts }}
    - host: {{ .host | quote }}
      http:
        paths:
          - path: {{ .paths[0].path }}
            pathType: {{ .paths[0].pathType | default "Prefix" }}
            backend:
              service:
                name: {{ include "e-commerce.fullname" $ }}
                port:
                  number: {{ $.Values.service.port }}
    {{- end }}
{{- end }}
```

---

## 七、Chart 仓库管理

### 7.1 Helm 仓库类型

```text
Helm 仓库类型：

  1. 公共仓库
     - Artifact Hub（artifacthub.io）
     - GitHub Pages（chartmuseum）
     - 各大云厂商仓库

  2. 私有仓库
     - Harbor
     - ChartMuseum
     - OCI Registry（与 Docker 镜像共享）

  3. 本地仓库
     - helm serve（开发测试）
     - 文件目录

  4. OCI 仓库（Helm 3 推荐）
     - 任意 OCI 兼容仓库
     - Harbor、Quay、GCR、ECR
```

### 7.2 添加公共仓库

```bash
# 1. 主流公共仓库
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add cert-manager https://charts.jetstack.io/cert-manager
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add prometheus https://prometheus-community.github.io/helm-charts

# 2. 查看
helm repo list

# 3. 搜索 Chart
helm search repo nginx
helm search repo ingress-nginx --version 4.0.0
```

### 7.3 部署 ChartMuseum（私有仓库）

```bash
# 1. 安装 ChartMuseum
helm install chartmuseum bitnami/chartmuseum \
  --namespace chartmuseum --create-namespace

# 2. 推送 Chart
curl --data-binary "@mychart-1.0.0.tgz" \
  http://chartmuseum:8080/api/charts

# 3. 添加仓库
helm repo add myrepo http://chartmuseum:8080
```

### 7.4 OCI 仓库（推荐）

```bash
# 1. 启用 OCI 支持
export HELM_EXPERIMENTAL_OCI=1

# 2. 推送 Chart 到 OCI 仓库
helm push mychart-1.0.0.tgz oci://registry.example.com/charts

# 3. 从 OCI 仓库安装
helm install my-release oci://registry.example.com/charts/mychart --version 1.0.0

# 4. Harbor OCI 仓库（推荐生产）
helm registry login registry.example.com
```

---

## 八、Chart 测试

### 8.1 helm lint 静态检查

```bash
# 基本检查
helm lint mychart

# 详细输出
helm lint mychart --strict

# 指定 values
helm lint mychart -f values-prod.yaml

# 输出示例
# [INFO] Chart.yaml: icon is recommended
# [INFO] values.yaml: profile not declared
# [WARNING] templates/deployment.yaml: container not found
```

### 8.2 helm template 渲染测试

```bash
# 1. 渲染到标准输出
helm template my-release mychart

# 2. 渲染到目录
helm template my-release mychart --output-dir ./rendered

# 3. 渲染到指定文件
helm template my-release mychart > all.yaml

# 4. 带 values 渲染
helm template my-release mychart -f prod-values.yaml > rendered.yaml

# 5. 调试模式
helm template my-release mychart --debug
# 输出所有模板变量
```

### 8.3 helm unittest 单元测试

```bash
# 安装 helm unittest 插件
helm plugin install https://github.com/helm-unittest/helm-unittest

# 创建测试文件
cat > tests/deployment_test.yaml <<EOF
suite: test deployment
templates:
  - deployment.yaml
release:
  name: my-release
  namespace: default
tests:
  - it: should create a deployment
    asserts:
      - isKind:
          of: Deployment
      - hasDocuments:
          count: 1
      - equal:
          path: spec.replicas
          value: 3
EOF

# 运行测试
helm unittest mychart
```

### 8.4 helm install --dry-run 模拟部署

```bash
# 1. 模拟部署（不实际安装）
helm install my-release mychart --dry-run
helm install my-release mychart --dry-run --debug

# 2. 模拟升级
helm upgrade my-release mychart --dry-run

# 3. 输出到文件
helm install my-release mychart --dry-run > dry-run.yaml
```

### 8.5 CI/CD 集成

```yaml
# .github/workflows/helm-test.yml
name: helm-test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: azure/setup-helm@v1
      with:
        version: v3.13.0
    - name: Lint
      run: helm lint mychart
    - name: Template
      run: |
        helm template my-release mychart > /tmp/rendered.yaml
        cat /tmp/rendered.yaml
    - name: Install Dry Run
      run: |
        helm install my-release mychart --dry-run > /tmp/install.yaml
        cat /tmp/install.yaml
    - name: Unittest
      run: helm unittest mychart
    - name: Trivy Scan
      uses: aquasecurity/trivy-action@master
      with:
        input-type: oci
        image-ref: 'mychart:1.0.0'
```

---

## 九、实战场景

### 9.1 场景 1：部署 WordPress + MySQL

```bash
# 1. 添加仓库
helm repo add bitnami https://charts.bitnami.com/bitnami

# 2. 查看 Chart
helm search repo wordpress

# 3. 自定义 values.yaml
cat > values.yaml <<EOF
mariadb:
  auth:
    rootPassword: secretpassword
  primary:
    persistence:
      enabled: true
      size: 8Gi

wordpress:
  username: admin
  password: mypassword
  email: admin@example.com
  persistence:
    enabled: true
    size: 10Gi
  service:
    type: LoadBalancer
EOF

# 4. 安装
helm install my-wp bitnami/wordpress -f values.yaml

# 5. 验证
kubectl get all -l app.kubernetes.io/name=wordpress

# 6. 升级
helm upgrade my-wp bitnami/wordpress -f new-values.yaml
```

### 9.2 场景 2：CI/CD 中使用 Helm

```yaml
# .gitlab-ci.yml
stages:
  - build
  - deploy

variables:
  CHART_DIR: mychart

build:
  stage: build
  script:
    - helm lint $CHART_DIR
    - helm package $CHART_DIR
    - cp $CHART_DIR-*.tgz ./chart.tgz
  artifacts:
    paths:
      - chart.tgz

deploy-staging:
  stage: deploy
  script:
    - helm upgrade my-release $CHART_DIR
        --install
        --namespace staging
        --set image.tag=$CI_COMMIT_SHA
        --wait
        --atomic
        --timeout 5m
  environment: staging
  only:
    - main

deploy-prod:
  stage: deploy
  script:
    - helm upgrade my-release $CHART_DIR
        --install
        --namespace production
        --set image.tag=$CI_COMMIT_SHA
        --wait
        --atomic
        --timeout 10m
  environment: production
  only:
    - tags
  when: $CI_COMMIT_TAG
```

### 9.3 场景 3：多环境管理

```bash
# 1. dev 环境
helm install my-release-dev mychart \
  --namespace dev \
  --values values-dev.yaml \
  --set replicaCount=1 \
  --set ingress.enabled=false

# 2. staging 环境
helm install my-release-staging mychart \
  --namespace staging \
  --values values-staging.yaml \
  --set replicaCount=3 \
  --set ingress.enabled=true

# 3. production 环境
helm install my-release-prod mychart \
  --namespace production \
  --values values-prod.yaml \
  --set replicaCount=5 \
  --set ingress.enabled=true

# 4. 查看所有环境
helm list -A
```

### 9.4 场景 4：Helm Hooks（升级前执行）

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: mychart-migration
  annotations:
    "helm.sh/hook": pre-upgrade
    "helm.sh/hook-weight": "-10"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migration
        image: my-app-migration:1.0
        command: ["sh", "-c", "migrate-database.sh"]
---
apiVersion: batch/v1
kind: Job
metadata:
  name: mychart-cleanup
  annotations:
    "helm.sh/hook": pre-delete
    "helm.sh/hook-weight": "0"
    "helm.sh/hook-delete-policy": before-hook-creation
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: cleanup
        image: my-app:1.0
        command: ["sh", "-c", "cleanup-database.sh"]
```

---

## 十、安全与最佳实践

### 10.1 Helm 安全最佳实践

```text
1. Chart 签名验证
   - helm install --verify
   - 使用 cosign 签名验证
   - 防止 Chart 篡改

2. values 文件管理
   - 不要将敏感信息提交到 Git
   - 使用 Sealed Secrets
   - 使用 External Secrets Operator
   - values 文件加密

3. 仓库安全
   - 私有仓库启用认证
   - HTTPS 传输
   - RBAC 控制访问

4. 版本控制
   - 固定 Chart 版本
   - 定期升级
   - 测试后再升级生产
```

### 10.2 values 文件加密

```bash
# 1. 安装 Sealed Secrets
helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system

# 2. 创建加密 secret
kubectl create secret generic my-secret \
  --from-literal=password=secret123 -n production -o yaml --dry-run=client | \
  kubeseal --format yaml > sealed-secret.yaml

# 3. 在 Chart 中引用
data:
  myPassword: "{{ .Values.secrets.myPassword | b64dec }}"
```

### 10.3 完整生产推荐

```yaml
# mychart/values-prod.yaml
replicaCount: 5

image:
  repository: my-registry.example.com/my-app
  tag: "1.2.3"            # 固定版本
  pullPolicy: IfNotPresent

resources:
  requests:
    cpu: 500m
    memory: 1Gi
  limits:
    cpu: 2000m
    memory: 4Gi

autoscaling:
  enabled: true
  minReplicas: 5
  maxReplicas: 50
  targetCPUUtilizationPercentage: 70

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: app.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - hosts:
        - app.example.com
      secretName: app-tls

secrets:
  enabled: true
  useExternalSecrets: true
  externalSecrets:
    backend: aws-secrets-manager
```

---

## 十一、核心要点速记

### Helm 三大核心

```text
1. Chart
   - K8s 资源的打包格式
   - 模板 + values + 元数据

2. Release
   - Chart 的运行实例
   - 一次 install 一个 release

3. Repository
   - Chart 仓库（公共/私有/OCI）
   - 类似 Docker Hub
```

### 核心命令速记

```bash
# Chart 管理
helm create mychart
helm lint mychart
helm template my-release mychart
helm package mychart

# Release 管理
helm install my-release mychart
helm list
helm status my-release
helm upgrade my-release mychart
helm rollback my-release 1
helm uninstall my-release

# 仓库管理
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo list
helm search repo nginx
helm repo update
```

### Chart 结构速记

```text
mychart/
├── Chart.yaml         # 元数据
├── values.yaml        # 默认配置
├── templates/         # 模板
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── _helpers.tpl
│   └── NOTES.txt
├── charts/            # 子 chart 依赖
├── crds/              # CRD 定义
└── .helmignore        # 排除文件
```

### values 覆盖优先级

```text
从低到高：
  defaults < values.yaml < --values < --set < --set-string < --set-json < --force-replace
```

### 最佳实践

```text
1. Chart 结构清晰
   - 模板和默认值分离
   - 命名规范统一
   - 包含 README 和 NOTES.txt

2. values 灵活
   - 合理默认值
   - 注释清晰
   - 支持多环境

3. 模板通用
   - 支持可选组件
   - 用条件渲染（if）
   - 用循环（range）

4. 测试覆盖
   - helm lint 静态检查
   - helm template 渲染测试
   - helm unittest 单元测试
   - 集成测试（kind 集群）

5. CI/CD 集成
   - GitOps 工作流
   - 自动化部署
   - 回滚机制
   - 蓝绿/金丝雀发布

6. 安全第一
   - Chart 签名验证
   - values 加密
   - 最小权限
   - 私有仓库认证
```

### 速记卡

- **Helm** = K8s 包管理工具（apt/yum/npm for K8s）
- **Chart** = K8s 资源打包（模板 + values + 元数据）
- **Release** = Chart 的运行实例
- **Repository** = Chart 仓库（公开/私有/OCI）
- **Helm 3** 不需要 Tiller（用 K8s 权限）
- **values 覆盖**：defaults < values.yaml < --values < --set
- **软驱逐 vs 硬驱逐**：evictionSoft（警告延迟）vs evictionHard（立即触发）
- **驱逐配置**：memory.available / nodefs.available / imagefs.available
- **Next**：CRI 容器运行时接口、CDI 设备插件接口